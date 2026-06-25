<script setup lang="ts">
import LumiButton from '../common/LumiButton.vue'
import LumiCard from '../common/LumiCard.vue'
import {
  Cpu,
  Settings2,
  Globe,
  Zap,
  ChevronRight,
} from 'lucide-vue-next'
import type { ModelProvider } from './types'

interface Props {
  providers: ModelProvider[]
}

defineProps<Props>()
</script>

<template>
  <LumiCard class="panel-card model-panel" padding="none">
    <template #title>
      <div class="panel-title-group">
        <Cpu :size="18" class="panel-icon shrink-0" style="color: var(--lumi-primary)" />
        <h3>模型配置</h3>
        <span class="panel-badge">Model Providers</span>
      </div>
    </template>
    <template #header>
      <LumiButton variant="ghost" size="sm" icon-only aria-label="设置">
        <template #icon>
          <Settings2 :size="14" />
        </template>
      </LumiButton>
    </template>
    <div class="provider-list">
      <div
        v-for="provider in providers"
        :key="provider.id"
        :class="['provider-item', { inactive: provider.status !== 'active' }]"
        :style="{ '--provider-color': provider.color }"
      >
        <div class="provider-avatar">
          <span>{{ provider.icon }}</span>
        </div>
        <div class="provider-info">
          <div class="provider-name-row">
            <span class="provider-name">{{ provider.name }}</span>
            <span :class="['status-dot', provider.status]" />
          </div>
          <span class="provider-model">{{ provider.model }}</span>
        </div>
        <div class="provider-stats">
          <div class="mini-stat">
            <Globe :size="11" />
            <span>{{ provider.requests.toLocaleString() }}</span>
          </div>
          <div class="mini-stat">
            <Zap :size="11" />
            <span>{{ provider.latency }}ms</span>
          </div>
        </div>
        <ChevronRight :size="16" class="provider-arrow" />
      </div>
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

.model-panel {
  flex: 1;
}

.provider-list {
  padding: var(--space-3) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.provider-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-normal);
  border: 1px solid transparent;
}

.provider-item:hover {
  background: var(--bg-secondary);
  border-color: var(--provider-color);
}

.provider-item.inactive {
  opacity: 0.5;
}

.provider-avatar {
  width: var(--space-8);
  height: var(--space-8);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
  font-weight: var(--font-bold);
  color: var(--provider-color);
  background: color-mix(in srgb, var(--provider-color) 10%, transparent);
  flex-shrink: 0;
}

.provider-info {
  flex: 1;
  min-width: 0;
}

.provider-name-row {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-bottom: calc(var(--space-1) / 2);
}

.provider-name {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.status-dot {
  width: var(--space-2);
  height: var(--space-2);
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.status-dot.active { background: var(--lumi-success); box-shadow: 0 0 var(--space-2) var(--task-green-border); }
.status-dot.inactive { background: var(--text-muted); }
.status-dot.error { background: var(--lumi-danger); box-shadow: 0 0 var(--space-2) var(--task-red-border); }

.provider-model {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.provider-stats {
  display: flex;
  gap: var(--space-3);
  flex-shrink: 0;
}

.mini-stat {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.provider-arrow {
  color: var(--text-muted);
  opacity: 0;
  transition: all var(--transition-fast);
}

.provider-item:hover .provider-arrow {
  opacity: 1;
  color: var(--provider-color);
}
</style>
