﻿﻿﻿﻿<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import {
  Plus,
  Search,
  Bell,
  Share2,
  Link,
  Filter,
  MoreHorizontal,
  CheckCircle2,
  Circle,
  Clock,
  Calendar,
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  Trash2,
  Edit3,
  Image,
  Lock,
  Type,
  Palette,
  Mic,
  CheckSquare,
  Square,
  X,
  CalendarDays,
  CalendarRange,
  Tag,
  Flag,
  Timer,
  Save,
  RotateCcw
} from 'lucide-vue-next'

type TaskStatus = 'done' | 'progress' | 'pending'
type TaskPriority = 'high' | 'medium' | 'low'
type ViewMode = 'card' | 'week' | 'month'

interface LuomiNestTask {
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

const STORAGE_KEY = 'luominest-tasks-state'

const WEEKDAY_NAMES = ['日', '一', '二', '三', '四', '五', '六']
const WEEKDAY_FULL = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const currentView = ref<ViewMode>('card')

const today = new Date()
const viewDate = ref(new Date(today.getFullYear(), today.getMonth(), today.getDate()))

const monthSlideDir = ref<'up' | 'down'>('up')
const isMonthTransitioning = ref(false)

const nextTaskId = ref(6)

const DEFAULT_TASKS: LuomiNestTask[] = [
  {
    id: 1,
    title: '完成 Agent 对话模块设计',
    desc: '根据 SRS 文档实现沉浸式陪伴域的对话界面',
    priority: 'high',
    status: 'done',
    dueDate: '2026-04-08',
    assignees: ['https://picsum.photos/id/1001/40/40', 'https://picsum.photos/id/1002/40/40'],
    tags: ['UI/UX', '核心功能'],
    progress: 100,
    colorVar: '--task-yellow',
    timeSlot: '10:15 - 12:15'
  },
  {
    id: 2,
    title: '浏览器内核集成',
    desc: '将 ima 风格浏览器视图嵌入桌面客户端',
    priority: 'high',
    status: 'progress',
    dueDate: '2026-04-09',
    assignees: ['https://picsum.photos/id/1003/40/40'],
    tags: ['嵌入式', 'Electron'],
    progress: 65,
    colorVar: '--task-blue',
    timeSlot: '13:00 - 14:30'
  },
  {
    id: 3,
    title: 'MCP 工具网关开发',
    desc: '实现标准化工具接入协议',
    priority: 'medium',
    status: 'pending',
    dueDate: '2026-04-12',
    assignees: ['https://picsum.photos/id/1004/40/40', 'https://picsum.photos/id/1005/40/40', 'https://picsum.photos/id/1006/40/40'],
    tags: ['后端', '协议'],
    progress: 0,
    colorVar: '--task-purple',
    timeSlot: '10:45 - 14:15'
  },
  {
    id: 4,
    title: '三层记忆架构实现',
    desc: '工作记忆 + 情景记忆 + 语义记忆',
    priority: 'medium',
    status: 'pending',
    dueDate: '2026-04-15',
    assignees: ['https://picsum.photos/id/1007/40/40'],
    tags: ['AI', '架构'],
    progress: 0,
    colorVar: '--task-pink',
    timeSlot: '全天'
  },
  {
    id: 5,
    title: 'Live2D 皮套渲染',
    desc: 'Cubism 5 引擎集成与嘴型同步',
    priority: 'low',
    status: 'pending',
    dueDate: '2026-04-20',
    assignees: ['https://picsum.photos/id/1008/40/40', 'https://picsum.photos/id/1009/40/40'],
    tags: ['渲染', '动画'],
    progress: 0,
    colorVar: '--task-green',
    timeSlot: '待安排'
  }
]

const tasks = ref<LuomiNestTask[]>([...DEFAULT_TASKS])

const normalizeTask = (raw: any, fallbackId: number): LuomiNestTask => ({
  id: typeof raw.id === 'number' ? raw.id : fallbackId,
  title: typeof raw.title === 'string' ? raw.title : '',
  desc: typeof raw.desc === 'string' ? raw.desc : '',
  priority: ['high', 'medium', 'low'].includes(raw.priority) ? raw.priority : 'medium',
  status: ['done', 'progress', 'pending'].includes(raw.status) ? raw.status : 'pending',
  dueDate: typeof raw.dueDate === 'string' ? raw.dueDate : formatDateStr(new Date()),
  assignees: Array.isArray(raw.assignees) ? raw.assignees.filter((a: any) => typeof a === 'string') : [],
  tags: Array.isArray(raw.tags) ? raw.tags.filter((t: any) => typeof t === 'string') : [],
  progress: typeof raw.progress === 'number' ? Math.max(0, Math.min(100, raw.progress)) : 0,
  colorVar: typeof raw.colorVar === 'string' ? raw.colorVar : '--task-blue',
  timeSlot: typeof raw.timeSlot === 'string' ? raw.timeSlot : '待安排',
})

const normalizeTasks = (rawList: any[]): LuomiNestTask[] => {
  if (!Array.isArray(rawList)) return [...DEFAULT_TASKS]
  const result: LuomiNestTask[] = []
  for (let i = 0; i < rawList.length; i++) {
    const item = rawList[i]
    if (typeof item !== 'object' || item === null) continue
    try {
      result.push(normalizeTask(item, i + 1))
    } catch {
      continue
    }
  }
  return result.length > 0 ? result : [...DEFAULT_TASKS]
}

const loadPersistedData = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const data = JSON.parse(raw)
      if (data.tasks && Array.isArray(data.tasks)) {
        tasks.value = normalizeTasks(data.tasks)
      }
      if (data.nextId && typeof data.nextId === 'number') {
        nextTaskId.value = data.nextId
      }
      if (data.viewDate && typeof data.viewDate === 'string') {
        const parts = String(data.viewDate).split('-')
        if (parts.length === 3) {
          const y = Number(parts[0])
          const m = Number(parts[1]) - 1
          const d = Number(parts[2])
          const parsed = new Date(y, m, d)
          if (!isNaN(parsed.getTime())) {
            viewDate.value = parsed
          }
        }
      }
      if (data.currentView && ['card', 'week', 'month'].includes(data.currentView)) {
        currentView.value = data.currentView
      }
    }
  } catch {
    // use default data
  }
}

const savePersistedData = () => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      tasks: tasks.value,
      nextId: nextTaskId.value,
      viewDate: formatDateStr(viewDate.value),
      currentView: currentView.value
    }))
  } catch {
    // silently fail
  }
}

watch(tasks, savePersistedData, { deep: true })
watch(viewDate, savePersistedData)
watch(currentView, savePersistedData)

onMounted(loadPersistedData)

const subTasks = ref([
  { label: '需求分析', done: true },
  { label: '原型设计', done: true },
  { label: 'UI 设计', done: true },
  { label: '前端开发', done: false },
  { label: '联调测试', done: false }
])

const completedSubTasks = computed(() => subTasks.value.filter(t => t.done).length)

const teamMembers = ref([
  'https://picsum.photos/id/1001/40/40',
  'https://picsum.photos/id/1002/40/40',
  'https://picsum.photos/id/1003/40/40',
  'https://picsum.photos/id/1004/40/40'
])

const colors = ref([
  { varName: '--task-pink', active: true },
  { varName: '--task-yellow', active: false },
  { varName: '--task-blue', active: false },
  { varName: '--task-purple', active: false },
  { varName: '--task-green', active: false }
])

const timeSlots = ref(['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00'])

const showCreateModal = ref(false)
const showEditModal = ref(false)
const editingTask = ref<LuomiNestTask | null>(null)
const searchQuery = ref('')
const newTagInput = ref('')

const formatDateStr = (d: Date) => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const cloneDate = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate())

