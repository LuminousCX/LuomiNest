import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { ChatMessage, Conversation, ConversationListItem, ChatStreamChunk } from '../types'
import { useApi } from '../composables/useApi'
import { useAgentStore } from './agent'

export const useChatStore = defineStore('chat', () => {
  const { apiGet, apiPost, apiDelete, apiStream, checkHealth } = useApi()
  const agentStore = useAgentStore()

  // 按agentId隔离存储对话状态
  const agentConversations = ref<Record<string, ConversationListItem[]>>({})
  const agentCurrentConversation = ref<Record<string, Conversation | null>>({})
  const agentMessages = ref<Record<string, ChatMessage[]>>({})
  const agentStreaming = ref<Record<string, boolean>>({})
  const isBackendReady = ref(false)
  const agentStreamingContent = ref<Record<string, string>>({})
  const lastError = ref<string | null>(null)
  const lastUsage = ref<{ promptTokens?: number; completionTokens?: number; totalTokens?: number } | null>(null)

  // 当前激活的agent的streaming状态
  const isStreaming = computed(() => agentStreaming.value[activeAgentId.value] || false)
  
  // 当前激活的agent的streaming内容
  const streamingContent = computed({
    get: () => agentStreamingContent.value[activeAgentId.value] || '',
    set: (value) => {
      if (activeAgentId.value) {
        agentStreamingContent.value[activeAgentId.value] = value
      }
    }
  })

  // 当前激活的agentId
  const activeAgentId = computed(() => agentStore.activeAgent?.id || '')

  // 当前agent的对话列表
  const conversations = computed(() => agentConversations.value[activeAgentId.value] || [])
  
  // 当前agent的当前对话
  const currentConversation = computed({
    get: () => agentCurrentConversation.value[activeAgentId.value] || null,
    set: (value) => {
      if (activeAgentId.value) {
        agentCurrentConversation.value[activeAgentId.value] = value
      }
    }
  })

  // 当前agent的消息列表 - 确保正序返回
  const messages = computed({
    get: () => agentMessages.value[activeAgentId.value] || [],
    set: (value) => {
      if (activeAgentId.value) {
        agentMessages.value[activeAgentId.value] = value
      }
    }
  })

  const currentMessages = computed(() => messages.value)

  // 监听activeAgent变化，切换对话状态
  watch(() => activeAgentId.value, async (newAgentId, oldAgentId) => {
    if (newAgentId) {
      // 确保新agent有对应的存储
      if (!agentConversations.value[newAgentId]) {
        agentConversations.value[newAgentId] = []
      }
      if (!agentCurrentConversation.value[newAgentId]) {
        agentCurrentConversation.value[newAgentId] = null
      }
      if (!agentMessages.value[newAgentId]) {
        agentMessages.value[newAgentId] = []
      }
      if (!agentStreaming.value[newAgentId]) {
        agentStreaming.value[newAgentId] = false
      }
      if (!agentStreamingContent.value[newAgentId]) {
        agentStreamingContent.value[newAgentId] = ''
      }
      
      // 加载该agent的对话历史
      await fetchConversations(newAgentId)
      
      // 如果该agent有当前对话，加载其消息
      const currentConv = agentCurrentConversation.value[newAgentId]
      if (currentConv && currentConv.id) {
        try {
          await loadConversation(currentConv.id)
        } catch (error) {
          // 如果加载失败，可能是对话已被删除，重置为null
          agentCurrentConversation.value[newAgentId] = null
          agentMessages.value[newAgentId] = []
        }
      } else if (agentConversations.value[newAgentId].length > 0) {
        // 如果没有当前对话但有历史对话，加载最新的一个
        const latestConv = agentConversations.value[newAgentId][0]
        if (latestConv && latestConv.id) {
          try {
            await loadConversation(latestConv.id)
          } catch (error) {
            // 如果加载失败，忽略
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
      agentConversations.value[targetAgentId] = await apiGet<ConversationListItem[]>(`/chat/conversations${query}`)
    } catch {
      agentConversations.value[targetAgentId] = []
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
    agentCurrentConversation.value[targetAgentId] = conv
    // 修复：异步状态捕获问题 - 使用新数组替换原数组
    agentMessages.value[targetAgentId] = []
    await fetchConversations(targetAgentId)
    return conv
  }

  const loadConversation = async (convId: string) => {
    if (!activeAgentId.value) return
    
    const conv = await apiGet<Conversation>(`/chat/conversations/${convId}`)
    agentCurrentConversation.value[activeAgentId.value] = conv
    // 修复：异步状态捕获问题 - 使用新数组替换原数组，确保正序
    agentMessages.value[activeAgentId.value] = (conv.messages || []).map((m: any) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      role: m.role,
      content: m.content,
      timestamp: Date.now(),
    }))
  }

  const deleteConversation = async (convId: string, agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return
    
    await apiDelete(`/chat/conversations/${convId}`)
    if (agentCurrentConversation.value[targetAgentId]?.id === convId) {
      agentCurrentConversation.value[targetAgentId] = null
      // 修复：异步状态捕获问题 - 使用新数组替换原数组
      agentMessages.value[targetAgentId] = []
    }
    await fetchConversations(targetAgentId)
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
    
    lastError.value = null

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    // 修复：异步状态捕获问题 - 使用新数组替换原数组，确保消息追加到末尾
    const currentMsgs = agentMessages.value[targetAgentId] || []
    agentMessages.value[targetAgentId] = [...currentMsgs, userMessage]

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
    // 修复：异步状态捕获问题 - 使用新数组替换原数组，确保消息追加到末尾
    const msgsWithUser = agentMessages.value[targetAgentId] || []
    agentMessages.value[targetAgentId] = [...msgsWithUser, assistantMessage]
    
    agentStreaming.value[targetAgentId] = true
    agentStreamingContent.value[targetAgentId] = ''

    let convId = agentCurrentConversation.value[targetAgentId]?.id
    // 如果没有当前对话，创建一个新的
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

    await apiStream(
      endpoint,
      requestBody,
      (chunk: ChatStreamChunk) => {
        agentStreamingContent.value[targetAgentId] += chunk.content
        // 修复：异步状态捕获问题 - 使用新数组替换原数组
        const currentMsgList = agentMessages.value[targetAgentId] || []
        const lastIndex = currentMsgList.length - 1
        if (lastIndex >= 0 && currentMsgList[lastIndex]?.role === 'assistant') {
          const updatedMsgs = [...currentMsgList]
          updatedMsgs[lastIndex] = {
            ...updatedMsgs[lastIndex],
            content: agentStreamingContent.value[targetAgentId]
          }
          agentMessages.value[targetAgentId] = updatedMsgs
        }
        if (chunk.usage) {
          lastUsage.value = chunk.usage
          // 修复：异步状态捕获问题 - 使用新数组替换原数组
          const msgListForUsage = agentMessages.value[targetAgentId] || []
          const usageLastIndex = msgListForUsage.length - 1
          if (usageLastIndex >= 0 && msgListForUsage[usageLastIndex]?.role === 'assistant') {
            const updatedMsgsWithUsage = [...msgListForUsage]
            updatedMsgsWithUsage[usageLastIndex] = {
              ...updatedMsgsWithUsage[usageLastIndex],
              usage: chunk.usage
            }
            agentMessages.value[targetAgentId] = updatedMsgsWithUsage
          }
        }
      },
      () => {
        // 修复：异步状态捕获问题 - 使用新数组替换原数组
        const completeMsgList = agentMessages.value[targetAgentId] || []
        const completeLastIndex = completeMsgList.length - 1
        if (completeLastIndex >= 0 && completeMsgList[completeLastIndex]?.role === 'assistant') {
          const completedMsgs = [...completeMsgList]
          completedMsgs[completeLastIndex] = {
            ...completedMsgs[completeLastIndex],
            done: true
          }
          agentMessages.value[targetAgentId] = completedMsgs
        }
        agentStreaming.value[targetAgentId] = false
        agentStreamingContent.value[targetAgentId] = ''
        // 修复：历史记录实时更新 - 发送消息后立即更新历史记录
        fetchConversations(targetAgentId)
        // 注意：不再调用 loadConversation，避免重新加载导致消息重复
      },
      (err: string) => {
        // 修复：异步状态捕获问题 - 使用新数组替换原数组
        const errorMsgList = agentMessages.value[targetAgentId] || []
        const errorLastIndex = errorMsgList.length - 1
        if (errorLastIndex >= 0 && errorMsgList[errorLastIndex]?.role === 'assistant') {
          const errorUpdatedMsgs = [...errorMsgList]
          errorUpdatedMsgs[errorLastIndex] = {
            ...errorUpdatedMsgs[errorLastIndex],
            content: errorUpdatedMsgs[errorLastIndex].content
              ? `${errorUpdatedMsgs[errorLastIndex].content}\n\n[Error] ${err}`
              : `[Error] ${err}`,
            done: true
          }
          agentMessages.value[targetAgentId] = errorUpdatedMsgs
        }
        agentStreaming.value[targetAgentId] = false
        agentStreamingContent.value[targetAgentId] = ''
        lastError.value = err
        // 修复：历史记录实时更新 - 发送消息后立即更新历史记录
        fetchConversations(targetAgentId)
      }
    )
  }

  const clearMessages = () => {
    if (activeAgentId.value) {
      // 修复：异步状态捕获问题 - 使用新数组替换原数组
      agentMessages.value[activeAgentId.value] = []
      agentCurrentConversation.value[activeAgentId.value] = null
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
  }
})
