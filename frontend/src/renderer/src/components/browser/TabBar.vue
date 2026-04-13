<script setup lang="ts">
import { X, Globe, Loader2, Moon } from 'lucide-vue-next'

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
    <div class="tab-list">
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
        <span>+</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.tab-bar {
  height: 38px;
  background: #f5f5f4;
  display: flex;
  align-items: center;
  padding: 0 8px;
  position: relative;
}

.tab-bar::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 8px;
  right: 8px;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, #e7e5e4 15%, #e7e5e4 85%, transparent 100%);
}

.tab-list {
  display: flex;
  align-items: center;
  gap: 2px;
  overflow-x: auto;
  scrollbar-width: none;
}

.tab-list::-webkit-scrollbar {
  display: none;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  min-width: 120px;
  max-width: 200px;
  height: 30px;
  background: #e7e5e4;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.15s ease-in-out, transform 0.15s ease-in-out;
}

.tab-item:hover {
  background: #d6d3d1;
}

.tab-item.active {
  background: #ffffff;
}

.tab-item.sleeping {
  opacity: 0.65;
}

.tab-item.sleeping:hover {
  opacity: 0.9;
}

.tab-item.error .tab-title {
  color: #dc2626;
}

.tab-favicon {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  flex-shrink: 0;
}

.tab-icon {
  flex-shrink: 0;
  color: #78716c;
}

.tab-sleep-icon {
  flex-shrink: 0;
  color: #a8a29e;
  animation: pulse-sleep 2s ease-in-out infinite;
}

@keyframes pulse-sleep {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.tab-spinner {
  flex-shrink: 0;
  animation: spin 1s linear infinite;
  color: #78716c;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.tab-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: #44403c;
}

.tab-title-sleeping {
  color: #a8a29e;
  font-style: italic;
}

.tab-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 3px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: #78716c;
  flex-shrink: 0;
  transition: all 0.15s ease-in-out;
}

.tab-close:hover {
  background: rgba(0, 0, 0, 0.1);
  color: #44403c;
}

.tab-add {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  color: #78716c;
  font-size: 16px;
  transition: all 0.2s ease-in-out;
}

.tab-add:hover {
  background: #d6d3d1;
  color: #44403c;
}
</style>
