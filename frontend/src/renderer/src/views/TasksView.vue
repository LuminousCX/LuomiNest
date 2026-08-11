<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { Search, Plus } from 'lucide-vue-next'
import { useTaskStreamStore } from '../stores/taskStream'
import { getItem, setItem } from '../utils/storage'
import type { ViewMode, TaskStatus, LuomiNestTask, CalendarDay, MonthGrid } from '../components/tasks/types'
import {
  WEEKDAY_NAMES,
  WEEKDAY_FULL,
  formatDateStr,
  cloneDate
} from '../components/tasks/types'
import TasksToolbar from '../components/tasks/TasksToolbar.vue'
import TasksCardView from '../components/tasks/TasksCardView.vue'
import TasksWeekView from '../components/tasks/TasksWeekView.vue'
import TasksMonthView from '../components/tasks/TasksMonthView.vue'
import TasksScheduledView from '../components/tasks/TasksScheduledView.vue'
import TasksEditModal from '../components/tasks/TasksEditModal.vue'

const taskStreamStore = useTaskStreamStore()

const STORAGE_KEY = 'luominest-tasks-state'

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
    colorVar: '--task-sky',
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

const normalizeTask = (raw: Record<string, unknown>, fallbackId: number): LuomiNestTask => ({
  id: typeof raw.id === 'number' ? raw.id : fallbackId,
  title: typeof raw.title === 'string' ? raw.title : '',
  desc: typeof raw.desc === 'string' ? raw.desc : '',
  priority: typeof raw.priority === 'string' && ['high', 'medium', 'low'].includes(raw.priority) ? raw.priority as LuomiNestTask['priority'] : 'medium',
  status: typeof raw.status === 'string' && ['done', 'progress', 'pending'].includes(raw.status) ? raw.status as LuomiNestTask['status'] : 'pending',
  dueDate: typeof raw.dueDate === 'string' ? raw.dueDate : formatDateStr(new Date()),
  assignees: Array.isArray(raw.assignees) ? raw.assignees.filter((a: unknown): a is string => typeof a === 'string') : [],
  tags: Array.isArray(raw.tags) ? raw.tags.filter((t: unknown): t is string => typeof t === 'string') : [],
  progress: typeof raw.progress === 'number' ? Math.max(0, Math.min(100, raw.progress)) : 0,
  colorVar: typeof raw.colorVar === 'string' ? raw.colorVar : '--task-blue',
  timeSlot: typeof raw.timeSlot === 'string' ? raw.timeSlot : '待安排',
})

const normalizeTasks = (rawList: unknown[]): LuomiNestTask[] => {
  if (!Array.isArray(rawList)) return [...DEFAULT_TASKS]
  const result: LuomiNestTask[] = []
  for (let i = 0; i < rawList.length; i++) {
    const item = rawList[i]
    if (typeof item !== 'object' || item === null) continue
    try {
      result.push(normalizeTask(item as Record<string, unknown>, i + 1))
    } catch {
      continue
    }
  }
  return result.length > 0 ? result : [...DEFAULT_TASKS]
}

interface PersistedTaskState {
  tasks?: unknown[]
  nextId?: number
  viewDate?: string
  currentView?: ViewMode
}

const loadPersistedData = () => {
  const data = getItem<PersistedTaskState | null>(STORAGE_KEY, null)
  if (!data) return
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
  if (data.currentView && (['card', 'week', 'month'] as ViewMode[]).includes(data.currentView)) {
    currentView.value = data.currentView
  }
}

const savePersistedData = () => {
  setItem(STORAGE_KEY, {
    tasks: tasks.value,
    nextId: nextTaskId.value,
    viewDate: formatDateStr(viewDate.value),
    currentView: currentView.value
  })
}

watch(tasks, savePersistedData, { deep: true })
watch(viewDate, savePersistedData)
watch(currentView, savePersistedData)

onMounted(() => {
  loadPersistedData()
  // 拉取后端定时任务（内存调度器 + 数据库持久化）
  taskStreamStore.fetchScheduledTasks()
  taskStreamStore.fetchDbScheduledTasks()
})

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
  { varName: '--task-sky', active: false },
  { varName: '--task-green', active: false }
])

