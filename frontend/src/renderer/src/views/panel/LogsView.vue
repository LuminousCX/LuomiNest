<script setup lang="ts">
/**
 * 统一日志页（/panel/logs）
 *
 * 数据源为主进程 log-hub 内存环形缓冲（1000 条，log:query 分页 + log:onAppended 实时尾随）。
 * 来源筛选（前端/主进程/后端/平台）+ 级别筛选 + 搜索 + 级别着色；支持清空、导出、
 * 上传（诊断日志手动上传，需辰汐通行证登录态）、打开日志目录、日志分割文件列表抽屉。
 * 分页渲染（每页 200 条）避免 1000 条裸渲染卡顿；尾随模式固定展示最新一页。
 */
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Search, Trash2, Download, Upload, FolderOpen, Files, X,
  ChevronLeft, ChevronRight, Pause, Play, ArrowDownToLine,
} from 'lucide-vue-next'
import type {
  CloudAuthStatus,
  LogEntry,
  LogQueryParams,
  LogSegmentInfo,
  LogSource,
  LogLevel,
  LogUploadResult,
} from '@shared/ipc-types'

const { t } = useI18n()

type SourceFilter = LogSource | 'all'
type LevelFilter = LogLevel | 'all'

const PAGE_SIZE = 200
const SEARCH_DEBOUNCE_MS = 300
const BOTTOM_EPSILON = 32

const sourceFilter = ref<SourceFilter>('all')
const levelFilter = ref<LevelFilter>('all')
const searchInput = ref('')
const search = ref('')
const follow = ref(true)

const entries = ref<LogEntry[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const listRef = ref<HTMLElement | null>(null)

const showSegments = ref(false)
const segments = ref<LogSegmentInfo[]>([])
const isLoadingSegments = ref(false)

/** 上传资格：辰汐通行证登录态（cloud:status 推送驱动，登录/登出即时更新按钮态） */
const isCloudLoggedIn = ref(false)
const isUploading = ref(false)
const statusMessage = ref('')
const statusIsError = ref(false)
let statusTimer: ReturnType<typeof setTimeout> | null = null

const sourceOptions: Array<{ value: SourceFilter; labelKey: string }> = [
  { value: 'all', labelKey: 'log.source.all' },
  { value: 'renderer', labelKey: 'log.source.renderer' },
  { value: 'main', labelKey: 'log.source.main' },
  { value: 'backend', labelKey: 'log.source.backend' },
  { value: 'platform', labelKey: 'log.source.platform' },
]

const levelOptions: Array<{ value: LevelFilter; labelKey: string }> = [
  { value: 'all', labelKey: 'log.level.all' },
  { value: 'debug', labelKey: 'log.level.debug' },
  { value: 'info', labelKey: 'log.level.info' },
  { value: 'warn', labelKey: 'log.level.warn' },
  { value: 'error', labelKey: 'log.level.error' },
]

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const isLastPage = computed(() => page.value >= totalPages.value)
const rangeLabel = computed(() => {
  if (total.value === 0) return ''
  const start = (page.value - 1) * PAGE_SIZE + 1
  const end = Math.min(page.value * PAGE_SIZE, total.value)
  return `${start}-${end}`
})

const buildQueryParams = (offset: number): LogQueryParams => ({
  source: sourceFilter.value,
  level: levelFilter.value,
  search: search.value || undefined,
  offset,
  limit: PAGE_SIZE,
})

const load = async (): Promise<void> => {
  if (!window.api?.log) return
  loading.value = true
  try {
    if (follow.value) {
      // 尾随模式：先取过滤后的总数，定位到最新一页
      const head = await window.api.log.query(buildQueryParams(0))
      total.value = head.total
      page.value = Math.max(1, Math.ceil(head.total / PAGE_SIZE))
    }
    const res = await window.api.log.query(buildQueryParams((page.value - 1) * PAGE_SIZE))
    total.value = res.total
    entries.value = res.entries
    await nextTick()
    scrollToBottom()
  } catch {
    // hub 未就绪时静默，保留上次数据
  } finally {
    loading.value = false
  }
}

const scrollToBottom = (): void => {
  const el = listRef.value
  if (el) el.scrollTop = el.scrollHeight
}

const onScroll = (): void => {
  const el = listRef.value
  if (!el) return
  const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - BOTTOM_EPSILON
  // 仅在最新一页时允许"滚到底恢复尾随"，避免翻看旧页时误触发跳转
  if (atBottom && isLastPage.value && !follow.value) {
    follow.value = true
  } else if (!atBottom && follow.value) {
    follow.value = false
  }
}

const toggleFollow = (): void => {
  follow.value = !follow.value
  if (follow.value) void load()
}

const setPage = (next: number): void => {
  const clamped = Math.min(totalPages.value, Math.max(1, next))
  if (clamped === page.value) return
  // 翻看历史页时自动暂停尾随（跳到最新页除外）
  if (follow.value && clamped !== totalPages.value) follow.value = false
  page.value = clamped
  void load()
}

const jumpToLatest = (): void => {
  page.value = totalPages.value
  follow.value = true
  void load()
}

/* ── 筛选变更 ───────────────────────────────────────────────────────────── */

let searchDebounce: ReturnType<typeof setTimeout> | null = null

const onSearchInput = (): void => {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => {
    search.value = searchInput.value.trim()
    page.value = 1
    void load()
  }, SEARCH_DEBOUNCE_MS)
}

