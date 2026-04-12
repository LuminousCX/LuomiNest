<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import {
  Send,
  Paperclip,
  MessageSquare,
  AtSign,
  ChevronDown,
  Plus,
  X,
  ArrowLeft,
  ArrowRight,
  RotateCw,
  Star,
  Search,
  ChevronRight,
  Globe,
  MousePointerClick,
  Code2,
  Camera,
  Bot,
  Tv,
  Video
} from 'lucide-vue-next'

interface TabData {
  id: string
  title: string
  url: string
  active: boolean
  favicon?: string
  loading?: boolean
  error?: string
}

interface SearchEngine {
  id: string
  name: string
  icon: any
  url: string
  color: string
}

const searchEngines: SearchEngine[] = [
  { id: 'bing', name: 'Bing', icon: Search, url: 'https://www.bing.com/search?q=', color: '#00809d' },
  { id: 'google', name: 'Google', icon: Globe, url: 'https://www.google.com/search?q=', color: '#4285f4' },
  { id: 'bilibili', name: 'Bilibili', icon: Tv, url: 'https://search.bilibili.com/all?keyword=', color: '#00a1d6' },
  { id: 'youtube', name: 'YouTube', icon: Video, url: 'https://www.youtube.com/results?search_query=', color: '#ff0000' },
  { id: 'ai', name: 'AI (本地)', icon: Bot, url: '', color: '#8b5cf6' }
]

const tabs = ref<TabData[]>([])
const addressBar = ref('')
const browserInput = ref('')
const currentUrl = ref('')
const selectedEngine = ref<SearchEngine>(searchEngines[0])
const showEngineDropdown = ref(false)
const isSearching = ref(false)
const showHomePage = ref(true)

const bookmarks = ref([
  { name: 'GitHub', url: 'https://github.com' },
  { name: 'Google', url: 'https://google.com' },
  { name: 'MDN', url: 'https://developer.mozilla.org' },
  { name: 'Stack Overflow', url: 'https://stackoverflow.com' },
  { name: 'Playwright', url: 'https://playwright.dev' },
  { name: 'Electron', url: 'https://electronjs.org' }
])

const quickActions = ref([
  { icon: Code2, label: '执行脚本', color: '#8b5cf6', action: 'script' },
  { icon: Camera, label: '页面截图', color: '#3b82f6', action: 'screenshot' },
  { icon: MousePointerClick, label: '点击元素', color: '#22c55e', action: 'click' },
  { icon: Globe, label: '读取DOM', color: '#f59e0b', action: 'dom' },
  { icon: Send, label: '填表单', color: '#f43f5e', action: 'fill' }
])

const showDevPanel = ref(false)
const devPanelMode = ref<'script' | 'dom'>('script')
const devScriptInput = ref('')
const devOutput = ref('')

const activeTab = computed(() => tabs.value.find(t => t.active))

const DEV_PANEL_HEIGHT = 220

watch(showDevPanel, async (show) => {
  try {
    await window.api?.tab.setBoundsConfig({
      devPanelHeight: show ? DEV_PANEL_HEIGHT : 0
    })
  } catch (e) {
    console.error('[LuomiNest] 设置边界配置失败:', e)
  }
})

onMounted(async () => {
  await syncTabs()

  // 监听来自主进程的创建新标签页请求
  window.electron?.ipcRenderer?.on('browser:create-tab', handleCreateTabFromLink)

  // 监听标签页更新（标题、URL）
  window.electron?.ipcRenderer?.on('browser:tab-updated', handleTabUpdated)

  // 监听 favicon 更新
  window.electron?.ipcRenderer?.on('browser:tab-favicon', handleTabFavicon)
})

onUnmounted(() => {
  // 移除监听器
  window.electron?.ipcRenderer?.removeListener('browser:create-tab', handleCreateTabFromLink)
  window.electron?.ipcRenderer?.removeListener('browser:tab-updated', handleTabUpdated)
  window.electron?.ipcRenderer?.removeListener('browser:tab-favicon', handleTabFavicon)

  // 切换页面时只隐藏视图，不关闭标签页
  // 标签页只在应用退出时清空
  window.api?.tab.hideAll().catch(() => {})
  window.api?.tab.setBoundsConfig({ devPanelHeight: 0 }).catch(() => {})
})

