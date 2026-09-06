<script setup lang="ts">
/**
 * PdfReaderView — CxPlugin PDF 智能阅读器主视图。
 *
 * 三栏布局：左侧大纲 / 中间文档渲染 / 右侧 AI 助手。
 * 顶部工具栏 + 多标签栏，底部状态栏。
 * 整个视图作为 DropZone，支持拖拽打开文件。
 *
 * 状态在视图内通过 ref/computed 管理，不创建 store。
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useToast } from '../../../../composables/useToast'
import { generateId } from '../../../../utils/id'
import { cxPdfApi } from '../services/pdfApi'
import type {
  CxPdfFileType,
  CxPdfOutlineItem,
} from '../services/pdfApi'
import ReaderToolbar from '../components/ReaderToolbar.vue'
import ReaderSidebar from '../components/ReaderSidebar.vue'
import PdfCanvas from '../components/PdfCanvas.vue'
import DocxViewer from '../components/DocxViewer.vue'
import TxtViewer from '../components/TxtViewer.vue'
import ReaderAIPanel from '../components/ReaderAIPanel.vue'
import ReaderStatusBar from '../components/ReaderStatusBar.vue'
import DropZone from '../components/DropZone.vue'

// ---------------------------------------------------------------------------
// 类型定义
// ---------------------------------------------------------------------------

interface CxPdfTab {
  id: string
  fileName: string
  fileId: string
  fileType: CxPdfFileType
  pageCount: number
  loaded: boolean
}

interface CxPdfDocStore {
  pdfData?: Uint8Array
  text?: string
  outline: CxPdfOutlineItem[]
  textPreview?: string
}

interface CxHistoryItem {
  fileName: string
  fileType: CxPdfFileType
  openedAt: number
}

// ---------------------------------------------------------------------------
// 常量
// ---------------------------------------------------------------------------

const HISTORY_STORAGE_KEY = 'cx_pdf_reader_history'
const MAX_HISTORY_ITEMS = 10
const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.txt']

// ---------------------------------------------------------------------------
// 状态
// ---------------------------------------------------------------------------

const toast = useToast()

const tabs = ref<CxPdfTab[]>([])
const activeTabId = ref<string | null>(null)
const docStore = ref<Map<string, CxPdfDocStore>>(new Map())

const currentPage = ref(1)
const totalPages = ref(0)
const scale = ref(1.0)

const sidebarOpen = ref(true)
const aiPanelOpen = ref(true)
const searchOpen = ref(false)

const searchQuery = ref('')
const currentMatch = ref(0)
const totalMatches = ref(0)

const history = ref<CxHistoryItem[]>([])
const loading = ref(false)
const isDragOver = ref(false)

const fileInputRef = ref<HTMLInputElement | null>(null)

// ---------------------------------------------------------------------------
// 计算属性
// ---------------------------------------------------------------------------

const activeTab = computed<CxPdfTab | null>(() =>
  tabs.value.find((t) => t.id === activeTabId.value) ?? null,
)

const hasActivePdf = computed(() => activeTab.value !== null)

const activeDoc = computed<CxPdfDocStore | null>(() => {
  if (!activeTab.value) return null
  return docStore.value.get(activeTab.value.fileId) ?? null
})

const activeOutline = computed<CxPdfOutlineItem[]>(() => activeDoc.value?.outline ?? [])
const activePdfData = computed<Uint8Array | undefined>(() => activeDoc.value?.pdfData)
const activeText = computed<string>(() => activeDoc.value?.text ?? '')
const activeFileName = computed<string>(() => activeTab.value?.fileName ?? '')
const activeFileType = computed<CxPdfFileType>(() => activeTab.value?.fileType ?? 'unknown')

// ---------------------------------------------------------------------------
// 历史（localStorage 持久化）
// ---------------------------------------------------------------------------

const loadHistory = () => {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY)
    if (!raw) return
    const arr = JSON.parse(raw)
    if (Array.isArray(arr)) {
      history.value = arr.slice(0, MAX_HISTORY_ITEMS)
    }
  } catch {
    // ignore parse errors
  }
}

const persistHistory = () => {
  try {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history.value))
  } catch {
    // ignore quota errors
  }
}

const addHistory = (fileName: string, fileType: CxPdfFileType) => {
  const item: CxHistoryItem = { fileName, fileType, openedAt: Date.now() }
  // 去重：相同文件名先移除
  history.value = history.value.filter((h) => h.fileName !== fileName)
  history.value.unshift(item)
  history.value = history.value.slice(0, MAX_HISTORY_ITEMS)
  persistHistory()
}

const clearHistory = () => {
  history.value = []
  persistHistory()
  toast.info('已清空最近打开记录')
}

// ---------------------------------------------------------------------------
// 文件类型推断
// ---------------------------------------------------------------------------

const detectFileType = (fileName: string): CxPdfFileType => {
  const lower = fileName.toLowerCase()
  if (lower.endsWith('.pdf')) return 'pdf'
  if (lower.endsWith('.docx')) return 'docx'
  if (lower.endsWith('.txt')) return 'txt'
  return 'unknown'
}

const isAcceptedFile = (file: File): boolean => {
  return ACCEPTED_EXTENSIONS.some((ext) => file.name.toLowerCase().endsWith(ext))
}

// ---------------------------------------------------------------------------
// 打开文件
// ---------------------------------------------------------------------------

const openFile = async (file: File) => {
  if (!isAcceptedFile(file)) {
    toast.error(`不支持的文件类型：${file.name}（仅支持 PDF/Word/TXT）`)
    return
  }

  loading.value = true
  try {
    // 1. 读取文件二进制（PDF 需要本地数据用于 canvas 渲染）
    const fileBuffer = await file.arrayBuffer()
    const fileBytes = new Uint8Array(fileBuffer)

    // 2. 调用后端提取文本与大纲
    const extractResult = await cxPdfApi.extractDocument(file)

    // 3. 创建标签
    const tabId = generateId('tab')
    const tab: CxPdfTab = {
      id: tabId,
      fileName: extractResult.fileName || file.name,
      fileId: extractResult.fileId,
      fileType: extractResult.fileType || detectFileType(file.name),
      pageCount: extractResult.pageCount || 0,
      loaded: true,
    }

    // 4. 存储文档数据
    const store: CxPdfDocStore = {
      outline: extractResult.outline ?? [],
      textPreview: extractResult.textPreview ?? '',
    }
    if (tab.fileType === 'pdf') {
      store.pdfData = fileBytes
    } else {
      // Word/TXT：textPreview 仅有 500 字预览，通过 getPageText 逐页拉取完整正文
      const pageCount = extractResult.pageCount || 0
      if (pageCount > 0 && extractResult.fileId) {
        const pageTexts = await Promise.all(
          Array.from({ length: pageCount }, (_, i) =>
            cxPdfApi.getPageText(extractResult.fileId, i + 1).then((p) => p.text || ''),
          ),
        )
        store.text = pageTexts.join('\n\n')
      } else {
        store.text = extractResult.textPreview ?? ''
      }
    }

    tabs.value.push(tab)
    docStore.value.set(tab.fileId, store)

    // 5. 切换到新标签
    activeTabId.value = tab.id
    currentPage.value = 1
    totalPages.value = tab.pageCount
    scale.value = 1.0

    // 6. 记录历史
    addHistory(tab.fileName, tab.fileType)

    toast.success(`已打开：${tab.fileName}`)
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    toast.error(`打开文件失败：${msg}`)
  } finally {
    loading.value = false
  }
}

const handleOpenFileClick = () => {
  fileInputRef.value?.click()
}

const handleFileInputChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return
  const file = target.files[0]
  void openFile(file)
  // 重置 input 以便可以重复选择同一文件
  target.value = ''
}

const handleReopenFromHistory = (item: CxHistoryItem) => {
  // 历史记录仅保存文件名，无法重新打开原文件 — 提示用户重新选择
  toast.info(`请重新选择文件：${item.fileName}`)
  fileInputRef.value?.click()
}

// ---------------------------------------------------------------------------
// 拖拽
// ---------------------------------------------------------------------------

const handleDragOver = (e: DragEvent) => {
  e.preventDefault()
  isDragOver.value = true
}

const handleDragLeave = (e: DragEvent) => {
  e.preventDefault()
  // 仅在离开容器时才隐藏 overlay
  if (e.currentTarget === e.target) {
    isDragOver.value = false
  }
}

const handleDrop = (e: DragEvent) => {
  e.preventDefault()
  isDragOver.value = false
  const files = e.dataTransfer?.files
  if (!files || files.length === 0) return
  void openFile(files[0])
}

// ---------------------------------------------------------------------------
// 标签操作
// ---------------------------------------------------------------------------

const handleTabClick = (tabId: string) => {
  const tab = tabs.value.find((t) => t.id === tabId)
  if (!tab) return
  activeTabId.value = tabId
  currentPage.value = 1
  totalPages.value = tab.pageCount
}

const handleTabClose = (tabId: string) => {
  const idx = tabs.value.findIndex((t) => t.id === tabId)
  if (idx === -1) return
  const tab = tabs.value[idx]
  // 清理文档数据
  docStore.value.delete(tab.fileId)
  tabs.value.splice(idx, 1)
  // 如果关闭的是当前激活的标签，切到下一个或上一个
  if (activeTabId.value === tabId) {
    const next = tabs.value[idx] ?? tabs.value[idx - 1] ?? null
    if (next) {
      activeTabId.value = next.id
      currentPage.value = 1
      totalPages.value = next.pageCount
    } else {
      activeTabId.value = null
      totalPages.value = 0
    }
  }
}

const handleNewTab = () => {
  fileInputRef.value?.click()
}

// ---------------------------------------------------------------------------
// 工具栏事件
// ---------------------------------------------------------------------------

const handleToggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value
}

const handleToggleAi = () => {
  aiPanelOpen.value = !aiPanelOpen.value
}

const handleToggleSearch = () => {
  searchOpen.value = !searchOpen.value
  if (!searchOpen.value) {
    searchQuery.value = ''
    totalMatches.value = 0
    currentMatch.value = 0
  }
}

const handleZoomChange = (newScale: number) => {
  scale.value = Math.max(0.25, Math.min(4.0, newScale))
}

const handlePageChange = (page: number) => {
  if (page < 1 || page > totalPages.value) return
  currentPage.value = page
}

// ---------------------------------------------------------------------------
// 大纲导航
// ---------------------------------------------------------------------------

const handleOutlinePageChange = (page: number) => {
  handlePageChange(page)
}

// ---------------------------------------------------------------------------
// 搜索
// ---------------------------------------------------------------------------

const handleSearchInput = async (query: string) => {
  searchQuery.value = query
  if (!query.trim() || !activeTab.value) {
    totalMatches.value = 0
    currentMatch.value = 0
    return
  }
  try {
    const result = await cxPdfApi.searchInDocument(activeTab.value.fileId, query)
    totalMatches.value = result.total
    currentMatch.value = result.total > 0 ? 1 : 0
  } catch {
    // 搜索失败时静默（不弹 toast 干扰用户）
    totalMatches.value = 0
    currentMatch.value = 0
  }
}

const handleSearchNext = () => {
  if (totalMatches.value === 0) return
  currentMatch.value = (currentMatch.value % totalMatches.value) + 1
}

const handleSearchPrev = () => {
  if (totalMatches.value === 0) return
  currentMatch.value = currentMatch.value === 1 ? totalMatches.value : currentMatch.value - 1
}

// ---------------------------------------------------------------------------
// PDF Canvas 事件
// ---------------------------------------------------------------------------

const handlePdfDocumentLoaded = (pages: number) => {
  totalPages.value = pages
  if (activeTab.value) {
    activeTab.value.pageCount = pages
  }
}

const handlePdfPageChange = (page: number) => {
  currentPage.value = page
}

const handlePdfScaleChange = (newScale: number) => {
  scale.value = newScale
}

// ---------------------------------------------------------------------------
// 键盘快捷键
// ---------------------------------------------------------------------------

const handleKeydown = (e: KeyboardEvent) => {
  // 仅在有活动文档时响应翻页快捷键
  if (!hasActivePdf.value) return
  // 当焦点在输入框时不响应
  const target = e.target as HTMLElement
  if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
    return
  }
  if (e.key === 'ArrowRight' || e.key === 'PageDown') {
    e.preventDefault()
    handlePageChange(currentPage.value + 1)
  } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
    e.preventDefault()
    handlePageChange(currentPage.value - 1)
  } else if (e.key === 'Home') {
    e.preventDefault()
    handlePageChange(1)
  } else if (e.key === 'End') {
    e.preventDefault()
    handlePageChange(totalPages.value)
  }
}

// ---------------------------------------------------------------------------
// 生命周期
// ---------------------------------------------------------------------------

onMounted(() => {
  loadHistory()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

// 监听激活标签变化，重置搜索
watch(activeTabId, () => {
  searchQuery.value = ''
  totalMatches.value = 0
  currentMatch.value = 0
})
</script>

<template>
  <div
    class="cx-pdf-reader-view"
    :class="{ 'is-drag-over': isDragOver }"
    @dragover="handleDragOver"
    @dragleave="handleDragLeave"
    @drop="handleDrop"
  >
    <!-- 隐藏的文件输入 -->
    <input
      ref="fileInputRef"
      type="file"
      accept=".pdf,.docx,.txt"
      style="display: none"
      @change="handleFileInputChange"
    />

    <!-- 顶部工具栏 + 标签栏 -->
    <ReaderToolbar
      :has-active-pdf="hasActivePdf"
      :tabs="tabs"
      :active-tab-id="activeTabId"
      :sidebar-open="sidebarOpen"
      :ai-panel-open="aiPanelOpen"
      :search-open="searchOpen"
      :current-page="currentPage"
      :total-pages="totalPages"
      :scale="scale"
      :search-query="searchQuery"
      :current-match="currentMatch"
      :total-matches="totalMatches"
      @open-file="handleOpenFileClick"
      @toggle-sidebar="handleToggleSidebar"
      @toggle-ai="handleToggleAi"
      @toggle-search="handleToggleSearch"
      @zoom-change="handleZoomChange"
      @page-change="handlePageChange"
      @search-input="handleSearchInput"
      @search-next="handleSearchNext"
      @search-prev="handleSearchPrev"
      @tab-click="handleTabClick"
      @tab-close="handleTabClose"
      @new-tab="handleNewTab"
    />

    <!-- 主体区域 -->
    <div class="reader-body">
      <!-- 左侧大纲侧边栏 -->
      <ReaderSidebar
        :outline="activeOutline"
        :current-page="currentPage"
        :is-open="sidebarOpen && hasActivePdf"
        @page-change="handleOutlinePageChange"
        @toggle="handleToggleSidebar"
      />

      <!-- 中间文档查看区 -->
      <div class="reader-content">
        <!-- 空状态 / DropZone -->
        <DropZone
          v-if="!hasActivePdf"
          :history="history"
          @file-loaded="openFile"
          @clear-history="clearHistory"
          @reopen-item="handleReopenFromHistory"
          @click-select="handleOpenFileClick"
        />

        <!-- 加载中 -->
        <div v-else-if="loading" class="reader-loading">
          <div class="loading-spinner" />
          <p class="loading-text">正在提取文档内容...</p>
        </div>

        <!-- PDF 渲染 -->
        <PdfCanvas
          v-else-if="activeFileType === 'pdf' && activePdfData"
          :pdf-data="activePdfData"
          :current-page="currentPage"
          :scale="scale"
          :search-query="searchQuery"
          :search-match-index="currentMatch"
          @page-change="handlePdfPageChange"
          @scale-change="handlePdfScaleChange"
          @document-loaded="handlePdfDocumentLoaded"
        />

        <!-- Word 渲染 -->
        <DocxViewer
          v-else-if="activeFileType === 'docx'"
          :text="activeText"
          :outline="activeOutline"
        />

        <!-- TXT 渲染 -->
        <TxtViewer
          v-else-if="activeFileType === 'txt'"
          :text="activeText"
        />

        <!-- 未知类型 -->
        <div v-else class="reader-unsupported">
          <p>暂不支持此文件类型的可视化预览</p>
        </div>
      </div>

      <!-- 右侧 AI 面板 -->
      <ReaderAIPanel
        :file-id="activeTab?.fileId ?? ''"
        :is-open="aiPanelOpen && hasActivePdf"
        :current-page="currentPage"
        @toggle="handleToggleAi"
      />
    </div>

    <!-- 底部状态栏 -->
    <ReaderStatusBar
      :current-page="currentPage"
      :total-pages="totalPages"
      :file-name="activeFileName"
      :scale="scale"
      :file-type="activeFileType"
    />

    <!-- 拖拽 overlay -->
    <Transition name="fade">
      <div v-if="isDragOver" class="drag-overlay">
        <div class="drag-overlay-inner">
          <div class="drag-overlay-icon">
            <svg viewBox="0 0 24 24" width="64" height="64" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 3v4a1 1 0 0 0 1 1h4" />
              <path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z" />
              <path d="M12 11v6M9 14l3 3 3-3" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </div>
          <p class="drag-overlay-text">松开以打开文档</p>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.cx-pdf-reader-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  position: relative;
  overflow: hidden;
}

.reader-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.reader-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  overflow: hidden;
}

.reader-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  color: var(--text-muted);
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border);
  border-top-color: var(--lumi-primary);
  border-radius: 50%;
  animation: cx-pdf-spin 0.8s linear infinite;
}

.loading-text {
  font-size: var(--text-base);
  color: var(--text-muted);
}

.reader-unsupported {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: var(--text-base);
}

.drag-overlay {
  position: absolute;
  inset: 0;
  background: var(--lumi-primary-light);
  border: 2px dashed var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-overlay);
  pointer-events: none;
  transition: opacity var(--transition-fast);
}

.drag-overlay-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-4);
  color: var(--lumi-primary);
}

.drag-overlay-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.drag-overlay-text {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--transition-fast);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@keyframes cx-pdf-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
