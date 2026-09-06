<script setup lang="ts">
import { computed } from 'vue'
import {
  Star, Download, Users,
  Check, AlertCircle, RefreshCw, Trash2,
  Loader2, Heart,
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import type { MarketplaceItem, InstallProgress } from '../../types/marketplace'
import { formatDownloadCount, formatSpeed } from '../../utils/format'
import { ITEM_ICON_MAP, DEFAULT_ICON } from '../../utils/marketplace-icons'

const props = defineProps<{
  item: MarketplaceItem
  installStatus: string
  installLoading: boolean
  uninstallLoading: boolean
  installError: string | null
  errorType: 'install' | 'uninstall'
  downloadProgress: InstallProgress | null
  likeLoading: boolean
}>()

const emit = defineEmits<{
  install: []
  uninstall: []
  retry: []
  toggleLike: []
}>()

const downloadDisplay = computed(() => {
  return formatDownloadCount(props.item.downloadCount)
})

const likeDisplay = computed(() => {
  return props.item.likeCount || 0
})

const formatEta = (seconds: number): string => {
  if (seconds <= 0) return ''
  if (seconds < 60) return `${Math.round(seconds)}秒`
  if (seconds < 3600) return `${Math.round(seconds / 60)}分钟`
  return `${Math.round(seconds / 3600)}小时`
}
</script>

<template>
  <div class="detail-hero animate-slide-up">
    <div class="hero-icon">
      <component :is="ITEM_ICON_MAP[item.icon] || DEFAULT_ICON" :size="40" />
    </div>
    <div class="hero-info">
      <div class="hero-title-row">
        <h1 class="hero-title">{{ item.name }}</h1>
        <span v-if="item.author?.verified" class="verified-badge">
          <Check :size="12" />
          认证
        </span>
      </div>
      <p class="hero-author">by {{ item.author?.name || '未知' }}</p>
      <p class="hero-summary">{{ item.summary }}</p>
      <div class="hero-stats">
        <div class="hero-stat">
          <Star :size="14" class="star-icon" />
          <span class="stat-value">{{ item.rating.toFixed(1) }}</span>
          <span class="stat-label">({{ item.ratingCount || 0 }})</span>
        </div>
        <div class="hero-stat">
          <Download :size="14" />
          <span class="stat-value">{{ downloadDisplay }}</span>
          <span class="stat-label">下载</span>
        </div>
        <div class="hero-stat">
          <Users :size="14" />
          <span class="stat-value">{{ item.installedCount }}</span>
          <span class="stat-label">安装</span>
        </div>
        <button
          :class="['hero-stat', 'hero-like-btn', { liked: item.isLiked }]"
          :disabled="likeLoading"
          @click="emit('toggleLike')"
        >
          <Heart :size="14" :fill="item.isLiked ? 'currentColor' : 'none'" />
          <span class="stat-value">{{ likeDisplay }}</span>
          <span class="stat-label">喜欢</span>
        </button>
      </div>
      <div class="hero-tags">
        <span
          v-for="tag in item.tags"
          :key="tag.id"
          class="detail-tag"
          :style="{ '--tag-color': tag.color || 'var(--text-muted)' }"
        >{{ tag.name }}</span>
      </div>

      <div class="hero-actions">
        <div v-if="installError" class="install-error">
          <AlertCircle :size="14" />
          <span>{{ installError }}</span>
          <LumiButton variant="outline" size="sm" @click="emit('retry')">
            <template #icon>
              <RefreshCw :size="12" />
            </template>
            {{ errorType === 'uninstall' ? '重试卸载' : '重试安装' }}
          </LumiButton>
        </div>

        <div
          v-if="downloadProgress && ['downloading', 'installing', 'updating'].includes(downloadProgress.status)"
          class="download-progress-bar"
        >
          <div class="progress-info">
            <span class="progress-message">
              <Loader2 :size="13" class="spin-animation" />
              {{ downloadProgress.message || (downloadProgress.status === 'downloading' ? '正在下载...' : '正在安装...') }}
            </span>
            <span class="progress-stats">
              <span v-if="downloadProgress.speed" class="progress-speed">{{ formatSpeed(downloadProgress.speed) }}</span>
              <span v-if="downloadProgress.eta" class="progress-eta">剩余 {{ formatEta(downloadProgress.eta) }}</span>
              <span class="progress-pct">{{ Math.round(downloadProgress.progress) }}%</span>
            </span>
          </div>
          <div class="progress-track">
            <div
              class="progress-fill"
              :class="downloadProgress.status"
              :style="{ width: downloadProgress.progress + '%' }"
            ></div>
          </div>
        </div>

        <template v-if="installStatus === 'installed'">
          <button class="action-btn installed-btn" disabled>
            <Check :size="16" />
            <span>已安装 v{{ item.version }}</span>
          </button>
          <button
            class="action-btn uninstall-btn"
            :disabled="uninstallLoading"
            @click="emit('uninstall')"
          >
            <Trash2 v-if="!uninstallLoading" :size="14" />
            <Loader2 v-else :size="14" class="spin-animation" />
            <span>{{ uninstallLoading ? '卸载中...' : '卸载' }}</span>
          </button>
        </template>

        <template v-else-if="installStatus === 'downloading' || installStatus === 'installing' || installStatus === 'updating'">
          <button class="action-btn operating-btn" disabled>
            <Loader2 :size="14" class="spin-animation" />
            <span>{{ downloadProgress?.message || '处理中...' }}</span>
          </button>
        </template>

        <template v-else-if="installStatus === 'error'">
          <button class="action-btn install-btn" @click="emit('retry')">
            <RefreshCw :size="14" />
            <span>{{ errorType === 'uninstall' ? '重试卸载' : '重试安装' }}</span>
          </button>
        </template>

        <template v-else>
          <button
            class="action-btn install-btn"
            :disabled="installLoading"
            @click="emit('install')"
          >
            <Download v-if="!installLoading" :size="14" />
            <Loader2 v-else :size="14" class="spin-animation" />
            <span>{{ installLoading ? '请求中...' : '安装' }}</span>
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.detail-hero {
  display: flex;
  gap: var(--space-6);
  margin-bottom: var(--space-7);
}

.hero-icon {
  width: calc(var(--space-8) * 2);
  height: calc(var(--space-8) * 2);
  border-radius: var(--radius-xl);
  background: var(--workspace-panel);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
  flex-shrink: 0;
}

.hero-info {
  flex: 1;
  min-width: 0;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-1);
}

