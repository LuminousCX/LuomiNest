<script setup lang="ts">
import { computed } from 'vue'
import { Heart, Download, Check, Loader2, RefreshCw, Trash2 } from 'lucide-vue-next'
import type { MarketplaceItem, InstallProgress } from '../../types/marketplace'
import { useMarketplaceStore } from '../../stores/marketplace'

const props = defineProps<{
  item: MarketplaceItem
  size?: 'normal' | 'large'
}>()

const store = useMarketplaceStore()

const progress = computed<InstallProgress | undefined>(() =>
  store.getInstallProgress(props.item.id)
)

const isOperating = computed(() =>
  progress.value && ['downloading', 'installing', 'updating'].includes(progress.value.status)
)

function handleInstall() {
  store.startInstall(props.item.id)
}

function handleUninstall() {
  store.uninstallItem(props.item.id)
}

function handleUpdate() {
  store.updateItem(props.item.id)
}

function handleFavorite() {
  store.toggleFavorite(props.item.id)
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

    <template v-if="item.installStatus === 'installed'">
      <button class="action-btn uninstall-btn" @click="handleUninstall">
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
        <Loader2 :size="size === 'large' ? 16 : 14" class="spin-icon" />
        <span>{{ progress?.message || '处理中...' }}</span>
        <span v-if="progress" class="progress-pct">{{ Math.round(progress.progress) }}%</span>
      </button>
    </template>

    <template v-else>
      <button class="action-btn install-btn" @click="handleInstall">
        <Download :size="size === 'large' ? 16 : 14" />
        <span>安装</span>
      </button>
    </template>
  </div>
</template>

<style scoped>
.install-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fav-action-btn {
  width: 38px;
  height: 38px;
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
  gap: 6px;
  padding: 8px 18px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.install-btn {
  color: var(--text-inverse);
  background: var(--lumi-primary);
}

.install-btn:hover {
  background: var(--lumi-primary-hover);
}

.installed-btn {
  color: var(--lumi-success);
  background: var(--lumi-success-light);
}

.update-btn {
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  border: 1px solid var(--lumi-primary);
}

.update-btn:hover {
  background: var(--lumi-primary);
  color: var(--text-inverse);
}

.uninstall-btn {
  color: var(--text-muted);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
}

.uninstall-btn:hover {
  border-color: var(--lumi-accent);
  color: var(--lumi-accent);
  background: var(--lumi-accent-light);
}

.operating-btn {
  color: var(--text-secondary);
  background: var(--workspace-panel);
  cursor: not-allowed;
}

.progress-pct {
  font-size: 11px;
  opacity: 0.7;
}

.spin-icon {
  animation: lumi-spin 1s linear infinite;
}

@keyframes lumi-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
