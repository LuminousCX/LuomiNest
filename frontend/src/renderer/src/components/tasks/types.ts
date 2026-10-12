import { i18n } from '../../i18n'

export type TaskStatus = 'done' | 'progress' | 'pending'
export type TaskPriority = 'high' | 'medium' | 'low'
export type ViewMode = 'card' | 'week' | 'month' | 'scheduled'

export interface LuomiNestTask {
  id: number
  title: string
  desc: string
  priority: TaskPriority
  status: TaskStatus
  dueDate: string
  assignees: string[]
  tags: string[]
  progress: number
  colorVar: string
  timeSlot: string
}

export interface CalendarDay {
  date: number
  month: number
  year: number
  weekday: string
  weekdayFull: string
  fullDate: string
  isToday: boolean
  isWeekend: boolean
}

export interface MonthDay {
  date: number
  month: number
  year: number
  fullDate: string
  isToday: boolean
  isWeekend: boolean
  isCurrentMonth: boolean
}

export interface MonthGrid {
  cells: MonthDay[]
  year: number
  month: number
  monthLabel: string
}

/** 24h 时间轴上按固定小时触发的任务（由定时任务视图解析 cron / next_run_time 生成） */
export interface TimelineTaskEntry {
  id: string
  name: string
  /** 触发小时 0-23 */
  hour: number
  /** 触发分钟 0-59（tooltip 展示用） */
  minute: number
  /** 本地化的时刻描述，如"每天 09:30"/"下次: 10-12 08:00" */
  summary: string
}

/** 无法定位到固定小时的任务（interval / once / 无下次执行时间），在时间轴下方列出 */
export interface TimelineUnplacedTask {
  id: string
  name: string
  note: string
  dim?: boolean
}

// 星期文案随界面语言：短形用于卡片日期头，完整形用于周视图表头（tasks.wds*/tasks.wd*）
export const weekdayShort = (day: number): string => i18n.global.t(`tasks.wds${day}`)
export const weekdayFull = (day: number): string => i18n.global.t(`tasks.wd${day}`)

// 时间段特殊值是持久化数据协议（历史数据已存中文哨兵值），展示时经 i18n 映射
export const ALL_DAY_SLOT = '全天'
export const UNPLANNED_SLOT = '待安排'

/** 时间段展示文案：全天/待安排哨兵值映射为本地化文案，普通时段原样返回 */
export const timeSlotLabel = (slot: string): string => {
  if (slot === ALL_DAY_SLOT) return i18n.global.t('tasks.timeSlot.allDay')
  if (slot === UNPLANNED_SLOT) return i18n.global.t('tasks.timeSlot.unplanned')
  return slot
}

export const formatDateStr = (d: Date): string => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export const cloneDate = (d: Date): Date => new Date(d.getFullYear(), d.getMonth(), d.getDate())

export const statusLabel = (s: TaskStatus | string): string => {
  const keys: Record<string, string> = { done: 'tasks.status.done', progress: 'tasks.status.progress', pending: 'tasks.status.pending' }
  return keys[s] ? i18n.global.t(keys[s]) : s
}

export const priorityLabel = (p: TaskPriority | string): string => {
  const keys: Record<string, string> = { high: 'tasks.priority.high', medium: 'tasks.priority.medium', low: 'tasks.priority.low' }
  return keys[p] ? i18n.global.t(keys[p]) : p
}

export const getTaskTopPosition = (task: LuomiNestTask, firstHour = 0, cellHeight = 38): string => {
  if (task.timeSlot === ALL_DAY_SLOT || task.timeSlot === UNPLANNED_SLOT) return '0px'
  const startHour = parseInt(task.timeSlot.split(':')[0], 10)
  const offset = (startHour - firstHour) * cellHeight
  return `${offset}px`
}
