/**
 * LuomiNest 全局任务流 Store
 *
 * 管理主 Agent 工具回调产生的所有任务：
 * 1. 浏览器标签页任务（create_browser_tab 工具触发）
 * 2. 定时任务（create_scheduled_task 工具触发 + 调度器执行事件）
 * 3. 子 Agent 任务（delegate_to_subagent 工具触发）
 *
 * 各页面（/browser /tasks /workflow /workbench）订阅同一任务流，
 * 实现"多页面同时显示"效果。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SubagentEvent, TaskStreamEvent } from '../types'
import { useApi } from '../composables/useApi'

/** 浏览器标签页任务 */
export interface BrowserTabTask {
  tab_id: string
  url: string
  title: string
  purpose?: string
  status: 'pending' | 'opened' | 'failed'
  created_at: number
}

/** 定时任务信息 */
export interface ScheduledTaskInfo {
  id: string
  name: string
  description: string
  task_type: 'date' | 'cron' | 'interval'
  status: 'pending' | 'running' | 'completed' | 'failed' | 'removed'
  next_run_time: string | null
  last_run_time: string | null
  last_result: string | null
  last_error: string | null
  payload: Record<string, unknown>
  source: string
  created_at: string
}

export const useTaskStreamStore = defineStore('taskStream', () => {
  const { apiGet, apiDelete } = useApi()

  // 浏览器标签页任务列表
  const browserTasks = ref<BrowserTabTask[]>([])
  // 定时任务列表
  const scheduledTasks = ref<ScheduledTaskInfo[]>([])
  // 最近的任务事件流（用于工作台展示）
  const recentEvents = ref<Array<{
    type: 'browser' | 'scheduled' | 'subagent'
    timestamp: number
    data: Record<string, unknown>
  }>>([])

  // 待处理跳转提示（智能无感跳转被防打断策略拦截时，标记侧边栏红点）
  const pendingNavigation = ref<{ browser: boolean; workflow: boolean }>({
    browser: false,
    workflow: false,
  })

  // 浏览器任务统计
  const browserTaskCount = computed(() => browserTasks.value.length)
  const pendingBrowserTasks = computed(() =>
    browserTasks.value.filter(t => t.status === 'pending')
  )

  // 定时任务统计
  const scheduledTaskCount = computed(() => scheduledTasks.value.length)
  const activeScheduledTasks = computed(() =>
    scheduledTasks.value.filter(t => t.status === 'pending' || t.status === 'running')
  )

  /**
   * 处理子 Agent 事件（含浏览器工具事件）
   * WorkbenchView 的 onChunk 收到 subagent_event 时调用
   */
  const handleSubagentEvent = (event: SubagentEvent) => {
    // 浏览器工具事件：create_browser_tab 复用 subagent_event 通道
    if (event.browser_action === 'open_tab' && event.browser_tab_id) {
      const task: BrowserTabTask = {
        tab_id: event.browser_tab_id,
        url: event.browser_url || '',
        title: event.browser_title || event.browser_url || '',
        purpose: event.browser_purpose,
        status: 'pending',
        created_at: Date.now(),
      }
      browserTasks.value.push(task)
      recentEvents.value.unshift({
        type: 'browser',
        timestamp: Date.now(),
        data: { ...event },
      })
      // 限制最近事件数量
      if (recentEvents.value.length > 50) {
        recentEvents.value = recentEvents.value.slice(0, 50)
      }
    }
  }

  /**
   * 处理定时任务事件
   * WorkbenchView 的 onChunk 收到 task_event 时调用
   */
  const handleTaskEvent = (event: TaskStreamEvent) => {
    // 更新定时任务状态
    const existing = scheduledTasks.value.find(t => t.id === event.task_id)
    if (existing) {
      existing.status = event.status as ScheduledTaskInfo['status']
      if (event.result) existing.last_result = event.result
      if (event.error) existing.last_error = event.error
      if (event.status === 'running') {
        existing.last_run_time = event.timestamp
      }
    } else {
      // 新任务事件（可能是主 Agent 刚创建的）
      scheduledTasks.value.push({
        id: event.task_id,
        name: event.task_name,
        description: '',
        task_type: event.task_type,
        status: event.status as ScheduledTaskInfo['status'],
        next_run_time: null,
        last_run_time: event.status === 'running' ? event.timestamp : null,
        last_result: event.result || null,
        last_error: event.error || null,
        payload: event.payload || {},
        source: 'main_agent',
        created_at: event.timestamp,
      })
    }

    recentEvents.value.unshift({
      type: 'scheduled',
      timestamp: Date.now(),
      data: { ...event },
    })
    if (recentEvents.value.length > 50) {
      recentEvents.value = recentEvents.value.slice(0, 50)
    }
  }

  /**
   * 标记浏览器标签页已打开
   * BrowserView 打开标签页后调用
   */
  const markBrowserTabOpened = (tabId: string) => {
    const task = browserTasks.value.find(t => t.tab_id === tabId)
    if (task) {
      task.status = 'opened'
    }
  }

  /**
   * 从后端拉取定时任务列表
   */
  const fetchScheduledTasks = async () => {
    try {
      const tasks = await apiGet<ScheduledTaskInfo[]>('/scheduler/tasks')
      scheduledTasks.value = tasks
    } catch (error) {
      console.warn('[TaskStreamStore] Failed to fetch scheduled tasks:', error)
    }
  }

  /**
   * 删除定时任务
   */
  const removeScheduledTask = async (taskId: string) => {
    try {
      await apiDelete(`/scheduler/tasks/${taskId}`)
      scheduledTasks.value = scheduledTasks.value.filter(t => t.id !== taskId)
    } catch (error) {
      console.warn('[TaskStreamStore] Failed to remove task:', error)
    }
  }

  /**
   * 清空已完成的浏览器任务
   */
  const clearOpenedBrowserTasks = () => {
    browserTasks.value = browserTasks.value.filter(t => t.status === 'pending')
  }

  /**
   * 标记目标页有待处理跳转（显示侧边栏红点提示）
   * 由 useTaskNavigation 在防打断策略拦截时调用
   */
  const markPendingNavigation = (target: 'browser' | 'workflow') => {
    pendingNavigation.value = { ...pendingNavigation.value, [target]: true }
  }

  /**
   * 清除目标页的待处理跳转提示（用户手动点击导航项时调用）
   */
  const clearPendingNavigation = (target: 'browser' | 'workflow') => {
    pendingNavigation.value = { ...pendingNavigation.value, [target]: false }
  }

  return {
    browserTasks,
    scheduledTasks,
    recentEvents,
    pendingNavigation,
    browserTaskCount,
    pendingBrowserTasks,
    scheduledTaskCount,
    activeScheduledTasks,
    handleSubagentEvent,
    handleTaskEvent,
    markBrowserTabOpened,
    fetchScheduledTasks,
    removeScheduledTask,
    clearOpenedBrowserTasks,
    markPendingNavigation,
    clearPendingNavigation,
  }
})
