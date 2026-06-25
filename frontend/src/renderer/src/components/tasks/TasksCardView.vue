<script setup lang="ts">
import {
  Plus,
  MoreHorizontal,
  Calendar,
  Edit3,
  Trash2,
  CheckSquare,
  Square
} from 'lucide-vue-next'
import type { CalendarDay, LuomiNestTask } from './types'
import { statusLabel, priorityLabel } from './types'

const props = defineProps<{
  cardDays: CalendarDay[]
  timeSlots: string[]
  tasksForDate: (fullDate: string) => LuomiNestTask[]
  subTasks: { label: string; done: boolean }[]
  completedSubTasks: number
}>()

const emit = defineEmits<{
  createTask: [date: string]
  editTask: [task: LuomiNestTask]
  deleteTask: [taskId: number]
}>()
</script>

<template>
  <div class="calendar-section animate-slide-up" style="animation-delay: 70ms">
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
          :class="{ 'has-tasks': tasksForDate(day.fullDate).length > 0 }"
        >
          <div class="column-tasks">
            <div
              v-for="task in tasksForDate(day.fullDate)"
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
                <button class="action-chip" title="编辑" @click.stop="emit('editTask', task)"><Edit3 :size="11" /></button>
                <button class="action-chip danger" title="删除" @click.stop="emit('deleteTask', task.id)"><Trash2 :size="11" /></button>
              </div>
            </div>

            <div v-if="tasksForDate(day.fullDate).length === 0" class="add-task-placeholder" @click="emit('createTask', day.fullDate)">
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
</template>

<style scoped>
.calendar-section {
  margin-bottom: 18px;
}

.calendar-header-row {
  display: grid;
  grid-template-columns: var(--space-9) repeat(4, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  padding: 0 var(--space-1);
}

.time-label-col {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding-bottom: var(--space-2);
}

.calendar-day-header {
  text-align: center;
  padding: var(--space-3) 0 var(--space-2);
}

.calendar-day-header.is-today .date-number {
  color: var(--lumi-brand);
}

.date-number {
  font-size: var(--text-4xl);
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.date-weekday {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-top: 2px;
}

.calendar-body {
  display: grid;
  grid-template-columns: var(--space-9) repeat(4, 1fr);
  gap: var(--space-3);
  min-height: 320px;
}

.time-axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: var(--space-2) 0;
}

.time-slot-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: 500;
  line-height: 1;
  padding: var(--space-1) 0;
}

.calendar-columns {
  display: contents;
}

.calendar-column {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: var(--space-1) 0;
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
  padding: 14px var(--space-4);
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
  left: var(--space-4);
  right: var(--space-4);
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
  margin-top: var(--space-1);
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.card-tag {
  font-size: var(--text-2xs);
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 5px;
  background: var(--task-purple-soft);
  color: var(--task-purple);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.card-priority {
  font-size: var(--text-2xs);
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
  width: var(--space-6);
  height: var(--space-6);
  border-radius: var(--radius-xs);
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
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-1);
  line-height: 1.35;
}

.card-time {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-bottom: 10px;
}

.progress-mini {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 10px;
}

.progress-bar-mini {
  flex: 1;
  height: var(--space-1);
  border-radius: 2px;
  background: var(--workspace-panel);
  overflow: hidden;
}

.progress-fill-mini {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--card-accent), var(--progress-shimmer));
  transition: width var(--duration-enter) var(--ease-in-out);
}

.progress-text {
  font-size: var(--text-2xs);
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
  font-size: var(--text-xs);
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
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-bottom: var(--space-1);
}

.completion-bar {
  height: var(--space-1);
  border-radius: 2px;
  background: var(--workspace-panel);
  overflow: hidden;
}

.completion-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--card-accent);
  transition: width var(--duration-enter) var(--ease-in-out);
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
  gap: var(--space-2);
}

.due-date {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.status-badge {
  font-size: var(--text-2xs);
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
  border-radius: var(--radius-full);
  border: 2px solid var(--workspace-card);
  margin-left: -7px;
  object-fit: cover;
}

.assignee-avatar:first-child {
  margin-left: 0;
}

.card-actions {
  position: absolute;
  top: var(--space-3);
  right: 38px;
  display: flex;
  gap: var(--space-1);
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.action-chip {
  width: var(--space-6);
  height: var(--space-6);
  border-radius: var(--radius-xs);
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
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

.add-task-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
}

.add-circle {
  width: 42px;
  height: 42px;
  border-radius: var(--radius-full);
  background: linear-gradient(135deg, var(--lumi-brand), var(--lumi-brand-soft));
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
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
}
</style>
