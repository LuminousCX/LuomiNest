<script setup lang="ts">
import { ref } from 'vue'
import type { Component } from 'vue'
import {
  Send,
  ChevronDown,
  Globe,
  MousePointerClick,
  Code2,
  Camera,
  Bot,
  Tv,
  Video,
  Search,
  ArrowRight
} from 'lucide-vue-next'

interface SearchEngine {
  id: string
  name: string
  icon: Component
  url: string
  color: string
}

interface QuickAction {
  icon: Component
  label: string
  color: string
  action: string
}

interface Website {
  name: string
  initial: string
  url: string
  className: string
}

const searchEngines: SearchEngine[] = [
  { id: 'bing', name: 'Bing', icon: Search, url: 'https://www.bing.com/search?q=', color: 'var(--lumi-brand)' },
  { id: 'google', name: 'Google', icon: Globe, url: 'https://www.google.com/search?q=', color: 'var(--lumi-info)' },
  { id: 'bilibili', name: 'Bilibili', icon: Tv, url: 'https://search.bilibili.com/all?keyword=', color: 'var(--lumi-sky)' },
  { id: 'youtube', name: 'YouTube', icon: Video, url: 'https://www.youtube.com/results?search_query=', color: 'var(--lumi-danger)' },
  { id: 'ai', name: 'AI', icon: Bot, url: '', color: 'var(--task-purple)' }
]

const websites: Website[] = [
  { name: 'GitHub', initial: 'G', url: 'https://github.com', className: 'ws-github' },
  { name: 'Google', initial: 'G', url: 'https://google.com', className: 'ws-google' },
  { name: 'MDN', initial: 'M', url: 'https://developer.mozilla.org', className: 'ws-mdn' },
  { name: 'Stack Overflow', initial: 'S', url: 'https://stackoverflow.com', className: 'ws-stack' },
  { name: 'Bing', initial: 'B', url: 'https://www.bing.com', className: 'ws-bing' },
  { name: 'Bilibili', initial: 'B', url: 'https://www.bilibili.com', className: 'ws-bili' },
  { name: 'YouTube', initial: 'Y', url: 'https://www.youtube.com', className: 'ws-youtube' },
  { name: '知乎', initial: '知', url: 'https://www.zhihu.com', className: 'ws-zhihu' }
]

const quickActions: QuickAction[] = [
  { icon: Code2, label: '执行脚本', color: 'var(--task-purple)', action: 'script' },
  { icon: Camera, label: '页面截图', color: 'var(--lumi-info)', action: 'screenshot' },
  { icon: MousePointerClick, label: '点击元素', color: 'var(--lumi-success)', action: 'click' },
  { icon: Globe, label: '读取DOM', color: 'var(--lumi-amber)', action: 'dom' },
  { icon: Send, label: '填表单', color: 'var(--lumi-accent)', action: 'fill' }
]

const searchInput = ref('')
const selectedEngine = ref<SearchEngine>(searchEngines[0])
const showEngineDropdown = ref(false)
const isSearching = ref(false)

const emit = defineEmits<{
  search: [url: string]
  action: [action: string]
}>()

function selectEngine(engine: SearchEngine) {
  selectedEngine.value = engine
  showEngineDropdown.value = false
}

function handleSearch() {
  const query = searchInput.value.trim()
  if (!query) return

  isSearching.value = true

  if (selectedEngine.value.id === 'ai') {
    emit('action', 'ai-search')
  } else {
    const url = selectedEngine.value.url + encodeURIComponent(query)
    emit('search', url)
  }

  setTimeout(() => {
    isSearching.value = false
    searchInput.value = ''
  }, 300)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSearch()
  }
}

function handleWebsiteClick(url: string) {
  emit('search', url)
}
</script>

<template>
  <div class="home-page">
    <!-- 顶部品牌 + 搜索框 -->
    <header class="home-header">
      <h1 class="brand-title">
        <span class="brand-lumi">Luomi</span><span class="brand-sub">Nest</span>
      </h1>

      <div class="search-box">
        <div class="search-input-row">
          <button class="engine-selector" @click="showEngineDropdown = !showEngineDropdown">
            <component :is="selectedEngine.icon" :size="16" :style="{ color: selectedEngine.color }" />
            <span class="engine-name">{{ selectedEngine.name }}</span>
            <ChevronDown :size="14" class="engine-arrow" :class="{ rotated: showEngineDropdown }" />
          </button>

          <input
            v-model="searchInput"
            :placeholder="selectedEngine.id === 'ai' ? '向 AI 提问...' : `在 ${selectedEngine.name} 中搜索...`"
            class="search-input"
            @keydown="handleKeydown"
          />

          <button
            class="send-btn"
            :class="{ loading: isSearching }"
            :disabled="!searchInput.trim() || isSearching"
            @click="handleSearch"
            aria-label="搜索"
          >
            <ArrowRight v-if="!isSearching" :size="18" />
            <div v-else class="loading-spinner" />
          </button>
        </div>

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
            </button>
          </div>
        </Transition>
      </div>
    </header>

    <!-- 常用网站 -->
    <section class="content-section">
      <h2 class="section-title">
        <span class="title-bar"></span>
        常用网站
      </h2>
      <div class="websites-grid">
        <button
          v-for="ws in websites"
          :key="ws.name"
          class="website-tile"
          :title="ws.name"
          @click="handleWebsiteClick(ws.url)"
        >
          <div :class="['website-icon', ws.className]">{{ ws.initial }}</div>
          <span class="website-name">{{ ws.name }}</span>
        </button>
      </div>
    </section>

    <!-- 开发者工具 -->
    <section class="content-section">
      <h2 class="section-title">
        <span class="title-bar"></span>
        开发者工具
      </h2>
      <div class="tools-grid">
        <button
          v-for="action in quickActions"
          :key="action.label"
          class="tool-card"
          :style="{ '--tool-color': action.color }"
          @click="emit('action', action.action)"
        >
          <div class="tool-icon">
            <component :is="action.icon" :size="20" />
          </div>
          <span class="tool-label">{{ action.label }}</span>
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-8) var(--space-6) var(--space-6);
  gap: var(--space-7);
  background: linear-gradient(180deg, var(--bg) 0%, var(--lumi-brand-subtle) 60%, var(--bg-secondary) 100%);
  overflow-y: auto;
}