const cardDays = computed(() => {
  const days = []
  for (let i = 0; i < 4; i++) {
    const d = cloneDate(viewDate.value)
    d.setDate(d.getDate() + i)
    const isToday = formatDateStr(d) === formatDateStr(new Date())
    days.push({
      date: d.getDate(),
      month: d.getMonth() + 1,
      year: d.getFullYear(),
      weekday: WEEKDAY_NAMES[d.getDay()],
      weekdayFull: WEEKDAY_FULL[d.getDay()],
      fullDate: formatDateStr(d),
      isToday,
      isWeekend: d.getDay() === 0 || d.getDay() === 6
    })
  }
  return days
})

const weekDays = computed(() => {
  const d = cloneDate(viewDate.value)
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(d.getFullYear(), d.getMonth(), diff)

  const days = []
  for (let i = 0; i < 7; i++) {
    const dd = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i)
    const isToday = formatDateStr(dd) === formatDateStr(new Date())
    days.push({
      date: dd.getDate(),
      month: dd.getMonth() + 1,
      year: dd.getFullYear(),
      weekday: WEEKDAY_NAMES[dd.getDay()],
      weekdayFull: WEEKDAY_FULL[dd.getDay()],
      fullDate: formatDateStr(dd),
      isToday,
      isWeekend: dd.getDay() === 0 || dd.getDay() === 6
    })
  }
  return days
})

const monthGrid = computed(() => {
  const year = viewDate.value.getFullYear()
  const month = viewDate.value.getMonth()
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  const startDayOfWeek = (firstDay.getDay() + 6) % 7
  const daysInMonth = lastDay.getDate()
  const prevMonthLastDay = new Date(year, month, 0).getDate()

  const cells = []

  for (let i = startDayOfWeek - 1; i >= 0; i--) {
    const d = prevMonthLastDay - i
    const prevMonth = month === 0 ? 12 : month
    const prevYear = month === 0 ? year - 1 : year
    cells.push({
      date: d,
      month: prevMonth,
      year: prevYear,
      fullDate: `${prevYear}-${String(prevMonth).padStart(2, '0')}-${String(d).padStart(2, '0')}`,
      isCurrentMonth: false,
      isToday: false,
      isWeekend: false
    })
  }

  for (let d = 1; d <= daysInMonth; d++) {
    const dateObj = new Date(year, month, d)
    const isToday = formatDateStr(dateObj) === formatDateStr(new Date())
    cells.push({
      date: d,
      month: month + 1,
      year,
      fullDate: formatDateStr(dateObj),
      isCurrentMonth: true,
      isToday,
      isWeekend: dateObj.getDay() === 0 || dateObj.getDay() === 6
    })
  }

  const remaining = 42 - cells.length
  for (let d = 1; d <= remaining; d++) {
    const nextMonth = month + 2 > 12 ? 1 : month + 2
    const nextYear = month + 2 > 12 ? year + 1 : year
    cells.push({
      date: d,
      month: nextMonth,
      year: nextYear,
      fullDate: `${nextYear}-${String(nextMonth).padStart(2, '0')}-${String(d).padStart(2, '0')}`,
      isCurrentMonth: false,
      isToday: false,
      isWeekend: false
    })
  }

  return {
    cells,
    year,
    month,
    monthLabel: `${year}年 ${month + 1}月`
  }
})

const monthKey = computed(() => `${viewDate.value.getFullYear()}-${viewDate.value.getMonth()}`)

const currentNavLabel = computed(() => {
  if (currentView.value === 'card') {
    const first = cardDays.value[0]
    const last = cardDays.value[3]
    if (first.month === last.month) {
      return `${first.year}年${first.month}月 ${first.date}日 - ${last.date}日`
    }
    if (first.year === last.year) {
      return `${first.year}年${first.month}月${first.date}日 - ${last.month}月${last.date}日`
    }
    return `${first.year}年${first.month}月${first.date}日 - ${last.year}年${last.month}月${last.date}日`
  }
  if (currentView.value === 'week') {
    const first = weekDays.value[0]
    const last = weekDays.value[6]
    if (first.month === last.month) {
      return `${first.year}年${first.month}月 ${first.date}日 - ${last.date}日`
    }
    if (first.year === last.year) {
      return `${first.year}年${first.month}月${first.date}日 - ${last.month}月${last.date}日`
    }
    return `${first.year}年${first.month}月${first.date}日 - ${last.year}年${last.month}月${last.date}日`
  }
  return `${viewDate.value.getFullYear()}年 ${viewDate.value.getMonth() + 1}月`
})

const statusLabel = (s: string) => {
  const map: Record<string, string> = { done: '已完成', progress: '进行中', pending: '待处理' }
  return map[s] || s
}

const priorityLabel = (p: string) => {
  const map: Record<string, string> = { high: '高', medium: '中', low: '低' }
  return map[p] || p
}

const getTasksForDate = (fullDate: string) => {
  return filteredTasks.value.filter(t => t.dueDate === fullDate)
}

const getTaskTopPosition = (task: LuomiNestTask) => {
  if (task.timeSlot === '全天' || task.timeSlot === '待安排') return '0px'
  const startHour = parseInt(task.timeSlot.split(':')[0], 10)
  const firstHour = 8
  const cellHeight = 38
  const offset = (startHour - firstHour) * cellHeight
  return `${offset}px`
}

const filteredTasks = computed(() => {
  if (!searchQuery.value.trim()) return tasks.value
  const q = searchQuery.value.toLowerCase()
  return tasks.value.filter(t =>
    t.title.toLowerCase().includes(q) ||
    t.desc.toLowerCase().includes(q) ||
    t.tags.some(tag => tag.toLowerCase().includes(q))
  )
})

const MIN_YEAR = 2000
const MAX_YEAR = 2099

const clampViewDate = (d: Date) => {
  const y = d.getFullYear()
  if (y < MIN_YEAR) return new Date(MIN_YEAR, 0, 1)
  if (y > MAX_YEAR) return new Date(MAX_YEAR, 11, 31)
  return d
}

const navigatePrev = () => {
  if (currentView.value === 'card') {
    const d = cloneDate(viewDate.value)
    d.setDate(d.getDate() - 4)
    viewDate.value = clampViewDate(d)
  } else if (currentView.value === 'week') {
    const d = cloneDate(viewDate.value)
    d.setDate(d.getDate() - 7)
    viewDate.value = clampViewDate(d)
  } else {
    const y = viewDate.value.getFullYear()
    const m = viewDate.value.getMonth()
    viewDate.value = clampViewDate(new Date(y, m - 1, 1))
  }
}

const navigateNext = () => {
  if (currentView.value === 'card') {
    const d = cloneDate(viewDate.value)
    d.setDate(d.getDate() + 4)
    viewDate.value = clampViewDate(d)
  } else if (currentView.value === 'week') {
    const d = cloneDate(viewDate.value)
    d.setDate(d.getDate() + 7)
    viewDate.value = clampViewDate(d)
  } else {
    const y = viewDate.value.getFullYear()
    const m = viewDate.value.getMonth()
    viewDate.value = clampViewDate(new Date(y, m + 1, 1))
  }
}

