<script setup lang="ts">
import { computed } from 'vue'
import {
  Plus,
  Filter,
  Clock,
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  CalendarDays,
  CalendarRange,
  Timer,
  Trash2,
  CheckCircle2,
  Circle
} from 'lucide-vue-next'
import type { ViewMode, LuomiNestTask } from './types'

const props = defineProps<{
  currentView: ViewMode
  currentNavLabel: string
  tasks: LuomiNestTask[]
  teamMembers: string[]
  colors: { varName: string; active: boolean }[]
  activeScheduledCount: number
}>()

const emit = defineEmits<{
  'update:currentView': [view: ViewMode]
  navigatePrev: []
  navigateNext: []
  goToday: []
  openCreate: []
}>()

const currentViewModel = computed<ViewMode>({
  get: () => props.currentView,
  set: (value) => emit('update:currentView', value)
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
  <div class="tasks-toolbar animate-slide-up">
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

  <div class="tasks-bottom-bar animate-slide-up" style="animation-delay: 210ms">
    <div class="bottom-bar-left">
      <button class="filter-btn">
        <Filter :size="14" />
        筛选
      </button>
      <div class="color-filters">
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
    <div class="bottom-bar-right">
      <button class="trash-btn" @click="emit('openCreate')">
        <Trash2 :size="14" />
        <span>回收站</span>
        <span v-if="tasks.filter(t => t.status === 'done').length > 0" class="trash-count">
          {{ tasks.filter(t => t.status === 'done').length }}
        </span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.tasks-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.view-switcher {
  display: flex;
  gap: 2px;
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
  border-radius: var(--radius-md);
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
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  font-weight: 600;
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
  gap: var(--space-3);
}

.date-nav {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.date-nav button {
  width: 28px;
  height: 28px;
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
  padding: 5px 12px;
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

.tasks-bottom-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: var(--space-4);
  border-top: 1px solid var(--workspace-border);
}

.bottom-bar-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px var(--space-3);
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
  gap: 6px;
}

.color-dot {
  width: var(--space-4);
  height: var(--space-4);
  border-radius: var(--radius-full);
  border: 2px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.color-dot.active {
  border-color: var(--text-primary);
  box-shadow: 0 0 0 2px var(--workspace-bg);
}

.color-dot:hover {
  transform: scale(1.15);
}

.add-color {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
}

.bottom-bar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.trash-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px var(--space-3);
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-muted);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.trash-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.trash-count {
  background: var(--task-red-soft);
  color: var(--task-red);
  padding: 1px 6px;
  border-radius: var(--radius-xs);
  font-size: var(--text-2xs);
  font-weight: 600;
}
</style>
