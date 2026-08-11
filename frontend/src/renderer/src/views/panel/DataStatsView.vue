<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  BarChart3,
  Zap,
  Brain,
  Database,
  Activity,
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
  // 读取上下文窗口大小（用户在设置页配置，0 = 自动检测），区别于生成 token 上限 defaultMaxTokens
  const windowSize = modelStore.modelConfig.contextWindowSize || 32768
  const totalCtx = tok
  return [
    { label: '累计上下文使用量', value: totalCtx, unit: 'tokens', max: Math.max(totalCtx, windowSize) },
    { label: '窗口使用率', value: windowSize > 0 ? Math.min(100, Math.round((totalCtx / windowSize) * 100)) : 0, unit: '%', max: 100 },
    { label: '对话轮次', value: msg, unit: '轮', max: Math.max(msg * 2, 100) },
    { label: '对话数', value: conv, unit: '个', max: Math.max(conv * 2, 50) },
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
      <LumiCard v-for="(stat, idx) in [
        { key: 'api', icon: Activity, label: 'API 请求', value: periodData.requests.toLocaleString() },
        { key: 'token', icon: Zap, label: 'Token 消耗', value: periodData.tokens },
        { key: 'memory', icon: Brain, label: '记忆行数', value: memoryLineCount },
        { key: 'context', icon: Cpu, label: '对话数', value: periodData.conversations },
      ]" :key="stat.key" class="stat-card" :style="{ animationDelay: `${(idx + 1) * 0.04}s` }" padding="md">
        <div class="stat-card-content">
          <div class="lumi-icon-wrap lumi-icon-wrap--md lumi-icon-wrap--brand">
            <component :is="stat.icon" :size="18" />
          </div>
          <div class="stat-body">
            <span class="stat-label">{{ stat.label }}</span>
            <span class="stat-value">{{ stat.value }}</span>
          </div>
        </div>
      </LumiCard>
    </div>

    <div class="main-content">
      <div class="left-col">
        <LumiCard class="section-card" :style="{ animationDelay: '0.10s' }" padding="md">
          <template #title>
            <BarChart3 :size="16" />
            <span>API 用量</span>
          </template>
          <div class="chart-area">
            <div class="big-chart-svg-wrap">
              <svg viewBox="0 0 400 160" class="area-chart" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="chartGrad1" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="var(--lumi-primary)" stop-opacity="0.3" />
                    <stop offset="100%" stop-color="var(--lumi-primary)" stop-opacity="0.02" />
                  </linearGradient>
                </defs>
                <path
                  :d="requestChartPaths.areaPath"
                  fill="url(#chartGrad1)"
                  class="chart-area-fill"
                />
                <path
                  :d="requestChartPaths.linePath"
                  fill="none"
                  stroke="var(--lumi-primary)"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  class="chart-line"
                />
                <circle
                  v-if="requestChartPaths.points.length"
                  :cx="requestChartPaths.points[requestChartPaths.points.length - 1].x"
                  :cy="requestChartPaths.points[requestChartPaths.points.length - 1].y"
                  r="4"
                  fill="var(--lumi-primary)"
                  class="chart-dot pulse-dot"
                />
              </svg>
              <div class="chart-overlay-stats">
                <div class="overlay-stat primary">
                  <span class="os-label">API 请求</span>
                  <span class="os-value">{{ periodData.requests.toLocaleString() }}</span>
                  <span :class="['os-trend', requestTrend >= 0 ? 'up' : 'down']">
                    {{ requestTrend >= 0 ? '+' : '' }}{{ requestTrend }}%
                  </span>
                </div>
                <div class="overlay-stat success">
                  <span class="os-label">Token 消耗</span>
                  <span class="os-value">{{ periodData.tokens }}</span>
                  <span :class="['os-trend', tokenTrend >= 0 ? 'up' : 'down']">
                    {{ tokenTrend >= 0 ? '+' : '' }}{{ tokenTrend }}%
                  </span>
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
                  :style="{ width: m.pct + '%', background: m.color }"
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
              :style="{ animationDelay: (0.14 + idx * 0.03) + 's' }"
            >
              <div class="provider-name-wrap">
                <Server :size="12" class="provider-icon" />
                <span class="provider-name">{{ p.name }}</span>
              </div>
              <div class="provider-bar-bg">
                <div class="provider-bar-fill" :style="{ width: p.pct + '%' }"></div>
              </div>
              <div class="provider-stats">
                <span class="provider-requests">{{ p.requests }} 次</span>
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
              <span class="memory-stat-label">长期记忆</span>
              <span class="memory-stat-value">{{ memoryLineCount }} 行</span>
            </div>
            <div class="memory-stat-item">
              <span class="memory-stat-label">蒸馏摘要</span>
              <span class="memory-stat-value">{{ hasSummary ? '已蒸馏' : '未蒸馏' }}</span>
            </div>
            <div class="memory-stat-item">
              <span class="memory-stat-label">日常记录</span>
              <span class="memory-stat-value">{{ dailyCount }} 天</span>
            </div>
            <div class="memory-stat-item">
              <span class="memory-stat-label">用户档案</span>
              <span class="memory-stat-value">{{ hasProfile ? '有' : '无' }}</span>
            </div>
          </div>

          <div class="donut-section">
            <div class="donut-wrap">
              <svg viewBox="0 0 100 100" class="donut-chart">
                <circle cx="50" cy="50" r="40" fill="none" stroke="var(--border)" stroke-width="10" />
                <circle
                  cx="50" cy="50" r="40" fill="none"
                  stroke="var(--lumi-brand)" stroke-width="10"
                  :stroke-dasharray="`${Math.min(memoryLineCount, 100) * 2.51} ${251.2 - Math.min(memoryLineCount, 100) * 2.51}`"
                  stroke-dashoffset="0"
                  class="donut-anim"
                />
              </svg>
              <div class="donut-center">
                <span class="dc-value">{{ memoryLineCount }}</span>
                <span class="dc-label">记忆行数</span>
              </div>
            </div>
            <div class="donut-legend">
              <div class="legend-item">
                <span class="legend-dot" style="background: var(--lumi-brand)" />
                <span class="legend-text">长期记忆</span>
                <span class="legend-count">{{ memoryLineCount }} 行</span>
              </div>
              <div class="legend-item">
                <span class="legend-dot" style="background: var(--lumi-success)" />
                <span class="legend-text">蒸馏摘要</span>
                <span class="legend-count">{{ hasSummary ? '有' : '无' }}</span>
              </div>
              <div class="legend-item">
                <span class="legend-dot" style="background: var(--lumi-warning)" />
                <span class="legend-text">日常记录</span>
                <span class="legend-count">{{ dailyCount }} 天</span>
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
              :style="{ animationDelay: (0.18 + idx * 0.04) + 's' }"
            >
              <div class="context-label-row">
                <span class="context-label">{{ m.label }}</span>
                <span class="context-value">{{ m.value }} {{ m.unit }}</span>
              </div>
              <div class="context-bar-bg">
                <div
                  class="context-bar-fill"
                  :style="{ width: (m.value / m.max * 100) + '%' }"
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
            <Database :size="14" class="section-icon-muted" />
          </template>
          <div class="activity-timeline">
            <div
              v-for="(a, idx) in recentActivities"
              :key="a.time + a.action"
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
  border-bottom: 1px solid var(--divider-soft, var(--border-light));
  animation: lumi-content-fade-up var(--duration-enter) var(--ease-default) both;
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
  gap: var(--space-3);
}

