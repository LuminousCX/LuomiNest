/**
 * LuomiNest 工作流 Store
 *
 * 管理主 Agent 长任务工作流的执行状态：
 * 1. 提交长任务到后端 WorkflowEngine
 * 2. 接收 SSE 流式事件（phase_change, task_started, task_completed, module_action 等）
 * 3. 将 module_action 事件路由到对应页面（浏览器、计划、记忆等）
 *
 * 事件路由机制：
 * - module_action 事件根据 data.module 字段分发
 * - browser → taskStreamStore（打开标签页）
 * - schedule → taskStreamStore（创建定时任务）
 * - memory → memoryStore（刷新记忆列表）
 * - console → 控制台输出
 *
 * 参考：
 * - deer-flow: StreamBridge 流式解耦
 * - taskStream.ts: 多页面共享枢纽模式
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '../composables/useApi'
import { useTaskStreamStore } from './taskStream'
import { useMemoryStore } from './memory'
import { generateId } from '../utils/id'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('Workflow')

/** 工作流阶段 */
export type WorkflowPhase =
  | 'analyzing'
  | 'planning'
  | 'waiting_confirmation'
  | 'executing'
  | 'synthesizing'
  | 'completed'
  | 'failed'

/** 工作流执行模式（仅工作流模式，普通模式见 ChatMode）
 * - standard: 标准模式，平衡速度与深度（默认），排除细粒度浏览器自动化工具
 * - ultra: 超长模式，最大能力，适合复杂长任务，全部工具可用
 */
export type WorkflowMode = 'standard' | 'ultra'

/** 工作流子任务状态 */
export type WorkflowTaskStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'skipped'

/** 工作流子任务 */
export interface WorkflowTask {
  task_id: string
  title: string
  description: string
  task_type: string
  tool_name: string
  arguments: Record<string, unknown>
  depends_on: string[]
  priority: 'normal' | 'high' | 'urgent' | 'low'
  node_type: 'input' | 'agent' | 'tool' | 'condition' | 'output'
  status: WorkflowTaskStatus
  result: string | null
  error: string | null
  metadata: Record<string, unknown>
  started_at: string | null
  completed_at: string | null
}

/** 模块操作事件 */
export interface ModuleActionEvent {
  module: string
  action: string
  success: boolean
  output?: string
  error?: string
  metadata?: Record<string, unknown>
  // 浏览器专用
  url?: string
  title?: string
  tab_id?: string
  purpose?: string
  // 计划任务专用
  task_id?: string
  name?: string
  schedule?: string
  task_action?: string
  // 记忆专用
  memory_id?: string
  content_preview?: string
  category?: string
  query?: string
  results_count?: number
  // 控制台专用
  command?: string
}

/** 类型守卫：验证 data 是否为 ModuleActionEvent */
function isModuleActionEvent(data: unknown): data is ModuleActionEvent {
  if (typeof data !== 'object' || data === null) return false
  const d = data as Record<string, unknown>
  return (
    typeof d.module === 'string' &&
    typeof d.action === 'string' &&
    typeof d.success === 'boolean'
  )
}

/** 工作流会话状态 */
export interface WorkflowSessionState {
  session_id: string
  phase: WorkflowPhase
  plan: string | null
  tasks: WorkflowTask[]
  final_result: string | null
  error: string | null
  created_at: string
  completed_at: string | null
  conversation_id: string | null
}

