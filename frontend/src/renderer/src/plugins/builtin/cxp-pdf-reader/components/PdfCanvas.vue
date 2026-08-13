<script setup lang="ts">
/**
 * PdfCanvas — PDF 文档渲染组件。
 *
 * 使用 pdfjs-dist 渲染当前页到 canvas。
 * - 动态 import pdfjs-dist，避免构建时硬依赖
 * - workerSrc 使用 Vite 打包的本地 worker（?url 导入），
 *   规避 CDN 网络不可达与 Electron CSP（worker-src 'self' blob:）拦截导致的
 *   "Setting up fake worker failed" 报错
 * - 仅渲染当前页（简化版，不做虚拟滚动）
 * - 支持搜索高亮（在文本层标记）
 * - 支持键盘翻页（由父组件已绑定全局监听，这里仅处理组件内 wheel 滚动）
 */
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-vue-next'

// 本地 PDF worker：通过 Vite 的 ?url 后缀将 pdf.worker.min.mjs 作为资源打包，
// 与主包同源加载，满足 CSP 且无需外部 CDN。
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

// pdfjs-dist 的类型（动态导入，类型宽松处理）
type PdfDocumentProxy = {
  numPages: number
  getPage: (n: number) => Promise<PdfPageProxy>
  destroy: () => void
}
type PdfPageProxy = {
  pageNumber: number
  getViewport: (opts: { scale: number }) => { width: number; height: number }
  render: (opts: {
    canvasContext: CanvasRenderingContext2D
    viewport: { width: number; height: number }
  }) => { promise: Promise<void> }
  getTextContent: () => Promise<{ items: Array<{ str: string; transform: number[]; width: number; height: number; strEnd?: number }> }>
  cleanup: () => void
}

const props = defineProps<{
  pdfData: Uint8Array
  currentPage: number
  scale: number
  searchQuery: string
  searchMatchIndex: number
}>()

const emit = defineEmits<{
  'page-change': [page: number]
  'scale-change': [scale: number]
  'document-loaded': [totalPages: number]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const textLayerRef = ref<HTMLDivElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)

const pdfDoc = ref<PdfDocumentProxy | null>(null)
const totalPages = ref(0)
const rendering = ref(false)
const loading = ref(true)
const errorMsg = ref<string | null>(null)
const pageTextItems = ref<Array<{ str: string; transform: number[]; width: number; height: number }>>([])

// 用于中断渲染任务的标记
let renderCancelled = false

// ---------------------------------------------------------------------------
// 加载 PDF
// ---------------------------------------------------------------------------

const loadPdf = async () => {
  loading.value = true
  errorMsg.value = null
  try {
    // 动态导入 pdfjs-dist
    const pdfjsLib: typeof import('pdfjs-dist') = await import('pdfjs-dist')

    // 配置 workerSrc（使用 Vite 打包的本地 worker，同源加载，满足 CSP 约束）
    if (!pdfjsLib.GlobalWorkerOptions.workerSrc) {
      pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl
    }

    // 加载文档
    const loadingTask = pdfjsLib.getDocument({
      data: props.pdfData.slice(),
    })
    const doc = (await loadingTask.promise) as unknown as PdfDocumentProxy
    pdfDoc.value = doc
    totalPages.value = doc.numPages
    emit('document-loaded', doc.numPages)
    loading.value = false

    // 渲染当前页
    await renderPage()
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    errorMsg.value = `PDF 加载失败：${msg}`
    loading.value = false
  }
}

// ---------------------------------------------------------------------------
// 渲染当前页
// ---------------------------------------------------------------------------