.stat-card {
  animation: lumi-content-fade-up var(--duration-enter) var(--ease-default) both;
}

.stat-card-content {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.stat-body {
  flex: 1;
  display: flex;
  flex-direction: column;
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

.stat-trend {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
}

.stat-trend.up {
  color: var(--lumi-success);
}

.stat-trend.down {
  color: var(--lumi-accent);
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
}

.right-col {
  width: 380px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.section-card {
  animation: lumi-content-fade-up var(--duration-enter) var(--ease-default) both;
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
  padding: var(--space-4) var(--space-5) 0;
}

.big-chart-svg-wrap {
  position: relative;
  height: calc(var(--space-5) * 9);
  border-radius: var(--radius-md);
  background: linear-gradient(180deg, var(--lumi-primary-subtle) 0%, transparent 100%);
}

.area-chart {
  width: 100%;
  height: 100%;
}

.chart-area-fill {
  opacity: 0;
  animation: fadeAreaIn var(--duration-slow) var(--ease-out-expo) var(--duration-normal) both;
}

@keyframes fadeAreaIn { to { opacity: 1; } }

.chart-line {
  stroke-dasharray: 800;
  stroke-dashoffset: 800;
  animation: drawLine var(--duration-enter) var(--ease-default) var(--duration-fast) both;
}

@keyframes drawLine { to { stroke-dashoffset: 0; } }

.chart-dot {
  opacity: 0;
  animation: dotIn var(--duration-fast) var(--ease-out-expo) var(--duration-slow) both;
}

@keyframes dotIn { to { opacity: 1; } }

.pulse-dot {
  animation: dotPulse var(--duration-slow) var(--ease-in-out) infinite;
}

@keyframes dotPulse {
  0%, 100% { r: 4; }
  50% { r: 6; }
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
}

.os-label {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.os-value {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text);
}

.os-trend {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  margin-left: var(--space-1);
}

.os-trend.up { color: var(--lumi-success); }
.os-trend.down { color: var(--lumi-danger); }

.overlay-stat.primary .os-value { color: var(--lumi-primary); }
.overlay-stat.success .os-value { color: var(--lumi-success); }

.chart-x-axis {
  display: flex;
  justify-content: space-between;
  padding: var(--space-2) var(--space-2) 0;
}

.chart-x-axis span {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.usage-mini-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5) var(--space-4);
  border-top: 1px solid var(--border-light);
}

.usage-mini-item {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
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
  color: var(--text);
}

.provider-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.provider-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--border-light);
  animation: lumi-content-fade-up var(--duration-slow) var(--ease-default) both;
}

