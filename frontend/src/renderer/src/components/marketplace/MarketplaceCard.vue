<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Star, Download, Heart, Check, Loader2 } from 'lucide-vue-next'
import type { MarketplaceItem, InstallProgress } from '../../types/marketplace'
import { useMarketplaceStore } from '../../stores/marketplace'
import { useApi } from '../../composables/useApi'
import { formatDownloadCount } from '../../utils/format'
import { ITEM_ICON_MAP, DEFAULT_ICON } from '../../utils/marketplace-icons'
import LumiCardIcon from '../common/LumiCardIcon.vue'
import LumiCard from '../common/LumiCard.vue'

const props = defineProps<{
  item: MarketplaceItem
}>()

const router = useRouter()
const store = useMarketplaceStore()
const api = useApi()

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

const downloadDisplay = computed(() => formatDownloadCount(props.item.downloadCount))

function navigateToDetail() {
  router.push(`/market/detail/${props.item.type}/${props.item.id}`)
}

const isInstalling = ref(false)

function handleInstall(e: Event) {
  e.stopPropagation()
  if (isInstalling.value) return
  isInstalling.value = true
  // 调用真实后端安装接口
  api.apiPost<InstallProgress>('/marketplace/install', {
    itemId: props.item.id,
    itemType: props.item.type,
    itemName: props.item.name,
    version: props.item.version,
    downloadUrl: props.item.versions?.[0]?.downloadUrl || '',
  }).then(result => {
    store.setInstallProgress(props.item.id, result)
    // 启动轮询
    store.startProgressPolling(props.item.id)
    // 同时直接更新当前 item 的状态（可能来自 repoSourceStore）
    props.item.installStatus = 'installing'
  }).catch(() => {
    // 安装请求失败，忽略
  }).finally(() => {
    isInstalling.value = false
  })
}

function handleLike(e: Event) {
  e.stopPropagation()
  store.toggleLike(props.item.id, props.item.type)
}

const likeDisplay = computed(() => formatDownloadCount(props.item.likeCount || 0))
</script>

<template>
  <LumiCard class="market-card" hoverable padding="lg" @click="navigateToDetail">
    <div class="card-header">
      <LumiCardIcon
        :icon="ITEM_ICON_MAP[item.icon] || DEFAULT_ICON"
        :size="24"
        :theme="item.icon"
      />
      <div class="card-badge-area">
        <span v-if="item.featured" class="badge badge-featured">推荐</span>
        <span v-if="item.installStatus === 'installed'" class="badge badge-installed">已安装</span>
      </div>
    </div>

    <div class="card-body">
      <h3 class="card-title">{{ item.name }}</h3>
      <p class="card-summary line-clamp-2">{{ item.summary }}</p>
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
        <div class="stat">
          <Heart :size="13" class="stat-icon like" :fill="item.isLiked ? 'currentColor' : 'none'" />
          <span>{{ likeDisplay }}</span>
        </div>
      </div>

      <div class="card-actions">
        <button
          :class="['fav-btn', { active: item.isLiked }]"
          aria-label="喜欢"
          @click="handleLike"
        >
          <Heart :size="15" :fill="item.isLiked ? 'currentColor' : 'none'" />
        </button>

        <button
          v-if="item.installStatus !== 'installed'"
          :class="['install-btn', { operating: isOperating }]"
          :disabled="isOperating"
          @click="handleInstall"
        >
          <Loader2 v-if="isOperating" :size="14" class="spin-animation" />
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
  </LumiCard>
</template>

<style scoped>
.market-card {
  cursor: pointer;
  transition: all var(--transition-normal);
}

.market-card:hover {
  border-color: var(--lumi-brand);
  box-shadow: var(--shadow-md), 0 0 0 1px var(--lumi-brand-glow);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.card-badge-area {
  display: flex;
  gap: var(--space-2);
}

.badge {
  padding: calc(var(--space-1) / 2) var(--space-2);
  border-radius: var(--radius-full);
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
}

.badge-featured {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.badge-installed {
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.card-body {
  flex: 1;
  margin-bottom: var(--space-3);
}

.card-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-2);
  line-height: var(--leading-snug);
}

.card-summary {
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: var(--leading-normal);
  margin-bottom: var(--space-2);
}

.card-author {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.author-name {
  font-size: var(--text-2xs);
  color: var(--text-secondary);
}

.verified-icon {
  color: var(--lumi-brand);
}

.card-tags {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}

.tag {
  padding: calc(var(--space-1) / 2) var(--space-2);
  border-radius: var(--radius-full);
  font-size: var(--text-2xs);
  font-weight: var(--font-medium);
  background: color-mix(in srgb, var(--tag-color) 10%, transparent);
  color: var(--tag-color);
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-light);
}

.card-stats {
  display: flex;
  gap: var(--space-3);
}

.stat {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.stat-icon.star {
  color: var(--lumi-warning);
}

.stat-icon.like {
  color: var(--lumi-accent);
}

.card-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.fav-btn {
  width: var(--space-7);
  height: var(--space-7);
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
  justify-content: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-inverse);
  background: var(--lumi-brand);
  transition: all var(--transition-fast);
  min-width: 64px;
  max-width: 120px;
  white-space: nowrap;
}

.install-btn:hover:not(:disabled) {
  background: var(--lumi-brand-hover);
  box-shadow: var(--shadow-sm);
}

.install-btn.operating {
  background: var(--lumi-brand);
  opacity: 0.85;
  cursor: default;
  position: relative;
  overflow: hidden;
}

.install-btn.installed {
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.progress-text {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  opacity: 0.9;
}

</style>