function handleTabUpdated(_event: any, data: { id: string; title: string; url: string; loading?: boolean; error?: string }) {
  const tab = tabs.value.find(t => t.id === data.id)
  if (tab) {
    tab.title = data.title
    tab.url = data.url
    tab.loading = data.loading
    tab.error = data.error
    if (tab.active) {
      addressBar.value = data.url
      currentUrl.value = data.url
    }
  }
}

function handleTabFavicon(_event: any, data: { id: string; favicon: string }) {
  const tab = tabs.value.find(t => t.id === data.id)
  if (tab) {
    tab.favicon = data.favicon
  }
}

async function syncTabs() {
  try {
    const managedTabs = await window.api?.tab.getAll() || []
    if (managedTabs.length === 0) {
      tabs.value = [{ id: 'home', title: '新标签页', url: '', active: true }]
      showHomePage.value = true
    } else {
      tabs.value = managedTabs.map(t => ({
        id: t.id,
        title: t.title || '加载中...',
        url: t.url,
        active: t.active
      }))
      const active = tabs.value.find(t => t.active)
      if (active?.url) {
        showHomePage.value = false
        addressBar.value = active.url
        currentUrl.value = active.url
      }
    }
  } catch (e) {
    tabs.value = [{ id: 'home', title: '新标签页', url: '', active: true }]
  }
}

function selectEngine(engine: SearchEngine) {
  selectedEngine.value = engine
  showEngineDropdown.value = false
}

async function closeTab(id: string) {
  if (tabs.value.length <= 1) return
  
  const idx = tabs.value.findIndex(t => t.id === id)
  if (idx === -1) return
  
  try {
    await window.api?.tab.closeManaged(id)
  } catch (e) {
    console.error('[LuomiNest] 关闭标签页失败:', e)
  }
  
  tabs.value.splice(idx, 1)
  
  if (tabs.value.length > 0) {
    const newActiveIdx = Math.min(idx, tabs.value.length - 1)
    const newActiveTab = tabs.value[newActiveIdx]
    newActiveTab.active = true
    
    if (newActiveTab.url) {
      try {
        await window.api?.tab.activate(newActiveTab.id)
      } catch (e) {
        console.error('[LuomiNest] 激活标签页失败:', e)
      }
      showHomePage.value = false
      addressBar.value = newActiveTab.url
      currentUrl.value = newActiveTab.url
    } else {
      showHomePage.value = true
      addressBar.value = ''
      currentUrl.value = ''
      await window.api?.tab.hideAll()
    }
  }
}

async function addTab() {
  tabs.value.forEach(t => t.active = false)
  tabs.value.push({ id: `home-${Date.now()}`, title: '新标签页', url: '', active: true })
  showHomePage.value = true
  addressBar.value = ''
  currentUrl.value = ''
  await window.api?.tab.hideAll()
}

async function handleCreateTabFromLink(_event: any, url: string) {
  if (!url) return

  tabs.value.forEach(t => t.active = false)
  const newTabId = `tab-${Date.now()}`
  const newTab: TabData = {
    id: newTabId,
    title: '加载中...',
    url,
    active: true,
    loading: true
  }
  tabs.value.push(newTab)
  showHomePage.value = false
  addressBar.value = url
  currentUrl.value = url

  try {
    const result = await window.api?.tab.createManaged(url)
    if (result) {
      const tab = tabs.value.find(t => t.id === newTabId)
      if (tab) {
        tab.id = result.id
        tab.title = result.title
        tab.loading = result.loading
        tab.error = result.error
      }
    }
  } catch (e: any) {
    console.error('[LuomiNest] 创建链接标签页失败:', e.message)
    const tab = tabs.value.find(t => t.id === newTabId)
    if (tab) {
      tab.title = '加载失败'
      tab.loading = false
      tab.error = e.message
    }
  }
}

