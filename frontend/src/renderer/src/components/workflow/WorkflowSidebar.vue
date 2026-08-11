<script setup lang="ts">
/**
 * 工作流侧栏 - 实时会话指示 + 历史会话列表
 */
import { Play, Loader2, CheckCircle2, XCircle, Zap, Clock } from 'lucide-vue-next'
import type { WorkflowSession } from '../../types/workflow'
import { PHASE_LABELS, formatWorkflowTime } from '../../composables/useWorkflowSessions'

defineProps<{
  sessions: WorkflowSession[]
  isLoadingSessions: boolean
  selectedSessionId: string | null
  hasLiveSession: boolean
  isRunning: boolean
  livePhase: string
}>()

defineEmits<{
  'select-session': [sessionId: string]
  'show-live': []
}>()
</script>

<template>
  <aside class="workflow-sidebar">
    <div class="sidebar-section">
      <div class="section-label">
        <Zap :size="14" />
        <span>实时工作流</span>
      </div>
      <button
        class="session-item"
        :class="{ active: selectedSessionId === null && hasLiveSession }"
        @click="$emit('show-live')"
      >
        <div class="session-item-icon" :class="{ running: isRunning }">
          <Loader2 v-if="isRunning" :size="14" class="spin-animation" />
          <Play v-else :size="14" />
        </div>
        <div class="session-item-info">
          <span class="session-item-title">
            {{ hasLiveSession ? '当前执行中' : '无实时工作流' }}
          </span>
          <span class="session-item-meta">
            {{ isRunning ? (PHASE_LABELS[livePhase] || '') : '空闲' }}
          </span>
        </div>
      </button>
    </div>

    <div class="sidebar-section sidebar-sessions">
      <div class="section-label">
        <Clock :size="14" />
        <span>历史工作流</span>
      </div>
      <div v-if="isLoadingSessions" class="loading-hint">
        <Loader2 :size="14" class="spin-animation" />
        <span>加载中...</span>
      </div>
      <div v-else-if="sessions.length === 0" class="empty-hint">
        暂无历史工作流
      </div>
      <div v-else class="session-list">
        <button
          v-for="session in sessions"
          :key="session.session_id"
          class="session-item"
          :class="{ active: selectedSessionId === session.session_id }"
          @click="$emit('select-session', session.session_id)"
        >
          <div class="session-item-icon" :class="session.phase">
            <CheckCircle2 v-if="session.phase === 'completed'" :size="14" />
            <XCircle v-else-if="session.phase === 'failed'" :size="14" />
            <Loader2 v-else :size="14" class="spin-animation" />
          </div>
          <div class="session-item-info">
            <span class="session-item-title">{{ session.user_message?.slice(0, 30) || '未命名工作流' }}</span>
            <span class="session-item-meta">
              {{ formatWorkflowTime(session.created_at) }} · {{ session.stats?.total ?? 0 }} 个任务
            </span>
          </div>
        </button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.workflow-sidebar {
  width: 240px;
  flex-shrink: 0;
  padding: var(--space-3);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--workspace-border);
  box-shadow: var(--shadow-sm);
  align-self: flex-start;
  position: sticky;
  top: 0;
  max-height: 100%;
}

.sidebar-section {
  padding: var(--space-2) var(--space-1);
}

.sidebar-sessions {
  flex: 1;
  overflow-y: auto;
}

.section-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--text-muted);
  margin-bottom: var(--space-3);
}

.session-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  text-align: left;
  transition: background var(--transition-fast, 0.15s ease-in-out);
  cursor: pointer;
  margin-bottom: var(--space-1);
}

.session-item:hover {
  background: var(--workspace-hover);
}

.session-item.active {
  background: var(--lumi-brand-light);
}

.session-item-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  background: var(--surface-hover);
  color: var(--text-muted);
  flex-shrink: 0;
}

.session-item-icon.running {
  color: var(--lumi-info);
}

.session-item-icon.completed {
  color: var(--lumi-success);
}

.session-item-icon.failed {
  color: var(--lumi-danger);
}

.session-item-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: 1;
}

.session-item-title {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-item-meta {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.loading-hint,
.empty-hint {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.session-list {
  display: flex;
  flex-direction: column;
}

.spin-animation {
  animation: spin 1.2s linear infinite;
}

button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}
</style>
