<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch, type VNodeRef } from 'vue'
import { useChatStore } from '../stores/chat'
import { useAgentStore } from '../stores/agent'
import { useModelStore } from '../stores/model'
import { useMemoryStore } from '../stores/memory'
import { usePlatformStore } from '../stores/platform'
import { useLuomiNestLive2D } from '../composables/useLuomiNestLive2D'
import { useAvatarChat } from '../composables/useAvatarChat'
import { useDebouncedSearch } from '../composables/useDebouncedSearch'
import { useApi } from '../composables/useApi'
import { useToast } from '../composables/useToast'
import { getProviderLogo } from '../config/provider-logos'
import { LUOMINEST_BUILTIN_MODELS, getAvatarBinding, resolveExpressionByModelUrl } from '../config/luominest-models'
import { useAvatarControlStore } from '../stores/avatar-control'
import { useTaskStreamStore } from '../stores/taskStream'
import { useWorkflowStore } from '../stores/workflow'
import { useStatsStore } from '../stores/stats'
import type { ConversationSearchResult, ChatStreamChunk, SubagentEvent, AgentProfile } from '../types'
import type {
  ToolActivity,
  SubagentActivity,
  SubagentToolCall,
  McpServerStatus,
  McpStatus,
  WorkflowModeLevel,
  WorkflowModeOption,
  WorkflowPendingPlan,
  TimeGroup,
} from '../components/workbench/types'
import { generateId } from '../utils/id'
import WorkbenchHistoryPanel from '../components/workbench/WorkbenchHistoryPanel.vue'
import WorkbenchChatArea from '../components/workbench/WorkbenchChatArea.vue'
import WorkbenchInputArea from '../components/workbench/WorkbenchInputArea.vue'
import WorkbenchAvatarPanel from '../components/workbench/WorkbenchAvatarPanel.vue'
import WorkbenchToolPanel from '../components/workbench/WorkbenchToolPanel.vue'

const chatStore = useChatStore()
const agentStore = useAgentStore()
const modelStore = useModelStore()
const memoryStore = useMemoryStore()
const platformStore = usePlatformStore()
const taskStreamStore = useTaskStreamStore()
const workflowStore = useWorkflowStore()
const statsStore = useStatsStore()
const avatarControl = useAvatarControlStore()
const { apiGet } = useApi()
const toast = useToast()

// 桌面宠物模式：通过全局 store 状态统一管理，与 AvatarView 共享同一状态源
const isDesktopMode = computed(() => avatarControl.isDesktopPetRunning)

// 主 Agent 固定标识
const MAIN_AGENT_ID = 'luominest_main_agent'

const MAIN_AGENT_PROFILE: AgentProfile = {
  id: MAIN_AGENT_ID,
  name: '主智能体',
  description: 'LuomiNest 工作台主 Agent，驱动 Live2D、记忆、工具、MCP 和子 Agent',
  color: 'var(--lumi-brand)',
  isMain: true,
  isActive: true,
}

// 工具调用与子 Agent 活动追踪
const toolActivities = ref<ToolActivity[]>([])
const expandedToolOutputs = ref<Record<string, boolean>>({})
const subagentActivities = ref<SubagentActivity[]>([])
const expandedSubagents = ref<Record<string, boolean>>({})
const expandedSubagentTools = ref<Record<string, boolean>>({})

const toggleToolOutput = (id: string) => {
  expandedToolOutputs.value = { ...expandedToolOutputs.value, [id]: !expandedToolOutputs.value[id] }
}

const toggleSubagent = (id: string) => {
  expandedSubagents.value = { ...expandedSubagents.value, [id]: !expandedSubagents.value[id] }
}

const toggleSubagentTools = (id: string) => {
  expandedSubagentTools.value = { ...expandedSubagentTools.value, [id]: !expandedSubagentTools.value[id] }
}