async function selectTab(tabId: string) {
  const tab = tabs.value.find(t => t.id === tabId)
  if (!tab) return
  
  tabs.value.forEach(t => t.active = t.id === tabId)
  
  if (tab.url) {
    try {
      await window.api?.tab.activate(tabId)
      showHomePage.value = false
      addressBar.value = tab.url
      currentUrl.value = tab.url
    } catch (e) {
      console.error('[LuomiNest] 切换标签页失败:', e)
    }
  } else {
    showHomePage.value = true
    addressBar.value = ''
    currentUrl.value = ''
    await window.api?.tab.hideAll()
  }
}

async function navigateToUrl() {
  let url = addressBar.value.trim()
  if (!url) return

  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    url = 'https://' + url
  }

  const tab = activeTab.value
  if (!tab) return

  tabs.value.forEach(t => t.active = false)
  
  const newTabId = `tab-${Date.now()}`
  const newTab: TabData = {
    id: newTabId,
    title: '加载中...',
    url,
    active: true,
    loading: true
  }
  
  const existingIdx = tabs.value.findIndex(t => t.id === tab.id && !t.url)
  if (existingIdx !== -1) {
    tabs.value[existingIdx] = newTab
  } else {
    tabs.value.push(newTab)
  }
  
  showHomePage.value = false
  addressBar.value = url
  currentUrl.value = url

  try {
    const result = await window.api?.tab.createManaged(url)
    if (result) {
      const targetTab = tabs.value.find(t => t.id === newTabId)
      if (targetTab) {
        targetTab.id = result.id
        targetTab.title = result.title
        targetTab.loading = result.loading
        targetTab.error = result.error
      }
    }
  } catch (e: any) {
    console.error('[LuomiNest] 导航失败:', e.message)
    const targetTab = tabs.value.find(t => t.id === newTabId)
    if (targetTab) {
      targetTab.title = '加载失败'
      targetTab.loading = false
      targetTab.error = e.message
    }
  }
}

async function handleBookmark(bm: typeof bookmarks.value[0]) {
  if (!bm.url) return
  addressBar.value = bm.url
  await navigateToUrl()
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
      devPanelMode.value = 'script'
      break
    case 'screenshot':
      try {
        const pwTab = await window.api?.playwright.createTab(tab.url)
        if (pwTab) {
          const dataUrl = await window.api?.playwright.screenshot(pwTab.id)
          devOutput.value = `[截图成功] 长度: ${Math.round((dataUrl?.length || 0) / 1024)}KB`
          showDevPanel.value = true
          devPanelMode.value = 'dom'
        }
      } catch (e: any) {
        devOutput.value = `[错误] ${e.message}`
        showDevPanel.value = true
      }
      break
    case 'dom':
      try {
        const pwTab = await window.api?.playwright.createTab(tab.url)
        if (pwTab) {
          const dom = await window.api?.playwright.getDom(pwTab.id)
          devOutput.value = (dom || '').substring(0, 2000) + ((dom?.length || 0) > 2000 ? '\n... (截断)' : '')
          showDevPanel.value = true
          devPanelMode.value = 'dom'
        }
      } catch (e: any) {
        devOutput.value = `[错误] ${e.message}`
        showDevPanel.value = true
      }
      break
    case 'click':
      devOutput.value = '[提示] 请在下方输入 CSS 选择器，然后点击执行'
      devScriptInput.value = ''
      showDevPanel.value = true
      devPanelMode.value = 'script'
      break
    case 'fill':
      devOutput.value = '[提示] 格式: selector|value （选择器和值用|分隔）'
      devScriptInput.value = ''
      showDevPanel.value = true
      devPanelMode.value = 'script'
      break
  }
}

