<script setup lang="ts">
import {
  ref,
  computed,
  watch,
  nextTick,
  onMounted,
  onBeforeUnmount
} from 'vue'
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

// --- 类型定义 ---
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

// --- 数据 ---
const searchEngines: SearchEngine[] = [
  { id: 'bing', name: 'Bing', icon: Search, url: 'https://www.bing.com/search?q=', color: 'var(--lumi-brand)' },
  { id: 'google', name: 'Google', icon: Globe, url: 'https://www.google.com/search?q=', color: 'var(--lumi-info)' },
  { id: 'bilibili', name: 'Bilibili', icon: Tv, url: 'https://search.bilibili.com/all?keyword=', color: 'var(--lumi-sky)' },
  { id: 'youtube', name: 'YouTube', icon: Video, url: 'https://www.youtube.com/results?search_query=', color: 'var(--lumi-danger)' },
  { id: 'ai', name: 'AI', icon: Bot, url: '', color: 'var(--lumi-accent)' }
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
  { icon: Code2, label: '执行脚本', color: 'var(--task-sky)', action: 'script' },
  { icon: Camera, label: '页面截图', color: 'var(--lumi-info)', action: 'screenshot' },
  { icon: MousePointerClick, label: '点击元素', color: 'var(--lumi-success)', action: 'click' },
  { icon: Globe, label: '读取DOM', color: 'var(--lumi-amber)', action: 'dom' },
  { icon: Send, label: '填表单', color: 'var(--lumi-accent)', action: 'fill' }
]

// --- 状态 ---
const searchInput = ref('')
const selectedEngine = ref(searchEngines[0])
const showEngineDropdown = ref(false)
const isSearching = ref(false)
const isSearchFocused = ref(false)
const searchBoxRef = ref<HTMLElement | null>(null)
const engineBtnRef = ref<HTMLElement | null>(null)
const dropdownPos = ref({ left: 0, top: 0 })
let searchResetTimer: ReturnType<typeof setTimeout> | null = null

// 时钟
const currentTime = ref('')
const currentDate = ref('')
const currentWeek = ref('')
let clockTimer: ReturnType<typeof setInterval> | null = null
const weekDays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 9) return '早上好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

// --- 网站品牌色 ---
const wsColorMap: Record<string, string> = {
  'ws-github': '#24292e',
  'ws-google': '#4285f4',
  'ws-mdn': '#1a1a1a',
  'ws-stack': '#f48024',
  'ws-bing': '#008373',
  'ws-bili': '#fb7299',
  'ws-youtube': '#ff0000',
  'ws-zhihu': '#0084ff'
}

const getWsColor = (className: string): string => wsColorMap[className] ?? 'var(--lumi-brand)'

// --- 事件 ---
const emit = defineEmits<{
  search: [url: string]
  action: [action: string]
}>()

const updateClock = () => {
  const now = new Date()
  currentTime.value = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
  currentDate.value = `${now.getMonth() + 1}月${now.getDate()}日`
  currentWeek.value = weekDays[now.getDay()]
}

const updateDropdownPos = () => {
  if (!engineBtnRef.value) return
  const rect = engineBtnRef.value.getBoundingClientRect()
  dropdownPos.value = {
    left: rect.left,
    top: rect.bottom + 8
  }
}

const dropdownStyle = computed(() => ({
  left: `${dropdownPos.value.left}px`,
  top: `${dropdownPos.value.top}px`
}))

watch(showEngineDropdown, (show) => {
  if (show) {
    nextTick(updateDropdownPos)
    window.addEventListener('resize', updateDropdownPos)
    window.addEventListener('scroll', updateDropdownPos, true)
  } else {
    window.removeEventListener('resize', updateDropdownPos)
    window.removeEventListener('scroll', updateDropdownPos, true)
  }
})

const selectEngine = (engine: SearchEngine) => {
  selectedEngine.value = engine
  showEngineDropdown.value = false
}

const handleSearch = () => {
  const query = searchInput.value.trim()
  if (!query) return
  isSearching.value = true

  if (selectedEngine.value.id === 'ai') {
    emit('action', 'ai-search')
  } else {
    emit('search', selectedEngine.value.url + encodeURIComponent(query))
  }

  if (searchResetTimer) clearTimeout(searchResetTimer)
  searchResetTimer = window.setTimeout(() => {
    isSearching.value = false
    searchInput.value = ''
    searchResetTimer = null
  }, 300)
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSearch()
  }
}

const handleWebsiteClick = (url: string) => emit('search', url)

const handleDocumentClick = (e: MouseEvent) => {
  if (
    showEngineDropdown.value &&
    searchBoxRef.value &&
    !searchBoxRef.value.contains(e.target as Node)
  ) {
    showEngineDropdown.value = false
  }
}

// --- 生命周期 ---
onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
  window.removeEventListener('resize', updateDropdownPos)
  window.removeEventListener('scroll', updateDropdownPos, true)
  if (searchResetTimer) clearTimeout(searchResetTimer)
  if (clockTimer) clearInterval(clockTimer)
})
</script>

