<script setup lang="ts">
import { ref, computed } from 'vue'
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
  Camera
} from 'lucide-vue-next'

const tabs = ref([
  { id: 'tab-1', title: '新标签页', url: '', active: true },
  { id: 'tab-2', title: 'GitHub', url: 'https://github.com', active: false }
])

const addressBar = ref('')
const browserInput = ref('')
const currentUrl = ref('')

const bookmarks = ref([
  { name: 'GitHub', icon: null, url: 'https://github.com' },
  { name: 'Google', icon: null, url: 'https://google.com' },
  { name: 'MDN', icon: null, url: 'https://developer.mozilla.org' },
  { name: 'Stack Overflow', icon: null, url: 'https://stackoverflow.com' },
  { name: 'Playwright 文档', icon: null, url: 'https://playwright.dev' },
  { name: 'Electron 文档', icon: null, url: 'https://electronjs.org' }
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

function minimizeWindow() {
  (globalThis as any).api?.window?.minimize()
}

function maximizeWindow() {
  (globalThis as any).api?.window?.maximize()
}

function closeWindow() {
  (globalThis as any).api?.window?.close()
}

function closeTab(id: string) {
  const idx = tabs.value.findIndex(t => t.id === id)
  if (idx > -1) {
    tabs.value.splice(idx, 1)
    if (tabs.value.length > 0 && !tabs.value.find(t => t.active)) {
      tabs.value[Math.max(0, idx - 1)].active = true
    }
  }
}

async function addTab() {
  const newId = `tab-${Date.now()}`
  tabs.value.forEach(t => t.active = false)
  tabs.value.push({ id: newId, title: '新标签页', url: '', active: true })
}

function selectTab(tabId: string) {
  tabs.value.forEach(t => t.active = t.id === tabId)
  const tab = tabs.value.find(t => t.id === tabId)
  if (tab?.url) {
    addressBar.value = tab.url
    currentUrl.value = tab.url
  } else {
    addressBar.value = ''
    currentUrl.value = ''
  }
}

async function navigateToUrl() {
  let url = addressBar.value.trim()
  if (!url) return

  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    url = 'https://' + url
  }

  const tab = activeTab.value
  if (tab && window.api?.playwright) {
    try {
      const updated = await window.api.playwright.navigate(tab.id, url)
      tab.title = updated.title || url
      tab.url = url
      currentUrl.value = url
      addressBar.value = url
    } catch {
      tab.url = url
      tab.title = new URL(url).hostname
      currentUrl.value = url
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
  if (!tab?.id || !window.api?.playwright) return

  switch (action) {
    case 'script':
      showDevPanel.value = !showDevPanel.value
      devPanelMode.value = 'script'
      break
    case 'screenshot':
      try {
        const dataUrl = await window.api.playwright.screenshot(tab.id)
        devOutput.value = `[截图成功] 长度: ${Math.round(dataUrl.length / 1024)}KB`
        showDevPanel.value = true
        devPanelMode.value = 'dom'
      } catch (e: any) {
        devOutput.value = `[错误] ${e.message}`
        showDevPanel.value = true
      }
      break
    case 'dom':
      try {
        const dom = await window.api.playwright.getDom(tab.id)
        devOutput.value = dom.substring(0, 2000) + (dom.length > 2000 ? '\n... (截断)' : '')
        showDevPanel.value = true
        devPanelMode.value = 'dom'
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
  if (!tab?.id || !window.api?.playwright) return

  const input = devScriptInput.value.trim()
  if (!input) return

  try {
    if (devPanelMode.value === 'script') {
      const result = await window.api.playwright.executeScript(tab.id, input)
      devOutput.value = typeof result === 'string' ? result : JSON.stringify(result, null, 2)
    }
  } catch (e: any) {
    devOutput.value = `[执行错误] ${e.message}`
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
          :class="['tab-item', { active: tab.active }]"
          @click="selectTab(tab.id)"
        >
          <Globe v-if="!tab.url" :size="12" class="tab-icon" />
          <span class="tab-title">{{ tab.title }}</span>
          <button class="tab-close" @click.stop="closeTab(tab.id)">
            <X :size="12" />
          </button>
        </div>
        <button class="tab-add" @click="addTab" title="新建标签页">
          <Plus :size="14" />
        </button>
      </div>
      <div class="window-controls-dark">
        <button class="wc-btn minimize" @click="minimizeWindow()">
          <svg width="10" height="1" viewBox="0 0 10 1"/>
        </button>
        <button class="wc-btn maximize" @click="maximizeWindow()">
          <svg width="10" height="10" viewBox="0 0 10 10"><rect x="0.5" y="0.5" width="9" height="9" fill="none" stroke="currentColor" stroke-width="1"/></svg>
        </button>
        <button class="wc-btn close" @click="closeWindow()">
          <X :size="12" />
        </button>
      </div>
    </div>

    <div class="browser-nav-bar">
      <div class="nav-buttons">
        <button class="nav-btn" title="后退">
          <ArrowLeft :size="16" />
        </button>
        <button class="nav-btn" title="前进">
          <ArrowRight :size="16" />
        </button>
        <button class="nav-btn" title="刷新" @click="navigateToUrl">
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
        <button class="nav-btn" title="收藏">
          <Star :size="15" />
        </button>
        <button
          :class="['nav-btn', 'dev-toggle', { active: showDevPanel }]"
          title="开发者面板"
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
      <button class="bookmark-more">
        <ChevronRight :size="14" />
      </button>
    </div>

    <div class="browser-content" :class="{ 'with-panel': showDevPanel }">
      <div class="copilot-center">
        <div class="brand-area">
          <h1 class="brand-title animate-brand-reveal">
            <span class="brand-lumi">Luomi</span><span class="brand-sub">Nest</span>
          </h1>
          <p class="brand-tagline animate-fade-in">copilot · playwright powered</p>
        </div>

        <div class="ai-input-section animate-slide-up">
          <div class="ai-input-box">
            <textarea
              v-model="browserInput"
              placeholder="有问题尽管问 Luomi，或让 AI 帮你操作浏览器"
              rows="2"
              class="ai-textarea"
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
                <button class="ai-send-btn" title="发送">
                  <Send :size="17" />
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
  opacity: 0.5;
}

.tab-title {
  overflow: hidden;
  text-overflow: ellipsis;
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

.window-controls-dark {
  display: flex;
  gap: 2px;
  padding-right: 8px;
}

.wc-btn {
  width: 36px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--browser-text-dim);
  transition: all var(--transition-fast);
  border-radius: 0;
}

.wc-btn:hover {
  background: var(--browser-elevated);
  color: var(--browser-text);
}

.wc-btn.close:hover {
  background: #e5484d;
  color: white;
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
  min-height: 0;
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
</style>
