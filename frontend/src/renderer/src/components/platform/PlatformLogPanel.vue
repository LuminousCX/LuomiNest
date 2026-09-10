<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  FileText, AlertCircle, Timer, Layers,
} from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import LumiEmptyState from '../../components/common/LumiEmptyState.vue'

const store = usePlatformStore()
const { t } = useI18n()

const expandedLogIds = ref<Set<string>>(new Set())

const formatLogTime = (ts: string) => {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ts
  }
}

const formatLogDate = (ts: string) => {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    const today = new Date()
    if (d.toDateString() === today.toDateString()) return ''
    return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) + ' '
  } catch {
    return ''
  }
}

const getLogLevelClass = (level: string) => {
  switch (level) {
    case 'error': return 'log-error'
    case 'warning': return 'log-warning'
    case 'success': return 'log-success'
    default: return 'log-info'
  }
}

const getLogEventLabel = (event: string) => {
  const map: Record<string, string> = {
    instance_created: t('platform.log.instanceCreated'),
    instance_started: t('platform.log.instanceStarted'),
    instance_stopped: t('platform.log.instanceStopped'),
    instance_removed: t('platform.log.instanceRemoved'),
    start_failed: t('platform.log.startFailed'),
    stop_failed: t('platform.log.stopFailed'),
    handshake_init: t('platform.log.handshakeInit'),
    handshake_ok: t('platform.log.handshakeOk'),
    handshake_fail: t('platform.log.handshakeFail'),
    connection_attempting: t('platform.log.connectionAttempting'),
    connection_established: t('platform.log.connectionEstablished'),
    connection_lost: t('platform.log.connectionLost'),
    connection_reconnecting: t('platform.log.connectionReconnecting'),
    message_received: t('platform.log.messageReceived'),
    message_sent: t('platform.log.messageSent'),
    message_failed: t('platform.log.messageFailed'),
    llm_call_start: t('platform.log.llmCallStart'),
    llm_call_success: t('platform.log.llmCallSuccess'),
    llm_call_failed: t('platform.log.llmCallFailed'),
    model_config_updated: t('platform.log.modelConfigUpdated'),
    config_updated: t('platform.log.configUpdated'),
    screenshot_received: t('platform.log.screenshotReceived'),
    error: t('platform.log.error'),
  }
  return map[event] || event
}

const getLogDetailEntries = (details: Record<string, unknown>) => {
  return Object.entries(details).filter(([_k, v]) => v !== null && v !== undefined && v !== '')
}

const formatLogDetailValue = (val: unknown): string => {
  if (val === null || val === undefined) return ''
  if (typeof val === 'object') return JSON.stringify(val, null, 2)
  return String(val)
}

const isPerformanceLog = (event: string) => {
  return ['llm_call_success', 'llm_call_failed', 'message_sent'].includes(event)
}

const isErrorLog = (event: string, level: string) => {
  return level === 'error' || ['message_failed', 'start_failed', 'stop_failed', 'connection_lost', 'handshake_fail', 'llm_call_failed'].includes(event)
}

const isTraceableLog = (event: string) => {
  return ['message_received', 'llm_call_start', 'llm_call_success', 'llm_call_failed', 'message_sent', 'message_failed'].includes(event)
}

const getPerfLabel = (key: string) => {
  const map: Record<string, string> = {
    elapsed: t('platform.log.perfElapsed'),
    llm_elapsed: t('platform.log.perfLlmElapsed'),
    total_tokens: t('platform.log.perfTotalTokens'),
    prompt_tokens: t('platform.log.perfPromptTokens'),
    completion_tokens: t('platform.log.perfCompletionTokens'),
    retry_count: t('platform.log.perfRetryCount'),
  }
  return map[key] || key
}

const getPerfUnit = (key: string) => {
  if (key.includes('elapsed')) return ' ms'
  if (key.includes('tokens')) return ''
  if (key === 'retry_count') return t('platform.log.unitTimes')
  return ''
}

const toggleLogExpand = (logId: string) => {
  if (expandedLogIds.value.has(logId)) {
    expandedLogIds.value.delete(logId)
  } else {
    expandedLogIds.value.add(logId)
  }
}

const isLogExpanded = (logId: string) => expandedLogIds.value.has(logId)
</script>