const handleSubagentEvent = (event: SubagentEvent) => {
  const existing = subagentActivities.value.find((a) => a.id === event.subagent_id)

  if (event.status === 'started') {
    if (existing) {
      existing.status = 'running'
      existing.task = event.task
      existing.depth = event.depth
      existing.iteration = 0
      existing.toolCalls = []
      existing.progress = undefined
      existing.result = undefined
      existing.error = undefined
    } else {
      subagentActivities.value.push({
        id: event.subagent_id,
        task: event.task,
        depth: event.depth,
        status: 'running',
        iteration: 0,
        toolCalls: [],
      })
    }
    return
  }

  if (!existing) return

  if (event.status === 'running') {
    existing.status = 'running'
    if (event.iteration !== undefined) existing.iteration = event.iteration
    if (event.progress) existing.progress = event.progress

    if (event.tool_name) {
      if (event.tool_output !== undefined) {
        const lastCall = [...existing.toolCalls]
          .reverse()
          .find((c) => c.name === event.tool_name && c.status === 'running')
        if (lastCall) {
          lastCall.status = 'completed'
          lastCall.output = event.tool_output
        }
      } else {
        existing.toolCalls.push({
          name: event.tool_name,
          args: event.tool_args,
          status: 'running',
        } as SubagentToolCall)
      }
    }
    return
  }

  if (event.status === 'completed') {
    existing.status = 'completed'
    if (event.result) existing.result = event.result
    existing.progress = undefined
    for (const tc of existing.toolCalls) {
      if (tc.status === 'running') tc.status = 'completed'
    }
    return
  }

  if (event.status === 'failed') {
    existing.status = 'failed'
    if (event.error) existing.error = event.error
    existing.progress = undefined
    for (const tc of existing.toolCalls) {
      if (tc.status === 'running') tc.status = 'completed'
    }
  }
}

// Live2D 集成
const canvasRef = ref<HTMLCanvasElement | null>(null)
const setCanvasRef: VNodeRef = (el) => {
  canvasRef.value = el as HTMLCanvasElement | null
}
const {
  isReady: isModelReady,
  isLoading: isModelLoading,
  error: loadError,
  loadModel,
  driveEmotion,
  syncLipParam,
  destroy: teardownLive2D,
} = useLuomiNestLive2D(canvasRef)

// TTS / 字幕
const ttsEnabled = ref(true)
const subtitleEnabled = ref(true)
const currentModelInfo = ref(LUOMINEST_BUILTIN_MODELS[0])
const currentBinding = computed(() => getAvatarBinding(currentModelInfo.value.id))

let inCodeBlock = false
const filterCodeForTts = (content: string): string => {
  if (!content) return ''
  const parts = content.split('```')
  let result = ''
  for (let i = 0; i < parts.length; i++) {
    if (i === 0) {
      if (!inCodeBlock) result += parts[i]
    } else {
      inCodeBlock = !inCodeBlock
      if (!inCodeBlock) result += parts[i]
    }
  }
  return result
}

const {
  isSpeaking,
  isSynthesizing,
  subtitleText,
  subtitleVisible,
  feedChunk,
  finishStream,
  stop: stopTts,
  dismissSubtitle,
} = useAvatarChat({
  voice: () => currentBinding.value?.voice || 'zh-CN-XiaoxiaoNeural',
  engine: () => modelStore.ttsConfig.provider || modelStore.ttsConfig.engine || 'auto',
  ttsConfig: () => ({
    model: modelStore.ttsConfig.model,
    speed: modelStore.ttsConfig.speed,
    apiKey: modelStore.ttsConfig.apiKey,
    baseUrl: modelStore.ttsConfig.baseUrl,
  }),
  driveEmotion: (emotionId: string) => {
    if (isDesktopMode.value) {
      const modelUrl = currentModelInfo.value.url
      const resolved = resolveExpressionByModelUrl(modelUrl, emotionId)
      avatarControl.triggerExpression(resolved)
    } else {
      driveEmotion(emotionId)
    }
  },
  syncLipParam: (value: number) => {
    if (isDesktopMode.value) {
      avatarControl.driveLipSync(value)
    } else {
      syncLipParam(value)
    }
  },
  ttsEnabled: () => ttsEnabled.value,
  subtitleEnabled: () => subtitleEnabled.value,
  onTtsError: (err: Error) => toast.warning(`语音合成失败：${err.message}`),
})

watch([subtitleVisible, subtitleText, isDesktopMode], ([visible, text, desktopMode]) => {
  if (!desktopMode) return
  if (visible && text) {
    window.api.desktopPet.sendSubtitle(text)
  } else {
    window.api.desktopPet.hideSubtitle()
  }
})

// 布局与状态面板
const isHistoryCollapsed = ref(false)
const mcpStatus = ref<McpStatus>({ servers: [], totalTools: 0 })
const sidePanelCollapsed = ref<Record<string, boolean>>({
  memory: true,
  mcp: true,
  platform: true,
  subagent: true,
})

