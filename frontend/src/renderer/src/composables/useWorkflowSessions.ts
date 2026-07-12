/**
 * LuomiNest 工作流会话列表状态
 *
 * 从 WorkflowView.vue 拆分：历史会话加载、当前显示会话计算、进度统计、运行控制。
 * 静态数据（PHASE_LABELS / formatWorkflowTime）以命名导出供子组件直接 import。
 */
import { ref, computed } from 'vue'
import { useWorkflowStore } from '../stores/workflow'
import { useApi } from './useApi'
import { createLuomiNestRendererLogger } from '../utils/logger'
import type { WorkflowSession } from '../types/workflow'

const logger = createLuomiNestRendererLogger('Workflow')

// ===== 静态数据 =====

export const PHASE_LABELS: Record<string, string> = {
  analyzing: '分析中',
  planning: '规划中',
  waiting_confirmation: '待确认',
  executing: '执行中',
  synthesizing: '综合中',
  completed: '已完成',
  failed: '已失败',
}

/** 格式化 ISO 时间为 MM/DD HH:mm */
export const formatWorkflowTime = (iso: string | null): string => {
  if (!iso) return '--'
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return '--'
  }
}

// ===== composable =====

export const useWorkflowSessions = () => {
  const workflowStore = useWorkflowStore()
  const { apiGet } = useApi()

  // 历史工作流会话列表
  const sessions = ref<WorkflowSession[]>([])
  const isLoadingSessions = ref(false)
  // 当前选中的会话 ID（null 表示显示 store 中的实时会话）
  const selectedSessionId = ref<string | null>(null)

  /**
   * 当前显示的会话（优先显示 store 中的实时会话，否则显示选中的历史会话）
   */
  const currentDisplaySession = computed<WorkflowSession | null>(() => {
    if (workflowStore.currentSession && workflowStore.isRunning) {
      const tasks = workflowStore.currentSession.tasks || []
      return {
        session_id: workflowStore.currentSession.session_id,
        user_message: '',
        phase: workflowStore.currentSession.phase,
        plan: workflowStore.currentSession.plan,
        tasks,
        final_result: workflowStore.currentSession.final_result,
        error: workflowStore.currentSession.error,
        created_at: workflowStore.currentSession.created_at,
        completed_at: workflowStore.currentSession.completed_at,
        conversation_id: workflowStore.currentSession.conversation_id,
        stats: {
          total: tasks.length,
          completed: tasks.filter((t) => t.status === 'completed').length,
          failed: tasks.filter((t) => t.status === 'failed').length,
        },
      }
    }
    // 显示选中的历史会话
    if (selectedSessionId.value) {
      return sessions.value.find((s) => s.session_id === selectedSessionId.value) || null
    }
    return null
  })

  // 加载历史工作流会话列表
  const loadSessions = async (): Promise<void> => {
    isLoadingSessions.value = true
    try {
      const data = await apiGet<{ sessions: WorkflowSession[] }>('/workflow/db/sessions?limit=20')
      sessions.value = data.sessions || []
    } catch (err: unknown) {
      logger.error('Failed to load workflow sessions:', err)
    } finally {
      isLoadingSessions.value = false
    }
  }

  // 选中历史会话
  const selectSession = (sessionId: string): void => {
    selectedSessionId.value = sessionId
  }

  // 返回实时会话视图
  const showLiveSession = (): void => {
    selectedSessionId.value = null
  }

  // 工作流运行状态
  const isRunning = computed(() => workflowStore.isRunning)

  // 实时会话指示（供侧栏组件使用）
  const hasLiveSession = computed(() => !!workflowStore.currentSession)
  const livePhase = computed(() => workflowStore.currentSession?.phase || '')

  const toggleRun = (): void => {
    if (isRunning.value) {
      workflowStore.cancelWorkflow()
    }
  }

  // 进度统计（CodeRabbit #6: 安全处理无 tasks 的历史会话）
  const progressStats = computed(() => {
    const session = currentDisplaySession.value
    if (!session || !session.tasks) {
      return { total: 0, completed: 0, failed: 0, progress: 0 }
    }
    const tasks = session.tasks
    const total = tasks.length
    const completed = tasks.filter((t) => t.status === 'completed').length
    const failed = tasks.filter((t) => t.status === 'failed').length
    const progress = total === 0 ? 0 : Math.round((completed / total) * 100)
    return { total, completed, failed, progress }
  })

  return {
    sessions,
    isLoadingSessions,
    selectedSessionId,
    currentDisplaySession,
    loadSessions,
    selectSession,
    showLiveSession,
    isRunning,
    hasLiveSession,
    livePhase,
    toggleRun,
    progressStats,
  }
}