async function executeDevAction() {
  const tab = activeTab.value
  if (!tab?.url) return

  const input = devScriptInput.value.trim()
  if (!input) return

  try {
    const pwTab = await window.api?.playwright.createTab(tab.url)
    if (pwTab && devPanelMode.value === 'script') {
      const result = await window.api?.playwright.executeScript(pwTab.id, input)
      devOutput.value = typeof result === 'string' ? result : JSON.stringify(result, null, 2)
    }
  } catch (e: any) {
    devOutput.value = `[执行错误] ${e.message}`
  }
}

async function handleSearch() {
  const query = browserInput.value.trim()
  if (!query) return

  isSearching.value = true

  if (selectedEngine.value.id === 'ai') {
    console.log('[LuomiNest] AI本地搜索:', query)
    await new Promise(resolve => setTimeout(resolve, 300))
  } else {
    const searchUrl = selectedEngine.value.url + encodeURIComponent(query)
    
    try {
      const newTab = await window.api?.tab.createManaged(searchUrl)
      if (newTab) {
        tabs.value.forEach(t => t.active = false)
        
        const homeTabIdx = tabs.value.findIndex(t => !t.url && t.active === false)
        if (homeTabIdx !== -1) {
          tabs.value[homeTabIdx] = {
            id: newTab.id,
            title: `${selectedEngine.value.name} - ${query}`,
            url: newTab.url,
            active: true
          }
        } else {
          tabs.value.push({
            id: newTab.id,
            title: `${selectedEngine.value.name} - ${query}`,
            url: newTab.url,
            active: true
          })
        }
        
        showHomePage.value = false
        addressBar.value = searchUrl
        currentUrl.value = searchUrl
      }
    } catch (e: any) {
      console.error('[LuomiNest] 创建搜索标签页失败:', e.message)
    }
  }

  setTimeout(() => {
    isSearching.value = false
    browserInput.value = ''
  }, 300)
}

function handleSearchKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSearch()
  }
}
</script>

