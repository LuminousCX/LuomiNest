<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  BarChart3,
  Brain,
  Database,
  Clock,
  Layers,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  Server,
  Cpu,
  Users,
  Sparkles,
  Calendar,
  User,
  MessageSquare,
  Activity,
  ChevronDown,
  TrendingUp,
  TrendingDown,
} from 'lucide-vue-next'
import LumiCard from '../../components/common/LumiCard.vue'
import LumiButton from '../../components/common/LumiButton.vue'
import { useMemoryStore } from '../../stores/memory'
import { useStatsStore, type StatsRange } from '../../stores/stats'
import { useModelStore } from '../../stores/model'
import { formatTime } from '../../utils/format'
import {
  aggregateSeriesByMonth,
  buildDailySeries,
  buildHeatmap,
  calculateTrend,
  diffDays,
  formatCompact,
  generateHistogramBars,
  isoDate,
  type HeatmapCell,
  type HistogramBar,
} from '../../utils/chart'

const memoryStore = useMemoryStore()
const statsStore = useStatsStore()
const modelStore = useModelStore()
const { t } = useI18n()

// ── 时间区间（下拉框） ──

type RangeKey = 'today' | 'yesterday' | 'last7' | 'last30' | 'lastMonth' | 'last90' | 'lastYear' | 'all'

const RANGE_KEYS: RangeKey[] = ['today', 'yesterday', 'last7', 'last30', 'lastMonth', 'last90', 'lastYear', 'all']

const rangeKey = ref<RangeKey>('last7')

const currentRange = computed<StatsRange>(() => {
  const now = new Date()
  switch (rangeKey.value) {
    case 'today': {
      const iso = isoDate(now)
      return { start: iso, end: iso }
    }
    case 'yesterday': {
      const d = new Date(now)
      d.setDate(d.getDate() - 1)
      const iso = isoDate(d)
      return { start: iso, end: iso }
    }
    case 'last7': return { days: 7 }
    case 'last30': return { days: 30 }
    case 'last90': return { days: 90 }
    case 'lastYear': return { days: 365 }
    case 'lastMonth': {
      const start = new Date(now.getFullYear(), now.getMonth() - 1, 1)
      const end = new Date(now.getFullYear(), now.getMonth(), 0)
      return { start: isoDate(start), end: isoDate(end) }
    }
    case 'all':
    default:
      return {}
  }
})

/** 直方图取数窗口：明确日期（缺失的天补 0），「全部」时退化为数据的实际日期范围 */
const histogramWindow = computed<{ start?: string; end?: string }>(() => {
  const r = currentRange.value
  if (r.start && r.end) return { start: r.start, end: r.end }
  if (r.days) {
    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - (r.days - 1))
    return { start: isoDate(start), end: isoDate(end) }
  }
  const keys = Object.keys(statsStore.dailyUsage).sort()
  if (!keys.length) return {}
  return { start: keys[0], end: keys[keys.length - 1] }
})

const rangeSpanDays = computed(() => {
  const { start, end } = histogramWindow.value
  if (start && end) return Math.max(1, diffDays(start, end) + 1)
  return 1
})

const monthName = (m: number) => t(`stats.month.m${m + 1}`)

/** 窗口 > 90 天时按月聚合成柱，避免柱子过密 */
const chartSeries = computed(() => {
  const { start, end } = histogramWindow.value
  const series = buildDailySeries(statsStore.dailyUsage, statsStore.tokensByDay, start, end)
  if (rangeSpanDays.value > 90) {
    return aggregateSeriesByMonth(series).map(m => ({
      ...m,
      label: monthName(Number(m.fullLabel.slice(5, 7)) - 1),
    }))
  }
  return series
})

const isMonthlyBuckets = computed(() => rangeSpanDays.value > 90)

const currentTime = ref(new Date())
let timeInterval: ReturnType<typeof setInterval>

const greeting = computed(() => {
  const hour = currentTime.value.getHours()
  if (hour < 6 || hour >= 23) return t('stats.greeting.lateNight')
  if (hour < 9) return t('stats.greeting.morning')
  if (hour < 12) return t('stats.greeting.forenoon')
  if (hour < 14) return t('stats.greeting.noon')
  if (hour < 18) return t('stats.greeting.afternoon')
  return t('stats.greeting.evening')
})

const formattedDate = computed(() => {
  const d = currentTime.value
  return t('stats.date', {
    y: d.getFullYear(),
    m: d.getMonth() + 1,
    d: d.getDate(),
    week: t(`stats.wd${d.getDay()}`),
  })
})

const profile = computed(() => memoryStore.profile)

const hasProfile = computed(() => !!profile.value.name)

const memoryLineCount = computed(() => {
  return memoryStore.facts.length
})

const dailyCount = computed(() => memoryStore.dailies.length)

const hasSummary = computed(() => {
  const s = memoryStore.summarySections
  return !!(s['用户画像'] || s['兴趣偏好'] || s['近期状态'] || s['事件时间线'])
})

// ── 区间汇总分析 ──

const requestTrend = computed(() => {
  const c = statsStore.usageComparison
  if (!c) return null
  return calculateTrend(c.current.total_requests, c.previous.total_requests)
})

