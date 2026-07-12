/**
 * LuomiNest 工作台消息/发送/工作流/重生成
 *
 * 从 WorkbenchView.vue 拆分：收纳对话面板状态、发送消息、工作流提交、重生成、
 * 滚动控制、对话模式切换等逻辑。onChunk 回调通过 createChunkHandler 工厂函数
 * 复用，避免 sendMessage 与 handleRegenerate 的重复代码。
 * TTS/子Agent/工具活动等跨关注点副作用通过 options 回调交由对应 composable 处理。
 */
import { ref, computed, watch, nextTick } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import { useChatStore } from '../stores/chat'
import { useModelStore } from '../stores/model'
import { useWorkflowStore } from '../stores/workflow'
import { useStatsStore } from '../stores/stats'
import { useTaskStreamStore } from '../stores/taskStream'
import { useToast } from './useToast'
import { createLuomiNestRendererLogger } from '../utils/logger'
import { generateId } from '../utils/id'
import type { ChatStreamChunk, SubagentEvent } from '../types'
import type { ToolActivity, SubagentActivity, ChatModeLevel, WorkflowModeOption } from '../components/workbench/types'
import type { WorkbenchModelOption } from './useWorkbenchLive2D'
import type { NavigationTarget } from './useTaskNavigation'
import WorkbenchChatArea from '../components/workbench/WorkbenchChatArea.vue'
import WorkbenchInputArea from '../components/workbench/WorkbenchInputArea.vue'

const logger = createLuomiNestRendererLogger('Workbench')

/** 发送消息选项（chatStore.sendMessage 的 options 子集） */
interface WorkbenchSendMessageOptions {
  agentId: string
  model?: string
  provider?: string
  temperature: number
  maxTokens: number
  topP: number
  chatMode: ChatModeLevel
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
  selectModel: (providerId: string, modelId: string) => Promise<void>
  availableModelOptions: ComputedRef<WorkbenchModelOption[]>
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
    selectModel,
    availableModelOptions,
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

  // 对话模式（普通/标准/超长）
  const chatMode = ref<ChatModeLevel>('normal')
  const CHAT_MODE_OPTIONS: WorkflowModeOption[] = [
    { value: 'normal', label: '普通', title: '普通模式：非工作流，工具最少（任务视图操作 + 表情操控）' },
    { value: 'standard', label: '标准', title: '标准模式：工作流，平衡速度与深度，排除细粒度浏览器工具' },
    { value: 'ultra', label: '超长', title: '超长模式：工作流，最大能力，全部工具可用' },
  ]
  const isWorkflowMode = computed(() => chatMode.value !== 'normal')

  const REASONING_MODEL_KEYWORDS = ['reasoner', 'reason', 'o1', 'o3', 'o4', 'thinking', 'r1']
  const isReasoningModel = (modelId: string): boolean => {
    const lower = modelId.toLowerCase()
    return REASONING_MODEL_KEYWORDS.some((kw) => lower.includes(kw))
  }

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
          (a) => a.name === ev.tool_name && a.iteration === (chunk.iteration || 0) && a.status !== 'completed' && a.status !== 'failed'
        )
        if (activity) {
          if (ev.status === 'started') {
            activity.status = 'running'
          } else if (ev.status === 'completed') {
            activity.status = 'completed'
            activity.output = ev.output || ''
          } else if (ev.status === 'failed') {
            activity.status = 'failed'
            activity.output = ev.output || ''
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
    chatMode.value = mode
    const opts = availableModelOptions.value
    if (opts.length === 0) return
    // 工作流模式优先推理模型，普通模式优先快速模型
    if (mode !== 'normal') {
      const reasoning = opts.find((opt) => isReasoningModel(opt.modelId))
      if (reasoning) selectModel(reasoning.providerId, reasoning.modelId)
    } else {
      const fast = opts.find((opt) => !isReasoningModel(opt.modelId))
      if (fast) selectModel(fast.providerId, fast.modelId)
    }
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
          const msgs = chatStore.convMessages[convId] || []
          const updatedMsgs = msgs.map((m) =>
            m.id === assistantMsgId
              ? { ...m, reasoningContent: (m.reasoningContent || '') + reasoningContent }
              : m
          )
          chatStore.convMessages = { ...chatStore.convMessages, [convId]: updatedMsgs }
        },
        onPlanCreated: (sessionId: string, taskCount: number) => {
          const msgs = chatStore.convMessages[convId] || []
          const updatedMsgs = msgs.map((m) =>
            m.id === assistantMsgId
              ? { ...m, workflowSessionId: sessionId, workflowTaskCount: taskCount }
              : m
          )
          chatStore.convMessages = { ...chatStore.convMessages, [convId]: updatedMsgs }
        },
        onFinalResult: (result: string) => {
          const msgs = chatStore.convMessages[convId] || []
          const updatedMsgs = msgs.map((m) =>
            m.id === assistantMsgId
              ? { ...m, content: result || '工作流执行完成', done: true }
              : m
          )
          chatStore.convMessages = { ...chatStore.convMessages, [convId]: updatedMsgs }

          if (result) {
            try {
              feedChunk({
                id: generateId('workflow'),
                content: result,
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
        },
      })
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e)
      toast.error(`工作流执行失败：${errMsg}`)
      const msgs = chatStore.convMessages[convId] || []
      const updatedMsgs = msgs.map((m) =>
        m.id === assistantMsgId
          ? { ...m, content: `工作流执行失败：${errMsg}`, done: true }
          : m
      )
      chatStore.convMessages = { ...chatStore.convMessages, [convId]: updatedMsgs }
      finishStream()
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
    // 子组件引用
    chatAreaRef,
    // 方法
    scrollToBottom,
    handleMessagesScroll,
    selectChatMode,
    sendMessage,
    cancelStreaming,
    handleRegenerate,
  }
}
