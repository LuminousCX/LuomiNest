<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import TabBar from '../components/browser/TabBar.vue'
import NavBar from '../components/browser/NavBar.vue'
import BookmarkBar from '../components/browser/BookmarkBar.vue'
import HomePage from '../components/browser/HomePage.vue'
import ErrorPage from '../components/browser/ErrorPage.vue'
import DevPanel from '../components/browser/DevPanel.vue'

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
const devOutput = ref('')
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
})

onUnmounted(() => {
  window.electron?.ipcRenderer?.removeListener('tab:updated', handleTabUpdated)
  window.electron?.ipcRenderer?.removeListener('tab:new-tab-request', handleNewTabRequest)
  window.electron?.ipcRenderer?.removeListener('tab:navigation-state', handleNavigationState)

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
      tabs.value = allTabs.map((t: any) => ({
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
    tabs.value.push({ id: `home-${Date.now()}`, title: '新标签页', url: '', active: true })
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
      id: `error-${Date.now()}`,
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
  if (tabs.value.length <= 1) return

  const idx = tabs.value.findIndex(t => t.id === tabId)
  if (idx === -1) return

  try {
    await window.api?.tab.close(tabId)
  } catch (e) {
    console.error('[ERROR][LuomiNestBrowser] Failed to close tab:', e)
  }

  tabs.value.splice(idx, 1)

  if (tabs.value.length > 0) {
    const newActiveIdx = Math.min(idx, tabs.value.length - 1)
    const newActiveTab = tabs.value[newActiveIdx]
    newActiveTab.active = true

    if (newActiveTab.url) {
      await selectTab(newActiveTab.id)
    } else {
      showHomePage.value = true
      addressBar.value = ''
      await window.api?.tab.hideAll()
    }
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

async function handleQuickAction(action: string) {
  const tab = activeTab.value
  if (!tab?.url) {
    devOutput.value = '[提示] 请先打开一个网页'
    showDevPanel.value = true
    return
  }

  switch (action) {
    case 'script':
      showDevPanel.value = !showDevPanel.value
      break
    case 'screenshot':
      devOutput.value = '[提示] 截图功能开发中...'
      showDevPanel.value = true
      break
    case 'dom':
      devOutput.value = '[提示] DOM 读取功能开发中...'
      showDevPanel.value = true
      break
    case 'click':
      devOutput.value = '[提示] 请输入 CSS 选择器'
      showDevPanel.value = true
      break
    case 'fill':
      devOutput.value = '[提示] 格式: selector|value'
      showDevPanel.value = true
      break
  }
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
      @close="showDevPanel = false"
    />
  </div>
</template>

<style scoped>
.browser-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fafaf9;
}

.captcha-banner {
  height: 36px;
  background: linear-gradient(90deg, rgba(254,243,199,0.9), rgba(254,243,199,0.7));
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
  left: 16px;
  right: 16px;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, #f59e0b 20%, #f59e0b 80%, transparent 100%);
}

.captcha-banner-content {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #92400e;
}

.captcha-icon {
  font-size: 16px;
}

.browser-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: height 0.2s ease-in-out;
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
</style>
