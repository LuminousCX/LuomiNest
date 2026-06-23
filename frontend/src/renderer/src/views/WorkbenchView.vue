<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import {
  Send,
  Square,
  Plus,
  Search,
  MessageSquare,
  Clock,
  Trash2,
  Pencil,
  Check,
  Copy,
  Loader2,
  AlertTriangle,
  RotateCcw,
  ChevronDown,
  PanelLeftClose,
  PanelLeftOpen,
  Bot,
  Sparkles,
  Wand2,
  Volume2,
  VolumeX,
  Subtitles,
  StopCircle,
  Wrench,
  Terminal,
  CheckCircle2,
  XCircle,
  Brain,
  Server,
  Radio,
  ChevronRight,
  Cpu,
  Monitor,
  ListChecks,
  X,
  ClipboardList,
} from 'lucide-vue-next'
import { useChatStore } from '../stores/chat'
import { useAgentStore } from '../stores/agent'
import { useModelStore } from '../stores/model'
import { useMemoryStore } from '../stores/memory'
import { usePlatformStore } from '../stores/platform'
import { useLuomiNestLive2D } from '../composables/useLuomiNestLive2D'
import { useAvatarChat } from '../composables/useAvatarChat'
import { useApi } from '../composables/useApi'
import { useToast } from '../composables/useToast'
import { getProviderLogo } from '../config/provider-logos'
import { stripEmotionTags } from '../utils/emotionTagInterceptor'
import { LUOMINEST_BUILTIN_MODELS, getAvatarBinding, resolveExpressionByModelUrl } from '../config/luominest-models'
import { useAvatarControlStore } from '../stores/avatar-control'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import type { ConversationListItem, ConversationSearchResult, ChatStreamChunk, SubagentEvent, AgentProfile } from '../types'
import { useTaskStreamStore } from '../stores/taskStream'
import { useWorkflowStore } from '../stores/workflow'
import { useStatsStore } from '../stores/stats'

marked.setOptions({
  breaks: true,
  gfm: true,
})

interface ToolActivity {
  id: string
  name: string
  arguments: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  output?: string
  iteration: number
}

/** 子 Agent 工具调用记录 */
interface SubagentToolCall {
  name: string
  args?: string
  output?: string
  status: 'running' | 'completed'
}

/** 子 Agent 执行活动（参考 deer-flow SubtaskCard） */
interface SubagentActivity {
  id: string             // subagent_id
  task: string           // 任务描述
  depth: number          // 委派深度
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress?: string      // 最新进度文本
  result?: string        // 最终结果
  error?: string         // 错误信息
  iteration: number      // 当前迭代轮次
  toolCalls: SubagentToolCall[]  // 工具调用历史
}

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
// 桌宠模式下工作台不渲染本地 Live2D，表情/动作/唇形通过 IPC 转发到桌宠窗口
const isDesktopMode = computed(() => avatarControl.isDesktopPetRunning)

// 主 Agent 固定标识：工作台所有对话均归属主 Agent，与对话页面的模拟联系人彻底分离
const MAIN_AGENT_ID = 'luominest_main_agent'

// 虚拟主 Agent Profile：用于让 chat store 的 computed（currentConvId/messages/conversations）
// 基于 MAIN_AGENT_ID 工作。在 onMounted 中设置到 agentStore.activeAgent。
const MAIN_AGENT_PROFILE: AgentProfile = {
  id: MAIN_AGENT_ID,
  name: '主智能体',
  description: 'LuomiNest 工作台主 Agent，驱动 Live2D、记忆、工具、MCP 和子 Agent',
  color: '#147EBC',
  isMain: true,
  isActive: true,
}

// 工具调用活动追踪（主 Agent 工具调用循环）
const toolActivities = ref<ToolActivity[]>([])
const expandedToolOutputs = ref<Record<string, boolean>>({})

// 子 Agent 群组活动追踪（主 Agent 通过 delegate_to_subagent 委派的子任务）
const subagentActivities = ref<SubagentActivity[]>([])
const expandedSubagents = ref<Record<string, boolean>>({})
const expandedSubagentTools = ref<Record<string, boolean>>({})

const toggleToolOutput = (id: string) => {
  expandedToolOutputs.value = {
    ...expandedToolOutputs.value,
    [id]: !expandedToolOutputs.value[id],
  }
}

const toggleSubagent = (id: string) => {
  expandedSubagents.value = {
    ...expandedSubagents.value,
    [id]: !expandedSubagents.value[id],
  }
}

const toggleSubagentTools = (id: string) => {
  expandedSubagentTools.value = {
    ...expandedSubagentTools.value,
    [id]: !expandedSubagentTools.value[id],
  }
}

/** 处理子 Agent 事件，更新 subagentActivities 状态 */
const handleSubagentEvent = (event: SubagentEvent) => {
  const existing = subagentActivities.value.find(a => a.id === event.subagent_id)

  if (event.status === 'started') {
    if (existing) {
      // 重置已有记录（理论上不应发生）
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

    // 工具调用事件
    if (event.tool_name) {
      if (event.tool_output !== undefined) {
        // 工具结果：更新最后一个同名工具调用
        const lastCall = [...existing.toolCalls].reverse().find(c => c.name === event.tool_name && c.status === 'running')
        if (lastCall) {
          lastCall.status = 'completed'
          lastCall.output = event.tool_output
        }
      } else {
        // 工具开始：添加新工具调用
        existing.toolCalls.push({
          name: event.tool_name,
          args: event.tool_args,
          status: 'running',
        })
      }
    }
    return
  }

  if (event.status === 'completed') {
    existing.status = 'completed'
    if (event.result) existing.result = event.result
    existing.progress = undefined
    // 标记所有未完成的工具调用为已完成
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
    return
  }
}

const activeSubagentCount = computed(
  () => subagentActivities.value.filter(a => a.status === 'running').length
)

const formatToolArgs = (args: string): string => {
  try {
    const parsed = JSON.parse(args)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return args
  }
}

// Live2D 集成
const canvasRef = ref<HTMLCanvasElement | null>(null)
const {
  isReady: isModelReady,
  isLoading: isModelLoading,
  error: loadError,
  loadModel,
  driveEmotion,
  syncLipParam,
  destroy: teardownLive2D,
} = useLuomiNestLive2D(canvasRef)

// TTS 配置状态
const ttsEnabled = ref(true)
const subtitleEnabled = ref(true)

// 当前模型绑定信息（用于获取 voice）
const currentModelInfo = ref(LUOMINEST_BUILTIN_MODELS[0])
const currentBinding = computed(() => getAvatarBinding(currentModelInfo.value.id))

// 代码块过滤状态机：跳过 ``` 包裹的代码块，不送入 TTS
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

// Avatar Chat TTS 集成（流式分段 + 唇形同步 + 表情驱动 + 字幕）
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
  driveEmotion: (emotionId: string) => {
    if (isDesktopMode.value) {
      // 桌宠模式：通过 IPC 转发到桌宠窗口（需先做表情名映射，与 composable 内部逻辑一致）
      const modelUrl = currentModelInfo.value.url
      const resolved = resolveExpressionByModelUrl(modelUrl, emotionId)
      avatarControl.triggerExpression(resolved)
    } else {
      driveEmotion(emotionId)
    }
  },
  syncLipParam: (value: number) => {
    if (isDesktopMode.value) {
      // 桌宠模式：唇形同步值通过 IPC 转发到桌宠窗口
      avatarControl.driveLipSync(value)
    } else {
      syncLipParam(value)
    }
  },
  ttsEnabled: () => ttsEnabled.value,
  subtitleEnabled: () => subtitleEnabled.value,
  onTtsError: (err: Error) => toast.warning(`语音合成失败：${err.message}`),
})

// 桌宠模式下：将字幕同步到桌宠窗口（与 AvatarView 行为一致）
watch([subtitleVisible, subtitleText, isDesktopMode], ([visible, text, desktopMode]) => {
  if (!desktopMode) return
  if (visible && text) {
    window.api.desktopPet.sendSubtitle(text)
  } else {
    window.api.desktopPet.hideSubtitle()
  }
})

// 布局状态
const isHistoryCollapsed = ref(false)

// ===== 主 Agent 状态面板（右栏可折叠：记忆 / MCP / 消息平台）=====
interface McpServerStatus {
  name: string
  status: string
  tool_count: number
  description?: string
  tools?: string[]
}
interface McpStatus {
  servers: McpServerStatus[]
  totalTools: number
}

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

const connectedMcpCount = computed(() => mcpStatus.value.servers.filter(s => s.status === 'connected').length)

const memorySummaryPreview = computed(() => {
  const s = memoryStore.summaryContent
  if (!s) return '暂无摘要'
  return s.length > 120 ? s.slice(0, 120) + '...' : s
})

const activePlatformCount = computed(() => platformStore.activeInstances.length)

// 对话历史
const searchQuery = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null
let searchSeq = 0
const searchResults = ref<ConversationSearchResult[]>([])
const isSearching = ref(false)

const isSearchMode = computed(() => searchQuery.value.trim().length > 0)

watch(searchQuery, (q) => {
  if (searchTimer) clearTimeout(searchTimer)
  if (!q.trim()) {
    searchResults.value = []
    isSearching.value = false
    return
  }
  isSearching.value = true
  searchSeq++
  const currentSeq = searchSeq
  searchTimer = setTimeout(async () => {
    const results = await chatStore.searchConversations(q)
    if (currentSeq === searchSeq) {
      searchResults.value = results
      isSearching.value = false
    }
  }, 300)
})

