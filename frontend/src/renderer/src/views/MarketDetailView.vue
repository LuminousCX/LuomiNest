<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Star, FileText, Tag, ArrowLeft } from 'lucide-vue-next'
import { useMarketplaceStore } from '../stores/marketplace'
import { useRepoSourceStore } from '../stores/repo-source'
import { useApi } from '../composables/useApi'
import MarketplaceReviews from '../components/marketplace/MarketplaceReviews.vue'
import LumiEmptyState from '../components/common/LumiEmptyState.vue'
import MarketDetailHeader from '../components/marketplace/MarketDetailHeader.vue'
import MarketDetailScreenshots from '../components/marketplace/MarketDetailScreenshots.vue'
import MarketDetailInfoTab from '../components/marketplace/MarketDetailInfoTab.vue'
import MarketDetailVersionsTab from '../components/marketplace/MarketDetailVersionsTab.vue'
import MarketDetailScreenshotModal from '../components/marketplace/MarketDetailScreenshotModal.vue'
import type { MarketplaceType, MarketplaceItem, InstallProgress } from '../types/marketplace'

const route = useRoute()
const router = useRouter()
const store = useMarketplaceStore()
const repoSourceStore = useRepoSourceStore()
const api = useApi()

const activeTab = ref<'info' | 'versions' | 'reviews'>('info')
const expandedVersion = ref<string | null>(null)
const screenshotModal = ref<number | null>(null)

const installLoading = ref(false)
const uninstallLoading = ref(false)
const installError = ref<string | null>(null)
const errorType = ref<'install' | 'uninstall'>('install')
const downloadProgress = ref<InstallProgress | null>(null)
let progressTimer: ReturnType<typeof setInterval> | null = null

const likeLoading = ref(false)

const VALID_TYPES: MarketplaceType[] = ['plugin', 'skill', 'agent']

const itemType = computed<MarketplaceType>(() => {
  const t = route.params.type as string
  return VALID_TYPES.includes(t as MarketplaceType) ? (t as MarketplaceType) : 'plugin'
})

const itemId = computed(() => route.params.id as string)

const item = computed<MarketplaceItem | undefined>(() => {
  const remoteItems = repoSourceStore.activeSourceItems
  const remoteItem = remoteItems.find(i => i.id === itemId.value && i.type === itemType.value)
  if (remoteItem) return remoteItem

  return store.getItemByTypeAndId(itemType.value, itemId.value)
})

const itemReviews = computed(() => store.getItemReviews(itemId.value))

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

function startProgressPolling(id: string) {
  stopProgressPolling()
  progressTimer = setInterval(async () => {
    try {
      const result = await api.apiGet<InstallProgress>(`/marketplace/download-progress/${id}`)
      downloadProgress.value = result
      if (result.status === 'installed' || result.status === 'error') {
        stopProgressPolling()
        if (result.status === 'installed') {
          const storeItem = store.getItemByTypeAndId(itemType.value, itemId.value)
          if (storeItem) {
            storeItem.installStatus = 'installed'
            storeItem.downloadCount += 1
          }
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

async function handleInstall() {
  if (!item.value) return
  const downloadUrl = item.value.versions?.[0]?.downloadUrl
  if (!downloadUrl) {
    installError.value = '此条目没有可用的下载地址'
    errorType.value = 'install'
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
  } catch (e: unknown) {
    installError.value = (e instanceof Error ? e.message : (e == null ? '' : String(e))) || '安装请求失败'
    errorType.value = 'install'
  } finally {
    installLoading.value = false
  }
}

async function handleUninstall() {
  if (!item.value) return
  uninstallLoading.value = true
  installError.value = null

  try {
    await api.apiPost('/marketplace/uninstall', { itemId: item.value.id })
    store.uninstallItem(item.value.id)
    if (item.value) {
      item.value.installStatus = 'none'
    }
    downloadProgress.value = null
  } catch (e: unknown) {
    installError.value = (e instanceof Error ? e.message : (e == null ? '' : String(e))) || '卸载失败'
    errorType.value = 'uninstall'
  } finally {
    uninstallLoading.value = false
  }
}

async function handleRetry() {
  installError.value = null
  downloadProgress.value = null
  if (errorType.value === 'uninstall') {
    await handleUninstall()
  } else {
    await handleInstall()
  }
}

function openScreenshot(index: number) {
  screenshotModal.value = index
}

function closeScreenshot() {
  screenshotModal.value = null
}

function prevScreenshot() {
  if (screenshotModal.value !== null && screenshotModal.value > 0) {
    screenshotModal.value--
  }
}

function nextScreenshot() {
  if (screenshotModal.value !== null && screenshotModal.value < (item.value?.screenshots.length || 0) - 1) {
    screenshotModal.value++
  }
}

async function handleToggleLike() {
  if (!item.value || likeLoading.value) return
  likeLoading.value = true
  try {
    await store.toggleLike(item.value.id, item.value.type)
  } finally {
    likeLoading.value = false
  }
}

onMounted(async () => {
  try {
    const result = await api.apiGet<{ status: string }>(`/marketplace/install-status/${itemId.value}`)
    if (result.status === 'installed' && item.value) {
      item.value.installStatus = 'installed'
    }
  } catch {
    // 忽略
  }
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
      <MarketDetailHeader
        :item="item"
        :install-status="installStatus"
        :install-loading="installLoading"
        :uninstall-loading="uninstallLoading"
        :install-error="installError"
        :error-type="errorType"
        :download-progress="downloadProgress"
        :like-loading="likeLoading"
        @install="handleInstall"
        @uninstall="handleUninstall"
        @retry="handleRetry"
        @toggle-like="handleToggleLike"
      />

      <MarketDetailScreenshots
        v-if="item.screenshots && item.screenshots.length > 0"
        :screenshots="item.screenshots"
        @open="openScreenshot"
      />

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
          <MarketDetailInfoTab v-if="activeTab === 'info'" key="info" :item="item" />
          <MarketDetailVersionsTab
            v-else-if="activeTab === 'versions'"
            key="versions"
            :item="item"
            :expanded-version="expandedVersion"
            @toggle-version="toggleVersion"
          />
          <div v-else-if="activeTab === 'reviews'" key="reviews" class="tab-content">
            <MarketplaceReviews :item-id="itemId" :reviews="itemReviews" />
          </div>
        </Transition>
      </div>
    </div>

    <MarketDetailScreenshotModal
      :screenshots="item.screenshots"
      :current-index="screenshotModal"
      @close="closeScreenshot"
      @prev="prevScreenshot"
      @next="nextScreenshot"
    />
  </div>

  <div v-else class="detail-not-found">
    <LumiEmptyState
      icon="file"
      title="未找到该商品"
      description="该商品可能已被移除或链接有误"
    >
      <template #action>
        <button class="back-btn" @click="goBack">返回市场</button>
      </template>
    </LumiEmptyState>
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
  padding: var(--space-3) var(--space-6);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
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
  padding: var(--space-6) var(--space-7);
}

.detail-tabs {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-1);
  background: var(--workspace-panel);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-5);
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-3) var(--space-5);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
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
  gap: var(--space-6);
}

.tab-switch-enter-active {
  animation: lumi-fade-in var(--duration-normal) var(--ease-out-expo);
}

.tab-switch-leave-active {
  animation: lumi-fade-in var(--duration-fast) var(--ease-out-expo) reverse;
}

.detail-not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: var(--space-4);
  color: var(--text-muted);
}

.detail-not-found .back-btn {
  color: var(--lumi-primary);
}
</style>