const toggleSidePanel = (key: string) => {
  sidePanelCollapsed.value = { ...sidePanelCollapsed.value, [key]: !sidePanelCollapsed.value[key] }
}

const fetchMcpStatus = async () => {
  try {
    const result = await apiGet<{ servers: McpServerStatus[]; count: number }>('/mcp/servers')
    const servers = result.servers || []
    const totalTools = servers.reduce((sum, s) => sum + (s.tool_count || 0), 0)
    mcpStatus.value = { servers, totalTools }
  } catch {
    mcpStatus.value = { servers: [], totalTools: 0 }
  }
}

const memorySummaryPreview = computed(() => {
  const s = memoryStore.summaryContent
  if (!s) return '暂无摘要'
  return s.length > 120 ? s.slice(0, 120) + '...' : s
})

const activePlatformCount = computed(() => platformStore.activeInstances.length)

// 对话历史
const searchQuery = ref('')
const { results: searchResults, isSearching } = useDebouncedSearch<ConversationSearchResult[]>(
  searchQuery,
  (q) => chatStore.searchConversations(q),
  300,
)

const isSearchMode = computed(() => searchQuery.value.trim().length > 0)

const timeGroups = computed<TimeGroup[]>(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const groups: TimeGroup[] = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '近7天', items: [] },
    { label: '更早', items: [] },
  ]

  for (const conv of chatStore.conversations) {
    const d = new Date(conv.updated_at)
    const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
    const diffDays = Math.floor((today.getTime() - target.getTime()) / 86400000)
    if (diffDays <= 0) groups[0].items.push(conv)
    else if (diffDays === 1) groups[1].items.push(conv)
    else if (diffDays <= 7) groups[2].items.push(conv)
    else groups[3].items.push(conv)
  }

  return groups.filter((g) => g.items.length > 0)
})

const selectConversation = (convId: string, searchKeyword?: string) => {
  if (searchKeyword) {
    chatStore.pendingSearchKeyword = searchKeyword
    chatStore.searchScrollTarget = { convId, keyword: searchKeyword }
  }
  chatStore.loadConversation(convId)
}

const handleNewConversation = () => {
  const prevConvId = chatStore.currentConvId
  if (prevConvId) {
    chatStore.leaveCurrentConversation(prevConvId).catch(() => {})
  }
  chatStore.clearMessages()
}

const handleDeleteConversation = async (convId: string) => {
  try {
    await chatStore.deleteConversation(convId, MAIN_AGENT_ID)
  } catch (e: unknown) {
    const errMsg = e instanceof Error ? e.message : String(e)
    toast.error(`删除对话失败：${errMsg}`)
  }
}

// 重命名
const renamingConvId = ref<string | null>(null)
const renamingTitle = ref('')

const startRename = (convId: string, currentTitle: string) => {
  renamingConvId.value = convId
  renamingTitle.value = currentTitle
}

const confirmRename = async () => {
  if (!renamingConvId.value) return
  const newTitle = renamingTitle.value.trim()
  if (!newTitle) {
    renamingConvId.value = null
    return
  }
  if (newTitle.length > 200) {
    toast.warning('标题过长，请限制在 200 字符以内')
    return
  }
  const success = await chatStore.renameConversation(renamingConvId.value, newTitle, MAIN_AGENT_ID)
  if (success) {
    renamingConvId.value = null
    renamingTitle.value = ''
  } else {
    toast.error('重命名对话失败，请重试')
  }
}

const cancelRename = () => {
  renamingConvId.value = null
  renamingTitle.value = ''
}

// 对话面板
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

// 工作流模式
const workflowMode = ref(false)
const workflowModeLevel = ref<WorkflowModeLevel>('standard')
const WORKFLOW_MODE_OPTIONS: WorkflowModeOption[] = [
  { value: 'flash', label: '闪电', title: '闪电模式：快速响应简单任务，跳过计划确认' },
  { value: 'standard', label: '标准', title: '标准模式：平衡速度与深度，需确认计划' },
  { value: 'pro', label: '专业', title: '专业模式：更多迭代与并发，适合中等复杂任务' },
  { value: 'ultra', label: '超长', title: '超长模式：最大能力，适合复杂长任务' },
]

const REASONING_MODEL_KEYWORDS = ['reasoner', 'reason', 'o1', 'o3', 'o4', 'thinking', 'r1']
const isReasoningModel = (modelId: string): boolean => {
  const lower = modelId.toLowerCase()
  return REASONING_MODEL_KEYWORDS.some((kw) => lower.includes(kw))
}