const onFilterChange = (): void => {
  page.value = 1
  void load()
}

/* ── 操作 ───────────────────────────────────────────────────────────────── */

const showStatus = (message: string, isError = false): void => {
  statusMessage.value = message
  statusIsError.value = isError
  if (statusTimer) clearTimeout(statusTimer)
  statusTimer = setTimeout(() => {
    statusMessage.value = ''
  }, 5000)
}

const handleClear = async (): Promise<void> => {
  try {
    await window.api?.log?.clear()
    page.value = 1
    await load()
    showStatus(t('log.cleared'))
  } catch {
    showStatus(t('log.error'), true)
  }
}

const handleExport = async (): Promise<void> => {
  try {
    const filePath = await window.api?.log?.exportLogs()
    if (filePath) {
      showStatus(t('log.exportedTo', { path: filePath }))
    } else {
      showStatus(t('log.error'), true)
    }
  } catch {
    showStatus(t('log.error'), true)
  }
}

const handleUpload = async (): Promise<void> => {
  if (!isCloudLoggedIn.value || isUploading.value) return
  isUploading.value = true
  try {
    const result: LogUploadResult = await window.api.log.upload()
    if (result.ok) {
      // 成功 toast 携带服务端返回的报表 ID，便于用户反馈问题时定位日志
      showStatus(
        result.reportId ? t('log.uploadOkReport', { id: result.reportId }) : t('log.uploadOkNoStatus')
      )
    } else if (result.reason === 'not_logged_in') {
      isCloudLoggedIn.value = false
      showStatus(t('log.uploadNotLoggedIn'), true)
    } else if (result.reason === 'unauthorized') {
      showStatus(t('log.uploadUnauthorized'), true)
    } else if (result.reason === 'rate_limited') {
      showStatus(t('log.uploadRateLimited'), true)
    } else if (result.reason === 'too_large') {
      showStatus(t('log.uploadTooLarge'), true)
    } else if (result.reason === 'network') {
      showStatus(t('log.uploadNetwork'), true)
    } else {
      showStatus(t('log.uploadFailed', { reason: result.status ? `HTTP ${result.status}` : 'server' }), true)
    }
  } catch {
    showStatus(t('log.error'), true)
  } finally {
    isUploading.value = false
  }
}

const handleOpenDir = async (): Promise<void> => {
  try {
    await window.api?.log?.openDir()
  } catch {
    // 打开目录失败静默（用户可见的场景极少）
  }
}

