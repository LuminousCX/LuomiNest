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
  TrendingUp,
  TrendingDown,
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
} from 'lucide-vue-next'
import LumiCard from '../../components/common/LumiCard.vue'
import LumiButton from '../../components/common/LumiButton.vue'
import { useMemoryStore } from '../../stores/memory'
import { useStatsStore } from '../../stores/stats'
import { useModelStore } from '../../stores/model'
import { formatTime } from '../../utils/format'
import { generateAreaChartPaths, calculateTrend, aggregateByDay } from '../../utils/chart'

const memoryStore = useMemoryStore()
const statsStore = useStatsStore()
const modelStore = useModelStore()
const { t } = useI18n()

const period = ref<7 | 30 | 90>(7)

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

const periodData = computed(() => {
  const req = statsStore.totalRequests
  const tok = statsStore.totalTokens
  const conv = statsStore.totalConversations
  const msg = statsStore.totalMessages
  let tokStr = '0'
  if (tok >= 1_000_000) tokStr = (tok / 1_000_000).toFixed(2) + 'M'
  else if (tok >= 1_000) tokStr = (tok / 1_000).toFixed(1) + 'K'
  else tokStr = String(tok)
  const ctxPct = msg > 0 ? Math.min(100, Math.round((msg / (conv || 1)) * 5)) : 0
  return { requests: req, tokens: tokStr, contextPct: ctxPct, conversations: conv, messages: msg }
})

const apiProviders = computed(() => {
  const providers = statsStore.byProvider
  if (!providers.length) return []
  const maxReq = Math.max(...providers.map(p => p.requests), 1)
  return providers.map(p => {
    const tok = p.total_tokens
    let tokStr = '0'
    if (tok >= 1_000_000) tokStr = (tok / 1_000_000).toFixed(1) + 'M'
    else if (tok >= 1_000) tokStr = (tok / 1_000).toFixed(1) + 'K'
    else tokStr = String(tok)
    return {
      name: p.name,
      requests: p.requests,
      tokens: tokStr,
      total_tokens: p.total_tokens,
      cost: 0,
      trend: 'up' as const,
      pct: Math.round((p.requests / maxReq) * 100),
    }
  })
})

const contextMetrics = computed(() => {
  const conv = statsStore.totalConversations
  const msg = statsStore.totalMessages
  const tok = statsStore.totalTokens
  const windowSize = modelStore.modelConfig.contextWindowSize || 32768
  const totalCtx = tok
  return [
    { label: t('stats.ctx.totalUsage'), value: totalCtx, unit: 'tokens', max: Math.max(totalCtx, windowSize), color: 'var(--lumi-brand)' },
    { label: t('stats.ctx.windowRate'), value: windowSize > 0 ? Math.min(100, Math.round((totalCtx / windowSize) * 100)) : 0, unit: '%', max: 100, color: 'var(--lumi-success)' },
    { label: t('stats.ctx.turns'), value: msg, unit: t('stats.ctx.unitTurns'), max: Math.max(msg * 2, 100), color: 'var(--lumi-warning)' },
    { label: t('stats.ctx.conversations'), value: conv, unit: t('stats.ctx.unitCount'), max: Math.max(conv * 2, 50), color: 'var(--lumi-info)' },
  ]
})

const chartData = computed(() => {
  return aggregateByDay(statsStore.byDay, 7)
})

const chartWrapRef = ref<HTMLElement | null>(null)
const chartWidth = ref(600)
const chartHeight = ref(260)
let resizeObserver: ResizeObserver | null = null

const requestChartPaths = computed(() => {
  const values = chartData.value.map(d => d.value)
  return generateAreaChartPaths(values, {
    width: chartWidth.value,
    height: chartHeight.value,
    padding: { top: 28, bottom: 32, left: 40, right: 24 },
    zeroBaseline: true,
  })
})

