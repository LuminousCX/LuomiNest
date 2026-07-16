<script setup lang="ts">
import {
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Check,
  Palette,
  FolderOpen,
  Layers,
  Box,
  Ghost,
  Bone,
  Image
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import type { ManifestSkinItem } from './types'
import type { AvatarRendererType } from '@/types/avatar'

const props = defineProps<{
  skinSidebarVisible: boolean
  importError: string | null
  showImportSuccess: boolean
  skinList: ManifestSkinItem[]
  selectedSkin: number
  currentMode: string
  modelCountByType: Record<AvatarRendererType, number>
}>()

const emit = defineEmits<{
  'toggle-sidebar': []
  'skin-select': [index: number]
  'import-click': []
  'switch-mode': [modeId: string]
}>()

// 模型类型标签配置（与 AVATAR_MODEL_TYPES 对齐）
const TYPE_TABS: Array<{ type: AvatarRendererType; label: string; icon: typeof Palette }> = [
  { type: 'live2d', label: 'Live2D', icon: Palette },
  { type: 'pixel', label: 'Pixel', icon: Ghost },
  { type: 'vrm', label: 'VRM', icon: Box },
  { type: 'spine', label: 'Spine', icon: Bone },
  { type: 'png', label: 'PNG', icon: Image },
]

// 类型标签显示文本
const TYPE_LABELS: Record<AvatarRendererType, string> = {
  live2d: 'Live2D',
  vrm: 'VRM',
  pixel: 'PixelPet',
  spine: 'Spine',
  png: 'PNG Tuber',
}
</script>

<template>
  <div :class="['skin-sidebar', { 'sidebar-collapsed': !props.skinSidebarVisible }, 'animate-slide-right']">
    <button class="sidebar-toggle" @click="emit('toggle-sidebar')" :title="props.skinSidebarVisible ? 'Hide Library' : 'Show Library'">
      <component :is="props.skinSidebarVisible ? ChevronRight : ChevronLeft" :size="14" />
    </button>

    <template v-if="props.skinSidebarVisible">
      <div class="sidebar-title">
        <Layers :size="14" />
        <span>Avatar Library</span>
      </div>

      <!-- 模型类型切换标签 -->
      <div class="type-tabs">
        <button
          v-for="tab in TYPE_TABS"
          :key="tab.type"
          :class="['type-tab', { active: props.currentMode === tab.type }]"
          :title="TYPE_LABELS[tab.type]"
          @click="emit('switch-mode', tab.type)"
        >
          <component :is="tab.icon" :size="12" />
          <span class="type-tab-label">{{ tab.label }}</span>
          <span v-if="props.modelCountByType[tab.type]" class="type-tab-count">{{ props.modelCountByType[tab.type] }}</span>
        </button>
      </div>

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
          :key="skin.id"
          :class="['skin-card', { selected: props.selectedSkin === idx }]"
          @click="emit('skin-select', idx)"
        >
          <div class="skin-thumb">
            <Palette :size="18" />
          </div>
          <div class="skin-info">
            <div class="skin-name-row">
              <span class="skin-name">{{ skin.name }}</span>
              <span class="skin-type">{{ TYPE_LABELS[skin.type] }}</span>
            </div>
            <div class="skin-tags">
              <span class="skin-tag source-tag" :class="skin.source">{{ skin.source }}</span>
              <span v-for="tag in skin.tags" :key="tag" class="skin-tag">{{ tag }}</span>
            </div>
            <!-- 能力摘要 -->
            <div class="skin-caps">
              <span v-if="skin.capabilities.expressionCount > 0" class="cap-badge" title="Expressions">
                {{ skin.capabilities.expressionCount }} exp
              </span>
              <span v-if="skin.capabilities.motionCount > 0" class="cap-badge" title="Motions">
                {{ skin.capabilities.motionCount }} mot
              </span>
              <span v-if="skin.capabilities.stateCount > 0" class="cap-badge" title="States">
                {{ skin.capabilities.stateCount }} states
              </span>
              <span v-if="skin.capabilities.lipSync" class="cap-badge lip" title="Lip Sync">Lip</span>
              <span v-if="skin.capabilities.focusTracking" class="cap-badge focus" title="Focus Tracking">Track</span>
            </div>
          </div>
        </div>

        <!-- 空列表提示 -->
        <div v-if="props.skinList.length === 0" class="empty-list-hint">
          <Palette :size="24" />
          <span>当前类型暂无模型</span>
        </div>
      </div>

      <LumiButton variant="outline" size="sm" block @click="emit('import-click')">
        <template #icon><FolderOpen :size="14" /></template>
        <span>Import Model</span>
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
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-base);
  font-weight: 600;
  margin-bottom: var(--space-2);
  color: var(--text);
  letter-spacing: 0.3px;
}

.type-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: var(--space-3);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--divider-soft);
}

.type-tab {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-in-out);
  font-size: var(--text-2xs);
  font-weight: 500;
}

.type-tab:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.type-tab.active {
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.type-tab-label {
  line-height: 1;
}

.type-tab-count {
  padding: 0 4px;
  border-radius: var(--radius-xs);
  background: var(--overlay-subtle);
  font-size: 9px;
  font-weight: 600;
  min-width: 14px;
  text-align: center;
  line-height: 1.4;
}

.type-tab.active .type-tab-count {
  background: var(--lumi-primary-subtle);
  color: var(--lumi-primary);
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
  gap: 4px;
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

.skin-tag.source-tag.builtin {
  background: var(--lumi-primary-subtle);
  color: var(--lumi-primary);
}

.skin-tag.source-tag.imported {
  background: var(--task-amber-soft, var(--overlay-subtle));
  color: var(--lumi-amber-dark, var(--text-muted));
}

.skin-caps {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: 2px;
}

.cap-badge {
  font-size: 9px;
  padding: 1px 4px;
  border-radius: var(--radius-xs);
  background: var(--surface-hover);
  color: var(--text-muted);
  font-weight: 500;
  line-height: 1.4;
}

.cap-badge.lip {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.cap-badge.focus {
  background: var(--lumi-primary-subtle);
  color: var(--lumi-primary);
}

.empty-list-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-6) var(--space-2);
  color: var(--text-muted);
  font-size: var(--text-xs);
  text-align: center;
  opacity: 0.6;
}

@keyframes slide-right {
  0% { opacity: 0; transform: translateX(30px); }
  100% { opacity: 1; transform: translateX(0); }
}

.animate-slide-right {
  animation: slide-right 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}
</style>
