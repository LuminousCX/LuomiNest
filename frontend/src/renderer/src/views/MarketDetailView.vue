<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft, Star, Download, Users, Tag,
  ExternalLink, Check, FileText, ChevronDown,
  ChevronRight, AlertCircle, RefreshCw, Trash2,
  Loader2, Image, X, Heart,
} from 'lucide-vue-next'
import { useMarketplaceStore } from '../stores/marketplace'
import { useRepoSourceStore } from '../stores/repo-source'
import { useApi } from '../composables/useApi'
import MarketplaceReviews from '../components/marketplace/MarketplaceReviews.vue'
import type { MarketplaceType, MarketplaceItem, InstallProgress } from '../types/marketplace'
import { formatDateRelative, formatFileSize, formatDownloadCount } from '../utils/format'
import { ITEM_ICON_MAP, DEFAULT_ICON } from '../utils/marketplace-icons'

const route = useRoute()
const router = useRouter()
const store = useMarketplaceStore()
const repoSourceStore = useRepoSourceStore()
const api = useApi()

const activeTab = ref<'info' | 'versions' | 'reviews'>('info')
const expandedVersion = ref<string | null>(null)
const screenshotModal = ref<number | null>(null)

// 安装/下载状态
const installLoading = ref(false)
const uninstallLoading = ref(false)
const installError = ref<string | null>(null)
const errorType = ref<'install' | 'uninstall'>('install')
const downloadProgress = ref<InstallProgress | null>(null)
let progressTimer: ReturnType<typeof setInterval> | null = null

const VALID_TYPES: MarketplaceType[] = ['plugin', 'skill', 'agent']

const itemType = computed<MarketplaceType>(() => {
  const t = route.params.type as string
  return VALID_TYPES.includes(t as MarketplaceType) ? (t as MarketplaceType) : 'plugin'
})

const itemId = computed(() => route.params.id as string)

// 优先从远程数据中查找，否则从本地 mock 数据查找
const item = computed<MarketplaceItem | undefined>(() => {
  // 先从远程数据中查找
  const remoteItems = repoSourceStore.activeSourceItems
  const remoteItem = remoteItems.find(i => i.id === itemId.value && i.type === itemType.value)
  if (remoteItem) return remoteItem

  // 回退到本地数据
  return store.getItemByTypeAndId(itemType.value, itemId.value)
})

const itemReviews = computed(() => store.getItemReviews(itemId.value))

const downloadDisplay = computed(() => {
  if (!item.value) return ''
  return formatDownloadCount(item.value.downloadCount)
})

// 格式化下载速度
const formatSpeed = (bytesPerSec: number): string => {
  if (bytesPerSec <= 0) return ''
  if (bytesPerSec < 1024) return `${bytesPerSec.toFixed(0)} B/s`
  if (bytesPerSec < 1024 * 1024) return `${(bytesPerSec / 1024).toFixed(1)} KB/s`
  return `${(bytesPerSec / 1024 / 1024).toFixed(1)} MB/s`
}

// 格式化剩余时间
const formatEta = (seconds: number): string => {
  if (seconds <= 0) return ''
  if (seconds < 60) return `${Math.round(seconds)}秒`
  if (seconds < 3600) return `${Math.round(seconds / 60)}分钟`
  return `${Math.round(seconds / 3600)}小时`
}

// 安装状态
const installStatus = computed(() => {
  if (downloadProgress.value) {
    const s = downloadProgress.value.status
    if (s === 'downloading' || s === 'installing' || s === 'updating') return s
    if (s === 'error') return 'error'
  }
  return item.value?.installStatus || 'none'
})

function goBack() {
  router.push('/market')
}

function toggleVersion(version: string) {
  expandedVersion.value = expandedVersion.value === version ? null : version
}

const formatSize = (bytes: number) => formatFileSize(bytes)
const formatDate = (dateStr: string) => formatDateRelative(dateStr)