const topStatCards = computed(() => [
  {
    key: 'api',
    label: t('stats.card.api.label'),
    sub: t('stats.card.api.sub'),
    value: periodData.value.requests.toLocaleString(),
    color: 'var(--lumi-brand)',
  },
  {
    key: 'token',
    label: t('stats.card.token.label'),
    sub: t('stats.card.token.sub'),
    value: periodData.value.tokens,
    color: 'var(--lumi-success)',
  },
  {
    key: 'memory',
    label: t('stats.card.memory.label'),
    sub: t('stats.card.memory.sub'),
    value: memoryLineCount.value.toLocaleString(),
    color: 'var(--lumi-warning)',
  },
  {
    key: 'context',
    label: t('stats.card.context.label'),
    sub: t('stats.card.context.sub'),
    value: periodData.value.conversations.toLocaleString(),
    color: 'var(--lumi-info)',
  },
])

const requestTrend = computed(() => {
  const current = statsStore.usageComparison?.current?.total_requests ?? 0
  const previous = statsStore.usageComparison?.previous?.total_requests ?? 0
  return calculateTrend(current, previous)
})

const tokenTrend = computed(() => {
  const current = statsStore.usageComparison?.current?.total_tokens ?? 0
  const previous = statsStore.usageComparison?.previous?.total_tokens ?? 0
  return calculateTrend(current, previous)
})

const memorySegments = computed(() => {
  const summaryValue = hasSummary.value ? 1 : 0
  const values = [
    { label: t('stats.memory.longTerm'), value: memoryLineCount.value, display: t('stats.memory.lineUnit', { n: memoryLineCount.value }), color: 'var(--lumi-brand)' },
    { label: t('stats.memory.distilledLabel'), value: summaryValue, display: hasSummary.value ? t('stats.memory.distilled') : t('stats.memory.notDistilled'), color: 'var(--lumi-success)' },
    { label: t('stats.memory.daily'), value: dailyCount.value, display: t('stats.memory.dayUnit', { n: dailyCount.value }), color: 'var(--lumi-warning)' },
  ]
  const total = values.reduce((sum, item) => sum + item.value, 0) || 1
  const circumference = 251.2
  let offset = 0
  return values.map(item => {
    const len = (item.value / total) * circumference
    const segment = { ...item, len, offset }
    offset -= len
    return segment
  })
})

const miniGridMetrics = computed(() => {
  const providers = apiProviders.value.slice(0, 2)
  const contexts = contextMetrics.value.slice(0, 2)
  const metrics: {
    label: string
    value: number | string
    unit: string
    change: number
    trend: 'up' | 'down'
    color: string
    pct: number
  }[] = []

  providers.forEach((p, idx) => {
    const trendValue = idx === 0 ? requestTrend.value : tokenTrend.value
    metrics.push({
      label: p.name,
      value: p.requests,
      unit: t('stats.unitTimes'),
      change: Math.abs(trendValue),
      trend: trendValue >= 0 ? 'up' : 'down',
      color: idx === 0 ? 'var(--lumi-primary)' : 'var(--lumi-success)',
      pct: p.pct,
    })
  })

  contexts.forEach((m, idx) => {
    const trendValue = idx === 0 ? tokenTrend.value : requestTrend.value
    metrics.push({
      label: m.label,
      value: m.value,
      unit: m.unit,
      change: Math.abs(trendValue),
      trend: trendValue >= 0 ? 'up' : 'down',
      color: idx === 0 ? 'var(--lumi-warning)' : 'var(--lumi-info)',
      pct: Math.round((m.value / m.max) * 100),
    })
  })

  return metrics
})

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

const hoveredPoint = ref<{ x: number; y: number; value: number; label: string; index: number } | null>(null)

const tooltipStyle = computed(() => {
  if (!hoveredPoint.value) return {}
  const { x, y } = hoveredPoint.value
  const isNearTop = y < 75
  const isNearLeft = x < 75
  const isNearRight = x > chartWidth.value - 75

  let transformX = '-50%'
  if (isNearLeft) transformX = '0%'
  else if (isNearRight) transformX = '-100%'

  let transformY = 'calc(-100% - 14px)'
  if (isNearTop) {
    transformY = '14px'
  }

  return {
    left: `${x}px`,
    top: `${y}px`,
    transform: `translate(${transformX}, ${transformY})`,
  }
})