const goToToday = () => {
  const now = new Date()
  viewDate.value = new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

const onMonthWheel = (e: WheelEvent) => {
  if (isMonthTransitioning.value) return
  isMonthTransitioning.value = true

  if (e.deltaY > 0) {
    monthSlideDir.value = 'up'
    navigateNext()
  } else if (e.deltaY < 0) {
    monthSlideDir.value = 'down'
    navigatePrev()
  }

  setTimeout(() => {
    isMonthTransitioning.value = false
  }, 320)
}

const defaultNewTask = () => ({
  title: '',
  desc: '',
  priority: 'medium' as TaskPriority,
  status: 'pending' as TaskStatus,
  dueDate: formatDateStr(viewDate.value),
  assignees: [] as string[],
  tags: [] as string[],
  progress: 0,
  colorVar: '--task-blue',
  timeSlot: '09:00 - 10:00'
})

const newTask = ref(defaultNewTask())

const openCreateModal = (prefillDate?: string, prefillTimeSlot?: string) => {
  newTask.value = defaultNewTask()
  if (prefillDate) {
    newTask.value.dueDate = prefillDate
  }
  if (prefillTimeSlot) {
    newTask.value.timeSlot = prefillTimeSlot
  }
  newTagInput.value = ''
  showCreateModal.value = true
}

const closeCreateModal = () => {
  showCreateModal.value = false
  newTask.value = defaultNewTask()
  newTagInput.value = ''
}

const addNewTag = () => {
  const tag = newTagInput.value.trim()
  if (tag && !newTask.value.tags.includes(tag)) {
    newTask.value.tags.push(tag)
  }
  newTagInput.value = ''
}

const removeNewTag = (tag: string) => {
  newTask.value.tags = newTask.value.tags.filter(t => t !== tag)
}

const createTask = () => {
  if (!newTask.value.title.trim()) return
  if (!timeSlotOptions.includes(newTask.value.timeSlot)) {
    newTask.value.timeSlot = '待安排'
  }
  tasks.value.push({
    id: nextTaskId.value++,
    ...newTask.value
  })
  closeCreateModal()
}

const openEditModal = (task: LuomiNestTask) => {
  editingTask.value = {
    ...task,
    tags: [...task.tags],
    assignees: [...task.assignees],
  }
  newTagInput.value = ''
  showEditModal.value = true
}

const closeEditModal = () => {
  showEditModal.value = false
  editingTask.value = null
}

const addEditTag = () => {
  if (!editingTask.value) return
  const tag = newTagInput.value.trim()
  if (tag && !editingTask.value.tags.includes(tag)) {
    editingTask.value.tags.push(tag)
  }
  newTagInput.value = ''
}

const removeEditTag = (tag: string) => {
  if (!editingTask.value) return
  editingTask.value.tags = editingTask.value.tags.filter(t => t !== tag)
}

const saveEditTask = () => {
  if (!editingTask.value || !editingTask.value.title.trim()) return
  if (!timeSlotOptions.includes(editingTask.value.timeSlot)) {
    editingTask.value.timeSlot = '待安排'
  }
  const idx = tasks.value.findIndex(t => t.id === editingTask.value!.id)
  if (idx !== -1) {
    tasks.value[idx] = { ...editingTask.value }
  }
  closeEditModal()
}

const deleteTask = (taskId: number) => {
  tasks.value = tasks.value.filter(t => t.id !== taskId)
}

const toggleTaskStatus = (task: LuomiNestTask) => {
  const idx = tasks.value.findIndex(t => t.id === task.id)
  if (idx === -1) return
  const statusCycle: TaskStatus[] = ['pending', 'progress', 'done']
  const currentIdx = statusCycle.indexOf(tasks.value[idx].status)
  const nextStatus = statusCycle[(currentIdx + 1) % statusCycle.length]
  tasks.value[idx].status = nextStatus
  if (nextStatus === 'done') {
    tasks.value[idx].progress = 100
  } else if (nextStatus === 'pending') {
    tasks.value[idx].progress = 0
  }
}

const colorOptions = [
  { varName: '--task-pink', label: '粉色' },
  { varName: '--task-yellow', label: '黄色' },
  { varName: '--task-blue', label: '蓝色' },
  { varName: '--task-purple', label: '紫色' },
  { varName: '--task-green', label: '绿色' }
]

const priorityOptions: { value: TaskPriority; label: string }[] = [
  { value: 'high', label: '高优先级' },
  { value: 'medium', label: '中优先级' },
  { value: 'low', label: '低优先级' }
]

const statusOptions: { value: TaskStatus; label: string }[] = [
  { value: 'pending', label: '待处理' },
  { value: 'progress', label: '进行中' },
  { value: 'done', label: '已完成' }
]

const timeSlotOptions = [
  '08:00 - 09:00',
  '09:00 - 10:00',
  '10:00 - 11:00',
  '11:00 - 12:00',
  '12:00 - 13:00',
  '13:00 - 14:00',
  '14:00 - 15:00',
  '15:00 - 16:00',
  '16:00 - 17:00',
  '17:00 - 18:00',
  '全天',
  '待安排'
]
</script>

<template>
  <div class="tasks-view">
    <header class="tasks-header animate-fade-in">
      <div class="header-left">
        <div class="project-indicator">
          <div class="indicator-dot"></div>
          <h1 class="page-title">LuomiNest 任务中心</h1>
        </div>
        <div class="team-avatars">
          <img v-for="(member, i) in teamMembers" :key="i" :src="member" class="avatar" alt="member" />
          <button class="avatar avatar-add">
            <Plus :size="12" />
          </button>
        </div>
        <span class="project-path">AI Agent / 前端 / 核心模块</span>
      </div>

      <div class="header-right">
        <div class="search-box">
          <Search :size="14" class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索任务..." />
          <Mic :size="14" class="mic-icon" />
        </div>
        <button class="icon-btn">
          <Bell :size="16" />
          <span class="notification-dot"></span>
        </button>
        <button class="icon-btn luomi-create-btn" @click="openCreateModal()">
          <Plus :size="16" />
        </button>
        <button class="action-btn">
          <Share2 :size="14" />
          分享
        </button>
        <button class="action-btn">
          <Link :size="14" />
          链接
        </button>
      </div>
    </header>

    <div class="toolbar animate-slide-up">
      <div class="view-switcher">
        <button
          v-for="view in (['card', 'week', 'month'] as ViewMode[])"
          :key="view"
          :class="['view-btn', { active: currentView === view }]"
          @click="currentView = view"
        >
          <LayoutGrid v-if="view === 'card'" :size="14" />
          <CalendarRange v-if="view === 'week'" :size="14" />
          <CalendarDays v-if="view === 'month'" :size="14" />
          {{ view === 'card' ? '卡片' : view === 'week' ? '周视图' : '月视图' }}
          <span v-if="view === 'card'" class="view-indicator"></span>
        </button>
      </div>

      <div class="toolbar-center">
        <div class="date-nav">
          <button @click="navigatePrev"><ChevronLeft :size="14" /></button>
          <span class="current-date" @click="goToToday" style="cursor: pointer">
            {{ currentNavLabel }}
          </span>
          <button @click="navigateNext"><ChevronRight :size="14" /></button>
        </div>
        <button class="today-btn" @click="goToToday">
          <Clock :size="12" />
          今天
        </button>
        <div class="last-update">
          <Clock :size="12" />
          30 分钟前
          <img src="https://picsum.photos/id/1010/30/30" class="update-avatar" alt="user" />
          <span>Sarah</span>
        </div>
      </div>
    </div>

    <!-- 卡片视图 -->
    <div v-if="currentView === 'card'" class="calendar-section animate-slide-up" style="animation-delay: 70ms">
      <div class="calendar-header-row">
        <div class="time-label-col">
          <span class="time-label-header"></span>
        </div>
        <div
          v-for="(day, idx) in cardDays"
          :key="idx"
          class="calendar-day-header"
          :class="{ 'is-today': day.isToday }"
        >
          <div class="date-number">{{ String(day.date).padStart(2, '0') }}</div>
          <div class="date-weekday">/{{ day.weekday }}</div>
        </div>
      </div>

      <div class="calendar-body">
        <div class="time-axis">
          <div v-for="(slot, idx) in timeSlots.slice(2, 7)" :key="idx" class="time-slot-label">
            {{ slot }}
          </div>
        </div>

        <div class="calendar-columns">
          <div
            v-for="(day, dayIdx) in cardDays"
            :key="dayIdx"
            class="calendar-column"
            :class="{ 'has-tasks': getTasksForDate(day.fullDate).length > 0 }"
          >
            <div class="column-tasks">
              <div
                v-for="task in getTasksForDate(day.fullDate)"
                :key="task.id"
                class="calendar-task-card"
                :class="[`status-${task.status}`]"
                :style="{ '--card-accent': `var(${task.colorVar})` }"
              >
                <div class="card-accent-bar"></div>

                <div class="card-top-row">
                  <div class="card-tags">
                    <span :class="['card-priority', task.priority]">{{ priorityLabel(task.priority) }}</span>
                    <span v-for="tag in task.tags" :key="tag" class="card-tag">{{ tag }}</span>
                  </div>
                  <button class="card-menu"><MoreHorizontal :size="13" /></button>
                </div>

                <h3 class="card-title">{{ task.title }}</h3>
                <p class="card-time">{{ task.timeSlot }}</p>

                <div v-if="task.status === 'progress'" class="progress-mini">
                  <div class="progress-bar-mini">
                    <div class="progress-fill-mini" :style="{ width: `${task.progress}%` }"></div>
                  </div>
                  <span class="progress-text">{{ task.progress }}%</span>
                </div>

                <div v-if="task.id === 1" class="subtask-list">
                  <ul>
                    <li v-for="sub in subTasks" :key="sub.label" :class="{ done: sub.done }">
                      <CheckSquare v-if="sub.done" :size="11" />
                      <Square v-else :size="11" />
                      {{ sub.label }}
                    </li>
                  </ul>
                </div>

                <div v-if="task.status === 'done'" class="completion-info">
                  <span>完成度 {{ completedSubTasks }}/{{ subTasks.length }}</span>
                  <div class="completion-bar">
                    <div class="completion-fill" :style="{ width: `${(completedSubTasks / subTasks.length) * 100}%` }"></div>
                  </div>
                </div>

                <div class="card-bottom">
                  <div class="bottom-left">
                    <span v-if="task.status !== 'done'" class="due-date">
                      <Calendar :size="11" /> {{ task.dueDate }}
                    </span>
                    <span :class="['status-badge', task.status]">
                      {{ statusLabel(task.status) }}
                    </span>
                  </div>
                  <div class="assignees-stack">
                    <img
                      v-for="(a, ai) in task.assignees.slice(0, 3)"
                      :key="ai"
                      :src="a"
                      class="assignee-avatar"
                      :style="{ zIndex: task.assignees.length - ai }"
                      alt=""
                    />
                  </div>
                </div>

                <div class="card-actions">
                  <button class="action-chip" title="编辑" @click.stop="openEditModal(task)"><Edit3 :size="11" /></button>
                  <button class="action-chip danger" title="删除" @click.stop="deleteTask(task.id)"><Trash2 :size="11" /></button>
                </div>
              </div>

              <div v-if="getTasksForDate(day.fullDate).length === 0" class="add-task-placeholder" @click="openCreateModal(day.fullDate)">
                <button class="add-task-inner">
                  <div class="add-circle">
                    <Plus :size="18" />
                  </div>
                  <span class="add-text">添加新任务</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 周视图 -->
    <div v-if="currentView === 'week'" class="week-section animate-slide-up" style="animation-delay: 70ms">
      <div class="week-header-row">
        <div class="week-time-gutter"></div>
        <div
          v-for="day in weekDays"
          :key="day.fullDate"
          class="week-day-header"
          :class="{ 'is-today': day.isToday, 'is-weekend': day.isWeekend }"
        >
          <div class="week-day-weekday">{{ day.weekdayFull }}</div>
          <div class="week-day-date" :class="{ 'today-dot': day.isToday }">{{ day.date }}</div>
          <div class="week-day-count" v-if="getTasksForDate(day.fullDate).length > 0">
            {{ getTasksForDate(day.fullDate).length }} 项
          </div>
        </div>
      </div>

      <div class="week-body">
        <div class="week-time-gutter">
          <div v-for="slot in timeSlots" :key="slot" class="week-time-label">
            {{ slot }}
          </div>
        </div>

        <div class="week-columns">
          <div
            v-for="day in weekDays"
            :key="day.fullDate"
            class="week-column"
            :class="{ 'is-today': day.isToday, 'is-weekend': day.isWeekend }"
          >
            <div
              v-for="slot in timeSlots.slice(0, -1)"
              :key="slot"
              class="week-cell"
              tabindex="0"
              role="button"
              @click="openCreateModal(day.fullDate, `${slot} - ${timeSlots[timeSlots.indexOf(slot) + 1]}`)"
              @keydown.enter="openCreateModal(day.fullDate, `${slot} - ${timeSlots[timeSlots.indexOf(slot) + 1]}`)"
              @keydown.space.prevent="openCreateModal(day.fullDate, `${slot} - ${timeSlots[timeSlots.indexOf(slot) + 1]}`)"
            >
              <div class="week-cell-time">{{ slot }}</div>
            </div>

            <div class="week-task-overlay">
              <div
                v-for="task in getTasksForDate(day.fullDate)"
                :key="task.id"
                class="week-task-item"
                :class="[`status-${task.status}`]"
                :style="{ '--card-accent': `var(${task.colorVar})`, top: getTaskTopPosition(task) }"
                @click.stop="openEditModal(task)"
              >
                <div class="week-task-accent"></div>
                <div class="week-task-content">
                  <span class="week-task-title">{{ task.title }}</span>
                  <span class="week-task-time">{{ task.timeSlot }}</span>
                </div>
                <div class="week-task-actions">
                  <button class="week-task-action" @click.stop="toggleTaskStatus(task)">
                    <CheckCircle2 v-if="task.status === 'done'" :size="10" />
                    <Circle v-else :size="10" />
                  </button>
                  <button class="week-task-action danger" @click.stop="deleteTask(task.id)">
                    <Trash2 :size="10" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 月视图 -->
    <div v-if="currentView === 'month'" class="month-section animate-slide-up" style="animation-delay: 70ms" @wheel.prevent="onMonthWheel">
      <div class="month-weekday-row">
        <div v-for="name in ['一', '二', '三', '四', '五', '六', '日']" :key="name" class="month-weekday-cell">
          {{ name }}
        </div>
      </div>

      <Transition :name="`month-slide-${monthSlideDir}`" mode="out-in">
        <div class="month-grid" :key="monthKey">
          <div
            v-for="cell in monthGrid.cells"
            :key="cell.fullDate"
            class="month-cell"
            :class="{
              'is-current': cell.isCurrentMonth,
              'is-today': cell.isToday,
              'is-weekend': cell.isWeekend,
              'is-other-month': !cell.isCurrentMonth
            }"
            tabindex="0"
            role="button"
            @click="openCreateModal(cell.fullDate)"
            @keydown.enter="openCreateModal(cell.fullDate)"
            @keydown.space.prevent="openCreateModal(cell.fullDate)"
          >
            <div class="month-cell-header">
              <span class="month-cell-date">{{ cell.date }}</span>
              <span v-if="getTasksForDate(cell.fullDate).length > 0" class="month-cell-count">
                {{ getTasksForDate(cell.fullDate).length }}
              </span>
            </div>

            <div class="month-cell-tasks">
              <div
                v-for="task in getTasksForDate(cell.fullDate).slice(0, 3)"
                :key="task.id"
                class="month-task-item"
                :style="{ '--card-accent': `var(${task.colorVar})` }"
                :class="[`status-${task.status}`]"
                @click.stop="openEditModal(task)"
              >
                <div class="month-task-dot"></div>
                <span class="month-task-title">{{ task.title }}</span>
              </div>
              <div
                v-if="getTasksForDate(cell.fullDate).length > 3"
                class="month-task-more"
              >
                +{{ getTasksForDate(cell.fullDate).length - 3 }} 更多
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </div>

    <!-- 统计概览 -->
    <div class="stats-overview animate-slide-up" style="animation-delay: 140ms">
      <div class="stat-pill" style="--pill-color: var(--task-blue)">
        <div class="pill-icon"><Clock :size="16" /></div>
        <div class="pill-content">
          <strong>{{ tasks.filter(t => t.status === 'progress').length }}</strong>
          <span>进行中</span>
        </div>
        <div class="pill-trend positive">&#8599;</div>
      </div>
      <div class="stat-pill" style="--pill-color: var(--task-green)">
        <div class="pill-icon"><CheckCircle2 :size="16" /></div>
        <div class="pill-content">
          <strong>{{ tasks.filter(t => t.status === 'done').length }}</strong>
          <span>已完成</span>
        </div>
        <div class="pill-trend positive">&#8599;</div>
      </div>
      <div class="stat-pill" style="--pill-color: var(--task-yellow)">
        <div class="pill-icon"><Circle :size="16" /></div>
        <div class="pill-content">
          <strong>{{ tasks.filter(t => t.status === 'pending').length }}</strong>
          <span>待处理</span>
        </div>
        <div class="pill-trend neutral">&#8212;</div>
      </div>
      <div class="insight-pill">
        <div class="insight-head">
          <span>团队效率</span>
          <span class="insight-growth">&#8599; +19.24%</span>
        </div>
        <div class="insight-grid">
          <div class="insight-cell">
            <small>Time Spent</small>
            <strong>9h <em>76%</em></strong>
          </div>
          <div class="insight-cell">
            <small>Tasks</small>
            <strong>{{ tasks.length }} <em>68%</em></strong>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部工具栏 -->
    <div class="bottom-toolbar animate-slide-up" style="animation-delay: 210ms">
      <div class="toolbar-left">
        <button class="filter-btn">
          <Filter :size="14" />
          筛选
        </button>
        <div class="color-filters">
          <span class="filter-label">颜色:</span>
          <button
            v-for="(color, idx) in colors"
            :key="idx"
            class="color-dot"
            :class="{ active: color.active }"
            :style="{ background: `var(${color.varName})` }"
          ></button>
          <button class="color-dot add-color">
            <Plus :size="10" />
          </button>
        </div>
      </div>

      <div class="toolbar-right">
        <button class="tool-btn"><Edit3 :size="14" /></button>
        <button class="tool-btn"><Lock :size="14" /></button>
        <button class="tool-btn"><Type :size="14" /></button>
        <button class="tool-btn"><Palette :size="14" /></button>
        <button class="tool-btn text-tool-btn" @click="openCreateModal()">
          <Image :size="14" />
          新建任务
        </button>
        <button class="tool-btn delete-tool-btn">
          <Trash2 :size="14" />
          回收站
          <span class="delete-count">{{ tasks.filter(t => t.status === 'done').length }}</span>
        </button>
      </div>
    </div>

    <!-- 创建任务弹窗 -->
    <Teleport to="body">
      <Transition name="luomi-modal">
        <div v-if="showCreateModal" class="luomi-modal-overlay" @click.self="closeCreateModal">
          <div class="luomi-modal">
            <div class="luomi-modal-header">
              <h2 class="luomi-modal-title">
                <Plus :size="18" />
                创建新任务
              </h2>
              <button class="luomi-modal-close" @click="closeCreateModal">
                <X :size="18" />
              </button>
            </div>

            <div class="luomi-modal-body">
              <div class="luomi-form-group">
                <label class="luomi-form-label">
                  <Type :size="13" />
                  任务标题
                </label>
                <input
                  v-model="newTask.title"
                  class="luomi-form-input"
                  placeholder="输入任务标题..."
                  @keydown.enter="createTask"
                />
              </div>

              <div class="luomi-form-group">
                <label class="luomi-form-label">
                  <Edit3 :size="13" />
                  任务描述
                </label>
                <textarea
                  v-model="newTask.desc"
                  class="luomi-form-textarea"
                  placeholder="描述任务详情..."
                  rows="3"
                ></textarea>
              </div>

              <div class="luomi-form-row">
                <div class="luomi-form-group luomi-form-half">
                  <label class="luomi-form-label">
                    <Flag :size="13" />
                    优先级
                  </label>
                  <div class="luomi-form-select-group">
                    <button
                      v-for="opt in priorityOptions"
                      :key="opt.value"
                      :class="['luomi-select-chip', `priority-${opt.value}`, { active: newTask.priority === opt.value }]"
                      @click="newTask.priority = opt.value"
                    >
                      {{ opt.label }}
                    </button>
                  </div>
                </div>

                <div class="luomi-form-group luomi-form-half">
                  <label class="luomi-form-label">
                    <Circle :size="13" />
                    状态
                  </label>
                  <div class="luomi-form-select-group">
                    <button
                      v-for="opt in statusOptions"
                      :key="opt.value"
                      :class="['luomi-select-chip', `status-${opt.value}`, { active: newTask.status === opt.value }]"
                      @click="newTask.status = opt.value"
                    >
                      {{ opt.label }}
                    </button>
                  </div>
                </div>
              </div>

              <div class="luomi-form-row">
                <div class="luomi-form-group luomi-form-half">
                  <label class="luomi-form-label">
                    <Calendar :size="13" />
                    截止日期
                  </label>
                  <input
                    v-model="newTask.dueDate"
                    class="luomi-form-input"
                    type="date"
                  />
                </div>

                <div class="luomi-form-group luomi-form-half">
                  <label class="luomi-form-label">
                    <Timer :size="13" />
                    时间段
                  </label>
                  <select v-model="newTask.timeSlot" class="luomi-form-select">
                    <option v-for="slot in timeSlotOptions" :key="slot" :value="slot">{{ slot }}</option>
                  </select>
                </div>
              </div>

              <div class="luomi-form-group">
                <label class="luomi-form-label">
                  <Palette :size="13" />
                  任务颜色
                </label>
                <div class="luomi-color-picker">
                  <button
                    v-for="color in colorOptions"
                    :key="color.varName"
                    :class="['luomi-color-option', { active: newTask.colorVar === color.varName }]"
                    :style="{ background: `var(${color.varName})` }"
                    @click="newTask.colorVar = color.varName"
                  >
                    <CheckCircle2 v-if="newTask.colorVar === color.varName" :size="14" />
                  </button>
                </div>
              </div>

              <div class="luomi-form-group">
                <label class="luomi-form-label">
                  <Tag :size="13" />
                  标签
                </label>
                <div class="luomi-tags-input">
                  <span v-for="tag in newTask.tags" :key="tag" class="luomi-tag-item">
                    {{ tag }}
                    <button @click="removeNewTag(tag)"><X :size="10" /></button>
                  </span>
                  <input
                    v-model="newTagInput"
                    class="luomi-tag-input"
                    placeholder="添加标签..."
                    @keydown.enter.prevent="addNewTag"
                  />
                </div>
              </div>

              <div v-if="newTask.status === 'progress'" class="luomi-form-group">
                <label class="luomi-form-label">
                  进度: {{ newTask.progress }}%
                </label>
                <input
                  v-model.number="newTask.progress"
                  class="luomi-form-range"
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                />
              </div>
            </div>

            <div class="luomi-modal-footer">
              <button class="luomi-btn luomi-btn-ghost" @click="closeCreateModal">
                <RotateCcw :size="14" />
                取消
              </button>
              <button class="luomi-btn luomi-btn-primary" @click="createTask" :disabled="!newTask.title.trim()">
                <Save :size="14" />
                创建任务
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 编辑任务弹窗 -->
    <Teleport to="body">
      <Transition name="luomi-modal">
        <div v-if="showEditModal && editingTask" class="luomi-modal-overlay" @click.self="closeEditModal">
          <div class="luomi-modal">
            <div class="luomi-modal-header">
              <h2 class="luomi-modal-title">
                <Edit3 :size="18" />
                编辑任务
              </h2>
              <button class="luomi-modal-close" @click="closeEditModal">
                <X :size="18" />
              </button>
            </div>

            <div class="luomi-modal-body">
              <div class="luomi-form-group">
                <label class="luomi-form-label">
                  <Type :size="13" />
                  任务标题
                </label>
                <input
                  v-model="editingTask.title"
                  class="luomi-form-input"
                  placeholder="输入任务标题..."
                />
              </div>

              <div class="luomi-form-group">
                <label class="luomi-form-label">
                  <Edit3 :size="13" />
                  任务描述
                </label>
                <textarea
                  v-model="editingTask.desc"
                  class="luomi-form-textarea"
                  placeholder="描述任务详情..."
                  rows="3"
                ></textarea>
              </div>

              <div class="luomi-form-row">
                <div class="luomi-form-group luomi-form-half">
                  <label class="luomi-form-label">
                    <Flag :size="13" />
                    优先级
                  </label>
                  <div class="luomi-form-select-group">
                    <button
                      v-for="opt in priorityOptions"
                      :key="opt.value"
                      :class="['luomi-select-chip', `priority-${opt.value}`, { active: editingTask.priority === opt.value }]"
                      @click="editingTask.priority = opt.value"
                    >
                      {{ opt.label }}
                    </button>
                  </div>
                </div>

                <div class="luomi-form-group luomi-form-half">
                  <label class="luomi-form-label">
                    <Circle :size="13" />
                    状态
                  </label>
                  <div class="luomi-form-select-group">
                    <button
                      v-for="opt in statusOptions"
                      :key="opt.value"
                      :class="['luomi-select-chip', `status-${opt.value}`, { active: editingTask.status === opt.value }]"
                      @click="editingTask.status = opt.value"
                    >
                      {{ opt.label }}
                    </button>
                  </div>
                </div>
              </div>

              <div class="luomi-form-row">
                <div class="luomi-form-group luomi-form-half">
                  <label class="luomi-form-label">
                    <Calendar :size="13" />
                    截止日期
                  </label>
                  <input
                    v-model="editingTask.dueDate"
                    class="luomi-form-input"
                    type="date"
                  />
                </div>

                <div class="luomi-form-group luomi-form-half">
                  <label class="luomi-form-label">
                    <Timer :size="13" />
                    时间段
                  </label>
                  <select v-model="editingTask.timeSlot" class="luomi-form-select">
                    <option v-for="slot in timeSlotOptions" :key="slot" :value="slot">{{ slot }}</option>
                  </select>
                </div>
              </div>

              <div class="luomi-form-group">
                <label class="luomi-form-label">
                  <Palette :size="13" />
                  任务颜色
                </label>
                <div class="luomi-color-picker">
                  <button
                    v-for="color in colorOptions"
                    :key="color.varName"
                    :class="['luomi-color-option', { active: editingTask.colorVar === color.varName }]"
                    :style="{ background: `var(${color.varName})` }"
                    @click="editingTask.colorVar = color.varName"
                  >
                    <CheckCircle2 v-if="editingTask.colorVar === color.varName" :size="14" />
                  </button>
                </div>
              </div>

              <div class="luomi-form-group">
                <label class="luomi-form-label">
                  <Tag :size="13" />
                  标签
                </label>
                <div class="luomi-tags-input">
                  <span v-for="tag in editingTask.tags" :key="tag" class="luomi-tag-item">
                    {{ tag }}
                    <button @click="removeEditTag(tag)"><X :size="10" /></button>
                  </span>
                  <input
                    v-model="newTagInput"
                    class="luomi-tag-input"
                    placeholder="添加标签..."
                    @keydown.enter.prevent="addEditTag"
                  />
                </div>
              </div>

              <div v-if="editingTask.status === 'progress'" class="luomi-form-group">
                <label class="luomi-form-label">
                  进度: {{ editingTask.progress }}%
                </label>
                <input
                  v-model.number="editingTask.progress"
                  class="luomi-form-range"
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                />
              </div>
            </div>

            <div class="luomi-modal-footer">
              <button class="luomi-btn luomi-btn-ghost" @click="closeEditModal">
                取消
              </button>
              <button class="luomi-btn luomi-btn-danger" @click="deleteTask(editingTask.id); closeEditModal()">
                <Trash2 :size="14" />
                删除
              </button>
              <button class="luomi-btn luomi-btn-primary" @click="saveEditTask" :disabled="!editingTask.title.trim()">
                <Save :size="14" />
                保存
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.tasks-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow-y: auto;
  padding: 20px 28px;
  color: var(--text-primary);
}