export const useWorkflowStore = defineStore('workflow', () => {
  const { apiSseStream, apiPost } = useApi()

  // 当前活跃的工作流会话
  const currentSession = ref<WorkflowSessionState | null>(null)
  // 是否正在执行工作流
  const isRunning = ref(false)
  // 执行进度日志
  const progressLog = ref<Array<{
    type: string
    message: string
    timestamp: number
  }>>([])
  // 模块操作事件（供各页面订阅）
  const moduleActions = ref<ModuleActionEvent[]>([])

  // 计划确认机制（借鉴 deer-flow ClarificationMiddleware）
  // 当 phase === 'waiting_confirmation' 时，pendingPlan 包含待确认的计划
  const pendingPlan = ref<{
    plan: string
    tasks: WorkflowTask[]
  } | null>(null)
  // 用户反馈输入
  const confirmationFeedback = ref('')

  // 统计
  const totalTasks = computed(() => currentSession.value?.tasks.length ?? 0)
  const completedTasks = computed(
    () => currentSession.value?.tasks.filter(t => t.status === 'completed').length ?? 0
  )
  const failedTasks = computed(
    () => currentSession.value?.tasks.filter(t => t.status === 'failed').length ?? 0
  )
  const progress = computed(() => {
    if (totalTasks.value === 0) return 0
    return Math.round((completedTasks.value / totalTasks.value) * 100)
  })

  /**
   * 提交长任务到工作流引擎（SSE 流式）
   */
  const submitWorkflow = async (
    message: string,
    options?: {
      provider?: string
      model?: string
      mode?: WorkflowMode
      conversationId?: string
      onPhaseChange?: (phase: WorkflowPhase) => void
      onModuleAction?: (event: ModuleActionEvent) => void
      onReasoning?: (content: string, phase: string) => void
      onPlanCreated?: (sessionId: string, taskCount: number) => void
      onFinalResult?: (result: string) => void
      externalAbortSignal?: AbortSignal
    }
  ): Promise<void> => {
    if (isRunning.value) {
      logger.warn('工作流正在执行中，请等待完成')
      return
    }

    isRunning.value = true
    currentSession.value = null
    progressLog.value = []
    moduleActions.value = []

    await apiSseStream(
      '/workflow/submit/stream',
      {
        message,
        provider: options?.provider,
        model: options?.model,
        mode: options?.mode ?? 'standard',
        conversation_id: options?.conversationId,
      },
      (event: Record<string, unknown>) => {
        handleWorkflowEvent(event, options)
      },
      () => {
        isRunning.value = false
      },
      (err: string) => {
        logger.error('工作流执行失败:', err)
        isRunning.value = false
        progressLog.value.unshift({
          type: 'error',
          message: err,
          timestamp: Date.now(),
        })
      },
      options?.externalAbortSignal
    )
  }

  /**
   * 处理工作流 SSE 事件
   */
  const handleWorkflowEvent = (
    event: Record<string, unknown>,
    options?: {
      onPhaseChange?: (phase: WorkflowPhase) => void
      onModuleAction?: (event: ModuleActionEvent) => void
      onReasoning?: (content: string, phase: string) => void
      onPlanCreated?: (sessionId: string, taskCount: number) => void
      onFinalResult?: (result: string) => void
    }
  ) => {
    const eventType = event.type as string
    const data = (event.data ?? {}) as Record<string, unknown>

    switch (eventType) {
      case 'session_start': {
        currentSession.value = {
          session_id: data.session_id as string,
          phase: data.phase as WorkflowPhase,
          plan: null,
          tasks: [],
          final_result: null,
          error: null,
          created_at: new Date().toISOString(),
          completed_at: null,
          conversation_id: (data.conversation_id as string | null) ?? null,
        }
        break
      }

      case 'phase_change': {
        const phase = data.phase as WorkflowPhase
        if (currentSession.value) {
          currentSession.value.phase = phase
        }
        progressLog.value.unshift({
          type: 'phase',
          message: `阶段切换: ${phase}`,
          timestamp: Date.now(),
        })
        options?.onPhaseChange?.(phase)
        break
      }

      case 'planning': {
        progressLog.value.unshift({
          type: 'planning',
          message: data.message as string,
          timestamp: Date.now(),
        })
        break
      }

      case 'reasoning': {
        const content = (data.content as string) || ''
        const phase = (data.phase as string) || 'planning'
        progressLog.value.unshift({
          type: 'reasoning',
          message: `思考过程 (${phase}): ${content.slice(0, 80)}${content.length > 80 ? '...' : ''}`,
          timestamp: Date.now(),
        })
        options?.onReasoning?.(content, phase)
        break
      }

      case 'plan_created': {
        if (currentSession.value) {
          currentSession.value.plan = data.plan as string
          currentSession.value.tasks = (data.tasks as WorkflowTask[]) || []
        }
        progressLog.value.unshift({
          type: 'plan',
          message: `执行计划已创建，共 ${data.task_count} 个子任务`,
          timestamp: Date.now(),
        })
        options?.onPlanCreated?.(
          currentSession.value?.session_id ?? '',
          (data.task_count as number) || 0
        )
        break
      }

      case 'plan_pending_confirmation': {
        // 计划等待用户确认（借鉴 deer-flow ClarificationMiddleware）
        pendingPlan.value = {
          plan: (data.plan as string) || '',
          tasks: (data.tasks as WorkflowTask[]) || [],
        }
        confirmationFeedback.value = ''
        progressLog.value.unshift({
          type: 'plan_pending',
          message: `计划已生成，等待确认（共 ${(data.task_count as number) || 0} 个子任务）`,
          timestamp: Date.now(),
        })
        break
      }

      case 'plan_confirmed': {
        pendingPlan.value = null
        confirmationFeedback.value = ''
        progressLog.value.unshift({
          type: 'plan_confirmed',
          message: '用户已确认执行计划',
          timestamp: Date.now(),
        })
        break
      }

      case 'plan_auto_confirmed': {
        // 闪电模式：计划自动确认，无需用户干预
        pendingPlan.value = null
        confirmationFeedback.value = ''
        progressLog.value.unshift({
          type: 'plan_confirmed',
          message: '计划已自动确认（闪电模式）',
          timestamp: Date.now(),
        })
        break
      }

      case 'plan_rejected': {
        pendingPlan.value = null
        progressLog.value.unshift({
          type: 'plan_rejected',
          message: `用户拒绝了执行计划${data.feedback ? `：${data.feedback}` : ''}`,
          timestamp: Date.now(),
        })
        break
      }

      case 'task_started': {
        if (currentSession.value) {
          const task = currentSession.value.tasks.find(
            t => t.task_id === data.task_id
          )
          if (task) {
            task.status = 'running'
            task.started_at = new Date().toISOString()
          }
        }
        progressLog.value.unshift({
          type: 'task_started',
          message: `开始执行: ${data.title}`,
          timestamp: Date.now(),
        })
        break
      }

      case 'task_completed': {
        if (currentSession.value) {
          const task = currentSession.value.tasks.find(
            t => t.task_id === data.task_id
          )
          if (task) {
            task.status = 'completed'
            task.result = data.result as string
            task.completed_at = new Date().toISOString()
          }
        }
        progressLog.value.unshift({
          type: 'task_completed',
          message: `完成: ${data.title}`,
          timestamp: Date.now(),
        })
        break
      }

      case 'task_failed': {
        if (currentSession.value) {
          const task = currentSession.value.tasks.find(
            t => t.task_id === data.task_id
          )
          if (task) {
            task.status = 'failed'
            task.error = data.error as string
            task.completed_at = new Date().toISOString()
          }
        }
        progressLog.value.unshift({
          type: 'task_failed',
          message: `失败: ${data.title} - ${data.error}`,
          timestamp: Date.now(),
        })
        break
      }

      case 'module_action': {
        if (!isModuleActionEvent(data)) {
          console.warn('[Workflow] Invalid module_action event, missing required fields:', data)
          break
        }
        const moduleEvent = data
        moduleActions.value.push(moduleEvent)
        // 限制事件数量
        if (moduleActions.value.length > 100) {
          moduleActions.value = moduleActions.value.slice(-100)
        }
        // 路由到对应页面
        routeModuleAction(moduleEvent)
        options?.onModuleAction?.(moduleEvent)
        progressLog.value.unshift({
          type: 'module_action',
          message: `[${moduleEvent.module}] ${moduleEvent.action}: ${moduleEvent.success ? '成功' : '失败'}`,
          timestamp: Date.now(),
        })
        break
      }

      case 'final_result': {
        if (currentSession.value) {
          currentSession.value.final_result = data.content as string
          currentSession.value.phase = 'completed'
          currentSession.value.completed_at = new Date().toISOString()
        }
        progressLog.value.unshift({
          type: 'final',
          message: '工作流执行完成',
          timestamp: Date.now(),
        })
        options?.onFinalResult?.(data.content as string)
        break
      }

      case 'error': {
        const errMsg = (data.message as string) || '未知错误'
        if (currentSession.value) {
          currentSession.value.error = errMsg
          currentSession.value.phase = 'failed'
        }
        progressLog.value.unshift({
          type: 'error',
          message: errMsg,
          timestamp: Date.now(),
        })
        break
      }
    }

    // 限制日志数量
    if (progressLog.value.length > 200) {
      progressLog.value = progressLog.value.slice(0, 200)
    }
  }

  /**
   * 路由模块操作事件到对应页面
   *
   * 这是前端事件路由器的核心：
   * 根据 module 字段分发到 taskStreamStore 或 memoryStore
   */
  const routeModuleAction = (event: ModuleActionEvent) => {
    const taskStreamStore = useTaskStreamStore()

    switch (event.module) {
      case 'browser': {
        // 浏览器事件 → taskStreamStore（触发 BrowserView 打开标签页）
        if (event.tab_id && event.url) {
          taskStreamStore.handleSubagentEvent({
            subagent_id: `workflow_${event.tab_id}`,
            status: 'completed',
            task: event.title || event.purpose || '浏览器导航',
            depth: 0,
            browser_action: 'open_tab',
            browser_tab_id: event.tab_id,
            browser_url: event.url,
            browser_title: event.title || event.url,
            browser_purpose: event.purpose,
          })
        }
        break
      }

      case 'schedule': {
        // 计划任务事件 → taskStreamStore（触发 TasksView 刷新）
        if (event.task_id) {
          taskStreamStore.handleTaskEvent({
            task_id: event.task_id,
            task_name: event.name || '工作流创建的任务',
            status: 'pending',
            task_type: 'cron',
            message: `工作流创建: ${event.name}`,
            timestamp: new Date().toISOString(),
            payload: {
              schedule: event.schedule,
              action: event.task_action,
            },
          })
          // 拉取最新任务列表
          taskStreamStore.fetchScheduledTasks()
        }
        break
      }

      case 'memory': {
        // 记忆事件 → memoryStore（触发 MemoryView 刷新）
        try {
          const memoryStore = useMemoryStore()
          if (event.action === 'stored') {
            memoryStore.fetchMemory()
            memoryStore.fetchFacts()
          }
        } catch {
          // memoryStore 可能在某些上下文不可用
        }
        break
      }

      case 'console': {
        // 控制台事件 → 日志记录（ConsoleView 可订阅 moduleActions）
        break
      }

      case 'market': {
        // 扩展市场事件 → 刷新已安装列表
        if (event.action === 'installed' || event.action === 'uninstalled') {
          try {
            // 通过 taskStreamStore 通知市场页面刷新
            taskStreamStore.handleSubagentEvent({
              subagent_id: generateId('workflow_market'),
              status: 'completed',
              task: `扩展市场: ${event.action === 'installed' ? '安装' : '卸载'} ${event.metadata?.item_id ?? ''}`,
              depth: 0,
              result: event.output || event.error,
            })
          } catch {
            // 忽略
          }
        }
        break
      }

      case 'platform': {
        // 平台接入事件 → 通知平台管理页面
        if (event.metadata?.instance_id) {
          taskStreamStore.handleSubagentEvent({
            subagent_id: `workflow_platform_${event.metadata.instance_id}`,
            status: 'completed',
            task: `平台实例: ${event.action} ${event.metadata.instance_id}`,
            depth: 0,
            result: event.output || event.error,
          })
        }
        break
      }

      case 'smart_home': {
        // 智能家居事件 → taskStreamStore（触发 SmartHomeView 更新设备状态）
        if (event.metadata?.device_id) {
          taskStreamStore.handleSubagentEvent({
            subagent_id: `workflow_smart_home_${event.metadata.device_id}`,
            status: 'completed',
            task: `智能家居控制: ${event.metadata.device_id} ${event.action}`,
            depth: 0,
            progress: event.success ? '操作成功' : '操作失败',
            result: event.output || event.error,
          })
        }
        break
      }

      case 'subagent': {
        // 子 Agent 事件 → 日志记录
        break
      }
    }
  }

  /**
   * 取消当前工作流
   */
  const cancelWorkflow = async () => {
    if (!currentSession.value || !isRunning.value) return
    try {
      await apiPost(`/workflow/sessions/${currentSession.value.session_id}/cancel`)
      progressLog.value.unshift({
        type: 'cancel',
        message: '工作流已请求取消',
        timestamp: Date.now(),
      })
    } catch (err) {
      logger.error('取消工作流失败:', err)
    }
  }

  /**
   * 确认执行计划
   *
   * 用户在 plan_pending_confirmation 阶段点击"确认执行"后调用，
   * 后端 confirmation_event 被触发，工作流继续执行子任务。
   */
  const confirmPlan = async () => {
    if (!currentSession.value || !pendingPlan.value) return
    try {
      await apiPost(
        `/workflow/sessions/${currentSession.value.session_id}/confirm`,
        { feedback: confirmationFeedback.value }
      )
      // 乐观清空待确认状态，等待 plan_confirmed 事件确认
      pendingPlan.value = null
      progressLog.value.unshift({
        type: 'plan_confirm_sent',
        message: '已发送确认请求',
        timestamp: Date.now(),
      })
    } catch (err) {
      logger.error('确认计划失败:', err)
    }
  }

  /**
   * 拒绝执行计划
   *
   * 用户在 plan_pending_confirmation 阶段点击"拒绝执行"后调用，
   * 后端 confirmation_event 被触发，工作流终止。
   */
  const rejectPlan = async () => {
    if (!currentSession.value || !pendingPlan.value) return
    try {
      await apiPost(
        `/workflow/sessions/${currentSession.value.session_id}/reject`,
        { feedback: confirmationFeedback.value }
      )
      // 乐观清空待确认状态，等待 plan_rejected 事件确认
      pendingPlan.value = null
      progressLog.value.unshift({
        type: 'plan_reject_sent',
        message: '已发送拒绝请求',
        timestamp: Date.now(),
      })
    } catch (err) {
      logger.error('拒绝计划失败:', err)
    }
  }

  /**
   * 清空工作流状态
   */
  const clearWorkflow = () => {
    currentSession.value = null
    isRunning.value = false
    progressLog.value = []
    moduleActions.value = []
    pendingPlan.value = null
    confirmationFeedback.value = ''
  }

  return {
    currentSession,
    isRunning,
    progressLog,
    moduleActions,
    pendingPlan,
    confirmationFeedback,
    totalTasks,
    completedTasks,
    failedTasks,
    progress,
    submitWorkflow,
    cancelWorkflow,
    confirmPlan,
    rejectPlan,
    clearWorkflow,
    handleWorkflowEvent,
  }
})