function onChartMove(event: MouseEvent) {
  if (!chartWrapRef.value) return
  const rect = chartWrapRef.value.getBoundingClientRect()
  const mouseX = Math.max(0, Math.min(chartWidth.value, event.clientX - rect.left))
  const points = requestChartPaths.value.points
  if (!points.length) return

  let nearest = 0
  let minDistance = Infinity
  points.forEach((p, i) => {
    const distance = Math.abs(p.x - mouseX)
    if (distance < minDistance) {
      minDistance = distance
      nearest = i
    }
  })

  const point = points[nearest]
  hoveredPoint.value = {
    x: point.x,
    y: point.y,
    value: point.value,
    label: chartData.value[nearest]?.label ?? '',
    index: nearest,
  }
}

function onChartLeave() {
  hoveredPoint.value = null
}

async function onAgentChange() {
  await memoryStore.switchAgent(selectedAgentId.value)
}

async function handleRefresh() {
  isRefreshing.value = true
  await memoryStore.switchAgent(selectedAgentId.value)
  await statsStore.fetchAll(period.value)
  setTimeout(() => { isRefreshing.value = false }, 600)
}

async function loadData() {
  await Promise.all([
    memoryStore.fetchMemoryAgents(),
    statsStore.fetchAll(period.value),
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

onMounted(() => {
  loadData()
  timeInterval = setInterval(() => { currentTime.value = new Date() }, 1000)

  if (chartWrapRef.value) {
    updateChartDimensions()
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect
        if (width > 0) {
          chartWidth.value = Math.round(width)
        }
        if (height > 0) {
          chartHeight.value = Math.round(height)
        }
      }
    })
    resizeObserver.observe(chartWrapRef.value)
  }
})

onUnmounted(() => {
  if (timeInterval) clearInterval(timeInterval)
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
})

watch(period, () => { loadData() })
</script>

