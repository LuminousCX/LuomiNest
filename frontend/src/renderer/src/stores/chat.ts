import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { ChatMessage, ApiMessage, MessageVersion, Conversation, ConversationListItem, ConversationSearchResult, ChatStreamChunk } from '../types'

interface RawMessageVersion {
  content: string
  reasoning_content?: string
  reasoningContent?: string
  model?: string
  provider?: string
  suggested_questions?: string[]
  suggestedQuestions?: string[]
}

interface RawConversation {
  id: string
  title: string
  agent_id: string
  model?: string
  provider?: string
  last_message?: string
  created_at?: string
  createdAt?: string
  updated_at?: string
  updatedAt?: string
}
import { useApi } from '../composables/useApi'
import { useToast } from '../composables/useToast'
import { useAgentStore } from './agent'
import { useChatTrashStore } from './chat-trash'
import { detectSearchIntent, extractSearchQuery } from '../utils/searchIntent'
import { generateId } from '../utils/id'

export const useChatStore = defineStore('chat', () => {
  const { apiGet, apiPost, apiPatch, apiDelete, apiStream, checkHealth } = useApi()
  const agentStore = useAgentStore()
  const toast = useToast()

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
      const rawConvs = await apiGet<RawConversation[]>(`/chat/conversations${query}`)
      const convs: ConversationListItem[] = rawConvs.map((conv) => ({
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

  const loadConversation = async (convId: string, agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return

    // 切换对话前，通知后端对当前对话执行最终蒸馏
    const prevConvId = agentCurrentConvId.value[targetAgentId]
    if (prevConvId && prevConvId !== convId) {
      apiPost(`/chat/conversations/${prevConvId}/leave`).catch(() => {})
    }

    // 加载对话时清除推荐
    currentSuggestionMessageId.value = null

    agentCurrentConvId.value = {
      ...agentCurrentConvId.value,
      [targetAgentId]: convId
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
          id: m.id || generateId(),
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
        if (m.versions && Array.isArray(m.versions) && m.versions.length > 0) {
          msg.versions = (m.versions as RawMessageVersion[]).map((v) => ({
            content: v.content || '',
            reasoningContent: v.reasoning_content || v.reasoningContent || undefined,
            model: v.model || undefined,
            provider: v.provider || undefined,
            suggestedQuestions: v.suggested_questions || v.suggestedQuestions || undefined,
          }))
          msg.currentVersion = m.current_version ?? m.versions.length - 1
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
    const trashStore = useChatTrashStore()
    trashStore.fetchTrash(targetAgentId)
  }

  const renameConversation = async (convId: string, newTitle: string, agentId?: string): Promise<boolean> => {
    const targetAgentId = agentId || activeAgentId.value
    try {
      await apiPatch(`/chat/conversations/${convId}/rename`, { title: newTitle })
      // 更新本地缓存的对话数据
      if (convData.value[convId]) {
        convData.value = {
          ...convData.value,
          [convId]: { ...convData.value[convId], title: newTitle }
        }
      }
      // 刷新对话列表以更新标题
      if (targetAgentId) {
        await fetchConversations(targetAgentId)
      }
      return true
    } catch (error) {
      console.warn('[ChatStore] Failed to rename conversation:', error)
      return false
    }
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
      chatMode?: 'normal' | 'standard' | 'ultra'
      _preserveVersions?: MessageVersion[]
      onChunk?: (chunk: ChatStreamChunk) => void
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
      id: generateId('user'),
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
          role: (qm.role === 'user' || qm.role === 'assistant' ? qm.role : 'user') as 'user' | 'assistant',
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
      id: generateId('assistant'),
      role: 'assistant',
      content: '',
      reasoningContent: '',
      timestamp: Date.now(),
      done: false,
      versions: options?._preserveVersions || undefined,
      currentVersion: options?._preserveVersions ? options._preserveVersions.length : undefined,
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

    const requestBody: Record<string, unknown> = {
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

    if (options?.chatMode) {
      requestBody.chat_mode = options.chatMode
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
          requestBody.search_results = searchResults.map((r: { title: string; snippet: string }) =>
            `${r.title}: ${r.snippet}`
          ).join('\n')
        }
      }
    } catch (err) {
      console.warn('[ChatStore] Browser search failed, continuing without search results:', err)
    }

    // URL 检测：如果用户消息包含 URL，自动 fetch 页面内容
    try {
      const urlMatches = [...content.matchAll(/https?:\/\/[^\s<>"')\]]+/g)].map(m => m[0])
      const urlsToFetch = urlMatches.slice(0, 3)
      if (urlsToFetch.length > 0) {
        // 显示加载提示：在已有的空assistant占位消息上显示加载状态
        const currentMsgList = convMessages.value[convId]
        if (currentMsgList && currentMsgList.length > 0) {
          const lastIdx = currentMsgList.length - 1
          const lastMsg = currentMsgList[lastIdx]
          if (lastMsg?.role === 'assistant' && !lastMsg.done) {
            const fetchingMsg: ChatMessage = {
              ...lastMsg,
              content: urlsToFetch.length === 1
                ? '正在获取网页内容...'
                : `正在获取 ${urlsToFetch.length} 个网页内容...`,
            }
            convMessages.value = {
              ...convMessages.value,
              [convId]: [...currentMsgList.slice(0, lastIdx), fetchingMsg]
            }
          }
        }

        for (const url of urlsToFetch) {
          const pageContent = await window.api.browserSearch.fetchUrl(url)
          if (pageContent) {
            requestBody.search_results = (requestBody.search_results ? requestBody.search_results + '\n\n' : '') + `[网页内容: ${url}]\n${pageContent}`
          }
        }

        // 清空加载提示，让 stream 正常填充
        const msgListAfterFetch = convMessages.value[convId]
        if (msgListAfterFetch) {
          const lastIdx = msgListAfterFetch.length - 1
          if (lastIdx >= 0 && msgListAfterFetch[lastIdx]?.role === 'assistant' && !msgListAfterFetch[lastIdx].done) {
            const clearedMsg: ChatMessage = {
              ...msgListAfterFetch[lastIdx],
              content: '',
            }
            convMessages.value = {
              ...convMessages.value,
              [convId]: [...msgListAfterFetch.slice(0, lastIdx), clearedMsg]
            }
          }
        }
      }
    } catch (err) {
      console.warn('[ChatStore] Fetch URL failed, continuing without page content:', err)
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
            content: currentMsgList[lastIndex].content + (chunk.content || ''),
            reasoningContent: currentMsgList[lastIndex].reasoningContent + (chunk.reasoning_content || ''),
          }
          if (chunk.done) {
            console.log('[Regen] done chunk suggestions:', chunk.suggested_questions)
            if (chunk.suggested_questions && chunk.suggested_questions.length > 0) {
              updatedMsg.suggestedQuestions = chunk.suggested_questions
            }
          } else {
            updatedMsg.suggestedQuestions = undefined
          }
          convMessages.value = {
            ...convMessages.value,
            [streamingConvId]: [...currentMsgList.slice(0, lastIndex), updatedMsg]
          }
        }
        if (chunk.usage) {
          lastUsage.value = chunk.usage
        }
        options?.onChunk?.(chunk)
      },
      async () => {
        const newControllers = { ...convAbortControllers.value }
        delete newControllers[streamingConvId]
        convAbortControllers.value = newControllers

        const completeMsgList = convMessages.value[streamingConvId] || []
        const completeLastIndex = completeMsgList.length - 1
        if (completeLastIndex >= 0 && completeMsgList[completeLastIndex]?.role === 'assistant') {
          const lastMsg = completeMsgList[completeLastIndex]
          const completedMsg: ChatMessage = {
            ...lastMsg,
            done: true
          }
          if (lastMsg.versions && lastMsg.versions.length > 0) {
            const newVersion: MessageVersion = {
              content: lastMsg.content,
              reasoningContent: lastMsg.reasoningContent || undefined,
              model: lastMsg.model,
              provider: lastMsg.provider,
              suggestedQuestions: lastMsg.suggestedQuestions || undefined,
            }
            completedMsg.versions = [...lastMsg.versions, newVersion]
            completedMsg.currentVersion = completedMsg.versions.length - 1
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
            lastMsg.suggestedQuestions = undefined
          }
        }
        if (currentSuggestionMessageId.value && errorMsgList) {
          const found = errorMsgList.some((m: ChatMessage) => m.id === currentSuggestionMessageId.value)
          if (!found) currentSuggestionMessageId.value = null
        }
        convStreaming.value = { ...convStreaming.value, [streamingConvId]: false }
        lastError.value = err
        toast.error(`对话失败：${err}`)
        fetchConversations(targetAgentId)
      },
      controller.signal
    )
  }

  const switchVersion = async (convId: string, messageId: string, versionIndex: number) => {
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
      suggestedQuestions: v.suggestedQuestions,
      currentVersion: versionIndex,
    }

    convMessages.value = {
      ...convMessages.value,
      [convId]: [...msgs.slice(0, idx), updated, ...msgs.slice(idx + 1)]
    }

    if (updated.suggestedQuestions && updated.suggestedQuestions.length > 0) {
      currentSuggestionMessageId.value = messageId
    } else if (currentSuggestionMessageId.value === messageId) {
      currentSuggestionMessageId.value = null
    }

    try {
      await apiPatch(`/chat/conversations/${convId}/messages/version`, {
        message_id: messageId,
        current_version: versionIndex,
      })
    } catch (error) {
      console.warn('[ChatStore] Failed to persist version switch:', error)
    }
  }

  const regenerateMessage = async (messageId: string, options?: { onChunk?: (chunk: ChatStreamChunk) => void; convId?: string; agentId?: string }) => {
    const convId = options?.convId || currentConvId.value
    if (!convId) return
    const msgs = convMessages.value[convId]
    if (!msgs) return

    const aiIndex = msgs.findIndex(m => m.id === messageId)
    if (aiIndex === -1) return
    const aiMsg = msgs[aiIndex]

    const existingVersions: MessageVersion[] = aiMsg.versions && aiMsg.versions.length > 0
      ? [...aiMsg.versions]
      : [{
          content: aiMsg.content,
          reasoningContent: aiMsg.reasoningContent || undefined,
          model: aiMsg.model,
          provider: aiMsg.provider,
          suggestedQuestions: aiMsg.suggestedQuestions || undefined,
        }]

    const updatedMsgs = [...msgs.slice(0, aiIndex), ...msgs.slice(aiIndex + 1)]
    convMessages.value = {
      ...convMessages.value,
      [convId]: updatedMsgs
    }

    const lastExistingVersion = existingVersions.length > 0 ? existingVersions[existingVersions.length - 1] : null
    const assistantMessage: ChatMessage = {
      id: generateId('assistant'),
      role: 'assistant',
      content: '',
      reasoningContent: '',
      timestamp: Date.now(),
      done: false,
      suggestedQuestions: lastExistingVersion?.suggestedQuestions || aiMsg.suggestedQuestions,
      versions: existingVersions,
      currentVersion: existingVersions.length,
    }
    const newMsgs = [...updatedMsgs]
    newMsgs.splice(aiIndex, 0, assistantMessage)
    convMessages.value = {
      ...convMessages.value,
      [convId]: newMsgs
    }

    convStreaming.value = { ...convStreaming.value, [convId]: true }
    currentSuggestionMessageId.value = null

    const requestBody: Record<string, unknown> = {
      model: aiMsg.model || undefined,
      provider: aiMsg.provider || undefined,
      stream: true,
      versions: existingVersions,
    }

    const targetAgentId = options?.agentId || activeAgentId.value
    if (targetAgentId) {
      requestBody.agent_id = targetAgentId
    }

    const controller = new AbortController()
    convAbortControllers.value = { ...convAbortControllers.value, [convId]: controller }
    const streamingConvId = convId

    let streamDoneSuggestions: string[] | undefined = undefined

    await apiStream(
      `/chat/conversations/${convId}/regenerate`,
      requestBody,
      (chunk: ChatStreamChunk) => {
        const currentMsgList = convMessages.value[streamingConvId]
        if (!currentMsgList) return
        const lastIndex = currentMsgList.length - 1
        if (lastIndex >= 0 && currentMsgList[lastIndex]?.role === 'assistant') {
          const existing = currentMsgList[lastIndex]
          if (chunk.done && chunk.suggested_questions && chunk.suggested_questions.length > 0) {
            streamDoneSuggestions = chunk.suggested_questions
          }
          const updatedMsg: ChatMessage = {
            ...existing,
            content: existing.content + (chunk.content || ''),
            reasoningContent: existing.reasoningContent + (chunk.reasoning_content || ''),
            suggestedQuestions: streamDoneSuggestions ?? existing.suggestedQuestions,
          }
          convMessages.value = {
            ...convMessages.value,
            [streamingConvId]: [...currentMsgList.slice(0, lastIndex), updatedMsg]
          }
        }
        if (chunk.usage) {
          lastUsage.value = chunk.usage
        }
        options?.onChunk?.(chunk)
      },
      async () => {
        const newControllers = { ...convAbortControllers.value }
        delete newControllers[streamingConvId]
        convAbortControllers.value = newControllers

        const completeMsgList = convMessages.value[streamingConvId] || []
        const completeLastIndex = completeMsgList.length - 1
        if (completeLastIndex >= 0 && completeMsgList[completeLastIndex]?.role === 'assistant') {
          const lastMsg = completeMsgList[completeLastIndex]
          const completedMsg: ChatMessage = {
            ...lastMsg,
            done: true
          }
          if (lastMsg.versions && lastMsg.versions.length > 0) {
            const newVersion: MessageVersion = {
              content: lastMsg.content,
              reasoningContent: lastMsg.reasoningContent || undefined,
              model: lastMsg.model,
              provider: lastMsg.provider,
              suggestedQuestions: lastMsg.suggestedQuestions || undefined,
            }
            completedMsg.versions = [...lastMsg.versions, newVersion]
            completedMsg.currentVersion = completedMsg.versions.length - 1
          }
          // 明确设置推荐问题：如果流式回调中已更新就用新的，否则清除旧的（新版本尚未生成推荐问题）
          completedMsg.suggestedQuestions = lastMsg.suggestedQuestions || undefined
          convMessages.value = {
            ...convMessages.value,
            [streamingConvId]: [...completeMsgList.slice(0, completeLastIndex), completedMsg]
          }
          if (completedMsg.suggestedQuestions && completedMsg.suggestedQuestions.length > 0) {
            currentSuggestionMessageId.value = completedMsg.id
          }
        }
        convStreaming.value = { ...convStreaming.value, [streamingConvId]: false }
        if (targetAgentId) {
          await fetchConversations(targetAgentId)
        }
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
        toast.error(`重新生成失败：${err}`)
        if (targetAgentId) {
          fetchConversations(targetAgentId)
        }
      },
      controller.signal
    )
  }

  const clearMessages = (agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return
    agentCurrentConvId.value = { ...agentCurrentConvId.value, [targetAgentId]: null }
    lastError.value = null
  }

  const leaveCurrentConversation = async (convId: string) => {
    try {
      await apiPost(`/chat/conversations/${convId}/leave`)
    } catch (error) {
      console.warn('[ChatStore] Failed to leave conversation:', error)
    }
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
    agentConversations,
    convStreaming,
    convMessages,
    currentSuggestionMessageId,
    checkBackend,
    fetchConversations,
    createConversation,
    loadConversation,
    deleteConversation,
    renameConversation,
    sendMessage,
    clearMessages,
    leaveCurrentConversation,
    cleanupUnusedConversations,
    cancelCurrentRequest,
    cancelConversationRequest,
    isConversationStreaming,
    searchConversations,
    pendingSearchKeyword,
    searchScrollTarget,
    quotedMessage,
    switchVersion,
    regenerateMessage,
  }
})
