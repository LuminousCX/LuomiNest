<script setup lang="ts">
import { computed } from 'vue'
import {
  Plus,
  Search,
  Bell,
  Share2,
  Link,
  Filter,
  Clock,
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  CalendarDays,
  CalendarRange,
  Timer,
  Edit3,
  Lock,
  Type,
  Palette,
  Image,
  Trash2,
  Mic,
  CheckCircle2,
  Circle
} from 'lucide-vue-next'
import type { ViewMode, LuomiNestTask } from './types'

const props = defineProps<{
  currentView: ViewMode
  searchQuery: string
  currentNavLabel: string
  tasks: LuomiNestTask[]
  teamMembers: string[]
  colors: { varName: string; active: boolean }[]
  activeScheduledCount: number
}>()

const emit = defineEmits<{
  'update:currentView': [view: ViewMode]
  'update:searchQuery': [query: string]
  navigatePrev: []
  navigateNext: []
  goToday: []
  openCreate: []
}>()

const currentViewModel = computed<ViewMode>({
  get: () => props.currentView,
  set: (value) => emit('update:currentView', value)
})

const searchQueryModel = computed<string>({
  get: () => props.searchQuery,
  set: (value) => emit('update:searchQuery', value)
})

const viewList: { value: ViewMode; label: string; icon: typeof LayoutGrid }[] = [
  { value: 'card', label: '卡片', icon: LayoutGrid },
  { value: 'week', label: '周视图', icon: CalendarRange },
  { value: 'month', label: '月视图', icon: CalendarDays },
  { value: 'scheduled', label: '定时任务', icon: Timer }
]

const showIndicator = (view: ViewMode) => {
  if (view === 'card') return true
  if (view === 'scheduled' && props.activeScheduledCount > 0) return true
  return false
}
</script>

<template>
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
        <input v-model="searchQueryModel" type="text" placeholder="搜索任务..." />
        <Mic :size="14" class="mic-icon" />
      </div>
      <button class="icon-btn">
        <Bell :size="16" />
        <span class="notification-dot"></span>
      </button>
      <button class="icon-btn luomi-create-btn" @click="emit('openCreate')">
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
        v-for="view in viewList"
        :key="view.value"
        :class="['view-btn', { active: currentView === view.value }]"
        @click="currentViewModel = view.value"
      >
        <component :is="view.icon" :size="14" />
        {{ view.label }}
        <span v-if="showIndicator(view.value)" class="view-indicator"></span>
      </button>
    </div>

    <div class="toolbar-center">
      <div class="date-nav">
        <button @click="emit('navigatePrev')"><ChevronLeft :size="14" /></button>
        <span class="current-date" @click="emit('goToday')" style="cursor: pointer">
          {{ currentNavLabel }}
        </span>
        <button @click="emit('navigateNext')"><ChevronRight :size="14" /></button>
      </div>
      <button class="today-btn" @click="emit('goToday')">
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

  <slot />

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
      <button class="tool-btn text-tool-btn" @click="emit('openCreate')">
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
</template>

<style scoped>
.tasks-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-5);
  padding-bottom: var(--space-4);
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
  gap: var(--space-2);
}

.indicator-dot {
  width: 9px;
  height: 9px;
  border-radius: var(--radius-full);
  background: linear-gradient(135deg, var(--lumi-brand), var(--lumi-brand-soft));
  box-shadow: 0 0 var(--space-2) var(--lumi-brand-glow);
}

.page-title {
  font-size: var(--text-2xl);
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
  border-radius: var(--radius-full);
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
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-left: 2px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.search-box {
  position: relative;
}

.search-box input {
  width: 200px;
  padding: 7px 30px 7px var(--space-7);
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-primary);
  font-size: var(--text-sm);
  outline: none;
  transition: all var(--transition-fast);
}

.search-box input:focus {
  border-color: var(--lumi-brand-light);
  box-shadow: 0 0 0 3px var(--lumi-brand-glow);
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
  right: var(--space-2);
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
  background: var(--lumi-brand);
  border-color: var(--lumi-brand);
  color: var(--text-inverse);
}

.luomi-create-btn:hover {
  background: var(--lumi-brand-hover);
  color: var(--text-inverse);
}

.notification-dot {
  position: absolute;
  top: 7px;
  right: 7px;
  width: 5px;
  height: 5px;
  border-radius: var(--radius-full);
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
  font-size: var(--text-sm);
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
  padding: 6px var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
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
  border-radius: var(--radius-full);
  background: var(--task-yellow);
}

.toolbar-center {
  display: flex;
  align-items: center;
  gap: var(--space-4);
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
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

.today-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: 5px 10px;
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.today-btn:hover {
  background: var(--lumi-brand);
  border-color: var(--lumi-brand);
  color: var(--text-inverse);
}

.last-update {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.update-avatar {
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  object-fit: cover;
}

.stats-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
  margin-bottom: 18px;
}

.stat-pill {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px var(--space-4);
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
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.pill-content span {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.pill-trend {
  margin-left: auto;
  font-size: var(--text-md);
  font-weight: 700;
}

.pill-trend.positive {
  color: var(--task-green);
}

.pill-trend.neutral {
  color: var(--text-muted);
}

.insight-pill {
  padding: 14px var(--space-4);
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
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.insight-growth {
  font-size: var(--text-xs);
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
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.insight-cell strong {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
}

.insight-cell em {
  font-style: normal;
  font-size: var(--text-xs);
  color: var(--task-green);
  font-weight: 500;
  margin-left: var(--space-1);
}

.bottom-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: var(--space-4);
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
  padding: 7px var(--space-3);
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-secondary);
  font-size: var(--text-sm);
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
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.color-dot {
  width: var(--space-5);
  height: var(--space-5);
  border-radius: var(--radius-full);
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
  width: var(--space-7);
  height: var(--space-7);
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
  font-size: var(--text-xs);
  font-weight: 500;
}

.delete-count {
  background: var(--task-red-soft);
  color: var(--task-red);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: var(--text-2xs);
  font-weight: 600;
}
</style>
