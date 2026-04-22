import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ChatMessage, Conversation, ConversationListItem, ChatStreamChunk } from '../types'
import { useApi } from '../composables/useApi'

export const useChatStore = defineStore('chat', () => {
  const { apiGet, apiPost, apiDelete, apiStream, checkHealth } = useApi()

  const conversations = ref<ConversationListItem[]>([])
  const currentConversation = ref<Conversation | null>(null)
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const isBackendReady = ref(false)
  const streamingContent = ref('')
  const lastError = ref<string | null>(null)
  const lastUsage = ref<{ promptTokens?: number; completionTokens?: number; totalTokens?: number } | null>(null)

  const currentMessages = computed(() => messages.value)

  const checkBackend = async () => {
    isBackendReady.value = await checkHealth()
    return isBackendReady.value
  }

  const fetchConversations = async (agentId?: string) => {
    try {
      const query = agentId ? `?agent_id=${agentId}` : ''
      conversations.value = await apiGet<ConversationListItem[]>(`/chat/conversations${query}`)
    } catch {
      conversations.value = []
    }
  }

  const createConversation = async (title?: string, agentId?: string, model?: string, provider?: string) => {
    const conv = await apiPost<Conversation>('/chat/conversations', {
      title: title || 'New Conversation',
      agent_id: agentId,
      model,
      provider,
    })
    currentConversation.value = conv
    messages.value = []
    await fetchConversations(agentId)
    return conv
  }

  const loadConversation = async (convId: string) => {
    const conv = await apiGet<Conversation>(`/chat/conversations/${convId}`)
    currentConversation.value = conv
    messages.value = (conv.messages || []).map((m: any) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      role: m.role,
      content: m.content,
      timestamp: Date.now(),
    }))
  }

  const deleteConversation = async (convId: string, agentId?: string) => {
    await apiDelete(`/chat/conversations/${convId}`)
    if (currentConversation.value?.id === convId) {
      currentConversation.value = null
      messages.value = []
    }
    await fetchConversations(agentId)
  }

  const sendMessage = async (
    content: string,
    options?: {
      model?: string
      provider?: string
      temperature?: number
      maxTokens?: number
      topP?: number
      systemPrompt?: string
      agentId?: string
    }
  ) => {
    lastError.value = null

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    messages.value.push(userMessage)

    const apiMessages: { role: string; content: string }[] = []
    if (options?.systemPrompt) {
      apiMessages.push({ role: 'system', content: options.systemPrompt })
    }
    for (const msg of messages.value) {
      if (msg.role === 'system' && !options?.systemPrompt) continue
      if (msg.role === 'assistant' && !msg.done) continue
      apiMessages.push({ role: msg.role, content: msg.content })
    }

    const assistantMessage: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      done: false,
    }
    messages.value.push(assistantMessage)
    isStreaming.value = true
    streamingContent.value = ''

    const convId = currentConversation.value?.id
    const endpoint = convId
      ? `/chat/conversations/${convId}/messages`
      : '/chat/completions'

    const requestBody: any = {
      messages: apiMessages,
      model: options?.model,
      provider: options?.provider,
      temperature: options?.temperature,
      max_tokens: options?.maxTokens,
      top_p: options?.topP,
      stream: true,
    }

    if (options?.agentId) {
      requestBody.agent_id = options.agentId
    }

    await apiStream(
      endpoint,
      requestBody,
      (chunk: ChatStreamChunk) => {
        streamingContent.value += chunk.content
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          lastMsg.content = streamingContent.value
        }
        if (chunk.usage) {
          lastUsage.value = chunk.usage
          const lastMsgRef = messages.value[messages.value.length - 1]
          if (lastMsgRef && lastMsgRef.role === 'assistant') {
            lastMsgRef.usage = chunk.usage
          }
        }
      },
      () => {
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          lastMsg.done = true
        }
        isStreaming.value = false
        streamingContent.value = ''
      },
      (err: string) => {
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          lastMsg.content = lastMsg.content
            ? `${lastMsg.content}\n\n[Error] ${err}`
            : `[Error] ${err}`
          lastMsg.done = true
        }
        isStreaming.value = false
        streamingContent.value = ''
        lastError.value = err
      }
    )
  }

  const clearMessages = () => {
    messages.value = []
    currentConversation.value = null
    lastError.value = null
  }

  return {
    conversations,
    currentConversation,
    messages,
    currentMessages,
    isStreaming,
    isBackendReady,
    streamingContent,
    lastError,
    lastUsage,
    checkBackend,
    fetchConversations,
    createConversation,
    loadConversation,
    deleteConversation,
    sendMessage,
    clearMessages,
  }
})