const renderPage = async () => {
  if (!pdfDoc.value || !canvasRef.value || rendering.value) return
  rendering.value = true
  renderCancelled = false

  try {
    const page = await pdfDoc.value.getPage(props.currentPage)
    const viewport = page.getViewport({ scale: props.scale })

    const canvas = canvasRef.value
    const context = canvas.getContext('2d')
    if (!context) return

    // 高 DPI 渲染
    const outputScale = window.devicePixelRatio || 1
    canvas.width = Math.floor(viewport.width * outputScale)
    canvas.height = Math.floor(viewport.height * outputScale)
    canvas.style.width = `${Math.floor(viewport.width)}px`
    canvas.style.height = `${Math.floor(viewport.height)}px`

    const transform = outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : undefined

    const renderTask = page.render({
      canvasContext: context,
      viewport,
      // @ts-expect-error — transform 字段在 pdfjs-dist 类型中存在但较新版本类型定义有差异
      transform,
    })

    await renderTask.promise

    if (renderCancelled) return

    // 提取文本（用于搜索高亮）
    try {
      const textContent = await page.getTextContent()
      pageTextItems.value = textContent.items.map((it) => ({
        str: it.str,
        transform: it.transform,
        width: it.width,
        height: it.height,
      }))
      renderTextLayer(viewport)
    } catch {
      // 文本提取失败时静默
      pageTextItems.value = []
    }

    page.cleanup()
  } catch (e) {
    if (!renderCancelled) {
      const msg = e instanceof Error ? e.message : String(e)
      errorMsg.value = `页面渲染失败：${msg}`
    }
  } finally {
    rendering.value = false
  }
}

// ---------------------------------------------------------------------------
// 文本层（用于搜索高亮 — 简化实现，仅显示文本并标记匹配项）
// ---------------------------------------------------------------------------

const renderTextLayer = (viewport: { width: number; height: number }) => {
  if (!textLayerRef.value) return
  const layer = textLayerRef.value
  layer.innerHTML = ''
  layer.style.width = `${viewport.width}px`
  layer.style.height = `${viewport.height}px`

  const query = props.searchQuery.trim().toLowerCase()
  let matchCount = 0

  pageTextItems.value.forEach((item) => {
    if (!item.str) return
    const span = document.createElement('span')
    span.textContent = item.str
    span.className = 'pdf-text-item'

    // 通过 transform 将文本放置到对应位置
    // transform: [a, b, c, d, e, f] — 矩阵变换
    // 仅 a/b/e/f 用于本组件的位置与字号计算,c/d 跳过
    const [a, b, , , e, f] = item.transform
    const x = e * props.scale
    const y = viewport.height - f * props.scale
    const fontSize = Math.sqrt(a * a + b * b) * props.scale

    span.style.left = `${x}px`
    span.style.top = `${y - fontSize}px`
    span.style.fontSize = `${fontSize}px`
    span.style.transformOrigin = '0 0'

    // 搜索高亮
    if (query && item.str.toLowerCase().includes(query)) {
      matchCount++
      if (matchCount === props.searchMatchIndex) {
        span.classList.add('pdf-text-match-current')
      } else {
        span.classList.add('pdf-text-match')
      }
    }

    layer.appendChild(span)
  })
}

// ---------------------------------------------------------------------------
// 翻页
// ---------------------------------------------------------------------------

const goToPage = (page: number) => {
  if (page < 1 || page > totalPages.value) return
  emit('page-change', page)
}

const prevPage = () => goToPage(props.currentPage - 1)
const nextPage = () => goToPage(props.currentPage + 1)

// ---------------------------------------------------------------------------
// 监听 props 变化重新渲染
// ---------------------------------------------------------------------------

watch(
  () => props.pdfData,
  async () => {
    if (pdfDoc.value) {
      pdfDoc.value.destroy()
      pdfDoc.value = null
    }
    await loadPdf()
  },
)

watch(
  () => props.currentPage,
  async () => {
    await nextTick()
    await renderPage()
  },
)

watch(
  () => props.scale,
  async () => {
    await nextTick()
    await renderPage()
  },
)

watch(
  () => [props.searchQuery, props.searchMatchIndex],
  async () => {
    if (pdfDoc.value && canvasRef.value) {
      // 仅重新渲染文本层（不必重渲 canvas）
      const page = await pdfDoc.value.getPage(props.currentPage)
      const viewport = page.getViewport({ scale: props.scale })
      renderTextLayer(viewport)
      page.cleanup()
    }
  },
)

// ---------------------------------------------------------------------------
// 滚轮缩放（按住 Ctrl）
// ---------------------------------------------------------------------------

const handleWheel = (e: WheelEvent) => {
  if (!e.ctrlKey && !e.metaKey) return
  e.preventDefault()
  const delta = e.deltaY > 0 ? -0.1 : 0.1
  const newScale = Math.max(0.25, Math.min(4.0, props.scale + delta))
  emit('scale-change', newScale)
}