.tasks-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--workspace-border);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.project-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.indicator-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--lumi-primary), var(--lumi-primary-soft));
  box-shadow: 0 0 8px var(--lumi-primary-glow);
}

.page-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.2px;
}

.team-avatars {
  display: flex;
  align-items: center;
}

.avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 2px solid var(--workspace-bg);
  margin-left: -7px;
  object-fit: cover;
}

.avatar:first-child {
  margin-left: 0;
}

.avatar-add {
  background: var(--workspace-card);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  border: 1px solid var(--workspace-border);
}

.avatar-add:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.project-path {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: 2px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-box {
  position: relative;
}

.search-box input {
  width: 200px;
  padding: 7px 30px 7px 32px;
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-primary);
  font-size: 12px;
  outline: none;
  transition: all var(--transition-fast);
}

.search-box input:focus {
  border-color: var(--lumi-primary-light);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.search-box input::placeholder {
  color: var(--text-muted);
}

.search-icon {
  position: absolute;
  left: 10px;
  color: var(--text-muted);
}

.mic-icon {
  position: absolute;
  right: 8px;
  color: var(--text-muted);
  cursor: pointer;
}

.icon-btn {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
}

.icon-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.luomi-create-btn {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
  color: var(--text-inverse);
}

.luomi-create-btn:hover {
  background: var(--lumi-primary-hover);
  color: var(--text-inverse);
}

.notification-dot {
  position: absolute;
  top: 7px;
  right: 7px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--lumi-accent);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.action-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.view-switcher {
  display: flex;
  gap: 3px;
  padding: 3px;
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--workspace-border);
}

