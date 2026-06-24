<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import {
  BarChart3,
  Zap,
  Brain,
  Database,
  Activity,
  Calendar,
  Clock,
  Layers,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Server,
  Cpu,
  Users,
} from 'lucide-vue-next'
import LumiCard from '../../components/common/LumiCard.vue'
import LumiButton from '../../components/common/LumiButton.vue'
import { useMemoryStore } from '../../stores/memory'
import { useStatsStore } from '../../stores/stats'

const memoryStore = useMemoryStore()
const statsStore = useStatsStore()

const period = ref<7 | 30 | 90>(7)

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
  const windowSize = 32768
  const avgCtx = conv > 0 ? Math.min(windowSize, Math.round(tok / conv)) : 0
  return [
    { label: '当前上下文', value: avgCtx, unit: 'tokens', max: windowSize },
    { label: '窗口使用率', value: Math.min(100, Math.round((avgCtx / windowSize) * 100)), unit: '%', max: 100 },
    { label: '对话轮次', value: msg, unit: '轮', max: Math.max(msg * 2, 100) },
    { label: '对话数', value: conv, unit: '个', max: Math.max(conv * 2, 50) },
  ]
})

const recentActivities = computed(() => {
  const records = statsStore.recentRecords
  if (!records.length) return []
  return records.slice(0, 10).map(r => {
    const ts = r.timestamp
    let timeStr = ''
    try {
      const d = new Date(ts)
      timeStr = d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0')
    } catch { timeStr = '--:--' }
    const tokStr = r.total_tokens > 0 ? ` (${r.total_tokens.toLocaleString()} tokens)` : ''
    return {
      time: timeStr,
      action: 'API 调用',
      detail: `${r.provider} / ${r.model}${tokStr}`,
      type: 'api' as const,
    }
  })
})

const dailyChartData = computed(() => {
  const byDay = statsStore.byDay
  const entries = Object.entries(byDay).sort((a, b) => a[0].localeCompare(b[0]))
  if (!entries.length) {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    return days.map(() => 0)
  }
  const maxVal = Math.max(...entries.map(([, v]) => v), 1)
  return entries.map(([, v]) => Math.round((v / maxVal) * 100))
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

onMounted(() => { loadData() })
watch(period, () => { statsStore.fetchAll(period.value) })
</script>

<template>
  <div class="data-stats-view">
    <div class="stats-header">
      <div class="header-left">
        <h1 class="header-title">数据统计</h1>
        <p class="header-subtitle">LuomiNest 运行数据概览</p>
      </div>
      <div class="header-actions">
        <div class="period-tabs">
          <button :class="['period-btn', { active: period === 7 }]" @click="period = 7">7天</button>
          <button :class="['period-btn', { active: period === 30 }]" @click="period = 30">30天</button>
          <button :class="['period-btn', { active: period === 90 }]" @click="period = 90">90天</button>
        </div>
        <LumiButton variant="ghost" size="sm" icon-only aria-label="刷新" @click="handleRefresh">
          <template #icon><RefreshCw :size="14" :class="{ spinning: isRefreshing }" /></template>
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
          <div class="stat-icon-wrap" :class="stat.key">
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
          <template #header>
            <Calendar :size="14" class="section-icon-muted" />
          </template>
          <div class="bar-chart-wrap">
            <svg viewBox="0 0 300 120" class="bar-chart-svg">
              <rect
                v-for="(h, i) in dailyChartData"
                :key="i"
                :x="i * 38 + 10"
                :y="120 - h"
                width="24"
                :height="h"
                rx="4"
                fill="var(--lumi-brand)"
                :opacity="0.3 + (i * 0.1)"
                class="bar-anim"
                :style="{ animationDelay: `${i * 0.1}s` }"
              />
            </svg>
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
  justify-content: space-between;
  align-items: flex-start;
  animation: content-fade-up var(--duration-enter) var(--ease-default) both;
}

.header-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.header-subtitle {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.header-actions {
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
  animation: content-fade-up var(--duration-enter) var(--ease-default) both;
}

.stat-card-content {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.stat-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
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
  font-size: 20px;
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
  animation: content-fade-up var(--duration-enter) var(--ease-default) both;
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

.bar-chart-wrap {
  margin-bottom: var(--space-4);
}

.bar-chart-svg {
  width: 100%;
  height: 100px;
}

.bar-anim {
  transition: opacity var(--transition-normal);
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
  animation: content-fade-up var(--duration-slow) var(--ease-default) both;
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
  border-radius: 3px;
  background: var(--bg-secondary);
  overflow: hidden;
}

.provider-bar-fill {
  height: 100%;
  border-radius: 3px;
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
  width: 8px;
  height: 8px;
  border-radius: 50%;
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
  border-radius: 3px;
  background: var(--bg-secondary);
  overflow: hidden;
}

.health-bar-fill {
  height: 100%;
  border-radius: 3px;
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
  animation: content-fade-up var(--duration-slow) var(--ease-default) both;
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
  border-radius: 3px;
  background: var(--bg-secondary);
  overflow: hidden;
}

.context-bar-fill {
  height: 100%;
  border-radius: 3px;
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
  animation: content-fade-up var(--duration-slow) var(--ease-default) both;
  padding: var(--space-2) 0;
}

.activity-dot-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 12px;
  flex-shrink: 0;
  padding-top: var(--space-1);
}

.activity-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
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

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes content-fade-up {
  from {
    opacity: 0;
    transform: translateY(14px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .stats-header,
  .stat-card,
  .section-card,
  .provider-row,
  .context-item,
  .activity-item,
  .period-btn,
  .bar-anim,
  .donut-anim,
  .provider-bar-fill,
  .health-bar-fill,
  .context-bar-fill {
    animation: none;
    transition: none;
  }

  .spinning {
    animation: none;
  }
}
</style>