const currentModel = computed(() => {
  const resolved = modelStore.resolveModel
  return resolved?.model || '未配置模型'
})

const currentProvider = computed(() => {
  const resolved = modelStore.resolveModel
  return resolved?.provider || ''
})

const currentProviderLogo = computed(() => getProviderLogo(currentProvider.value))

const showModelDropdown = ref(false)
const availableModelOptions = computed(() => {
  const options: {
    providerId: string
    providerName: string
    providerLogo: ReturnType<typeof getProviderLogo>
    modelId: string
    modelName: string
  }[] = []
  for (const provider of modelStore.providers) {
    const logo = getProviderLogo(provider.id)
    const modelIds = provider.selectedModels.length > 0
      ? provider.selectedModels
      : (provider.defaultModel ? [provider.defaultModel] : [])
    for (const modelId of modelIds) {
      options.push({
        providerId: provider.id,
        providerName: provider.name,
        providerLogo: logo,
        modelId,
        modelName: modelId,
      })
    }
  }
  return options
})

const selectModel = async (providerId: string, modelId: string) => {
  try {
    await platformStore.updateMainAgent({ provider: providerId, model: modelId })
  } catch (e: any) {
    toast.error(`切换模型失败：${e.message || '未知错误'}`)
  }
  showModelDropdown.value = false
}

const toggleWorkflowMode = () => {
  workflowMode.value = !workflowMode.value
  const options = availableModelOptions.value
  if (options.length === 0) return
  if (workflowMode.value) {
    const reasoning = options.find((opt) => isReasoningModel(opt.modelId))
    if (reasoning) selectModel(reasoning.providerId, reasoning.modelId)
  } else {
    const fast = options.find((opt) => !isReasoningModel(opt.modelId))
    if (fast) selectModel(fast.providerId, fast.modelId)
  }
}

const canSend = computed(() => {
  if (!isBackendReady.value) return false
  return inputText.value.trim().length > 0
})

const chatAreaRef = ref<InstanceType<typeof WorkbenchChatArea> | null>(null)
const inputAreaRef = ref<InstanceType<typeof WorkbenchInputArea> | null>(null)

const scrollToBottom = (force = false) => {
  chatAreaRef.value?.scrollToBottom(force)
}

const handleMessagesScroll = (metrics: { scrollTop: number; scrollHeight: number; clientHeight: number }) => {
  const { scrollTop, scrollHeight, clientHeight } = metrics
  const distanceFromBottom = scrollHeight - scrollTop - clientHeight
  isNearBottom.value = distanceFromBottom < SCROLL_BOTTOM_THRESHOLD
  showScrollToBottomBtn.value = !isNearBottom.value && messages.value.length > 0
}

