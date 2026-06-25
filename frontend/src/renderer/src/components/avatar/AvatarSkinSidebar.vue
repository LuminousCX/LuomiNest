<script setup lang="ts">
import {
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Check,
  Palette,
  FolderOpen
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import type { SkinItem } from './types'

const props = defineProps<{
  skinSidebarVisible: boolean
  importError: string | null
  showImportSuccess: boolean
  skinList: SkinItem[]
  selectedSkin: number
}>()

const emit = defineEmits<{
  'toggle-sidebar': []
  'skin-select': [index: number]
  'import-click': []
}>()
</script>

<template>
  <div :class="['skin-sidebar', { 'sidebar-collapsed': !props.skinSidebarVisible }, 'animate-slide-right']">
    <button class="sidebar-toggle" @click="emit('toggle-sidebar')" :title="props.skinSidebarVisible ? 'Hide Library' : 'Show Library'">
      <component :is="props.skinSidebarVisible ? ChevronRight : ChevronLeft" :size="14" />
    </button>

    <template v-if="props.skinSidebarVisible">
      <div class="sidebar-title">Avatar Library</div>

      <div v-if="props.importError" class="import-error">
        <AlertCircle :size="14" />
        <span>{{ props.importError }}</span>
      </div>

      <div v-if="props.showImportSuccess" class="import-success">
        <Check :size="14" />
        <span>Model imported successfully</span>
      </div>

      <div class="skin-list custom-scrollbar--thin">
        <div
          v-for="(skin, idx) in props.skinList"
          :key="idx"
          :class="['skin-card', { selected: props.selectedSkin === idx }]"
          @click="emit('skin-select', idx)"
        >
          <div class="skin-thumb">
            <Palette :size="18" />
          </div>
          <div class="skin-info">
            <div class="skin-name-row">
              <span class="skin-name">{{ skin.name }}</span>
              <span class="skin-type">{{ skin.type }}</span>
            </div>
            <div class="skin-tags">
              <span v-for="tag in skin.tags" :key="tag" class="skin-tag">{{ tag }}</span>
            </div>
          </div>
        </div>
      </div>

      <LumiButton variant="outline" size="sm" block @click="emit('import-click')">
        <template #icon><FolderOpen :size="14" /></template>
        <span>Import .model3.json</span>
      </LumiButton>
    </template>
  </div>
</template>

<style scoped>
.skin-sidebar {
  width: 230px;
  padding: var(--space-4) var(--space-3);
  overflow-y: auto;
  overflow-x: hidden;
  flex-shrink: 0;
  background: var(--surface);
  position: relative;
  display: flex;
  flex-direction: column;
  transition: width var(--duration-normal) var(--ease-in-out), padding var(--duration-normal) var(--ease-in-out);
}

.skin-sidebar.sidebar-collapsed {
  width: 36px;
  padding: var(--space-5) 6px;
  overflow: hidden;
}

.skin-sidebar::before {
  content: '';
  position: absolute;
  top: var(--space-4);
  bottom: var(--space-4);
  left: 0;
  width: 1px;
  background: var(--divider-vertical);
}

.sidebar-toggle {
  position: absolute;
  top: 50%;
  left: -12px;
  transform: translateY(-50%);
  width: var(--space-6);
  height: var(--space-6);
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface);
  border: 1px solid var(--border-light);
  color: var(--text-muted);
  cursor: pointer;
  z-index: 10;
  transition: all var(--duration-normal) var(--ease-in-out);
}

.sidebar-toggle:hover {
  background: var(--surface-hover);
  color: var(--lumi-primary);
  border-color: var(--lumi-primary);
}

.sidebar-title {
  font-size: var(--text-base);
  font-weight: 600;
  margin-bottom: var(--space-3);
  color: var(--text);
  letter-spacing: 0.3px;
}

.import-error {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  background: var(--task-red-soft);
  color: var(--lumi-danger);
  font-size: var(--text-xs);
  margin-bottom: 10px;
}

.import-success {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  background: var(--task-green-soft);
  color: var(--lumi-success);
  font-size: var(--text-xs);
  margin-bottom: 10px;
  animation: fade-in var(--duration-normal) var(--ease-in-out);
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

.skin-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
  overflow-y: auto;
  margin-right: 2px;
  padding-right: 2px;
}

.skin-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-in-out);
}

.skin-card:hover {
  background: var(--surface-hover);
  border-color: var(--lumi-primary-border);
}

.skin-card.selected {
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary);
}

.skin-thumb {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-sm);
  background: var(--surface-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  flex-shrink: 0;
}

.skin-info {
  display: flex;
  flex-direction: column;
  gap: 5px;
  flex: 1;
  min-width: 0;
}

.skin-name-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.skin-name {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text);
  line-height: 1.2;
}

.skin-type {
  font-size: var(--text-xs);
  color: var(--text-muted);
  opacity: 0.75;
  line-height: 1.2;
}

.skin-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.skin-tag {
  font-size: var(--text-2xs);
  padding: 1px 5px;
  border-radius: var(--radius-xs);
  background: var(--surface-hover);
  color: var(--text-muted);
  line-height: 1.4;
}

.import-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: var(--space-2) 14px;
  border-radius: var(--radius-md);
  border: 1px dashed var(--border-light);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-in-out);
  font-size: var(--text-sm);
  margin-top: var(--space-3);
  flex-shrink: 0;
}

.import-btn:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-subtle);
}

@keyframes slide-right {
  0% { opacity: 0; transform: translateX(30px); }
  100% { opacity: 1; transform: translateX(0); }
}

.animate-slide-right {
  animation: slide-right 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}
</style>