.view-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.view-btn:hover {
  color: var(--text-secondary);
  background: var(--surface-ghost);
}

.view-btn.active {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.view-indicator {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--task-yellow);
}

.toolbar-center {
  display: flex;
  align-items: center;
  gap: 16px;
}

.date-nav {
  display: flex;
  align-items: center;
  gap: 10px;
}

.date-nav button {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.date-nav button:hover {
  background: var(--workspace-card);
  color: var(--text-primary);
}

.current-date {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

.today-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.today-btn:hover {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
  color: var(--text-inverse);
}

.last-update {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--text-muted);
}

.update-avatar {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  object-fit: cover;
}

.calendar-section {
  margin-bottom: 18px;
}

.calendar-header-row {
  display: grid;
  grid-template-columns: 48px repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 12px;
  padding: 0 4px;
}

.time-label-col {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding-bottom: 8px;
}

.calendar-day-header {
  text-align: center;
  padding: 12px 0 8px;
}

.calendar-day-header.is-today .date-number {
  color: var(--lumi-primary);
}

.date-number {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.date-weekday {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.calendar-body {
  display: grid;
  grid-template-columns: 48px repeat(4, 1fr);
  gap: 12px;
  min-height: 320px;
}

.time-axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 8px 0;
}

.time-slot-label {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
  line-height: 1;
  padding: 4px 0;
}

.calendar-columns {
  display: contents;
}

.calendar-column {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0;
}

.column-tasks {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
}

.calendar-task-card {
  position: relative;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  padding: 14px 16px;
  transition: all var(--transition-normal);
  overflow: hidden;
}

.calendar-task-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
  border-color: var(--surface-ghost-hover);
}

.calendar-task-card:hover .card-actions {
  opacity: 1;
}

.card-accent-bar {
  position: absolute;
  top: 0;
  left: 16px;
  right: 16px;
  height: 3px;
  border-radius: 0 0 3px 3px;
  background: var(--card-accent);
  opacity: 0.85;
}

.card-top-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 10px;
  margin-top: 4px;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.card-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 5px;
  background: var(--task-purple-soft);
  color: var(--task-purple);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.card-priority {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 5px;
  letter-spacing: 0.3px;
}

.card-priority.high {
  background: var(--task-red-soft);
  color: var(--task-red);
}

.card-priority.medium {
  background: var(--task-yellow-soft);
  color: var(--task-yellow);
}

.card-priority.low {
  background: var(--task-green-soft);
  color: var(--task-green);
}

.card-menu {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.card-menu:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
  line-height: 1.35;
}

.card-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.progress-mini {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.progress-bar-mini {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: var(--workspace-panel);
  overflow: hidden;
}

.progress-fill-mini {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--card-accent), var(--progress-shimmer));
  transition: width 0.5s ease-in-out;
}