// ---------------------------------------------------------------------------
// 生命周期
// ---------------------------------------------------------------------------

onMounted(() => {
  void loadPdf()
  containerRef.value?.addEventListener('wheel', handleWheel, { passive: false })
})

onUnmounted(() => {
  renderCancelled = true
  containerRef.value?.removeEventListener('wheel', handleWheel)
  if (pdfDoc.value) {
    pdfDoc.value.destroy()
    pdfDoc.value = null
  }
})
</script>

<template>
  <div ref="containerRef" class="pdf-canvas-container">
    <!-- 加载中 -->
    <div v-if="loading" class="pdf-loading">
      <Loader2 :size="32" class="loading-spin" />
      <p class="loading-text">正在加载 PDF...</p>
    </div>

    <!-- 错误 -->
    <div v-else-if="errorMsg" class="pdf-error">
      <p class="error-text">{{ errorMsg }}</p>
      <button class="retry-btn" @click="loadPdf">重试</button>
    </div>

    <!-- 渲染区域 -->
    <div v-else class="pdf-viewer">
      <div class="pdf-page-wrapper">
        <canvas ref="canvasRef" class="pdf-canvas" />
        <div ref="textLayerRef" class="pdf-text-layer" />
      </div>

      <!-- 浮动翻页按钮 -->
      <button
        class="floating-nav prev"
        :disabled="currentPage <= 1"
        title="上一页"
        @click="prevPage"
      >
        <ChevronLeft :size="20" />
      </button>
      <button
        class="floating-nav next"
        :disabled="currentPage >= totalPages"
        title="下一页"
        @click="nextPage"
      >
        <ChevronRight :size="20" />
      </button>

      <!-- 渲染中指示 -->
      <Transition name="fade">
        <div v-if="rendering" class="rendering-indicator">
          <Loader2 :size="14" class="loading-spin" />
          <span>渲染中</span>
        </div>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.pdf-canvas-container {
  flex: 1;
  position: relative;
  overflow: auto;
  background: var(--bg-secondary);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: var(--space-6);
}

.pdf-loading,
.pdf-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-8);
  color: var(--text-muted);
  margin: auto;
}

.loading-spin {
  animation: cx-pdf-spin 1s linear infinite;
  color: var(--lumi-primary);
}

.loading-text,
.error-text {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.error-text {
  color: var(--lumi-danger);
}

.retry-btn {
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--lumi-primary);
  border-radius: var(--radius-sm);
  background: var(--lumi-primary);
  color: var(--text-inverse);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.retry-btn:hover {
  background: var(--lumi-primary-hover);
}

.pdf-viewer {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  width: 100%;
  min-height: 100%;
}

.pdf-page-wrapper {
  position: relative;
  background: var(--surface);
  box-shadow: var(--shadow-md);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.pdf-canvas {
  display: block;
}

.pdf-text-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 1;
}

.pdf-text-layer :deep(.pdf-text-item) {
  position: absolute;
  color: transparent;
  white-space: pre;
  font-family: var(--font-sans);
  user-select: text;
  pointer-events: auto;
  line-height: 1;
}

.pdf-text-layer :deep(.pdf-text-match) {
  background: var(--lumi-warning-light);
  color: transparent;
  border-radius: 2px;
}

.pdf-text-layer :deep(.pdf-text-match-current) {
  background: var(--lumi-accent-light);
  color: transparent;
  border: 1px solid var(--lumi-accent);
  border-radius: 2px;
}

.floating-nav {
  position: sticky;
  top: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  background: var(--surface);
  color: var(--text-secondary);
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-fast);
  z-index: 2;
}

.floating-nav.prev {
  left: var(--space-3);
  margin-right: auto;
  align-self: center;
  transform: translateY(-50%);
}

.floating-nav.next {
  right: var(--space-3);
  margin-left: auto;
  align-self: center;
  transform: translateY(-50%);
}

.floating-nav:hover:not(:disabled) {
  background: var(--lumi-primary);
  color: var(--text-inverse);
  border-color: var(--lumi-primary);
}

.floating-nav:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.rendering-indicator {
  position: fixed;
  bottom: 60px;
  right: 20px;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  box-shadow: var(--shadow-sm);
  color: var(--text-muted);
  font-size: var(--text-xs);
  z-index: var(--z-sticky);
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