.provider-row:last-child {
  border-bottom: none;
}

.provider-name-wrap {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  width: 100px;
  flex-shrink: 0;
}

.provider-icon {
  color: var(--text-muted);
}

.provider-name {
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-primary);
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
  background: var(--lumi-brand);
  transition: width var(--transition-normal);
}

.provider-stats {
  display: flex;
  gap: var(--space-2);
  width: 110px;
  flex-shrink: 0;
}

.provider-requests,
.provider-tokens {
  font-size: var(--text-xs);
  color: var(--text-muted);
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
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3) var(--space-3);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.memory-stat-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.memory-stat-value {
  font-size: var(--text-2xl);
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
  width: 120px;
  height: 120px;
  flex-shrink: 0;
}

.donut-chart {
  width: 100%;
  height: 100%;
}

.donut-anim {
  transition: stroke-dasharray var(--transition-normal);
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
  gap: var(--space-1);
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
  background: var(--lumi-brand);
  transition: width var(--transition-normal);
}

.context-metrics {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.context-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  animation: lumi-content-fade-up var(--duration-slow) var(--ease-default) both;
}

.context-label-row {
  display: flex;
  justify-content: space-between;
}

.context-label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
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
  background: var(--lumi-brand);
  transition: width var(--transition-normal);
}

.activity-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.activity-item {
  display: flex;
  gap: var(--space-3);
  animation: lumi-content-fade-up var(--duration-slow) var(--ease-default) both;
  padding: var(--space-2) 0;
}

.activity-dot-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: var(--space-3);
  flex-shrink: 0;
  padding-top: var(--space-1);
}

.activity-dot {
  width: var(--space-2);
  height: var(--space-2);
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.activity-dot.api {
  background: var(--lumi-brand);
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
  background: var(--border-light);
  margin-top: var(--space-1);
}

.activity-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.activity-top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.activity-action {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.activity-time {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.activity-detail {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}


</style>
