/**
 * LuomiNest 工作台消息/流式/模型/版本/删除/引用/推理
 *
 * 从 WorkspaceView.vue 拆分：收纳消息列表、流式状态、模型选择、发送/重生成、
 * 版本切换、消息删除（含范围计算）、回退到起点、引用、推理折叠、上下文用量等逻辑。
 * 跨关注点副作用（删除确认弹窗）通过 openConfirmDialog 回调交回视图处理。
 */
import { ref, computed, watch, nextTick } from 'vue'
import type { Ref } from 'vue'
import type { AgentProfile, ChatMessage } from '../types'
import type { ChatModeLevel, WorkflowModeOption } from '../components/workbench/types'
import { useChatStore } from '../stores/chat'
import { useModelStore } from '../stores/model'
import { useAgentStore } from '../stores/agent'
import { useApi } from './useApi'
import { useToast } from './useToast'
import { getProviderLogo } from '../config/provider-logos'

/** WorkspaceAgentChat 子组件实例的最小接口（避免依赖具体组件类型） */
interface WorkspaceAgentChatComponent {
  resetTextareaHeight: () => void
  scrollToBottom: (force?: boolean) => void
  scrollToSearchResult: (keyword: string) => void
  focusTextarea: () => void
  autoResize: () => void
}

/** 模型下拉选项 */
interface ModelOption {
  providerId: string
  providerName: string
  providerLogo: ReturnType<typeof getProviderLogo>
  modelId: string
  modelName: string
}

/** 发送消息的 options（与 chatStore.sendMessage 兼容的子集） */
export interface SendMessageOptions {
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
  chatMode?: ChatModeLevel
}

/** 文件上传状态（由 useFileUpload 提供，透传给本 composable） */
interface FileUploadState {
  isUploading: Ref<boolean>
  parsedContent: Ref<string>
  fileName: Ref<string>
  fileType: Ref<string>
  uploadingFile: Ref<{ name: string; status: 'uploading' | 'success' | 'failed'; type?: string; result?: string; error?: string } | null>
  clearUploadState: () => void
}

export interface UseWorkspaceMessagesOptions {
  localSelectedAgent: Ref<AgentProfile | null>
  localSelectedConvId: Ref<string | null>
  agentChatRef: Ref<WorkspaceAgentChatComponent | null>
  fileUpload: FileUploadState
  openConfirmDialog: (message: string, callback: () => void, isDanger?: boolean) => void
}

