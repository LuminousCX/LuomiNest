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
  padding: 40px;
  gap: 32px;
  background: linear-gradient(180deg, #fafaf9 0%, #f5f5f4 100%);
}

.brand-area {
  text-align: center;
}

.brand-title {
  font-size: 42px;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 0;
}

.brand-lumi {
  color: #1c1917;
}

.brand-sub {
  color: #78716c;
}

.brand-tagline {
  margin-top: 8px;
  font-size: 14px;
  color: #a8a29e;
}

.search-section {
  width: 100%;
  max-width: 600px;
}

.search-box {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #e7e5e4;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

.engine-bar {
  padding: 12px 16px;
  border-bottom: 1px solid #f5f5f4;
  position: relative;
}

.engine-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 8px;
  background: #f5f5f4;
  border: none;
  cursor: pointer;
  transition: background 0.15s ease;
}

.engine-selector:hover {
  background: #e7e5e4;
}

.engine-name {
  font-size: 13px;
  color: #44403c;
}

.engine-arrow {
  color: #78716c;
  transition: transform 0.2s ease;
}

.engine-arrow.rotated {
  transform: rotate(180deg);
}

.engine-dropdown {
  position: absolute;
  top: 100%;
  left: 12px;
  margin-top: 4px;
  background: #ffffff;
  border-radius: 8px;
  border: 1px solid #e7e5e4;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  z-index: 100;
}

.engine-option {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 14px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 13px;
  color: #44403c;
  transition: background 0.15s ease;
}

.engine-option:hover {
  background: #f5f5f4;
}

.engine-option.active {
  background: #fafaf9;
}

.search-textarea {
  width: 100%;
  min-height: 60px;
  padding: 16px;
  border: none;
  font-size: 15px;
  color: #1c1917;
  resize: none;
  outline: none;
}

.search-textarea::placeholder {
  color: #a8a29e;
}

.search-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-top: 1px solid #f5f5f4;
}

.actions-left,
.actions-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 6px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 13px;
  color: #78716c;
  transition: all 0.15s ease;
}

.tool-btn:hover {
  background: #f5f5f4;
  color: #44403c;
}

.tool-btn.icon-only {
  padding: 6px;
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: #1c1917;
  border: none;
  cursor: pointer;
  color: #ffffff;
  transition: all 0.15s ease;
}

.send-btn:hover:not(:disabled) {
  background: #44403c;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.quick-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}

.qa-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 20px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #e7e5e4;
  cursor: pointer;
  transition: all 0.15s ease;
}

.qa-card:hover {
  border-color: var(--qa-color);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.qa-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--qa-color), color-mix(in srgb, var(--qa-color) 70%, white));
  color: #ffffff;
}

.qa-label {
  font-size: 12px;
  color: #57534e;
}

.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.2s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
