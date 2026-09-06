<script setup lang="ts">
import {
  RotateCcw,
  Maximize2,
  Download,
  Settings2,
  Volume2,
  Type,
  Monitor,
  MonitorOff,
  Loader
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'

const props = defineProps<{
  isDesktopMode: boolean
  isSwitchingMode: boolean
  ttsEnabled: boolean
  subtitleEnabled: boolean
}>()

const emit = defineEmits<{
  'toggle-desktop-mode': []
  'reset-pose': []
  'toggle-tts': []
  'toggle-subtitle': []
  'import-click': []
}>()
</script>

<template>
  <div class="avatar-header">
    <div class="avatar-header__left">
      <h1 class="avatar-title">皮套工坊</h1>
      <p class="avatar-desc">Live2D 形象管理、动作编辑与场景配置</p>
    </div>
    <div class="avatar-header__actions">
      <div
        class="desktop-mode-toggle"
        :class="{ active: props.isDesktopMode, switching: props.isSwitchingMode }"
        @click="emit('toggle-desktop-mode')"
        :title="props.isSwitchingMode ? 'Switching...' : (props.isDesktopMode ? 'Switch to Inline Mode' : 'Switch to Desktop Mode')"
      >
        <component :is="props.isSwitchingMode ? Loader : (props.isDesktopMode ? Monitor : MonitorOff)" :size="16" :class="{ spin: props.isSwitchingMode }" />
        <span class="toggle-label">{{ props.isSwitchingMode ? '...' : (props.isDesktopMode ? 'Desktop' : 'Inline') }}</span>
      </div>
      <div class="header-divider"></div>
      <LumiButton variant="ghost" size="sm" icon-only aria-label="Reset Pose" @click="emit('reset-pose')">
        <template #icon><RotateCcw :size="16" /></template>
      </LumiButton>
      <LumiButton variant="ghost" size="sm" icon-only aria-label="Fullscreen">
        <template #icon><Maximize2 :size="16" /></template>
      </LumiButton>
      <LumiButton
        :variant="props.ttsEnabled ? 'outline' : 'ghost'"
        size="sm"
        icon-only
        aria-label="Toggle TTS"
        @click="emit('toggle-tts')"
      >
        <template #icon><Volume2 :size="16" /></template>
      </LumiButton>
      <LumiButton
        :variant="props.subtitleEnabled ? 'outline' : 'ghost'"
        size="sm"
        icon-only
        aria-label="Subtitle"
        @click="emit('toggle-subtitle')"
      >
        <template #icon><Type :size="16" /></template>
      </LumiButton>
      <LumiButton variant="primary" size="sm" @click="emit('import-click')">
        <template #icon><Download :size="16" /></template>
        <span>Import</span>
      </LumiButton>
      <LumiButton variant="ghost" size="sm" icon-only aria-label="Settings">
        <template #icon><Settings2 :size="16" /></template>
      </LumiButton>
    </div>
  </div>
</template>

<style scoped>
.avatar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-7);
  flex-shrink: 0;
  background: transparent !important;
}

.avatar-header__left {
  display: flex;
  flex-direction: column;
}

.avatar-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  line-height: 1.2;
}

.avatar-desc {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.avatar-header__actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.desktop-mode-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-muted);
  background: var(--surface-hover);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-in-out);
  user-select: none;
}

.desktop-mode-toggle:hover {
  color: var(--text);
  background: var(--surface);
  border-color: var(--lumi-brand);
}

.desktop-mode-toggle.active {
  background: var(--lumi-brand-glow);
  color: var(--lumi-brand);
  border: 1px solid var(--lumi-brand-border);
}

.desktop-mode-toggle.switching {
  opacity: 0.6;
  cursor: wait;
  pointer-events: none;
}

.desktop-mode-toggle .spin {
  animation: spin var(--duration-normal) linear infinite;
}



.toggle-label {
  font-weight: var(--font-semibold);
}

.header-divider {
  width: 1px;
  height: var(--space-5);
  background: var(--divider-soft);
  margin: 0 var(--space-1);
}
</style>