/* ===== 顶部品牌 + 搜索框 ===== */
.home-header {
  width: 100%;
  max-width: 720px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-5);
}

.brand-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-semibold);
  letter-spacing: -0.02em;
  margin: 0;
}

.brand-lumi {
  color: var(--text);
}

.brand-sub {
  color: var(--text-muted);
}

.search-box {
  width: 100%;
  position: relative;
}

.search-input-row {
  display: flex;
  align-items: center;
  height: var(--space-10);
  background: var(--surface);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-sm), var(--shadow-inset);
  padding: 0 var(--space-2) 0 var(--space-3);
  gap: var(--space-2);
  transition: all var(--transition-normal);
}

.search-input-row:focus-within {
  border-color: var(--lumi-brand-border);
  box-shadow: var(--shadow-md), 0 0 0 3px var(--lumi-brand-light);
}

.engine-selector {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  border: none;
  cursor: pointer;
  height: calc(var(--space-8) - var(--space-1));
  flex-shrink: 0;
  transition: background var(--transition-fast);
}

.engine-selector:hover {
  background: var(--border);
}

.engine-name {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.engine-arrow {
  color: var(--text-muted);
  transition: transform var(--transition-fast);
}

.engine-arrow.rotated {
  transform: rotate(180deg);
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: var(--text-base);
  color: var(--text);
  outline: none;
  height: 100%;
}

.search-input::placeholder {
  color: var(--text-muted);
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-8);
  height: var(--space-8);
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--text), var(--text-secondary));
  border: none;
  cursor: pointer;
  color: var(--text-inverse);
  flex-shrink: 0;
  transition: all var(--transition-fast);
}

.send-btn:hover:not(:disabled) {
  background: var(--text-secondary);
  transform: scale(1.05);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.loading-spinner {
  width: var(--space-4);
  height: var(--space-4);
  border: 2px solid color-mix(in srgb, var(--text-inverse) 30%, transparent);
  border-top-color: var(--text-inverse);
  border-radius: var(--radius-full);
  animation: spin calc(var(--duration-normal) * 3 + var(--duration-fast)) linear infinite;
}

.engine-dropdown {
  position: absolute;
  top: calc(100% + var(--space-1));
  left: 0;
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-md);
  overflow: hidden;
  z-index: var(--z-dropdown);
  min-width: 160px;
}

.engine-option {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-2) var(--space-4);
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  transition: background var(--transition-fast);
}

.engine-option:hover {
  background: var(--bg-secondary);
}

.engine-option.active {
  background: var(--bg);
}

/* ===== 内容分区通用 ===== */
.content-section {
  width: 100%;
  max-width: 720px;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.section-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-muted);
  margin: 0;
  letter-spacing: 0.02em;
}

.title-bar {
  display: inline-block;
  width: 3px;
  height: var(--space-4);
  background: var(--lumi-brand);
  border-radius: var(--radius-xs);
}

/* ===== 常用网站磁贴 ===== */
.websites-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
}

.website-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-2);
  border-radius: var(--radius-lg);
  background: var(--surface);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.website-tile:hover {
  border-color: var(--ws-color, var(--lumi-brand-border));
  box-shadow: var(--shadow-md);
  transform: translateY(calc(var(--space-1) / -2));
}

.website-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: calc(var(--space-8) + var(--space-1));
  height: calc(var(--space-8) + var(--space-1));
  border-radius: var(--radius-md);
  background: var(--ws-color, var(--lumi-brand));
  color: var(--text-inverse);
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  transition: transform var(--transition-fast);
}

.website-tile:hover .website-icon {
  transform: scale(1.08);
}

.website-name {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

/* 网站品牌色（通过 CSS 变量定义，避免硬编码） */
.ws-github { --ws-color: #24292e; }
.ws-google { --ws-color: #4285f4; }
.ws-mdn { --ws-color: #1a1a1a; }
.ws-stack { --ws-color: #f48024; }
.ws-bing { --ws-color: #008373; }
.ws-bili { --ws-color: #fb7299; }
.ws-youtube { --ws-color: #ff0000; }
.ws-zhihu { --ws-color: #0084ff; }

/* ===== 开发者工具卡片 ===== */
.tools-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--space-3);
}

.tool-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-2);
  border-radius: var(--radius-lg);
  background: var(--surface);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tool-card:hover {
  border-color: var(--tool-color);
  box-shadow: var(--shadow-md);
  transform: translateY(calc(var(--space-1) / -2));
}

.tool-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-8);
  height: var(--space-8);
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--tool-color), color-mix(in srgb, var(--tool-color) 70%, var(--text-inverse)));
  color: var(--text-inverse);
  transition: transform var(--transition-fast);
}

.tool-card:hover .tool-icon {
  transform: scale(1.08);
}

.tool-label {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  text-align: center;
}

/* ===== 动画 ===== */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all var(--transition-fast);
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(calc(var(--space-1) * -2));
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ===== 响应式 ===== */
@media (max-width: 640px) {
  .websites-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .tools-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