<template>
  <div class="browser-view dark">
    <div class="browser-tab-bar">
      <div class="tab-list">
        <div
          v-for="tab in tabs"
          :key="tab.id"
          :class="['tab-item', { active: tab.active, error: tab.error }]"
          @click="selectTab(tab.id)"
        >
          <div v-if="tab.loading" class="tab-loading-spinner" />
          <img v-else-if="tab.favicon" :src="tab.favicon" class="tab-favicon" alt="" />
          <Globe v-else-if="tab.url" :size="12" class="tab-icon" />
          <span class="tab-title">{{ tab.title }}</span>
          <button class="tab-close" aria-label="关闭标签页" @click.stop="closeTab(tab.id)">
            <X :size="12" />
          </button>
        </div>
        <button class="tab-add" aria-label="新建标签页" @click="addTab">
          <Plus :size="14" />
        </button>
      </div>
    </div>

    <div class="browser-nav-bar">
      <div class="nav-buttons">
        <button class="nav-btn" aria-label="后退">
          <ArrowLeft :size="16" />
        </button>
        <button class="nav-btn" aria-label="前进">
          <ArrowRight :size="16" />
        </button>
        <button class="nav-btn" aria-label="刷新" @click="navigateToUrl">
          <RotateCw :size="14" />
        </button>
      </div>
      <div class="address-bar">
        <Search :size="15" class="addr-icon" />
        <input
          v-model="addressBar"
          type="text"
          class="addr-input"
          placeholder="搜索或输入网址"
          @keydown.enter="navigateToUrl"
        />
      </div>
      <div class="nav-right">
        <button class="nav-btn" aria-label="收藏">
          <Star :size="15" />
        </button>
        <button
          :class="['nav-btn', 'dev-toggle', { active: showDevPanel }]"
          aria-label="开发者面板"
          @click="showDevPanel = !showDevPanel"
        >
          <Code2 :size="15" />
        </button>
      </div>
    </div>

    <div class="bookmark-bar">
      <button
        v-for="(bm, idx) in bookmarks"
        :key="idx"
        class="bookmark-item"
        @click="handleBookmark(bm)"
      >
        <Globe :size="13" class="bm-icon-svg" />
        <span class="bm-name">{{ bm.name }}</span>
      </button>
      <button class="bookmark-more" aria-label="更多书签">
        <ChevronRight :size="14" />
      </button>
    </div>

    <div class="browser-content" :class="{ 'with-panel': showDevPanel }">
      <div v-if="showHomePage" class="copilot-center">
        <div class="brand-area">
          <h1 class="brand-title animate-brand-reveal">
            <span class="brand-lumi">Luomi</span><span class="brand-sub">Nest</span>
          </h1>
          <p class="brand-tagline animate-fade-in">copilot · playwright powered</p>
        </div>

        <div class="ai-input-section animate-slide-up">
          <div class="ai-input-box">
            <div class="search-engine-bar">
              <button class="engine-selector" @click="showEngineDropdown = !showEngineDropdown">
                <component :is="selectedEngine.icon" :size="16" :style="{ color: selectedEngine.color }" />
                <span class="engine-name">{{ selectedEngine.name }}</span>
                <ChevronDown :size="14" class="engine-arrow" :class="{ rotated: showEngineDropdown }" />
              </button>
              <Transition name="dropdown">
                <div v-if="showEngineDropdown" class="engine-dropdown">
                  <button
                    v-for="engine in searchEngines"
                    :key="engine.id"
                    :class="['engine-option', { active: engine.id === selectedEngine.id }]"
                    @click="selectEngine(engine)"
                  >
                    <component :is="engine.icon" :size="15" :style="{ color: engine.color }" />
                    <span>{{ engine.name }}</span>
                    <div v-if="engine.id === selectedEngine.id" class="engine-check" />
                  </button>
                </div>
              </Transition>
            </div>
            <textarea
              v-model="browserInput"
              :placeholder="selectedEngine.id === 'ai' ? '向 AI 提问...' : `在 ${selectedEngine.name} 中搜索...`"
              rows="2"
              class="ai-textarea"
              @keydown="handleSearchKeydown"
            ></textarea>
            <div class="ai-input-actions">
              <div class="ai-actions-left">
                <button class="ai-tool-btn" title="对话模式">
                  <MessageSquare :size="16" />
                  <span>对话模式</span>
                  <ChevronDown :size="13" />
                </button>
                <button class="ai-tool-btn icon-only" title="@提及">
                  <AtSign :size="16" />
                </button>
              </div>
              <div class="ai-actions-right">
                <button class="ai-tool-btn icon-only" title="附件">
                  <Paperclip :size="16" />
                </button>
                <button class="ai-tool-btn icon-only" title="更多">
                  <ChevronDown :size="16" />
                </button>
                <button
                  class="ai-send-btn"
                  :class="{ loading: isSearching }"
                  :disabled="!browserInput.trim() || isSearching"
                  title="搜索"
                  @click="handleSearch"
                >
                  <Send v-if="!isSearching" :size="17" />
                  <div v-else class="loading-spinner" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="quick-actions-grid animate-scale-in">
          <button
            v-for="action in quickActions"
            :key="action.label"
            class="qa-card"
            :style="{ '--qa-color': action.color }"
            @click="handleQuickAction(action.action)"
          >
            <div class="qa-icon-wrap">
              <component :is="action.icon" :size="22" />
            </div>
            <span class="qa-label">{{ action.label }}</span>
          </button>
        </div>
      </div>
    </div>

    <Transition name="panel-slide-up">
      <div v-if="showDevPanel" class="dev-panel">
        <div class="dev-panel-header">
          <div class="dev-tabs">
            <button
              :class="['dev-tab', { active: devPanelMode === 'script' }]"
              @click="devPanelMode = 'script'"
            >
              <Code2 :size="13" />
              <span>脚本</span>
            </button>
            <button
              :class="['dev-tab', { active: devPanelMode === 'dom' }]"
              @click="devPanelMode = 'dom'"
            >
              <Globe :size="13" />
              <span>输出</span>
            </button>
          </div>
          <button class="dev-close-btn" @click="showDevPanel = false">
            <X :size="14" />
          </button>
        </div>
        <div v-if="devPanelMode === 'script'" class="dev-panel-body">
          <input
            v-model="devScriptInput"
            type="text"
            class="dev-script-input"
            placeholder="输入 JS 表达式 / CSS 选择器 / selector|值 ..."
            @keydown.enter="executeDevAction"
          />
          <button class="dev-exec-btn" @click="executeDevAction">
            <Send :size="13" />
            执行
          </button>
        </div>
        <div class="dev-output">
          <pre v-if="devOutput" class="dev-output-text">{{ devOutput }}</pre>
          <div v-else class="dev-output-placeholder">
            <Code2 :size="20" />
            <span>执行结果将显示在这里</span>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.browser-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--browser-bg);
  color: var(--browser-text);
}

