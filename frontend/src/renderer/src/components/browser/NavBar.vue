<script setup lang="ts">
import { ArrowLeft, ArrowRight, RotateCw, Search, Camera, Square } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  url: string
  canGoBack?: boolean
  canGoForward?: boolean
  /** 当前标签页是否加载中（加载中显示停止按钮） */
  loading?: boolean
}>()

const emit = defineEmits<{
  back: []
  forward: []
  refresh: []
  stop: []
  navigate: [url: string]
  screenshot: []
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
      <button v-if="loading" class="nav-btn" :aria-label="t('browser.actions.stopLoad')" @click="emit('stop')">
        <Square :size="13" />
      </button>
      <button v-else class="nav-btn" @click="emit('refresh')">
        <RotateCw :size="14" />
      </button>
    </div>

    <div class="address-bar">
      <Search :size="15" class="addr-icon" />
      <input
        :value="url"
        type="text"
        class="addr-input"
        :placeholder="t('browser.addressPlaceholder')"
        @keydown="handleKeydown"
      />
    </div>

    <div class="nav-right">
      <button class="nav-btn" :aria-label="t('browser.screenshotTitle')" @click="emit('screenshot')">
        <Camera :size="15" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.nav-bar {
  height: calc(var(--space-9) + var(--space-1));
  background: var(--surface);
  display: flex;
  align-items: center;
  padding: 0 var(--space-3);
  gap: var(--space-3);
  position: relative;
}

.nav-bar::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: var(--space-3);
  right: var(--space-3);
  height: 1px;
  background: var(--divider-soft);
}

.nav-buttons {
  display: flex;
  gap: var(--space-1);
}

.nav-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: calc(var(--space-7) + var(--space-1));
  height: calc(var(--space-7) + var(--space-1));
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.nav-btn:hover:not(:disabled) {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.nav-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.address-bar {
  flex: 1;
  display: flex;
  align-items: center;
  height: var(--btn-height-md);
  background: var(--bg-secondary);
  border-radius: var(--radius-xl);
  padding: 0 var(--space-3);
  gap: var(--space-2);
}

.address-bar:focus-within {
  background: var(--surface);
  box-shadow: 0 0 0 calc(var(--space-1) / 2) var(--border);
}

.addr-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.addr-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: var(--text-base);
  color: var(--text-secondary);
  outline: none;
}

.addr-input::placeholder {
  color: var(--text-muted);
}

.nav-right {
  display: flex;
  gap: var(--space-1);
}

</style>
