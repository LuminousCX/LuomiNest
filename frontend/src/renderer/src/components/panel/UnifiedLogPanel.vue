<script setup lang="ts">
/**
 * 统一日志面板（控制台"日志" Tab 内嵌）
 *
 * 数据源为主进程 log-hub 内存环形缓冲（1000 条，log:query 分页 + log:onAppended 实时尾随），
 * 覆盖 前端(renderer) / 主进程(main) / 后端(backend) / 平台(platform) 四路来源。
 * 来源小号 sub-tab + 级别筛选 + 搜索 + 尾随/翻页 + 清空/导出/上传/日志目录/分割文件。
 * 由原独立"应用日志"页（LogsView）整体迁入，随日志集成进控制台（2026-10）。
 */
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { formatTime as formatClockTime } from '@/utils/format'
import { debounce } from '@/utils/debounce'
import { useI18n } from 'vue-i18n'
import SegmentTabs from '@/components/common/SegmentTabs.vue'
import type { SegmentTabOption } from '@/components/common/SegmentTabs.vue'
import {
  Search, Trash2, Download, Upload, FolderOpen, Files, X,
  ChevronLeft, ChevronRight, Pause, Play, ArrowDownToLine, RefreshCw,
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

const { t, locale } = useI18n()

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

/** 来源分段器（SegmentTabs sm 档）选项 */
const sourceTabs = computed<SegmentTabOption<SourceFilter>[]>(() =>
  sourceOptions.map((opt) => ({ value: opt.value, label: t(opt.labelKey) }))
)

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

const onSearchInput = debounce((): void => {
  search.value = searchInput.value.trim()
  page.value = 1
  void load()
}, SEARCH_DEBOUNCE_MS)

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
  return formatClockTime(ts, { seconds: true })
}

/** 本地时区日期键（用于跨日比较），解析失败返回空串 */
const localDayKey = (ts: string): string => {
  const date = new Date(ts)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
}

/** 分隔行展示的本地日期（跨年时补年份），按界面语言格式化 */
const formatDayLabel = (ts: string): string => {
  const date = new Date(ts)
  if (Number.isNaN(date.getTime())) return ts
  const options: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' }
  if (date.getFullYear() !== new Date().getFullYear()) options.year = 'numeric'
  return new Intl.DateTimeFormat(locale.value, options).format(date)
}

/** 日志行视图模型：相邻条目本地日期不同时插入日期分隔行 */
interface LogRow {
  key: string
  entry?: LogEntry
  day?: string
}

const logRows = computed<LogRow[]>(() => {
  const rows: LogRow[] = []
  let lastDay = ''
  for (const entry of entries.value) {
    const day = localDayKey(entry.ts)
    if (day && day !== lastDay) {
      rows.push({ key: `day-${day}`, day: formatDayLabel(entry.ts) })
      lastDay = day
    }
    rows.push({ key: `seq-${entry.seq}`, entry })
  }
  return rows
})

const formatFullTime = (ts: string): string => {
  const date = new Date(ts)
  if (Number.isNaN(date.getTime())) return ts
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

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

/* ── 供控制台页头"复制"/终端 refresh/clear 命令调用 ─────────────────────── */

const getCopyText = (): string =>
  entries.value.map(e =>
    `[${e.ts}] [${e.level.toUpperCase()}] [${e.source}] [${e.scope}] ${e.message}${formatData(e) ? ` ${formatData(e)}` : ''}`
  ).join('\n')

const clearAll = (): Promise<void> => handleClear()

defineExpose({ getCopyText, clearAll, reload: load })

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
  onSearchInput.cancel()
  if (statusTimer) clearTimeout(statusTimer)
})
</script>

