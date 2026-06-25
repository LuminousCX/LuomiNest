<script setup lang="ts">
import LumiButton from '../common/LumiButton.vue'
import LumiCard from '../common/LumiCard.vue'
import LumiInput from '../common/LumiInput.vue'
import {
  Terminal,
  RotateCcw,
  Copy,
  Play,
} from 'lucide-vue-next'
import type { LogEntry } from './types'

interface Props {
  logs: LogEntry[]
  input: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:input', value: string): void
  (e: 'enter'): void
  (e: 'clear'): void
}>()

function getLogLevelStyle(level: string) {
  const map: Record<string, { bg: string; text: string; dot: string }> = {
    info: { bg: 'var(--lumi-primary-light)', text: 'var(--lumi-primary)', dot: 'var(--lumi-primary)' },
    warn: { bg: 'var(--lumi-warning-light)', text: 'var(--lumi-warning)', dot: 'var(--lumi-warning)' },
    error: { bg: 'var(--lumi-danger-light)', text: 'var(--lumi-danger)', dot: 'var(--lumi-danger)' },
    success: { bg: 'var(--lumi-success-light)', text: 'var(--lumi-success)', dot: 'var(--lumi-success)' },
  }
  return map[level] || map.info
}

function updateInput(value: string | number | null) {
  emit('update:input', value === null ? '' : String(value))
}
</script>

<template>
  <LumiCard class="panel-card console-panel" padding="none">
    <template #title>
      <div class="panel-title-group">
        <Terminal :size="18" class="panel-icon shrink-0" style="color: var(--lumi-warning)" />
        <h3>控制台</h3>
        <span class="panel-badge yellow">Real-time</span>
      </div>
    </template>
    <template #header>
      <div class="console-actions">
        <LumiButton variant="ghost" size="sm" icon-only aria-label="清空日志" @click="emit('clear')">
          <template #icon>
            <RotateCcw :size="13" />
          </template>
        </LumiButton>
        <LumiButton variant="ghost" size="sm" icon-only aria-label="复制全部">
          <template #icon>
            <Copy :size="13" />
          </template>
        </LumiButton>
      </div>
    </template>
    <div class="console-log-area">
      <div
        v-for="log in logs"
        :key="log.id"
        class="log-entry"
        :style="{
          '--log-bg': getLogLevelStyle(log.level).bg,
          '--log-text': getLogLevelStyle(log.level).text,
          '--log-dot': getLogLevelStyle(log.level).dot,
        }"
      >
        <span class="log-time">{{ log.timestamp }}</span>
        <span class="log-level-dot" />
        <span class="log-source">[{{ log.source }}]</span>
        <span class="log-message">{{ log.message }}</span>
      </div>
    </div>
    <div class="console-input-row">
      <span class="console-prompt">$ luominest</span>
      <LumiInput
        :model-value="props.input"
        class="console-input"
        placeholder="输入命令... (help 查看帮助)"
        @update:model-value="updateInput"
        @enter="emit('enter')"
      />
      <LumiButton variant="primary" size="sm" icon-only :disabled="!props.input.trim()" @click="emit('enter')">
        <template #icon>
          <Play :size="14" />
        </template>
      </LumiButton>
    </div>
  </LumiCard>
</template>

<style scoped>
.panel-card {
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-card :deep(.lumi-card__body) {
  display: contents;
}

.panel-title-group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.panel-title-group h3 {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.panel-badge {
  font-size: var(--text-2xs);
  padding: calc(var(--space-1) / 2) var(--space-3);
  border-radius: var(--radius-full);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  font-weight: var(--font-medium);
  letter-spacing: 0.3px;
}

.panel-badge.yellow { background: var(--lumi-amber-soft); color: var(--lumi-amber); }

.console-panel {
  flex: 1;
  min-height: calc(var(--space-8) * 6);
}

.console-actions {
  display: flex;
  gap: var(--space-1);
}

.console-log-area {
  flex: 1;
  padding: var(--space-3) var(--space-4);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  min-height: calc(var(--space-5) * 9);
  max-height: calc(var(--space-5) * 11);
}

.log-entry {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-xs);
  background: var(--log-bg);
  transition: all var(--transition-fast);
}

.log-entry:hover {
  filter: brightness(1.05);
}

.log-time {
  color: var(--text-muted);
  flex-shrink: 0;
  font-family: inherit;
}

.log-level-dot {
  width: var(--space-2);
  height: var(--space-2);
  border-radius: var(--radius-full);
  background: var(--log-dot);
  flex-shrink: 0;
}

.log-source {
  color: var(--log-text);
  font-weight: var(--font-semibold);
  flex-shrink: 0;
  font-family: inherit;
}

.log-message {
  color: var(--text-secondary);
  font-family: inherit;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.console-input-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border-light);
  background: var(--bg-secondary);
}

.console-prompt {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--lumi-primary);
  flex-shrink: 0;
}

.console-input {
  flex: 1;
}

.console-input :deep(.lumi-input) {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  background: var(--surface);
  border-color: transparent;
}

.console-input :deep(.lumi-input:focus) {
  border-color: var(--lumi-primary);
  box-shadow: var(--input-focus-ring);
}

.console-input :deep(.lumi-input::placeholder) {
  color: var(--text-muted);
}
</style>