<template>
  <div class="data-stats-view">
    <div class="stats-header animate-fade-in">
      <div class="stats-header__text">
        <h1 class="stats-title">{{ t('stats.title') }}</h1>
        <p class="stats-desc">{{ greeting }}，LuminousChenXi · {{ formattedDate }}</p>
      </div>
      <div class="stats-header__actions">
        <div class="period-tabs">
          <button :class="['period-btn', { active: period === 7 }]" @click="period = 7">{{ t('stats.days', { n: 7 }) }}</button>
          <button :class="['period-btn', { active: period === 30 }]" @click="period = 30">{{ t('stats.days', { n: 30 }) }}</button>
          <button :class="['period-btn', { active: period === 90 }]" @click="period = 90">{{ t('stats.days', { n: 90 }) }}</button>
        </div>
        <LumiButton variant="ghost" size="sm" icon-only :aria-label="t('stats.refresh')" @click="handleRefresh">
          <template #icon><RefreshCw :size="14" :class="{ 'spin-animation': isRefreshing }" /></template>
        </LumiButton>
      </div>
    </div>

    <div class="top-stats-row">
      <LumiCard
        v-for="(stat, idx) in topStatCards"
        :key="stat.key"
        class="top-stat-card"
        :style="{
          animationDelay: `${(idx + 1) * 0.05}s`,
          '--card-accent': stat.color,
        }"
        padding="md"
        hoverable
      >
        <div class="top-stat-card__inner">
          <div class="top-stat-card__left">
            <span class="top-stat-title">{{ stat.label }}</span>
            <span class="top-stat-sub">
              <span class="top-stat-sub-dot"></span>
              {{ stat.sub }}
            </span>
          </div>
          <div class="top-stat-card__right">
            <span class="top-stat-value">{{ stat.value }}</span>
          </div>
        </div>
      </LumiCard>
    </div>

    <div class="main-content">
      <div class="left-col">
        <LumiCard class="section-card chart-card" :style="{ animationDelay: '0.10s' }" padding="none">
          <template #title>
            <div class="chart-header-left">
              <div class="chart-title-icon-badge">
                <BarChart3 :size="16" />
              </div>
              <div class="chart-title-text">
                <span class="chart-title-main">{{ t('stats.chartTitle') }}</span>
                <span class="chart-title-sub">周期调用趋势与流量监控</span>
              </div>
            </div>
          </template>
          <template #header>
            <div class="chart-header-kpis">
              <div class="chart-kpi-chip primary">
                <span class="kpi-chip-label">{{ t('stats.card.api.label') }}</span>
                <span class="kpi-chip-val">{{ periodData.requests.toLocaleString() }}</span>
                <span :class="['kpi-chip-trend', requestTrend >= 0 ? 'up' : 'down']">
                  <component :is="requestTrend >= 0 ? ArrowUpRight : ArrowDownRight" :size="12" />
                  {{ Math.abs(requestTrend) }}%
                </span>
              </div>
              <div class="chart-kpi-chip success">
                <span class="kpi-chip-label">{{ t('stats.card.token.label') }}</span>
                <span class="kpi-chip-val">{{ periodData.tokens }}</span>
                <span :class="['kpi-chip-trend', tokenTrend >= 0 ? 'up' : 'down']">
                  <component :is="tokenTrend >= 0 ? ArrowUpRight : ArrowDownRight" :size="12" />
                  {{ Math.abs(tokenTrend) }}%
                </span>
              </div>
            </div>
          </template>

          <div class="chart-area" @mousemove="onChartMove" @mouseleave="onChartLeave">
            <div ref="chartWrapRef" class="big-chart-svg-wrap">
              <svg
                :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
                class="area-chart"
              >
                <defs>
                  <linearGradient id="chartGrad1" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="var(--lumi-brand)" stop-opacity="0.30" />
                    <stop offset="60%" stop-color="var(--lumi-brand)" stop-opacity="0.08" />
                    <stop offset="100%" stop-color="var(--lumi-brand)" stop-opacity="0" />
                  </linearGradient>
                  <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stop-color="var(--lumi-brand-soft)" />
                    <stop offset="100%" stop-color="var(--lumi-brand)" />
                  </linearGradient>
                  <filter id="chartLineGlow" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="var(--lumi-brand)" flood-opacity="0.35" />
                  </filter>
                </defs>

                <!-- Y 轴水平网格参考线及刻度 -->
                <g class="chart-grid">
                  <g v-for="tick in requestChartPaths.ticks" :key="'tick-' + tick.value">
                    <line
                      :x1="40"
                      :y1="tick.y"
                      :x2="chartWidth - 20"
                      :y2="tick.y"
                      class="grid-line"
                    />
                    <text
                      :x="32"
                      :y="tick.y + 4"
                      text-anchor="end"
                      class="grid-tick-text"
                    >
                      {{ tick.label }}
                    </text>
                  </g>
                </g>

                <!-- 面积填充与曲线描边 -->
                <path
                  :d="requestChartPaths.areaPath"
                  fill="url(#chartGrad1)"
                  class="chart-area-fill"
                />
                <path
                  :d="requestChartPaths.linePath"
                  fill="none"
                  stroke="url(#lineGrad)"
                  stroke-width="3"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  filter="url(#chartLineGlow)"
                  class="chart-line"
                />

                <!-- 悬浮垂直指示参考线 -->
                <line
                  v-if="hoveredPoint"
                  class="chart-hover-line"
                  :x1="hoveredPoint.x"
                  y1="16"
                  :x2="hoveredPoint.x"
                  :y2="chartHeight - 30"
                />

                <!-- 静态数据点 -->
                <circle
                  v-for="(p, idx) in requestChartPaths.points"
                  :key="'d' + idx"
                  :cx="p.x"
                  :cy="p.y"
                  r="3.5"
                  class="chart-point"
                  :class="{ active: hoveredPoint?.index === idx }"
                />

                <!-- 悬浮激活点光环与中心实心圆点 -->
                <g v-if="hoveredPoint">
                  <circle
                    :cx="hoveredPoint.x"
                    :cy="hoveredPoint.y"
                    r="8"
                    class="chart-point-ring"
                  />
                  <circle
                    :cx="hoveredPoint.x"
                    :cy="hoveredPoint.y"
                    r="4"
                    class="chart-point-active-center"
                  />
                </g>

                <!-- X 轴日期刻度标签（与数据点 X 坐标绝对对齐） -->
                <g class="chart-x-axis-svg">
                  <text
                    v-for="(item, idx) in chartData"
                    :key="'x-lbl-' + idx"
                    :x="requestChartPaths.points[idx]?.x ?? 0"
                    :y="chartHeight - 10"
                    text-anchor="middle"
                    class="chart-axis-label"
                    :class="{ 'axis-label--active': hoveredPoint?.index === idx }"
                  >
                    {{ item.label }}
                  </text>
                </g>
              </svg>

              <!-- 悬浮提示框 (Tooltip) -->
              <div
                v-if="hoveredPoint"
                class="chart-tooltip"
                :class="{ 'chart-tooltip--bottom': hoveredPoint.y < 75 }"
                :style="tooltipStyle"
              >
                <div class="ct-header">
                  <span class="ct-dot"></span>
                  <span class="ct-label">{{ hoveredPoint.label }}</span>
                </div>
                <div class="ct-value-row">
                  <span class="ct-num">{{ hoveredPoint.value.toLocaleString() }}</span>
                  <span class="ct-unit">{{ t('stats.unitTimes') }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="usage-mini-grid">
            <div
              v-for="m in miniGridMetrics"
              :key="m.label"
              class="usage-mini-item"
              :style="{ '--umi-accent': m.color }"
            >
              <div class="umi-top">
                <span class="umi-label">{{ m.label }}</span>
                <span :class="['umi-change-badge', m.trend]">
                  <component :is="m.trend === 'up' ? ArrowUpRight : ArrowDownRight" :size="12" />
                  {{ Math.abs(m.change) }}%
                </span>
              </div>
              <div class="umi-mid">
                <span class="umi-value">{{ m.value }}</span>
                <span class="umi-unit">{{ m.unit }}</span>
              </div>
              <div class="umi-bar-track">
                <div
                  class="umi-bar-fill"
                  :style="{
                    width: `${Math.min(100, Math.max(0, m.pct))}%`,
                    background: `linear-gradient(90deg, ${m.color}, color-mix(in srgb, ${m.color} 60%, var(--surface)))`
                  }"
                />
              </div>
            </div>
          </div>

          <div class="provider-list">
            <div
              v-for="(p, idx) in apiProviders"
              :key="p.name"
              class="provider-row"
              :style="{ animationDelay: (0.14 + idx * 0.04) + 's' }"
            >
              <span :class="['provider-rank', { 'provider-rank--first': idx === 0 }]">{{ idx + 1 }}</span>
              <div class="provider-name-wrap">
                <Server :size="14" class="provider-icon" />
                <span class="provider-name">{{ p.name }}</span>
              </div>
              <div class="provider-bar-bg">
                <div class="provider-bar-fill" :style="{ width: p.pct + '%' }"></div>
              </div>
              <div class="provider-stats">
                <span class="provider-requests">{{ t('stats.countTimes', { n: p.requests }) }}</span>
                <span class="provider-divider"></span>
                <span class="provider-tokens">{{ p.tokens }} tokens</span>
              </div>
              <div :class="['provider-trend', p.trend]">
                <TrendingUp v-if="p.trend === 'up'" :size="12" />
                <TrendingDown v-else :size="12" />
              </div>
            </div>
          </div>
        </LumiCard>

        <LumiCard class="section-card" :style="{ animationDelay: '0.18s' }" padding="md">
          <template #title>
            <Brain :size="16" />
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
                <span class="dc-value">{{ memoryLineCount }}</span>
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
            <div class="health-header">
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
        <LumiCard class="section-card" :style="{ animationDelay: '0.14s' }" padding="md">
          <template #title>
            <Layers :size="16" />
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
              :style="{ animationDelay: (0.18 + idx * 0.04) + 's', '--ctx-accent': m.color }"
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

        <LumiCard class="section-card" :style="{ animationDelay: '0.22s' }" padding="md">
          <template #title>
            <Clock :size="16" />
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
                <span :class="['activity-dot', a.type]"></span>
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
  padding-bottom: var(--space-4);
  animation: lumi-content-fade-up var(--duration-enter) var(--ease-out-expo) both;
}

