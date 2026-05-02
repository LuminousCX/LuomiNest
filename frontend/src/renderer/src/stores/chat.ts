import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { ChatMessage, Conversation, ConversationListItem, ChatStreamChunk } from '../types'
import { useApi } from '../composables/useApi'
import { useAgentStore } from './agent'

export const useChatStore = defineStore('chat', () => {
  const { apiGet, apiPost, apiDelete, apiStream, checkHealth } = useApi()
  const agentStore = useAgentStore()

  const agentConversations = ref<Record<string, ConversationListItem[]>>({})
  const agentCurrentConvId = ref<Record<string, string | null>>({})

  const convMessages = ref<Record<string, ChatMessage[]>>({})
  const convStreaming = ref<Record<string, boolean>>({})
  const convAbortControllers = ref<Record<string, AbortController>>({})
  const convStreamingContent = ref<Record<string, string>>({})
  const convLoading = ref<Record<string, boolean>>({})
  const convData = ref<Record<string, Conversation>>({})

  const isBackendReady = ref(false)
  const lastError = ref<string | null>(null)
  const lastUsage = ref<{ promptTokens?: number; completionTokens?: number; totalTokens?: number } | null>(null)

  const activeAgentId = computed(() => agentStore.activeAgent?.id || '')

  const currentConvId = computed(() => agentCurrentConvId.value[activeAgentId.value] || '')

  const conversations = computed(() => agentConversations.value[activeAgentId.value] || [])

  const currentConversation = computed(() => {
    const convId = currentConvId.value
    if (!convId) return null
    return convData.value[convId] || null
  })

  const messages = computed(() => convMessages.value[currentConvId.value] || [])

  const isStreaming = computed(() => !!convStreaming.value[currentConvId.value])

  const isLoadingCurrentConversation = computed(() => !!convLoading.value[currentConvId.value])

  const streamingContent = computed({
    get: () => convStreamingContent.value[currentConvId.value] || '',
    set: (value) => {
      const convId = currentConvId.value
      if (convId) {
        convStreamingContent.value = { ...convStreamingContent.value, [convId]: value }
      }
    }
  })

  const currentMessages = computed(() => messages.value)

  const isConversationStreaming = (convId: string) => !!convStreaming.value[convId]

  const fetchConversations = async (agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return

    try {
      const query = `?agent_id=${targetAgentId}`
      const convs = await apiGet<ConversationListItem[]>(`/chat/conversations${query}`)
      agentConversations.value = {
        ...agentConversations.value,
        [targetAgentId]: convs
      }
    } catch (error: unknown) {
      console.warn('[ChatStore] Failed to fetch conversations:', error)
      agentConversations.value = {
        ...agentConversations.value,
        [targetAgentId]: []
      }
    }
  }

  const loadConversation = async (convId: string) => {
    if (!activeAgentId.value) return

    agentCurrentConvId.value = {
      ...agentCurrentConvId.value,
      [activeAgentId.value]: convId
    }

    if (convMessages.value[convId] && convMessages.value[convId].length > 0) {
      return
    }

    convLoading.value = { ...convLoading.value, [convId]: true }

    try {
      const conv = await apiGet<Conversation>(`/chat/conversations/${convId}`)
      convData.value = { ...convData.value, [convId]: conv }
      const mappedMessages = (conv.messages || []).map((m: any) => ({
        id: m.id || `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        role: m.role,
        content: m.content,
        timestamp: m.timestamp || Date.now(),
        done: true,
      }))
      convMessages.value = { ...convMessages.value, [convId]: mappedMessages }
    } catch (error) {
      if (!convMessages.value[convId]) {
        convMessages.value = { ...convMessages.value, [convId]: [] }
      }
    } finally {
      const newLoading = { ...convLoading.value }
      delete newLoading[convId]
      convLoading.value = newLoading
    }
  }

  const checkBackend = async () => {
    isBackendReady.value = await checkHealth()
    return isBackendReady.value
  }

  const createConversation = async (title?: string, agentId?: string, model?: string, provider?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return null

    const conv = await apiPost<Conversation>('/chat/conversations', {
      title: title || 'New Conversation',
      agent_id: targetAgentId,
      model,
      provider,
    })
    convData.value = { ...convData.value, [conv.id]: conv }
    agentCurrentConvId.value = { ...agentCurrentConvId.value, [targetAgentId]: conv.id }
    convMessages.value = { ...convMessages.value, [conv.id]: [] }
    await fetchConversations(targetAgentId)
    return conv
  }

  const deleteConversation = async (convId: string, agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return

    if (convStreaming.value[convId]) {
      cancelConversationRequest(convId)
    }

    await apiDelete(`/chat/conversations/${convId}`)

    const newMessages = { ...convMessages.value }
    delete newMessages[convId]
    convMessages.value = newMessages

    const newStreaming = { ...convStreaming.value }
    delete newStreaming[convId]
    convStreaming.value = newStreaming

    const newStreamingContent = { ...convStreamingContent.value }
    delete newStreamingContent[convId]
    convStreamingContent.value = newStreamingContent

    const newData = { ...convData.value }
    delete newData[convId]
    convData.value = newData

    const newLoading = { ...convLoading.value }
    delete newLoading[convId]
    convLoading.value = newLoading

    if (agentCurrentConvId.value[targetAgentId] === convId) {
      agentCurrentConvId.value = { ...agentCurrentConvId.value, [targetAgentId]: null }
    }

    await fetchConversations(targetAgentId)
  }

  const cancelConversationRequest = (convId?: string) => {
    const targetConvId = convId || currentConvId.value
    if (!targetConvId) return

    const controller = convAbortControllers.value[targetConvId]
    if (controller) {
      controller.abort()
      const newControllers = { ...convAbortControllers.value }
      delete newControllers[targetConvId]
      convAbortControllers.value = newControllers
    }

    convStreaming.value = { ...convStreaming.value, [targetConvId]: false }
    const currentMsgs = convMessages.value[targetConvId] || []
    const lastIndex = currentMsgs.length - 1
    if (lastIndex >= 0 && currentMsgs[lastIndex]?.role === 'assistant' && !currentMsgs[lastIndex].done) {
      convMessages.value = {
        ...convMessages.value,
        [targetConvId]: [...currentMsgs.slice(0, lastIndex), {
          ...currentMsgs[lastIndex],
          done: true,
          content: currentMsgs[lastIndex].content || '[已中断]'
        }]
      }
    }
    convStreamingContent.value = { ...convStreamingContent.value, [targetConvId]: '' }
  }

  const cancelCurrentRequest = (_agentId?: string) => {
    cancelConversationRequest()
  }

  const sendMessage = async (
    content: string,
    options?: {
      model?: string
      provider?: string
      temperature?: number
      maxTokens?: number
      topP?: number
      agentId?: string
    }
  ) => {
    const targetAgentId = options?.agentId || activeAgentId.value
    if (!targetAgentId) return

    let convId = agentCurrentConvId.value[targetAgentId]

    if (!convId) {
      const conv = await createConversation(
        content.slice(0, 30),
        targetAgentId,
        options?.model,
        options?.provider
      )
      convId = conv?.id || null
      if (!convId) return
    }

    if (convStreaming.value[convId]) {
      cancelConversationRequest(convId)
    }

    lastError.value = null

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    convMessages.value = {
      ...convMessages.value,
      [convId]: [...(convMessages.value[convId] || []), userMessage]
    }

    const assistantMessage: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      done: false,
    }
    convMessages.value = {
      ...convMessages.value,
      [convId]: [...convMessages.value[convId], assistantMessage]
    }

    convStreaming.value = { ...convStreaming.value, [convId]: true }
    convStreamingContent.value = { ...convStreamingContent.value, [convId]: '' }

    const apiMessages: { role: string; content: string }[] = []
    for (const msg of convMessages.value[convId]) {
      if (msg.role === 'system') continue
      if (msg.role === 'assistant' && !msg.done) continue
      apiMessages.push({ role: msg.role, content: msg.content })
    }

    const endpoint = `/chat/conversations/${convId}/messages`

    const requestBody: any = {
      messages: apiMessages,
      model: options?.model,
      provider: options?.provider,
      temperature: options?.temperature,
      max_tokens: options?.maxTokens,
      top_p: options?.topP,
      stream: true,
      timestamp: Date.now() / 1000,
    }

    if (targetAgentId) {
      requestBody.agent_id = targetAgentId
    }

    const controller = new AbortController()
    convAbortControllers.value = { ...convAbortControllers.value, [convId]: controller }

    const streamingConvId = convId

    await apiStream(
      endpoint,
      requestBody,
      (chunk: ChatStreamChunk) => {
        const prevContent = convStreamingContent.value[streamingConvId] || ''
        const newContent = prevContent + chunk.content
        convStreamingContent.value = { ...convStreamingContent.value, [streamingConvId]: newContent }

        const currentMsgList = convMessages.value[streamingConvId] || []
        const lastIndex = currentMsgList.length - 1
        if (lastIndex >= 0 && currentMsgList[lastIndex]?.role === 'assistant') {
          convMessages.value = {
            ...convMessages.value,
            [streamingConvId]: [...currentMsgList.slice(0, lastIndex), {
              ...currentMsgList[lastIndex],
              content: newContent
            }]
          }
        }
        if (chunk.usage) {
          lastUsage.value = chunk.usage
        }
      },
      async () => {
        const newControllers = { ...convAbortControllers.value }
        delete newControllers[streamingConvId]
        convAbortControllers.value = newControllers

        const completeMsgList = convMessages.value[streamingConvId] || []
        const completeLastIndex = completeMsgList.length - 1
        if (completeLastIndex >= 0 && completeMsgList[completeLastIndex]?.role === 'assistant') {
          convMessages.value = {
            ...convMessages.value,
            [streamingConvId]: [...completeMsgList.slice(0, completeLastIndex), {
              ...completeMsgList[completeLastIndex],
              done: true
            }]
          }
        }
        convStreaming.value = { ...convStreaming.value, [streamingConvId]: false }
        convStreamingContent.value = { ...convStreamingContent.value, [streamingConvId]: '' }
        await fetchConversations(targetAgentId)
      },
      (err: string) => {
        const newControllers = { ...convAbortControllers.value }
        delete newControllers[streamingConvId]
        convAbortControllers.value = newControllers

        const errorMsgList = convMessages.value[streamingConvId] || []
        const errorLastIndex = errorMsgList.length - 1
        if (errorLastIndex >= 0 && errorMsgList[errorLastIndex]?.role === 'assistant') {
          convMessages.value = {
            ...convMessages.value,
            [streamingConvId]: [...errorMsgList.slice(0, errorLastIndex), {
              ...errorMsgList[errorLastIndex],
              content: errorMsgList[errorLastIndex].content
                ? `${errorMsgList[errorLastIndex].content}\n\n[Error] ${err}`
                : `[Error] ${err}`,
              done: true
            }]
          }
        }
        convStreaming.value = { ...convStreaming.value, [streamingConvId]: false }
        convStreamingContent.value = { ...convStreamingContent.value, [streamingConvId]: '' }
        lastError.value = err
        fetchConversations(targetAgentId)
      },
      controller.signal
    )
  }

  const clearMessages = () => {
    agentCurrentConvId.value = { ...agentCurrentConvId.value, [activeAgentId.value]: null }
    lastError.value = null
  }

  const cleanupUnusedConversations = () => {
    const currentId = currentConvId.value
    const keysToDelete: string[] = []

    for (const convId of Object.keys(convMessages.value)) {
      if (convId === currentId) continue
      if (convStreaming.value[convId]) continue
      const msgs = convMessages.value[convId]
      if (!msgs || msgs.length === 0) {
        keysToDelete.push(convId)
      }
    }

    if (keysToDelete.length === 0) return

    const newMessages = { ...convMessages.value }
    const newStreaming = { ...convStreaming.value }
    const newStreamingContent = { ...convStreamingContent.value }
    const newData = { ...convData.value }
    const newLoading = { ...convLoading.value }

    for (const convId of keysToDelete) {
      delete newMessages[convId]
      delete newStreaming[convId]
      delete newStreamingContent[convId]
      delete newData[convId]
      delete newLoading[convId]
    }

    convMessages.value = newMessages
    convStreaming.value = newStreaming
    convStreamingContent.value = newStreamingContent
    convData.value = newData
    convLoading.value = newLoading
  }

  watch(() => activeAgentId.value, async (newAgentId) => {
    if (newAgentId) {
      if (!agentConversations.value[newAgentId]) {
        agentConversations.value = { ...agentConversations.value, [newAgentId]: [] }
      }

      await fetchConversations(newAgentId)

      const currentId = agentCurrentConvId.value[newAgentId]
      if (currentId) {
        if (!convMessages.value[currentId] || convMessages.value[currentId].length === 0) {
          await loadConversation(currentId)
        }
      } else if (agentConversations.value[newAgentId].length > 0) {
        const latestConv = agentConversations.value[newAgentId][0]
        if (latestConv?.id) {
          try {
            await loadConversation(latestConv.id)
          } catch (error) {
            console.warn(`[ChatStore] Failed to load latest conversation for agent ${newAgentId}:`, error)
          }
        }
      }
    }
  }, { immediate: true })

  return {
    conversations,
    currentConversation,
    currentConvId,
    messages,
    currentMessages,
    isStreaming,
    isBackendReady,
    isLoadingCurrentConversation,
    streamingContent,
    lastError,
    lastUsage,
    activeAgentId,
    convStreaming,
    checkBackend,
    fetchConversations,
    createConversation,
    loadConversation,
    deleteConversation,
    sendMessage,
    clearMessages,
    cleanupUnusedConversations,
    cancelCurrentRequest,
    cancelConversationRequest,
    isConversationStreaming,
  }
})
