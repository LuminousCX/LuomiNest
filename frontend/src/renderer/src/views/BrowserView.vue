<script setup lang="ts">
/**
 * LuomiNest 内置浏览器视图
 *
 * 通过 3 个 composable 解耦关注点：
 * - useBrowserNavigation：地址栏、前进/后退、侧栏宽度同步
 * - useBrowserTabs：标签页 CRUD、IPC 事件、taskStream 监听
 * - useBrowserActions：DevPanel、截图、快速点击/填表、AI 搜索、toast、prompt 对话框
 */
import { ref, onMounted, onUnmounted } from 'vue'
import TabBar from '../components/browser/TabBar.vue'
import NavBar from '../components/browser/NavBar.vue'
import BookmarkBar from '../components/browser/BookmarkBar.vue'
import HomePage from '../components/browser/HomePage.vue'
import ErrorPage from '../components/browser/ErrorPage.vue'
import DevPanel from '../components/browser/DevPanel.vue'
import { useBrowserNavigation } from '../composables/useBrowserNavigation'
import { useBrowserTabs } from '../composables/useBrowserTabs'
import { useBrowserActions, type DevPanelHandle } from '../composables/useBrowserActions'
import { X, Camera } from 'lucide-vue-next'

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

// DevPanel 组件实例 ref（view 定义，供 template ref 与 composable 共享）
const devPanelRef = ref<DevPanelHandle | null>(null)

// 快捷操作：DevPanel + 截图 + 快速点击/填表 + AI 搜索 + toast + prompt
const {
  showDevPanel,
  screenshotUrl,
  toastMessage,
  showToast,
  promptState,
  promptInput,
  closeScreenshot,
  handleQuickAction,
  submitPrompt,
  cancelPrompt,
  cleanup,
} = useBrowserActions({
  getActiveTab: () => activeTab.value,
  devPanelRef,
})

// 静态书签数据
const bookmarks = [
  { name: 'GitHub', url: 'https://github.com' },
  { name: 'Google', url: 'https://google.com' },
  { name: 'MDN', url: 'https://developer.mozilla.org' },
  { name: 'Stack Overflow', url: 'https://stackoverflow.com' }
]

onMounted(async () => {
  await syncTabs()
  await restoreActiveTab()

  window.electron?.ipcRenderer?.on('tab:updated', handleTabUpdated)
  window.electron?.ipcRenderer?.on('tab:new-tab-request', handleNewTabRequest)
  window.electron?.ipcRenderer?.on('tab:navigation-state', handleNavigationState)

  setupSidebarObserver()
})

onUnmounted(() => {
  window.electron?.ipcRenderer?.removeListener('tab:updated', handleTabUpdated)
  window.electron?.ipcRenderer?.removeListener('tab:new-tab-request', handleNewTabRequest)
  window.electron?.ipcRenderer?.removeListener('tab:navigation-state', handleNavigationState)

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
      :show-dev-panel="showDevPanel"
      @navigate="navigateToUrl"
      @refresh="refreshTab"
      @back="goBack"
      @forward="goForward"
      @toggle-dev-panel="showDevPanel = !showDevPanel"
    />

    <BookmarkBar
      :bookmarks="bookmarks"
      @select="navigateToUrl"
    />

    <div v-if="showCaptchaBanner" class="captcha-banner">
      <div class="captcha-banner-content">
        <span class="captcha-icon">&#9888;</span>
        <span>检测到人机验证页面，请在下方完成验证后继续浏览</span>
      </div>
    </div>

    <div class="browser-content" :class="{ 'with-panel': showDevPanel, 'with-captcha': showCaptchaBanner }">
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
        @action="handleQuickAction"
      />
    </div>

    <DevPanel
      v-if="showDevPanel"
      ref="devPanelRef"
      @close="showDevPanel = false"
    />

    <!-- 截图预览弹层 -->
    <div v-if="screenshotUrl" class="screenshot-overlay" @click="closeScreenshot">
      <div class="screenshot-modal" @click.stop>
        <div class="screenshot-header">
          <div class="screenshot-title">
            <Camera :size="16" />
            <span>页面截图</span>
          </div>
          <button class="screenshot-close" @click="closeScreenshot" aria-label="关闭">
            <X :size="18" />
          </button>
        </div>
        <img :src="screenshotUrl" class="screenshot-image" alt="页面截图" />
      </div>
    </div>

    <!-- 应用内 prompt 对话框（CodeRabbit #5 替代 window.prompt） -->
    <Transition name="prompt-fade">
      <div v-if="promptState" class="prompt-overlay" @click="cancelPrompt">
        <div class="prompt-modal" @click.stop>
          <div class="prompt-header">
            <span class="prompt-title">{{ promptState.title }}</span>
            <button class="prompt-close" @click="cancelPrompt" aria-label="取消">
              <X :size="16" />
            </button>
          </div>
          <div class="prompt-body">
            <input
              v-model="promptInput"
              class="prompt-input"
              :placeholder="promptState.placeholder"
              type="text"
              autofocus
              @keydown.enter="submitPrompt"
              @keydown.esc="cancelPrompt"
            />
          </div>
          <div class="prompt-actions">
            <button class="prompt-btn prompt-btn-cancel" @click="cancelPrompt">取消</button>
            <button class="prompt-btn prompt-btn-confirm" @click="submitPrompt">确定</button>
          </div>
        </div>
      </div>
    </Transition>

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

.browser-content.with-panel {
  height: calc(100% - 220px);
}

.browser-content.with-captcha {
  height: calc(100% - 36px);
}

.browser-content.with-panel.with-captcha {
  height: calc(100% - 256px);
}

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
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border);
}

.screenshot-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-base);
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

.prompt-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal, 1000);
  animation: lumi-fade-in var(--duration-normal) var(--ease-in-out);
}

.prompt-modal {
  width: 420px;
  max-width: 90vw;
  background: var(--surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.prompt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-4) var(--space-2);
}

.prompt-title {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
}

.prompt-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-6);
  height: var(--space-6);
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.prompt-close:hover {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.prompt-input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: var(--text-sm);
  outline: none;
  transition: border-color var(--transition-fast);
  box-sizing: border-box;
}

.prompt-body {
  padding: 0 var(--space-4) var(--space-2);
}

.prompt-input:focus {
  border-color: var(--lumi-primary);
}

.prompt-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4) var(--space-4);
}

.prompt-btn {
  padding: var(--space-1) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  cursor: pointer;
  border: none;
  transition: all var(--transition-fast);
}

.prompt-btn-cancel {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.prompt-btn-cancel:hover {
  background: var(--surface-active);
}

.prompt-btn-confirm {
  background: var(--lumi-primary);
  color: var(--text-inverse);
}

.prompt-btn-confirm:hover {
  opacity: 0.9;
}

.prompt-fade-enter-active,
.prompt-fade-leave-active {
  transition: opacity var(--duration-normal) var(--ease-in-out);
}

.prompt-fade-enter-from,
.prompt-fade-leave-to {
  opacity: 0;
}

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
