<script setup lang="ts">
import { CheckCircle2, Circle, Trash2 } from 'lucide-vue-next'
import type { CalendarDay, LuomiNestTask } from './types'
import { getTaskTopPosition } from './types'

const props = defineProps<{
  weekDays: CalendarDay[]
  timeSlots: string[]
  tasksForDate: (fullDate: string) => LuomiNestTask[]
}>()

const emit = defineEmits<{
  createTask: [date: string, timeSlot: string]
  editTask: [task: LuomiNestTask]
  toggleStatus: [task: LuomiNestTask]
  deleteTask: [taskId: number]
}>()

const openCreateForSlot = (day: CalendarDay, slot: string) => {
  const nextSlot = props.timeSlots[props.timeSlots.indexOf(slot) + 1]
  emit('createTask', day.fullDate, `${slot} - ${nextSlot}`)
}
</script>

<template>
  <div class="week-section animate-slide-up" style="animation-delay: 70ms">
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
        <div class="week-day-count" v-if="tasksForDate(day.fullDate).length > 0">
          {{ tasksForDate(day.fullDate).length }} 项
        </div>
      </div>
    </div>

    <div class="week-body custom-scrollbar--thin">
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
            @click="openCreateForSlot(day, slot)"
            @keydown.enter="openCreateForSlot(day, slot)"
            @keydown.space.prevent="openCreateForSlot(day, slot)"
          >
            <div class="week-cell-time">{{ slot }}</div>
          </div>

          <div class="week-task-overlay">
            <div
              v-for="task in tasksForDate(day.fullDate)"
              :key="task.id"
              class="week-task-item"
              :class="[`status-${task.status}`]"
              :style="{ '--card-accent': `var(${task.colorVar})`, top: getTaskTopPosition(task) }"
              @click.stop="emit('editTask', task)"
            >
              <div class="week-task-accent"></div>
              <div class="week-task-content">
                <span class="week-task-title">{{ task.title }}</span>
                <span class="week-task-time">{{ task.timeSlot }}</span>
              </div>
              <div class="week-task-actions">
                <button class="week-task-action" @click.stop="emit('toggleStatus', task)">
                  <CheckCircle2 v-if="task.status === 'done'" :size="10" />
                  <Circle v-else :size="10" />
                </button>
                <button class="week-task-action danger" @click.stop="emit('deleteTask', task.id)">
                  <Trash2 :size="10" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
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
  padding: var(--space-3) var(--space-2);
  text-align: center;
  border-right: 1px solid var(--workspace-border);
  transition: background var(--transition-fast);
}

.week-day-header:last-child {
  border-right: none;
}

.week-day-header.is-today {
  background: var(--lumi-brand-light);
}

.week-day-header.is-weekend {
  background: var(--surface-ghost);
}

.week-day-weekday {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: 500;
}

.week-day-date {
  font-size: var(--text-3xl);
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.week-day-date.today-dot {
  color: var(--lumi-brand);
}

.week-day-count {
  font-size: var(--text-2xs);
  color: var(--lumi-brand);
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
  font-size: var(--text-2xs);
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
  background: var(--lumi-brand-light);
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
  padding: var(--space-1) 6px;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  pointer-events: none;
}

.week-task-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-xs);
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
  padding-left: var(--space-1);
  flex: 1;
  min-width: 0;
}

.week-task-title {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.week-task-time {
  font-size: var(--text-2xs);
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
  width: var(--space-5);
  height: var(--space-5);
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

</style>