.stats-header__text {
  display: flex;
  flex-direction: column;
}

.stats-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  line-height: 1.2;
}

.stats-desc {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.stats-header__actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.period-tabs {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-1);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.period-btn {
  padding: var(--space-1) var(--space-4);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  border: none;
  background: transparent;
}

.period-btn.active {
  background: var(--surface);
  color: var(--lumi-brand);
  box-shadow: var(--shadow-xs);
}

.period-btn:hover:not(.active) {
  color: var(--text-secondary);
}

.top-stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}

.top-stat-card {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-lg);
  background: color-mix(in srgb, var(--surface) 88%, transparent);
  border: 1px solid var(--border-light);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  transition: transform var(--transition-fast), box-shadow var(--transition-fast), border-color var(--transition-fast);
  animation: lumi-content-fade-up var(--duration-enter) var(--ease-out-expo) both;
}

.top-stat-card::before {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  width: 130px;
  height: 130px;
  background: radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--card-accent) 14%, transparent) 0%, transparent 70%);
  pointer-events: none;
  border-radius: inherit;
}

.top-stat-card:hover {
  transform: translateY(-3px);
  border-color: color-mix(in srgb, var(--card-accent) 45%, var(--border-light));
  box-shadow: 0 12px 28px -6px color-mix(in srgb, var(--card-accent) 22%, transparent);
}