export const useWorkspaceMessages = (options: UseWorkspaceMessagesOptions) => {
  const chatStore = useChatStore()
  const modelStore = useModelStore()
  const agentStore = useAgentStore()
  const { truncateMessages, deleteMessage } = useApi()
  const { localSelectedAgent, localSelectedConvId, agentChatRef, fileUpload, openConfirmDialog } = options
  const { isUploading, parsedContent, fileName, fileType, uploadingFile, clearUploadState } = fileUpload

  // —— 输入与 UI 状态 ——
  const inputText = ref('')
  const selectedSkillIds = ref<string[]>([])
  const showModelDropdown = ref(false)
  const showReasoning = ref<Record<string, boolean>>({})

  // —— 消息与流式状态 ——
  const messages = computed<ChatMessage[]>(() => {
    if (!localSelectedConvId.value) return []
    return chatStore.convMessages[localSelectedConvId.value] || []
  })
  const isStreaming = computed(() => {
    if (!localSelectedConvId.value) return false
    return !!chatStore.convStreaming[localSelectedConvId.value]
  })
  const isLoadingCurrentConv = computed(() => chatStore.isLoadingCurrentConversation)
  const isBackendReady = computed(() => chatStore.isBackendReady)
  const currentConvId = computed(() => localSelectedConvId.value || '')

  // —— 模型选择 ——
  const currentModel = computed(() => {
    const agent = localSelectedAgent.value
    if (agent?.model) return agent.model
    const resolved = modelStore.resolveModel
    return resolved?.model || '未配置模型'
  })
  const currentProvider = computed(() => {
    const agent = localSelectedAgent.value
    if (agent?.provider) return agent.provider
    const resolved = modelStore.resolveModel
    return resolved?.provider || ''
  })
  const currentProviderLogo = computed(() => getProviderLogo(currentProvider.value))
  const hasProvider = computed(() => modelStore.providers.length > 0)

  const availableModelOptions = computed<ModelOption[]>(() => {
    const list: ModelOption[] = []
    for (const provider of modelStore.providers) {
      const logo = getProviderLogo(provider.id)
      const modelIds = provider.selectedModels.length > 0
        ? provider.selectedModels
        : (provider.defaultModel ? [provider.defaultModel] : [])
      for (const modelId of modelIds) {
        list.push({
          providerId: provider.id,
          providerName: provider.name,
          providerLogo: logo,
          modelId,
          modelName: modelId,
        })
      }
    }
    return list
  })

  const selectModel = async (providerId: string, modelId: string): Promise<void> => {
    if (localSelectedAgent.value) {
      // Optimistic update: 立即修改本地对象让 UI 即时反映
      localSelectedAgent.value.model = modelId
      localSelectedAgent.value.provider = providerId

      await agentStore.updateAgent(localSelectedAgent.value.id, {
        provider: providerId,
        model: modelId,
      })

      // Re-sync: fetchAgents 替换了整个数组后，抓回新鲜引用
      const updated = agentStore.agents.find(a => a.id === localSelectedAgent.value?.id)
      if (updated) localSelectedAgent.value = updated
    }
    showModelDropdown.value = false
  }

  // —— 对话模式（普通/标准/超长） ——
  const toast = useToast()
  const chatMode = ref<ChatModeLevel>('normal')
  const chatModeOptions: WorkflowModeOption[] = [
    { value: 'normal', label: '普通', title: '普通模式：工具最少（任务视图操作 + 表情操控）' },
    { value: 'standard', label: '标准', title: '专业模式·标准：平衡速度与深度，排除细粒度浏览器工具' },
    { value: 'ultra', label: '超长', title: '专业模式·超长：最大能力，全部工具可用，适合复杂长任务' },
  ]
  const isWorkflowMode = computed(() => chatMode.value !== 'normal')

  // 切换对话时从存储的 chat_mode 字段同步
  watch(localSelectedConvId, (convId) => {
    if (convId) {
      const conv = chatStore.convData[convId]
      chatMode.value = (conv?.chat_mode as ChatModeLevel) || 'normal'
    } else {
      chatMode.value = 'normal'
    }
  })

  const REASONING_MODEL_KEYWORDS = ['reasoner', 'reason', 'o1', 'o3', 'o4', 'thinking', 'r1']
  const isReasoningModel = (modelId: string): boolean => {
    const lower = modelId.toLowerCase()
    return REASONING_MODEL_KEYWORDS.some((kw) => lower.includes(kw))
  }

  const selectChatMode = (mode: ChatModeLevel): void => {
    // 上下文隔离：如果当前对话已有消息，禁止切换模式
    const convId = localSelectedConvId.value
    if (convId) {
      const currentMsgs = chatStore.convMessages[convId] || []
      if (currentMsgs.length > 0 && chatMode.value !== mode) {
        toast.warning('当前对话已有内容，无法切换模式。请新建对话后再选择所需模式。')
        return
      }
    }

    chatMode.value = mode
    const opts = availableModelOptions.value
    if (opts.length === 0) return
    // 专业模式优先推理模型，普通模式优先快速模型
    if (mode !== 'normal') {
      const reasoning = opts.find((opt) => isReasoningModel(opt.modelId))
      if (reasoning) selectModel(reasoning.providerId, reasoning.modelId)
    } else {
      const fast = opts.find((opt) => !isReasoningModel(opt.modelId))
      if (fast) selectModel(fast.providerId, fast.modelId)
    }
  }

  // —— 发送消息 ——
  const canSend = computed(() => {
    if (!isBackendReady.value) return false
    if (isUploading.value) return false
    return inputText.value.trim().length > 0 || !!parsedContent.value || !!chatStore.quotedMessage
  })

  const sendMessage = async (): Promise<void> => {
    if (!canSend.value) return

    let content = inputText.value.trim()
    const fileContent = parsedContent.value
    const currentFileName = fileName.value
    const currentFileType = fileType.value

    if (!content && fileContent) {
      content = '请帮我分析上传的文件'
    }
    if (!content && chatStore.quotedMessage) {
      content = '请看上面的引用内容'
    }

    inputText.value = ''
    agentChatRef.value?.resetTextareaHeight()
    clearUploadState()

    const agent = localSelectedAgent.value
    const resolved = modelStore.resolveModel

    const sendOptions: SendMessageOptions = {
      model: agent?.model || resolved?.model || undefined,
      provider: agent?.provider || resolved?.provider || undefined,
      temperature: modelStore.modelConfig.defaultTemperature,
      maxTokens: modelStore.modelConfig.defaultMaxTokens,
      topP: modelStore.modelConfig.defaultTopP,
      chatMode: chatMode.value,
    }
    if (agent?.systemPrompt) sendOptions.systemPrompt = agent.systemPrompt
    if (agent?.id) sendOptions.agentId = agent.id

    if (fileContent) {
      sendOptions.fileContent = fileContent
      sendOptions.fileType = currentFileType
      sendOptions.fileName = currentFileName
    }

    await chatStore.sendMessage(content, sendOptions)
    await nextTick()
    agentChatRef.value?.scrollToBottom(true)
  }

  const cancelStreaming = (): void => {
    chatStore.cancelCurrentRequest()
  }

  // —— 上下文用量与推荐 ——
  const contextUsage = computed(() => {
    const lastAssistantMsg = messages.value.findLast(m => m.role === 'assistant' && m.done)
    return lastAssistantMsg?.usage || chatStore.lastUsage || null
  })
  const currentSuggestionMessageId = computed(() => chatStore.currentSuggestionMessageId)
  const contextTokens = computed(() => {
    const convId = localSelectedConvId.value
    if (!convId) return 0
    return chatStore.convContextTokens[convId] || 0
  })
  const contextMaxTokens = computed(() => {
    const convId = localSelectedConvId.value
    if (!convId) return 0
    return chatStore.convContextMaxTokens[convId] || 0
  })
  const contextPercent = computed(() => {
    const max = contextMaxTokens.value
    if (!max || max <= 0) return 0
    const used = contextTokens.value
    if (!used || used <= 0) return 0
    return Math.min(100, Math.round((used / max) * 100))
  })

  // —— 版本切换与重生成 ——
  const handleSwitchVersion = (messageId: string, versionIndex: number): void => {
    const convId = currentConvId.value
    if (!convId) return
    chatStore.switchVersion(convId, messageId, versionIndex)
  }

  const handleSuggestionClick = (question: string): void => {
    inputText.value = question
    nextTick(() => sendMessage())
  }

  const handleRegenerate = async (messageId: string): Promise<void> => {
    await chatStore.regenerateMessage(messageId, {
      convId: localSelectedConvId.value || undefined,
      agentId: localSelectedAgent.value?.id,
    })
    await nextTick()
    agentChatRef.value?.scrollToBottom(true)
  }

  // —— 消息删除（含范围计算） ——
  const computeDeleteRange = (
    msgs: ChatMessage[],
    messageId: string,
  ): { startIndex: number; deleteCount: number } => {
    const index = msgs.findIndex((m: ChatMessage) => m.id === messageId)
    if (index === -1) return { startIndex: -1, deleteCount: 0 }

    let startIndex = index
    if (msgs[startIndex].role === 'assistant') {
      for (let i = startIndex - 1; i >= 0; i--) {
        if (msgs[i].role === 'user') {
          startIndex = i
          break
        }
      }
    }

    let deleteCount = 1
    if (msgs[startIndex].role === 'user') {
      for (let i = startIndex + 1; i < msgs.length; i++) {
        if (msgs[i].role === 'assistant') {
          deleteCount++
        } else {
          break
        }
      }
    }

    return { startIndex, deleteCount }
  }

  const handleDeleteMessage = (messageId: string): void => {
    const convId = currentConvId.value
    if (!convId) return
    const msgs = chatStore.convMessages[convId]
    if (!msgs) return

    const { startIndex } = computeDeleteRange(msgs, messageId)
    if (startIndex === -1) return

    openConfirmDialog(
      '确定删除这条消息及其关联回复？此操作不可撤销。',
      async () => {
        const currentConvIdLocal = currentConvId.value
        if (!currentConvIdLocal) return
        const currentMsgs = chatStore.convMessages[currentConvIdLocal]
        if (!currentMsgs) return

        const { startIndex: reStart, deleteCount: reCount } = computeDeleteRange(currentMsgs, messageId)
        if (reStart === -1) return

        if (reStart + reCount === currentMsgs.length) {
          await truncateMessages(currentConvIdLocal, reStart)
          chatStore.convMessages[currentConvIdLocal] = currentMsgs.slice(0, reStart)
        } else {
          const idsToDelete = currentMsgs.slice(reStart, reStart + reCount).map((m: ChatMessage) => m.id)
          for (const id of idsToDelete) {
            await deleteMessage(currentConvIdLocal, id)
          }
          chatStore.convMessages[currentConvIdLocal] = currentMsgs.slice(0, reStart).concat(currentMsgs.slice(reStart + reCount))
        }

        if (chatStore.currentSuggestionMessageId === messageId) {
          chatStore.currentSuggestionMessageId = null
        }
      },
      true,
    )
  }

  // —— 回退到起点 ——
  const handleGoBackToStart = (msg: ChatMessage): void => {
    openConfirmDialog(
      '确定回退这条消息？该消息及之后的所有消息将被删除，内容将恢复到输入框。',
      async () => {
        const convId = currentConvId.value
        if (!convId) return
        const msgs = chatStore.convMessages[convId]
        if (!msgs) return

        inputText.value = msg.content || ''

        if (msg.files && msg.files.length > 0) {
          const file = msg.files[0]
          parsedContent.value = file.content || ''
          fileName.value = file.name || ''
          fileType.value = file.type || 'text'
          uploadingFile.value = {
            name: file.name || 'file',
            status: 'success',
            type: file.type,
            result: file.content,
          }
          isUploading.value = false
        } else {
          clearUploadState()
        }

        const index = msgs.findIndex((m: ChatMessage) => m.id === msg.id)
        if (index !== -1) {
          const keepCount = index
          await truncateMessages(convId, keepCount)
          chatStore.convMessages[convId] = msgs.slice(0, keepCount)
          chatStore.currentSuggestionMessageId = null
        }

        nextTick(() => {
          agentChatRef.value?.focusTextarea()
          agentChatRef.value?.autoResize()
        })
      },
      true,
    )
  }

  // —— 引用 ——
  const handleQuoteMessage = (msg: ChatMessage): void => {
    chatStore.quotedMessage = msg
  }

  // —— 推理折叠 ——
  const toggleReasoning = (msgId: string): void => {
    showReasoning.value = {
      ...showReasoning.value,
      [msgId]: !showReasoning.value[msgId],
    }
  }

  // —— 搜索关键词滚动监听 ——
  watch(isLoadingCurrentConv, (loading) => {
    if (!loading) {
      const keyword = chatStore.pendingSearchKeyword
      if (keyword) {
        chatStore.pendingSearchKeyword = ''
        nextTick(() => {
          agentChatRef.value?.scrollToSearchResult(keyword)
        })
      } else {
        nextTick(() => {
          agentChatRef.value?.scrollToBottom(true)
        })
      }
    }
  })

  watch(() => chatStore.pendingSearchKeyword, (keyword) => {
    if (keyword && !chatStore.isLoadingCurrentConversation && messages.value.length > 0) {
      chatStore.pendingSearchKeyword = ''
      nextTick(() => {
        agentChatRef.value?.scrollToSearchResult(keyword)
      })
    }
  })

  return {
    // 输入与 UI 状态
    inputText,
    selectedSkillIds,
    showModelDropdown,
    showReasoning,
    // 消息与流式状态
    messages,
    isStreaming,
    isLoadingCurrentConv,
    isBackendReady,
    currentConvId,
    // 模型选择
    currentModel,
    currentProvider,
    currentProviderLogo,
    hasProvider,
    availableModelOptions,
    selectModel,
    // 对话模式
    chatMode,
    chatModeOptions,
    isWorkflowMode,
    selectChatMode,
    // 发送消息
    canSend,
    sendMessage,
    cancelStreaming,
    // 上下文用量与推荐
    contextUsage,
    contextTokens,
    contextMaxTokens,
    contextPercent,
    currentSuggestionMessageId,
    // 版本切换与重生成
    handleSwitchVersion,
    handleSuggestionClick,
    handleRegenerate,
    // 消息删除
    handleDeleteMessage,
    // 回退到起点
    handleGoBackToStart,
    // 引用
    handleQuoteMessage,
    // 推理折叠
    toggleReasoning,
  }
}
