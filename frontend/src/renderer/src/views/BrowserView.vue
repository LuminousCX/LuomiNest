<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import type { TabInfo } from '@shared/ipc-types'
import TabBar from '../components/browser/TabBar.vue'
import NavBar from '../components/browser/NavBar.vue'
import BookmarkBar from '../components/browser/BookmarkBar.vue'
import HomePage from '../components/browser/HomePage.vue'
import ErrorPage from '../components/browser/ErrorPage.vue'
import DevPanel from '../components/browser/DevPanel.vue'
import { useTaskStreamStore } from '../stores/taskStream'
import { generateId } from '../utils/id'
import { X, Camera } from 'lucide-vue-next'

const taskStreamStore = useTaskStreamStore()

interface Tab {
  id: string
  title: string
  url: string
  favicon?: string
  loading?: boolean
  error?: { code: number; title: string; message: string }
  active?: boolean
  captchaDetected?: boolean
  sleeping?: boolean
}

const tabs = ref<Tab[]>([])
const addressBar = ref('')
const showHomePage = ref(true)
const showDevPanel = ref(false)
const devPanelRef = ref<{ switchMode: (m: 'script' | 'dom') => void } | null>(null)
const screenshotUrl = ref('')
const screenshotLoading = ref(false)
const toastMessage = ref('')
const showToast = ref(false)
let toastTimer: ReturnType<typeof setTimeout> | null = null
let sidebarResizeObserver: ResizeObserver | null = null
const canGoBack = ref(false)
const canGoForward = ref(false)

const bookmarks = [
  { name: 'GitHub', url: 'https://github.com' },
  { name: 'Google', url: 'https://google.com' },
  { name: 'MDN', url: 'https://developer.mozilla.org' },
  { name: 'Stack Overflow', url: 'https://stackoverflow.com' }
]

const activeTab = computed(() => tabs.value.find(t => t.active))
const showCaptchaBanner = computed(() => activeTab.value?.captchaDetected && !activeTab.value?.loading)

watch(showDevPanel, async (show) => {
  try {
    await window.api?.tab.setBoundsConfig({
      devPanelHeight: show ? 220 : 0
    })
  } catch (e) {
    console.error('[ERROR][LuomiNestBrowser] Failed to set panel height:', e)
  }
})

onMounted(async () => {
  await syncTabs()

  const active = tabs.value.find(t => t.active)
  if (active?.url && !active.sleeping) {
    try {
      await window.api?.tab.showActive()
    } catch (e) {
      console.error('[ERROR][LuomiNestBrowser] Failed to restore active tab:', e)
    }
  } else if (active?.url && active.sleeping) {
    try {
      await window.api?.tab.activate(active.id)
    } catch (e) {
      console.error('[ERROR][LuomiNestBrowser] Failed to wake up tab:', e)
    }
  }

  window.electron?.ipcRenderer?.on('tab:updated', handleTabUpdated)
  window.electron?.ipcRenderer?.on('tab:new-tab-request', handleNewTabRequest)
  window.electron?.ipcRenderer?.on('tab:navigation-state', handleNavigationState)

  // 监听 sidebar 宽度变化，同步到主进程 tabManager（修复浏览器覆盖左侧导航）
  const sidebarEl = document.querySelector('.lumi-sidebar')
  if (sidebarEl) {
    const syncSidebarWidth = (): void => {
      const width = Math.round(sidebarEl.getBoundingClientRect().width)
      if (width > 0) {
        window.api?.tab.setBoundsConfig({ sidebarWidth: width })
      }
    }
    syncSidebarWidth()
    sidebarResizeObserver = new ResizeObserver(syncSidebarWidth)
    sidebarResizeObserver.observe(sidebarEl)
  }
})

// 订阅 taskStream：主 Agent 通过 create_browser_tab 工具创建的标签页自动打开
watch(
  () => taskStreamStore.pendingBrowserTasks,
  (pendingTasks) => {
    for (const task of pendingTasks) {
      if (task.url) {
        console.info(`[LuomiNestBrowser] 主 Agent 请求打开标签页: ${task.url}`)
        createTab(task.url)
        taskStreamStore.markBrowserTabOpened(task.tab_id)
      }
    }
  },
  { deep: true }
)

onUnmounted(() => {
  window.electron?.ipcRenderer?.removeListener('tab:updated', handleTabUpdated)
  window.electron?.ipcRenderer?.removeListener('tab:new-tab-request', handleNewTabRequest)
  window.electron?.ipcRenderer?.removeListener('tab:navigation-state', handleNavigationState)

  sidebarResizeObserver?.disconnect()
  sidebarResizeObserver = null

  window.api?.tab.hideAll().catch(() => {})
  window.api?.tab.setBoundsConfig({ devPanelHeight: 0 }).catch(() => {})
})

