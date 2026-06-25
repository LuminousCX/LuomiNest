<script setup lang="ts">
import { Sun, Moon } from 'lucide-vue-next'
import { useThemeStore } from '../../stores/theme'
import type { SectionItem } from './types'

defineProps<{
  section: string
  items: SectionItem[]
}>()

const themeStore = useThemeStore()
</script>

<template>
  <div class="setting-items-card animate-slide-up">
    <div
      v-for="(item, idx) in items"
      :key="item.label"
      :class="['setting-row', { last: idx === items.length - 1 }]"
    >
      <div class="row-info">
        <span class="row-label">{{ item.label }}</span>
        <span class="row-desc">{{ item.desc }}</span>
      </div>
      <div class="row-control">
        <div v-if="item.type === 'toggle' && item.label === '动画效果'" class="toggle-switch" :class="{ on: true }">
          <span class="toggle-thumb" />
        </div>
        <div v-else-if="item.type === 'select' && section === 'appearance' && item.label === '主题模式'" class="theme-mode-selector">
          <button
            :class="['theme-option', { active: !themeStore.isDark }]"
            @click="themeStore.setTheme(false)"
          >
            <Sun :size="14" />
            <span>浅色</span>
          </button>
          <button
            :class="['theme-option', { active: themeStore.isDark }]"
            @click="themeStore.setTheme(true)"
          >
            <Moon :size="14" />
            <span>深色</span>
          </button>
        </div>
        <div v-else-if="item.type === 'select'" class="control-select">
          <span class="control-placeholder">请选择</span>
        </div>
        <div v-else-if="item.type === 'input'" class="control-input">
          <span class="control-placeholder">点击输入</span>
        </div>
        <div v-else-if="item.type === 'slider'" class="control-slider">
          <div class="slider-track" />
        </div>
        <div v-else-if="item.type === 'connect'" class="control-connect">
          <span class="connect-btn">连接</span>
        </div>
        <div v-else class="control-default">
          <span class="control-placeholder">配置</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.setting-items-card {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  max-width: 640px;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-4);
  border-bottom: 1px solid var(--workspace-border);
  transition: background var(--transition-fast);
}

.setting-row.last {
  border-bottom: none;
}

.setting-row:hover {
  background: var(--workspace-hover);
}

.row-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.row-label {
  font-size: var(--text-md);
  font-weight: 500;
  color: var(--text-primary);
}

.row-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.row-control {
  flex-shrink: 0;
  margin-left: var(--space-4);
}

.toggle-switch {
  width: var(--space-9);
  height: var(--space-6);
  border-radius: var(--radius-md);
  background: var(--workspace-border);
  position: relative;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.toggle-switch.on {
  background: var(--lumi-primary);
}

.toggle-thumb {
  position: absolute;
  top: var(--space-1);
  left: var(--space-1);
  width: var(--space-4);
  height: var(--space-4);
  border-radius: var(--radius-full);
  background: var(--surface);
  box-shadow: 0 1px var(--space-1) var(--overlay-subtle);
  transition: all var(--transition-fast);
}

.toggle-switch.on .toggle-thumb {
  left: 23px;
}

.theme-mode-selector {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-1);
  border-radius: var(--radius-sm);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
}

.theme-option {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-xs);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-muted);
  background: transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
  border: none;
}

.theme-option.active {
  background: var(--workspace-card);
  color: var(--text-primary);
  box-shadow: var(--shadow-xs);
}

.control-select,
.control-input,
.control-default {
  padding: var(--space-2) var(--space-3);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-sm);
}

.control-placeholder {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.control-slider {
  width: 120px;
  height: var(--space-2);
}

.slider-track {
  width: 100%;
  height: var(--space-2);
  border-radius: var(--space-1);
  background: var(--workspace-border);
  position: relative;
}

.slider-track::after {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 60%;
  height: 100%;
  border-radius: var(--space-1);
  background: var(--lumi-primary);
}

.control-connect {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-light);
}

.connect-btn {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--lumi-primary);
}
</style>
