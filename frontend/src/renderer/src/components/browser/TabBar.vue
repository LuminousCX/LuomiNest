<script setup lang="ts">
import { X, Globe, Loader2, Moon, Plus } from 'lucide-vue-next'

interface Tab {
  id: string
  title: string
  url: string
  favicon?: string
  loading?: boolean
  error?: { title: string; message: string }
  active?: boolean
  sleeping?: boolean
}

defineProps<{
  tabs: Tab[]
}>()

const emit = defineEmits<{
  select: [tabId: string]
  close: [tabId: string]
  add: []
}>()

function getTabTooltip(tab: Tab): string {
  if (tab.sleeping) {
    return `${tab.title}\n此标签页已进入休眠状态以节省资源，点击即可唤醒`
  }
  return tab.title
}
</script>

<template>
  <div class="tab-bar">
    <div class="tab-list custom-scrollbar--thin">
      <div
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-item', { active: tab.active, error: tab.error, sleeping: tab.sleeping }]"
        :title="getTabTooltip(tab)"
        @click="emit('select', tab.id)"
      >
        <Loader2 v-if="tab.loading" :size="12" class="tab-spinner" />
        <Moon v-else-if="tab.sleeping" :size="12" class="tab-sleep-icon" />
        <img v-else-if="tab.favicon" :src="tab.favicon" class="tab-favicon" alt="" />
        <Globe v-else-if="tab.url" :size="12" class="tab-icon" />
        <span class="tab-title" :class="{ 'tab-title-sleeping': tab.sleeping }">{{ tab.title }}</span>
        <button class="tab-close" @click.stop="emit('close', tab.id)">
          <X :size="12" />
        </button>
      </div>
      <button class="tab-add" @click="emit('add')">
        <Plus :size="16" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.tab-bar {
  height: calc(var(--space-8) - 2px);
  background: var(--bg-secondary);
  display: flex;
  align-items: center;
  padding: 0 var(--space-2);
  position: relative;
}

.tab-bar::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: var(--space-2);
  right: var(--space-2);
  height: 1px;
  background: var(--divider-soft);
}

.tab-list {
  display: flex;
  align-items: center;
  gap: calc(var(--space-1) / 2);
  overflow-x: auto;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  min-width: calc(var(--space-9) * 2 + var(--space-6));
  max-width: calc(var(--space-9) * 4 + var(--space-2));
  height: calc(var(--space-7) - 2px);
  background: var(--border-light);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast), transform var(--transition-fast);
}

.tab-item:hover {
  background: var(--surface-hover);
}

.tab-item.active {
  background: var(--surface);
}

.tab-item.sleeping {
  opacity: 0.65;
}

.tab-item.sleeping:hover {
  opacity: 0.9;
}

.tab-item.error .tab-title {
  color: var(--lumi-danger);
}

.tab-favicon {
  width: var(--space-3);
  height: var(--space-3);
  border-radius: calc(var(--space-1) / 2);
  flex-shrink: 0;
}

.tab-icon {
  flex-shrink: 0;
  color: var(--text-muted);
}

.tab-sleep-icon {
  flex-shrink: 0;
  color: var(--text-muted);
  animation: pulse-sleep calc(var(--duration-normal) * 8) var(--ease-in-out) infinite;
}

@keyframes pulse-sleep {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.tab-spinner {
  flex-shrink: 0;
  animation: spin calc(var(--duration-normal) * 4) linear infinite;
  color: var(--text-muted);
}

.tab-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.tab-title-sleeping {
  color: var(--text-muted);
  font-style: italic;
}

.tab-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-4);
  height: var(--space-4);
  border-radius: calc(var(--space-1) - 1px);
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  flex-shrink: 0;
  transition: all var(--transition-fast);
}

.tab-close:hover {
  background: var(--overlay-subtle);
  color: var(--text-secondary);
}

.tab-add {
  display: flex;
  align-items: center;
  justify-content: center;
  width: calc(var(--space-6) + var(--space-1));
  height: calc(var(--space-6) + var(--space-1));
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  font-size: var(--text-xl);
  transition: all var(--transition-fast);
}

.tab-add:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

</style>