<template>
  <div class="home-page">
    <!-- 沉浸式背景 -->
    <div class="home-bg" aria-hidden="true">
      <div class="home-glow home-glow--top" />
      <div class="home-glow home-glow--bottom" />
    </div>

    <!-- 内容滚动区域 -->
    <div class="home-scroll">
      <div class="home-content">
        <!-- ==================== 英雄区域 ==================== -->
        <header class="hero-area home-stagger-enter">
          <h1 class="hero-logo">
            <span class="hero-logo-main">Luomi</span>
            <span class="hero-logo-dim">Nest</span>
          </h1>
          <div class="hero-greeting">
            <span class="hero-greeting-text">{{ greeting }}</span>
            <span class="hero-greeting-dot" />
            <time class="hero-greeting-time">{{ currentTime }}</time>
          </div>
          <p class="hero-date">{{ currentDate }} · {{ currentWeek }}</p>
        </header>

        <!-- ==================== 搜索框 ==================== -->
        <div ref="searchBoxRef" class="search-wrap home-stagger-enter" style="animation-delay: 80ms">
          <div
            class="search-row"
            :class="{ 'search-row--focus': isSearchFocused || showEngineDropdown }"
          >
            <!-- 引擎选择 -->
            <button
              ref="engineBtnRef"
              class="search-engine-btn"
              aria-haspopup="listbox"
              :aria-expanded="showEngineDropdown"
              @click="showEngineDropdown = !showEngineDropdown"
            >
              <component :is="selectedEngine.icon" :size="16" :style="{ color: selectedEngine.color }" />
              <span class="search-engine-name">{{ selectedEngine.name }}</span>
              <ChevronDown :size="13" class="search-engine-arrow" :class="{ 'is-open': showEngineDropdown }" />
            </button>

            <input
              v-model="searchInput"
              :placeholder="selectedEngine.id === 'ai' ? '向 AI 提问...' : `在 ${selectedEngine.name} 中搜索...`"
              class="search-input"
              @focus="isSearchFocused = true"
              @blur="isSearchFocused = false"
              @keydown="handleKeydown"
            />

            <button
              class="search-submit"
              :disabled="!searchInput.trim() || isSearching"
              aria-label="搜索"
              @click="handleSearch"
            >
              <ArrowRight v-if="!isSearching" :size="18" />
              <span v-else class="search-submit-spinner" />
            </button>
          </div>

          <!-- 引擎下拉面板：Teleport 到 body，fixed 定位，避免被父容器裁剪 -->
          <Teleport to="body">
            <Transition name="dropdown">
              <div
                v-if="showEngineDropdown"
                class="engine-dropdown"
                role="listbox"
                :style="dropdownStyle"
              >
                <button
                  v-for="engine in searchEngines"
                  :key="engine.id"
                  class="engine-dropdown-item"
                  :class="{ 'is-active': engine.id === selectedEngine.id }"
                  role="option"
                  :aria-selected="engine.id === selectedEngine.id"
                  @click="selectEngine(engine)"
                >
                  <component :is="engine.icon" :size="15" :style="{ color: engine.color }" />
                  <span>{{ engine.name }}</span>
                </button>
              </div>
            </Transition>
          </Teleport>
        </div>

        <!-- ==================== 常用网站 ==================== -->
        <section class="home-section home-stagger-enter" style="animation-delay: 160ms">
          <header class="section-head">
            <span class="section-marker" />
            <h2 class="section-label">常用网站</h2>
          </header>
          <div class="home-card">
            <div class="tiles-grid tiles-grid--4">
              <button
                v-for="ws in websites"
                :key="ws.name"
                class="home-tile"
                :style="{ '--tile-accent': getWsColor(ws.className) }"
                :title="ws.name"
                @click="handleWebsiteClick(ws.url)"
              >
                <span class="home-tile-icon" :class="ws.className">{{ ws.initial }}</span>
                <span class="home-tile-label">{{ ws.name }}</span>
              </button>
            </div>
          </div>
        </section>

        <!-- ==================== 开发者工具 ==================== -->
        <section class="home-section home-stagger-enter" style="animation-delay: 240ms">
          <header class="section-head">
            <span class="section-marker section-marker--accent" />
            <h2 class="section-label">开发者工具</h2>
          </header>
          <div class="home-card">
            <div class="tiles-grid tiles-grid--5">
              <button
                v-for="action in quickActions"
                :key="action.label"
                class="home-tile"
                :style="{ '--tile-accent': action.color }"
                @click="emit('action', action.action)"
              >
                <span class="home-tile-icon home-tile-icon--gradient" :style="{ '--tile-accent': action.color }">
                  <component :is="action.icon" :size="18" />
                </span>
                <span class="home-tile-label">{{ action.label }}</span>
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 仅保留本组件强相关的局部覆盖，公共样式已全部迁移至 components.css */
</style>
