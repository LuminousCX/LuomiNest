/**
 * LuomiNest 工作台消息/发送/工作流/重生成
 *
 * 从 WorkbenchView.vue 拆分：收纳对话面板状态、发送消息、工作流提交、重生成、
 * 滚动控制、对话模式切换等逻辑。onChunk 回调通过 createChunkHandler 工厂函数
 * 复用，避免 sendMessage 与 handleRegenerate 的重复代码。
 * TTS/子Agent/工具活动等跨关注点副作用通过 options 回调交由对应 composable 处理。
 */
import { ref, computed, watch, nextTick } from 'vue'
import type { Ref } from 'vue'
import { useChatStore } from '../stores/chat'
import { useModelStore } from '../stores/model'
import { useWorkflowStore } from '../stores/workflow'
import { useStatsStore } from '../stores/stats'
import { useTaskStreamStore } from '../stores/taskStream'
import { useToast } from './useToast'
import { createLuomiNestRendererLogger } from '../utils/logger'
import { generateId } from '../utils/id'
import type { ChatStreamChunk, SubagentEvent, ChatMessage } from '../types'
import type { ToolActivity, SubagentActivity, ChatModeLevel, WorkflowModeOption } from '../components/workbench/types'
import type { NavigationTarget } from './useTaskNavigation'
import WorkbenchChatArea from '../components/workbench/WorkbenchChatArea.vue'
import WorkbenchInputArea from '../components/workbench/WorkbenchInputArea.vue'

const logger = createLuomiNestRendererLogger('Workbench')

/** 拦截消息前缀（与后端 app/security/command_policy 保持一致） */
const INTERCEPTION_MARKER = '命令已被安全策略拦截'

/** 从后端拦截消息中提取原因（“：原因” 段） */
const parseInterceptionReason = (text: string): string => {
  const match = /拦截：(.+?)(?:（命令:|。)/.exec(text)
  return match ? match[1].trim() : text
}

/** 从后端拦截消息中提取被拦截的命令（“（命令: xxx）” 段） */
const parseInterceptionCommand = (text: string): string => {
  const match = /命令:\s*([^）]+)/.exec(text)
  return match ? match[1].trim() : ''
}

/** 发送消息选项（chatStore.sendMessage 的 options 子集） */
interface WorkbenchSendMessageOptions {
  agentId: string
  model?: string
  provider?: string
  temperature: number
  maxTokens: number
  topP: number
  chatMode: ChatModeLevel
  skillIds?: string[]
  onChunk: (chunk: ChatStreamChunk) => void
}

export interface UseWorkbenchMessagesOptions {
  agentId: string
  handleSubagentEvent: (event: SubagentEvent) => void
  toolActivities: Ref<ToolActivity[]>
  subagentActivities: Ref<SubagentActivity[]>
  feedChunk: (chunk: ChatStreamChunk) => void
  finishStream: () => void
  filterCodeForTts: (content: string) => string
  resetCodeBlockFilter: () => void
  navigateToTask: (target: NavigationTarget) => void
  stopTts: () => void
  inputAreaRef: Ref<InstanceType<typeof WorkbenchInputArea> | null>
}

