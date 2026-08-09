<script setup lang="ts">
import { X, Edit3, Trash2, Calendar, Timer, Flag, Tag, CheckCircle2, Circle } from 'lucide-vue-next'
import type { LuomiNestTask } from './types'
import { statusLabel, priorityLabel } from './types'

const props = defineProps<{
  visible: boolean
  task: LuomiNestTask | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  edit: [task: LuomiNestTask]
  delete: [taskId: number]
}>()

const closeModal = () => {
  emit('update:visible', false)
}
</script>

<template>
  <Teleport to="body">
    <Transition name="luomi-modal">
      <div v-if="visible && task" class="luomi-modal-overlay" @click.self="closeModal">
        <div class="luomi-modal">
          <div class="luomi-modal-header">
            <h2 class="luomi-modal-title">
              <CheckCircle2 v-if="task.status === 'done'" :size="18" />
              <Circle v-else :size="18" />
              任务详情
            </h2>
            <button class="luomi-modal-close" @click="closeModal">
              <X :size="18" />
            </button>
          </div>

          <div class="luomi-modal-body">
            <div class="detail-header" :style="{ '--card-accent': `var(${task.colorVar})` }">
              <div class="detail-accent"></div>
              <h3 class="detail-title">{{ task.title }}</h3>
              <p class="detail-desc">{{ task.desc || '暂无描述' }}</p>
            </div>

            <div class="detail-meta-grid">
              <div class="detail-meta-item">
                <span class="detail-meta-label"><Flag :size="13" /> 优先级</span>
                <span :class="['detail-meta-value', `priority-${task.priority}`]">
                  {{ priorityLabel(task.priority) }}
                </span>
              </div>
              <div class="detail-meta-item">
                <span class="detail-meta-label"><Circle :size="13" /> 状态</span>
                <span :class="['detail-meta-value', `status-${task.status}`]">
                  {{ statusLabel(task.status) }}
                </span>
              </div>
              <div class="detail-meta-item">
                <span class="detail-meta-label"><Calendar :size="13" /> 截止日期</span>
                <span class="detail-meta-value">{{ task.dueDate }}</span>
              </div>
              <div class="detail-meta-item">
                <span class="detail-meta-label"><Timer :size="13" /> 时间段</span>
                <span class="detail-meta-value">{{ task.timeSlot }}</span>
              </div>
            </div>

            <div v-if="task.tags.length > 0" class="detail-section">
              <span class="detail-section-label"><Tag :size="13" /> 标签</span>
              <div class="detail-tags">
                <span v-for="tag in task.tags" :key="tag" class="detail-tag">{{ tag }}</span>
              </div>
            </div>

            <div v-if="task.progress > 0" class="detail-section">
              <span class="detail-section-label">进度</span>
              <div class="detail-progress">
                <div class="detail-progress-bar">
                  <div class="detail-progress-fill" :style="{ width: `${task.progress}%` }"></div>
                </div>
                <span class="detail-progress-text">{{ task.progress }}%</span>
              </div>
            </div>

            <div v-if="task.assignees.length > 0" class="detail-section">
              <span class="detail-section-label">负责人</span>
              <div class="detail-assignees">
                <img
                  v-for="(a, i) in task.assignees"
                  :key="i"
                  :src="a"
                  class="detail-assignee"
                  alt=""
                />
              </div>
            </div>
          </div>

          <div class="luomi-modal-footer">
            <button class="luomi-btn luomi-btn-ghost" @click="closeModal">关闭</button>
            <button class="luomi-btn luomi-btn-danger" @click="emit('delete', task.id); closeModal()">
              <Trash2 :size="14" />
              删除
            </button>
            <button class="luomi-btn luomi-btn-primary" @click="emit('edit', task); closeModal()">
              <Edit3 :size="14" />
              编辑
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.luomi-modal-overlay {
  background: var(--overlay-backdrop);
  backdrop-filter: var(--glass-blur);
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
  padding: var(--space-5) var(--space-6) var(--space-4);
  border-bottom: 1px solid var(--workspace-border);
}

.luomi-modal-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--text-primary);
}

.luomi-modal-close {
  width: var(--space-7);
  height: var(--space-7);
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
  padding: var(--space-5) var(--space-6);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.luomi-modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--workspace-border);
}

.detail-header {
  position: relative;
  padding-left: var(--space-4);
}

.detail-accent {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: var(--space-1);
  border-radius: 2px;
  background: var(--card-accent);
}

.detail-title {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.detail-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: 1.6;
}

.detail-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.detail-meta-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--workspace-bg);
  border: 1px solid var(--workspace-border);
}

.detail-meta-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.detail-meta-value {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.detail-meta-value.priority-high {
  color: var(--task-red);
}

.detail-meta-value.priority-medium {
  color: var(--task-yellow);
}

.detail-meta-value.priority-low {
  color: var(--task-green);
}

.detail-meta-value.status-done {
  color: var(--task-green);
}

.detail-meta-value.status-progress {
  color: var(--task-blue);
}

.detail-meta-value.status-pending {
  color: var(--task-yellow);
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.detail-section-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.detail-tag {
  font-size: var(--text-xs);
  font-weight: 600;
  padding: 3px var(--space-2);
  border-radius: 5px;
  background: var(--task-sky-soft);
  color: var(--task-sky);
}

.detail-progress {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.detail-progress-bar {
  flex: 1;
  height: var(--space-1);
  border-radius: 2px;
  background: var(--workspace-panel);
  overflow: hidden;
}

.detail-progress-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--lumi-brand);
  transition: width var(--duration-enter) var(--ease-in-out);
}

.detail-progress-text {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-secondary);
}

.detail-assignees {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.detail-assignee {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-full);
  object-fit: cover;
  border: 2px solid var(--workspace-border);
}

.luomi-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: 600;
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-fast);
  font-family: inherit;
}

.luomi-btn-ghost {
  background: var(--workspace-bg);
  color: var(--text-secondary);
}

.luomi-btn-ghost:hover {
  background: var(--workspace-hover);
}

.luomi-btn-primary {
  background: var(--lumi-brand);
  border-color: var(--lumi-brand);
  color: var(--text-inverse);
}

.luomi-btn-primary:hover {
  background: var(--lumi-brand-hover);
}

.luomi-btn-danger {
  background: var(--task-red-soft);
  border-color: var(--task-red);
  color: var(--task-red);
}

.luomi-btn-danger:hover {
  background: var(--task-red);
  color: var(--text-inverse);
}

.luomi-modal-enter-active {
  transition: all var(--duration-normal) var(--ease-in-out);
}

.luomi-modal-leave-active {
  transition: all var(--duration-leave) var(--ease-in-out);
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
</style>