.browser-tab-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 38px;
  background: var(--browser-surface);
  border-bottom: 1px solid var(--browser-border);
  flex-shrink: 0;
  padding-left: 8px;
}

.tab-list {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: 1;
  overflow-x: auto;
  scrollbar-width: none;
}

.tab-list::-webkit-scrollbar {
  display: none;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 180px;
  height: 32px;
  padding: 0 10px 0 14px;
  border-radius: 6px 6px 0 0;
  font-size: 12px;
  color: var(--browser-text-dim);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
  position: relative;
}

.tab-item:hover {
  background: var(--browser-elevated);
  color: var(--browser-text);
}

.tab-item.active {
  background: var(--browser-bg);
  color: var(--browser-text);
}

.tab-icon {
  flex-shrink: 0;
  opacity: 0.6;
}

.tab-favicon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  object-fit: contain;
  border-radius: 2px;
}

.tab-title {
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--browser-text);
}

.tab-close {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  opacity: 0;
  transition: all var(--transition-fast);
  color: inherit;
  flex-shrink: 0;
}

.tab-item:hover .tab-close {
  opacity: 0.6;
}

.tab-loading-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--browser-border);
  border-top-color: var(--lumi-primary);
  border-radius: 50%;
  animation: tab-spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes tab-spin {
  to { transform: rotate(360deg); }
}

.tab-item.error .tab-title {
  color: #f87171;
}

.tab-item.error .tab-icon {
  color: #f87171;
}

.tab-close:hover {
  opacity: 1 !important;
  background: rgba(255,255,255,0.1);
}

.tab-add {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  color: var(--browser-text-dim);
  transition: all var(--transition-fast);
  flex-shrink: 0;
  margin-right: 8px;
}

.tab-add:hover {
  background: var(--browser-elevated);
  color: var(--browser-text);
}

.browser-nav-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--browser-surface);
  flex-shrink: 0;
}

.nav-buttons {
  display: flex;
  gap: 2px;
}

.nav-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  color: var(--browser-text-dim);
  transition: all var(--transition-fast);
}

.nav-btn:hover {
  background: var(--browser-elevated);
  color: var(--browser-text);
}

.nav-btn.dev-toggle.active {
  color: #8b5cf6;
  background: rgba(139, 92, 246, 0.12);
}

.address-bar {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 14px;
  background: var(--browser-input);
  border: 1px solid var(--browser-input-border);
  border-radius: var(--radius-lg);
  transition: all var(--transition-fast);
}

.address-bar:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 2px rgba(13, 148, 136, 0.2);
}

.addr-icon {
  color: var(--browser-text-dim);
  flex-shrink: 0;
}

.addr-input {
  flex: 1;
  background: transparent;
  font-size: 13px;
  color: var(--browser-text);
}

.addr-input::placeholder {
  color: var(--browser-text-dim);
}

.nav-right {
  display: flex;
  gap: 2px;
}

.bookmark-bar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 12px;
  background: var(--browser-surface);
  border-bottom: 1px solid var(--browser-border);
  overflow-x: auto;
  flex-shrink: 0;
  scrollbar-width: none;
}

.bookmark-bar::-webkit-scrollbar {
  display: none;
}

