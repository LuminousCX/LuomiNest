import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { ChatMessage, ApiMessage, Conversation, ConversationListItem, ConversationSearchResult, TrashListItem, ChatStreamChunk } from '../types'
import { useApi } from '../composables/useApi'
import { useAgentStore } from './agent'
import { detectSearchIntent, extractSearchQuery } from '../utils/searchIntent'

export const useChatStore = defineStore('chat', () => {
  const { apiGet, apiPost, apiDelete, apiStream, checkHealth } = useApi()
  const agentStore = useAgentStore()

  const agentConversations = ref<Record<string, ConversationListItem[]>>({})
  const agentCurrentConvId = ref<Record<string, string | null>>({})

  const convMessages = ref<Record<string, ChatMessage[]>>({})
  const convStreaming = ref<Record<string, boolean>>({})
  const convAbortControllers = ref<Record<string, AbortController>>({})
  const convLoading = ref<Record<string, boolean>>({})
  const convData = ref<Record<string, Conversation>>({})

  // 搜索跳转：点击搜索结果时暂存关键词，加载完对话后滚动到匹配消息
  const pendingSearchKeyword = ref('')
  const searchScrollTarget = ref<{ convId: string; keyword: string } | null>(null)

  // 推荐问题：当前显示推荐的消息ID，只有最后一条AI消息才显示推荐
  const currentSuggestionMessageId = ref<string | null>(null)

  const isBackendReady = ref(false)
  const lastError = ref<string | null>(null)
  const lastUsage = ref<{ promptTokens?: number; completionTokens?: number; totalTokens?: number } | null>(null)
  const quotedMessage = ref<ChatMessage | null>(null)
  const trashItems = ref<TrashListItem[]>([])

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

  const currentMessages = computed(() => messages.value)

  const isConversationStreaming = (convId: string) => !!convStreaming.value[convId]

  const fetchConversations = async (agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return

    try {
      const query = `?agent_id=${targetAgentId}`
      const rawConvs = await apiGet<any[]>(`/chat/conversations${query}`)
      const convs: ConversationListItem[] = rawConvs.map((conv: any) => ({
        id: conv.id,
        title: conv.title,
        agent_id: conv.agent_id,
        model: conv.model,
        provider: conv.provider,
        last_message: conv.last_message,
        created_at: conv.created_at || conv.createdAt || '',
        updated_at: conv.updated_at || conv.updatedAt || '',
      }))
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

    // 加载对话时清除推荐
    currentSuggestionMessageId.value = null

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
      const mappedMessages: ChatMessage[] = []
      for (const m of (conv.messages || []) as ApiMessage[]) {
        const msg: ChatMessage = {
          id: m.id || `${Date.now()}-${Math.random().toString(36).slice(2)}`,
          role: m.role,
          content: m.content || '',
          timestamp: m.timestamp || Date.now(),
          done: true,
        }
        if (m.reasoning_content) {
          msg.reasoningContent = m.reasoning_content
        }
        if (m.interrupted || m.content === '[已中断]') {
          msg.interrupted = true
        }
        if (m.files) {
          msg.files = m.files
        } else if (m.file_name) {
          msg.files = [{ name: m.file_name, type: m.file_type }]
        }
        mappedMessages.push(msg)
      }
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
      title: title || '新对话',
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
    fetchTrash(targetAgentId)
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
    const currentMsgs = convMessages.value[targetConvId]
    if (currentMsgs) {
      const lastIndex = currentMsgs.length - 1
      if (lastIndex >= 0 && currentMsgs[lastIndex]?.role === 'assistant' && !currentMsgs[lastIndex].done) {
        const lastMsg = currentMsgs[lastIndex]
        lastMsg.done = true
        if (!lastMsg.content) lastMsg.content = '[已中断]'
        lastMsg.interrupted = true
      }
    }
  }

  const cancelCurrentRequest = (_agentId?: string) => {
    cancelConversationRequest()
  }

  const searchConversations = async (keyword: string, agentId?: string): Promise<ConversationSearchResult[]> => {
    if (!keyword.trim()) return []
    const targetAgentId = agentId || activeAgentId.value
    try {
      let query = `?keyword=${encodeURIComponent(keyword.trim())}`
      if (targetAgentId) query += `&agent_id=${targetAgentId}`
      return await apiGet<ConversationSearchResult[]>(`/chat/conversations/search${query}`)
    } catch (error) {
      console.warn('[ChatStore] Search failed:', error)
      return []
    }
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
      systemPrompt?: string
      fileContent?: string
      fileType?: string
      fileName?: string
      _preserveVersions?: any[]
    }
  ) => {
    const targetAgentId = options?.agentId || activeAgentId.value
    if (!targetAgentId) return

    // 发送消息时立即清除推荐
    currentSuggestionMessageId.value = null

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
      content: content,
      timestamp: Date.now(),
      files: options?.fileContent && options?.fileName ? [{ name: options.fileName, type: options.fileType, content: options.fileContent }] : undefined,
      quote: quotedMessage.value ? (() => {
        const qm = quotedMessage.value
        let quoteText = qm.content || ''
        // 如果消息内容为空但有文件，使用文件信息作为引用内容
        if (!quoteText && qm.files && qm.files.length > 0) {
          quoteText = qm.files.map(f => f.name || f.content?.slice(0, 200) || '').filter(Boolean).join('\n')
        }
        return {
          id: qm.id,
          role: qm.role,
          content: quoteText.slice(0, 500),
        }
      })() : undefined,
    }
    quotedMessage.value = null
    convMessages.value = {
      ...convMessages.value,
      [convId]: [...(convMessages.value[convId] || []), userMessage]
    }

    const assistantMessage: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      reasoningContent: '',
      timestamp: Date.now(),
      done: false,
      versions: options?._preserveVersions || undefined,
      activeVersion: options?._preserveVersions ? options._preserveVersions.length : undefined,
    }
    convMessages.value = {
      ...convMessages.value,
      [convId]: [...convMessages.value[convId], assistantMessage]
    }

    convStreaming.value = { ...convStreaming.value, [convId]: true }

    const apiMessages: { role: string; content: string }[] = []
    for (const msg of convMessages.value[convId]) {
      if (msg.role === 'system') continue
      if (msg.role === 'assistant' && !msg.done) continue
      let msgContent = msg.content
      if (msg.quote) {
        const quoteLabel = msg.quote.role === 'assistant' ? '助手' : '用户'
        const quoteContent = msg.quote.content.slice(0, 1000)
        msgContent = `[引用了${quoteLabel}的消息]\n${quoteContent}\n\n${msgContent}`
      }
      apiMessages.push({ role: msg.role, content: msgContent })
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

    if (options?.fileContent) {
      requestBody.file_content = options.fileContent
      if (options.fileName) requestBody.file_name = options.fileName
      if (options.fileType) requestBody.file_type = options.fileType
    }

    // 搜索意图检测：如果用户消息需要联网搜索，先调用内置浏览器搜索
    try {
      const searchNeeded = await detectSearchIntent(content)
      if (searchNeeded) {
        const searchQuery = extractSearchQuery(content)
        const searchResults = await window.api.browserSearch.search(searchQuery)
        if (searchResults && searchResults.length > 0) {
          requestBody.search_results = searchResults.map((r: any) =>
            `${r.title}: ${r.snippet}`
          ).join('\n')
        }
      }
    } catch (err) {
      console.warn('[ChatStore] Browser search failed, continuing without search results:', err)
    }

    const controller = new AbortController()
    convAbortControllers.value = { ...convAbortControllers.value, [convId]: controller }

    const streamingConvId = convId

    await apiStream(
      endpoint,
      requestBody,
      (chunk: ChatStreamChunk) => {
        const currentMsgList = convMessages.value[streamingConvId]
        if (!currentMsgList) return
        const lastIndex = currentMsgList.length - 1
        if (lastIndex >= 0 && currentMsgList[lastIndex]?.role === 'assistant') {
          const updatedMsg: ChatMessage = {
            ...currentMsgList[lastIndex],
            content: newContent,
            reasoningContent: newReasoning,
          }
          // 如果 done 事件中携带了推荐问题，写入消息
          if (chunk.done && chunk.suggested_questions && chunk.suggested_questions.length > 0) {
            updatedMsg.suggestedQuestions = chunk.suggested_questions
          }
          convMessages.value = {
            ...convMessages.value,
            [streamingConvId]: [...currentMsgList.slice(0, lastIndex), updatedMsg]
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
          const completedMsg: ChatMessage = {
            ...completeMsgList[completeLastIndex],
            done: true
          }
          convMessages.value = {
            ...convMessages.value,
            [streamingConvId]: [...completeMsgList.slice(0, completeLastIndex), completedMsg]
          }
          // 只有这条消息有推荐问题时，才设置当前推荐消息ID
          if (completedMsg.suggestedQuestions && completedMsg.suggestedQuestions.length > 0) {
            currentSuggestionMessageId.value = completedMsg.id
          }
        }
        convStreaming.value = { ...convStreaming.value, [streamingConvId]: false }
        await fetchConversations(targetAgentId)
      },
      (err: string) => {
        const newControllers = { ...convAbortControllers.value }
        delete newControllers[streamingConvId]
        convAbortControllers.value = newControllers

        const errorMsgList = convMessages.value[streamingConvId]
        if (errorMsgList) {
          const errorLastIndex = errorMsgList.length - 1
          if (errorLastIndex >= 0 && errorMsgList[errorLastIndex]?.role === 'assistant') {
            const lastMsg = errorMsgList[errorLastIndex]
            lastMsg.content = lastMsg.content
              ? `${lastMsg.content}\n\n[Error] ${err}`
              : `[Error] ${err}`
            lastMsg.done = true
          }
        }
        convStreaming.value = { ...convStreaming.value, [streamingConvId]: false }
        lastError.value = err
        fetchConversations(targetAgentId)
      },
      controller.signal
    )
  }

  const switchVersion = (convId: string, messageId: string, versionIndex: number) => {
    const msgs = convMessages.value[convId]
    if (!msgs) return
    const idx = msgs.findIndex(m => m.id === messageId)
    if (idx === -1) return
    const msg = msgs[idx]
    if (!msg.versions || versionIndex < 0 || versionIndex >= msg.versions.length) return
    const v = msg.versions[versionIndex]
    const updated: ChatMessage = {
      ...msg,
      content: v.content,
      reasoningContent: v.reasoningContent,
      model: v.model,
      provider: v.provider,
      activeVersion: versionIndex,
    }
    convMessages.value = {
      ...convMessages.value,
      [convId]: [...msgs.slice(0, idx), updated, ...msgs.slice(idx + 1)]
    }
  }

  const fetchTrash = async (agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return

    try {
      const query = `?agent_id=${targetAgentId}`
      trashItems.value = await apiGet<TrashListItem[]>(`/chat/trash${query}`)
    } catch (error) {
      console.warn('[ChatStore] Failed to fetch trash:', error)
      trashItems.value = []
    }
  }

  const batchSoftDelete = async (convIds: string[], agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId || convIds.length === 0) return

    try {
      await apiPost(`/chat/conversations/batch-delete`, {
        ids: convIds,
        agent_id: targetAgentId,
      })
      await fetchConversations(targetAgentId)
    } catch (error) {
      console.warn('[ChatStore] Batch soft delete failed:', error)
    }
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
    const newData = { ...convData.value }
    const newLoading = { ...convLoading.value }

    for (const convId of keysToDelete) {
      delete newMessages[convId]
      delete newStreaming[convId]
      delete newData[convId]
      delete newLoading[convId]
    }

    convMessages.value = newMessages
    convStreaming.value = newStreaming
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
    lastError,
    lastUsage,
    activeAgentId,
    convStreaming,
    convMessages,
    currentSuggestionMessageId,
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
    searchConversations,
    pendingSearchKeyword,
    searchScrollTarget,
    quotedMessage,
    trashItems,
    switchVersion,
    fetchTrash,
    batchSoftDelete,
  }
})