// 轮询下载进度
function startProgressPolling(id: string) {
  stopProgressPolling()
  progressTimer = setInterval(async () => {
    try {
      const result = await api.apiGet<InstallProgress>(`/marketplace/download-progress/${id}`)
      downloadProgress.value = result
      if (result.status === 'installed' || result.status === 'error') {
        stopProgressPolling()
        if (result.status === 'installed') {
          // 通过 store 方法更新状态，避免直接修改 computed 派生值
          const storeItem = store.getItemByTypeAndId(itemType.value, itemId.value)
          if (storeItem) {
            storeItem.installStatus = 'installed'
            storeItem.downloadCount += 1
          }
          // 同步后端统计数据 + 排行榜
          store.syncAllStats()
          setTimeout(() => {
            downloadProgress.value = null
          }, 2000)
        }
        if (result.status === 'error') {
          installError.value = result.error || result.message || '安装失败'
        }
      }
    } catch {
      stopProgressPolling()
    }
  }, 500)
}

function stopProgressPolling() {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

// 安装
async function handleInstall() {
  if (!item.value) return
  const downloadUrl = item.value.versions?.[0]?.downloadUrl
  if (!downloadUrl) {
    installError.value = '此条目没有可用的下载地址'
    return
  }
  installLoading.value = true
  installError.value = null

  try {
    const result = await api.apiPost<InstallProgress>('/marketplace/install', {
      itemId: item.value.id,
      itemType: item.value.type,
      itemName: item.value.name,
      version: item.value.version,
      downloadUrl,
    })

    downloadProgress.value = result
    startProgressPolling(item.value.id)
  } catch (e: any) {
    installError.value = e.message || '安装请求失败'
    errorType.value = 'install'
  } finally {
    installLoading.value = false
  }
}

// 卸载
async function handleUninstall() {
  if (!item.value) return
  uninstallLoading.value = true
  installError.value = null

  try {
    await api.apiPost('/marketplace/uninstall', { itemId: item.value.id })
    // 通过 store 统一更新状态，确保所有页面一致
    store.uninstallItem(item.value.id)
    // 同时更新当前详情页的 item（可能来自 repoSourceStore）
    if (item.value) {
      item.value.installStatus = 'none'
    }
    downloadProgress.value = null
  } catch (e: any) {
    installError.value = e.message || '卸载失败'
    errorType.value = 'uninstall'
  } finally {
    uninstallLoading.value = false
  }
}

// 重试
async function handleRetry() {
  installError.value = null
  downloadProgress.value = null
  if (errorType.value === 'uninstall') {
    await handleUninstall()
  } else {
    await handleInstall()
  }
}

// 截图模态框
function openScreenshot(index: number) {
  screenshotModal.value = index
}

function closeScreenshot() {
  screenshotModal.value = null
}

// 喜欢
const likeLoading = ref(false)

async function handleToggleLike() {
  if (!item.value || likeLoading.value) return
  likeLoading.value = true
  try {
    await store.toggleLike(item.value.id, item.value.type)
  } finally {
    likeLoading.value = false
  }
}

const likeDisplay = computed(() => {
  if (!item.value) return 0
  return item.value.likeCount || 0
})

onMounted(async () => {
  // 检查当前条目的安装状态
  try {
    const result = await api.apiGet<{ status: string }>(`/marketplace/install-status/${itemId.value}`)
    if (result.status === 'installed' && item.value) {
      item.value.installStatus = 'installed'
    }
  } catch {
    // 忽略
  }
  // 同步统计数据（下载计数、喜欢计数、排行榜）
  await store.syncAllStats()
})

onUnmounted(() => {
  stopProgressPolling()
})
</script>

<template>
  <div v-if="item" class="market-detail-view">
    <div class="detail-topbar animate-fade-in">
      <button class="back-btn" @click="goBack">
        <ArrowLeft :size="18" />
        <span>{{ itemType === 'plugin' ? '插件市场' : itemType === 'skill' ? '技能市场' : '智能体市场' }}</span>
      </button>
    </div>

    <div class="detail-content">
      <!-- Hero 区域 -->
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
              @click="handleToggleLike"
              :disabled="likeLoading"
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
              :style="{ '--tag-color': tag.color || '#6b7280' }"
            >{{ tag.name }}</span>
          </div>

          <!-- 安装/卸载按钮区域 -->
          <div class="hero-actions">
            <!-- 错误提示 -->
            <div v-if="installError" class="install-error">
              <AlertCircle :size="14" />
              <span>{{ installError }}</span>
              <button class="retry-btn" @click="handleRetry">
                <RefreshCw :size="12" />
                {{ errorType === 'uninstall' ? '重试卸载' : '重试安装' }}
              </button>
            </div>

            <!-- 下载进度条 -->
            <div
              v-if="downloadProgress && ['downloading', 'installing', 'updating'].includes(downloadProgress.status)"
              class="download-progress-bar"
            >
              <div class="progress-info">
                <span class="progress-message">
                  <Loader2 :size="13" class="spin-icon" />
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

            <!-- 已安装状态 -->
            <template v-if="installStatus === 'installed'">
              <button class="action-btn installed-btn" disabled>
                <Check :size="16" />
                <span>已安装 v{{ item.version }}</span>
              </button>
              <button
                class="action-btn uninstall-btn"
                :disabled="uninstallLoading"
                @click="handleUninstall"
              >
                <Trash2 v-if="!uninstallLoading" :size="14" />
                <Loader2 v-else :size="14" class="spin-icon" />
                <span>{{ uninstallLoading ? '卸载中...' : '卸载' }}</span>
              </button>
            </template>

            <!-- 安装中/下载中 -->
            <template v-else-if="installStatus === 'downloading' || installStatus === 'installing' || installStatus === 'updating'">
              <button class="action-btn operating-btn" disabled>
                <Loader2 :size="14" class="spin-icon" />
                <span>{{ downloadProgress?.message || '处理中...' }}</span>
              </button>
            </template>

            <!-- 错误状态 -->
            <template v-else-if="installStatus === 'error'">
              <button class="action-btn install-btn" @click="handleRetry">
                <RefreshCw :size="14" />
                <span>{{ errorType === 'uninstall' ? '重试卸载' : '重试安装' }}</span>
              </button>
            </template>

            <!-- 未安装状态 -->
            <template v-else>
              <button
                class="action-btn install-btn"
                :disabled="installLoading"
                @click="handleInstall"
              >
                <Download v-if="!installLoading" :size="14" />
                <Loader2 v-else :size="14" class="spin-icon" />
                <span>{{ installLoading ? '请求中...' : '安装' }}</span>
              </button>
            </template>
          </div>
        </div>
      </div>

      <!-- 截图区域 -->
      <div v-if="item.screenshots && item.screenshots.length > 0" class="detail-screenshots animate-slide-up">
        <h3 class="section-title">截图预览</h3>
        <div class="screenshots-grid">
          <div
            v-for="(shot, idx) in item.screenshots"
            :key="idx"
            class="screenshot-thumb"
            @click="openScreenshot(idx)"
          >
            <img :src="shot.url" :alt="shot.caption || `截图 ${idx + 1}`" loading="lazy" />
            <div class="screenshot-overlay">
              <Image :size="20" />
            </div>
          </div>
        </div>
      </div>

      <!-- 标签页 -->
      <div class="detail-tabs">
        <button
          :class="['tab-btn', { active: activeTab === 'info' }]"
          @click="activeTab = 'info'"
        >
          <FileText :size="15" />
          详情
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'versions' }]"
          @click="activeTab = 'versions'"
        >
          <Tag :size="15" />
          版本 ({{ item.versions?.length || 0 }})
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'reviews' }]"
          @click="activeTab = 'reviews'"
        >
          <Star :size="15" />
          评价 ({{ item.ratingCount || 0 }})
        </button>
      </div>

      <div class="detail-body">
        <Transition name="tab-switch" mode="out-in">
          <!-- 详情 Tab -->
          <div v-if="activeTab === 'info'" key="info" class="tab-content">
            <div class="info-section">
              <h3 class="info-title">详细介绍</h3>
              <p class="info-text">{{ item.description || item.summary }}</p>
            </div>

            <div class="info-section">
              <h3 class="info-title">信息</h3>
              <div class="info-grid">
                <div class="info-item">
                  <span class="info-label">版本</span>
                  <span class="info-value">v{{ item.version }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">大小</span>
                  <span class="info-value">{{ formatSize(item.size) }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">许可证</span>
                  <span class="info-value">{{ item.license || '未指定' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">最低版本</span>
                  <span class="info-value">{{ item.minAppVersion || '无要求' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">更新日期</span>
                  <span class="info-value">{{ formatDate(item.updatedAt) }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">创建日期</span>
                  <span class="info-value">{{ formatDate(item.createdAt) }}</span>
                </div>
              </div>
            </div>

            <div v-if="item.homepage || item.repository" class="info-section">
              <h3 class="info-title">链接</h3>
              <div class="info-links">
                <a v-if="item.homepage" :href="item.homepage" target="_blank" class="info-link">
                  <ExternalLink :size="14" />
                  主页
                </a>
                <a v-if="item.repository" :href="item.repository" target="_blank" class="info-link">
                  <ExternalLink :size="14" />
                  仓库
                </a>
              </div>
            </div>
          </div>

          <!-- 版本 Tab -->
          <div v-else-if="activeTab === 'versions'" key="versions" class="tab-content">
            <div v-if="item.versions && item.versions.length > 0" class="versions-list">
              <div
                v-for="ver in item.versions"
                :key="ver.version"
                class="version-item"
              >
                <button class="version-header" @click="toggleVersion(ver.version)">
                  <div class="version-info">
                    <span class="version-number">v{{ ver.version }}</span>
                    <span v-if="ver.version === item.version" class="version-current">当前</span>
                    <span class="version-date">{{ formatDate(ver.releasedAt) }}</span>
                  </div>
                  <div class="version-meta">
                    <span class="version-size">{{ formatSize(ver.size) }}</span>
                    <component
                      :is="expandedVersion === ver.version ? ChevronDown : ChevronRight"
                      :size="16"
                      class="version-expand"
                    />
                  </div>
                </button>
                <Transition name="expand">
                  <div v-if="expandedVersion === ver.version" class="version-changelog">
                    <p>{{ ver.changelog || '暂无更新日志' }}</p>
                  </div>
                </Transition>
              </div>
            </div>
            <div v-else class="empty-versions">
              <Tag :size="32" />
              <p>暂无版本信息</p>
            </div>
          </div>

          <!-- 评价 Tab -->
          <div v-else-if="activeTab === 'reviews'" key="reviews" class="tab-content">
            <MarketplaceReviews :item-id="itemId" :reviews="itemReviews" />
          </div>
        </Transition>
      </div>
    </div>

    <!-- 截图模态框 -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="screenshotModal !== null && item.screenshots?.[screenshotModal]" class="screenshot-modal" @click="closeScreenshot">
          <div class="modal-content" @click.stop>
            <button class="modal-close" @click="closeScreenshot">
              <X :size="20" />
            </button>
            <img :src="item.screenshots[screenshotModal].url" :alt="item.screenshots[screenshotModal].caption" />
            <div class="modal-caption">
              {{ item.screenshots[screenshotModal].caption || `截图 ${screenshotModal + 1}` }}
              <span class="modal-counter">{{ screenshotModal + 1 }} / {{ item.screenshots.length }}</span>
            </div>
            <div class="modal-nav">
              <button v-if="screenshotModal > 0" class="nav-btn prev" @click.stop="screenshotModal!--">
                <ChevronDown :size="20" style="transform: rotate(90deg)" />
              </button>
              <button v-if="screenshotModal < item.screenshots.length - 1" class="nav-btn next" @click.stop="screenshotModal++">
                <ChevronDown :size="20" style="transform: rotate(-90deg)" />
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>

  <div v-else class="detail-not-found">
    <p>未找到该商品</p>
    <button class="back-btn" @click="goBack">返回市场</button>
  </div>
</template>

<style scoped>
.market-detail-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.detail-topbar {
  display: flex;
  align-items: center;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.back-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
}

/* Hero */
.detail-hero {
  display: flex;
  gap: 24px;
  margin-bottom: 28px;
}

.hero-icon {
  width: 80px;
  height: 80px;
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
  gap: 10px;
  margin-bottom: 4px;
}

.hero-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.verified-badge {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 600;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.hero-author {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.hero-summary {
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 14px;
}

.hero-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 14px;
}

.hero-stat {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
}

.hero-stat .star-icon {
  color: var(--lumi-star);
}

.hero-like-btn {
  cursor: pointer;
  padding: 2px 8px;
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
  font-weight: 600;
  color: var(--text-primary);
}

.stat-label {
  color: var(--text-muted);
  font-size: 12px;
}

.hero-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.detail-tag {
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 500;
  background: color-mix(in srgb, var(--tag-color) 10%, transparent);
  color: var(--tag-color);
}

/* 安装/卸载按钮区域 */
.hero-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
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

.spin-icon {
  animation: lumi-spin 1s linear infinite;
}

@keyframes lumi-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 错误提示 */
.install-error {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--lumi-accent);
  background: var(--lumi-accent-light);
  width: 100%;
}

.retry-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 500;
  color: var(--lumi-accent);
  transition: all var(--transition-fast);
}

.retry-btn:hover {
  background: var(--lumi-accent);
  color: var(--text-inverse);
}

/* 下载进度条 */
.download-progress-bar {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-message {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.progress-stats {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 11px;
  color: var(--text-muted);
}

.progress-speed {
  color: var(--lumi-primary);
  font-weight: 500;
}

.progress-track {
  height: 6px;
  border-radius: 3px;
  background: var(--border-light);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
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

/* 截图区域 */
.detail-screenshots {
  margin-bottom: 24px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.screenshots-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.screenshot-thumb {
  position: relative;
  aspect-ratio: 16/10;
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-fast);
}

.screenshot-thumb:hover {
  border-color: var(--lumi-primary);
  box-shadow: var(--shadow-sm);
}

.screenshot-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.screenshot-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
  color: white;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.screenshot-thumb:hover .screenshot-overlay {
  opacity: 1;
}

/* 截图模态框 */
.screenshot-modal {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.85);
  animation: lumi-fade-in 0.2s ease-out;
}

.modal-content {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.modal-content img {
  max-width: 100%;
  max-height: 80vh;
  border-radius: var(--radius-lg);
  object-fit: contain;
}

.modal-close {
  position: absolute;
  top: -40px;
  right: 0;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: all var(--transition-fast);
}

.modal-close:hover {
  background: rgba(255, 255, 255, 0.2);
}

.modal-caption {
  margin-top: 12px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  display: flex;
  align-items: center;
  gap: 12px;
}

.modal-counter {
  font-size: 11px;
  opacity: 0.5;
}

.modal-nav {
  position: absolute;
  top: 50%;
  left: -50px;
  right: -50px;
  display: flex;
  justify-content: space-between;
  transform: translateY(-50%);
  pointer-events: none;
}

.nav-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  background: rgba(255, 255, 255, 0.15);
  pointer-events: auto;
  transition: all var(--transition-fast);
}

.nav-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* Tabs */
.detail-tabs {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--workspace-panel);
  border-radius: var(--radius-lg);
  margin-bottom: 20px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.tab-btn:hover {
  color: var(--text-secondary);
}

.tab-btn.active {
  background: var(--workspace-card);
  color: var(--text-primary);
  box-shadow: var(--shadow-xs);
}

.detail-body {
  min-height: 200px;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.info-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.info-text {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
}

.info-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.info-links {
  display: flex;
  gap: 12px;
}

.info-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  transition: all var(--transition-fast);
}

.info-link:hover {
  background: var(--lumi-primary);
  color: var(--text-inverse);
}

/* Versions */
.versions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.version-item {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.version-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 14px 18px;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.version-header:hover {
  background: var(--surface-hover);
}

.version-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.version-number {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.version-current {
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 600;
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.version-date {
  font-size: 12px;
  color: var(--text-muted);
}

.version-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.version-size {
  font-size: 12px;
  color: var(--text-muted);
}

.version-expand {
  color: var(--text-muted);
}

.version-changelog {
  padding: 0 18px 14px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.empty-versions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px 0;
  color: var(--text-muted);
}

.empty-versions p {
  font-size: 13px;
}

/* Transitions */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease-in-out;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.tab-switch-enter-active {
  animation: lumi-fade-in 0.2s ease-out;
}

.tab-switch-leave-active {
  animation: lumi-fade-in 0.1s ease-out reverse;
}

.modal-enter-active {
  animation: lumi-fade-in 0.2s ease-out;
}

.modal-leave-active {
  animation: lumi-fade-in 0.15s ease-out reverse;
}

.detail-not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
  color: var(--text-muted);
}

.detail-not-found .back-btn {
  color: var(--lumi-primary);
}
</style>
