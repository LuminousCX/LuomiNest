<script setup lang="ts">
import { ref } from 'vue'
import {
  Send,
  Paperclip,
  MessageSquare,
  AtSign,
  ChevronDown,
  Globe,
  MousePointerClick,
  Code2,
  Camera,
  Bot,
  Tv,
  Video,
  Search
} from 'lucide-vue-next'

interface SearchEngine {
  id: string
  name: string
  icon: any
  url: string
  color: string
}

interface QuickAction {
  icon: any
  label: string
  color: string
  action: string
}

const searchEngines: SearchEngine[] = [
  { id: 'bing', name: 'Bing', icon: Search, url: 'https://www.bing.com/search?q=', color: '#00809d' },
  { id: 'google', name: 'Google', icon: Globe, url: 'https://www.google.com/search?q=', color: '#4285f4' },
  { id: 'bilibili', name: 'Bilibili', icon: Tv, url: 'https://search.bilibili.com/all?keyword=', color: '#00a1d6' },
  { id: 'youtube', name: 'YouTube', icon: Video, url: 'https://www.youtube.com/results?search_query=', color: '#ff0000' },
  { id: 'ai', name: 'AI', icon: Bot, url: '', color: '#8b5cf6' }
]

const quickActions: QuickAction[] = [
  { icon: Code2, label: '执行脚本', color: '#8b5cf6', action: 'script' },
  { icon: Camera, label: '页面截图', color: '#3b82f6', action: 'screenshot' },
  { icon: MousePointerClick, label: '点击元素', color: '#22c55e', action: 'click' },
  { icon: Globe, label: '读取DOM', color: '#f59e0b', action: 'dom' },
  { icon: Send, label: '填表单', color: '#f43f5e', action: 'fill' }
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
</script>

<template>
  <div class="home-page">
    <div class="brand-area">
      <h1 class="brand-title">
        <span class="brand-lumi">Luomi</span><span class="brand-sub">Nest</span>
      </h1>
      <p class="brand-tagline">copilot · browser powered</p>
    </div>

    <div class="search-section">
      <div class="search-box">
        <div class="engine-bar">
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
              </button>
            </div>
          </Transition>
        </div>
        
        <textarea
          v-model="searchInput"
          :placeholder="selectedEngine.id === 'ai' ? '向 AI 提问...' : `在 ${selectedEngine.name} 中搜索...`"
          rows="2"
          class="search-textarea"
          @keydown="handleKeydown"
        ></textarea>
        
        <div class="search-actions">
          <div class="actions-left">
            <button class="tool-btn">
              <MessageSquare :size="16" />
              <span>对话模式</span>
              <ChevronDown :size="13" />
            </button>
            <button class="tool-btn icon-only">
              <AtSign :size="16" />
            </button>
          </div>
          <div class="actions-right">
            <button class="tool-btn icon-only">
              <Paperclip :size="16" />
            </button>
            <button
              class="send-btn"
              :class="{ loading: isSearching }"
              :disabled="!searchInput.trim() || isSearching"
              @click="handleSearch"
            >
              <Send v-if="!isSearching" :size="17" />
              <div v-else class="loading-spinner" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="quick-actions">
      <button
        v-for="action in quickActions"
        :key="action.label"
        class="qa-card"
        :style="{ '--qa-color': action.color }"
        @click="emit('action', action.action)"
      >
        <div class="qa-icon">
          <component :is="action.icon" :size="22" />
        </div>
        <span class="qa-label">{{ action.label }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.home-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-8);
  gap: var(--space-7);
  background: linear-gradient(180deg, var(--bg) 0%, var(--lumi-brand-subtle) 50%, var(--bg-secondary) 100%);
}

.brand-area {
  text-align: center;
}

.brand-title {
  font-size: 42px;
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

.brand-tagline {
  margin-top: var(--space-2);
  font-size: var(--text-md);
  color: var(--text-muted);
}

.search-section {
  width: 100%;
  max-width: 600px;
}

.search-box {
  background: var(--surface);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-sm), var(--shadow-inset);
  overflow: hidden;
  transition: all var(--transition-normal);
}

.search-box:focus-within {
  border-color: var(--lumi-brand-border);
  box-shadow: var(--shadow-md), 0 0 0 3px var(--lumi-brand-light);
}

.engine-bar {
  padding: var(--space-3) var(--space-4);
  position: relative;
}

.engine-bar::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: var(--space-4);
  right: var(--space-4);
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, var(--bg-secondary) 15%, var(--bg-secondary) 85%, transparent 100%);
}

.engine-selector {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.engine-selector:hover {
  background: var(--border);
}

.engine-name {
  font-size: var(--text-base);
  color: var(--text-secondary);
}

.engine-arrow {
  color: var(--text-muted);
  transition: transform var(--transition-fast);
}

.engine-arrow.rotated {
  transform: rotate(180deg);
}

.engine-dropdown {
  position: absolute;
  top: 100%;
  left: var(--space-3);
  margin-top: var(--space-1);
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-md);
  overflow: hidden;
  z-index: var(--z-dropdown);
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
  font-size: var(--text-base);
  color: var(--text-secondary);
  transition: background var(--transition-fast);
}

.engine-option:hover {
  background: var(--bg-secondary);
}

.engine-option.active {
  background: var(--bg);
}

.search-textarea {
  width: 100%;
  min-height: 60px;
  padding: var(--space-4);
  border: none;
  font-size: var(--text-lg);
  color: var(--text);
  resize: none;
  outline: none;
}

.search-textarea::placeholder {
  color: var(--text-muted);
}

.search-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  position: relative;
}

.search-actions::before {
  content: '';
  position: absolute;
  top: 0;
  left: var(--space-4);
  right: var(--space-4);
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, var(--bg-secondary) 15%, var(--bg-secondary) 85%, transparent 100%);
}

.actions-left,
.actions-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.tool-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: var(--text-base);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.tool-btn:hover {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.tool-btn.icon-only {
  padding: var(--space-1);
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--text), var(--text-secondary));
  border: none;
  cursor: pointer;
  color: var(--text-inverse);
  transition: all var(--transition-fast);
}

.send-btn:hover:not(:disabled) {
  background: var(--text-secondary);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid color-mix(in srgb, var(--text-inverse) 30%, transparent);
  border-top-color: var(--text-inverse);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.quick-actions {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
  justify-content: center;
}

.qa-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
  border-radius: var(--radius-lg);
  background: var(--surface);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.qa-card:hover {
  border-color: var(--qa-color);
  box-shadow: var(--shadow-md), 0 0 0 1px var(--lumi-brand-subtle);
  transform: translateY(-2px);
}

.qa-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--qa-color), color-mix(in srgb, var(--qa-color) 70%, var(--text-inverse)));
  color: var(--text-inverse);
}

.qa-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.dropdown-enter-active,
.dropdown-leave-active {
  transition: all var(--transition-fast);
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