<template>
  <div class="unified-log-panel">
    <div class="panel-toolbar">
      <div class="toolbar-left">
        <SegmentTabs
          v-model="sourceFilter"
          :options="sourceTabs"
          size="sm"
          :aria-label="t('log.title')"
          @update:model-value="onFilterChange"
        />
        <select v-model="levelFilter" class="level-select" @change="onFilterChange">
          <option v-for="opt in levelOptions" :key="opt.value" :value="opt.value">
            {{ t(opt.labelKey) }}
          </option>
        </select>
        <div class="search-box">
          <Search :size="13" class="search-icon" />
          <input
            v-model="searchInput"
            type="text"
            class="search-input"
            :placeholder="t('log.searchPlaceholder')"
            @input="onSearchInput"
          />
        </div>
      </div>
      <div class="toolbar-right">
        <button
          class="icon-action"
          :class="{ 'is-on': follow }"
          :title="follow ? t('log.following') : t('log.paused')"
          :aria-label="t('log.follow')"
          @click="toggleFollow"
        >
          <Pause v-if="follow" :size="14" />
          <Play v-else :size="14" />
        </button>
        <button class="icon-action" :title="t('log.segments')" :aria-label="t('log.segments')" @click="toggleSegments">
          <Files :size="14" />
        </button>
        <button class="icon-action" :title="t('log.openDir')" :aria-label="t('log.openDir')" @click="handleOpenDir">
          <FolderOpen :size="14" />
        </button>
        <button
          class="icon-action"
          :disabled="!isCloudLoggedIn || isUploading"
          :title="isCloudLoggedIn ? t('log.upload') : t('log.uploadNeedLoginHint')"
          :aria-label="t('log.upload')"
          @click="handleUpload"
        >
          <Upload :size="14" />
        </button>
        <button class="icon-action" :title="t('log.export')" :aria-label="t('log.export')" @click="handleExport">
          <Download :size="14" />
        </button>
        <button
          class="icon-action danger"
          :title="t('log.clear')"
          :aria-label="t('log.clear')"
          @click="handleClear"
        >
          <RefreshCw v-if="loading" :size="14" class="spin" />
          <Trash2 v-else :size="14" />
        </button>
      </div>
    </div>

    <div ref="listRef" class="log-list" @scroll="onScroll">
      <div v-if="entries.length === 0 && !loading" class="log-empty">
        {{ t('log.empty') }}
      </div>
      <template v-for="row in logRows" :key="row.key">
        <div v-if="row.day" class="log-day-divider" role="separator">
          <span>{{ row.day }}</span>
        </div>
        <div
          v-else-if="row.entry"
          :class="['log-row', levelClass(row.entry.level)]"
          :title="formatFullTime(row.entry.ts)"
        >
          <span class="log-time">{{ formatTime(row.entry.ts) }}</span>
          <span class="log-source">[{{ t(`log.source.${row.entry.source}`) }}]</span>
          <span class="log-level" :class="levelClass(row.entry.level)">{{ row.entry.level.toUpperCase() }}</span>
          <span class="log-scope">[{{ row.entry.scope }}]</span>
          <span class="log-message">{{ row.entry.message }}<template v-if="formatData(row.entry)"> <span class="log-data">{{ formatData(row.entry) }}</span></template></span>
        </div>
      </template>
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
.unified-log-panel {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  flex-wrap: wrap;
  row-gap: var(--space-2);
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.level-select {
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  background: var(--surface);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.level-select:hover {
  border-color: var(--lumi-brand);
}

.search-box {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  transition: border-color var(--transition-fast);
}

.search-box:focus-within {
  border-color: var(--lumi-brand);
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  width: 180px;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--text-xs);
  color: var(--text);
}

.search-input::placeholder {
  color: var(--text-muted);
}

/* ===== 右侧图标动作组（尾随/文件/目录/上传/导出/清空） ===== */
.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.icon-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.icon-action:hover:not(:disabled) {
  background: var(--surface-hover);
  color: var(--text);
}

.icon-action:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.icon-action.is-on {
  color: var(--lumi-brand);
}

.icon-action.danger:hover:not(:disabled) {
  color: var(--lumi-danger);
}

.spin {
  animation: spin 1s linear infinite;
}

/* ===== 日志列表 ===== */
.log-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-2) var(--space-3);
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: var(--leading-relaxed);
}

.log-empty {
  padding: var(--space-6) 0;
  text-align: center;
  color: var(--text-muted);
  font-size: var(--text-sm);
  font-family: var(--font-sans);
}

.log-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  padding: 1px 0;
  white-space: nowrap;
}

/* 跨日分隔行：hairline + 本地日期小字 */
.log-day-divider {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: var(--space-1) 0;
  color: var(--text-muted);
  font-size: var(--text-2xs);
  font-family: var(--font-sans);
  user-select: none;
}

.log-day-divider::before,
.log-day-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border-light);
}

.log-row:hover {
  background: var(--surface-hover);
}

.log-time {
  color: var(--text-muted);
  flex-shrink: 0;
}

.log-source {
  color: var(--text-muted);
  flex-shrink: 0;
}

.log-level {
  flex-shrink: 0;
  font-weight: var(--font-semibold);
}

.level-debug .log-level { color: var(--text-muted); }
.level-info .log-level { color: var(--text-secondary); }
.level-warn .log-level { color: var(--lumi-warning); }
.level-error .log-level { color: var(--lumi-danger); }

.level-error .log-message { color: var(--lumi-danger); }
.level-warn .log-message { color: var(--lumi-warning); }

.log-scope {
  color: var(--text-muted);
  flex-shrink: 0;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-message {
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-data {
  color: var(--text-muted);
}

/* ===== 底部：计数 / 状态 / 分页 ===== */
.list-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  flex-shrink: 0;
}

.count-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.status-label {
  font-size: var(--text-xs);
  color: var(--lumi-success);
}

.status-label.error {
  color: var(--lumi-danger);
}

.pagination {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-left: auto;
}

.jump-latest {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  margin-right: var(--space-2);
  padding: 2px var(--space-2);
  border: none;
  background: transparent;
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  color: var(--lumi-brand);
  cursor: pointer;
}

.jump-latest:hover {
  background: var(--surface-hover);
}

.page-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  border-radius: var(--radius-xs);
  color: var(--text-secondary);
  cursor: pointer;
}

.page-btn:hover:not(:disabled) {
  background: var(--surface-hover);
  color: var(--text);
}

.page-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.page-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  min-width: 64px;
  text-align: center;
}

/* ===== 分割文件抽屉 ===== */
.segments-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 320px;
  z-index: var(--z-sticky);
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border-left: 1px solid var(--border-light);
  border-radius: 0 var(--radius-lg) var(--radius-lg) 0;
  box-shadow: var(--shadow-lg);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-light);
}

.drawer-title {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.drawer-close {
  display: inline-flex;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: var(--radius-xs);
  padding: 2px;
}

.drawer-close:hover {
  color: var(--text);
  background: var(--surface-hover);
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2) var(--space-3);
}

.drawer-empty {
  padding: var(--space-6) 0;
  text-align: center;
  color: var(--text-muted);
  font-size: var(--text-xs);
}

.segment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-1);
  border-bottom: 1px solid var(--border-light);
}

.segment-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.segment-name {
  font-size: var(--text-xs);
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.segment-meta {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.segment-open {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: none;
  background: transparent;
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  cursor: pointer;
  flex-shrink: 0;
}

.segment-open:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.drawer-enter-active,
.drawer-leave-active {
  transition: transform var(--duration-normal) var(--ease-in-out), opacity var(--duration-normal) var(--ease-in-out);
}

.drawer-enter-from,
.drawer-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