const sendMessage = async () => {
  if (!canSend.value) return

  const content = inputText.value.trim()
  inputText.value = ''
  inputAreaRef.value?.resetTextareaHeight()
  statsStore.recordPrompt(content)

  const resolved = modelStore.resolveModel

  if (workflowMode.value) {
    await submitWorkflowTask(content, resolved)
    return
  }

  toolActivities.value = []
  subagentActivities.value = []

  const options: any = {
    agentId: MAIN_AGENT_ID,
    model: resolved?.model || undefined,
    provider: resolved?.provider || undefined,
    temperature: modelStore.modelConfig.defaultTemperature,
    maxTokens: modelStore.modelConfig.defaultMaxTokens,
    topP: modelStore.modelConfig.defaultTopP,
    onChunk: (chunk: ChatStreamChunk) => {
      statsStore.interceptChunk(chunk, chatStore.currentConvId)

      if (chunk.done) {
        finishStream()
        return
      }
      if (chunk.subagent_event) {
        handleSubagentEvent(chunk.subagent_event)
        taskStreamStore.handleSubagentEvent(chunk.subagent_event)
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
    },
  }

  inCodeBlock = false
  isNearBottom.value = true
  try {
    await chatStore.sendMessage(content, options)
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
) => {
  toolActivities.value = []
  subagentActivities.value = []
  isNearBottom.value = true
  inCodeBlock = false

  let convId = chatStore.currentConvId
  if (!convId) {
    try {
      const conv = await chatStore.createConversation(
        content.slice(0, 30) || '新对话',
        MAIN_AGENT_ID,
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
      mode: workflowModeLevel.value,
      onPhaseChange: (phase) => {
        console.info(`[Workbench] 工作流阶段: ${phase}`)
      },
      onReasoning: (reasoningContent) => {
        const msgs = chatStore.convMessages[convId] || []
        const updatedMsgs = msgs.map((m) =>
          m.id === assistantMsgId
            ? { ...m, reasoningContent: (m.reasoningContent || '') + reasoningContent }
            : m
        )
        chatStore.convMessages = { ...chatStore.convMessages, [convId]: updatedMsgs }
      },
      onFinalResult: (result) => {
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
            console.warn('[Workbench] TTS 播报失败，消息已正常显示:', ttsErr)
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

const cancelStreaming = () => {
  if (workflowStore.isRunning) {
    workflowStore.cancelWorkflow()
    return
  }
  chatStore.cancelCurrentRequest()
  stopTts()
}

const handleRegenerate = async (messageId: string) => {
  inCodeBlock = false
  toolActivities.value = []
  subagentActivities.value = []
  await chatStore.regenerateMessage(messageId, {
    onChunk: (chunk: ChatStreamChunk) => {
      if (chunk.done) {
        finishStream()
        return
      }
      if (chunk.subagent_event) {
        handleSubagentEvent(chunk.subagent_event)
        taskStreamStore.handleSubagentEvent(chunk.subagent_event)
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
    },
  })
  await nextTick()
  scrollToBottom(true)
}

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

watch(
  messages,
  () => {
    if (isStreaming.value && isNearBottom.value) {
      nextTick(() => scrollToBottom())
    }
  },
  { deep: true }
)

watch(isLoadingCurrentConv, (loading) => {
  if (loading) {
    isNearBottom.value = true
  } else {
    nextTick(() => scrollToBottom(true))
  }
})

const switchModel = async (model: typeof LUOMINEST_BUILTIN_MODELS[0]) => {
  currentModelInfo.value = model
  if (isDesktopMode.value) {
    await window.api.desktopPet.loadModel(model)
  } else {
    await loadModel(model.url, model.scale)
  }
}

onMounted(async () => {
  agentStore.setActiveAgent(MAIN_AGENT_PROFILE)

  await chatStore.checkBackend()
  if (chatStore.isBackendReady) {
    await Promise.all([
      agentStore.fetchAgents(),
      modelStore.fetchProviders(),
      modelStore.fetchModelConfig(),
      platformStore.fetchMainAgent(),
      chatStore.fetchConversations(MAIN_AGENT_ID),
      memoryStore.fetchMemory(MAIN_AGENT_ID),
      memoryStore.fetchSummary(MAIN_AGENT_ID),
      platformStore.fetchInstances(),
      fetchMcpStatus(),
    ])
  }
  await avatarControl.checkDesktopPetStatus()
  if (!isDesktopMode.value) {
    const defaultModel = LUOMINEST_BUILTIN_MODELS[0]
    await loadModel(defaultModel.url, defaultModel.scale)
  }
  document.addEventListener('click', handleClickOutsideModel)
  nextTick(() => chatAreaRef.value?.setupResizeObserver())
})

watch(isDesktopMode, async (desktopMode) => {
  if (desktopMode) {
    teardownLive2D()
  } else {
    await nextTick()
    const modelToLoad = currentModelInfo.value
    await loadModel(modelToLoad.url, modelToLoad.scale)
  }
})

const handleClickOutsideModel = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.closest('.model-dropdown-container')) {
    showModelDropdown.value = false
  }
}

onBeforeUnmount(() => {
  chatAreaRef.value?.teardownResizeObserver()
  document.removeEventListener('click', handleClickOutsideModel)
  stopTts()
  teardownLive2D()
})
</script>

<template>
  <div class="workbench-layout">
    <WorkbenchHistoryPanel
      v-model:search-query="searchQuery"
      v-model:renaming-title="renamingTitle"
      :is-search-mode="isSearchMode"
      :search-results="searchResults"
      :is-searching="isSearching"
      :time-groups="timeGroups"
      :current-conv-id="chatStore.currentConvId"
      :renaming-conv-id="renamingConvId"
      :is-history-collapsed="isHistoryCollapsed"
      @select="selectConversation"
      @new-conversation="handleNewConversation"
      @start-rename="startRename"
      @confirm-rename="confirmRename"
      @cancel-rename="cancelRename"
      @delete-conversation="handleDeleteConversation"
      @collapse="isHistoryCollapsed = true"
      @expand="isHistoryCollapsed = false"
    />

    <div class="workbench-chat">
      <WorkbenchChatArea
        ref="chatAreaRef"
        :messages="messages"
        :is-loading-current-conv="isLoadingCurrentConv"
        :is-streaming="isStreaming"
        :is-backend-ready="isBackendReady"
        :current-model="currentModel"
        :tool-activities="toolActivities"
        :subagent-activities="subagentActivities"
        :expanded-tool-outputs="expandedToolOutputs"
        :expanded-subagents="expandedSubagents"
        :expanded-subagent-tools="expandedSubagentTools"
        :show-reasoning="showReasoning"
        :workflow-pending-plan="(workflowStore.pendingPlan as WorkflowPendingPlan | null)"
        :confirmation-feedback="workflowStore.confirmationFeedback"
        :is-near-bottom="isNearBottom"
        :show-scroll-to-bottom-btn="showScrollToBottomBtn"
        @toggle-reasoning="(id) => { showReasoning = { ...showReasoning, [id]: !showReasoning[id] } }"
        @regenerate="handleRegenerate"
        @toggle-tool-output="toggleToolOutput"
        @toggle-subagent="toggleSubagent"
        @toggle-subagent-tools="toggleSubagentTools"
        @confirm-plan="workflowStore.confirmPlan"
        @reject-plan="workflowStore.rejectPlan"
        @update:confirmation-feedback="(v) => workflowStore.confirmationFeedback = v"
        @scroll="handleMessagesScroll"
        @scroll-to-bottom="scrollToBottom(true)"
        @retry-backend="chatStore.checkBackend()"
        @set-input-text="(text) => inputText = text"
      />

      <WorkbenchInputArea
        ref="inputAreaRef"
        v-model:input-text="inputText"
        v-model:workflow-mode-level="workflowModeLevel"
        v-model:selected-skill-ids="selectedSkillIds"
        :is-backend-ready="isBackendReady"
        :is-streaming="isStreaming"
        :can-send="canSend"
        :current-model="currentModel"
        :current-provider="currentProvider"
        :current-provider-logo="currentProviderLogo"
        :available-model-options="availableModelOptions"
        :show-model-dropdown="showModelDropdown"
        :workflow-mode="workflowMode"
        :workflow-mode-options="WORKFLOW_MODE_OPTIONS"
        @send="sendMessage"
        @cancel="cancelStreaming"
        @toggle-model-dropdown="showModelDropdown = !showModelDropdown"
        @select-model="selectModel"
        @toggle-workflow-mode="toggleWorkflowMode"
      />
    </div>

    <div class="workbench-avatar">
      <WorkbenchAvatarPanel
        :is-desktop-mode="isDesktopMode"
        :current-model-info="currentModelInfo"
        :is-model-loading="isModelLoading"
        :is-model-ready="isModelReady"
        :load-error="loadError"
        :is-speaking="isSpeaking"
        :is-synthesizing="isSynthesizing"
        :subtitle-visible="subtitleVisible"
        :subtitle-text="subtitleText"
        :tts-enabled="ttsEnabled"
        :subtitle-enabled="subtitleEnabled"
        :builtin-models="LUOMINEST_BUILTIN_MODELS"
        :set-canvas-ref="setCanvasRef"
        @switch-model="switchModel"
        @toggle-tts="ttsEnabled = !ttsEnabled"
        @toggle-subtitle="subtitleEnabled = !subtitleEnabled"
        @stop-tts="stopTts"
        @dismiss-subtitle="dismissSubtitle"
      />

      <WorkbenchToolPanel
        :memory-fact-count="memoryStore.facts.length"
        :memory-profile-name="memoryStore.profile.name"
        :memory-summary-preview="memorySummaryPreview"
        :mcp-status="mcpStatus"
        :platform-instances="platformStore.instances"
        :active-platform-count="activePlatformCount"
        :subagent-activities="subagentActivities"
        :collapsed="sidePanelCollapsed"
        @toggle-panel="toggleSidePanel"
      />
    </div>
  </div>
</template>

<style scoped>
.workbench-layout {
  display: flex;
  width: 100%;
  height: 100%;
  background: var(--bg);
  overflow: hidden;
  position: relative;
}

.workbench-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--bg);
  position: relative;
}

.workbench-avatar {
  width: 340px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border-left: 1px solid var(--border-light);
  flex-shrink: 0;
  overflow: hidden;
}
</style>