.top-stat-card__inner {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.top-stat-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.top-stat-title {
  font-size: 1.125rem;
  font-weight: var(--font-bold);
  color: var(--text-primary);
  letter-spacing: -0.01em;
  line-height: 1.3;
}

.top-stat-icon-badge {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--card-accent) 12%, transparent);
  color: var(--card-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid color-mix(in srgb, var(--card-accent) 20%, transparent);
  transition: transform var(--transition-fast);
}

.top-stat-card:hover .top-stat-icon-badge {
  transform: scale(1.08);
}

.top-stat-card__value-wrap {
  display: flex;
  align-items: baseline;
  margin-top: 2px;
}

.top-stat-value {
  font-size: 2.35rem;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}

.top-stat-card__footer {
  display: flex;
  align-items: center;
  margin-top: 2px;
}

.top-stat-sub {
  font-size: 0.8125rem;
  color: var(--text-muted);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.top-stat-sub-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--card-accent);
  opacity: 0.85;
  flex-shrink: 0;
}

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

.chart-card :deep(.lumi-card__body) {
  padding: 0;
}

.chart-header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.chart-title-icon-badge {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--lumi-brand) 12%, transparent);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.chart-title-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.chart-title-main {
  font-size: var(--text-base);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  line-height: 1.2;
}

