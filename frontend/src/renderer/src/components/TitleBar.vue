<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Minus, Square, X, Minimize2 } from 'lucide-vue-next'
import LumiBrandStar from './common/LumiBrandStar.vue'

const isMaximized = ref(false)

const handleMinimize = async () => {
  if (window.api) await window.api.window.minimize()
}

const handleMaximize = async () => {
  if (window.api) {
    await window.api.window.maximize()
    isMaximized.value = await window.api.window.isMaximized()
  }
}

const handleClose = async () => {
  if (window.api) await window.api.window.close()
}

const checkMaximized = async () => {
  if (window.api) isMaximized.value = await window.api.window.isMaximized()
}

onMounted(() => {
  checkMaximized()
  window.addEventListener('resize', checkMaximized)
})

onUnmounted(() => window.removeEventListener('resize', checkMaximized))
</script>

<template>
  <header class="lumi-title-bar">
    <div class="title-drag-region">
      <div class="brand-mark">
        <LumiBrandStar :size="16" :animated="false" />
        <span class="brand-text lumi-gradient-text">LuomiNest</span>
        <span class="brand-sub">LuminousChenXi v0.5.0</span>
      </div>
    </div>
    <div class="win-controls">
      <button class="ctrl-btn minimize" aria-label="最小化" @click="handleMinimize">
        <Minus :size="13" />
      </button>
      <button class="ctrl-btn maximize" :aria-label="isMaximized ? '还原' : '最大化'" @click="handleMaximize">
        <Square v-if="!isMaximized" :size="11" />
        <Minimize2 v-else :size="13" />
      </button>
      <button class="ctrl-btn close" aria-label="关闭" @click="handleClose">
        <X :size="13" />
      </button>
    </div>
  </header>
</template>

<style scoped>
.lumi-title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--btn-height-md);
  background: var(--surface);
  border-bottom: 1px solid var(--border-light);
  box-shadow: var(--shadow-xs);
  -webkit-app-region: drag;
  user-select: none;
  flex-shrink: 0;
  position: relative;
  z-index: var(--z-sticky);
}

.title-drag-region {
  display: flex;
  align-items: center;
  padding-left: var(--space-4);
  gap: var(--space-2);
  flex: 1;
  min-width: 0;
  height: 100%;
}

.brand-mark {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  -webkit-app-region: no-drag;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  transition: background-color var(--transition-fast);
}

.brand-mark:hover {
  background: var(--surface-hover);
}

.brand-text {
  font-size: var(--text-sm);
  font-weight: var(--font-bold);
  letter-spacing: -0.2px;
  white-space: nowrap;
}

.brand-sub {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-muted);
  white-space: nowrap;
  margin-left: var(--space-1);
}

.win-controls {
  display: flex;
  height: 100%;
  -webkit-app-region: no-drag;
}

.ctrl-btn {
  width: calc(var(--space-9) - 2px);
  height: var(--btn-height-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition:
    background-color var(--transition-fast),
    color var(--transition-fast),
    transform var(--transition-fast);
  outline: none;
}

.ctrl-btn:focus-visible {
  background: var(--surface-hover);
  box-shadow: inset 0 0 0 1px var(--focus-ring);
}

.ctrl-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.ctrl-btn.close:hover {
  background: var(--lumi-danger);
  color: var(--text-inverse);
}

.ctrl-btn:active {
  transform: scale(0.92);
}

</style>
