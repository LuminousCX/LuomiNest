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
import { useChatStore } from '../stores/chat'
import { useModelStore } from '../stores/model'
import { useAgentStore } from '../stores/agent'
import { useApi } from './useApi'
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

  const selectModel = (providerId: string, modelId: string): void => {
    if (localSelectedAgent.value) {
      agentStore.updateAgent(localSelectedAgent.value.id, {
        provider: providerId,
        model: modelId,
      })
    }
    showModelDropdown.value = false
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
  const contextPercent = computed(() => {
    if (!contextUsage.value?.totalTokens || !modelStore.modelConfig.defaultMaxTokens) return 0
    return Math.min(100, Math.round((contextUsage.value.totalTokens / modelStore.modelConfig.defaultMaxTokens) * 100))
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
    // 发送消息
    canSend,
    sendMessage,
    cancelStreaming,
    // 上下文用量与推荐
    contextUsage,
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
