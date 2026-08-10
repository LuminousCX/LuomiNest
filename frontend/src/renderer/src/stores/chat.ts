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
import { enrichWithSearchResults, enrichWithUrlContent } from '../utils/chatSearchHelpers'
import { generateId } from '../utils/id'
import { createLuomiNestRendererLogger } from '../utils/logger'
import { MAIN_AGENT_ID } from '../constants'

const logger = createLuomiNestRendererLogger('Chat')

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
  const convContextTokens = ref<Record<string, number>>({})
  // 每个对话的上下文窗口容量（max_tokens），用于前端计算使用百分比
  const convContextMaxTokens = ref<Record<string, number>>({})

  // 分页状态：每个对话是否有更多历史消息 & 后端消息总数
  const convHasMore = ref<Record<string, boolean>>({})
  const convTotalMessages = ref<Record<string, number>>({})

  // 三端（工作台 / 桌宠 / 皮套工坊）共享 MAIN_AGENT 的当前对话，
  // 通过 agentCurrentConvId[MAIN_AGENT_ID] 获取，无需单独的"桌宠对话 ID"
  // 启动时不创建对话，第一次发消息时自动创建（按需创建，避免空对话堆积）

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

  const currentHasMore = computed(() => !!convHasMore.value[currentConvId.value])

  const currentMessages = computed(() => messages.value)

  const currentContextTokens = computed(() => {
    const convId = currentConvId.value
    if (!convId) return 0
    return convContextTokens.value[convId] || 0
  })

  // 当前对话的上下文窗口容量
  const currentContextMaxTokens = computed(() => {
    const convId = currentConvId.value
    if (!convId) return 0
    return convContextMaxTokens.value[convId] || 0
  })

  // 当前对话的上下文使用百分比（0-100，未配置 max 时为 0）
  const currentContextPercent = computed(() => {
    const max = currentContextMaxTokens.value
    if (!max || max <= 0) return 0
    const used = currentContextTokens.value
    if (!used || used <= 0) return 0
    return Math.min(100, Math.round((used / max) * 100))
  })

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
        is_hidden: (conv as any).is_hidden,
        created_at: conv.created_at || conv.createdAt || '',
        updated_at: conv.updated_at || conv.updatedAt || '',
      }))
      // 二次过滤：排除 is_hidden=True 的对话（后端已过滤，前端做兜底）
      const visibleConvs = convs.filter(c => !c.is_hidden)
      agentConversations.value = {
        ...agentConversations.value,
        [targetAgentId]: visibleConvs
      }
    } catch (error: unknown) {
      logger.warn('Failed to fetch conversations:', error)
      agentConversations.value = {
        ...agentConversations.value,
        [targetAgentId]: []
      }
    }
  }

  const mapApiMessage = (m: ApiMessage): ChatMessage => {
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
    return msg
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
      convHasMore.value = { ...convHasMore.value, [convId]: !!conv.has_more }
      convTotalMessages.value = { ...convTotalMessages.value, [convId]: conv.total_messages ?? (conv.messages?.length ?? 0) }
      const mappedMessages = (conv.messages || []).map(mapApiMessage)
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

  const loadMoreMessages = async (convId: string) => {
    if (!convHasMore.value[convId]) return

    const existing = convMessages.value[convId] || []
    if (existing.length === 0) return

    const beforeId = existing[0].id
    convLoading.value = { ...convLoading.value, [convId]: true }

    try {
      const conv = await apiGet<Conversation>(`/chat/conversations/${convId}?before_id=${beforeId}`)
      const olderMessages = (conv.messages || []).map(mapApiMessage)
      convMessages.value[convId].unshift(...olderMessages)
      convHasMore.value = { ...convHasMore.value, [convId]: !!conv.has_more }
    } catch (error) {
      logger.warn('Failed to load more messages:', error)
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

  const createConversation = async (title?: string, agentId?: string, model?: string, provider?: string, chatMode?: string, isHidden?: boolean) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return null

    const conv = await apiPost<Conversation>('/chat/conversations', {
      title: title || '新对话',
      agent_id: targetAgentId,
      model,
      provider,
      chat_mode: chatMode || 'normal',
      is_hidden: isHidden || false,
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
      logger.warn('Failed to rename conversation:', error)
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
      logger.warn('Search failed:', error)
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
      targetConvId?: string
    }
  ) => {
    const targetAgentId = options?.agentId || activeAgentId.value
    if (!targetAgentId) return

    // 空消息守卫：内容为空时不触发自动创建对话
    if (!content.trim()) return

    // 发送消息时立即清除推荐
    currentSuggestionMessageId.value = null

    // 优先使用调用方指定的对话 ID（桌宠/皮套工坊场景）
    // 三端共享：工作台/桌宠/皮套工坊都用 agentCurrentConvId[MAIN_AGENT_ID]
    // 启动时为 null，第一次发消息时自动创建新对话（按需创建，避免空对话堆积）
    let convId = options?.targetConvId || agentCurrentConvId.value[targetAgentId]

    if (!convId) {
      const conv = await createConversation(
        content.slice(0, 30),
        targetAgentId,
        options?.model,
        options?.provider,
        options?.chatMode
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

    // 搜索意图检测 + URL 内容抓取（已解耦到独立模块）
    await enrichWithSearchResults(content, requestBody)

    await enrichWithUrlContent(
      content,
      requestBody,
      (patch) => {
        const msgList = convMessages.value[convId]
        if (!msgList || msgList.length === 0) return
        const lastIdx = msgList.length - 1
        const lastMsg = msgList[lastIdx]
        if (lastMsg?.role === 'assistant' && !lastMsg.done) {
          convMessages.value = {
            ...convMessages.value,
            [convId]: [...msgList.slice(0, lastIdx), { ...lastMsg, ...patch }],
          }
        }
      },
    )

    const controller = new AbortController()
    convAbortControllers.value = { ...convAbortControllers.value, [convId]: controller }

    const streamingConvId = convId

    await apiStream(
      endpoint,
      requestBody,
      (chunk: ChatStreamChunk) => {
        const msgsList = convMessages.value[streamingConvId]
        if (!msgsList) return
        const lastIdx = msgsList.length - 1
        if (lastIdx >= 0 && msgsList[lastIdx]?.role === 'assistant') {
          // 直接修改响应式代理属性，避免每个 chunk 都拷贝整个消息数组
          const lastMsg = msgsList[lastIdx]
          lastMsg.content += (chunk.content || '')
          lastMsg.reasoningContent += (chunk.reasoning_content || '')
          if (chunk.done) {
            logger.debug('done chunk suggestions:', chunk.suggested_questions)
            if (chunk.suggested_questions && chunk.suggested_questions.length > 0) {
              lastMsg.suggestedQuestions = chunk.suggested_questions
            }
            if (chunk.context_tokens !== undefined) {
              convContextTokens.value = { ...convContextTokens.value, [streamingConvId]: chunk.context_tokens }
            }
            if (chunk.context_max_tokens !== undefined && chunk.context_max_tokens > 0) {
              convContextMaxTokens.value = { ...convContextMaxTokens.value, [streamingConvId]: chunk.context_max_tokens }
            }
          } else {
            lastMsg.suggestedQuestions = undefined
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
          lastMsg.done = true
          if (lastMsg.versions && lastMsg.versions.length > 0) {
            const newVersion: MessageVersion = {
              content: lastMsg.content,
              reasoningContent: lastMsg.reasoningContent || undefined,
              model: lastMsg.model,
              provider: lastMsg.provider,
              suggestedQuestions: lastMsg.suggestedQuestions || undefined,
            }
            lastMsg.versions = [...lastMsg.versions, newVersion]
            lastMsg.currentVersion = lastMsg.versions.length - 1
          }
          // 只有这条消息有推荐问题时，才设置当前推荐消息ID
          if (lastMsg.suggestedQuestions && lastMsg.suggestedQuestions.length > 0) {
            currentSuggestionMessageId.value = lastMsg.id
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
      logger.warn('Failed to persist version switch:', error)
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
        const msgsList = convMessages.value[streamingConvId]
        if (!msgsList) return
        const lastIdx = msgsList.length - 1
        if (lastIdx >= 0 && msgsList[lastIdx]?.role === 'assistant') {
          const lastMsg = msgsList[lastIdx]
          if (chunk.done && chunk.suggested_questions && chunk.suggested_questions.length > 0) {
            streamDoneSuggestions = chunk.suggested_questions
          }
          if (chunk.done && chunk.context_tokens !== undefined) {
            convContextTokens.value = { ...convContextTokens.value, [streamingConvId]: chunk.context_tokens }
          }
          if (chunk.done && chunk.context_max_tokens !== undefined && chunk.context_max_tokens > 0) {
            convContextMaxTokens.value = { ...convContextMaxTokens.value, [streamingConvId]: chunk.context_max_tokens }
          }
          // 直接修改响应式代理属性，避免每个 chunk 都拷贝整个消息数组
          lastMsg.content += (chunk.content || '')
          lastMsg.reasoningContent += (chunk.reasoning_content || '')
          lastMsg.suggestedQuestions = streamDoneSuggestions ?? lastMsg.suggestedQuestions
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
          lastMsg.done = true
          if (lastMsg.versions && lastMsg.versions.length > 0) {
            const newVersion: MessageVersion = {
              content: lastMsg.content,
              reasoningContent: lastMsg.reasoningContent || undefined,
              model: lastMsg.model,
              provider: lastMsg.provider,
              suggestedQuestions: lastMsg.suggestedQuestions || undefined,
            }
            lastMsg.versions = [...lastMsg.versions, newVersion]
            lastMsg.currentVersion = lastMsg.versions.length - 1
          }
          // 明确设置推荐问题：如果流式回调中已更新就用新的，否则清除旧的（新版本尚未生成推荐问题）
          lastMsg.suggestedQuestions = lastMsg.suggestedQuestions || undefined
          if (lastMsg.suggestedQuestions && lastMsg.suggestedQuestions.length > 0) {
            currentSuggestionMessageId.value = lastMsg.id
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

  const compressConversation = async (convId: string): Promise<{ compressed: boolean; tokens_before: number; tokens_after: number }> => {
    try {
      const result = await apiPost<{ compressed: boolean; tokens_before: number; tokens_after: number }>(
        `/chat/conversations/${convId}/compress`,
        {}
      )
      if (result.compressed) {
        convContextTokens.value = { ...convContextTokens.value, [convId]: result.tokens_after }
      }
      return result
    } catch (error) {
      logger.warn('Failed to compress conversation:', error)
      throw error
    }
  }

  const leaveCurrentConversation = async (convId: string) => {
    try {
      await apiPost(`/chat/conversations/${convId}/leave`)
    } catch (error) {
      logger.warn('Failed to leave conversation:', error)
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
        // 已有当前对话（如用户点击左侧列表后切换 agent 再切回），加载它
        if (!convMessages.value[currentId] || convMessages.value[currentId].length === 0) {
          await loadConversation(currentId)
        }
      } else if (newAgentId !== MAIN_AGENT_ID && agentConversations.value[newAgentId].length > 0) {
        // 非主 Agent：优先选择最近有消息的对话（Bug2 逻辑）
        // 主 Agent：不自动选择，保留空对话页面，等用户发消息时按需创建（方案 B）
        // 桌宠/皮套工坊创建的对话会出现在左侧列表，用户可点击查看
        const sortedConvs = [...agentConversations.value[newAgentId]]
          .filter(c => c.last_message && c.last_message.trim())
          .sort((a, b) => {
            const ta = a.updated_at ? new Date(a.updated_at).getTime() : 0
            const tb = b.updated_at ? new Date(b.updated_at).getTime() : 0
            return tb - ta
          })
        const latestConv = sortedConvs[0] || agentConversations.value[newAgentId][0]
        if (latestConv?.id) {
          try {
            await loadConversation(latestConv.id)
          } catch (error) {
            logger.warn(`Failed to load latest conversation for agent ${newAgentId}:`, error)
          }
        }
      }
      // 主 Agent 且无 currentId：保持空对话页面，第一次发消息时由 sendMessage 自动创建
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
    convContextTokens,
    convContextMaxTokens,
    currentContextTokens,
    currentContextMaxTokens,
    currentContextPercent,
    compressConversation,
    agentCurrentConvId,
    convHasMore,
    currentHasMore,
    loadMoreMessages,
  }
})
