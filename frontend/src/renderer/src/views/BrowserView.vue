<script setup lang="ts">
/**
 * LuomiNest 内置浏览器视图（只读化，2026-09）
 *
 * 重心：网址栏输入 → 自动访问 → 访问成功自动截图。
 * - 保留：网址栏、前进/后退/刷新/停止、标签页条、书签条、页面标题/加载状态、验证码横幅、错误页、首页导航
 * - 新增：截图历史条（本次会话内，点击放大预览、可复制/另存 PNG）
 * - 移除：DevPanel（脚本/DOM/源码）、快速点击/填表、AI 搜索等交互面板
 *
 * 通过 3 个 composable 解耦关注点：
 * - useBrowserNavigation：地址栏、前进/后退、侧栏宽度同步
 * - useBrowserTabs：标签页 CRUD、IPC 事件、taskStream 监听
 * - useBrowserActions：截图（手动/自动）、截图历史、预览/复制/另存、toast
 */
import { watch, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import TabBar from '../components/browser/TabBar.vue'
import NavBar from '../components/browser/NavBar.vue'
import BookmarkBar from '../components/browser/BookmarkBar.vue'
import HomePage from '../components/browser/HomePage.vue'
import ErrorPage from '../components/browser/ErrorPage.vue'
import { useBrowserNavigation } from '../composables/useBrowserNavigation'
import { useBrowserTabs } from '../composables/useBrowserTabs'
import { useBrowserActions } from '../composables/useBrowserActions'
import { X, Camera, Copy, Download } from 'lucide-vue-next'

const { t } = useI18n()

// 导航状态：地址栏 + 前进/后退 + 侧栏宽度同步
const {
  addressBar,
  canGoBack,
  canGoForward,
  syncNavigationState,
  resetNavigation,
  setNavigationFlags,
  goBack,
  goForward,
  setupSidebarObserver,
  teardownSidebarObserver,
} = useBrowserNavigation()

// 标签页管理：CRUD + IPC + taskStream 监听
const {
  tabs,
  showHomePage,
  activeTab,
  showCaptchaBanner,
  syncTabs,
  createTab,
  selectTab,
  closeTab,
  navigateToUrl,
  refreshTab,
  restoreActiveTab,
  handleTabUpdated,
  handleNewTabRequest,
  handleNavigationState,
} = useBrowserTabs({
  addressBar,
  syncNavigationState,
  resetNavigation,
  setNavigationFlags,
})

// 截图历史 + 预览/复制/另存 + toast
const {
  history,
  previewItem,
  toastMessage,
  showToast,
  displayToast,
  captureScreenshot,
  openScreenshot,
  closeScreenshot,
  copyScreenshot,
  saveScreenshot,
  cleanup,
} = useBrowserActions()

// 静态书签数据
const bookmarks = [
  { name: 'GitHub', url: 'https://github.com' },
  { name: 'Google', url: 'https://google.com' },
  { name: 'MDN', url: 'https://developer.mozilla.org' },
  { name: 'Stack Overflow', url: 'https://stackoverflow.com' }
]

// ===== 停止加载：W4-7 只读白名单后 execute_js 对渲染层不可达，改走 tab:stop
// 专用通道（主进程 webContents.stop()，见 tab.ts stopNavigation）=====
const stopLoading = async (): Promise<void> => {
  try {
    await window.api?.tab.stop()
  } catch {
    // 静默失败：停止加载本身无需打扰用户
  }
}

// ===== W4-8 风控提示：主进程 did-fail-load(412/403) 下发的 riskBlocked 标记，
// 复用验证码黄条 UI 切换为「该网站风控拦截」文案 =====
// （useBrowserTabs 的 Tab 模型未登记该字段且不在本次改动范围，此处局部窄化读取）
const activeTabRiskBlocked = computed(
  () => (activeTab.value as { riskBlocked?: boolean } | undefined)?.riskBlocked === true
)

// ===== W4-6 下载拦截提示：主进程 will-download 取消下载后经 tab:download-blocked 转发 =====
const handleDownloadBlocked = (): void => {
  displayToast(t('browser.downloadBlocked', '内置浏览器不支持下载，已取消'))
}

// ===== 访问成功后自动截图 =====
// 截图历史条高度：与主进程 tabManager 的底部预留（devPanelHeight）保持一致
const SHOT_STRIP_HEIGHT = 92
/** load 完成后的渲染稳定延迟，避免截到白屏/半渲染帧 */
const AUTO_SHOT_DELAY = 600

let autoShotTimer: ReturnType<typeof setTimeout> | null = null

watch(
  () => {
    const tab = activeTab.value
    if (!tab) return null
    return { id: tab.id, loading: !!tab.loading, url: tab.url, error: !!tab.error }
  },
  (cur, prev) => {
    if (!cur || !prev || prev.id !== cur.id) return
    // 仅在「加载中 → 加载完成」且确有页面、无错误时自动截图
    if (prev.loading && !cur.loading && cur.url && !cur.error) {
      if (autoShotTimer) clearTimeout(autoShotTimer)
      const tabSnapshot = activeTab.value
      autoShotTimer = setTimeout(() => {
        autoShotTimer = null
        captureScreenshot(
          { url: cur.url, title: tabSnapshot?.title || '' },
          true // 自动截图成功静默，失败 toast
        )
      }, AUTO_SHOT_DELAY)
    }
  }
)

// 手动截图（NavBar 相机按钮）
const handleManualScreenshot = (): void => {
  const tab = activeTab.value
  if (!tab?.url) {
    displayToast(t('browser.actions.needOpenPage'))
    return
  }
  captureScreenshot({ url: tab.url, title: tab.title || '' })
}

// ===== 截图历史条显隐 → 同步主进程底部预留高度 =====
const syncShotStripBounds = (): void => {
  const reserved = history.value.length > 0 ? SHOT_STRIP_HEIGHT : 0
  window.api?.tab.setBoundsConfig({ devPanelHeight: reserved })?.catch(() => {})
}

watch(() => history.value.length, syncShotStripBounds)

onMounted(async () => {
  await syncTabs()
  await restoreActiveTab()

  window.electron?.ipcRenderer?.on('tab:updated', handleTabUpdated)
  window.electron?.ipcRenderer?.on('tab:new-tab-request', handleNewTabRequest)
  window.electron?.ipcRenderer?.on('tab:navigation-state', handleNavigationState)
  window.electron?.ipcRenderer?.on('tab:download-blocked', handleDownloadBlocked)

  setupSidebarObserver()
  syncShotStripBounds()
})

onUnmounted(() => {
  window.electron?.ipcRenderer?.removeListener('tab:updated', handleTabUpdated)
  window.electron?.ipcRenderer?.removeListener('tab:new-tab-request', handleNewTabRequest)
  window.electron?.ipcRenderer?.removeListener('tab:navigation-state', handleNavigationState)
  window.electron?.ipcRenderer?.removeListener('tab:download-blocked', handleDownloadBlocked)

  if (autoShotTimer) {
    clearTimeout(autoShotTimer)
    autoShotTimer = null
  }

  teardownSidebarObserver()
  cleanup()

  window.api?.tab.hideAll().catch(() => {})
  window.api?.tab.setBoundsConfig({ devPanelHeight: 0 }).catch(() => {})
})
</script>

<template>
  <div class="browser-view">
    <TabBar
      :tabs="tabs"
      @select="selectTab"
      @close="closeTab"
      @add="createTab()"
    />

    <NavBar
      :url="addressBar"
      :can-go-back="canGoBack"
      :can-go-forward="canGoForward"
      :loading="activeTab?.loading"
      @navigate="navigateToUrl"
      @refresh="refreshTab"
      @back="goBack"
      @forward="goForward"
      @stop="stopLoading"
      @screenshot="handleManualScreenshot"
    />

    <BookmarkBar
      :bookmarks="bookmarks"
      @select="navigateToUrl"
    />

    <div v-if="showCaptchaBanner" class="captcha-banner">
      <div class="captcha-banner-content">
        <span class="captcha-icon">&#9888;</span>
        <!-- W4-8：风控拦截（412/403）与人机验证共用黄条，按 riskBlocked 切换文案 -->
        <span v-if="activeTabRiskBlocked">
          {{ t('browser.riskBlockedBanner', '该网站风控拦截，本次访问被站点反爬策略阻止，可稍后重试') }}
        </span>
        <span v-else>{{ t('browser.captchaBanner') }}</span>
      </div>
    </div>

    <div class="browser-content" :class="{ 'with-captcha': showCaptchaBanner }">
      <ErrorPage
        v-if="activeTab?.error && !activeTab?.loading"
        :code="activeTab.error.code"
        :title="activeTab.error.title"
        :message="activeTab.error.message"
        :url="activeTab.url"
        @retry="refreshTab"
        @new-tab="createTab()"
      />

      <HomePage
        v-else-if="showHomePage"
        @search="navigateToUrl"
      />
    </div>

    <!-- 截图历史条（本次会话内，新→旧） -->
    <div v-if="history.length" class="shot-strip">
      <div class="shot-strip-header">
        <Camera :size="13" />
        <span>{{ t('browser.screenshotHistory') }}</span>
        <span class="shot-count">{{ history.length }}</span>
      </div>
      <div class="shot-strip-items">
        <button
          v-for="item in history"
          :key="item.id"
          class="shot-thumb"
          :title="item.title || item.url"
          @click="openScreenshot(item)"
        >
          <img :src="item.dataUrl" :alt="item.title || item.url" loading="lazy" />
        </button>
      </div>
    </div>

    <!-- 截图大图预览弹层（点击历史缩略图打开，可复制/另存） -->
    <div v-if="previewItem" class="screenshot-overlay" @click="closeScreenshot">
      <div class="screenshot-modal" @click.stop>
        <div class="screenshot-header">
          <div class="screenshot-title">
            <Camera :size="16" />
            <span class="screenshot-meta">{{ previewItem.title || previewItem.url || t('browser.screenshotTitle') }}</span>
          </div>
          <div class="screenshot-header-actions">
            <button
              class="screenshot-action"
              :aria-label="t('browser.copyImage')"
              :title="t('browser.copyImage')"
              @click="copyScreenshot(previewItem)"
            >
              <Copy :size="15" />
            </button>
            <button
              class="screenshot-action"
              :aria-label="t('browser.saveImage')"
              :title="t('browser.saveImage')"
              @click="saveScreenshot(previewItem)"
            >
              <Download :size="15" />
            </button>
            <button class="screenshot-close" @click="closeScreenshot" :aria-label="t('browser.close')">
              <X :size="18" />
            </button>
          </div>
        </div>
        <img :src="previewItem.dataUrl" class="screenshot-image" :alt="t('browser.screenshotAlt')" />
      </div>
    </div>

    <!-- 操作反馈 toast -->
    <Transition name="toast-fade">
      <div v-if="showToast" class="toast-notification">
        <span>{{ toastMessage }}</span>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.browser-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surface);
}