.progress-text {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
}

.subtask-list {
  margin-bottom: 10px;
  padding: 10px;
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
}

.subtask-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.subtask-list li {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.subtask-list li.done {
  color: var(--text-muted);
  text-decoration: line-through;
}

.subtask-list li svg {
  color: var(--card-accent);
  flex-shrink: 0;
}

.subtask-list li.done svg {
  color: var(--task-green);
}

.completion-info {
  margin-bottom: 10px;
}

.completion-info > span {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.completion-bar {
  height: 4px;
  border-radius: 2px;
  background: var(--workspace-panel);
  overflow: hidden;
}

.completion-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--card-accent);
  transition: width 0.5s ease-in-out;
}

.card-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 10px;
  border-top: 1px solid var(--workspace-border);
}

.bottom-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.due-date {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  color: var(--text-muted);
}

.status-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 5px;
  letter-spacing: 0.3px;
}

.status-badge.done {
  background: var(--task-green-soft);
  color: var(--task-green);
}

.status-badge.progress {
  background: var(--task-blue-soft);
  color: var(--task-blue);
}

.status-badge.pending {
  background: var(--task-yellow-soft);
  color: var(--task-yellow);
}

.assignees-stack {
  display: flex;
  align-items: center;
}

.assignee-avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid var(--workspace-card);
  margin-left: -7px;
  object-fit: cover;
}

