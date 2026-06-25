<script setup lang="ts">
import {
  Timer,
  RotateCcw,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  Trash2
} from 'lucide-vue-next'
import type { ScheduledTaskInfo } from '../../stores/taskStream'

const props = defineProps<{
  scheduledTasks: ScheduledTaskInfo[]
}>()

const emit = defineEmits<{
  refresh: []
  delete: [taskId: string]
}>()

const formatScheduledTime = (isoStr: string | null): string => {
  if (!isoStr) return '未知'
  try {
    const dt = new Date(isoStr)
    return dt.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return isoStr
  }
}
</script>

<template>
  <div class="scheduled-section animate-slide-up" style="animation-delay: 70ms">
    <div class="scheduled-header">
      <div class="scheduled-title">
        <Timer :size="18" />
        <span>定时任务</span>
        <span class="scheduled-count">{{ scheduledTasks.length }}</span>
      </div>
      <button class="scheduled-refresh-btn" @click="emit('refresh')">
        <RotateCcw :size="14" />
        刷新
      </button>
    </div>

    <div v-if="scheduledTasks.length === 0" class="scheduled-empty">
      <Timer :size="40" />
      <p>暂无定时任务</p>
      <span>主 Agent 可通过 create_scheduled_task 工具创建定时任务</span>
    </div>

    <div v-else class="scheduled-list">
      <div
        v-for="task in scheduledTasks"
        :key="task.id"
        :class="['scheduled-card', `status-${task.status}`]"
      >
        <div class="scheduled-card-header">
          <div class="scheduled-status-icon">
            <Loader2 v-if="task.status === 'running'" :size="16" class="spin-animation" />
            <CheckCircle2 v-else-if="task.status === 'completed'" :size="16" />
            <XCircle v-else-if="task.status === 'failed'" :size="16" />
            <Clock v-else-if="task.status === 'pending'" :size="16" />
            <AlertCircle v-else :size="16" />
          </div>
          <div class="scheduled-card-info">
            <div class="scheduled-card-title">{{ task.name }}</div>
            <div class="scheduled-card-meta">
              <span class="scheduled-type">{{ task.task_type }}</span>
              <span v-if="task.next_run_time" class="scheduled-next">
                下次: {{ formatScheduledTime(task.next_run_time) }}
              </span>
              <span v-if="task.last_run_time" class="scheduled-last">
                上次: {{ formatScheduledTime(task.last_run_time) }}
              </span>
            </div>
          </div>
          <button class="scheduled-delete-btn" @click="emit('delete', task.id)">
            <Trash2 :size="14" />
          </button>
        </div>

        <div v-if="task.description" class="scheduled-card-desc">{{ task.description }}</div>

        <div v-if="task.last_result" class="scheduled-card-result">
          <div class="scheduled-result-label">
            <CheckCircle2 :size="12" />
            <span>执行结果</span>
          </div>
          <div class="scheduled-result-content">{{ task.last_result }}</div>
        </div>

        <div v-if="task.last_error" class="scheduled-card-error">
          <div class="scheduled-error-label">
            <XCircle :size="12" />
            <span>错误信息</span>
          </div>
          <div class="scheduled-error-content">{{ task.last_error }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scheduled-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  overflow: hidden;
}

.scheduled-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-1);
}

.scheduled-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text);
}

.scheduled-count {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-muted);
  padding: 2px var(--space-2);
  background: var(--workspace-hover);
  border-radius: var(--radius-full);
}

.scheduled-refresh-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-muted);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-leave) var(--ease-in-out);
}

.scheduled-refresh-btn:hover {
  color: var(--text);
  background: var(--workspace-hover);
}

.scheduled-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--text-muted);
}

.scheduled-empty p {
  font-size: var(--text-md);
  font-weight: 500;
  margin: var(--space-2) 0 0;
}

.scheduled-empty span {
  font-size: var(--text-sm);
}

.scheduled-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: var(--space-1);
}

.scheduled-card {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  padding: 14px var(--space-4);
  transition: border-color var(--duration-leave) var(--ease-in-out);
}

.scheduled-card.status-running {
  border-color: var(--lumi-brand);
}

.scheduled-card.status-failed {
  border-color: var(--lumi-danger);
}

.scheduled-card.status-completed {
  border-color: var(--lumi-success);
}

.scheduled-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.scheduled-status-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-6);
  height: var(--space-6);
  flex-shrink: 0;
}

.scheduled-status-icon .spin-animation {
  animation: spin 1s linear infinite;
  color: var(--lumi-brand);
}

.status-completed .scheduled-status-icon {
  color: var(--lumi-success);
}

.status-failed .scheduled-status-icon {
  color: var(--lumi-danger);
}

.status-pending .scheduled-status-icon {
  color: var(--text-muted);
}

.scheduled-card-info {
  flex: 1;
  min-width: 0;
}

.scheduled-card-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text);
  margin-bottom: var(--space-1);
}

.scheduled-card-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.scheduled-type {
  padding: 1px 6px;
  background: var(--workspace-hover);
  border-radius: 4px;
  font-family: var(--font-mono);
}

.scheduled-delete-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-in-out);
}

.scheduled-delete-btn:hover {
  color: var(--lumi-danger);
  background: var(--workspace-hover);
}

.scheduled-card-desc {
  margin-top: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: 1.5;
}

.scheduled-card-result,
.scheduled-card-error {
  margin-top: 10px;
  padding: var(--space-2) 10px;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
}

.scheduled-card-result {
  background: var(--lumi-success-light);
  border-left: 2px solid var(--lumi-success);
}

.scheduled-card-error {
  background: var(--lumi-danger-light);
  border-left: 2px solid var(--lumi-danger);
}

.scheduled-result-label,
.scheduled-error-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-weight: 600;
  margin-bottom: var(--space-1);
}

.scheduled-result-label {
  color: var(--lumi-success);
}

.scheduled-error-label {
  color: var(--lumi-danger);
}

.scheduled-result-content,
.scheduled-error-content {
  color: var(--text);
  line-height: 1.5;
  max-height: 120px;
  overflow-y: auto;
  word-break: break-word;
  white-space: pre-wrap;
}
</style>
