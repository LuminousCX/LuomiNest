<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
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

const period = ref<7 | 30 | 90>(7)

const currentTime = ref(new Date())
let timeInterval: ReturnType<typeof setInterval>

const greeting = computed(() => {
  const hour = currentTime.value.getHours()
  if (hour < 6 || hour >= 23) return '夜深了'
  if (hour < 9) return '早上好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const formattedDate = computed(() => {
  const d = currentTime.value
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ${weekdays[d.getDay()]}`
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
    { label: '累计上下文使用量', value: totalCtx, unit: 'tokens', max: Math.max(totalCtx, windowSize), color: 'var(--lumi-brand)' },
    { label: '窗口使用率', value: windowSize > 0 ? Math.min(100, Math.round((totalCtx / windowSize) * 100)) : 0, unit: '%', max: 100, color: 'var(--lumi-success)' },
    { label: '对话轮次', value: msg, unit: '轮', max: Math.max(msg * 2, 100), color: 'var(--lumi-warning)' },
    { label: '对话数', value: conv, unit: '个', max: Math.max(conv * 2, 50), color: 'var(--lumi-info)' },
  ]
})

const chartData = computed(() => {
  return aggregateByDay(statsStore.byDay, 7)
})

const requestChartPaths = computed(() => {
  const values = chartData.value.map(d => d.value)
  return generateAreaChartPaths(values, { width: 400, height: 160 })
})

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
    { label: '长期记忆', value: memoryLineCount.value, display: `${memoryLineCount.value} 行`, color: 'var(--lumi-brand)' },
    { label: '蒸馏摘要', value: summaryValue, display: hasSummary.value ? '已蒸馏' : '未蒸馏', color: 'var(--lumi-success)' },
    { label: '日常记录', value: dailyCount.value, display: `${dailyCount.value} 天`, color: 'var(--lumi-warning)' },
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
      unit: '次',
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
      action: 'API 调用',
      detail: `${r.provider} / ${r.model}${tokStr}`,
      type: 'api' as const,
    }
  })
})

const isRefreshing = ref(false)

const selectedAgentId = ref<string | null>(null)

const hoveredPoint = ref<{ x: number; y: number; value: number; label: string; index: number } | null>(null)

function onChartMove(event: MouseEvent) {
  const wrap = event.currentTarget as HTMLElement
  const rect = wrap.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width))
  const x = ratio * 400
  const points = requestChartPaths.value.points
  if (!points.length) return

  let nearest = 0
  let minDistance = Infinity
  points.forEach((p, i) => {
    const distance = Math.abs(p.x - x)
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

onMounted(() => {
  loadData()
  timeInterval = setInterval(() => { currentTime.value = new Date() }, 1000)
})

onUnmounted(() => {
  if (timeInterval) clearInterval(timeInterval)
})

watch(period, () => { loadData() })
</script>

<template>
  <div class="data-stats-view">
    <div class="stats-header animate-fade-in">
      <div class="stats-header__text">
        <h1 class="stats-title">数据统计</h1>
        <p class="stats-desc">{{ greeting }}，LuminousChenXi · {{ formattedDate }}</p>
      </div>
      <div class="stats-header__actions">
        <div class="period-tabs">
          <button :class="['period-btn', { active: period === 7 }]" @click="period = 7">7天</button>
          <button :class="['period-btn', { active: period === 30 }]" @click="period = 30">30天</button>
          <button :class="['period-btn', { active: period === 90 }]" @click="period = 90">90天</button>
        </div>
        <LumiButton variant="ghost" size="sm" icon-only aria-label="刷新" @click="handleRefresh">
          <template #icon><RefreshCw :size="14" :class="{ 'spin-animation': isRefreshing }" /></template>
        </LumiButton>
      </div>
    </div>

    <div class="top-stats-row">
      <LumiCard
        v-for="(stat, idx) in [
          { key: 'api', label: 'API 请求', sub: '周期调用总量', value: periodData.requests.toLocaleString(), color: 'var(--lumi-brand)' },
          { key: 'token', label: 'Token 消耗', sub: '输入 + 输出', value: periodData.tokens, color: 'var(--lumi-success)' },
          { key: 'memory', label: '记忆行数', sub: '长期记忆条目', value: memoryLineCount, color: 'var(--lumi-warning)' },
          { key: 'context', label: '对话数', sub: '累计会话数量', value: periodData.conversations, color: 'var(--lumi-info)' },
        ]"
        :key="stat.key"
        class="stat-card"
        :style="{ animationDelay: `${(idx + 1) * 0.05}s` }"
        padding="md"
        hoverable
      >
        <div class="stat-card-content">
          <div class="stat-body">
            <span class="stat-label">{{ stat.label }}</span>
            <span class="stat-value">{{ stat.value }}</span>
            <span class="stat-sub">{{ stat.sub }}</span>
          </div>
        </div>
        <div class="stat-card-accent" :style="{ background: stat.color }"></div>
      </LumiCard>
    </div>

    <div class="main-content">
      <div class="left-col">
        <LumiCard class="section-card chart-card" :style="{ animationDelay: '0.10s' }" padding="none">
          <template #title>
            <BarChart3 :size="16" />
            <span>API 用量</span>
          </template>

          <div class="chart-area" @mousemove="onChartMove" @mouseleave="onChartLeave">
            <div class="big-chart-svg-wrap">
              <svg viewBox="0 0 400 160" class="area-chart" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="chartGrad1" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="var(--lumi-brand)" stop-opacity="0.35" />
                    <stop offset="60%" stop-color="var(--lumi-brand)" stop-opacity="0.08" />
                    <stop offset="100%" stop-color="var(--lumi-brand)" stop-opacity="0.01" />
                  </linearGradient>
                  <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stop-color="var(--lumi-brand-soft)" />
                    <stop offset="100%" stop-color="var(--lumi-brand)" />
                  </linearGradient>
                </defs>

                <g class="chart-grid">
                  <line x1="0" y1="40" x2="400" y2="40" />
                  <line x1="0" y1="80" x2="400" y2="80" />
                  <line x1="0" y1="120" x2="400" y2="120" />
                </g>

                <path
                  :d="requestChartPaths.areaPath"
                  fill="url(#chartGrad1)"
                  class="chart-area-fill"
                />
                <path
                  :d="requestChartPaths.linePath"
                  fill="none"
                  stroke="url(#lineGrad)"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="chart-line"
                />

                <line
                  v-if="hoveredPoint"
                  class="chart-hover-line"
                  :x1="hoveredPoint.x"
                  y1="0"
                  :x2="hoveredPoint.x"
                  y2="160"
                />

                <circle
                  v-for="(p, idx) in requestChartPaths.points"
                  :key="'d' + idx"
                  :cx="p.x"
                  :cy="p.y"
                  r="2.5"
                  fill="var(--lumi-brand)"
                  class="chart-point"
                  :class="{ active: hoveredPoint?.index === idx }"
                />

                <circle
                  v-if="hoveredPoint"
                  :key="hoveredPoint.index"
                  :cx="requestChartPaths.points[hoveredPoint.index].x"
                  :cy="requestChartPaths.points[hoveredPoint.index].y"
                  r="4.5"
                  fill="none"
                  stroke="var(--lumi-brand)"
                  stroke-width="1.2"
                  class="chart-point-ring"
                />
              </svg>

              <div
                v-if="hoveredPoint"
                class="chart-tooltip"
                :style="{
                  left: `${(hoveredPoint.x / 400) * 100}%`,
                  top: `${(hoveredPoint.y / 160) * 100}%`,
                }"
              >
                <span class="ct-label">{{ hoveredPoint.label }}</span>
                <span class="ct-value">{{ hoveredPoint.value.toLocaleString() }} 次</span>
              </div>

              <div class="chart-overlay-stats">
                <div class="overlay-stat primary">
                  <span class="os-label">API 请求</span>
                  <div class="os-row">
                    <span class="os-value">{{ periodData.requests.toLocaleString() }}</span>
                    <span :class="['os-trend', requestTrend >= 0 ? 'up' : 'down']">
                      {{ requestTrend >= 0 ? '+' : '' }}{{ requestTrend }}%
                    </span>
                  </div>
                </div>
                <div class="overlay-stat success">
                  <span class="os-label">Token 消耗</span>
                  <div class="os-row">
                    <span class="os-value">{{ periodData.tokens }}</span>
                    <span :class="['os-trend', tokenTrend >= 0 ? 'up' : 'down']">
                      {{ tokenTrend >= 0 ? '+' : '' }}{{ tokenTrend }}%
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div class="chart-x-axis">
              <span v-for="(item, idx) in chartData" :key="idx">{{ item.label }}</span>
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
                <span :class="['umi-change', m.trend]">
                  <component :is="m.trend === 'up' ? ArrowUpRight : ArrowDownRight" :size="11" />
                  {{ Math.abs(m.change) }}%
                </span>
              </div>
              <div class="umi-bar-track">
                <div
                  class="umi-bar-fill"
                  :style="{ width: m.pct + '%', background: `linear-gradient(90deg, ${m.color}, color-mix(in srgb, ${m.color} 70%, var(--surface)))` }"
                />
              </div>
              <span class="umi-value">{{ m.value }}{{ m.unit }}</span>
            </div>
          </div>

          <div class="provider-list">
            <div
              v-for="(p, idx) in apiProviders"
              :key="p.name"
              class="provider-row"
              :style="{ animationDelay: (0.14 + idx * 0.04) + 's' }"
            >
              <span class="provider-rank">{{ idx + 1 }}</span>
              <div class="provider-name-wrap">
                <Server :size="12" class="provider-icon" />
                <span class="provider-name">{{ p.name }}</span>
              </div>
              <div class="provider-bar-bg">
                <div class="provider-bar-fill" :style="{ width: p.pct + '%' }"></div>
              </div>
              <div class="provider-stats">
                <span class="provider-requests">{{ p.requests }} 次</span>
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
            <span>记忆统计</span>
          </template>
          <template #header>
            <div class="agent-selector">
              <Users :size="12" />
              <select v-model="selectedAgentId" class="agent-select" @change="onAgentChange">
                <option v-for="a in memoryStore.memoryAgents" :key="a.id" :value="a.id">
                  {{ a.name }}{{ a.fact_count !== undefined ? ` (${a.fact_count}条)` : '' }}
                </option>
              </select>
            </div>
          </template>

          <div class="memory-stats-grid">
            <div class="memory-stat-item">
              <Database :size="16" class="memory-stat-icon" />
              <span class="memory-stat-label">长期记忆</span>
              <span class="memory-stat-value">{{ memoryLineCount }} 行</span>
            </div>
            <div class="memory-stat-item">
              <Sparkles :size="16" class="memory-stat-icon" />
              <span class="memory-stat-label">蒸馏摘要</span>
              <span class="memory-stat-value">{{ hasSummary ? '已蒸馏' : '未蒸馏' }}</span>
            </div>
            <div class="memory-stat-item">
              <Calendar :size="16" class="memory-stat-icon" />
              <span class="memory-stat-label">日常记录</span>
              <span class="memory-stat-value">{{ dailyCount }} 天</span>
            </div>
            <div class="memory-stat-item">
              <User :size="16" class="memory-stat-icon" />
              <span class="memory-stat-label">用户档案</span>
              <span class="memory-stat-value">{{ hasProfile ? '有' : '无' }}</span>
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
                <span class="dc-label">记忆行数</span>
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
              <span class="health-label">记忆充实度</span>
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
            <span>上下文监控</span>
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
            <span>最近活动</span>
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
              暂无近期活动
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

.stat-card {
  position: relative;
  overflow: hidden;
  animation: lumi-content-fade-up var(--duration-enter) var(--ease-out-expo) both;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast);
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.stat-card-content {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.stat-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.stat-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.stat-sub {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.stat-card-accent {
  position: absolute;
  top: 0;
  left: 0;
  width: 3px;
  height: 100%;
  opacity: 0.8;
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
  padding: var(--space-5) var(--space-5) 0;
  cursor: crosshair;
}

.big-chart-svg-wrap {
  position: relative;
  height: 200px;
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, color-mix(in srgb, var(--lumi-brand) 8%, transparent) 0%, transparent 70%);
  overflow: hidden;
}

.area-chart {
  width: 100%;
  height: 100%;
  display: block;
}

.chart-grid line {
  stroke: var(--border-light);
  stroke-width: 1;
  stroke-dasharray: 4 4;
}

.chart-area-fill {
  opacity: 0;
  animation: fadeAreaIn var(--duration-slow) var(--ease-out-expo) var(--duration-normal) both;
}

@keyframes fadeAreaIn { to { opacity: 1; } }

.chart-line {
  stroke-dasharray: 800;
  stroke-dashoffset: 800;
  animation: drawLine 1.2s var(--ease-out-expo) var(--duration-fast) both;
}

@keyframes drawLine { to { stroke-dashoffset: 0; } }

.chart-point {
  opacity: 0;
  transform-box: fill-box;
  transform-origin: center;
  transform: scale(1);
  transition: opacity var(--transition-fast), transform var(--transition-fast);
  animation: dotIn var(--duration-fast) var(--ease-out-expo) var(--duration-slow) both;
  pointer-events: none;
}

.chart-point.active {
  transform: scale(1.6);
}

.chart-point-ring {
  opacity: 0;
  transform-box: fill-box;
  transform-origin: center;
  pointer-events: none;
  animation: ringIn var(--duration-fast) var(--ease-out-expo) both;
}

@keyframes dotIn { to { opacity: 0.9; } }

@keyframes ringIn {
  from {
    opacity: 0;
    transform: scale(0.4);
  }
  to {
    opacity: 0.45;
    transform: scale(1);
  }
}

.chart-hover-line {
  stroke: var(--lumi-brand);
  stroke-width: 1;
  stroke-dasharray: 3 3;
  opacity: 0.5;
  pointer-events: none;
}

.chart-tooltip {
  position: absolute;
  transform: translate(-50%, calc(-100% - 10px));
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2) var(--space-3);
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  pointer-events: none;
  z-index: 10;
  transition: opacity var(--transition-fast);
}

.ct-label {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.ct-value {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.chart-overlay-stats {
  position: absolute;
  top: var(--space-4);
  right: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.overlay-stat {
  text-align: right;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--surface) 80%, transparent);
  border: 1px solid var(--border-light);
  backdrop-filter: blur(4px);
}

.os-label {
  display: block;
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.os-row {
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: var(--space-2);
}

.os-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.os-trend {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
}

.os-trend.up { color: var(--lumi-success); }
.os-trend.down { color: var(--lumi-danger); }

.overlay-stat.primary .os-value { color: var(--lumi-primary); }
.overlay-stat.success .os-value { color: var(--lumi-success); }

.chart-x-axis {
  display: flex;
  justify-content: space-between;
  padding: var(--space-3) var(--space-2) var(--space-4);
}

.chart-x-axis span {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.usage-mini-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--border-light);
}

.usage-mini-item {
  position: relative;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  border-top: 2px solid var(--umi-accent, var(--lumi-brand));
  transition: transform var(--transition-fast);
}

.usage-mini-item:hover {
  transform: translateY(-2px);
}

.umi-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}

.umi-label {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.umi-change {
  display: flex;
  align-items: center;
  gap: calc(var(--space-1) / 2);
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
}

.umi-change.up { color: var(--lumi-success); }
.umi-change.down { color: var(--lumi-danger); }

.umi-bar-track {
  height: var(--space-1);
  background: var(--border);
  border-radius: calc(var(--space-1) / 2);
  overflow: hidden;
  margin-bottom: var(--space-2);
}

.umi-bar-fill {
  height: 100%;
  border-radius: calc(var(--space-1) / 2);
  transition: width var(--duration-enter) var(--ease-out-expo);
}

.umi-value {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
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
  width: 18px;
  text-align: center;
  font-size: var(--text-xs);
  font-weight: var(--font-bold);
  color: var(--text-muted);
  flex-shrink: 0;
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

.spin-animation {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
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
</style>