.hero-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.verified-badge {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-full);
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.hero-author {
  font-size: var(--text-base);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.hero-summary {
  font-size: var(--text-md);
  color: var(--text-muted);
  margin-bottom: var(--space-3);
}

.hero-stats {
  display: flex;
  gap: var(--space-5);
  margin-bottom: var(--space-3);
}

.hero-stat {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-base);
}

.hero-stat .star-icon {
  color: var(--lumi-warning);
}

.hero-like-btn {
  cursor: pointer;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
  color: var(--text-muted);
}

.hero-like-btn:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.hero-like-btn.liked {
  color: var(--lumi-accent);
}

.stat-value {
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.stat-label {
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.hero-tags {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}

.detail-tag {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  background: color-mix(in srgb, var(--tag-color) 10%, transparent);
  color: var(--tag-color);
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
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
  background: var(--lumi-primary);
}

.install-btn:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.installed-btn {
  color: var(--lumi-success);
  background: var(--lumi-success-light);
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
  color: var(--text-secondary);
  background: var(--workspace-panel);
  cursor: not-allowed;
}

.install-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--lumi-accent);
  background: var(--lumi-accent-light);
  width: 100%;
}

.install-error .lumi-btn {
  margin-left: auto;
}

.download-progress-bar {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-message {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.progress-stats {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.progress-speed {
  color: var(--lumi-primary);
  font-weight: var(--font-medium);
}

.progress-track {
  height: 6px;
  border-radius: var(--radius-xs);
  background: var(--border-light);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: var(--radius-xs);
  transition: width var(--transition-slow);
}

.progress-fill.downloading {
  background: var(--lumi-primary);
}

.progress-fill.installing {
  background: var(--lumi-warning);
}

.progress-fill.updating {
  background: var(--lumi-primary);
}
</style>