const tokenTrend = computed(() => {
  const c = statsStore.usageComparison
  if (!c) return null
  return calculateTrend(c.current.total_tokens, c.previous.total_tokens)
})

const summaryStats = computed(() => {
  const totalReq = statsStore.totalRequests
  const totalTok = statsStore.totalTokens
  let peak: { date: string; count: number } | null = null
  for (const [date, count] of Object.entries(statsStore.byDay)) {
    if (!peak || count > peak.count) peak = { date, count }
  }
  const span = rangeSpanDays.value
  return {
    totalReq,
    totalTok: formatCompact(totalTok),
    avgReq: formatCompact(Math.round(totalReq / span)),
    avgTok: formatCompact(Math.round(totalTok / span)),
    peakDate: peak ? peak.date.slice(5) : null,
    peakCount: peak?.count ?? 0,
    hasData: totalReq > 0 || !!peak,
  }
})

// ── 模型排行 ──

const apiProviders = computed(() => {
  const providers = statsStore.byProvider
  if (!providers.length) return []
  const maxReq = Math.max(...providers.map(p => p.requests), 1)
  return providers.map(p => {
    return {
      name: p.name,
      requests: p.requests,
      tokens: formatCompact(p.total_tokens),
      pct: Math.round((p.requests / maxReq) * 100),
      trend: 'up' as const,
    }
  })
})

// ── 上下文监控（单色细条） ──

const contextMetrics = computed(() => {
  const conv = statsStore.totalConversations
  const msg = statsStore.totalMessages
  const tok = statsStore.totalTokens
  const windowSize = modelStore.modelConfig.contextWindowSize || 32768
  const totalCtx = tok
  return [
    { label: t('stats.ctx.totalUsage'), value: totalCtx, unit: 'tokens', max: Math.max(totalCtx, windowSize) },
    { label: t('stats.ctx.windowRate'), value: windowSize > 0 ? Math.min(100, Math.round((totalCtx / windowSize) * 100)) : 0, unit: '%', max: 100 },
    { label: t('stats.ctx.turns'), value: msg, unit: t('stats.ctx.unitTurns'), max: Math.max(msg * 2, 100) },
    { label: t('stats.ctx.conversations'), value: conv, unit: t('stats.ctx.unitCount'), max: Math.max(conv * 2, 50) },
  ]
})

// ── 直方图 ──

const chartWrapRef = ref<HTMLElement | null>(null)
const chartWidth = ref(600)
const chartHeight = ref(240)
let resizeObserver: ResizeObserver | null = null

const histogram = computed(() => generateHistogramBars(chartSeries.value, {
  width: chartWidth.value,
  height: chartHeight.value,
  padding: { top: 16, bottom: 28, left: 44, right: 8 },
  maxLabelCount: 10,
}))

const hoveredBar = ref<HistogramBar | null>(null)

const chartTooltipStyle = computed(() => {
  if (!hoveredBar.value) return {}
  const cx = hoveredBar.value.x + hoveredBar.value.width / 2
  const y = hoveredBar.value.y
  const isNearTop = y < 90
  const isNearLeft = cx < 90
  const isNearRight = cx > chartWidth.value - 90

  let transformX = '-50%'
  if (isNearLeft) transformX = '0%'
  else if (isNearRight) transformX = '-100%'

  const transformY = isNearTop ? '14px' : 'calc(-100% - 12px)'

  return {
    left: `${cx}px`,
    top: `${y}px`,
    transform: `translate(${transformX}, ${transformY})`,
  }
})

function onChartMove(event: MouseEvent) {
  if (!chartWrapRef.value || !histogram.value.bars.length) return
  const rect = chartWrapRef.value.getBoundingClientRect()
  const scale = chartWidth.value / Math.max(rect.width, 1)
  const mx = (event.clientX - rect.left) * scale

  let nearest: HistogramBar | null = null
  let minDistance = Infinity
  for (const bar of histogram.value.bars) {
    const distance = Math.abs(bar.x + bar.width / 2 - mx)
    if (distance < minDistance) {
      minDistance = distance
      nearest = bar
    }
  }
  hoveredBar.value = nearest
}

function onChartLeave() {
  hoveredBar.value = null
}

// ── 活跃度热力图 ──

const heatmapWrapRef = ref<HTMLElement | null>(null)
const heatmapWidth = ref(0)
let heatmapResizeObserver: ResizeObserver | null = null
const hoveredCell = ref<HeatmapCell | null>(null)

const heatmapModel = computed(() => buildHeatmap(statsStore.heatmapByDay, statsStore.heatmapTokensByDay, {
  days: 365,
  fitWidth: heatmapWidth.value,
  monthName,
}))

const heatmapTooltipStyle = computed(() => {
  if (!hoveredCell.value) return {}
  const model = heatmapModel.value
  const scale = (heatmapWidth.value || model.width) / model.width
  const x = (hoveredCell.value.x + model.cellSize / 2) * scale
  const y = hoveredCell.value.y * scale
  const isNearTop = y < 90
  const isNearLeft = x < 100
  const isNearRight = x > heatmapWidth.value - 100

  let transformX = '-50%'
  if (isNearLeft) transformX = '0%'
  else if (isNearRight) transformX = '-100%'

  const transformY = isNearTop ? '14px' : 'calc(-100% - 12px)'

  return {
    left: `${x}px`,
    top: `${y}px`,
    transform: `translate(${transformX}, ${transformY})`,
  }
})

