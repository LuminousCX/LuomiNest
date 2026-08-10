<script setup lang="ts">
/**
 * ReaderToolbar — PDF 阅读器顶部工具栏。
 *
 * 包含：打开文件、标签栏（ReaderTabs）、搜索、AI、笔记、缩放、翻页、设置。
 * 所有状态由父组件管理，本组件只负责触发事件。
 */
import { computed } from 'vue'
import {
  FolderOpen,
  Search,
  Sparkles,
  StickyNote,
  ZoomIn,
  ZoomOut,
  ChevronLeft,
  ChevronRight,
  Settings,
  PanelLeft,
  PanelRight,
  X,
  ChevronDown,
  ChevronUp,
} from 'lucide-vue-next'
import ReaderTabs from './ReaderTabs.vue'
import type { CxPdfFileType } from '../services/pdfApi'

interface CxPdfTab {
  id: string
  fileName: string
  fileId: string
  fileType: CxPdfFileType
  pageCount: number
  loaded: boolean
}

const props = defineProps<{
  hasActivePdf: boolean
  tabs: CxPdfTab[]
  activeTabId: string | null
  sidebarOpen: boolean
  aiPanelOpen: boolean
  searchOpen: boolean
  currentPage: number
  totalPages: number
  scale: number
  searchQuery: string
  currentMatch: number
  totalMatches: number
}>()

const emit = defineEmits<{
  'open-file': []
  'toggle-sidebar': []
  'toggle-ai': []
  'toggle-search': []
  'tab-click': [tabId: string]
  'tab-close': [tabId: string]
  'new-tab': []
  'zoom-change': [scale: number]
  'page-change': [page: number]
  'search-input': [query: string]
  'search-next': []
  'search-prev': []
  'open-settings': []
  'open-notes': []
}>()

// 缩放百分比显示
const scalePercent = computed(() => `${Math.round(props.scale * 100)}%`)

// 处理缩放
const handleZoomIn = () => {
  emit('zoom-change', props.scale + 0.1)
}

const handleZoomOut = () => {
  emit('zoom-change', props.scale - 0.1)
}

// 处理翻页
const handlePrevPage = () => {
  if (props.currentPage > 1) emit('page-change', props.currentPage - 1)
}

const handleNextPage = () => {
  if (props.currentPage < props.totalPages) emit('page-change', props.currentPage + 1)
}

// 搜索输入
const handleSearchInput = (e: Event) => {
  const target = e.target as HTMLInputElement
  emit('search-input', target.value)
}
</script>