.assignee-avatar:first-child {
  margin-left: 0;
}

.card-actions {
  position: absolute;
  top: 12px;
  right: 38px;
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.action-chip {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--workspace-hover);
  border: 1px solid var(--workspace-border);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.action-chip:hover {
  background: var(--surface-ghost-hover);
  color: var(--text-primary);
}

.action-chip.danger:hover {
  background: var(--task-red-soft);
  color: var(--task-red);
}

.calendar-task-card.status-done {
  opacity: 0.85;
}

.calendar-task-card.status-done .card-title {
  text-decoration: line-through;
  color: var(--text-muted);
}

.add-task-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed var(--workspace-border);
  border-radius: var(--radius-lg);
  min-height: 160px;
  transition: all var(--transition-normal);
  cursor: pointer;
}

.add-task-placeholder:hover {
  border-color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.add-task-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
}

.add-circle {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--lumi-primary), var(--lumi-primary-soft));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-inverse);
  box-shadow: var(--shadow-glow-sm);
  transition: all var(--transition-fast);
}

.add-task-inner:hover .add-circle {
  transform: scale(1.06);
  box-shadow: var(--shadow-glow-md);
}

.add-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.week-section {
  margin-bottom: 18px;
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  overflow: hidden;
}

.week-header-row {
  display: grid;
  grid-template-columns: 52px repeat(7, 1fr);
  border-bottom: 1px solid var(--workspace-border);
}

.week-time-gutter {
  background: var(--workspace-bg);
  border-right: 1px solid var(--workspace-border);
}

.week-day-header {
  padding: 12px 8px;
  text-align: center;
  border-right: 1px solid var(--workspace-border);
  transition: background var(--transition-fast);
}

.week-day-header:last-child {
  border-right: none;
}

.week-day-header.is-today {
  background: var(--lumi-primary-light);
}

.week-day-header.is-weekend {
  background: var(--surface-ghost);
}

.week-day-weekday {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
}

.week-day-date {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.week-day-date.today-dot {
  color: var(--lumi-primary);
}

.week-day-count {
  font-size: 10px;
  color: var(--lumi-primary);
  font-weight: 600;
  margin-top: 2px;
}

.week-body {
  display: grid;
  grid-template-columns: 52px repeat(7, 1fr);
  max-height: 420px;
  overflow-y: auto;
}

.week-body > .week-time-gutter {
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--workspace-border);
}

.week-time-label {
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: var(--text-muted);
  font-weight: 500;
  border-bottom: 1px solid var(--workspace-border);
}

.week-columns {
  display: contents;
}

.week-column {
  position: relative;
  border-right: 1px solid var(--workspace-border);
}

.week-column:last-child {
  border-right: none;
}

.week-column.is-today {
  background: var(--lumi-primary-light);
}

.week-column.is-weekend {
  background: var(--surface-ghost);
}

.week-cell {
  height: 38px;
  border-bottom: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: background var(--transition-fast);
  position: relative;
}

.week-cell:hover {
  background: var(--workspace-hover);
}

.week-cell-time {
  display: none;
}

.week-task-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 2;
  padding: 4px 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  pointer-events: none;
}

.week-task-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 6px;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  pointer-events: auto;
  transition: all var(--transition-fast);
  position: relative;
  overflow: hidden;
}

.week-task-item:hover {
  transform: translateX(2px);
  box-shadow: var(--shadow-sm);
}

.week-task-item.status-done {
  opacity: 0.6;
}

.week-task-item.status-done .week-task-title {
  text-decoration: line-through;
}

.week-task-accent {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--card-accent);
}

.week-task-content {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding-left: 4px;
  flex: 1;
  min-width: 0;
}

.week-task-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.week-task-time {
  font-size: 9px;
  color: var(--text-muted);
}

.week-task-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.week-task-item:hover .week-task-actions {
  opacity: 1;
}

.week-task-action {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.week-task-action:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.week-task-action.danger:hover {
  background: var(--task-red-soft);
  color: var(--task-red);
}

.month-section {
  margin-bottom: 18px;
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  overflow: hidden;
}

.month-weekday-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  border-bottom: 1px solid var(--workspace-border);
}

.month-weekday-cell {
  padding: 10px 8px;
  text-align: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  border-right: 1px solid var(--workspace-border);
}

.month-weekday-cell:last-child {
  border-right: none;
}

.month-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
}

.month-cell {
  min-height: 100px;
  padding: 8px;
  border-right: 1px solid var(--workspace-border);
  border-bottom: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.month-cell:nth-child(7n) {
  border-right: none;
}

.month-cell:hover {
  background: var(--workspace-hover);
}

.month-cell.is-today {
  background: var(--lumi-primary-light);
}

.month-cell.is-weekend {
  background: var(--surface-ghost);
}

.month-cell.is-other-month {
  opacity: 0.4;
}

.month-cell-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.month-cell-date {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.month-cell.is-today .month-cell-date {
  background: var(--lumi-primary);
  color: var(--text-inverse);
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

.month-cell-count {
  font-size: 10px;
  font-weight: 600;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  padding: 1px 6px;
  border-radius: 10px;
}

.month-cell-tasks {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.month-task-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 6px;
  border-radius: 5px;
  background: var(--workspace-bg);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.month-task-item:hover {
  background: var(--workspace-hover);
  transform: translateX(2px);
}

.month-task-item.status-done {
  opacity: 0.5;
}

.month-task-item.status-done .month-task-title {
  text-decoration: line-through;
}

.month-task-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--card-accent);
  flex-shrink: 0;
}

.month-task-title {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.month-task-more {
  font-size: 10px;
  color: var(--lumi-primary);
  font-weight: 500;
  padding: 2px 6px;
  cursor: pointer;
}

.month-task-more:hover {
  text-decoration: underline;
}

.month-slide-up-enter-active,
.month-slide-up-leave-active,
.month-slide-down-enter-active,
.month-slide-down-leave-active {
  transition: all 0.28s ease-in-out;
}

.month-slide-up-enter-from {
  opacity: 0;
  transform: translateY(36px);
}

.month-slide-up-leave-to {
  opacity: 0;
  transform: translateY(-18px);
}

.month-slide-down-enter-from {
  opacity: 0;
  transform: translateY(-36px);
}

.month-slide-down-leave-to {
  opacity: 0;
  transform: translateY(18px);
}

.stats-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 18px;
}

.stat-pill {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-normal);
}

.stat-pill:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.pill-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-ghost);
  color: var(--pill-color);
}

