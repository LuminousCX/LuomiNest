<script setup lang="ts">
import LumiButton from '../common/LumiButton.vue'
import LumiCard from '../common/LumiCard.vue'
import {
  Cpu,
  Plus,
  MoreHorizontal,
  Key,
  Globe,
  Server,
  Shield,
  Layers,
  Activity,
  Zap,
} from 'lucide-vue-next'
import type { ModelProvider } from './types'

interface Props {
  providers: ModelProvider[]
}

defineProps<Props>()
</script>

<template>
  <section class="dash-section full-panel">
    <LumiCard class="full-height" padding="none">
      <template #title>
        <div class="panel-title-group">
          <Cpu :size="20" class="panel-icon shrink-0" style="color: var(--lumi-primary)" />
          <h3>模型配置中心</h3>
        </div>
      </template>
      <template #header>
        <LumiButton variant="primary" size="sm">
          <template #icon>
            <Plus :size="14" />
          </template>
          添加供应商
        </LumiButton>
      </template>
      <div class="model-config-grid">
        <div
          v-for="provider in providers"
          :key="provider.id"
          :class="['model-config-card lumi-card', `status-${provider.status}`]"
          :style="{ '--pc-color': provider.color }"
        >
          <div class="mc-header">
            <div
              class="mc-brand"
              :style="{ background: `color-mix(in srgb, ${provider.color} 10%, transparent)` }"
            >
              <span :style="{ color: provider.color }">{{ provider.icon }}</span>
            </div>
            <div class="mc-meta">
              <span class="mc-name">{{ provider.name }}</span>
              <span :class="['mc-status', provider.status]">
                {{ provider.status === 'active' ? '在线' : provider.status === 'error' ? '异常' : '离线' }}
              </span>
            </div>
            <MoreHorizontal :size="16" class="mc-menu" />
          </div>
          <div class="mc-fields">
            <div class="mc-field">
              <label><Key :size="12" /> API Key</label>
              <div class="mc-input-mock">sk-••••••••••••••••a7x9k</div>
            </div>
            <div class="mc-field">
              <label><Globe :size="12" /> 端点地址</label>
              <div class="mc-input-mock">{{ provider.endpoint }}</div>
            </div>
            <div class="mc-field">
              <label><Server :size="12" /> 当前模型</label>
              <div class="mc-input-mock highlight">{{ provider.model }}</div>
            </div>
            <div class="mc-field">
              <label><Shield :size="12" /> 请求方式</label>
              <div class="mc-input-mock">REST API · Stream</div>
            </div>
            <div class="mc-field">
              <label><Layers :size="12" /> 上下文窗口</label>
              <div class="mc-progress-bar">
                <div class="mc-progress-fill" :style="{ width: '68%', background: provider.color }" />
                <span>128K · 已用 68%</span>
              </div>
            </div>
          </div>
          <div class="mc-footer">
            <div class="mc-footer-stat">
              <Activity :size="13" />
              <span>{{ provider.requests.toLocaleString() }} 次请求</span>
            </div>
            <div class="mc-footer-stat">
              <Zap :size="13" />
              <span>{{ provider.latency }}ms 延迟</span>
            </div>
          </div>
        </div>
      </div>
    </LumiCard>
  </section>
</template>

<style scoped>
.full-panel {
  flex: 1;
}

.full-height {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.full-height :deep(.lumi-card__body) {
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

.model-config-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
  padding: var(--space-5);
  flex: 1;
  overflow-y: auto;
  align-content: start;
}

.model-config-card {
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  transition: all var(--transition-normal);
  opacity: 0;
  animation: cardSlideUp var(--duration-enter) var(--ease-out-expo) both;
}

.model-config-card:hover {
  border-color: var(--pc-color);
  box-shadow: var(--shadow-md);
}

.model-config-card.status-error { border-color: var(--lumi-danger); }

@keyframes cardSlideUp {
  from { opacity: 0; transform: translateY(var(--space-4)); }
  to { opacity: 1; transform: translateY(0); }
}

.mc-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.mc-brand {
  width: var(--space-9);
  height: var(--space-9);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-md);
  font-weight: var(--font-bold);
  flex-shrink: 0;
}

.mc-meta {
  flex: 1;
}

.mc-name {
  display: block;
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.mc-status {
  font-size: var(--text-xs);
  padding: var(--badge-padding);
  border-radius: var(--radius-xs);
  margin-top: calc(var(--space-1) / 2);
  display: inline-block;
}

.mc-status.active { background: var(--task-green-soft); color: var(--lumi-success); }
.mc-status.inactive { background: var(--surface-hover); color: var(--text-muted); }
.mc-status.error { background: var(--task-red-soft); color: var(--lumi-danger); }

.mc-menu {
  color: var(--text-muted);
  cursor: pointer;
  padding: var(--space-1);
  border-radius: var(--radius-xs);
  transition: all var(--transition-fast);
}

.mc-menu:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.mc-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.mc-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.mc-field label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: var(--font-medium);
}

.mc-input-mock {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.mc-input-mock.highlight {
  color: var(--pc-color);
  font-weight: var(--font-semibold);
}

.mc-progress-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border);
}

.mc-progress-fill {
  height: var(--space-1);
  border-radius: calc(var(--space-1) / 2);
  flex: 1;
  max-width: calc(var(--space-8) * 3);
  transition: width var(--duration-enter) var(--ease-out-expo);
}

.mc-progress-bar span {
  font-size: var(--text-xs);
  color: var(--text-muted);
  white-space: nowrap;
}

.mc-footer {
  display: flex;
  gap: var(--space-5);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-light);
}

.mc-footer-stat {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.mc-footer-stat svg { color: var(--lumi-primary); }
</style>