.bookmark-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--browser-text-dim);
  white-space: nowrap;
  transition: all var(--transition-fast);
}

.bookmark-item:hover {
  background: var(--browser-elevated);
  color: var(--browser-text);
}

.bm-icon-svg {
  color: var(--text-muted);
  flex-shrink: 0;
}

.bm-name {
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--browser-text);
}

.bookmark-more {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--browser-text-dim);
  border-radius: 4px;
  flex-shrink: 0;
  transition: all var(--transition-fast);
}

.bookmark-more:hover {
  background: var(--browser-elevated);
  color: var(--browser-text);
}

.browser-content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  position: relative;
  min-height: 400px;
  contain: layout style;
}

.browser-content.with-panel {
  align-items: stretch;
}

.copilot-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 40px;
  width: 100%;
  max-width: 680px;
  padding: 40px;
}

.brand-area {
  text-align: center;
  user-select: none;
}

@keyframes brand-reveal {
  0% {
    opacity: 0;
    transform: translateY(24px) scale(0.96);
    filter: blur(8px);
    letter-spacing: 8px;
  }
  60% {
    opacity: 1;
    filter: blur(0);
    letter-spacing: -2px;
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
    letter-spacing: -3px;
  }
}

.animate-brand-reveal {
  animation: brand-reveal 0.8s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.brand-title {
  font-size: 56px;
  font-weight: 300;
  letter-spacing: -3px;
  line-height: 1;
  margin-bottom: 4px;
}

.brand-lumi {
  font-weight: 700;
  background: linear-gradient(135deg, #d6d3d1 0%, #a8a29e 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.brand-sub {
  font-weight: 300;
  color: var(--browser-text-dim);
  -webkit-text-fill-color: var(--browser-text-dim);
}

.brand-tagline {
  font-size: 15px;
  font-weight: 400;
  color: var(--browser-text-dim);
  letter-spacing: 3px;
  text-transform: lowercase;
}

.ai-input-section {
  width: 100%;
}

.ai-input-box {
  background: var(--browser-elevated);
  border: 1px solid var(--browser-border);
  border-radius: var(--radius-xl);
  overflow: hidden;
  transition: all var(--transition-normal);
}

.ai-input-box:focus-within {
  border-color: rgba(13, 148, 136, 0.4);
  box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.08), 0 8px 32px rgba(0,0,0,0.3);
}

.search-engine-bar {
  position: relative;
  padding: 12px 16px;
  border-bottom: 1px solid var(--browser-border);
}

.engine-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--browser-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.engine-selector:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.15);
}

.engine-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--browser-text);
}

.engine-arrow {
  color: var(--browser-text-dim);
  transition: transform var(--transition-fast);
}

.engine-arrow.rotated {
  transform: rotate(180deg);
}

.engine-dropdown {
  position: absolute;
  top: calc(100% - 4px);
  left: 16px;
  min-width: 160px;
  background: var(--browser-elevated);
  border: 1px solid var(--browser-border);
  border-radius: var(--radius-md);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  z-index: 100;
  overflow: hidden;
}

.engine-option {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--browser-text-dim);
  transition: all var(--transition-fast);
}

.engine-option:hover {
  background: rgba(255, 255, 255, 0.06);
  color: var(--browser-text);
}

.engine-option.active {
  background: rgba(13, 148, 136, 0.1);
  color: var(--browser-text);
}

.engine-check {
  width: 6px;
  height: 6px;
  margin-left: auto;
  border-radius: 50%;
  background: var(--lumi-primary);
}

.ai-textarea {
  width: 100%;
  padding: 18px 20px;
  font-size: 15px;
  resize: none;
  min-height: 56px;
  max-height: 140px;
  background: transparent;
  color: var(--browser-text);
  line-height: 1.6;
}

.ai-textarea::placeholder {
  color: var(--browser-text-dim);
}

.ai-input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px 14px;
  border-top: 1px solid var(--browser-border);
}

.ai-actions-left,
.ai-actions-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.ai-tool-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 11px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--browser-text-dim);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
}