// ── 记忆统计 ──

const memorySegments = computed(() => {
  const summaryValue = hasSummary.value ? 1 : 0
  const shades = [
    'var(--lumi-brand)',
    'color-mix(in srgb, var(--lumi-brand) 55%, transparent)',
    'color-mix(in srgb, var(--lumi-brand) 26%, transparent)',
  ]
  const values = [
    { label: t('stats.memory.longTerm'), value: memoryLineCount.value, display: t('stats.memory.lineUnit', { n: memoryLineCount.value }) },
    { label: t('stats.memory.distilledLabel'), value: summaryValue, display: hasSummary.value ? t('stats.memory.distilled') : t('stats.memory.notDistilled') },
    { label: t('stats.memory.daily'), value: dailyCount.value, display: t('stats.memory.dayUnit', { n: dailyCount.value }) },
  ]
  const total = values.reduce((sum, item) => sum + item.value, 0) || 1
  const circumference = 251.2
  let offset = 0
  return values.map((item, idx) => {
    const len = (item.value / total) * circumference
    const segment = { ...item, color: shades[idx % shades.length], len, offset }
    offset -= len
    return segment
  })
})

// ── 最近活动 ──

const recentActivities = computed(() => {
  const records = statsStore.recentRecords
  if (!records.length) return []
  return records.slice(0, 10).map(r => {
    const ts = r.timestamp
    const timeStr = formatTime(ts)
    const tokStr = r.total_tokens > 0 ? ` (${r.total_tokens.toLocaleString()} tokens)` : ''
    return {
      time: timeStr,
      action: t('stats.activity.apiCall'),
      detail: `${r.provider} / ${r.model}${tokStr}`,
      type: 'api' as const,
    }
  })
})

const isRefreshing = ref(false)

const selectedAgentId = ref<string | null>(null)

async function onAgentChange() {
  await memoryStore.switchAgent(selectedAgentId.value)
}

async function handleRefresh() {
  isRefreshing.value = true
  await memoryStore.switchAgent(selectedAgentId.value)
  await statsStore.fetchAll(currentRange.value)
  setTimeout(() => { isRefreshing.value = false }, 600)
}

async function loadData() {
  await Promise.all([
    memoryStore.fetchMemoryAgents(),
    statsStore.fetchAll(currentRange.value),
  ])
  await memoryStore.switchAgent(selectedAgentId.value)
}

const updateChartDimensions = () => {
  if (!chartWrapRef.value) return
  const rect = chartWrapRef.value.getBoundingClientRect()
  if (rect.width > 0) {
    chartWidth.value = Math.round(rect.width)
  }
  if (rect.height > 0) {
    chartHeight.value = Math.round(rect.height)
  }
}

const updateHeatmapWidth = () => {
  if (!heatmapWrapRef.value) return
  const rect = heatmapWrapRef.value.getBoundingClientRect()
  if (rect.width > 0) {
    heatmapWidth.value = Math.round(rect.width)
  }
}

onMounted(() => {
  loadData()
  timeInterval = setInterval(() => { currentTime.value = new Date() }, 1000)

  if (chartWrapRef.value) {
    updateChartDimensions()
    resizeObserver = new ResizeObserver(() => updateChartDimensions())
    resizeObserver.observe(chartWrapRef.value)
  }
  if (heatmapWrapRef.value) {
    updateHeatmapWidth()
    heatmapResizeObserver = new ResizeObserver(() => updateHeatmapWidth())
    heatmapResizeObserver.observe(heatmapWrapRef.value)
  }
})

onUnmounted(() => {
  if (timeInterval) clearInterval(timeInterval)
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (heatmapResizeObserver) {
    heatmapResizeObserver.disconnect()
    heatmapResizeObserver = null
  }
})

watch(rangeKey, () => { loadData() })
</script>

