<script setup lang="ts">
import { computed, ref } from 'vue'
import { Heart, Download, Check, Loader2, RefreshCw, Trash2, AlertCircle } from 'lucide-vue-next'
import type { MarketplaceItem, InstallProgress } from '../../types/marketplace'
import { useMarketplaceStore } from '../../stores/marketplace'
import { useApi } from '../../composables/useApi'

const props = defineProps<{
  item: MarketplaceItem
  size?: 'normal' | 'large'
}>()

const store = useMarketplaceStore()
const api = useApi()

const loading = ref(false)
const error = ref<string | null>(null)

const progress = computed<InstallProgress | undefined>(() =>
  store.getInstallProgress(props.item.id)
)

const isOperating = computed(() =>
  progress.value && ['downloading', 'installing', 'updating'].includes(progress.value.status)
)

// 格式化下载速度
const formatSpeed = (bytesPerSec: number): string => {
  if (bytesPerSec <= 0) return ''
  if (bytesPerSec < 1024) return `${bytesPerSec.toFixed(0)} B/s`
  if (bytesPerSec < 1024 * 1024) return `${(bytesPerSec / 1024).toFixed(1)} KB/s`
  return `${(bytesPerSec / 1024 / 1024).toFixed(1)} MB/s`
}

async function handleInstall() {
  loading.value = true
  error.value = null
  try {
    // 先调用后端 API
    const result = await api.apiPost<InstallProgress>('/marketplace/install', {
      itemId: props.item.id,
      itemType: props.item.type,
      itemName: props.item.name,
      version: props.item.version,
      downloadUrl: props.item.versions?.[0]?.downloadUrl || '',
    })

    // 用后端返回的状态更新 store
    store.setInstallProgress(props.item.id, result)

    // 开始轮询进度
    store.startProgressPolling(props.item.id)
  } catch (e: unknown) {
    error.value = (e instanceof Error ? e.message : String(e)) || '安装请求失败'
    store.setInstallProgress(props.item.id, { itemId: props.item.id, status: 'error', progress: 0, error: error.value ?? undefined })
  } finally {
    loading.value = false
  }
}

async function handleUninstall() {
  loading.value = true
  error.value = null
  try {
    await api.apiPost('/marketplace/uninstall', { itemId: props.item.id })
    store.uninstallItem(props.item.id)
  } catch (e: unknown) {
    error.value = (e instanceof Error ? e.message : String(e)) || '卸载失败'
    // 保持当前安装状态不变
  } finally {
    loading.value = false
  }
}

function handleUpdate() {
  store.updateItem(props.item.id)
}

function handleFavorite() {
  store.toggleFavorite(props.item.id)
}

function handleRetry() {
  error.value = null
  handleInstall()
}
</script>

<template>
  <div class="install-actions">
    <button
      :class="['fav-action-btn', { active: item.isFavorite }]"
      aria-label="收藏"
      @click="handleFavorite"
    >
      <Heart :size="size === 'large' ? 18 : 16" />
    </button>

    <!-- 错误提示 -->
    <div v-if="error" class="install-error-inline">
      <AlertCircle :size="12" />
      <button class="retry-inline-btn" @click="handleRetry">
        <RefreshCw :size="10" />
      </button>
    </div>

    <template v-if="item.installStatus === 'installed'">
      <button class="action-btn uninstall-btn" :disabled="loading" @click="handleUninstall">
        <Trash2 :size="size === 'large' ? 16 : 14" />
        <span>卸载</span>
      </button>
      <button v-if="item.latestVersion && item.latestVersion !== item.version" class="action-btn update-btn" @click="handleUpdate">
        <RefreshCw :size="size === 'large' ? 16 : 14" />
        <span>更新</span>
      </button>
      <button class="action-btn installed-btn" disabled>
        <Check :size="size === 'large' ? 16 : 14" />
        <span>已安装 v{{ item.version }}</span>
      </button>
    </template>

    <template v-else-if="isOperating">
      <button class="action-btn operating-btn" disabled>
        <Loader2 :size="size === 'large' ? 16 : 14" class="spin-animation" />
        <span>{{ progress?.message || '处理中...' }}</span>
        <span v-if="progress" class="progress-pct">{{ Math.round(progress.progress) }}%</span>
      </button>
      <span v-if="progress?.speed" class="speed-label">{{ formatSpeed(progress.speed) }}</span>
    </template>

    <template v-else-if="error">
      <button class="action-btn retry-action-btn" @click="handleRetry">
        <RefreshCw :size="size === 'large' ? 16 : 14" />
        <span>重试</span>
      </button>
    </template>

    <template v-else>
      <button class="action-btn install-btn" :disabled="loading" @click="handleInstall">
        <Download v-if="!loading" :size="size === 'large' ? 16 : 14" />
        <Loader2 v-else :size="size === 'large' ? 16 : 14" class="spin-animation" />
        <span>{{ loading ? '请求中...' : '安装' }}</span>
      </button>
    </template>
  </div>
</template>

<style scoped>
.install-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.fav-action-btn {
  width: calc(var(--space-8) - var(--space-1) / 2);
  height: calc(var(--space-8) - var(--space-1) / 2);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-fast);
}

.fav-action-btn:hover {
  border-color: var(--lumi-accent);
  color: var(--lumi-accent);
  background: var(--lumi-accent-light);
}

.fav-action-btn.active {
  color: var(--lumi-accent);
  border-color: var(--lumi-accent);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-5);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  transition: all var(--transition-fast);
}

.install-btn {
  color: var(--text-inverse);
  background: var(--lumi-brand);
}

.install-btn:hover:not(:disabled) {
  background: var(--lumi-brand-hover);
}

.retry-action-btn {
  color: var(--lumi-accent);
  background: var(--lumi-accent-light);
  border: 1px solid var(--lumi-accent);
}

.retry-action-btn:hover {
  background: var(--lumi-accent);
  color: var(--text-inverse);
}

.installed-btn {
  color: var(--lumi-success);
  background: var(--lumi-success-light);
}

.update-btn {
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  border: 1px solid var(--lumi-brand);
}

.update-btn:hover {
  background: var(--lumi-brand);
  color: var(--text-inverse);
}

.uninstall-btn {
  color: var(--text-muted);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
}

.uninstall-btn:hover:not(:disabled) {
  border-color: var(--lumi-accent);
  color: var(--lumi-accent);
  background: var(--lumi-accent-light);
}

.operating-btn {
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  border: 1px solid var(--lumi-brand);
  cursor: not-allowed;
  opacity: 0.85;
}

.progress-pct {
  font-size: var(--text-xs);
  opacity: 0.7;
}

.speed-label {
  font-size: var(--text-2xs);
  color: var(--lumi-brand);
  font-weight: var(--font-medium);
}

.install-error-inline {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--lumi-accent);
}

.retry-inline-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-5);
  height: var(--space-5);
  border-radius: var(--radius-sm);
  color: var(--lumi-accent);
  transition: all var(--transition-fast);
}

.retry-inline-btn:hover {
  background: var(--lumi-accent);
  color: var(--text-inverse);
}

</style>
