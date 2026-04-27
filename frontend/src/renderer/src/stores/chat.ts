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
  const pendingToolCalls = ref<Record<string, any[]>>({})
  const agentLoadingConversation = ref<Record<string, boolean>>({})
  const agentPendingConversationId = ref<Record<string, string | null>>({})
  const agentSwitchingAgent = ref<Record<string, boolean>>({})
  const agentLoadingDelayed = ref<Record<string, boolean>>({})
  const loadingDelayTimers = ref<Record<string, ReturnType<typeof setTimeout>>>({})

  const isStreaming = computed(() => agentStreaming.value[activeAgentId.value] || false)
  
  const isLoadingConversation = computed(() => {
    if (!activeAgentId.value) return false
    return agentLoadingDelayed.value[activeAgentId.value] || false
  })
  
  const pendingConversationId = computed({
    get: () => agentPendingConversationId.value[activeAgentId.value] || null,
    set: (value) => {
      if (activeAgentId.value) {
        agentPendingConversationId.value = {
          ...agentPendingConversationId.value,
          [activeAgentId.value]: value
        }
      }
    }
  })
  
  const isSwitchingAgent = computed(() => {
    if (!activeAgentId.value) return false
    return agentSwitchingAgent.value[activeAgentId.value] || false
  })
  
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
    
    if (agentLoadingConversation.value[activeAgentId.value]) {
      return
    }
    
    // 如果已经加载了这个对话，直接返回成功
    if (agentCurrentConversation.value[activeAgentId.value]?.id === convId) {
      return
    }
    
    agentPendingConversationId.value = {
      ...agentPendingConversationId.value,
      [activeAgentId.value]: convId
    }
    
    agentLoadingConversation.value = {
      ...agentLoadingConversation.value,
      [activeAgentId.value]: true
    }
    
    // 延迟 200ms 才显示加载状态，避免快速加载时的闪烁
    if (loadingDelayTimers.value[activeAgentId.value]) {
      clearTimeout(loadingDelayTimers.value[activeAgentId.value])
    }
    loadingDelayTimers.value = {
      ...loadingDelayTimers.value,
      [activeAgentId.value]: setTimeout(() => {
        if (agentLoadingConversation.value[activeAgentId.value]) {
          agentLoadingDelayed.value = {
            ...agentLoadingDelayed.value,
            [activeAgentId.value]: true
          }
        }
      }, 200)
    }
    
    try {
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
    } catch (error: any) {
      lastError.value = error.message || '加载对话失败'
      throw error
    } finally {
      agentLoadingConversation.value = {
        ...agentLoadingConversation.value,
        [activeAgentId.value]: false
      }
      agentLoadingDelayed.value = {
        ...agentLoadingDelayed.value,
        [activeAgentId.value]: false
      }
      agentPendingConversationId.value = {
        ...agentPendingConversationId.value,
        [activeAgentId.value]: null
      }
      // 清除定时器
      if (loadingDelayTimers.value[activeAgentId.value]) {
        clearTimeout(loadingDelayTimers.value[activeAgentId.value])
        loadingDelayTimers.value = {
          ...loadingDelayTimers.value,
          [activeAgentId.value]: undefined as any
        }
      }
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

  // Watch 必须在所有函数定义之后
  watch(() => activeAgentId.value, async (newAgentId, oldAgentId) => {
    if (newAgentId) {
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
      if (!agentLoadingConversation.value[newAgentId]) {
        agentLoadingConversation.value = {
          ...agentLoadingConversation.value,
          [newAgentId]: false
        }
      }
      if (!agentPendingConversationId.value[newAgentId]) {
        agentPendingConversationId.value = {
          ...agentPendingConversationId.value,
          [newAgentId]: null
        }
      }
      if (!agentSwitchingAgent.value[newAgentId]) {
        agentSwitchingAgent.value = {
          ...agentSwitchingAgent.value,
          [newAgentId]: false
        }
      }
      
      const existingMessages = agentMessages.value[newAgentId]
      const hasExistingMessages = existingMessages && existingMessages.length > 0
      const isCurrentlyStreaming = agentStreaming.value[newAgentId]
      
      // 只有在真正切换 Agent 时才显示切换状态
      const isActuallySwitching = newAgentId !== oldAgentId && oldAgentId !== undefined
      
      if (isActuallySwitching) {
        agentSwitchingAgent.value = {
          ...agentSwitchingAgent.value,
          [newAgentId]: true
        }
      }
      
      await fetchConversations(newAgentId)
      
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
      
      // 重置切换状态
      if (isActuallySwitching) {
        agentSwitchingAgent.value = {
          ...agentSwitchingAgent.value,
          [newAgentId]: false
        }
      }
    }
  }, { immediate: true })

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
    pendingToolCalls,
    isLoadingConversation,
    pendingConversationId,
    isSwitchingAgent,
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