interface TimeGroup {
  label: string
  items: ConversationListItem[]
}

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

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const formatTime = (dateStr: string) => {
  const d = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diffDays = Math.floor((today.getTime() - target.getTime()) / 86400000)
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

  if (diffDays <= 0) return time
  if (diffDays === 1) return `昨天 ${time}`
  if (diffDays <= 7) return `${WEEKDAYS[d.getDay()]} ${time}`
  if (d.getFullYear() === now.getFullYear()) return `${d.getMonth() + 1}月${d.getDate()}日`
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

const highlightSnippet = (snippet: string): string => {
  if (!snippet) return ''
  const escaped = snippet
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
  const q = searchQuery.value.trim()
  if (!q) return escaped
  const escapedQ = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${escapedQ})`, 'gi')
  return escaped.replace(regex, '<mark>$1</mark>')
}

const selectConversation = (convId: string, searchKeyword?: string) => {
  if (searchKeyword) {
    chatStore.pendingSearchKeyword = searchKeyword
    chatStore.searchScrollTarget = { convId, keyword: searchKeyword }
  }
  chatStore.loadConversation(convId)
}

const handleNewConversation = () => {
  // activeAgent 已在 onMounted 中设为虚拟主 Agent，currentConvId 基于 activeAgentId
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
  nextTick(() => {
    const input = document.querySelector('.workbench-rename-input') as HTMLInputElement
    if (input) {
      input.focus()
      input.select()
    }
  })
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
const messagesContainer = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const copiedId = ref<string | null>(null)
const showReasoning = ref<Record<string, boolean>>({})
const isNearBottom = ref(true)
const SCROLL_BOTTOM_THRESHOLD = 120
const showScrollToBottomBtn = ref(false)
let resizeObserver: ResizeObserver | null = null

const messages = computed(() => chatStore.messages)
const isStreaming = computed(() => chatStore.isStreaming || workflowStore.isRunning)
const isBackendReady = computed(() => chatStore.isBackendReady)
const isLoadingCurrentConv = computed(() => chatStore.isLoadingCurrentConversation)

// 工作流模式：开启后输入的任务将通过 WorkflowEngine 执行长任务
const workflowMode = ref(false)
// 工作流执行模式（P2：长任务执行模式）
// - flash: 闪电模式，快速响应简单任务（跳过计划确认）
// - standard: 标准模式，平衡速度与深度（默认）
// - pro: 专业模式，更多迭代与并发，适合中等复杂任务
// - ultra: 超长模式，最大能力，适合复杂长任务
type WorkflowModeLevel = 'flash' | 'standard' | 'pro' | 'ultra'
const workflowModeLevel = ref<WorkflowModeLevel>('standard')
const WORKFLOW_MODE_OPTIONS: Array<{
  value: WorkflowModeLevel
  label: string
  title: string
}> = [
  { value: 'flash', label: '闪电', title: '闪电模式：快速响应简单任务，跳过计划确认' },
  { value: 'standard', label: '标准', title: '标准模式：平衡速度与深度，需确认计划' },
  { value: 'pro', label: '专业', title: '专业模式：更多迭代与并发，适合中等复杂任务' },
  { value: 'ultra', label: '超长', title: '超长模式：最大能力，适合复杂长任务' },
]

// 推理模型关键词：模型名包含这些词的视为推理模型
const REASONING_MODEL_KEYWORDS = ['reasoner', 'reason', 'o1', 'o3', 'o4', 'thinking', 'r1']

/** 判断模型是否是推理模型 */
const isReasoningModel = (modelId: string): boolean => {
  const lower = modelId.toLowerCase()
  return REASONING_MODEL_KEYWORDS.some(kw => lower.includes(kw))
}

const currentModel = computed(() => {
  const resolved = modelStore.resolveModel
  return resolved?.model || '未配置模型'
})

const currentProvider = computed(() => {
  const resolved = modelStore.resolveModel
  return resolved?.provider || ''
})

/**
 * 切换工作流模式时自动选择对应类型的模型
 * - 工作流模式 → 优先选择推理模型（deepseek-reasoner, o1 等）
 * - 普通模式 → 优先选择快速响应模型（deepseek-chat, gpt-4o 等）
 */
const toggleWorkflowMode = () => {
  workflowMode.value = !workflowMode.value

  const options = availableModelOptions.value
  if (options.length === 0) return

  if (workflowMode.value) {
    // 工作流模式：优先选择推理模型
    const reasoning = options.find(opt => isReasoningModel(opt.modelId))
    if (reasoning) {
      selectModel(reasoning.providerId, reasoning.modelId)
    }
  } else {
    // 普通模式：优先选择快速响应模型
    const fast = options.find(opt => !isReasoningModel(opt.modelId))
    if (fast) {
      selectModel(fast.providerId, fast.modelId)
    }
  }
}

const currentProviderLogo = computed(() => getProviderLogo(currentProvider.value))

// 模型下拉框：只展示各供应商已多选的模型（selectedModels）
const showModelDropdown = ref(false)
const availableModelOptions = computed(() => {
  const options: { providerId: string; providerName: string; providerLogo: ReturnType<typeof getProviderLogo>; modelId: string; modelName: string }[] = []
  for (const provider of modelStore.providers) {
    const logo = getProviderLogo(provider.id)
    // 优先使用已多选模型；若未多选则回退到 defaultModel
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

const canSend = computed(() => {
  if (!isBackendReady.value) return false
  return inputText.value.trim().length > 0
})

const sendMessage = async () => {
  if (!canSend.value) return

  const content = inputText.value.trim()
  inputText.value = ''
  resetTextareaHeight()

  // Token 侦听器：记录 prompt 字符数
  statsStore.recordPrompt(content)

  // 模型配置：使用工具栏选择的模型（modelStore.resolveModel）
  const resolved = modelStore.resolveModel

  // 工作流模式：通过 WorkflowEngine 执行长任务
  if (workflowMode.value) {
    await submitWorkflowTask(content, resolved)
    return
  }

  // 重置工具调用活动追踪
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
      // Token 侦听器：拦截 LLM 返回的所有字符
      statsStore.interceptChunk(chunk, chatStore.currentConversationId)

      if (chunk.done) {
        finishStream()
        return
      }
      // 处理子 Agent 执行事件（含浏览器工具事件）
      if (chunk.subagent_event) {
        handleSubagentEvent(chunk.subagent_event)
        taskStreamStore.handleSubagentEvent(chunk.subagent_event)
      }
      // 处理定时任务事件
      if (chunk.task_event) {
        taskStreamStore.handleTaskEvent(chunk.task_event)
      }
      // 处理工具调用事件
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
        feedChunk({
          ...chunk,
          content: filteredContent,
        })
      }
    },
  }
  // systemPrompt 由后端 build_system_prompt 从 main_agent_config 加载，前端不传

  // 重置代码块过滤状态机
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

/**
 * 提交长任务到工作流引擎
 * 工作流模式下，主 Agent 通过 WorkflowEngine 分解任务、调度内部模块
 */
const submitWorkflowTask = async (
  content: string,
  resolved: { model?: string; provider?: string } | null,
) => {
  // 重置工具调用活动追踪
  toolActivities.value = []
  subagentActivities.value = []

  isNearBottom.value = true
  inCodeBlock = false

  // === DEBUG START ===
  console.group('[WorkflowDebug] submitWorkflowTask 调用')
  console.log('[WorkflowDebug] 输入内容:', content)
  console.log('[WorkflowDebug] resolved model/provider:', resolved)
  console.log('[WorkflowDebug] MAIN_AGENT_ID:', MAIN_AGENT_ID)
  console.log('[WorkflowDebug] agentStore.activeAgent:', agentStore.activeAgent)
  console.log('[WorkflowDebug] chatStore.activeAgentId:', chatStore.activeAgentId)
  console.log('[WorkflowDebug] chatStore.currentConvId:', chatStore.currentConvId)
  console.log('[WorkflowDebug] chatStore.conversations count:', chatStore.conversations.length)
  console.log('[WorkflowDebug] chatStore.conversations:', chatStore.conversations)
  // === DEBUG END ===

  let convId = chatStore.currentConvId
  if (!convId) {
    console.warn('[WorkflowDebug] currentConvId 为空，尝试自动创建对话...')
    try {
      const conv = await chatStore.createConversation(
        content.slice(0, 30) || '新对话',
        MAIN_AGENT_ID,
        resolved?.model,
        resolved?.provider,
      )
      convId = conv?.id || null
      console.log('[WorkflowDebug] 自动创建对话结果:', conv)
      console.log('[WorkflowDebug] 创建后 currentConvId:', chatStore.currentConvId)
    } catch (e: unknown) {
      console.error('[WorkflowDebug] 自动创建对话失败:', e)
      const errMsg = e instanceof Error ? e.message : String(e)
      toast.error(`创建对话失败：${errMsg}`)
      return
    }
  }

  if (!convId) {
    console.error('[WorkflowDebug] convId 仍为空，无法继续')
    toast.error('请先选择或创建对话')
    return
  }
  console.log('[WorkflowDebug] 使用 convId:', convId)
  console.groupEnd()

  // 1. 添加用户消息到 chatStore
  const userMsgId = `user-${Date.now()}`
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

  // 2. 添加空的 assistant 消息（占位，工作流完成后填充）
  const assistantMsgId = `assistant-${Date.now()}`
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
      onReasoning: (reasoningContent, phase) => {
        console.info(`[Workbench] 收到思考过程 (${phase}): ${reasoningContent.slice(0, 80)}${reasoningContent.length > 80 ? '...' : ''}`)
        const msgs = chatStore.convMessages[convId] || []
        const updatedMsgs = msgs.map(m =>
          m.id === assistantMsgId
            ? { ...m, reasoningContent: (m.reasoningContent || '') + reasoningContent }
            : m
        )
        chatStore.convMessages = {
          ...chatStore.convMessages,
          [convId]: updatedMsgs,
        }
      },
      onFinalResult: (result) => {
        // 工作流完成后，更新 assistant 消息内容
        const msgs = chatStore.convMessages[convId] || []
        const updatedMsgs = msgs.map(m =>
          m.id === assistantMsgId
            ? { ...m, content: result || '工作流执行完成', done: true }
            : m
        )
        chatStore.convMessages = {
          ...chatStore.convMessages,
          [convId]: updatedMsgs,
        }

        // TTS 播报（失败不阻断消息显示）
        if (result) {
          try {
            feedChunk({
              id: `workflow_${Date.now()}`,
              content: result,
              reasoning_content: '',
              model: resolved?.model || '',
              provider: resolved?.provider || '',
              done: true,
            })
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
    // 错误时也要更新 assistant 消息
    const msgs = chatStore.convMessages[convId] || []
    const updatedMsgs = msgs.map(m =>
      m.id === assistantMsgId
        ? { ...m, content: `工作流执行失败：${errMsg}`, done: true }
        : m
    )
    chatStore.convMessages = {
      ...chatStore.convMessages,
      [convId]: updatedMsgs,
    }
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

const scrollToBottom = (force = false) => {
  if (!messagesContainer.value) return
  if (!force && !isNearBottom.value) return
  messagesContainer.value.scrollTo({
    top: messagesContainer.value.scrollHeight,
    behavior: force ? 'auto' : 'smooth',
  })
}

const handleMessagesScroll = () => {
  if (!messagesContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
  const distanceFromBottom = scrollHeight - scrollTop - clientHeight
  isNearBottom.value = distanceFromBottom < SCROLL_BOTTOM_THRESHOLD
  showScrollToBottomBtn.value = !isNearBottom.value && messages.value.length > 0
}

const setupResizeObserver = () => {
  if (!messagesContainer.value) return
  const inner = messagesContainer.value.querySelector('.messages-container') as HTMLElement
  if (!inner) return
  resizeObserver = new ResizeObserver(() => {
    if (isNearBottom.value) {
      scrollToBottom(true)
    }
  })
  resizeObserver.observe(inner)
}

const resetTextareaHeight = () => {
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
  }
}

const autoResize = () => {
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
    textareaRef.value.style.height = `${Math.min(textareaRef.value.scrollHeight, 120)}px`
  }
}

const renderMarkdown = (text: string): string => {
  if (!text) return ''
  // 拦截器：剥离 <exp:xxx> 表情标签，防止标签显示在前端
  const cleaned = stripEmotionTags(text)
  const raw = marked.parse(cleaned) as string
  return DOMPurify.sanitize(raw)
}

const renderReasoningMarkdown = (text: string): string => {
  if (!text) return ''
  // 拦截器：剥离 <exp:xxx> 表情标签，防止标签显示在前端
  const cleaned = stripEmotionTags(text)
  const raw = marked.parse(cleaned) as string
  return DOMPurify.sanitize(raw)
}

const toggleReasoning = (msgId: string) => {
  showReasoning.value = {
    ...showReasoning.value,
    [msgId]: !showReasoning.value[msgId],
  }
}

const copyMessage = async (msgId: string, content: string) => {
  try {
    await navigator.clipboard.writeText(content)
    copiedId.value = msgId
    setTimeout(() => {
      copiedId.value = null
    }, 2000)
  } catch {}
}

const isLastAssistantMessage = (msgId: string) => {
  const msgs = messages.value
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant' && !msgs[i].done) return false
  }
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant') {
      return msgs[i].id === msgId
    }
  }
  return false
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
        feedChunk({
          ...chunk,
          content: filteredContent,
        })
      }
    },
  })
  await nextTick()
  scrollToBottom(true)
}

watch(() => messages.value, async (msgs) => {
  for (const msg of msgs) {
    if (msg.role !== 'assistant') continue
    if (msg.content && msg.content.length > 0 && showReasoning.value[msg.id] === undefined) {
      showReasoning.value = { ...showReasoning.value, [msg.id]: false }
    }
  }
}, { deep: true, immediate: true })

watch(messages, () => {
  if (isStreaming.value && isNearBottom.value) {
    nextTick(() => scrollToBottom())
  }
}, { deep: true })

watch(isLoadingCurrentConv, (loading) => {
  if (loading) {
    isNearBottom.value = true
  } else {
    nextTick(() => scrollToBottom(true))
  }
})

// Live2D 模型切换
const switchModel = async (model: typeof LUOMINEST_BUILTIN_MODELS[0]) => {
  currentModelInfo.value = model
  if (isDesktopMode.value) {
    // 桌宠模式：通过 IPC 切换桌宠窗口的模型，不加载本地实例
    await window.api.desktopPet.loadModel(model)
  } else {
    await loadModel(model.url, model.scale)
  }
}

onMounted(async () => {
  // 设置虚拟主 Agent Profile，使 chat store 的 computed 基于 MAIN_AGENT_ID 工作
  agentStore.setActiveAgent(MAIN_AGENT_PROFILE)

  await chatStore.checkBackend()
  if (chatStore.isBackendReady) {
    // 并发加载：主 Agent 配置 / 模型 / 对话历史 / 记忆 / 状态面板
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
  // 检查桌宠窗口运行状态（可能从上次会话残留或由 AvatarView 开启）
  await avatarControl.checkDesktopPetStatus()
  // 仅在内联模式下加载本地 Live2D 模型；桌宠模式下由桌宠窗口负责渲染
  if (!isDesktopMode.value) {
    const defaultModel = LUOMINEST_BUILTIN_MODELS[0]
    await loadModel(defaultModel.url, defaultModel.scale)
  }
  document.addEventListener('click', handleClickOutsideModel)
  nextTick(() => setupResizeObserver())
})

// 监听桌宠模式切换：与 AvatarView 的开关操作联动，自动销毁/重建本地 Live2D 实例
watch(isDesktopMode, async (desktopMode) => {
  if (desktopMode) {
    // 进入桌宠模式：销毁本地 Live2D 实例，避免双窗口同时渲染
    teardownLive2D()
  } else {
    // 退出桌宠模式：重新加载本地模型
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
  resizeObserver?.disconnect()
  document.removeEventListener('click', handleClickOutsideModel)
  stopTts()
  teardownLive2D()
})
</script>

<template>
  <div class="workbench-layout">
    <!-- 左侧：聊天历史记录 -->
    <Transition name="history-slide">
      <div v-if="!isHistoryCollapsed" class="workbench-history">
        <div class="history-header">
          <div class="history-title">
            <Bot :size="16" />
            <span>陪伴对话</span>
          </div>
          <button class="history-collapse-btn" title="收起历史记录" @click="isHistoryCollapsed = true">
            <PanelLeftClose :size="15" />
          </button>
        </div>

        <div class="history-search">
          <Search :size="14" class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索对话..." class="search-input" />
        </div>

        <button class="new-conv-btn" @click="handleNewConversation">
          <Plus :size="15" />
          <span>新建对话</span>
        </button>

        <div class="history-list">
          <template v-if="isSearchMode">
            <div v-if="isSearching" class="history-empty">
              <Loader2 :size="20" class="spin-animation" />
              <span>搜索中...</span>
            </div>
            <template v-else>
              <div
                v-for="result in searchResults"
                :key="result.id"
                :class="['history-item', { active: chatStore.currentConvId === result.id }]"
                @click="selectConversation(result.id, searchQuery.trim())"
              >
                <MessageSquare :size="14" class="history-item-icon" />
                <div class="history-item-content">
                  <span class="history-item-title">{{ result.title }}</span>
                  <span class="history-item-snippet" v-html="highlightSnippet(result.snippet)"></span>
                </div>
              </div>
              <div v-if="searchResults.length === 0" class="history-empty">
                <MessageSquare :size="24" />
                <span>未找到匹配的会话</span>
              </div>
            </template>
          </template>

          <template v-else>
            <template v-for="group in timeGroups" :key="group.label">
              <div class="time-group">
                <div class="time-group-label">
                  <Clock :size="12" />
                  <span>{{ group.label }}</span>
                </div>
                <div
                  v-for="conv in group.items"
                  :key="conv.id"
                  :class="['history-item', { active: chatStore.currentConvId === conv.id }]"
                  @click="selectConversation(conv.id)"
                >
                  <MessageSquare :size="14" class="history-item-icon" />
                  <div class="history-item-content">
                    <template v-if="renamingConvId === conv.id">
                      <input
                        v-model="renamingTitle"
                        class="workbench-rename-input"
                        maxlength="200"
                        @keydown.enter="confirmRename"
                        @keydown.escape="cancelRename"
                        @blur="confirmRename"
                        @click.stop
                      />
                    </template>
                    <template v-else>
                      <span class="history-item-title">{{ conv.title }}</span>
                      <span class="history-item-time">{{ formatTime(conv.updated_at) }}</span>
                    </template>
                  </div>
                  <template v-if="renamingConvId !== conv.id">
                    <button class="history-item-rename" title="重命名" @click.stop="startRename(conv.id, conv.title)">
                      <Pencil :size="13" />
                    </button>
                    <button class="history-item-delete" title="删除对话" @click.stop="handleDeleteConversation(conv.id)">
                      <Trash2 :size="13" />
                    </button>
                  </template>
                </div>
              </div>
            </template>

            <div v-if="timeGroups.length === 0" class="history-empty">
              <MessageSquare :size="24" />
              <span>暂无历史记录</span>
            </div>
          </template>
        </div>
      </div>
    </Transition>

    <!-- 收起状态：展开按钮 -->
    <button v-if="isHistoryCollapsed" class="history-expand-toggle" title="展开历史记录" @click="isHistoryCollapsed = false">
      <PanelLeftOpen :size="15" />
    </button>

    <!-- 中间：对话面板 -->
    <div class="workbench-chat">
      <div v-if="!isBackendReady" class="backend-warning">
        <div class="warning-content">
          <AlertTriangle :size="20" />
          <div class="warning-text">
            <p class="warning-title">后端服务未连接</p>
            <p class="warning-desc">请确保 LuomiNest 后端服务已启动</p>
          </div>
          <button class="retry-btn" @click="chatStore.checkBackend()">
            <RotateCcw :size="14" />
            重试
          </button>
        </div>
      </div>

      <div class="chat-area">
        <!-- 主智能体标识栏 -->
        <div class="main-agent-bar">
          <div class="main-agent-badge">
            <Brain :size="14" />
            <span>主智能体</span>
          </div>
          <span class="main-agent-model">{{ currentModel }}</span>
        </div>
        <div ref="messagesContainer" class="messages-scroll" @scroll="handleMessagesScroll">
          <div class="messages-container">
            <TransitionGroup name="msg-appear" tag="div">
              <div
                v-for="msg in messages"
                :key="msg.id"
                :class="['message-row', msg.role]"
              >
                <div v-if="msg.role === 'assistant'" class="message-avatar">
                  <div class="avatar-assistant">
                    <Bot :size="16" />
                  </div>
                </div>
                <div class="message-body">
                  <div v-if="msg.role === 'assistant'" class="message-sender">
                    主智能体
                  </div>
                  <div
                    v-if="msg.role === 'assistant' && (msg.reasoningContent !== undefined || (!msg.done && msg.id === messages[messages.length - 1].id && !msg.content))"
                    class="reasoning-section"
                  >
                    <div class="reasoning-header" @click="toggleReasoning(msg.id)">
                      <Loader2 v-if="!msg.done && !msg.content && !msg.reasoningContent" :size="12" class="spin-animation" />
                      <Wand2 v-else :size="12" />
                      <span>
                        <template v-if="!msg.done && !msg.content && !msg.reasoningContent">等待模型中...</template>
                        <template v-else-if="!msg.done && !msg.content && msg.reasoningContent">思考中...</template>
                        <template v-else-if="msg.reasoningContent && msg.reasoningContent.length > 0">{{ showReasoning[msg.id] ? '思考过程' : '思考过程（已折叠）' }}</template>
                        <template v-else>思考完成</template>
                      </span>
                      <ChevronDown :size="12" class="reasoning-chevron" :class="{ rotated: !showReasoning[msg.id] }" />
                    </div>
                    <div
                      v-show="showReasoning[msg.id] !== false"
                      class="reasoning-content reasoning-markdown"
                    >
                      <div v-html="renderReasoningMarkdown(msg.reasoningContent || '')"></div>
                    </div>
                  </div>

                  <div
                    v-if="msg.role === 'assistant' && msg.id === messages[messages.length - 1].id && toolActivities.length > 0"
                    class="tool-activities-section"
                  >
                    <div class="tool-activities-header">
                      <Wrench :size="12" />
                      <span>工具调用 ({{ toolActivities.length }})</span>
                    </div>
                    <div class="tool-activities-list">
                      <div
                        v-for="activity in toolActivities"
                        :key="activity.id"
                        class="tool-activity-item"
                      >
                        <div class="tool-activity-header" @click="toggleToolOutput(activity.id)">
                          <div class="tool-activity-icon">
                            <Loader2 v-if="activity.status === 'running' || activity.status === 'pending'" :size="13" class="spin-animation" />
                            <CheckCircle2 v-else-if="activity.status === 'completed'" :size="13" />
                            <XCircle v-else-if="activity.status === 'failed'" :size="13" />
                          </div>
                          <Terminal :size="12" />
                          <span class="tool-activity-name">{{ activity.name }}</span>
                          <span class="tool-activity-iteration" v-if="activity.iteration > 0">轮次 {{ activity.iteration + 1 }}</span>
                          <ChevronDown
                            v-if="activity.output"
                            :size="12"
                            class="tool-activity-chevron"
                            :class="{ rotated: !expandedToolOutputs[activity.id] }"
                          />
                        </div>
                        <div v-if="activity.arguments && activity.arguments !== '{}'" class="tool-activity-args">
                          <pre>{{ formatToolArgs(activity.arguments) }}</pre>
                        </div>
                        <div
                          v-if="activity.output && expandedToolOutputs[activity.id]"
                          class="tool-activity-output"
                        >
                          <pre>{{ activity.output }}</pre>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- 子 Agent 群组执行卡片（参考 deer-flow SubtaskCard） -->
                  <div
                    v-if="msg.role === 'assistant' && msg.id === messages[messages.length - 1].id && subagentActivities.length > 0"
                    class="subagent-activities-section"
                  >
                    <div class="subagent-activities-header">
                      <Cpu :size="12" />
                      <span>子 Agent 群组 ({{ subagentActivities.length }})</span>
                      <span v-if="activeSubagentCount > 0" class="subagent-active-badge">{{ activeSubagentCount }} 执行中</span>
                    </div>
                    <div class="subagent-activities-list">
                      <div
                        v-for="agent in subagentActivities"
                        :key="agent.id"
                        :class="['subagent-card', { running: agent.status === 'running' }]"
                      >
                        <div class="subagent-card-header" @click="toggleSubagent(agent.id)">
                          <div class="subagent-status-icon">
                            <Loader2 v-if="agent.status === 'running'" :size="13" class="spin-animation" />
                            <CheckCircle2 v-else-if="agent.status === 'completed'" :size="13" />
                            <XCircle v-else-if="agent.status === 'failed'" :size="13" />
                          </div>
                          <div class="subagent-card-info">
                            <div class="subagent-card-title">
                              <span class="subagent-task">{{ agent.task }}</span>
                              <span class="subagent-depth">深度 {{ agent.depth }}</span>
                            </div>
                            <div class="subagent-card-meta">
                              <template v-if="agent.status === 'running' && agent.progress">
                                <span class="subagent-progress">{{ agent.progress }}</span>
                              </template>
                              <template v-else-if="agent.status === 'completed'">
                                <span class="subagent-status-text completed">已完成</span>
                              </template>
                              <template v-else-if="agent.status === 'failed'">
                                <span class="subagent-status-text failed">执行失败</span>
                              </template>
                              <span v-if="agent.toolCalls.length > 0" class="subagent-tools-count">
                                {{ agent.toolCalls.length }} 次工具调用
                              </span>
                            </div>
                          </div>
                          <ChevronDown
                            :size="14"
                            class="subagent-chevron"
                            :class="{ rotated: !expandedSubagents[agent.id] }"
                          />
                        </div>

                        <Transition name="subagent-slide">
                          <div v-show="expandedSubagents[agent.id]" class="subagent-card-body">
                            <!-- 工具调用历史 -->
                            <div v-if="agent.toolCalls.length > 0" class="subagent-tools-section">
                              <div class="subagent-tools-header" @click="toggleSubagentTools(agent.id)">
                                <Terminal :size="11" />
                                <span>工具调用历史</span>
                                <ChevronDown
                                  :size="11"
                                  class="subagent-tools-chevron"
                                  :class="{ rotated: !expandedSubagentTools[agent.id] }"
                                />
                              </div>
                              <div v-show="expandedSubagentTools[agent.id]" class="subagent-tools-list">
                                <div
                                  v-for="(tc, idx) in agent.toolCalls"
                                  :key="idx"
                                  class="subagent-tool-item"
                                >
                                  <div class="subagent-tool-header">
                                    <div class="subagent-tool-icon">
                                      <Loader2 v-if="tc.status === 'running'" :size="11" class="spin-animation" />
                                      <CheckCircle2 v-else :size="11" />
                                    </div>
                                    <span class="subagent-tool-name">{{ tc.name }}</span>
                                  </div>
                                  <div v-if="tc.args && tc.args !== '{}'" class="subagent-tool-args">
                                    <pre>{{ formatToolArgs(tc.args) }}</pre>
                                  </div>
                                  <div v-if="tc.output" class="subagent-tool-output">
                                    <pre>{{ tc.output }}</pre>
                                  </div>
                                </div>
                              </div>
                            </div>

                            <!-- 最终结果 -->
                            <div v-if="agent.result" class="subagent-result">
                              <div class="subagent-result-label">
                                <CheckCircle2 :size="11" />
                                <span>执行结果</span>
                              </div>
                              <div class="subagent-result-content markdown-body">
                                <div v-html="renderMarkdown(agent.result)"></div>
                              </div>
                            </div>

                            <!-- 错误信息 -->
                            <div v-if="agent.error" class="subagent-error">
                              <div class="subagent-error-label">
                                <XCircle :size="11" />
                                <span>错误信息</span>
                              </div>
                              <div class="subagent-error-content">{{ agent.error }}</div>
                            </div>
                          </div>
                        </Transition>
                      </div>
                    </div>
                  </div>

                  <!-- 计划确认卡片（借鉴 deer-flow ClarificationMiddleware） -->
                  <div
                    v-if="msg.role === 'assistant' && msg.id === messages[messages.length - 1].id && workflowStore.pendingPlan"
                    class="plan-confirmation-section"
                  >
                    <div class="plan-confirmation-header">
                      <ClipboardList :size="14" />
                      <span>执行计划待确认</span>
                      <span class="plan-task-count">{{ workflowStore.pendingPlan.tasks.length }} 个子任务</span>
                    </div>
                    <div class="plan-confirmation-body">
                      <div v-if="workflowStore.pendingPlan.plan" class="plan-summary">
                        {{ workflowStore.pendingPlan.plan }}
                      </div>
                      <div class="plan-tasks-list">
                        <div
                          v-for="(task, idx) in workflowStore.pendingPlan.tasks"
                          :key="task.task_id || idx"
                          class="plan-task-item"
                        >
                          <div class="plan-task-index">{{ idx + 1 }}</div>
                          <div class="plan-task-info">
                            <div class="plan-task-title">{{ task.title }}</div>
                            <div v-if="task.description" class="plan-task-desc">{{ task.description }}</div>
                            <div class="plan-task-meta">
                              <span v-if="task.tool_name" class="plan-task-tool">
                                <Wrench :size="10" />
                                {{ task.tool_name }}
                              </span>
                              <span v-if="task.priority && task.priority !== 'normal'" class="plan-task-priority" :class="task.priority">
                                {{ task.priority }}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                      <div class="plan-feedback-area">
                        <textarea
                          v-model="workflowStore.confirmationFeedback"
                          class="plan-feedback-input"
                          placeholder="反馈（可选）：如需调整计划，请在此说明..."
                          rows="2"
                        ></textarea>
                      </div>
                      <div class="plan-confirmation-actions">
                        <button class="plan-btn plan-btn-reject" @click="workflowStore.rejectPlan">
                          <X :size="14" />
                          <span>拒绝执行</span>
                        </button>
                        <button class="plan-btn plan-btn-confirm" @click="workflowStore.confirmPlan">
                          <Check :size="14" />
                          <span>确认执行</span>
                        </button>
                      </div>
                    </div>
                  </div>

                  <div v-if="msg.role === 'assistant' && msg.content && msg.content !== '[已中断]'" class="message-content markdown-body">
                    <div v-html="renderMarkdown(msg.content)"></div>
                    <span v-if="msg.interrupted" class="interrupted-inline">
                      <AlertTriangle :size="12" /> 已中断
                    </span>
                  </div>
                  <div v-else-if="(msg.interrupted || msg.content === '[已中断]') && msg.role === 'assistant'" class="interrupted-only">
                    <AlertTriangle :size="12" /> 已中断
                  </div>
                  <div v-if="msg.role === 'assistant' && !msg.done && msg.content" class="streaming-indicator">
                    <span class="streaming-dot"></span>
                  </div>

                  <div v-if="msg.role === 'assistant' && msg.done" class="assistant-msg-actions">
                    <button class="u-btn" title="复制" @click="copyMessage(msg.id, msg.content)">
                      <Check v-if="copiedId === msg.id" :size="14" />
                      <Copy v-else :size="14" />
                    </button>
                    <button
                      v-if="isLastAssistantMessage(msg.id)"
                      class="u-btn"
                      title="重新生成"
                      @click="handleRegenerate(msg.id)"
                    >
                      <RotateCcw :size="14" />
                    </button>
                  </div>

                  <div v-if="msg.role === 'user'" class="user-msg-layout">
                    <div class="user-msg-btns">
                      <button class="u-btn u-btn-hover" title="复制" @click="copyMessage(msg.id, msg.content)">
                        <Check v-if="copiedId === msg.id" :size="14" />
                        <Copy v-else :size="14" />
                      </button>
                    </div>
                    <div class="message-content user-message">
                      {{ msg.content }}
                    </div>
                  </div>
                </div>
              </div>
            </TransitionGroup>

            <div v-if="messages.length === 0 && !isLoadingCurrentConv" class="empty-state">
              <div class="empty-icon">
                <Sparkles :size="48" />
              </div>
              <p class="empty-title">与陪伴 AI 开始对话</p>
              <p class="empty-desc">右侧的 Live2D 将作为主 Agent 陪伴你</p>
              <div class="empty-quick-actions">
                <button class="quick-action" @click="inputText = '你好，请介绍一下你自己'">打个招呼</button>
                <button class="quick-action" @click="inputText = '帮我写一段 Python 代码'">写段代码</button>
                <button class="quick-action" @click="inputText = '解释一下什么是大语言模型'">了解 LLM</button>
              </div>
            </div>
          </div>
        </div>

        <Transition name="conv-loading-fade">
          <div v-if="isLoadingCurrentConv" class="conv-loading-overlay">
            <div class="conv-loading-content">
              <Loader2 :size="20" class="spin-animation" />
              <span>加载对话中...</span>
            </div>
          </div>
        </Transition>

        <Transition name="scroll-btn-fade">
          <button v-if="showScrollToBottomBtn" class="scroll-to-bottom-btn" @click="scrollToBottom(true)">
            <ChevronDown :size="18" />
          </button>
        </Transition>
      </div>

      <div class="input-area">
        <div class="input-wrapper">
          <textarea
            ref="textareaRef"
            v-model="inputText"
            placeholder="与陪伴 AI 对话..."
            rows="1"
            class="chat-input"
            :disabled="!isBackendReady"
            @keydown.enter.exact.prevent="sendMessage"
            @input="autoResize"
          ></textarea>
          <div class="input-toolbar">
            <div class="toolbar-left">
              <div class="model-dropdown-container">
                <button class="tool-btn" title="选择模型" @click.stop="showModelDropdown = !showModelDropdown">
                  <span v-if="currentProviderLogo.svgIcon" class="provider-icon-mini provider-svg-mini" v-html="currentProviderLogo.svgIcon"></span>
                  <span v-else class="provider-icon-mini" :style="{ background: currentProviderLogo.color }">
                    {{ currentProviderLogo.initials }}
                  </span>
                  <span class="model-btn-text">{{ currentModel }}</span>
                  <ChevronDown :size="14" />
                </button>
                <Transition name="dropdown-fade">
                  <div v-if="showModelDropdown" class="model-dropdown">
                    <div class="dropdown-header">选择模型</div>
                    <div class="dropdown-list">
                      <button
                        v-for="opt in availableModelOptions"
                        :key="`${opt.providerId}-${opt.modelId}`"
                        :class="['dropdown-item', { active: currentProvider === opt.providerId && currentModel === opt.modelId }]"
                        @click="selectModel(opt.providerId, opt.modelId)"
                      >
                        <span v-if="opt.providerLogo.svgIcon" class="provider-icon-mini provider-svg-mini" v-html="opt.providerLogo.svgIcon"></span>
                        <span v-else class="provider-icon-mini" :style="{ background: opt.providerLogo.color }">
                          {{ opt.providerLogo.initials }}
                        </span>
                        <div class="dropdown-item-info">
                          <span class="dropdown-item-model">{{ opt.modelName }}</span>
                          <span class="dropdown-item-provider">{{ opt.providerName }}</span>
                        </div>
                      </button>
                      <div v-if="availableModelOptions.length === 0" class="dropdown-empty">
                        暂无可用模型，请先到设置多选模型
                      </div>
                    </div>
                  </div>
                </Transition>
              </div>
              <button
                :class="['tool-btn', 'workflow-toggle', { active: workflowMode }]"
                :title="workflowMode ? '工作流模式已开启：长任务将自动分解并调度内部模块' : '开启工作流模式：长任务自动分解执行'"
                @click="toggleWorkflowMode"
              >
                <Wand2 :size="15" />
                <span class="workflow-toggle-text">{{ workflowMode ? '工作流' : '普通' }}</span>
              </button>
              <div v-if="workflowMode" class="workflow-mode-selector">
                <button
                  v-for="opt in WORKFLOW_MODE_OPTIONS"
                  :key="opt.value"
                  :class="['mode-chip', { active: workflowModeLevel === opt.value }]"
                  :title="opt.title"
                  @click="workflowModeLevel = opt.value"
                >
                  {{ opt.label }}
                </button>
              </div>
            </div>
            <div class="toolbar-right">
              <button
                v-if="isStreaming"
                class="send-btn stop"
                title="停止生成"
                @click="cancelStreaming"
              >
                <Square :size="16" />
              </button>
              <button
                v-else
                :class="['send-btn', { disabled: !canSend }]"
                title="发送"
                @click="sendMessage"
              >
                <Send :size="17" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧：Live2D 陪伴区 -->
    <div class="workbench-avatar">
      <div class="avatar-header">
        <div class="avatar-title">
          <!-- <Sparkles :size="15" /> -->
          <span>陪伴形象</span>
        </div>
        <div class="avatar-model-selector">
          <button
            v-for="model in LUOMINEST_BUILTIN_MODELS"
            :key="model.id"
            :class="['model-chip', { active: currentModelInfo.id === model.id }]"
            :title="model.name"
            @click="switchModel(model)"
          >
            {{ model.name }}
          </button>
        </div>
      </div>

      <div class="avatar-stage" :class="{ 'desktop-mode-active': isDesktopMode }">
        <template v-if="!isDesktopMode">
          <canvas ref="canvasRef" class="live2d-canvas"></canvas>
          <Transition name="fade">
            <div v-if="isModelLoading && !isModelReady" class="avatar-loading">
              <Loader2 :size="28" class="spin-animation" />
              <span>加载模型中...</span>
            </div>
          </Transition>
          <Transition name="fade">
            <div v-if="loadError" class="avatar-error">
              <AlertTriangle :size="24" />
              <span>{{ loadError }}</span>
            </div>
          </Transition>
          <div v-if="isModelReady" class="avatar-status">
            <span class="status-dot" :class="{ speaking: isSpeaking }"></span>
            <span>{{ isSpeaking ? '正在说话' : (isSynthesizing ? '合成语音中' : (currentModelInfo.name + ' 已就绪')) }}</span>
          </div>
          <Transition name="subtitle-fade">
            <div
              v-if="subtitleVisible && subtitleText"
              class="avatar-subtitle"
              @click="dismissSubtitle"
            >
              {{ subtitleText }}
            </div>
          </Transition>
        </template>

        <div v-else class="desktop-mode-hint">
          <div class="hint-icon">
            <Monitor :size="40" />
          </div>
          <div class="hint-content">
            <h3>桌宠模式已开启</h3>
            <p>模型已切换到桌面宠物窗口，请直接在桌面上与角色互动。</p>
            <p class="hint-sub">工作台的对话、表情和动作会同步到桌宠。前往"皮套工坊"可切换回内联模式。</p>
          </div>
        </div>
      </div>

      <div class="avatar-footer">
        <div class="avatar-controls">
          <button
            :class="['ctrl-btn', { active: ttsEnabled }]"
            :title="ttsEnabled ? '关闭语音播报' : '开启语音播报'"
            @click="ttsEnabled = !ttsEnabled"
          >
            <Volume2 v-if="ttsEnabled" :size="15" />
            <VolumeX v-else :size="15" />
          </button>
          <button
            :class="['ctrl-btn', { active: subtitleEnabled }]"
            :title="subtitleEnabled ? '关闭字幕' : '开启字幕'"
            @click="subtitleEnabled = !subtitleEnabled"
          >
            <Subtitles :size="15" />
          </button>
          <button
            v-if="isSpeaking || isSynthesizing"
            class="ctrl-btn stop-btn"
            title="停止播放"
            @click="stopTts"
          >
            <StopCircle :size="15" />
          </button>
        </div>
        <p class="avatar-tip">主 Agent 工作台 · 支持工具调用与子 Agent 协作</p>
      </div>

      <!-- 主 Agent 状态面板（可折叠：记忆 / MCP / 消息平台） -->
      <div class="agent-panels">
        <!-- 记忆快览 -->
        <div class="agent-panel">
          <div class="agent-panel-header" @click="toggleSidePanel('memory')">
            <Brain :size="14" />
            <span class="agent-panel-title">记忆</span>
            <span class="agent-panel-badge">{{ memoryStore.facts.length }}</span>
            <ChevronRight :size="14" class="agent-panel-chevron" :class="{ expanded: !sidePanelCollapsed.memory }" />
          </div>
          <Transition name="panel-slide">
            <div v-show="!sidePanelCollapsed.memory" class="agent-panel-body">
              <div class="memory-profile">
                <span class="memory-label">用户画像</span>
                <span class="memory-value">{{ memoryStore.profile.name || '未设置' }}</span>
              </div>
              <div class="memory-summary">{{ memorySummaryPreview }}</div>
            </div>
          </Transition>
        </div>

        <!-- MCP 工具状态 -->
        <div class="agent-panel">
          <div class="agent-panel-header" @click="toggleSidePanel('mcp')">
            <Server :size="14" />
            <span class="agent-panel-title">MCP 工具</span>
            <span class="agent-panel-badge">{{ connectedMcpCount }}/{{ mcpStatus.servers.length }}</span>
            <ChevronRight :size="14" class="agent-panel-chevron" :class="{ expanded: !sidePanelCollapsed.mcp }" />
          </div>
          <Transition name="panel-slide">
            <div v-show="!sidePanelCollapsed.mcp" class="agent-panel-body">
              <div v-if="mcpStatus.servers.length === 0" class="panel-empty">未配置 MCP 服务器</div>
              <template v-else>
                <div
                  v-for="server in mcpStatus.servers"
                  :key="server.name"
                  class="mcp-server-item"
                >
                  <span class="mcp-server-dot" :class="server.status"></span>
                  <span class="mcp-server-name">{{ server.name }}</span>
                  <span class="mcp-server-tools">{{ server.tool_count }} 工具</span>
                </div>
                <div class="mcp-total">共 {{ mcpStatus.totalTools }} 个工具可用</div>
              </template>
            </div>
          </Transition>
        </div>

        <!-- 消息平台状态 -->
        <div class="agent-panel">
          <div class="agent-panel-header" @click="toggleSidePanel('platform')">
            <Radio :size="14" />
            <span class="agent-panel-title">消息平台</span>
            <span class="agent-panel-badge">{{ activePlatformCount }}/{{ platformStore.instances.length }}</span>
            <ChevronRight :size="14" class="agent-panel-chevron" :class="{ expanded: !sidePanelCollapsed.platform }" />
          </div>
          <Transition name="panel-slide">
            <div v-show="!sidePanelCollapsed.platform" class="agent-panel-body">
              <div v-if="platformStore.instances.length === 0" class="panel-empty">未配置消息平台</div>
              <template v-else>
                <div
                  v-for="inst in platformStore.instances"
                  :key="inst.id"
                  class="platform-item"
                >
                  <span class="platform-dot" :class="{ active: inst.status === 'running' }"></span>
                  <span class="platform-name">{{ inst.name }}</span>
                  <span class="platform-type">{{ inst.displayName }}</span>
                </div>
              </template>
            </div>
          </Transition>
        </div>

        <!-- 子 Agent 能力提示 -->
        <div class="agent-panel">
          <div class="agent-panel-header" @click="toggleSidePanel('subagent')">
            <Cpu :size="14" />
            <span class="agent-panel-title">子 Agent</span>
            <span class="agent-panel-badge">{{ subagentActivities.length }}</span>
            <ChevronRight :size="14" class="agent-panel-chevron" :class="{ expanded: !sidePanelCollapsed.subagent }" />
          </div>
          <Transition name="panel-slide">
            <div v-show="!sidePanelCollapsed.subagent" class="agent-panel-body">
              <div v-if="subagentActivities.length === 0" class="panel-empty">主 Agent 按需创建子 Agent</div>
              <template v-else>
                <div
                  v-for="agent in subagentActivities"
                  :key="agent.id"
                  class="subagent-side-item"
                >
                  <span class="subagent-side-dot" :class="agent.status"></span>
                  <span class="subagent-side-task">{{ agent.task }}</span>
                  <span class="subagent-side-depth">d{{ agent.depth }}</span>
                </div>
                <div class="mcp-total">共 {{ subagentActivities.length }} 个子 Agent</div>
              </template>
            </div>
          </Transition>
        </div>
      </div>
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

/* 左侧历史记录 */
.workbench-history {
  width: 260px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-light);
  flex-shrink: 0;
  overflow: hidden;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px;
  flex-shrink: 0;
}

.history-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.history-collapse-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-muted);
  transition: background 0.15s ease-in-out, color 0.15s ease-in-out;
}

.history-collapse-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.history-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin: 0 14px 8px;
  height: 36px;
  background: var(--surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  transition: all var(--transition-fast);
  box-sizing: border-box;
}

.history-search:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  width: 100%;
  height: 100%;
  background: transparent;
  border: none;
  outline: none;
  font-size: 13px;
  color: var(--text-primary);
}

.search-input::placeholder {
  color: var(--text-muted);
}

.new-conv-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  margin: 0 14px 8px;
  border: none;
  background: var(--lumi-primary);
  color: var(--text-inverse);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: background 0.15s ease-in-out;
}

.new-conv-btn:hover {
  background: var(--lumi-primary-hover);
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
}

.time-group {
  margin-bottom: 8px;
}

.time-group-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  cursor: pointer;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  transition: background 0.15s ease-in-out, color 0.15s ease-in-out;
  position: relative;
}

.history-item:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.history-item.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.history-item-icon {
  flex-shrink: 0;
  color: inherit;
}

.history-item-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.history-item-title {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-item-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.history-item-snippet {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}

.history-item-snippet :deep(mark) {
  background: var(--lumi-primary-glow);
  color: var(--lumi-primary);
  padding: 0 2px;
  border-radius: 2px;
}

.workbench-rename-input {
  width: 100%;
  height: 24px;
  background: var(--surface);
  border: 1px solid var(--lumi-primary);
  border-radius: var(--radius-sm);
  padding: 0 6px;
  font-size: 13px;
  color: var(--text-primary);
  outline: none;
  box-sizing: border-box;
}

.history-item-rename,
.history-item-delete {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s ease-in-out, background 0.15s ease-in-out, color 0.15s ease-in-out;
  flex-shrink: 0;
}

.history-item:hover .history-item-rename,
.history-item:hover .history-item-delete {
  opacity: 1;
}

.history-item-rename:hover {
  background: var(--surface-active);
  color: var(--text-primary);
}

.history-item-delete:hover {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 16px;
  color: var(--text-muted);
  font-size: 12px;
}

.history-expand-toggle {
  width: 28px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  color: var(--text-muted);
  cursor: pointer;
  background: var(--surface);
  border: none;
  border-right: 1px solid var(--border-light);
  transition: all var(--transition-fast);
  flex-shrink: 0;
  z-index: 5;
}

.history-expand-toggle:hover {
  color: var(--lumi-primary);
  background: var(--surface-hover);
}

/* 中间对话区 */
.workbench-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--bg);
  position: relative;
}

.backend-warning {
  padding: 16px 24px;
  background: var(--lumi-danger-light);
  border-bottom: 1px solid var(--lumi-danger);
}

.warning-content {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--lumi-danger);
}

.warning-text {
  flex: 1;
}

.warning-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0;
}

.warning-desc {
  font-size: 12px;
  margin: 2px 0 0;
  opacity: 0.8;
}

.retry-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: none;
  background: var(--lumi-danger);
  color: var(--text-inverse);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: background 0.15s ease-in-out;
}

.retry-btn:hover {
  background: var(--lumi-danger-hover);
}

.chat-area {
  flex: 1;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 主智能体标识栏 */
.main-agent-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 20px;
  border-bottom: 1px solid var(--border-light);
  background: var(--surface);
  flex-shrink: 0;
}

.main-agent-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  background: var(--lumi-primary-light);
  border-radius: var(--radius-sm);
  color: var(--lumi-primary);
  font-size: 12px;
  font-weight: 600;
}

.main-agent-model {
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.messages-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.messages-container {
  max-width: 820px;
  margin: 0 auto;
}

.message-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  animation: msg-in 0.25s ease-in-out;
}

@keyframes msg-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-row.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.avatar-assistant {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--lumi-primary), var(--lumi-primary-soft));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-inverse);
}

.message-body {
  flex: 1;
  min-width: 0;
  max-width: calc(100% - 44px);
}

.message-sender {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.reasoning-section {
  margin-bottom: 8px;
  background: var(--surface-hover);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.reasoning-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-muted);
  transition: background 0.15s ease-in-out;
}

.reasoning-header:hover {
  background: var(--surface-active);
}

.reasoning-chevron {
  margin-left: auto;
  transition: transform 0.2s ease-in-out;
}

.reasoning-chevron.rotated {
  transform: rotate(-90deg);
}

.reasoning-content {
  padding: 8px 12px 12px;
  font-size: 12px;
  color: var(--text-muted);
  max-height: 240px;
  overflow-y: auto;
}

/* 工具调用活动区 */
.tool-activities-section {
  margin-bottom: 8px;
  background: var(--surface-hover);
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-light);
}

.tool-activities-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--surface-active);
}

.tool-activities-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.tool-activity-item {
  background: var(--surface);
}

.tool-activity-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary);
  transition: background 0.15s ease-in-out;
}

.tool-activity-header:hover {
  background: var(--surface-hover);
}

.tool-activity-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.tool-activity-icon :deep(svg) {
  color: var(--text-muted);
}

.tool-activity-icon .spin-animation {
  color: var(--lumi-primary);
}

.tool-activity-item .tool-activity-icon svg[stroke="currentColor"] {
  color: var(--lumi-success);
}

.tool-activity-name {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-weight: 500;
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-activity-iteration {
  font-size: 10px;
  color: var(--text-muted);
  padding: 1px 6px;
  background: var(--surface-hover);
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.tool-activity-chevron {
  margin-left: auto;
  flex-shrink: 0;
  color: var(--text-muted);
  transition: transform 0.2s ease-in-out;
}

.tool-activity-chevron.rotated {
  transform: rotate(-90deg);
}

.tool-activity-args {
  padding: 0 12px 8px 36px;
}

.tool-activity-args pre {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  margin: 0;
  overflow-x: auto;
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.tool-activity-output {
  padding: 0 12px 8px 36px;
}

.tool-activity-output pre {
  font-size: 11px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  margin: 0;
  overflow-x: auto;
  max-height: 200px;
  overflow-y: auto;
  font-family: 'JetBrains Mono', Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ===== 子 Agent 群组执行卡片 ===== */
.subagent-activities-section {
  margin-bottom: 8px;
  background: var(--surface-hover);
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-light);
}

.subagent-activities-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--surface-active);
}

.subagent-active-badge {
  margin-left: auto;
  font-size: 10px;
  font-weight: 500;
  color: var(--lumi-primary);
  padding: 2px 8px;
  background: var(--lumi-primary-light);
  border-radius: var(--radius-full);
  animation: pulse 1.5s ease-in-out infinite;
}

.subagent-activities-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px;
}

.subagent-card {
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: border-color 0.2s ease-in-out;
}

/* 进行中的子 Agent 卡片：流光边框效果（参考 deer-flow ShineBorder） */
.subagent-card.running {
  border-color: var(--lumi-primary);
  position: relative;
}

.subagent-card.running::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: var(--radius-md);
  padding: 1px;
  background: linear-gradient(
    90deg,
    var(--lumi-primary),
    var(--lumi-primary-soft),
    var(--lumi-primary)
  );
  background-size: 200% 100%;
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  animation: subagent-shine 2s linear infinite;
  pointer-events: none;
  z-index: 1;
}

@keyframes subagent-shine {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.subagent-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  transition: background 0.15s ease-in-out;
}

.subagent-card-header:hover {
  background: var(--surface-hover);
}

.subagent-status-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.subagent-status-icon :deep(svg) {
  color: var(--text-muted);
}

.subagent-card.running .subagent-status-icon .spin-animation {
  color: var(--lumi-primary);
}

.subagent-card.completed .subagent-status-icon :deep(svg) {
  color: var(--lumi-success);
}

.subagent-card.failed .subagent-status-icon :deep(svg) {
  color: var(--lumi-danger);
}

.subagent-card-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.subagent-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.subagent-task {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subagent-depth {
  font-size: 10px;
  color: var(--text-muted);
  padding: 1px 6px;
  background: var(--surface-hover);
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.subagent-card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-muted);
}

.subagent-progress {
  color: var(--lumi-primary);
  font-style: italic;
}

.subagent-status-text.completed {
  color: var(--lumi-success);
}

.subagent-status-text.failed {
  color: var(--lumi-danger);
}

.subagent-tools-count {
  margin-left: auto;
  font-size: 10px;
  padding: 1px 6px;
  background: var(--surface-hover);
  border-radius: var(--radius-full);
}

.subagent-chevron {
  color: var(--text-muted);
  flex-shrink: 0;
  transition: transform 0.2s ease-in-out;
}

.subagent-chevron.rotated {
  transform: rotate(-90deg);
}

.subagent-card-body {
  padding: 0 12px 12px;
  border-top: 1px solid var(--border-light);
}

/* 子 Agent 工具调用历史 */
.subagent-tools-section {
  margin-top: 8px;
}

.subagent-tools-header {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 8px;
  cursor: pointer;
  font-size: 11px;
  color: var(--text-muted);
  background: var(--surface-hover);
  border-radius: var(--radius-sm);
  transition: background 0.15s ease-in-out;
}

.subagent-tools-header:hover {
  background: var(--surface-active);
}

.subagent-tools-chevron {
  margin-left: auto;
  transition: transform 0.2s ease-in-out;
}

.subagent-tools-chevron.rotated {
  transform: rotate(-90deg);
}

.subagent-tools-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 6px;
}

.subagent-tool-item {
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  padding: 6px 8px;
}

.subagent-tool-header {
  display: flex;
  align-items: center;
  gap: 5px;
}

.subagent-tool-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.subagent-tool-icon .spin-animation {
  color: var(--lumi-primary);
}

.subagent-tool-icon :deep(svg) {
  color: var(--lumi-success);
}

.subagent-tool-name {
  font-size: 11px;
  font-family: 'JetBrains Mono', Consolas, monospace;
  color: var(--text-primary);
  font-weight: 500;
}

.subagent-tool-args pre,
.subagent-tool-output pre {
  font-size: 10px;
  color: var(--text-muted);
  background: var(--surface);
  padding: 4px 6px;
  border-radius: var(--radius-sm);
  margin: 4px 0 0;
  overflow-x: auto;
  max-height: 120px;
  overflow-y: auto;
  font-family: 'JetBrains Mono', Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 子 Agent 最终结果 */
.subagent-result {
  margin-top: 10px;
  padding: 8px;
  background: var(--lumi-success-light, rgba(34, 197, 94, 0.08));
  border-radius: var(--radius-sm);
  border-left: 2px solid var(--lumi-success);
}

.subagent-result-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 600;
  color: var(--lumi-success);
  margin-bottom: 4px;
}

.subagent-result-content {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-primary);
  max-height: 240px;
  overflow-y: auto;
}

.subagent-result-content :deep(p) {
  margin: 4px 0;
}

.subagent-result-content :deep(pre) {
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  padding: 8px;
  overflow-x: auto;
  font-size: 11px;
  margin: 4px 0;
}

/* 子 Agent 错误信息 */
.subagent-error {
  margin-top: 10px;
  padding: 8px;
  background: var(--lumi-danger-light);
  border-radius: var(--radius-sm);
  border-left: 2px solid var(--lumi-danger);
}

.subagent-error-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 600;
  color: var(--lumi-danger);
  margin-bottom: 4px;
}

.subagent-error-content {
  font-size: 11px;
  color: var(--text-secondary);
  word-break: break-word;
  line-height: 1.5;
}

/* 子 Agent 卡片展开动画 */
.subagent-slide-enter-active,
.subagent-slide-leave-active {
  transition: opacity 0.2s ease-in-out, max-height 0.2s ease-in-out;
  overflow: hidden;
}

.subagent-slide-enter-from,
.subagent-slide-leave-to {
  opacity: 0;
  max-height: 0;
}

/* ===== 计划确认卡片（借鉴 deer-flow ClarificationMiddleware） ===== */
.plan-confirmation-section {
  margin-bottom: 8px;
  background: var(--surface-hover);
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
  animation: plan-appear 0.25s ease-in-out;
}

@keyframes plan-appear {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

.plan-confirmation-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  border-bottom: 1px solid var(--border-light);
}

.plan-task-count {
  margin-left: auto;
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  background: var(--surface);
  border-radius: var(--radius-full);
  color: var(--text-secondary);
}

.plan-confirmation-body {
  padding: 12px 14px;
}

.plan-summary {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 10px;
  padding: 8px 10px;
  background: var(--surface);
  border-radius: var(--radius-sm);
  border-left: 2px solid var(--lumi-primary);
}

.plan-tasks-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.plan-task-item {
  display: flex;
  gap: 10px;
  padding: 8px 10px;
  background: var(--surface);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
  transition: border-color 0.15s ease-in-out;
}

.plan-task-item:hover {
  border-color: var(--lumi-primary);
}

.plan-task-index {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.plan-task-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.plan-task-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.4;
}

.plan-task-desc {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.5;
}

.plan-task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
}

.plan-task-tool {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  color: var(--text-muted);
  padding: 1px 6px;
  background: var(--surface-hover);
  border-radius: var(--radius-full);
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.plan-task-priority {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  font-weight: 500;
}

.plan-task-priority.urgent {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.plan-task-priority.high {
  background: var(--lumi-warning-light, rgba(245, 158, 11, 0.1));
  color: var(--lumi-warning);
}

.plan-task-priority.low {
  background: var(--surface-hover);
  color: var(--text-muted);
}

.plan-feedback-area {
  margin-bottom: 10px;
}

.plan-feedback-input {
  width: 100%;
  border: 1px solid var(--border-light);
  background: var(--surface);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  font-size: 12px;
  color: var(--text-primary);
  font-family: inherit;
  resize: none;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s ease-in-out;
}

.plan-feedback-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 2px var(--lumi-primary-glow);
}

.plan-feedback-input::placeholder {
  color: var(--text-muted);
}

.plan-confirmation-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.plan-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: background 0.15s ease-in-out, transform 0.1s ease-in-out;
}

.plan-btn:active {
  transform: scale(0.97);
}

.plan-btn-confirm {
  background: var(--lumi-primary);
  color: var(--text-inverse);
}

.plan-btn-confirm:hover {
  background: var(--lumi-primary-hover);
}

.plan-btn-reject {
  background: var(--surface-hover);
  color: var(--text-secondary);
  border: 1px solid var(--border-light);
}

.plan-btn-reject:hover {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
  border-color: var(--lumi-danger);
}

.message-content {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
  word-break: break-word;
}

.message-content.user-message {
  background: var(--lumi-primary);
  color: var(--text-inverse);
  padding: 10px 14px;
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg);
  display: inline-block;
  max-width: 100%;
}

.user-msg-layout {
  display: flex;
  flex-direction: row-reverse;
  align-items: flex-end;
  gap: 8px;
}

.user-msg-btns {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.15s ease-in-out;
}

.message-row.user:hover .user-msg-btns {
  opacity: 1;
}

.markdown-body :deep(pre) {
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  overflow-x: auto;
  font-size: 13px;
  margin: 8px 0;
}

.markdown-body :deep(code) {
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.markdown-body :deep(p) {
  margin: 6px 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 6px 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 12px 0 6px;
  font-weight: 600;
}

.interrupted-inline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--lumi-warning);
  margin-left: 6px;
}

.interrupted-only {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--lumi-warning);
  padding: 4px 0;
}

.streaming-indicator {
  display: inline-flex;
  align-items: center;
  margin-top: 4px;
}

.streaming-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--lumi-primary);
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}

.assistant-msg-actions {
  display: flex;
  gap: 4px;
  margin-top: 6px;
  opacity: 0;
  transition: opacity 0.15s ease-in-out;
}

.message-row.assistant:hover .assistant-msg-actions {
  opacity: 1;
}

.u-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.15s ease-in-out, color 0.15s ease-in-out;
}

.u-btn:hover {
  background: var(--surface-active);
  color: var(--text-primary);
}

.u-btn-hover {
  background: var(--surface);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
  color: var(--text-muted);
}

.empty-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--lumi-primary-gradient-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
  margin-bottom: 20px;
  box-shadow: 0 4px 24px var(--lumi-primary-glow);
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 6px;
}

.empty-desc {
  font-size: 13px;
  margin: 0 0 20px;
}

.empty-quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.quick-action {
  padding: 8px 16px;
  border: 1px solid var(--border-light);
  background: var(--surface);
  color: var(--text-secondary);
  border-radius: var(--radius-full);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s ease-in-out;
}

.quick-action:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.conv-loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--overlay-subtle);
  backdrop-filter: blur(4px);
  z-index: 5;
}

.conv-loading-content {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: var(--surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  font-size: 13px;
  color: var(--text-secondary);
}

.scroll-to-bottom-btn {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  width: 36px;
  height: 36px;
  border: 1px solid var(--border-light);
  background: var(--surface);
  color: var(--text-secondary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: all 0.15s ease-in-out;
  z-index: 4;
}

.scroll-to-bottom-btn:hover {
  color: var(--lumi-primary);
  box-shadow: var(--shadow-lg);
}

.spin-animation {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 输入区 */
.input-area {
  padding: 12px 24px 16px;
  background: var(--bg);
  flex-shrink: 0;
}

.input-wrapper {
  max-width: 820px;
  margin: 0 auto;
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: 10px 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  transition: border-color 0.15s ease-in-out;
}

.input-wrapper:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.chat-input {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  resize: none;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  font-family: inherit;
  min-height: 24px;
  max-height: 120px;
}

.chat-input::placeholder {
  color: var(--text-muted);
}

.chat-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 工作流模式切换按钮 */
.workflow-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 11px;
  color: var(--text-muted);
  background: var(--surface-hover);
  border: 1px solid transparent;
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all 0.2s ease-in-out;
}

.workflow-toggle:hover {
  background: var(--surface-active);
  color: var(--text-primary);
}

.workflow-toggle.active {
  color: var(--accent-primary, #10b981);
  background: var(--accent-surface, rgba(16, 185, 129, 0.1));
  border-color: var(--accent-border, rgba(16, 185, 129, 0.3));
}

.workflow-toggle-text {
  white-space: nowrap;
}

/* P2：工作流执行模式选择器 */
.workflow-mode-selector {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 2px;
  background: var(--surface-hover);
  border-radius: var(--radius-full);
}

.mode-chip {
  padding: 3px 9px;
  font-size: 11px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  white-space: nowrap;
}

.mode-chip:hover {
  color: var(--text-primary);
  background: var(--surface-active);
}

.mode-chip.active {
  color: var(--accent-primary, #10b981);
  background: var(--accent-surface, rgba(16, 185, 129, 0.15));
  font-weight: 500;
}

.model-tag {
  font-size: 11px;
  color: var(--text-muted);
  padding: 3px 8px;
  background: var(--surface-hover);
  border-radius: var(--radius-full);
}

/* 模型下拉框 */
.model-btn-text {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-dropdown-container {
  position: relative;
}

.model-dropdown {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  width: 280px;
  background: var(--surface);
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  border: 1px solid var(--border-light);
  z-index: 9999;
  overflow: hidden;
}

.dropdown-header {
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
}

.dropdown-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 14px;
  right: 14px;
  height: 1px;
  background: var(--divider-soft);
}

.dropdown-list {
  max-height: 280px;
  overflow-y: auto;
  padding: 4px;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  text-align: left;
  transition: all 250ms ease-in-out;
}

.dropdown-item:hover {
  background: var(--workspace-hover);
}

.dropdown-item.active {
  background: var(--lumi-primary-light);
}

.dropdown-item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.dropdown-item-model {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-item-provider {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-item.active .dropdown-item-model {
  color: var(--lumi-primary);
}

.dropdown-empty {
  padding: 20px 14px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}

.provider-icon-mini {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 8px;
  font-weight: 700;
  color: var(--text-inverse);
  flex-shrink: 0;
}

.provider-svg-mini {
  background: transparent !important;
}

.provider-svg-mini :deep(svg) {
  width: 16px;
  height: 16px;
}

.dropdown-fade-enter-active {
  animation: dropdown-in 0.2s ease-out;
}

.dropdown-fade-leave-active {
  animation: dropdown-in 0.15s ease-out reverse;
}

@keyframes dropdown-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  background: var(--lumi-primary);
  color: var(--text-inverse);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.15s ease-in-out;
}

.send-btn:hover {
  background: var(--lumi-primary-hover);
}

.send-btn.disabled {
  background: var(--surface-hover);
  color: var(--text-muted);
  cursor: not-allowed;
}

.send-btn.stop {
  background: var(--lumi-danger);
}

.send-btn.stop:hover {
  background: var(--lumi-danger-hover);
}

/* 右侧 Live2D 区 */
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

.avatar-header {
  padding: 14px 16px 10px;
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.avatar-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.avatar-model-selector {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.model-chip {
  padding: 4px 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-muted);
  border-radius: var(--radius-full);
  cursor: pointer;
  font-size: 11px;
  transition: all 0.15s ease-in-out;
}

.model-chip:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.model-chip.active {
  background: var(--lumi-primary);
  color: var(--text-inverse);
  border-color: var(--lumi-primary);
}

.avatar-stage {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface);
  overflow: hidden;
}

.avatar-stage.desktop-mode-active {
  background:
    radial-gradient(circle at 50% 50%, var(--lumi-primary-subtle) 0%, transparent 70%),
    var(--surface);
}

.desktop-mode-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  padding: 40px 24px;
  text-align: center;
  animation: hint-fade-in 500ms ease-in-out;
}

@keyframes hint-fade-in {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.desktop-mode-hint .hint-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  animation: hint-icon-pulse 3s ease-in-out infinite;
}

@keyframes hint-icon-pulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--lumi-primary-glow); }
  50% { box-shadow: 0 0 0 12px transparent; }
}

.desktop-mode-hint .hint-content h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.desktop-mode-hint .hint-content p {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.6;
  max-width: 280px;
}

.desktop-mode-hint .hint-sub {
  font-size: 11px !important;
  opacity: 0.7;
  margin-top: 4px;
}

.live2d-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.avatar-loading,
.avatar-error {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--text-muted);
  font-size: 13px;
  background: var(--surface);
}

.avatar-error {
  color: var(--lumi-danger);
}

.avatar-status {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  background: var(--surface);
  backdrop-filter: blur(8px);
  border-radius: var(--radius-full);
  font-size: 11px;
  color: var(--text-secondary);
  border: 1px solid var(--border-light);
  z-index: 2;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--lumi-success);
  animation: pulse 2s ease-in-out infinite;
}

.status-dot.speaking {
  background: var(--lumi-primary);
  animation: pulse 0.6s ease-in-out infinite;
}

.avatar-subtitle {
  position: absolute;
  bottom: 48px;
  left: 50%;
  transform: translateX(-50%);
  max-width: 88%;
  padding: 8px 14px;
  background: var(--surface);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-primary);
  text-align: center;
  cursor: pointer;
  z-index: 3;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.avatar-footer {
  padding: 10px 16px 14px;
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

.avatar-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 8px;
}

.ctrl-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-muted);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s ease-in-out;
}

.ctrl-btn:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.ctrl-btn.active {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.ctrl-btn.stop-btn {
  border-color: var(--lumi-danger);
  color: var(--lumi-danger);
  background: var(--lumi-danger-light);
}

.ctrl-btn.stop-btn:hover {
  background: var(--lumi-danger);
  color: var(--text-inverse);
}

.avatar-tip {
  font-size: 11px;
  color: var(--text-muted);
  margin: 0;
  text-align: center;
  line-height: 1.5;
}

/* ===== 主 Agent 状态面板 ===== */
.agent-panels {
  flex-shrink: 0;
  border-top: 1px solid var(--border-light);
  max-height: 40%;
  overflow-y: auto;
}

.agent-panel {
  border-bottom: 1px solid var(--border-light);
}

.agent-panel:last-child {
  border-bottom: none;
}

.agent-panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary);
  transition: background 0.15s ease-in-out;
}

.agent-panel-header:hover {
  background: var(--surface-hover);
}

.agent-panel-header.static {
  cursor: default;
}

.agent-panel-header.static:hover {
  background: transparent;
}

.agent-panel-title {
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.agent-panel-badge {
  font-size: 10px;
  color: var(--text-muted);
  padding: 2px 7px;
  background: var(--surface-hover);
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.agent-panel-hint {
  font-size: 10px;
  color: var(--text-muted);
  flex: 1;
  text-align: right;
}

.agent-panel-chevron {
  color: var(--text-muted);
  transition: transform 0.2s ease-in-out;
  flex-shrink: 0;
}

.agent-panel-chevron.expanded {
  transform: rotate(90deg);
}

.agent-panel-body {
  padding: 8px 16px 12px;
  font-size: 11px;
  color: var(--text-secondary);
}

.panel-empty {
  color: var(--text-muted);
  font-size: 11px;
  padding: 4px 0;
}

/* 记忆快览 */
.memory-profile {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.memory-label {
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.memory-value {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-primary);
}

.memory-summary {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.5;
  max-height: 60px;
  overflow-y: auto;
  word-break: break-word;
}

/* MCP 服务器列表 */
.mcp-server-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
}

.mcp-server-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
}

.mcp-server-dot.connected {
  background: var(--lumi-success);
}

.mcp-server-dot.connecting {
  background: var(--lumi-warning);
}

.mcp-server-dot.error,
.mcp-server-dot.disconnected {
  background: var(--text-muted);
}

.mcp-server-name {
  flex: 1;
  font-size: 11px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mcp-server-tools {
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.mcp-total {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid var(--border-light);
}

/* 消息平台列表 */
.platform-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
}

.platform-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
}

.platform-dot.active {
  background: var(--lumi-success);
}

.platform-name {
  flex: 1;
  font-size: 11px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.platform-type {
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
}

/* 右侧面板子 Agent 列表 */
.subagent-side-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
}

.subagent-side-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
}

.subagent-side-dot.running {
  background: var(--lumi-primary);
  animation: pulse 1s ease-in-out infinite;
}

.subagent-side-dot.completed {
  background: var(--lumi-success);
}

.subagent-side-dot.failed {
  background: var(--lumi-danger);
}

.subagent-side-task {
  flex: 1;
  font-size: 11px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subagent-side-depth {
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
}

/* 面板折叠动画 */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: opacity 0.2s ease-in-out, max-height 0.2s ease-in-out;
  overflow: hidden;
}

.panel-slide-enter-from,
.panel-slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.subtitle-fade-enter-active,
.subtitle-fade-leave-active {
  transition: opacity 0.2s ease-in-out, transform 0.2s ease-in-out;
}

.subtitle-fade-enter-from,
.subtitle-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

/* 过渡动画 */
.history-slide-enter-active {
  animation: history-slide-in 0.2s ease-in-out;
}

.history-slide-leave-active {
  animation: history-slide-out 0.15s ease-in-out;
}

@keyframes history-slide-in {
  from { opacity: 0; transform: translateX(-10px); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes history-slide-out {
  from { opacity: 1; transform: translateX(0); }
  to { opacity: 0; transform: translateX(-10px); }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease-in-out;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.conv-loading-fade-enter-active,
.conv-loading-fade-leave-active {
  transition: opacity 0.2s ease-in-out;
}

.conv-loading-fade-enter-from,
.conv-loading-fade-leave-to {
  opacity: 0;
}

.scroll-btn-fade-enter-active,
.scroll-btn-fade-leave-active {
  transition: opacity 0.2s ease-in-out, transform 0.2s ease-in-out;
}

.scroll-btn-fade-enter-from,
.scroll-btn-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

.msg-appear-enter-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}

.msg-appear-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
</style>