const loadSegments = async (): Promise<void> => {
  isLoadingSegments.value = true
  try {
    segments.value = (await window.api?.log?.getSegments()) ?? []
  } catch {
    segments.value = []
  } finally {
    isLoadingSegments.value = false
  }
}

const toggleSegments = async (): Promise<void> => {
  showSegments.value = !showSegments.value
  if (showSegments.value) await loadSegments()
}

const openSegmentFolder = async (): Promise<void> => {
  await handleOpenDir()
}

/* ── 展示辅助 ───────────────────────────────────────────────────────────── */

const formatTime = (ts: string): string => {
  const date = new Date(ts)
  if (Number.isNaN(date.getTime())) return ts
  const pad = (n: number, len = 2): string => String(n).padStart(len, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

const formatFullTime = (ts: string): string => ts.replace('T', ' ').replace('Z', '')

const formatSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

const formatSegmentTime = (mtimeMs: number): string => {
  const date = new Date(mtimeMs)
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const levelClass = (level: LogLevel): string => `level-${level}`

const formatData = (entry: LogEntry): string => {
  if (entry.data === undefined || entry.data === null) return ''
  try {
    const text = typeof entry.data === 'string' ? entry.data : JSON.stringify(entry.data)
    return text.length > 300 ? `${text.slice(0, 300)}…` : text
  } catch {
    return ''
  }
}

/* ── 实时尾随订阅 ───────────────────────────────────────────────────────── */

let unsubscribe: (() => void) | null = null
let unsubscribeCloudStatus: (() => void) | null = null

onMounted(async () => {
  await load()
  unsubscribe = window.api?.log?.onAppended(() => {
    if (follow.value) {
      void load()
    } else {
      // 非尾随时不打断浏览，仅刷新总数角标
      window.api?.log
        ?.query(buildQueryParams(0))
        .then((head) => {
          total.value = head.total
        })
        .catch(() => {})
    }
  }) ?? null
  // 上传资格：取一次当前登录态 + 订阅状态推送（页内登录/登出/续期失败即时反映到按钮态）
  try {
    const status: CloudAuthStatus | undefined = await window.api?.cloud?.status()
    isCloudLoggedIn.value = status?.state === 'authorized'
  } catch {
    isCloudLoggedIn.value = false
  }
  unsubscribeCloudStatus = window.api?.cloud?.onStatus?.((status) => {
    isCloudLoggedIn.value = status.state === 'authorized'
  }) ?? null
})

onBeforeUnmount(() => {
  unsubscribe?.()
  unsubscribeCloudStatus?.()
  if (searchDebounce) clearTimeout(searchDebounce)
  if (statusTimer) clearTimeout(statusTimer)
})
</script>

<template>
  <div class="logs-view">
    <div class="page-header">
      <div class="header-text">
        <h1 class="page-title">{{ t('log.title') }}</h1>
        <p class="page-desc">{{ t('log.desc') }}</p>
      </div>
      <div class="header-actions">
        <button class="action-btn" :title="t('log.follow')" @click="toggleFollow">
          <Pause v-if="follow" :size="15" />
          <Play v-else :size="15" />
          <span>{{ follow ? t('log.following') : t('log.paused') }}</span>
        </button>
        <button class="action-btn" :title="t('log.segments')" @click="toggleSegments">
          <Files :size="15" />
          <span>{{ t('log.segments') }}</span>
        </button>
        <button class="action-btn" :title="t('log.openDir')" @click="handleOpenDir">
          <FolderOpen :size="15" />
          <span>{{ t('log.openDir') }}</span>
        </button>
        <button
          class="action-btn"
          :disabled="!isCloudLoggedIn || isUploading"
          :title="isCloudLoggedIn ? t('log.upload') : t('log.uploadNeedLoginHint')"
          @click="handleUpload"
        >
          <Upload :size="15" />
          <span>{{ isUploading ? t('log.uploading') : t('log.upload') }}</span>
        </button>
        <button class="action-btn" :title="t('log.export')" @click="handleExport">
          <Download :size="15" />
          <span>{{ t('log.export') }}</span>
        </button>
        <button class="action-btn danger" :title="t('log.clear')" @click="handleClear">
          <Trash2 :size="15" />
          <span>{{ t('log.clear') }}</span>
        </button>
      </div>
    </div>

    <div class="toolbar">
      <div class="source-tabs">
        <button
          v-for="opt in sourceOptions"
          :key="opt.value"
          :class="['source-tab', { active: sourceFilter === opt.value }]"
          @click="sourceFilter = opt.value; onFilterChange()"
        >
          {{ t(opt.labelKey) }}
        </button>
      </div>
      <select v-model="levelFilter" class="level-select" @change="onFilterChange">
        <option v-for="opt in levelOptions" :key="opt.value" :value="opt.value">
          {{ t(opt.labelKey) }}
        </option>
      </select>
      <div class="search-box">
        <Search :size="14" class="search-icon" />
        <input
          v-model="searchInput"
          type="text"
          class="search-input"
          :placeholder="t('log.searchPlaceholder')"
          @input="onSearchInput"
        />
      </div>
    </div>

    <div ref="listRef" class="log-list" @scroll="onScroll">
      <div v-if="entries.length === 0 && !loading" class="log-empty">
        {{ t('log.empty') }}
      </div>
      <div
        v-for="entry in entries"
        :key="entry.seq"
        :class="['log-row', levelClass(entry.level)]"
        :title="formatFullTime(entry.ts)"
      >
        <span class="log-time">{{ formatTime(entry.ts) }}</span>
        <span class="log-source" :class="`src-${entry.source}`">{{ t(`log.source.${entry.source}`) }}</span>
        <span class="log-level" :class="levelClass(entry.level)">{{ entry.level.toUpperCase() }}</span>
        <span class="log-scope">[{{ entry.scope }}]</span>
        <span class="log-message">{{ entry.message }}<template v-if="formatData(entry)"> <span class="log-data">{{ formatData(entry) }}</span></template></span>
      </div>
    </div>

    <div class="list-footer">
      <span class="count-label">
        {{ t('log.count', { n: total }) }}<template v-if="rangeLabel"> · {{ rangeLabel }}</template>
      </span>
      <span v-if="statusMessage" :class="['status-label', { error: statusIsError }]">{{ statusMessage }}</span>
      <div class="pagination">
        <button
          v-if="!follow && !isLastPage"
          class="jump-latest"
          :title="t('log.follow')"
          @click="jumpToLatest"
        >
          <ArrowDownToLine :size="13" />
          <span>{{ t('log.jumpLatest') }}</span>
        </button>
        <button class="page-btn" :disabled="page <= 1" @click="setPage(page - 1)">
          <ChevronLeft :size="14" />
        </button>
        <span class="page-label">{{ t('log.page', { current: page, total: totalPages }) }}</span>
        <button class="page-btn" :disabled="page >= totalPages" @click="setPage(page + 1)">
          <ChevronRight :size="14" />
        </button>
      </div>
    </div>

    <Transition name="drawer">
      <div v-if="showSegments" class="segments-drawer">
        <div class="drawer-header">
          <span class="drawer-title">{{ t('log.segments') }}</span>
          <button class="drawer-close" :title="t('log.close')" @click="showSegments = false">
            <X :size="15" />
          </button>
        </div>
        <div class="drawer-body">
          <div v-if="segments.length === 0 && !isLoadingSegments" class="drawer-empty">
            {{ t('log.segmentsEmpty') }}
          </div>
          <div v-for="seg in segments" :key="seg.name" class="segment-row">
            <div class="segment-info">
              <span class="segment-name">{{ seg.name }}</span>
              <span class="segment-meta">{{ formatSize(seg.size) }} · {{ formatSegmentTime(seg.mtimeMs) }}</span>
            </div>
            <button class="segment-open" :title="t('log.openFolder')" @click="openSegmentFolder">
              <FolderOpen :size="14" />
              <span>{{ t('log.openFolder') }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.logs-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--space-4, 16px);
  gap: var(--space-3, 12px);
  position: relative;
  overflow: hidden;
  color: var(--text-primary, inherit);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3, 12px);
  flex-shrink: 0;
}

.page-title {
  margin: 0;
  font-size: var(--text-xl, 20px);
  font-weight: var(--font-bold, 700);
}

.page-desc {
  margin: var(--space-1, 4px) 0 0;
  font-size: var(--text-sm, 13px);
  color: var(--text-secondary, inherit);
  opacity: 0.8;
}

.header-actions {
  display: flex;
  gap: var(--space-2, 8px);
  flex-wrap: wrap;
  justify-content: flex-end;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1, 4px);
  padding: var(--space-1, 4px) var(--space-2, 8px);
  border: 1px solid var(--border-light, rgba(128, 128, 128, 0.25));
  background: var(--surface-hover, transparent);
  border-radius: var(--radius-md, 8px);
  color: var(--text-secondary, inherit);
  font-size: var(--text-xs, 12px);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.action-btn:hover:not(:disabled) {
  background: var(--surface-active, rgba(128, 128, 128, 0.15));
  color: var(--text-primary, inherit);
}

.action-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.action-btn.danger:hover:not(:disabled) {
  color: var(--lumi-danger, #e5484d);
  border-color: var(--lumi-danger, #e5484d);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-2, 8px);
  flex-wrap: wrap;
  flex-shrink: 0;
}

.source-tabs {
  display: inline-flex;
  border: 1px solid var(--border-light, rgba(128, 128, 128, 0.25));
  border-radius: var(--radius-md, 8px);
  overflow: hidden;
}

.source-tab {
  padding: var(--space-1, 4px) var(--space-3, 12px);
  border: none;
  background: transparent;
  color: var(--text-secondary, inherit);
  font-size: var(--text-xs, 12px);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.source-tab:hover {
  background: var(--surface-hover, rgba(128, 128, 128, 0.1));
}

.source-tab.active {
  background: var(--nav-item-active-bg, var(--lumi-brand, #6c5ce7));
  color: var(--nav-item-active-color, var(--text-primary, #fff));
  font-weight: var(--font-semibold, 600);
}

.level-select {
  height: 28px;
  border: 1px solid var(--border-light, rgba(128, 128, 128, 0.25));
  border-radius: var(--radius-md, 8px);
  background: var(--surface, transparent);
  color: var(--text-primary, inherit);
  font-size: var(--text-xs, 12px);
  padding: 0 var(--space-2, 8px);
  cursor: pointer;
}

.search-box {
  position: relative;
  flex: 1;
  min-width: 160px;
  max-width: 320px;
}

.search-icon {
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted, inherit);
  opacity: 0.7;
  pointer-events: none;
}

.search-input {
  width: 100%;
  height: 28px;
  border: 1px solid var(--border-light, rgba(128, 128, 128, 0.25));
  border-radius: var(--radius-md, 8px);
  background: var(--surface, transparent);
  color: var(--text-primary, inherit);
  font-size: var(--text-xs, 12px);
  padding: 0 var(--space-2, 8px) 0 28px;
  outline: none;
}

.search-input:focus {
  border-color: var(--lumi-brand, #6c5ce7);
}

.log-list {
  flex: 1;
  overflow-y: auto;
  border: 1px solid var(--border-light, rgba(128, 128, 128, 0.2));
  border-radius: var(--radius-lg, 10px);
  background: var(--surface, transparent);
  font-family: 'JetBrains Mono', 'Cascadia Mono', Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
}

.log-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted, inherit);
  opacity: 0.7;
}

.log-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-2, 8px);
  padding: 1px var(--space-2, 8px);
  white-space: pre-wrap;
  word-break: break-all;
}

.log-row:hover {
  background: var(--surface-hover, rgba(128, 128, 128, 0.08));
}

.log-time {
  color: var(--text-muted, #888);
  flex-shrink: 0;
}

.log-source {
  flex-shrink: 0;
  min-width: 40px;
  text-align: center;
  font-size: 10px;
  padding: 0 4px;
  border-radius: var(--radius-full, 999px);
  border: 1px solid currentColor;
  opacity: 0.85;
}

.src-renderer { color: #4a9eff; }
.src-main { color: #9d7bff; }
.src-backend { color: #2fbf71; }
.src-platform { color: #e6a23c; }

.log-level {
  flex-shrink: 0;
  min-width: 42px;
  font-weight: 600;
}

.level-debug .log-level { color: #8a8f98; }
.level-info .log-level { color: var(--lumi-brand, #4a9eff); }
.level-warn .log-level { color: var(--lumi-accent, #e6a23c); }
.level-error .log-level { color: var(--lumi-danger, #e5484d); }

.level-error .log-message { color: var(--lumi-danger, #e5484d); }
.level-warn .log-message { color: var(--lumi-accent, #e6a23c); }

.log-scope {
  color: var(--text-secondary, #aaa);
  flex-shrink: 0;
}

.log-message {
  flex: 1;
  color: var(--text-primary, inherit);
}

.log-data {
  opacity: 0.65;
  font-size: 11px;
}

.list-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3, 12px);
  flex-shrink: 0;
  font-size: var(--text-xs, 12px);
  color: var(--text-secondary, inherit);
}

.count-label {
  flex-shrink: 0;
}

.status-label {
  flex: 1;
  text-align: center;
  color: var(--lumi-brand, #4a9eff);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-label.error {
  color: var(--lumi-danger, #e5484d);
}

.pagination {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1, 4px);
  flex-shrink: 0;
}

.page-btn,
.jump-latest {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  border: 1px solid var(--border-light, rgba(128, 128, 128, 0.25));
  background: transparent;
  color: var(--text-secondary, inherit);
  border-radius: var(--radius-sm, 6px);
  padding: 2px 6px;
  cursor: pointer;
  font-size: var(--text-xs, 12px);
}

.page-btn:hover:not(:disabled),
.jump-latest:hover {
  background: var(--surface-hover, rgba(128, 128, 128, 0.1));
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-label {
  padding: 0 var(--space-1, 4px);
  white-space: nowrap;
}

/* 日志段抽屉 */
.segments-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 320px;
  background: var(--surface, #fff);
  border-left: 1px solid var(--border-light, rgba(128, 128, 128, 0.25));
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  z-index: 30;
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3, 12px);
  border-bottom: 1px solid var(--divider-horizontal, rgba(128, 128, 128, 0.2));
  flex-shrink: 0;
}

.drawer-title {
  font-weight: var(--font-semibold, 600);
  font-size: var(--text-sm, 13px);
}

.drawer-close {
  border: none;
  background: transparent;
  color: var(--text-secondary, inherit);
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm, 6px);
}

.drawer-close:hover {
  background: var(--surface-hover, rgba(128, 128, 128, 0.1));
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2, 8px);
  display: flex;
  flex-direction: column;
  gap: var(--space-2, 8px);
}

.drawer-empty {
  text-align: center;
  color: var(--text-muted, inherit);
  opacity: 0.7;
  padding: var(--space-4, 16px);
  font-size: var(--text-xs, 12px);
}

.segment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2, 8px);
  padding: var(--space-2, 8px);
  border: 1px solid var(--border-light, rgba(128, 128, 128, 0.2));
  border-radius: var(--radius-md, 8px);
}

.segment-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.segment-name {
  font-family: Consolas, monospace;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.segment-meta {
  font-size: 11px;
  color: var(--text-muted, inherit);
  opacity: 0.8;
}

.segment-open {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--border-light, rgba(128, 128, 128, 0.25));
  background: transparent;
  color: var(--text-secondary, inherit);
  border-radius: var(--radius-sm, 6px);
  padding: 3px 8px;
  cursor: pointer;
  font-size: 11px;
  flex-shrink: 0;
}

.segment-open:hover {
  background: var(--surface-hover, rgba(128, 128, 128, 0.1));
}

.drawer-enter-active,
.drawer-leave-active {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.drawer-enter-from,
.drawer-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