function handleTabUpdated(_event: any, data: { tabId: string; updates: Partial<Tab> }) {
  const tab = tabs.value.find(t => t.id === data.tabId)
  if (tab) {
    Object.assign(tab, data.updates)
    if (tab.active && data.updates.url !== undefined) {
      addressBar.value = data.updates.url
    }
    if (data.updates.sleeping !== undefined && !data.updates.sleeping && tab.active) {
      syncNavigationState()
    }
  }
}

function handleNewTabRequest(_event: any, data: { url: string }) {
  createTab(data.url)
}

function handleNavigationState(_event: any, data: { tabId: string; canGoBack: boolean; canGoForward: boolean }) {
  const tab = tabs.value.find(t => t.id === data.tabId)
  if (tab?.active) {
    canGoBack.value = data.canGoBack
    canGoForward.value = data.canGoForward
  }
}

async function syncNavigationState() {
  try {
    const state = await window.api?.tab.getNavigationState()
    if (state) {
      canGoBack.value = state.canGoBack
      canGoForward.value = state.canGoForward
    }
  } catch {
    canGoBack.value = false
    canGoForward.value = false
  }
}

async function syncTabs() {
  try {
    const allTabs = await window.api?.tab.getAll() || []
    if (allTabs.length === 0) {
      tabs.value = [{ id: 'home', title: '新标签页', url: '', active: true }]
      showHomePage.value = true
    } else {
      tabs.value = allTabs.map((t: TabInfo) => ({
        id: t.id,
        title: t.title || '加载中...',
        url: t.url,
        active: t.active,
        loading: t.loading,
        favicon: t.favicon,
        error: t.error,
        captchaDetected: t.captchaDetected,
        sleeping: t.sleeping
      }))
      const active = tabs.value.find(t => t.active)
      if (active?.url) {
        showHomePage.value = false
        addressBar.value = active.url
        if (!active.sleeping) {
          await syncNavigationState()
        }
      }
    }
  } catch (e) {
    tabs.value = [{ id: 'home', title: '新标签页', url: '', active: true }]
  }
}

async function createTab(url: string = '') {
  tabs.value.forEach(t => t.active = false)

  if (!url) {
    tabs.value.push({ id: generateId('home'), title: '新标签页', url: '', active: true })
    showHomePage.value = true
    addressBar.value = ''
    canGoBack.value = false
    canGoForward.value = false
    await window.api?.tab.hideAll()
    return
  }

  showHomePage.value = false
  addressBar.value = url

  try {
    const newTab = await window.api?.tab.create(url)
    if (newTab) {
      tabs.value.push({
        id: newTab.id,
        title: newTab.title || '加载中...',
        url: newTab.url,
        active: true,
        loading: newTab.loading,
        error: newTab.error,
        captchaDetected: newTab.captchaDetected,
        sleeping: newTab.sleeping
      })
    }
  } catch (e: any) {
    console.error('[ERROR][LuomiNestBrowser] Failed to create tab:', e.message)
    tabs.value.push({
      id: generateId('error'),
      title: '加载失败',
      url,
      active: true,
      error: { code: -1, title: '加载失败', message: e.message }
    })
  }
}

async function selectTab(tabId: string) {
  const tab = tabs.value.find(t => t.id === tabId)
  if (!tab) return

  tabs.value.forEach(t => t.active = t.id === tabId)

  if (tab.url) {
    try {
      if (tab.sleeping) {
        tab.sleeping = false
        tab.loading = true
      }
      await window.api?.tab.activate(tabId)
      showHomePage.value = false
      addressBar.value = tab.url
      await syncNavigationState()
    } catch (e) {
      console.error('[ERROR][LuomiNestBrowser] Failed to switch tab:', e)
    }
  } else {
    showHomePage.value = true
    addressBar.value = ''
    canGoBack.value = false
    canGoForward.value = false
    await window.api?.tab.hideAll()
  }
}

async function closeTab(tabId: string) {
  const idx = tabs.value.findIndex(t => t.id === tabId)
  if (idx === -1) return

  const tab = tabs.value[idx]
  const isHomeTab = !tab.url

  if (!isHomeTab) {
    try {
      await window.api?.tab.close(tabId)
    } catch (e) {
      console.error('[ERROR][LuomiNestBrowser] Failed to close tab:', e)
    }
  }

  tabs.value.splice(idx, 1)

  // 无剩余标签页 → 回到默认首页
  if (tabs.value.length === 0) {
    tabs.value = [{ id: generateId('home'), title: '新标签页', url: '', active: true }]
    showHomePage.value = true
    addressBar.value = ''
    canGoBack.value = false
    canGoForward.value = false
    await window.api?.tab.hideAll()
    return
  }

  // 有剩余 → 切换到相邻标签
  tabs.value.forEach(t => t.active = false)
  const newActiveIdx = Math.min(idx, tabs.value.length - 1)
  const newActiveTab = tabs.value[newActiveIdx]
  newActiveTab.active = true

  if (newActiveTab.url) {
    await selectTab(newActiveTab.id)
  } else {
    showHomePage.value = true
    addressBar.value = ''
    canGoBack.value = false
    canGoForward.value = false
    await window.api?.tab.hideAll()
  }
}