.captcha-banner {
  height: 36px;
  background: var(--lumi-amber-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
}

.captcha-banner::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: var(--space-4);
  right: var(--space-4);
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, var(--lumi-amber) 20%, var(--lumi-amber) 80%, transparent 100%);
}

.captcha-banner-content {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-base);
  color: var(--lumi-amber-dark);
}

.captcha-icon {
  font-size: var(--text-xl);
}

.browser-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: height var(--duration-leave) var(--ease-in-out);
}

.browser-content.with-captcha {
  height: calc(100% - 36px);
}

/* ===== 截图历史条 ===== */
.shot-strip {
  height: 92px;
  flex-shrink: 0;
  display: flex;
  align-items: stretch;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--surface);
  border-top: 1px solid var(--divider-soft);
}

.shot-strip-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  color: var(--text-muted);
  font-size: var(--text-xs, 12px);
  min-width: 64px;
}

.shot-count {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 18px;
  padding: 0 var(--space-1);
  border-radius: var(--radius-full, 999px);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-size: 11px;
}

.shot-strip-items {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  overflow-x: auto;
  overflow-y: hidden;
}

.shot-thumb {
  flex-shrink: 0;
  height: 64px;
  width: 104px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  cursor: pointer;
  background: var(--bg-secondary);
  transition: all var(--transition-fast);
}

.shot-thumb:hover {
  border-color: var(--lumi-primary);
  transform: translateY(-2px);
}

.shot-thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top left;
}

/* ===== 截图预览弹层 ===== */
.screenshot-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal, 1000);
  animation: lumi-fade-in var(--duration-normal) var(--ease-in-out);
}

.screenshot-modal {
  max-width: 90%;
  max-height: 90%;
  background: var(--surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.screenshot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border);
}

.screenshot-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-base);
  color: var(--text-secondary);
  min-width: 0;
}

.screenshot-meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.screenshot-header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-shrink: 0;
}

.screenshot-action {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.screenshot-action:hover {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.screenshot-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.screenshot-close:hover {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.screenshot-image {
  display: block;
  max-width: 100%;
  max-height: calc(90vh - 60px);
  object-fit: contain;
}

/* ===== toast ===== */
.toast-notification {
  position: fixed;
  bottom: var(--space-6);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--text);
  color: var(--text-inverse);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  font-size: var(--text-sm);
  z-index: var(--z-modal, 1000);
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: all var(--duration-normal) var(--ease-in-out);
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, var(--space-2));
}

@keyframes lumi-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