<template>
  <div class="data-stats-view">
    <div class="stats-header animate-fade-in">
      <div class="stats-header__text">
        <h1 class="stats-title lumi-page-title">{{ t('stats.title') }}</h1>
        <p class="stats-desc lumi-page-desc">{{ greeting }}，LuminousChenXi · {{ formattedDate }}</p>
      </div>
      <div class="stats-header__actions lumi-row-3">
        <label class="range-select-wrap">
          <Calendar :size="14" class="range-select-icon" />
          <select v-model="rangeKey" class="range-select" :aria-label="t('stats.range.label')">
            <option v-for="key in RANGE_KEYS" :key="key" :value="key">
              {{ t('stats.range.' + key) }}
            </option>
          </select>
          <ChevronDown :size="12" class="range-select-chevron" />
        </label>
        <LumiButton variant="ghost" size="sm" icon-only :aria-label="t('stats.refresh')" @click="handleRefresh">
          <template #icon><RefreshCw :size="14" :class="{ 'spin-animation': isRefreshing }" /></template>
        </LumiButton>
      </div>
    </div>

    <!-- 区间汇总分析：无边框统计条，hairline 分隔 -->
    <div class="summary-strip">
      <div class="summary-item">
        <span class="summary-label">{{ t('stats.summary.totalRequests') }}</span>
        <div class="summary-value-row">
          <span class="summary-value">{{ summaryStats.totalReq.toLocaleString() }}</span>
          <span v-if="requestTrend !== null" class="summary-trend">
            <component :is="requestTrend >= 0 ? ArrowUpRight : ArrowDownRight" :size="12" />
            {{ Math.abs(requestTrend) }}%
          </span>
        </div>
      </div>
      <div class="summary-item">
        <span class="summary-label">{{ t('stats.summary.totalTokens') }}</span>
        <div class="summary-value-row">
          <span class="summary-value">{{ summaryStats.totalTok }}</span>
          <span v-if="tokenTrend !== null" class="summary-trend">
            <component :is="tokenTrend >= 0 ? ArrowUpRight : ArrowDownRight" :size="12" />
            {{ Math.abs(tokenTrend) }}%
          </span>
        </div>
      </div>
      <div class="summary-item">
        <span class="summary-label">{{ t('stats.summary.avgDailyRequests') }}</span>
        <div class="summary-value-row">
          <span class="summary-value">{{ summaryStats.avgReq }}</span>
        </div>
      </div>
      <div class="summary-item">
        <span class="summary-label">{{ t('stats.summary.avgDailyTokens') }}</span>
        <div class="summary-value-row">
          <span class="summary-value">{{ summaryStats.avgTok }}</span>
        </div>
      </div>
      <div class="summary-item">
        <span class="summary-label">{{ t('stats.summary.peakDay') }}</span>
        <div class="summary-value-row">
          <span class="summary-value">{{ summaryStats.peakDate ?? '—' }}</span>
          <span v-if="summaryStats.peakDate" class="summary-sub">{{ t('stats.countTimes', { n: summaryStats.peakCount }) }}</span>
        </div>
      </div>
    </div>

    <!-- 活跃度热力图：最近一年每日 API 调用密度 -->
    <LumiCard class="section-card heatmap-card" padding="md">
      <template #title>
        <Activity :size="15" class="section-icon-muted" />
        <div class="chart-title-text">
          <span class="chart-title-main">{{ t('stats.heatmap.title') }}</span>
          <span class="chart-title-sub">{{ t('stats.heatmap.subtitle') }}</span>
        </div>
      </template>
      <template #header>
        <div class="hm-legend">
          <span class="hm-legend-label">{{ t('stats.heatmap.less') }}</span>
          <span v-for="l in 5" :key="l" :class="['hm-cell', 'hm-legend-cell', 'hm-level-' + (l - 1)]" />
          <span class="hm-legend-label">{{ t('stats.heatmap.more') }}</span>
        </div>
      </template>

      <div ref="heatmapWrapRef" class="heatmap-wrap" @mouseleave="hoveredCell = null">
        <svg
          :viewBox="`0 0 ${heatmapModel.width} ${heatmapModel.height}`"
          class="heatmap-svg"
        >
          <!-- 星期标注（隔行显示） -->
          <text
            v-for="d in [1, 3, 5]"
            :key="'hm-wd-' + d"
            :x="heatmapModel.labelWidth - 6"
            :y="heatmapModel.labelHeight + d * (heatmapModel.cellSize + heatmapModel.gap) + heatmapModel.cellSize / 2 + 3"
            text-anchor="end"
            class="hm-weekday-text"
          >
            {{ t(`stats.wd${d}`) }}
          </text>

          <!-- 月份标注 -->
          <text
            v-for="(m, i) in heatmapModel.monthLabels"
            :key="'hm-m-' + i"
            :x="m.x"
            y="11"
            class="hm-month-text"
          >
            {{ m.label }}
          </text>

          <!-- 格子 -->
          <rect
            v-for="cell in heatmapModel.cells"
            :key="cell.date"
            :x="cell.x"
            :y="cell.y"
            :width="heatmapModel.cellSize"
            :height="heatmapModel.cellSize"
            rx="2"
            :class="['hm-cell', 'hm-level-' + cell.level]"
            @mouseenter="hoveredCell = cell"
          />
        </svg>

        <div
          v-if="hoveredCell"
          class="chart-tooltip"
          :style="heatmapTooltipStyle"
        >
          <div class="ct-header">
            <span class="ct-label">{{ hoveredCell.date }}</span>
          </div>
          <div class="ct-value-row">
            <span class="ct-num">{{ hoveredCell.count.toLocaleString() }}</span>
            <span class="ct-unit">{{ t('stats.unitTimes') }}</span>
          </div>
          <div class="ct-value-row">
            <span class="ct-num-sm">{{ formatCompact(hoveredCell.tokens) }}</span>
            <span class="ct-unit">tokens</span>
          </div>
        </div>
      </div>
    </LumiCard>

    <div class="main-content">
      <div class="left-col">
        <LumiCard class="section-card chart-card" padding="none">
          <template #title>
            <div class="chart-header-left">
              <BarChart3 :size="16" class="section-icon-muted" />
              <div class="chart-title-text">
                <span class="chart-title-main">{{ t('stats.chartTitle') }}</span>
                <span class="chart-title-sub">{{ isMonthlyBuckets ? t('stats.chartSubtitleMonthly') : t('stats.chartSubtitle') }}</span>
              </div>
            </div>
          </template>
          <template #header>
            <div class="chart-kpis">
              <div class="kpi-item">
                <span class="kpi-label">{{ t('stats.summary.totalRequests') }}</span>
                <span class="kpi-value">{{ statsStore.totalRequests.toLocaleString() }}</span>
                <span v-if="requestTrend !== null" class="summary-trend">
                  <component :is="requestTrend >= 0 ? ArrowUpRight : ArrowDownRight" :size="12" />
                  {{ Math.abs(requestTrend) }}%
                </span>
              </div>
              <div class="kpi-item">
                <span class="kpi-label">{{ t('stats.summary.totalTokens') }}</span>
                <span class="kpi-value">{{ formatCompact(statsStore.totalTokens) }}</span>
                <span v-if="tokenTrend !== null" class="summary-trend">
                  <component :is="tokenTrend >= 0 ? ArrowUpRight : ArrowDownRight" :size="12" />
                  {{ Math.abs(tokenTrend) }}%
                </span>
              </div>
            </div>
          </template>

          <div class="chart-area" @mousemove="onChartMove" @mouseleave="onChartLeave">
            <div ref="chartWrapRef" class="histogram-svg-wrap">
              <svg
                v-if="histogram.bars.length"
                :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
                class="histogram-chart"
              >
                <!-- Y 轴水平参考线及刻度 -->
                <g class="chart-grid">
                  <g v-for="tick in histogram.ticks" :key="'tick-' + tick.value">
                    <line
                      :x1="44"
                      :y1="tick.y"
                      :x2="chartWidth - 8"
                      :y2="tick.y"
                      class="grid-line"
                    />
                    <text
                      :x="36"
                      :y="tick.y + 3"
                      text-anchor="end"
                      class="grid-tick-text"
                    >
                      {{ tick.label }}
                    </text>
                  </g>
                </g>

                <!-- 直方图柱体 -->
                <rect
                  v-for="bar in histogram.bars"
                  :key="'bar-' + bar.index"
                  :x="bar.x"
                  :y="bar.y"
                  :width="bar.width"
                  :height="bar.height"
                  rx="2"
                  :class="['hist-bar', { active: hoveredBar?.index === bar.index }]"
                />

                <!-- X 轴基线 -->
                <line
                  class="axis-baseline"
                  :x1="44"
                  :y1="histogram.baselineY"
                  :x2="chartWidth - 8"
                  :y2="histogram.baselineY"
                />

                <!-- X 轴抽样标签 -->
                <g class="chart-x-axis-svg">
                  <template v-for="(bar, idx) in histogram.bars" :key="'xl-' + idx">
                    <text
                      v-if="idx % histogram.labelEvery === 0"
                      :x="bar.x + bar.width / 2"
                      :y="chartHeight - 8"
                      text-anchor="middle"
                      class="chart-axis-label"
                      :class="{ 'axis-label--active': hoveredBar?.index === idx }"
                    >
                      {{ bar.label }}
                    </text>
                  </template>
                </g>
              </svg>

              <div v-else class="chart-empty">{{ t('stats.chartEmpty') }}</div>

              <!-- 悬浮提示框 -->
              <div
                v-if="hoveredBar && histogram.bars.length"
                class="chart-tooltip"
                :style="chartTooltipStyle"
              >
                <div class="ct-header">
                  <span class="ct-label">{{ hoveredBar.fullLabel }}</span>
                </div>
                <div class="ct-value-row">
                  <span class="ct-num">{{ hoveredBar.value.toLocaleString() }}</span>
                  <span class="ct-unit">{{ t('stats.unitTimes') }}</span>
                </div>
                <div class="ct-value-row">
                  <span class="ct-num-sm">{{ formatCompact(hoveredBar.tokens) }}</span>
                  <span class="ct-unit">tokens</span>
                </div>
              </div>
            </div>
          </div>

          <div class="provider-list">
            <div
              v-for="(p, idx) in apiProviders"
              :key="p.name"
              class="provider-row"
            >
              <span :class="['provider-rank', { 'provider-rank--first': idx === 0 }]">{{ idx + 1 }}</span>
              <div class="provider-name-wrap">
                <Server :size="14" class="provider-icon" />
                <span class="provider-name lumi-clip-sm">{{ p.name }}</span>
              </div>
              <div class="provider-bar-bg">
                <div class="provider-bar-fill" :style="{ width: p.pct + '%' }"></div>
              </div>
              <div class="provider-stats">
                <span class="provider-requests">{{ t('stats.countTimes', { n: p.requests }) }}</span>
                <span class="provider-divider"></span>
                <span class="provider-tokens">{{ p.tokens }} tokens</span>
              </div>
              <div class="provider-trend">
                <TrendingUp v-if="p.trend === 'up'" :size="12" />
                <TrendingDown v-else :size="12" />
              </div>
            </div>
          </div>
        </LumiCard>

        <LumiCard class="section-card" padding="md">
          <template #title>
            <Brain :size="16" class="section-icon-muted" />
            <span>{{ t('stats.memory.title') }}</span>
          </template>
          <template #header>
            <div class="agent-selector">
              <Users :size="12" />
              <select v-model="selectedAgentId" class="agent-select" @change="onAgentChange">
                <option v-for="a in memoryStore.memoryAgents" :key="a.id" :value="a.id">
                  {{ a.name }}{{ a.fact_count !== undefined ? t('stats.agentFactCount', { n: a.fact_count }) : '' }}
                </option>
              </select>
            </div>
          </template>

          <div class="memory-stats-grid">
            <div class="memory-stat-item">
              <Database :size="16" class="memory-stat-icon" />
              <span class="memory-stat-label">{{ t('stats.memory.longTerm') }}</span>
              <span class="memory-stat-value">{{ t('stats.memory.lineUnit', { n: memoryLineCount }) }}</span>
            </div>
            <div class="memory-stat-item">
              <Sparkles :size="16" class="memory-stat-icon" />
              <span class="memory-stat-label">{{ t('stats.memory.distilledLabel') }}</span>
              <span class="memory-stat-value">{{ hasSummary ? t('stats.memory.distilled') : t('stats.memory.notDistilled') }}</span>
            </div>
            <div class="memory-stat-item">
              <Calendar :size="16" class="memory-stat-icon" />
              <span class="memory-stat-label">{{ t('stats.memory.daily') }}</span>
              <span class="memory-stat-value">{{ t('stats.memory.dayUnit', { n: dailyCount }) }}</span>
            </div>
            <div class="memory-stat-item">
              <User :size="16" class="memory-stat-icon" />
              <span class="memory-stat-label">{{ t('stats.memory.userProfile') }}</span>
              <span class="memory-stat-value">{{ hasProfile ? t('stats.memory.has') : t('stats.memory.none') }}</span>
            </div>
          </div>

          <div class="donut-section">
            <div class="donut-wrap">
              <svg viewBox="0 0 100 100" class="donut-chart">
                <circle cx="50" cy="50" r="40" fill="none" stroke="var(--border-light)" stroke-width="10" />
                <circle
                  v-for="(seg, idx) in memorySegments"
                  :key="seg.label"
                  cx="50"
                  cy="50"
                  r="40"
                  fill="none"
                  :stroke="seg.color"
                  stroke-width="10"
                  :stroke-dasharray="`${Math.max(0, seg.len - 2)} ${251.2 - Math.max(0, seg.len - 2)}`"
                  :stroke-dashoffset="seg.offset"
                  stroke-linecap="round"
                  class="donut-anim"
                  :style="{ animationDelay: `${idx * 0.1}s` }"
                />
              </svg>
              <div class="donut-center">
                <span class="dc-value lumi-title-2xl">{{ memoryLineCount }}</span>
                <span class="dc-label">{{ t('stats.card.memory.label') }}</span>
              </div>
            </div>
            <div class="donut-legend">
              <div v-for="seg in memorySegments" :key="seg.label" class="legend-item">
                <span class="legend-dot" :style="{ background: seg.color }"></span>
                <span class="legend-text">{{ seg.label }}</span>
                <span class="legend-count">{{ seg.display }}</span>
              </div>
            </div>
          </div>

          <div class="health-section">
            <div class="health-header lumi-row-between">
              <span class="health-label">{{ t('stats.memory.healthLabel') }}</span>
              <span class="health-value">{{ Math.min(100, Math.round((memoryLineCount / 50) * 100)) }}%</span>
            </div>
            <div class="health-bar-bg">
              <div
                class="health-bar-fill"
                :style="{ width: Math.min(100, Math.round((memoryLineCount / 50) * 100)) + '%' }"
              ></div>
            </div>
          </div>
        </LumiCard>
      </div>

      <div class="right-col">
        <LumiCard class="section-card" padding="md">
          <template #title>
            <Layers :size="16" class="section-icon-muted" />
            <span>{{ t('stats.ctx.title') }}</span>
          </template>
          <template #header>
            <Cpu :size="14" class="section-icon-muted" />
          </template>
          <div class="context-metrics">
            <div
              v-for="(m, idx) in contextMetrics"
              :key="m.label"
              class="context-item"
              :style="{ animationDelay: (0.18 + idx * 0.04) + 's' }"
            >
              <div class="context-label-row">
                <span class="context-label">{{ m.label }}</span>
                <span class="context-value">{{ m.value }} {{ m.unit }}</span>
              </div>
              <div class="context-bar-bg">
                <div
                  class="context-bar-fill"
                  :style="{ width: Math.min(100, (m.value / m.max * 100)) + '%' }"
                ></div>
              </div>
            </div>
          </div>
        </LumiCard>

        <LumiCard class="section-card" padding="md">
          <template #title>
            <Clock :size="16" class="section-icon-muted" />
            <span>{{ t('stats.activity.title') }}</span>
          </template>
          <template #header>
            <MessageSquare :size="14" class="section-icon-muted" />
          </template>
          <div class="activity-timeline">
            <div
              v-for="(a, idx) in recentActivities"
              :key="a.time + a.action + idx"
              class="activity-item"
              :style="{ animationDelay: (0.26 + idx * 0.03) + 's' }"
            >
              <div class="activity-dot-wrap">
                <span class="activity-dot"></span>
                <span v-if="idx < recentActivities.length - 1" class="activity-line"></span>
              </div>
              <div class="activity-content">
                <div class="activity-top-row">
                  <span class="activity-action">{{ a.action }}</span>
                  <span class="activity-time">{{ a.time }}</span>
                </div>
                <span class="activity-detail">{{ a.detail }}</span>
              </div>
            </div>
            <div v-if="!recentActivities.length" class="activity-empty">
              {{ t('stats.activity.empty') }}
            </div>
          </div>
        </LumiCard>
      </div>
    </div>
  </div>