.pill-content {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.pill-content strong {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.pill-content span {
  font-size: 11px;
  color: var(--text-muted);
}

.pill-trend {
  margin-left: auto;
  font-size: 14px;
  font-weight: 700;
}

.pill-trend.positive {
  color: var(--task-green);
}

.pill-trend.neutral {
  color: var(--text-muted);
}

.insight-pill {
  padding: 14px 16px;
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
}

.insight-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.insight-head span:first-child {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.insight-growth {
  font-size: 11px;
  color: var(--task-green);
  font-weight: 600;
}

.insight-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.insight-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.insight-cell small {
  font-size: 10px;
  color: var(--text-muted);
}

.insight-cell strong {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
}

.insight-cell em {
  font-style: normal;
  font-size: 11px;
  color: var(--task-green);
  font-weight: 500;
  margin-left: 4px;
}

.bottom-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid var(--workspace-border);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 12px;
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.filter-btn:hover {
  background: var(--workspace-hover);
}

.color-filters {
  display: flex;
  align-items: center;
  gap: 7px;
}

.filter-label {
  font-size: 11px;
  color: var(--text-muted);
}

.color-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.color-dot.active {
  border-color: var(--text-inverse);
  box-shadow: 0 0 0 2px var(--workspace-bg);
}

.color-dot:hover {
  transform: scale(1.12);
}

.add-color {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 5px;
}

.tool-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tool-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.text-tool-btn,
.delete-tool-btn {
  width: auto;
  padding: 0 10px;
  gap: 5px;
  font-size: 11px;
  font-weight: 500;
}

.delete-count {
  background: var(--task-red-soft);
  color: var(--task-red);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
}

.luomi-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: var(--overlay-backdrop);
  backdrop-filter: var(--glass-blur);
  display: flex;
  align-items: center;
  justify-content: center;
}

.luomi-modal {
  width: 520px;
  max-height: 85vh;
  background: var(--surface);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.luomi-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--workspace-border);
}

.luomi-modal-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.luomi-modal-close {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.luomi-modal-close:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.luomi-modal-body {
  padding: 20px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.luomi-modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 24px;
  border-top: 1px solid var(--workspace-border);
}

.luomi-form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.luomi-form-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.luomi-form-input {
  padding: 9px 12px;
  border-radius: var(--radius-md);
  background: var(--workspace-bg);
  border: 1px solid var(--workspace-border);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: all var(--transition-fast);
  font-family: inherit;
}

.luomi-form-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.luomi-form-input::placeholder {
  color: var(--text-muted);
}

.luomi-form-textarea {
  padding: 9px 12px;
  border-radius: var(--radius-md);
  background: var(--workspace-bg);
  border: 1px solid var(--workspace-border);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: all var(--transition-fast);
  font-family: inherit;
  resize: vertical;
  min-height: 60px;
}

.luomi-form-textarea:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.luomi-form-textarea::placeholder {
  color: var(--text-muted);
}

.luomi-form-select {
  padding: 9px 12px;
  border-radius: var(--radius-md);
  background: var(--workspace-bg);
  border: 1px solid var(--workspace-border);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: all var(--transition-fast);
  font-family: inherit;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394A3B8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;
  padding-right: 30px;
}

.luomi-form-select:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.luomi-form-row {
  display: flex;
  gap: 12px;
}

.luomi-form-half {
  flex: 1;
}

.luomi-form-select-group {
  display: flex;
  gap: 4px;
}

.luomi-select-chip {
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 500;
  border: 1px solid var(--workspace-border);
  background: var(--workspace-bg);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.luomi-select-chip:hover {
  border-color: var(--text-muted);
}

.luomi-select-chip.active.priority-high {
  background: var(--task-red-soft);
  border-color: var(--task-red);
  color: var(--task-red);
}

.luomi-select-chip.active.priority-medium {
  background: var(--task-yellow-soft);
  border-color: var(--task-yellow);
  color: var(--task-yellow);
}

.luomi-select-chip.active.priority-low {
  background: var(--task-green-soft);
  border-color: var(--task-green);
  color: var(--task-green);
}

.luomi-select-chip.active.status-pending {
  background: var(--task-yellow-soft);
  border-color: var(--task-yellow);
  color: var(--task-yellow);
}

.luomi-select-chip.active.status-progress {
  background: var(--task-blue-soft);
  border-color: var(--task-blue);
  color: var(--task-blue);
}

.luomi-select-chip.active.status-done {
  background: var(--task-green-soft);
  border-color: var(--task-green);
  color: var(--task-green);
}

.luomi-color-picker {
  display: flex;
  gap: 8px;
}

.luomi-color-option {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  border: 2px solid transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-fast);
  color: var(--text-inverse);
}

.luomi-color-option:hover {
  transform: scale(1.1);
}

.luomi-color-option.active {
  border-color: var(--text-inverse);
  box-shadow: 0 0 0 2px var(--workspace-bg), var(--shadow-sm);
  transform: scale(1.1);
}

.luomi-tags-input {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  background: var(--workspace-bg);
  border: 1px solid var(--workspace-border);
  min-height: 38px;
  align-items: center;
  transition: all var(--transition-fast);
}

.luomi-tags-input:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.luomi-tag-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 5px;
  background: var(--task-purple-soft);
  color: var(--task-purple);
  font-size: 11px;
  font-weight: 600;
}

.luomi-tag-item button {
  display: flex;
  align-items: center;
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  opacity: 0.6;
  transition: opacity var(--transition-fast);
}

.luomi-tag-item button:hover {
  opacity: 1;
}

.luomi-tag-input {
  flex: 1;
  min-width: 80px;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 12px;
  outline: none;
  font-family: inherit;
}

.luomi-tag-input::placeholder {
  color: var(--text-muted);
}

.luomi-form-range {
  width: 100%;
  height: 4px;
  border-radius: 2px;
  background: var(--workspace-panel);
  outline: none;
  appearance: none;
  cursor: pointer;
}

.luomi-form-range::-webkit-slider-thumb {
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--lumi-primary);
  border: 2px solid var(--surface);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
}

.luomi-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 600;
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-fast);
  font-family: inherit;
}

.luomi-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.luomi-btn-ghost {
  background: var(--workspace-bg);
  color: var(--text-secondary);
}

.luomi-btn-ghost:hover:not(:disabled) {
  background: var(--workspace-hover);
}

.luomi-btn-primary {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
  color: var(--text-inverse);
}

.luomi-btn-primary:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.luomi-btn-danger {
  background: var(--task-red-soft);
  border-color: var(--task-red);
  color: var(--task-red);
}

.luomi-btn-danger:hover:not(:disabled) {
  background: var(--task-red);
  color: var(--text-inverse);
}

.luomi-modal-enter-active {
  transition: all 0.25s ease-in-out;
}

.luomi-modal-leave-active {
  transition: all 0.2s ease-in-out;
}

.luomi-modal-enter-from {
  opacity: 0;
}

.luomi-modal-enter-from .luomi-modal {
  transform: scale(0.95) translateY(10px);
}

.luomi-modal-leave-to {
  opacity: 0;
}

.luomi-modal-leave-to .luomi-modal {
  transform: scale(0.95) translateY(10px);
}

.tasks-view::-webkit-scrollbar {
  width: 5px;
}

.tasks-view::-webkit-scrollbar-track {
  background: transparent;
}

.tasks-view::-webkit-scrollbar-thumb {
  background: var(--workspace-border);
  border-radius: 10px;
}

.tasks-view::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

.week-body::-webkit-scrollbar {
  width: 4px;
}

.week-body::-webkit-scrollbar-track {
  background: transparent;
}

.week-body::-webkit-scrollbar-thumb {
  background: var(--workspace-border);
  border-radius: 10px;
}

.luomi-modal-body::-webkit-scrollbar {
  width: 4px;
}

.luomi-modal-body::-webkit-scrollbar-track {
  background: transparent;
}

.luomi-modal-body::-webkit-scrollbar-thumb {
  background: var(--workspace-border);
  border-radius: 10px;
}
</style>
