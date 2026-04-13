<script setup lang="ts">
import { ArrowLeft, ArrowRight, RotateCw, Star, Search, Code2 } from 'lucide-vue-next'

defineProps<{
  url: string
  canGoBack?: boolean
  canGoForward?: boolean
  showDevPanel?: boolean
}>()

const emit = defineEmits<{
  back: []
  forward: []
  refresh: []
  navigate: [url: string]
  toggleDevPanel: []
}>()

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    const target = e.target as HTMLInputElement
    emit('navigate', target.value)
  }
}
</script>

<template>
  <div class="nav-bar">
    <div class="nav-buttons">
      <button class="nav-btn" :disabled="!canGoBack" @click="emit('back')">
        <ArrowLeft :size="16" />
      </button>
      <button class="nav-btn" :disabled="!canGoForward" @click="emit('forward')">
        <ArrowRight :size="16" />
      </button>
      <button class="nav-btn" @click="emit('refresh')">
        <RotateCw :size="14" />
      </button>
    </div>
    
    <div class="address-bar">
      <Search :size="15" class="addr-icon" />
      <input
        :value="url"
        type="text"
        class="addr-input"
        placeholder="搜索或输入网址"
        @keydown="handleKeydown"
      />
    </div>
    
    <div class="nav-right">
      <button class="nav-btn">
        <Star :size="15" />
      </button>
      <button 
        :class="['nav-btn', 'dev-toggle', { active: showDevPanel }]"
        @click="emit('toggleDevPanel')"
      >
        <Code2 :size="15" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.nav-bar {
  height: 52px;
  background: #ffffff;
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 12px;
  position: relative;
}

.nav-bar::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 12px;
  right: 12px;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, #e7e5e4 15%, #e7e5e4 85%, transparent 100%);
}

.nav-buttons {
  display: flex;
  gap: 4px;
}

.nav-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  color: #78716c;
  transition: all 0.15s ease-in-out;
}

.nav-btn:hover:not(:disabled) {
  background: #f5f5f4;
  color: #44403c;
}

.nav-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.nav-btn.dev-toggle.active {
  background: #e7e5e4;
  color: #44403c;
}

.address-bar {
  flex: 1;
  display: flex;
  align-items: center;
  height: 34px;
  background: #f5f5f4;
  border-radius: var(--radius-xl);
  padding: 0 12px;
  gap: 8px;
}

.address-bar:focus-within {
  background: #ffffff;
  box-shadow: 0 0 0 2px #d6d3d1;
}

.addr-icon {
  color: #a8a29e;
  flex-shrink: 0;
}

.addr-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 13px;
  color: #44403c;
  outline: none;
}

.addr-input::placeholder {
  color: #a8a29e;
}

.nav-right {
  display: flex;
  gap: 4px;
}
</style>