.chart-title-sub {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.chart-header-kpis {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.chart-kpi-chip {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 4px var(--space-3);
  border-radius: var(--radius-full);
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  backdrop-filter: blur(8px);
}

.kpi-chip-label {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.kpi-chip-val {
  font-size: var(--text-sm);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.kpi-chip-trend {
  display: inline-flex;
  align-items: center;
  gap: 1px;
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
}

.kpi-chip-trend.up { color: var(--lumi-success); }
.kpi-chip-trend.down { color: var(--lumi-danger); }

.section-icon-muted {
  color: var(--text-muted);
}

.agent-selector {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: 3px var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--surface);
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

.chart-area {
  position: relative;
  padding: var(--space-4) var(--space-5) var(--space-3);
  cursor: crosshair;
}

.big-chart-svg-wrap {
  position: relative;
  height: 270px;
  border-radius: var(--radius-lg);
  background: radial-gradient(circle at 50% 0%, color-mix(in srgb, var(--lumi-brand) 9%, transparent) 0%, transparent 75%), var(--bg-secondary);
  overflow: hidden;
  border: 1px solid var(--border-light);
}

.area-chart {
  width: 100%;
  height: 100%;
  display: block;
}

.grid-line {
  stroke: var(--border-light);
  stroke-width: 1;
  stroke-dasharray: 4 4;
  opacity: 0.8;
}

.grid-tick-text {
  font-size: 10px;
  fill: var(--text-muted);
  font-family: var(--font-sans);
  font-variant-numeric: tabular-nums;
}

.chart-area-fill {
  opacity: 0;
  animation: fadeAreaIn var(--duration-slow) var(--ease-out-expo) var(--duration-normal) both;
}

@keyframes fadeAreaIn { to { opacity: 1; } }

.chart-line {
  stroke-dasharray: 1200;
  stroke-dashoffset: 1200;
  animation: drawLine 1.2s var(--ease-out-expo) var(--duration-fast) both;
}

@keyframes drawLine { to { stroke-dashoffset: 0; } }

.chart-point {
  fill: var(--surface);
  stroke: var(--lumi-brand);
  stroke-width: 2.5;
  opacity: 0.9;
  transform-box: fill-box;
  transform-origin: center;
  transition: opacity var(--transition-fast), transform var(--transition-fast);
  animation: dotIn var(--duration-fast) var(--ease-out-expo) var(--duration-slow) both;
  pointer-events: none;
}

.chart-point.active {
  transform: scale(1.4);
  fill: var(--lumi-brand);
}

.chart-point-ring {
  fill: none;
  stroke: var(--lumi-brand);
  stroke-width: 1.5;
  opacity: 0.4;
  pointer-events: none;
  animation: ringPulse 1.6s ease-out infinite;
}

.chart-point-active-center {
  fill: var(--lumi-brand);
  pointer-events: none;
}

@keyframes ringPulse {
  0% { r: 6px; opacity: 0.7; }
  100% { r: 16px; opacity: 0; }
}

@keyframes dotIn { to { opacity: 0.9; } }

.chart-hover-line {
  stroke: var(--lumi-brand);
  stroke-width: 1.5;
  stroke-dasharray: 4 4;
  opacity: 0.6;
  pointer-events: none;
}

.chart-axis-label {
  font-size: 11px;
  fill: var(--text-muted);
  font-family: var(--font-sans);
  transition: fill var(--transition-fast), font-weight var(--transition-fast);
  pointer-events: none;
}

.chart-axis-label.axis-label--active {
  fill: var(--lumi-brand);
  font-weight: var(--font-bold);
}

.chart-tooltip {
  position: absolute;
  transform: translate(-50%, calc(-100% - 14px));
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

.ct-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--lumi-brand);
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

.ct-unit {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.usage-mini-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--border-light);
  background: color-mix(in srgb, var(--surface) 40%, transparent);
}

.usage-mini-item {
  position: relative;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-xs);
  transition: transform var(--transition-fast), border-color var(--transition-fast), box-shadow var(--transition-fast);
  overflow: hidden;
}

.usage-mini-item:hover {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--umi-accent, var(--lumi-brand)) 40%, var(--border-light));
  box-shadow: 0 6px 16px -4px color-mix(in srgb, var(--umi-accent, var(--lumi-brand)) 15%, transparent);
}

.umi-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-1);
}

.umi-label {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}

.umi-change-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
  padding: 2px 6px;
  border-radius: var(--radius-full);
}

.umi-change-badge.up {
  background: color-mix(in srgb, var(--lumi-success) 12%, transparent);
  color: var(--lumi-success);
  border: 1px solid color-mix(in srgb, var(--lumi-success) 24%, transparent);
}