<template>
  <div class="reader-toolbar">
    <!-- 第一行：工具按钮 + 标签栏 -->
    <div class="toolbar-row">
      <div class="toolbar-left">
        <button
          class="toolbar-btn"
          :class="{ active: sidebarOpen }"
          :disabled="!hasActivePdf"
          title="切换大纲侧边栏"
          @click="emit('toggle-sidebar')"
        >
          <PanelLeft :size="18" />
        </button>

        <button
          class="toolbar-btn primary"
          title="打开文件 (PDF/Word/TXT)"
          @click="emit('open-file')"
        >
          <FolderOpen :size="18" />
          <span class="btn-label">打开</span>
        </button>

        <div class="toolbar-divider" />

        <button
          class="toolbar-btn"
          :class="{ active: searchOpen }"
          :disabled="!hasActivePdf"
          title="搜索"
          @click="emit('toggle-search')"
        >
          <Search :size="18" />
        </button>

        <button
          class="toolbar-btn"
          :class="{ active: aiPanelOpen }"
          :disabled="!hasActivePdf"
          title="AI 助手"
          @click="emit('toggle-ai')"
        >
          <Sparkles :size="18" />
        </button>

        <button
          class="toolbar-btn"
          :disabled="!hasActivePdf"
          title="笔记"
          @click="emit('open-notes')"
        >
          <StickyNote :size="18" />
        </button>
      </div>

      <!-- 中间：标签栏 -->
      <div class="toolbar-tabs">
        <ReaderTabs
          :tabs="tabs"
          :active-tab-id="activeTabId"
          @tab-click="(id: string) => emit('tab-click', id)"
          @tab-close="(id: string) => emit('tab-close', id)"
          @new-tab="emit('new-tab')"
        />
      </div>

      <div class="toolbar-right">
        <button
          class="toolbar-btn"
          title="设置"
          @click="emit('open-settings')"
        >
          <Settings :size="18" />
        </button>
        <button
          class="toolbar-btn"
          :class="{ active: aiPanelOpen }"
          :disabled="!hasActivePdf"
          title="切换 AI 面板"
          @click="emit('toggle-ai')"
        >
          <PanelRight :size="18" />
        </button>
      </div>
    </div>

    <!-- 第二行：搜索条（条件渲染） -->
    <Transition name="slide-down">
      <div v-if="searchOpen" class="search-bar">
        <Search :size="16" class="search-icon" />
        <input
          type="text"
          class="search-input"
          placeholder="在文档中搜索..."
          :value="searchQuery"
          @input="handleSearchInput"
        />
        <div class="search-info">
          <template v-if="totalMatches > 0">
            {{ currentMatch }} / {{ totalMatches }}
          </template>
          <template v-else-if="searchQuery">
            无匹配
          </template>
        </div>
        <button
          class="toolbar-btn small"
          :disabled="totalMatches === 0"
          title="上一个"
          @click="emit('search-prev')"
        >
          <ChevronUp :size="16" />
        </button>
        <button
          class="toolbar-btn small"
          :disabled="totalMatches === 0"
          title="下一个"
          @click="emit('search-next')"
        >
          <ChevronDown :size="16" />
        </button>
        <button
          class="toolbar-btn small"
          title="关闭搜索"
          @click="emit('toggle-search')"
        >
          <X :size="16" />
        </button>
      </div>
    </Transition>

    <!-- 第三行：翻页 + 缩放（条件渲染） -->
    <Transition name="slide-down">
      <div v-if="hasActivePdf" class="page-bar">
        <div class="page-control">
          <button
            class="toolbar-btn small"
            :disabled="currentPage <= 1"
            title="上一页"
            @click="handlePrevPage"
          >
            <ChevronLeft :size="16" />
          </button>
          <div class="page-info">
            <input
              type="number"
              class="page-input"
              :value="currentPage"
              :min="1"
              :max="totalPages"
              @change="(e) => {
                const v = parseInt((e.target as HTMLInputElement).value, 10)
                if (!isNaN(v)) emit('page-change', v)
              }"
            />
            <span class="page-total">/ {{ totalPages }}</span>
          </div>
          <button
            class="toolbar-btn small"
            :disabled="currentPage >= totalPages"
            title="下一页"
            @click="handleNextPage"
          >
            <ChevronRight :size="16" />
          </button>
        </div>

        <div class="zoom-control">
          <button
            class="toolbar-btn small"
            title="缩小"
            @click="handleZoomOut"
          >
            <ZoomOut :size="16" />
          </button>
          <span class="zoom-label">{{ scalePercent }}</span>
          <button
            class="toolbar-btn small"
            title="放大"
            @click="handleZoomIn"
          >
            <ZoomIn :size="16" />
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.reader-toolbar {
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.toolbar-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  min-height: 44px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-shrink: 0;
}

.toolbar-tabs {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  overflow: hidden;
}

.toolbar-divider {
  width: 1px;
  height: 20px;
  background: var(--border);
  margin: 0 var(--space-1);
}

.toolbar-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  height: 32px;
  min-width: 32px;
  padding: 0 var(--space-2);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.toolbar-btn:hover:not(:disabled) {
  background: var(--surface-hover);
  color: var(--text);
}

.toolbar-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  border-color: var(--lumi-primary-border);
}

.toolbar-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.toolbar-btn.primary {
  background: var(--lumi-primary);
  color: var(--text-inverse);
  border-color: var(--lumi-primary);
}

.toolbar-btn.primary:hover {
  background: var(--lumi-primary-hover);
}

.toolbar-btn.small {
  height: 28px;
  min-width: 28px;
  padding: 0 var(--space-1);
}

.btn-label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

.search-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-secondary);
  border-top: 1px solid var(--border);
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  height: 30px;
  padding: 0 var(--space-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font-size: var(--text-sm);
  outline: none;
  transition: border-color var(--transition-fast);
}

.search-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.search-info {
  font-size: var(--text-xs);
  color: var(--text-muted);
  min-width: 60px;
  text-align: center;
  flex-shrink: 0;
}

.page-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-secondary);
  border-top: 1px solid var(--border);
}

.page-control,
.zoom-control {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.page-info {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--text);
}

.page-input {
  width: 50px;
  height: 28px;
  padding: 0 var(--space-1);
  text-align: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font-size: var(--text-sm);
  outline: none;
  transition: border-color var(--transition-fast);
}

.page-input:focus {
  border-color: var(--lumi-primary);
}

.page-total {
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.zoom-label {
  min-width: 50px;
  text-align: center;
  font-size: var(--text-sm);
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.slide-down-enter-active,
.slide-down-leave-active {
  transition: max-height var(--transition-normal), opacity var(--transition-fast);
  overflow: hidden;
}

.slide-down-enter-from,
.slide-down-leave-to {
  max-height: 0;
  opacity: 0;
}

.slide-down-enter-to,
.slide-down-leave-from {
  max-height: 200px;
  opacity: 1;
}
</style>