const timeSlots = ref(['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00'])

const searchQuery = ref('')
const showModal = ref(false)
const editingTask = ref<LuomiNestTask | null>(null)

const defaultNewTask = (): LuomiNestTask => ({
  id: 0,
  title: '',
  desc: '',
  priority: 'medium',
  status: 'pending',
  dueDate: formatDateStr(viewDate.value),
  assignees: [] as string[],
  tags: [] as string[],
  progress: 0,
  colorVar: '--task-blue',
  timeSlot: '09:00 - 10:00'
})

const newTask = ref(defaultNewTask())

const cardDays = computed((): CalendarDay[] => {
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

const weekDays = computed((): CalendarDay[] => {
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

const monthGrid = computed((): MonthGrid => {
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

const filteredTasks = computed(() => {
  if (!searchQuery.value.trim()) return tasks.value
  const q = searchQuery.value.toLowerCase()
  return tasks.value.filter(t =>
    t.title.toLowerCase().includes(q) ||
    t.desc.toLowerCase().includes(q) ||
    t.tags.some(tag => tag.toLowerCase().includes(q))
  )
})

const getTasksForDate = (fullDate: string) => {
  return filteredTasks.value.filter(t => t.dueDate === fullDate)
}

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

const openCreateModal = (prefillDate?: string, prefillTimeSlot?: string) => {
  editingTask.value = null
  newTask.value = defaultNewTask()
  if (prefillDate) {
    newTask.value.dueDate = prefillDate
  }
  if (prefillTimeSlot) {
    newTask.value.timeSlot = prefillTimeSlot
  }
  showModal.value = true
}

const openEditModal = (task: LuomiNestTask) => {
  editingTask.value = {
    ...task,
    tags: [...task.tags],
    assignees: [...task.assignees]
  }
  showModal.value = true
}

const closeModal = () => {
  showModal.value = false
  editingTask.value = null
  newTask.value = defaultNewTask()
}

const handleSaveTask = (task: LuomiNestTask) => {
  if (editingTask.value) {
    const idx = tasks.value.findIndex(t => t.id === task.id)
    if (idx !== -1) {
      tasks.value[idx] = { ...task }
    }
  } else {
    const { id: _, ...taskData } = task
    tasks.value.push({
      id: nextTaskId.value++,
      ...taskData
    })
  }
  closeModal()
}

const deleteTask = (taskId: number) => {
  tasks.value = tasks.value.filter(t => t.id !== taskId)
}

const toggleTaskStatus = (task: LuomiNestTask) => {
  const idx = tasks.value.findIndex(t => t.id === task.id)
  if (idx === -1) return
  const statusCycle: Array<TaskStatus> = ['pending', 'progress', 'done']
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
  { varName: '--task-sky', label: '天蓝' },
  { varName: '--task-green', label: '绿色' }
]

const priorityOptions: { value: 'high' | 'medium' | 'low'; label: string }[] = [
  { value: 'high', label: '高优先级' },
  { value: 'medium', label: '中优先级' },
  { value: 'low', label: '低优先级' }
]

const statusOptions: { value: 'done' | 'progress' | 'pending'; label: string }[] = [
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
  <div class="tasks-view custom-scrollbar">
    <div class="tasks-page-header animate-fade-in">
      <div class="tasks-page-header__left">
        <h1 class="tasks-page-title">计划视图</h1>
        <p class="tasks-page-desc">项目管理、任务跟踪与团队协作</p>
        <div class="tasks-page-avatars">
          <img v-for="(member, i) in teamMembers" :key="i" :src="member" class="tasks-avatar" alt="member" />
          <button class="tasks-avatar tasks-avatar-add">
            <Plus :size="12" />
          </button>
        </div>
      </div>
      <div class="tasks-page-header__right">
        <div class="tasks-search-box">
          <Search :size="14" class="tasks-search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索任务..." />
        </div>
        <button class="tasks-create-btn" @click="() => openCreateModal()">
          <Plus :size="16" />
          <span>新建任务</span>
        </button>
      </div>
    </div>

    <TasksToolbar
      v-model:currentView="currentView"
      :currentNavLabel="currentNavLabel"
      :tasks="tasks"
      :teamMembers="teamMembers"
      :colors="colors"
      :activeScheduledCount="taskStreamStore.activeScheduledTasks.length + taskStreamStore.dbScheduledTaskCount"
      @navigatePrev="navigatePrev"
      @navigateNext="navigateNext"
      @goToday="goToToday"
      @openCreate="openCreateModal"
    >
      <TasksCardView
        v-if="currentView === 'card'"
        :cardDays="cardDays"
        :timeSlots="timeSlots"
        :tasksForDate="getTasksForDate"
        :subTasks="subTasks"
        :completedSubTasks="completedSubTasks"
        @createTask="openCreateModal"
        @editTask="openEditModal"
        @deleteTask="deleteTask"
      />

      <TasksWeekView
        v-if="currentView === 'week'"
        :weekDays="weekDays"
        :timeSlots="timeSlots"
        :tasksForDate="getTasksForDate"
        @createTask="openCreateModal"
        @editTask="openEditModal"
        @toggleStatus="toggleTaskStatus"
        @deleteTask="deleteTask"
      />

      <TasksMonthView
        v-if="currentView === 'month'"
        :monthGrid="monthGrid"
        :monthKey="monthKey"
        :monthSlideDir="monthSlideDir"
        :tasksForDate="getTasksForDate"
        @createTask="openCreateModal"
        @editTask="openEditModal"
        @wheel="onMonthWheel"
      />

      <TasksScheduledView
        v-if="currentView === 'scheduled'"
        :scheduledTasks="taskStreamStore.scheduledTasks"
        :dbScheduledTasks="taskStreamStore.dbScheduledTasks"
        @refresh="taskStreamStore.fetchScheduledTasks"
        @delete="taskStreamStore.removeScheduledTask"
        @create-db-task="taskStreamStore.createDbScheduledTask"
        @delete-db-task="taskStreamStore.removeDbScheduledTask"
        @refresh-db="taskStreamStore.fetchDbScheduledTasks"
      />
    </TasksToolbar>

    <TasksEditModal
      v-model:visible="showModal"
      :mode="editingTask ? 'edit' : 'create'"
      :initialTask="editingTask || newTask"
      :priorityOptions="priorityOptions"
      :statusOptions="statusOptions"
      :timeSlotOptions="timeSlotOptions"
      :colorOptions="colorOptions"
      @save="handleSaveTask"
      @delete="deleteTask"
    />
  </div>
</template>

<style scoped>
.tasks-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow-y: auto;
  padding: var(--space-5) 28px;
  color: var(--text-primary);
}

.tasks-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--divider-soft, var(--workspace-border));
}

.tasks-page-header__left {
  display: flex;
  flex-direction: column;
}

.tasks-page-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  line-height: 1.2;
}

.tasks-page-desc {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.tasks-page-avatars {
  display: flex;
  align-items: center;
  margin-top: var(--space-3);
}

.tasks-avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  border: 2px solid var(--workspace-bg);
  margin-left: -6px;
  object-fit: cover;
}

.tasks-avatar:first-child {
  margin-left: 0;
}

.tasks-avatar-add {
  background: var(--workspace-card);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  cursor: pointer;
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-fast);
}

.tasks-avatar-add:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.tasks-page-header__right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.tasks-search-box {
  position: relative;
}

.tasks-search-box input {
  width: 200px;
  padding: 7px 12px 7px var(--space-7);
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-primary);
  font-size: var(--text-sm);
  outline: none;
  transition: all var(--transition-fast);
}

.tasks-search-box input:focus {
  border-color: var(--lumi-brand-light);
  box-shadow: 0 0 0 3px var(--lumi-brand-glow);
}

.tasks-search-box input::placeholder {
  color: var(--text-muted);
}

.tasks-search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
}

.tasks-create-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 7px 16px;
  border-radius: var(--radius-md);
  background: var(--lumi-brand);
  color: var(--text-inverse);
  border: none;
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tasks-create-btn:hover {
  background: var(--lumi-brand-hover);
  box-shadow: var(--shadow-sm);
}

</style>
