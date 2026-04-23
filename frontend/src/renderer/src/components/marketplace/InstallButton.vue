<script setup lang="ts">
import { computed } from 'vue'
import { Download, Loader2, Check, AlertCircle } from 'lucide-vue-next'
import type { MarketItem, InstallStatus } from '../../types/marketplace'

const props = defineProps<{
  item: MarketItem
}>()

const emit = defineEmits<{
  install: [itemId: string]
  uninstall: [itemId: string]
}>()

const statusConfig: Record<InstallStatus, { label: string; icon: any; class: string }> = {
  idle: { label: '安装', icon: Download, class: 'install' },
  downloading: { label: '下载中', icon: Loader2, class: 'downloading' },
  installing: { label: '安装中', icon: Loader2, class: 'installing' },
  installed: { label: '已安装', icon: Check, class: 'installed' },
  error: { label: '安装失败', icon: AlertCircle, class: 'error' }
}

const config = computed(() => statusConfig[props.item.installStatus])
const isProcessing = computed(() => props.item.installStatus === 'downloading' || props.item.installStatus === 'installing')

function handleClick() {
  if (isProcessing.value) return
  if (props.item.isInstalled) {
    emit('uninstall', props.item.id)
  } else {
    emit('install', props.item.id)
  }
}
</script>

<template>
  <div class="install-button-wrapper">
    <button
      :class="['install-btn', config.class, { processing: isProcessing }]"
      :disabled="isProcessing"
      @click="handleClick"
    >
      <component :is="config.icon" :size="16" :class="{ spinning: isProcessing }" />
      <span>{{ config.label }}</span>
    </button>
    <div v-if="item.installStatus === 'downloading'" class="progress-bar">
      <div class="progress-fill" :style="{ width: item.downloadProgress + '%' }"></div>
    </div>
  </div>
</template>

<style scoped>
.install-button-wrapper {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.install-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 20px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  min-width: 100px;
}

.install-btn.install {
  background: var(--lumi-primary);
  color: white;
}

.install-btn.install:hover {
  background: var(--lumi-primary-hover);
  box-shadow: var(--shadow-glow-sm);
}

.install-btn.downloading,
.install-btn.installing {
  background: var(--bg-secondary);
  color: var(--text-secondary);
  cursor: not-allowed;
}

.install-btn.installed {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.install-btn.installed:hover {
  background: rgba(244, 63, 94, 0.1);
  color: var(--lumi-accent);
}

.install-btn.error {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.progress-bar {
  height: 3px;
  background: var(--bg-secondary);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--lumi-primary);
  border-radius: 2px;
  transition: width 0.2s ease;
}
</style>