</template>

<style scoped>
.data-stats-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--space-6) var(--space-7);
  gap: var(--space-5);
  overflow-y: auto;
}

.stats-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: var(--space-2);
  animation: lumi-content-fade-up var(--duration-enter) var(--ease-out-expo) both;
}

.stats-header__text {
  display: flex;
  flex-direction: column;
}

/* ── 区间下拉框 ── */

.range-select-wrap {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 5px var(--space-3);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: border-color var(--transition-fast), color var(--transition-fast);
  cursor: pointer;
}

.range-select-wrap:hover,
.range-select-wrap:focus-within {
  border-color: var(--lumi-brand);
  color: var(--text-secondary);
}

.range-select-icon {
  flex-shrink: 0;
}

.range-select-chevron {
  flex-shrink: 0;
  opacity: 0.7;
}

.range-select {
  appearance: none;
  -webkit-appearance: none;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  cursor: pointer;
  padding-right: 2px;
}

.range-select option {
  background: var(--surface);
  color: var(--text-primary);
}

/* ── 区间汇总分析条 ── */

.summary-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-5);
  padding: var(--space-4) 0;
  border-top: 1px solid var(--border-light);
  border-bottom: 1px solid var(--border-light);
  animation: lumi-content-fade-up var(--duration-enter) var(--ease-out-expo) both;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.summary-item + .summary-item {
  border-left: 1px solid var(--border-light);
  padding-left: var(--space-5);
}