export const useWorkbenchMessages = (options: UseWorkbenchMessagesOptions) => {
  const {
    agentId,
    handleSubagentEvent,
    toolActivities,
    subagentActivities,
    feedChunk,
    finishStream,
    filterCodeForTts,
    resetCodeBlockFilter,
    navigateToTask,
    stopTts,
    inputAreaRef,
  } = options

  const chatStore = useChatStore()
  const modelStore = useModelStore()
  const workflowStore = useWorkflowStore()
  const statsStore = useStatsStore()
  const taskStreamStore = useTaskStreamStore()
  const toast = useToast()

  // 对话面板状态
  const inputText = ref('')
  const selectedSkillIds = ref<string[]>([])
  const showReasoning = ref<Record<string, boolean>>({})
  const isNearBottom = ref(true)
  const SCROLL_BOTTOM_THRESHOLD = 120
  const showScrollToBottomBtn = ref(false)

  const messages = computed(() => chatStore.messages)
  const isStreaming = computed(() => chatStore.isStreaming || workflowStore.isRunning)
  const isBackendReady = computed(() => chatStore.isBackendReady)
  const isLoadingCurrentConv = computed(() => chatStore.isLoadingCurrentConversation)
  const contextTokens = computed(() => chatStore.currentContextTokens)
  const contextMaxTokens = computed(() => chatStore.currentContextMaxTokens)
  const contextPercent = computed(() => chatStore.currentContextPercent)
  const isCompressing = ref(false)
  const hasMoreMessages = computed(() => chatStore.currentHasMore)

  // 对话模式（普通/标准/超长）
  const chatMode = ref<ChatModeLevel>('normal')
  const CHAT_MODE_OPTIONS: WorkflowModeOption[] = [
    { value: 'normal', label: '普通', title: '普通模式：工具最少（任务视图操作 + 表情操控）' },
    { value: 'standard', label: '标准', title: '专业模式·标准：平衡速度与深度，排除细粒度浏览器工具' },
    { value: 'ultra', label: '超长', title: '专业模式·超长：最大能力，全部工具可用，适合复杂长任务' },
  ]
  const isWorkflowMode = computed(() => chatMode.value !== 'normal')

  // 切换对话时同步 chatMode（从对话存储的 chat_mode 字段读取）
  // 监听 currentConversation?.chat_mode 确保异步加载完成后也能同步
  watch(
    () => chatStore.currentConversation?.chat_mode,
    (newMode) => {
      chatMode.value = (newMode as ChatModeLevel) || 'normal'
    },
    { immediate: true },
  )

  const canSend = computed(() => {
    if (!isBackendReady.value) return false
    return inputText.value.trim().length > 0
  })

  // 子组件引用
  const chatAreaRef = ref<InstanceType<typeof WorkbenchChatArea> | null>(null)

  const scrollToBottom = (force = false): void => {
    chatAreaRef.value?.scrollToBottom(force)
  }

  const handleMessagesScroll = (metrics: { scrollTop: number; scrollHeight: number; clientHeight: number }): void => {
    const { scrollTop, scrollHeight, clientHeight } = metrics
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight
    isNearBottom.value = distanceFromBottom < SCROLL_BOTTOM_THRESHOLD
    showScrollToBottomBtn.value = !isNearBottom.value && messages.value.length > 0
  }

  /**
   * onChunk 回调工厂函数
   * sendMessage 和 handleRegenerate 的 onChunk 逻辑几乎相同，
   * 仅差 statsStore.interceptChunk 调用（仅 sendMessage 需要）。
   */
  const createChunkHandler = (isRegenerate: boolean) => {
    return (chunk: ChatStreamChunk): void => {
      if (!isRegenerate) {
        statsStore.interceptChunk(chunk, chatStore.currentConvId)
      }

      // 模型路由通知（如专业模式推理模型退化为主模型）：右上角 toast
      if (chunk.notice) {
        toast.warning(chunk.notice)
      }

      if (chunk.done) {
        finishStream()
        return
      }
      if (chunk.subagent_event) {
        handleSubagentEvent(chunk.subagent_event)
        taskStreamStore.handleSubagentEvent(chunk.subagent_event)
        if (chunk.subagent_event.browser_action === 'open_tab') {
          navigateToTask('browser')
        }
      }
      if (chunk.task_event) {
        taskStreamStore.handleTaskEvent(chunk.task_event)
      }
      if (chunk.tool_calls && chunk.tool_calls.length > 0) {
        for (const tc of chunk.tool_calls) {
          toolActivities.value.push({
            id: tc.id,
            name: tc.function.name,
            arguments: tc.function.arguments,
            status: 'pending',
            iteration: chunk.iteration || 0,
          })
        }
      }
      if (chunk.tool_event) {
        const ev = chunk.tool_event
        const activity = toolActivities.value.find(
          (a) => a.name === ev.tool_name && a.iteration === (chunk.iteration || 0) && a.status !== 'completed' && a.status !== 'failed' && a.status !== 'blocked'
        )
        if (activity) {
          if (ev.status === 'started') {
            activity.status = 'running'
          } else if (ev.status === 'completed') {
            // 识别命令安全拦截：输出包含统一拦截文案时标记为 blocked
            const output = ev.output || ''
            if (output.includes(INTERCEPTION_MARKER)) {
              activity.status = 'blocked'
              activity.output = output
              activity.blockedReason = parseInterceptionReason(output)
              activity.blockedCommand = parseInterceptionCommand(output)
            } else {
              activity.status = 'completed'
              activity.output = output || ''
            }
          } else if (ev.status === 'failed') {
            const output = ev.output || ''
            if (output.includes(INTERCEPTION_MARKER)) {
              activity.status = 'blocked'
              activity.output = output
              activity.blockedReason = parseInterceptionReason(output)
              activity.blockedCommand = parseInterceptionCommand(output)
            } else {
              activity.status = 'failed'
              activity.output = output || ''
            }
          }
        }
      }
      const filteredContent = filterCodeForTts(chunk.content || '')
      if (filteredContent || chunk.emotion) {
        feedChunk({ ...chunk, content: filteredContent })
      }
    }
  }

  const selectChatMode = (mode: ChatModeLevel): void => {
    // 上下文隔离：如果当前对话已有消息，禁止切换模式，三种模式间不允许相互切换
    const currentConvId = chatStore.currentConvId
    if (currentConvId) {
      const currentMessages = chatStore.convMessages[currentConvId] || []
      if (currentMessages.length > 0 && chatMode.value !== mode) {
        toast.warning('当前对话已有内容，无法切换模式。请新建对话后再选择所需模式。')
        return
      }
    }

    // 2026-08 全局模型统一：切换模式不再改动全局主模型。
    // 专业模式（standard/ultra）由后端按轮路由到推理模型（设置页配置），
    // 推理模型不可用时后端退化为主模型并通过 SSE notice 通知前端 toast。
    chatMode.value = mode
  }

  const sendMessage = async (): Promise<void> => {
    if (!canSend.value) return

    const content = inputText.value.trim()
    inputText.value = ''
    inputAreaRef.value?.resetTextareaHeight()
    statsStore.recordPrompt(content)

    const resolved = modelStore.resolveModel

    if (isWorkflowMode.value) {
      await submitWorkflowTask(content, resolved)
      return
    }

    toolActivities.value = []
    subagentActivities.value = []

    const sendOptions: WorkbenchSendMessageOptions = {
      agentId,
      model: resolved?.model || undefined,
      provider: resolved?.provider || undefined,
      temperature: modelStore.modelConfig.defaultTemperature,
      maxTokens: modelStore.modelConfig.defaultMaxTokens,
      topP: modelStore.modelConfig.defaultTopP,
      chatMode: chatMode.value,
      skillIds: selectedSkillIds.value,
      onChunk: createChunkHandler(false),
    }

    resetCodeBlockFilter()
    isNearBottom.value = true
    try {
      await chatStore.sendMessage(content, sendOptions)
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e)
      toast.error(`发送消息失败：${errMsg}`)
    }
    await nextTick()
    scrollToBottom(true)
  }

  const submitWorkflowTask = async (
    content: string,
    resolved: { model?: string; provider?: string } | null,
  ): Promise<void> => {
    toolActivities.value = []
    subagentActivities.value = []
    isNearBottom.value = true
    resetCodeBlockFilter()

    let convId = chatStore.currentConvId
    if (!convId) {
      try {
        const conv = await chatStore.createConversation(
          content.slice(0, 30) || '新对话',
          agentId,
          resolved?.model,
          resolved?.provider,
          chatMode.value,
        )
        convId = conv?.id || ''
      } catch (e: unknown) {
        const errMsg = e instanceof Error ? e.message : String(e)
        toast.error(`创建对话失败：${errMsg}`)
        return
      }
    }

    if (!convId) {
      toast.error('请先选择或创建对话')
      return
    }

    const userMsgId = generateId('user')
    const userMessage = {
      id: userMsgId,
      role: 'user' as const,
      content,
      timestamp: Date.now(),
    }
    chatStore.convMessages = {
      ...chatStore.convMessages,
      [convId]: [...(chatStore.convMessages[convId] || []), userMessage],
    }

    const assistantMsgId = generateId('assistant')
    const assistantMessage = {
      id: assistantMsgId,
      role: 'assistant' as const,
      content: '',
      reasoningContent: '',
      timestamp: Date.now(),
      done: false,
    }
    chatStore.convMessages = {
      ...chatStore.convMessages,
      [convId]: [...(chatStore.convMessages[convId] || []), assistantMessage],
    }

    await nextTick()
    scrollToBottom(true)

    // 更新 assistantMessage 的辅助函数（不可变更新，触发 Vue 响应式）
    const updateAssistantMsg = (updater: (m: ChatMessage) => ChatMessage): void => {
      const msgs = chatStore.convMessages[convId] || []
      chatStore.convMessages = {
        ...chatStore.convMessages,
        [convId]: msgs.map((m) => (m.id === assistantMsgId ? updater(m) : m)),
      }
    }

    // 标记完成并触发 TTS 的辅助函数
    const finalizeAssistant = (finalContent: string): void => {
      updateAssistantMsg((m) => ({ ...m, content: finalContent, done: true }))
      if (finalContent) {
        try {
          feedChunk({
            id: generateId('workflow'),
            content: finalContent,
            reasoning_content: '',
            model: resolved?.model || '',
            provider: resolved?.provider || '',
            done: true,
          } as ChatStreamChunk)
        } catch (ttsErr) {
          logger.warn('TTS 播报失败，消息已正常显示:', ttsErr)
        }
      }
      finishStream()
    }

    try {
      await workflowStore.submitWorkflow(content, {
        provider: resolved?.provider || undefined,
        model: resolved?.model || undefined,
        mode: chatMode.value === 'ultra' ? 'ultra' : 'standard',
        conversationId: convId,
        onPhaseChange: (phase: string) => {
          logger.info(`工作流阶段: ${phase}`)
        },
        onModuleAction: () => {
          navigateToTask('workflow')
        },
        onReasoning: (reasoningContent: string) => {
          updateAssistantMsg((m) => ({
            ...m,
            reasoningContent: (m.reasoningContent || '') + reasoningContent,
          }))
        },
        onContent: (delta: string) => {
          // 流式追加 content（LLM 输出增量，可能含 JSON 计划或 think 标签，final_result 时会覆盖）
          updateAssistantMsg((m) => ({
            ...m,
            content: (m.content || '') + delta,
          }))
          nextTick(() => {
            if (isNearBottom.value) scrollToBottom()
          })
        },
        onPlanCreated: (sessionId: string, taskCount: number) => {
          // 收到执行计划后清空 content（之前流式显示的是 JSON 计划，不是用户回复）
          updateAssistantMsg((m) => ({
            ...m,
            content: '',
            workflowSessionId: sessionId,
            workflowTaskCount: taskCount,
          }))
        },
        onFinalResult: (result: string) => {
          // final_result 覆盖 content（后端已清理 think 标签，是干净的最终回复）
          finalizeAssistant(result || '工作流执行完成')
        },
        onError: (errMsg: string) => {
          // SSE 连接错误或工作流引擎错误：更新 assistantMessage 为错误状态，避免 UI 卡住
          finalizeAssistant(`工作流执行失败：${errMsg}`)
        },
      })
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e)
      toast.error(`工作流执行失败：${errMsg}`)
      finalizeAssistant(`工作流执行失败：${errMsg}`)
    }
    await nextTick()
    scrollToBottom(true)
  }

  const cancelStreaming = (): void => {
    if (workflowStore.isRunning) {
      workflowStore.cancelWorkflow()
      return
    }
    chatStore.cancelCurrentRequest()
    stopTts()
  }

  const handleRegenerate = async (messageId: string): Promise<void> => {
    resetCodeBlockFilter()
    toolActivities.value = []
    subagentActivities.value = []
    try {
      await chatStore.regenerateMessage(messageId, {
        onChunk: createChunkHandler(true),
      })
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e)
      toast.error(`重新生成失败：${errMsg}`)
    }
    await nextTick()
    scrollToBottom(true)
  }

  const handleLoadMore = async (): Promise<void> => {
    const convId = chatStore.currentConvId
    if (!convId) return
    const container = chatAreaRef.value?.$el?.querySelector?.('.messages-scroll') as HTMLElement | null
    const prevScrollHeight = container?.scrollHeight ?? 0
    try {
      await chatStore.loadMoreMessages(convId)
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e)
      toast.error(`加载历史消息失败：${errMsg}`)
    }
    await nextTick()
    // 保持滚动位置：prepending 消息后恢复用户当前视口
    if (container) {
      const newScrollHeight = container.scrollHeight
      container.scrollTop += newScrollHeight - prevScrollHeight
    }
  }

  const handleCompressContext = async (): Promise<void> => {
    const convId = chatStore.currentConvId
    if (!convId || isCompressing.value) return
    isCompressing.value = true
    try {
      const result = await chatStore.compressConversation(convId)
      if (result.compressed) {
        toast.success(`上下文压缩成功：${result.tokens_before} → ${result.tokens_after} tokens`)
      }
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e)
      toast.error(`上下文压缩失败：${errMsg}`)
    } finally {
      isCompressing.value = false
    }
  }

  // watch: 初始化 showReasoning
  watch(
    () => messages.value,
    async (msgs) => {
      for (const msg of msgs) {
        if (msg.role !== 'assistant') continue
        if (msg.content && msg.content.length > 0 && showReasoning.value[msg.id] === undefined) {
          showReasoning.value = { ...showReasoning.value, [msg.id]: false }
        }
      }
    },
    { deep: true, immediate: true }
  )

  // watch: 流式输出时自动滚动到底部
  watch(
    messages,
    () => {
      if (isStreaming.value && isNearBottom.value) {
        nextTick(() => scrollToBottom())
      }
    },
    { deep: true }
  )

  // watch: 加载对话时滚动到底部
  watch(isLoadingCurrentConv, (loading) => {
    if (loading) {
      isNearBottom.value = true
    } else {
      nextTick(() => scrollToBottom(true))
    }
  })

  return {
    // 状态
    inputText,
    selectedSkillIds,
    showReasoning,
    isNearBottom,
    showScrollToBottomBtn,
    chatMode,
    CHAT_MODE_OPTIONS,
    // computed
    messages,
    isStreaming,
    isBackendReady,
    isLoadingCurrentConv,
    isWorkflowMode,
    canSend,
    contextTokens,
    contextMaxTokens,
    contextPercent,
    isCompressing,
    hasMoreMessages,
    // 子组件引用
    chatAreaRef,
    // 方法
    scrollToBottom,
    handleMessagesScroll,
    selectChatMode,
    sendMessage,
    cancelStreaming,
    handleRegenerate,
    handleCompressContext,
    handleLoadMore,
  }
}