.umi-change-badge.down {
  background: color-mix(in srgb, var(--lumi-danger) 12%, transparent);
  color: var(--lumi-danger);
  border: 1px solid color-mix(in srgb, var(--lumi-danger) 24%, transparent);
}

.umi-mid {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: var(--space-2);
}

.umi-value {
  font-size: 1.35rem;
  font-weight: var(--font-bold);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.umi-unit {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: var(--font-normal);
}

.umi-bar-track {
  height: 5px;
  background: color-mix(in srgb, var(--border) 60%, transparent);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.umi-bar-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width var(--duration-enter) var(--ease-out-expo);
}

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
  animation: lumi-content-fade-up var(--duration-slow) var(--ease-out-expo) both;
  transition: background-color var(--transition-fast);
}

.provider-row:hover {
  background: var(--bg-secondary);
}

.provider-row:last-child {
  border-bottom: none;
}

.provider-rank {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-size: var(--text-xs);
  font-weight: var(--font-bold);
  color: var(--text-muted);
  flex-shrink: 0;
  border-radius: var(--radius-xs);
  background: color-mix(in srgb, var(--border) 40%, transparent);
}

.provider-rank--first {
  color: var(--lumi-brand);
  background: color-mix(in srgb, var(--lumi-brand) 16%, transparent);
  border: 1px solid color-mix(in srgb, var(--lumi-brand) 28%, transparent);
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
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.provider-bar-bg {
  flex: 1;
  height: 6px;
  border-radius: var(--radius-xs);
  background: var(--bg-secondary);
  overflow: hidden;
}

.provider-bar-fill {
  height: 100%;
  border-radius: var(--radius-xs);
  background: linear-gradient(90deg, var(--lumi-brand-soft), var(--lumi-brand));
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
}

.provider-trend.up {
  color: var(--lumi-success);
}

.provider-trend.down {
  color: var(--lumi-accent);
}

.memory-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.memory-stat-item {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: transform var(--transition-fast);
}

.memory-stat-item:hover {
  transform: translateY(-2px);
}

.memory-stat-icon {
  color: var(--lumi-brand);
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
  padding: var(--space-3);
  border-radius: var(--radius-lg);
  background: var(--bg-secondary);
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

.dc-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
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

.health-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.health-label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}

.health-value {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--lumi-brand);
}

.health-bar-bg {
  height: 6px;
  border-radius: var(--radius-xs);
  background: var(--bg-secondary);
  overflow: hidden;
}

.health-bar-fill {
  height: 100%;
  border-radius: var(--radius-xs);
  background: linear-gradient(90deg, var(--lumi-brand-soft), var(--lumi-brand));
  transition: width var(--transition-slow);
}

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
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.context-label::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--ctx-accent, var(--lumi-brand));
}

.context-value {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.context-bar-bg {
  height: 6px;
  border-radius: var(--radius-xs);
  background: var(--bg-secondary);
  overflow: hidden;
}

.context-bar-fill {
  height: 100%;
  border-radius: var(--radius-xs);
  background: linear-gradient(90deg, color-mix(in srgb, var(--ctx-accent, var(--lumi-brand)) 70%, transparent), var(--ctx-accent, var(--lumi-brand)));
  transition: width var(--transition-slow);
}

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
  border: 2px solid var(--surface);
  box-shadow: 0 0 0 1px var(--border);
}

.activity-dot.api {
  background: var(--lumi-brand);
  box-shadow: 0 0 0 1px var(--lumi-brand-border);
}

.activity-dot.memory {
  background: var(--lumi-success);
}

.activity-dot.context {
  background: var(--lumi-warning);
}

.activity-dot.system {
  background: var(--lumi-accent);
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

@media (max-width: 900px) {
  .top-stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .top-stats-row {
    grid-template-columns: 1fr;
  }
  .chart-header-kpis {
    display: none;
  }
}
</style>