.ai-tool-btn:hover {
  background: rgba(255,255,255,0.06);
  color: var(--browser-text);
}

.ai-tool-btn.icon-only {
  padding: 7px;
}

.ai-send-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: var(--lumi-primary);
  color: white;
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-left: 6px;
}

.ai-send-btn:hover {
  background: var(--lumi-primary-hover);
  transform: scale(1.05);
  box-shadow: 0 4px 16px rgba(13, 148, 136, 0.35);
}

.quick-actions-grid {
  display: flex;
  gap: 16px;
}

.qa-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 18px 20px;
  border-radius: var(--radius-lg);
  background: var(--browser-surface);
  border: 1px solid var(--browser-border);
  cursor: pointer;
  transition: all var(--transition-normal);
  min-width: 90px;
}

.qa-card:hover {
  border-color: var(--qa-color);
  box-shadow: 0 4px 20px color-mix(in srgb, var(--qa-color) 15%, transparent);
  transform: translateY(-3px);
}

.qa-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--qa-color) 12%, transparent);
  color: var(--qa-color);
  transition: all var(--transition-normal);
}

.qa-card:hover .qa-icon-wrap {
  background: color-mix(in srgb, var(--qa-color) 20%, transparent);
  transform: scale(1.08);
}

.qa-label {
  font-size: 12px;
  color: var(--browser-text-dim);
  font-weight: 500;
  transition: color var(--transition-fast);
}

.qa-card:hover .qa-label {
  color: var(--browser-text);
}

.dev-panel {
  height: 220px;
  background: var(--browser-elevated);
  border-top: 1px solid var(--browser-border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.dev-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid var(--browser-border);
  height: 38px;
  flex-shrink: 0;
}

.dev-tabs {
  display: flex;
  gap: 2px;
}

.dev-tab {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 0 14px;
  height: 38px;
  font-size: 12px;
  color: var(--browser-text-dim);
  border-bottom: 2px solid transparent;
  transition: all var(--transition-fast);
}

.dev-tab.active {
  color: var(--browser-text);
  border-bottom-color: #8b5cf6;
}

.dev-close-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--browser-text-dim);
  transition: all var(--transition-fast);
}

.dev-close-btn:hover {
  background: rgba(255,255,255,0.06);
  color: var(--browser-text);
}

.dev-panel-body {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  flex-shrink: 0;
}

.dev-script-input {
  flex: 1;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--browser-input);
  border: 1px solid var(--browser-border);
  font-size: 12px;
  color: var(--browser-text);
  font-family: 'Cascadia Code', 'Fira Code', monospace;
}

.dev-script-input::placeholder {
  color: var(--browser-text-dim);
}

.dev-exec-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 7px 14px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  background: #8b5cf6;
  color: white;
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
}

.dev-exec-btn:hover {
  background: #7c3aed;
  transform: scale(1.02);
}

.dev-output {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px 10px;
  min-height: 0;
}

.dev-output-text {
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  font-size: 11px;
  line-height: 1.6;
  color: var(--browser-text-dim);
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

.dev-output-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px;
  color: var(--browser-text-dim);
  opacity: 0.4;
  font-size: 12px;
}

.panel-slide-up-enter-active {
  animation: slideUp 0.25s ease-out both;
}

.panel-slide-up-leave-active {
  animation: slideUp 0.2s ease-in reverse both;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(10px); height: 0; }
  to { opacity: 1; transform: translateY(0); height: 220px; }
}

.ai-send-btn.loading {
  background: var(--lumi-primary-hover);
  cursor: wait;
}

.ai-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.loading-spinner {
  width: 17px;
  height: 17px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.dropdown-enter-active,
.dropdown-leave-active {
  transition: all var(--transition-fast);
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.animate-fade-in {
  animation: fadeIn 0.5s ease-out both;
}

.animate-slide-up {
  animation: slideUpFade 0.6s ease-out both;
}

.animate-scale-in {
  animation: scaleIn 0.4s ease-out both;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUpFade {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
</style>
