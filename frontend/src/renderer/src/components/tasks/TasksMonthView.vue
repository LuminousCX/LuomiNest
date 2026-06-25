<script setup lang="ts">
import type { MonthGrid, LuomiNestTask } from './types'

const props = defineProps<{
  monthGrid: MonthGrid
  monthKey: string
  monthSlideDir: 'up' | 'down'
  tasksForDate: (fullDate: string) => LuomiNestTask[]
}>()

const emit = defineEmits<{
  createTask: [date: string]
  editTask: [task: LuomiNestTask]
  wheel: [event: WheelEvent]
}>()

const weekdayNames = ['一', '二', '三', '四', '五', '六', '日']
</script>

<template>
  <div
    class="month-section animate-slide-up"
    style="animation-delay: 70ms"
    @wheel.prevent="emit('wheel', $event)"
  >
    <div class="month-weekday-row">
      <div v-for="name in weekdayNames" :key="name" class="month-weekday-cell">
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
          @click="emit('createTask', cell.fullDate)"
          @keydown.enter="emit('createTask', cell.fullDate)"
          @keydown.space.prevent="emit('createTask', cell.fullDate)"
        >
          <div class="month-cell-header">
            <span class="month-cell-date">{{ cell.date }}</span>
            <span v-if="tasksForDate(cell.fullDate).length > 0" class="month-cell-count">
              {{ tasksForDate(cell.fullDate).length }}
            </span>
          </div>

          <div class="month-cell-tasks">
            <div
              v-for="task in tasksForDate(cell.fullDate).slice(0, 3)"
              :key="task.id"
              class="month-task-item"
              :style="{ '--card-accent': `var(${task.colorVar})` }"
              :class="[`status-${task.status}`]"
              @click.stop="emit('editTask', task)"
            >
              <div class="month-task-dot"></div>
              <span class="month-task-title">{{ task.title }}</span>
            </div>
            <div
              v-if="tasksForDate(cell.fullDate).length > 3"
              class="month-task-more"
            >
              +{{ tasksForDate(cell.fullDate).length - 3 }} 更多
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
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
  padding: 10px var(--space-2);
  text-align: center;
  font-size: var(--text-sm);
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
  padding: var(--space-2);
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
  background: var(--lumi-brand-light);
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
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
}

.month-cell.is-today .month-cell-date {
  background: var(--lumi-brand);
  color: var(--text-inverse);
  width: var(--space-6);
  height: var(--space-6);
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-sm);
}

.month-cell-count {
  font-size: var(--text-2xs);
  font-weight: 600;
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  padding: 1px 6px;
  border-radius: var(--radius-full);
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
  border-radius: var(--radius-full);
  background: var(--card-accent);
  flex-shrink: 0;
}

.month-task-title {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.month-task-more {
  font-size: var(--text-2xs);
  color: var(--lumi-brand);
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
  transition: all var(--duration-slow) var(--ease-in-out);
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
</style>