.summary-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: 0.02em;
}

.summary-value-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  min-width: 0;
}

.summary-value {
  font-size: 1.55rem;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  line-height: 1.15;
  white-space: nowrap;
}

.summary-trend {
  display: inline-flex;
  align-items: center;
  gap: 1px;
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.summary-sub {
  font-size: var(--text-xs);
  color: var(--text-muted);
  white-space: nowrap;
}

/* ── 区块卡片 ── */

.main-content {
  display: flex;
  gap: var(--space-4);
}

.left-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}

.right-col {
  width: 360px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.section-card {
  animation: lumi-content-fade-up var(--duration-enter) var(--ease-out-expo) both;
}

.section-icon-muted {
  color: var(--text-muted);
  flex-shrink: 0;
}

.chart-title-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.chart-title-main {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  line-height: 1.2;
}

.chart-title-sub {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

/* ── 热力图 ── */

.hm-legend {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.hm-legend-label {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  margin: 0 2px;
}

.hm-legend-cell {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  display: inline-block;
}

.heatmap-wrap {
  position: relative;
  overflow-x: auto;
  padding: 2px 0 4px;
}

.heatmap-svg {
  display: block;
  width: 100%;
  height: auto;
}

.hm-cell {
  transition: fill var(--transition-fast);
}

.hm-level-0 { fill: var(--border-light); }
.hm-level-1 { fill: color-mix(in srgb, var(--lumi-brand) 22%, transparent); }
.hm-level-2 { fill: color-mix(in srgb, var(--lumi-brand) 45%, transparent); }
.hm-level-3 { fill: color-mix(in srgb, var(--lumi-brand) 68%, transparent); }
.hm-level-4 { fill: var(--lumi-brand); }

.hm-month-text {
  font-size: 10px;
  fill: var(--text-muted);
  font-family: var(--font-sans);
}

.hm-weekday-text {
  font-size: 9px;
  fill: var(--text-muted);
  font-family: var(--font-sans);
}

/* ── 直方图 ── */

.chart-card :deep(.lumi-card__body) {
  padding: 0;
}

.chart-header-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.chart-kpis {
  display: flex;
  align-items: baseline;
  gap: var(--space-5);
}

.kpi-item {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}

.kpi-label {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.kpi-value {
  font-size: var(--text-sm);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.chart-area {
  position: relative;
  padding: var(--space-4) var(--space-5) var(--space-2);
  cursor: crosshair;
}

.histogram-svg-wrap {
  position: relative;
  height: 250px;
}

.histogram-chart {
  width: 100%;
  height: 100%;
  display: block;
}

.grid-line {
  stroke: var(--border-light);
  stroke-width: 1;
  stroke-dasharray: 3 5;
  opacity: 0.7;
}

.grid-tick-text {
  font-size: 10px;
  fill: var(--text-muted);
  font-family: var(--font-sans);
  font-variant-numeric: tabular-nums;
}

.hist-bar {
  fill: color-mix(in srgb, var(--lumi-brand) 72%, transparent);
  transition: fill var(--transition-fast);
}

.hist-bar.active {
  fill: var(--lumi-brand);
}

.axis-baseline {
  stroke: var(--border);
  stroke-width: 1;
}

.chart-axis-label {
  font-size: 10px;
  fill: var(--text-muted);
  font-family: var(--font-sans);
  font-variant-numeric: tabular-nums;
  transition: fill var(--transition-fast);
  pointer-events: none;
}

.chart-axis-label.axis-label--active {
  fill: var(--text-primary);
  font-weight: var(--font-semibold);
}

.chart-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: var(--text-sm);
}

/* ── 悬浮提示框 ── */

.chart-tooltip {
  position: absolute;
  transform: translate(-50%, calc(-100% - 12px));
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--space-2) var(--space-3);
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  pointer-events: none;
  z-index: 10;
  min-width: 90px;
  transition: opacity var(--transition-fast);
}

.ct-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ct-label {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  font-weight: var(--font-medium);
}

.ct-value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.ct-num {
  font-size: var(--text-base);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.ct-num-sm {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.ct-unit {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

/* ── 模型排行（单色条） ── */

.provider-list {
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--border-light);
}

.provider-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-5);
  transition: background-color var(--transition-fast);
}

.provider-row:hover {
  background: var(--bg-secondary);
}

.provider-rank {
  width: 22px;
  text-align: center;
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.provider-rank--first {
  color: var(--text-primary);
  font-weight: var(--font-bold);
}

.provider-name-wrap {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  width: 90px;
  flex-shrink: 0;
}

.provider-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.provider-name {
  font-weight: var(--font-medium);
}

.provider-bar-bg {
  flex: 1;
  height: 4px;
  border-radius: var(--radius-xs);
  background: var(--border-light);
  overflow: hidden;
}

.provider-bar-fill {
  height: 100%;
  border-radius: var(--radius-xs);
  background: var(--lumi-brand);
  transition: width var(--transition-slow);
}

.provider-stats {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 130px;
  flex-shrink: 0;
}

.provider-requests,
.provider-tokens {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.provider-divider {
  width: 1px;
  height: 10px;
  background: var(--border);
}

.provider-trend {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  color: var(--text-muted);
}

/* ── 智能体选择 ── */

.agent-selector {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: 3px var(--space-2);
  border-radius: var(--radius-sm);
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-muted);
  font-size: var(--text-xs);
  transition: border-color var(--transition-fast);
}

.agent-selector:focus-within {
  border-color: var(--lumi-brand);
}

.agent-select {
  background: transparent;
  border: none;
  color: var(--text);
  font-size: var(--text-xs);
  outline: none;
  cursor: pointer;
}

/* ── 记忆统计 ── */

.memory-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3) var(--space-4);
  margin-bottom: var(--space-4);
}

.memory-stat-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-left: var(--space-3);
  border-left: 1px solid var(--border-light);
}

.memory-stat-icon {
  color: var(--text-muted);
  margin-bottom: var(--space-1);
}

.memory-stat-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.memory-stat-value {
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.donut-section {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  margin-bottom: var(--space-4);
}

.donut-wrap {
  position: relative;
  width: 130px;
  height: 130px;
  flex-shrink: 0;
}

.donut-chart {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.donut-anim {
  animation: donutGrow 0.8s var(--ease-out-expo) both;
}

@keyframes donutGrow {
  from {
    stroke-dasharray: 0 251.2;
  }
}

.donut-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.dc-label {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.donut-legend {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.legend-dot {
  width: var(--space-2);
  height: var(--space-2);
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.legend-text {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.legend-count {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-left: auto;
}

.health-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.health-label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}

.health-value {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.health-bar-bg {
  height: 4px;
  border-radius: var(--radius-xs);
  background: var(--border-light);
  overflow: hidden;
}

.health-bar-fill {
  height: 100%;
  border-radius: var(--radius-xs);
  background: var(--lumi-brand);
  transition: width var(--transition-slow);
}

/* ── 上下文监控（单色细条） ── */

.context-metrics {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.context-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  animation: lumi-content-fade-up var(--duration-slow) var(--ease-out-expo) both;
}

.context-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.context-label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.context-value {
  font-size: var(--text-sm);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.context-bar-bg {
  height: 4px;
  border-radius: var(--radius-xs);
  background: var(--border-light);
  overflow: hidden;
}

.context-bar-fill {
  height: 100%;
  border-radius: var(--radius-xs);
  background: var(--lumi-brand);
  transition: width var(--transition-slow);
}

/* ── 最近活动 ── */

.activity-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-height: 360px;
  overflow-y: auto;
  padding-right: var(--space-1);
}

.activity-item {
  display: flex;
  gap: var(--space-3);
  animation: lumi-content-fade-up var(--duration-slow) var(--ease-out-expo) both;
  padding: var(--space-2) 0;
}

.activity-dot-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: var(--space-4);
  flex-shrink: 0;
  padding-top: var(--space-1);
}

.activity-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
  background: var(--lumi-brand);
}

.activity-line {
  width: 1px;
  flex: 1;
  background: var(--divider-vertical);
  margin-top: var(--space-1);
}

.activity-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.activity-top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
}

.activity-action {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.activity-time {
  font-size: var(--text-xs);
  color: var(--text-muted);
  flex-shrink: 0;
}

.activity-detail {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-empty {
  padding: var(--space-6) 0;
  text-align: center;
  font-size: var(--text-sm);
  color: var(--text-muted);
}

@media (max-width: 1200px) {
  .main-content {
    flex-direction: column;
  }

  .right-col {
    width: 100%;
  }
}

@media (max-width: 1100px) {
  .summary-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    row-gap: var(--space-4);
  }

  .summary-item:nth-child(4),
  .summary-item:nth-child(5) {
    border-left: none;
    padding-left: 0;
  }
}

@media (max-width: 900px) {
  .summary-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