<template>
  <div class="detail-body">
    <div class="log-list">
      <div
        v-for="log in store.logs"
        :key="log.id"
        :class="['log-entry', getLogLevelClass(log.level), {
          'log-traceable': isTraceableLog(log.event),
          'log-error-entry': isErrorLog(log.event, log.level),
          'log-performance': isPerformanceLog(log.event),
          'expanded': isLogExpanded(log.id),
        }]"
        @click="toggleLogExpand(log.id)"
      >
        <div class="log-header">
          <span :class="['log-level', log.level]">{{ log.level.toUpperCase() }}</span>
          <span class="log-event">
            <Layers v-if="isTraceableLog(log.event)" :size="11" class="log-event-icon" />
            <Timer v-else-if="isPerformanceLog(log.event)" :size="11" class="log-event-icon" />
            <AlertCircle v-else-if="isErrorLog(log.event, log.level)" :size="11" class="log-event-icon" />
            {{ getLogEventLabel(log.event) }}
          </span>
          <span class="log-time">{{ formatLogDate(log.timestamp) }}{{ formatLogTime(log.timestamp) }}</span>
          <span v-if="getLogDetailEntries(log.details).length > 0" class="log-expand-hint">
            {{ isLogExpanded(log.id) ? t('platform.log.collapse') : t('platform.log.expand') }}
          </span>
        </div>
        <div class="log-message">{{ log.message }}</div>

        <div v-if="isPerformanceLog(log.event) && getLogDetailEntries(log.details).length > 0" class="log-perf-stats">
          <template v-for="(val, key) in log.details" :key="key">
            <span v-if="['elapsed', 'llm_elapsed', 'total_tokens', 'prompt_tokens', 'completion_tokens', 'retry_count'].includes(String(key))" class="perf-stat">
              <span class="perf-key">{{ getPerfLabel(String(key)) }}</span>
              <span class="perf-val">{{ formatLogDetailValue(val) }}{{ getPerfUnit(String(key)) }}</span>
            </span>
          </template>
        </div>

        <div v-if="isLogExpanded(log.id) && getLogDetailEntries(log.details).length > 0" class="log-details-expanded">
          <template v-for="(val, key) in log.details" :key="key">
            <div v-if="String(key) === 'stack_trace'" class="log-stack-trace">
              <span class="log-detail-key">stack_trace:</span>
              <pre class="stack-trace-content">{{ formatLogDetailValue(val) }}</pre>
            </div>
            <div v-else class="log-detail-row">
              <span class="log-detail-key">{{ key }}</span>:
              <span class="log-detail-val">{{ formatLogDetailValue(val) }}</span>
            </div>
          </template>
        </div>
      </div>
      <LumiEmptyState
        v-if="store.logs.length === 0"
        :icon="FileText"
        :title="store.selectedInstanceId ? t('platform.log.emptyNoInstance') : t('platform.log.emptySelectInstance')"
        size="md"
      />
    </div>
    <div class="detail-notice">
      <FileText :size="14" />
      <span>{{ t('platform.log.notice') }}</span>
    </div>
  </div>
</template>

<style scoped>
.detail-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.log-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-1);
  font-family: var(--font-mono);
}

.log-entry {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-xs);
  margin-bottom: 2px;
  transition: background var(--transition-fast);
  border-left: 3px solid transparent;
  cursor: pointer;
}

.log-entry:hover {
  background: var(--surface-hover);
}

.log-entry.log-info {
  border-left-color: var(--lumi-brand);
}

.log-entry.log-success {
  border-left-color: var(--lumi-success);
}

.log-entry.log-warning {
  border-left-color: var(--lumi-warning);
}

.log-entry.log-error {
  border-left-color: var(--lumi-danger);
  background: var(--lumi-danger-light);
}

.log-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 3px;
}

.log-level {
  font-size: var(--text-2xs);
  font-weight: var(--font-bold);
  padding: 1px var(--space-1);
  border-radius: var(--radius-xs);
  letter-spacing: 0.5px;
}

.log-level.info {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.log-level.success {
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.log-level.warning {
  background: var(--lumi-amber-soft);
  color: var(--lumi-amber);
}

.log-level.error {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.log-event {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.log-time {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  margin-left: auto;
}

.log-message {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  line-height: var(--leading-normal);
  padding-left: 2px;
}

.log-detail-key {
  color: var(--lumi-brand);
  font-weight: var(--font-medium);
}

.log-detail-val {
  color: var(--text-secondary);
}

.detail-notice {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: var(--space-2);
  background: var(--bg-secondary);
  color: var(--text-muted);
  font-size: var(--text-xs);
  border-top: 1px solid var(--border-light);
}

.log-entry.log-traceable {
  border-left-color: var(--lumi-brand);
}

.log-entry.log-performance {
  border-left-color: var(--lumi-amber);
}

.log-entry.log-error-entry {
  border-left-color: var(--lumi-danger);
  background: var(--lumi-danger-light);
}

.log-entry.expanded {
  background: var(--surface-hover);
}

.log-event-icon {
  vertical-align: middle;
  margin-right: 2px;
}

.log-expand-hint {
  font-size: var(--text-2xs);
  padding: 1px var(--space-1);
  border-radius: var(--radius-xs);
  background: var(--bg-secondary);
  color: var(--text-muted);
  margin-left: var(--space-1);
}

.log-entry.expanded .log-expand-hint {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.log-perf-stats {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-1);
  padding: var(--space-1) var(--space-2);
  background: var(--lumi-amber-soft);
  border-radius: var(--radius-xs);
  border: 1px solid var(--lumi-amber-border);
}

.perf-stat {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-2xs);
}

.perf-key {
  color: var(--lumi-amber);
  font-weight: var(--font-medium);
}

.perf-val {
  color: var(--text-primary);
  font-weight: var(--font-semibold);
}

.log-details-expanded {
  margin-top: var(--space-1);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-secondary);
  border-radius: var(--radius-xs);
  border: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.log-detail-row {
  display: flex;
  gap: var(--space-1);
  font-size: var(--text-2xs);
  line-height: var(--leading-normal);
}

.log-detail-row .log-detail-key {
  color: var(--lumi-brand);
  font-weight: var(--font-medium);
  flex-shrink: 0;
  min-width: 80px;
}

.log-detail-row .log-detail-val {
  color: var(--text-secondary);
  word-break: break-all;
  white-space: pre-wrap;
}

.log-stack-trace {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.log-stack-trace .log-detail-key {
  color: var(--lumi-danger);
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
}

.stack-trace-content {
  margin: 0;
  padding: var(--space-2);
  background: var(--lumi-danger-light);
  border-radius: var(--radius-xs);
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--lumi-danger);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}
</style>
