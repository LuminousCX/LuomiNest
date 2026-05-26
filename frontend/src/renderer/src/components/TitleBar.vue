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
        <span class="brand-text">LuomiNest</span>
        <span class="brand-sub">LuminousChenXi v0.1.0</span>
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
  height: 34px;
  background: var(--surface);
  box-shadow: var(--shadow-xs);
  -webkit-app-region: drag;
  user-select: none;
  flex-shrink: 0;
  position: relative;
  z-index: 100;
}

.title-drag-region {
  display: flex;
  align-items: center;
  padding-left: 14px;
  gap: 8px;
  flex: 1;
  min-width: 0;
  height: 100%;
}

.brand-mark {
  display: flex;
  align-items: center;
  gap: 7px;
  -webkit-app-region: no-drag;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast);
}

.brand-mark:hover {
  background: var(--surface-hover);
}

.brand-text {
  font-size: 12.5px;
  font-weight: 700;
  letter-spacing: -0.2px;
  background: linear-gradient(135deg, var(--lumi-primary), var(--lumi-primary-soft));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  white-space: nowrap;
}

.brand-sub {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted);
  white-space: nowrap;
  margin-left: 4px;
}

.win-controls {
  display: flex;
  height: 100%;
  -webkit-app-region: no-drag;
}

.ctrl-btn {
  width: 46px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
  outline: none;
}

.ctrl-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.ctrl-btn.close:hover {
  background: #e5484d;
  color: #ffffff;
}

.ctrl-btn:active {
  transform: scale(0.92);
}
</style>
