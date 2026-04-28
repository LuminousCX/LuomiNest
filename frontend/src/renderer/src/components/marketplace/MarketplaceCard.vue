<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Star, Download, Heart, Check, Loader2 } from 'lucide-vue-next'
import type { MarketplaceItem, InstallProgress } from '../../types/marketplace'
import { useMarketplaceStore } from '../../stores/marketplace'

const props = defineProps<{
  item: MarketplaceItem
}>()

const router = useRouter()
const store = useMarketplaceStore()

const installProgress = computed<InstallProgress | undefined>(() =>
  store.getInstallProgress(props.item.id)
)

const isOperating = computed(() =>
  installProgress.value && ['downloading', 'installing', 'updating'].includes(installProgress.value.status)
)

const installLabel = computed(() => {
  if (!installProgress.value) {
    if (props.item.installStatus === 'installed') return '已安装'
    return '安装'
  }
  switch (installProgress.value.status) {
    case 'downloading': return '下载中'
    case 'installing': return '安装中'
    case 'updating': return '更新中'
    case 'installed': return '已完成'
    case 'error': return '失败'
    default: return '安装'
  }
})

const ratingDisplay = computed(() => props.item.rating.toFixed(1))

const downloadDisplay = computed(() => {
  const n = props.item.downloadCount
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return n.toString()
})

function navigateToDetail() {
  router.push(`/market/detail/${props.item.type}/${props.item.id}`)
}

function handleInstall(e: Event) {
  e.stopPropagation()
  store.startInstall(props.item.id)
}

function handleFavorite(e: Event) {
  e.stopPropagation()
  store.toggleFavorite(props.item.id)
}
</script>

<template>
  <div class="market-card" @click="navigateToDetail">
    <div class="card-header">
      <div class="card-icon">{{ item.icon }}</div>
      <div class="card-badge-area">
        <span v-if="item.featured" class="badge badge-featured">推荐</span>
        <span v-if="item.installStatus === 'installed'" class="badge badge-installed">已安装</span>
      </div>
    </div>

    <div class="card-body">
      <h3 class="card-title">{{ item.name }}</h3>
      <p class="card-summary">{{ item.summary }}</p>
      <div class="card-author">
        <span class="author-name">{{ item.author.name }}</span>
        <Check v-if="item.author.verified" :size="12" class="verified-icon" />
      </div>
    </div>

    <div class="card-tags">
      <span
        v-for="tag in item.tags.slice(0, 3)"
        :key="tag.id"
        class="tag"
        :style="{ '--tag-color': tag.color }"
      >{{ tag.name }}</span>
    </div>

    <div class="card-footer">
      <div class="card-stats">
        <div class="stat">
          <Star :size="13" class="stat-icon star" />
          <span>{{ ratingDisplay }}</span>
        </div>
        <div class="stat">
          <Download :size="13" class="stat-icon" />
          <span>{{ downloadDisplay }}</span>
        </div>
      </div>

      <div class="card-actions">
        <button
          :class="['fav-btn', { active: item.isFavorite }]"
          aria-label="收藏"
          @click="handleFavorite"
        >
          <Heart :size="15" />
        </button>

        <button
          v-if="item.installStatus !== 'installed'"
          :class="['install-btn', { operating: isOperating }]"
          :disabled="isOperating"
          @click="handleInstall"
        >
          <Loader2 v-if="isOperating" :size="14" class="spin-icon" />
          <span>{{ installLabel }}</span>
          <span v-if="installProgress && isOperating" class="progress-text">
            {{ Math.round(installProgress.progress) }}%
          </span>
        </button>
        <button v-else class="install-btn installed" disabled>
          <Check :size="14" />
          <span>已安装</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.market-card {
  display: flex;
  flex-direction: column;
  padding: 18px;
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.market-card:hover {
  border-color: var(--lumi-primary);
  box-shadow: var(--shadow-md), 0 0 0 1px var(--lumi-primary-glow);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 14px;
}

.card-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  background: var(--workspace-panel);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.card-badge-area {
  display: flex;
  gap: 6px;
}

.badge {
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 600;
}

.badge-featured {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.badge-installed {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.card-body {
  flex: 1;
  margin-bottom: 12px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
  line-height: 1.3;
}

.card-summary {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-author {
  display: flex;
  align-items: center;
  gap: 4px;
}

.author-name {
  font-size: 11px;
  color: var(--text-secondary);
}

.verified-icon {
  color: var(--lumi-primary);
}

.card-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.tag {
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 500;
  background: color-mix(in srgb, var(--tag-color) 10%, transparent);
  color: var(--tag-color);
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

.card-stats {
  display: flex;
  gap: 12px;
}

.stat {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.stat-icon.star {
  color: #f59e0b;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fav-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.fav-btn:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.fav-btn.active {
  color: var(--lumi-accent);
}

.install-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  color: white;
  background: var(--lumi-primary);
  transition: all var(--transition-fast);
}

.install-btn:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.install-btn.operating {
  background: var(--text-secondary);
  cursor: not-allowed;
}

.install-btn.installed {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.progress-text {
  font-size: 11px;
  opacity: 0.8;
}

.spin-icon {
  animation: lumi-spin 1s linear infinite;
}

@keyframes lumi-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
