import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { ChatMessage, Conversation, ConversationListItem, ChatStreamChunk } from '../types'
import { useApi } from '../composables/useApi'
import { useAgentStore } from './agent'

export const useChatStore = defineStore('chat', () => {
  const { apiGet, apiPost, apiDelete, apiStream, checkHealth } = useApi()
  const agentStore = useAgentStore()

  const agentConversations = ref<Record<string, ConversationListItem[]>>({})
  const agentCurrentConversation = ref<Record<string, Conversation | null>>({})
  const agentMessages = ref<Record<string, ChatMessage[]>>({})
  const agentStreaming = ref<Record<string, boolean>>({})
  const agentAbortControllers = ref<Record<string, AbortController>>({})
  const isBackendReady = ref(false)
  const agentStreamingContent = ref<Record<string, string>>({})
  const lastError = ref<string | null>(null)
  const lastUsage = ref<{ promptTokens?: number; completionTokens?: number; totalTokens?: number } | null>(null)

  const isStreaming = computed(() => agentStreaming.value[activeAgentId.value] || false)
  
  const streamingContent = computed({
    get: () => agentStreamingContent.value[activeAgentId.value] || '',
    set: (value) => {
      if (activeAgentId.value) {
        agentStreamingContent.value[activeAgentId.value] = value
      }
    }
  })

  const activeAgentId = computed(() => agentStore.activeAgent?.id || '')

  const conversations = computed(() => agentConversations.value[activeAgentId.value] || [])
  
  const currentConversation = computed({
    get: () => agentCurrentConversation.value[activeAgentId.value] || null,
    set: (value) => {
      if (activeAgentId.value) {
        agentCurrentConversation.value = {
          ...agentCurrentConversation.value,
          [activeAgentId.value]: value
        }
      }
    }
  })

  const messages = computed({
    get: () => agentMessages.value[activeAgentId.value] || [],
    set: (value) => {
      if (activeAgentId.value) {
        agentMessages.value = {
          ...agentMessages.value,
          [activeAgentId.value]: value
        }
      }
    }
  })

  const currentMessages = computed(() => messages.value)

  watch(() => activeAgentId.value, async (newAgentId, oldAgentId) => {
    if (newAgentId) {
      // 初始化 Agent 的数据结构
      if (!agentConversations.value[newAgentId]) {
        agentConversations.value = {
          ...agentConversations.value,
          [newAgentId]: []
        }
      }
      if (!agentCurrentConversation.value[newAgentId]) {
        agentCurrentConversation.value = {
          ...agentCurrentConversation.value,
          [newAgentId]: null
        }
      }
      if (!agentMessages.value[newAgentId]) {
        agentMessages.value = {
          ...agentMessages.value,
          [newAgentId]: []
        }
      }
      if (!agentStreaming.value[newAgentId]) {
        agentStreaming.value = {
          ...agentStreaming.value,
          [newAgentId]: false
        }
      }
      if (!agentStreamingContent.value[newAgentId]) {
        agentStreamingContent.value = {
          ...agentStreamingContent.value,
          [newAgentId]: ''
        }
      }
      
      // 检查是否已有消息或正在流式输出
      const existingMessages = agentMessages.value[newAgentId]
      const hasExistingMessages = existingMessages && existingMessages.length > 0
      const isCurrentlyStreaming = agentStreaming.value[newAgentId]
      
      await fetchConversations(newAgentId)
      
      // 只有在没有现有消息且不在流式输出时才加载对话
      if (!hasExistingMessages && !isCurrentlyStreaming) {
        const currentConv = agentCurrentConversation.value[newAgentId]
        if (currentConv && currentConv.id) {
          try {
            await loadConversation(currentConv.id)
          } catch (error) {
            agentCurrentConversation.value = {
              ...agentCurrentConversation.value,
              [newAgentId]: null
            }
            agentMessages.value = {
              ...agentMessages.value,
              [newAgentId]: []
            }
          }
        } else if (agentConversations.value[newAgentId].length > 0) {
          const latestConv = agentConversations.value[newAgentId][0]
          if (latestConv && latestConv.id) {
            try {
              await loadConversation(latestConv.id)
            } catch (error) {
            }
          }
        }
      }
    }
  }, { immediate: true })

  const checkBackend = async () => {
    isBackendReady.value = await checkHealth()
    return isBackendReady.value
  }

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
    } catch {
      agentConversations.value = {
        ...agentConversations.value,
        [targetAgentId]: []
      }
    }
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
    agentCurrentConversation.value = {
      ...agentCurrentConversation.value,
      [targetAgentId]: conv
    }
    agentMessages.value = {
      ...agentMessages.value,
      [targetAgentId]: []
    }
    await fetchConversations(targetAgentId)
    return conv
  }

  const loadConversation = async (convId: string) => {
    if (!activeAgentId.value) return
    
    const conv = await apiGet<Conversation>(`/chat/conversations/${convId}`)
    agentCurrentConversation.value = {
      ...agentCurrentConversation.value,
      [activeAgentId.value]: conv
    }
    agentMessages.value = {
      ...agentMessages.value,
      [activeAgentId.value]: (conv.messages || []).map((m: any) => ({
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        role: m.role,
        content: m.content,
        timestamp: Date.now(),
      }))
    }
  }

  const deleteConversation = async (convId: string, agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return
    
    await apiDelete(`/chat/conversations/${convId}`)
    if (agentCurrentConversation.value[targetAgentId]?.id === convId) {
      agentCurrentConversation.value = {
        ...agentCurrentConversation.value,
        [targetAgentId]: null
      }
      agentMessages.value = {
        ...agentMessages.value,
        [targetAgentId]: []
      }
    }
    await fetchConversations(targetAgentId)
  }

  const cancelCurrentRequest = (agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return
    
    const controller = agentAbortControllers.value[targetAgentId]
    if (controller) {
      controller.abort()
      delete agentAbortControllers.value[targetAgentId]
    }
    
    agentStreaming.value[targetAgentId] = false
    const currentMsgs = agentMessages.value[targetAgentId] || []
    const lastIndex = currentMsgs.length - 1
    if (lastIndex >= 0 && currentMsgs[lastIndex]?.role === 'assistant' && !currentMsgs[lastIndex].done) {
      agentMessages.value = {
        ...agentMessages.value,
        [targetAgentId]: [...currentMsgs.slice(0, lastIndex), {
          ...currentMsgs[lastIndex],
          done: true,
          content: currentMsgs[lastIndex].content || '[已中断]'
        }]
      }
    }
    agentStreamingContent.value[targetAgentId] = ''
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
    const targetAgentId = options?.agentId || activeAgentId.value
    if (!targetAgentId) return
    
    if (agentStreaming.value[targetAgentId]) {
      cancelCurrentRequest(targetAgentId)
    }
    
    lastError.value = null

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    const currentMsgs = agentMessages.value[targetAgentId] || []
    agentMessages.value = {
      ...agentMessages.value,
      [targetAgentId]: [...currentMsgs, userMessage]
    }

    const apiMessages: { role: string; content: string }[] = []
    if (options?.systemPrompt) {
      apiMessages.push({ role: 'system', content: options.systemPrompt })
    }
    for (const msg of agentMessages.value[targetAgentId]) {
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
    const msgsWithUser = agentMessages.value[targetAgentId] || []
    agentMessages.value = {
      ...agentMessages.value,
      [targetAgentId]: [...msgsWithUser, assistantMessage]
    }
    
    agentStreaming.value[targetAgentId] = true
    agentStreamingContent.value[targetAgentId] = ''

    let convId = agentCurrentConversation.value[targetAgentId]?.id
    if (!convId) {
      const conv = await createConversation(
        content.slice(0, 30),
        targetAgentId,
        options?.model,
        options?.provider
      )
      convId = conv?.id
    }

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

    if (targetAgentId) {
      requestBody.agent_id = targetAgentId
    }

    // 创建独立的 AbortController
    const controller = new AbortController()
    agentAbortControllers.value[targetAgentId] = controller

    await apiStream(
      endpoint,
      requestBody,
      (chunk: ChatStreamChunk) => {
        agentStreamingContent.value[targetAgentId] += chunk.content
        const currentMsgList = agentMessages.value[targetAgentId] || []
        const lastIndex = currentMsgList.length - 1
        if (lastIndex >= 0 && currentMsgList[lastIndex]?.role === 'assistant') {
          agentMessages.value = {
            ...agentMessages.value,
            [targetAgentId]: [...currentMsgList.slice(0, lastIndex), {
              ...currentMsgList[lastIndex],
              content: agentStreamingContent.value[targetAgentId]
            }]
          }
        }
        if (chunk.usage) {
          lastUsage.value = chunk.usage
          const msgListForUsage = agentMessages.value[targetAgentId] || []
          const usageLastIndex = msgListForUsage.length - 1
          if (usageLastIndex >= 0 && msgListForUsage[usageLastIndex]?.role === 'assistant') {
            agentMessages.value = {
              ...agentMessages.value,
              [targetAgentId]: [...msgListForUsage.slice(0, usageLastIndex), {
                ...msgListForUsage[usageLastIndex],
                usage: chunk.usage
              }]
            }
          }
        }
      },
      async () => {
        delete agentAbortControllers.value[targetAgentId]
        const completeMsgList = agentMessages.value[targetAgentId] || []
        const completeLastIndex = completeMsgList.length - 1
        if (completeLastIndex >= 0 && completeMsgList[completeLastIndex]?.role === 'assistant') {
          agentMessages.value = {
            ...agentMessages.value,
            [targetAgentId]: [...completeMsgList.slice(0, completeLastIndex), {
              ...completeMsgList[completeLastIndex],
              done: true
            }]
          }
        }
        agentStreaming.value[targetAgentId] = false
        agentStreamingContent.value[targetAgentId] = ''
        await fetchConversations(targetAgentId)
        // 重新加载对话以确保消息同步
        const convId = agentCurrentConversation.value[targetAgentId]?.id
        if (convId) {
          try {
            const conv = await apiGet<Conversation>(`/chat/conversations/${convId}`)
            agentMessages.value = {
              ...agentMessages.value,
              [targetAgentId]: (conv.messages || []).map((m: any) => ({
                id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
                role: m.role,
                content: m.content,
                timestamp: Date.now(),
                done: true,
              }))
            }
          } catch (e) {
            console.error('Failed to reload conversation:', e)
          }
        }
      },
      (err: string) => {
        delete agentAbortControllers.value[targetAgentId]
        const errorMsgList = agentMessages.value[targetAgentId] || []
        const errorLastIndex = errorMsgList.length - 1
        if (errorLastIndex >= 0 && errorMsgList[errorLastIndex]?.role === 'assistant') {
          agentMessages.value = {
            ...agentMessages.value,
            [targetAgentId]: [...errorMsgList.slice(0, errorLastIndex), {
              ...errorMsgList[errorLastIndex],
              content: errorMsgList[errorLastIndex].content
                ? `${errorMsgList[errorLastIndex].content}\n\n[Error] ${err}`
                : `[Error] ${err}`,
              done: true
            }]
          }
        }
        agentStreaming.value[targetAgentId] = false
        agentStreamingContent.value[targetAgentId] = ''
        lastError.value = err
        fetchConversations(targetAgentId)
      },
      controller.signal
    )
  }

  const clearMessages = () => {
    if (activeAgentId.value) {
      agentMessages.value = {
        ...agentMessages.value,
        [activeAgentId.value]: []
      }
      agentCurrentConversation.value = {
        ...agentCurrentConversation.value,
        [activeAgentId.value]: null
      }
    }
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
    activeAgentId,
    checkBackend,
    fetchConversations,
    createConversation,
    loadConversation,
    deleteConversation,
    sendMessage,
    clearMessages,
    cancelCurrentRequest,
  }
})