async function navigateToUrl(url: string) {
  if (!url.trim()) return

  let normalizedUrl = url.trim()
  if (!normalizedUrl.startsWith('http://') && !normalizedUrl.startsWith('https://')) {
    normalizedUrl = 'https://' + normalizedUrl
  }

  const tab = activeTab.value
  if (tab && !tab.url) {
    const idx = tabs.value.findIndex(t => t.id === tab.id)
    if (idx !== -1) {
      tabs.value.splice(idx, 1)
    }
  }

  await createTab(normalizedUrl)
}

async function refreshTab() {
  const tab = activeTab.value
  if (!tab?.url) return

  try {
    if (tab.sleeping) {
      tab.sleeping = false
      tab.loading = true
    }
    await window.api?.tab.reload(tab.id)
  } catch (e) {
    console.error('[ERROR][LuomiNestBrowser] Failed to reload tab:', e)
  }
}

async function goBack() {
  try {
    await window.api?.tab.goBack()
  } catch (e) {
    console.error('[ERROR][LuomiNestBrowser] Failed to go back:', e)
  }
}

async function goForward() {
  try {
    await window.api?.tab.goForward()
  } catch (e) {
    console.error('[ERROR][LuomiNestBrowser] Failed to go forward:', e)
  }
}

function handleBookmarkSelect(url: string) {
  navigateToUrl(url)
}

function handleSearch(url: string) {
  navigateToUrl(url)
}

const displayToast = (msg: string): void => {
  if (toastTimer) clearTimeout(toastTimer)
  toastMessage.value = msg
  showToast.value = true
  toastTimer = setTimeout(() => {
    showToast.value = false
    toastTimer = null
  }, 3000)
}

async function handleQuickAction(action: string) {
  // ai-search 不需要打开网页，其余动作需要先有活跃标签页
  if (action !== 'ai-search' && !activeTab.value?.url) {
    displayToast('请先打开一个网页再使用此功能')
    return
  }

  switch (action) {
    case 'script':
      showDevPanel.value = !showDevPanel.value
      if (showDevPanel.value) devPanelRef.value?.switchMode('script')
      break
    case 'screenshot':
      await captureScreenshot()
      break
    case 'dom':
      showDevPanel.value = true
      devPanelRef.value?.switchMode('dom')
      break
    case 'click':
      await quickClick()
      break
    case 'fill':
      await quickFill()
      break
    case 'ai-search':
      await aiSearch()
      break
  }
}

async function captureScreenshot(): Promise<void> {
  if (screenshotLoading.value) return
  screenshotLoading.value = true
  try {
    const result = await window.api?.browserAutomation?.execute('screenshot')
    if (result?.success && result.data?.screenshot) {
      screenshotUrl.value = String(result.data.screenshot)
      displayToast('截图已生成')
    } else {
      displayToast(`截图失败：${result?.error || '未知错误'}`)
    }
  } catch (e: any) {
    displayToast(`截图异常：${e?.message || e}`)
  } finally {
    screenshotLoading.value = false
  }
}

async function quickClick(): Promise<void> {
  const selector = window.prompt('请输入要点击的元素选择器或 DOM 索引（如 5 或 #search）')
  if (!selector) return
  try {
    const result = await window.api?.browserAutomation?.execute('click', { selector })
    if (result?.success) {
      displayToast('点击成功')
    } else {
      displayToast(`点击失败：${result?.error || '元素未找到'}`)
    }
  } catch (e: any) {
    displayToast(`点击异常：${e?.message || e}`)
  }
}

async function quickFill(): Promise<void> {
  const input = window.prompt('请输入选择器和文本，格式: selector|text（如 #search|你好）')
  if (!input) return
  const sep = input.indexOf('|')
  if (sep === -1) {
    displayToast('格式错误，请使用 selector|text 格式')
    return
  }
  const selector = input.slice(0, sep)
  const text = input.slice(sep + 1)
  try {
    const result = await window.api?.browserAutomation?.execute('type', {
      selector, text, clear: true
    })
    if (result?.success) {
      displayToast('填表成功')
    } else {
      displayToast(`填表失败：${result?.error || '元素未找到'}`)
    }
  } catch (e: any) {
    displayToast(`填表异常：${e?.message || e}`)
  }
}

async function aiSearch(): Promise<void> {
  const query = window.prompt('请输入要向 AI 搜索的问题')
  if (!query) return
  try {
    const result = await window.api?.browserSearch?.search(query)
    if (result) {
      displayToast('AI 搜索请求已发送')
    } else {
      displayToast('AI 搜索无响应')
    }
  } catch (e: any) {
    displayToast(`AI 搜索异常：${e?.message || e}`)
  }
}

function closeScreenshot(): void {
  screenshotUrl.value = ''
}
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
      @select="handleBookmarkSelect"
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
        @search="handleSearch"
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
