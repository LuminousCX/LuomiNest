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

export const WEEKDAY_NAMES = ['日', '一', '二', '三', '四', '五', '六'] as const
export const WEEKDAY_FULL = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'] as const

export const formatDateStr = (d: Date): string => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export const cloneDate = (d: Date): Date => new Date(d.getFullYear(), d.getMonth(), d.getDate())

export const statusLabel = (s: TaskStatus | string): string => {
  const map: Record<string, string> = { done: '已完成', progress: '进行中', pending: '待处理' }
  return map[s] || s
}

export const priorityLabel = (p: TaskPriority | string): string => {
  const map: Record<string, string> = { high: '高', medium: '中', low: '低' }
  return map[p] || p
}

export const getTaskTopPosition = (task: LuomiNestTask, firstHour = 8, cellHeight = 38): string => {
  if (task.timeSlot === '全天' || task.timeSlot === '待安排') return '0px'
  const startHour = parseInt(task.timeSlot.split(':')[0], 10)
  const offset = (startHour - firstHour) * cellHeight
  return `${offset}px`
}
