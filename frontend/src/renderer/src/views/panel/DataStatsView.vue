<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
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
  Shield,
  Cpu,
  Search,
  Bot,
  MessageSquare,
  Sparkles,
  Archive,
  Trash2,
  Edit3,
  Plus,
  Loader2,
  X,
  Save,
  Globe,
  Lock,
  Flame,
  Tag,
  Users,
} from 'lucide-vue-next'
import { useMemoryStore } from '../../stores/memory'
import { useStatsStore } from '../../stores/stats'

const router = useRouter()
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
        <button :class="['refresh-btn', { spinning: isRefreshing }]" @click="handleRefresh">
          <RefreshCw :size="14" />
        </button>
      </div>
    </div>

    <div class="top-stats-row">
      <div class="stat-card" style="animation-delay: 0.04s">
        <div class="stat-icon-wrap api">
          <Activity :size="18" />
        </div>
        <div class="stat-body">
          <span class="stat-label">API 请求</span>
          <span class="stat-value">{{ periodData.requests.toLocaleString() }}</span>
        </div>
      </div>

      <div class="stat-card" style="animation-delay: 0.08s">
        <div class="stat-icon-wrap token">
          <Zap :size="18" />
        </div>
        <div class="stat-body">
          <span class="stat-label">Token 消耗</span>
          <span class="stat-value">{{ periodData.tokens }}</span>
        </div>
      </div>

      <div class="stat-card" style="animation-delay: 0.12s">
        <div class="stat-icon-wrap memory">
          <Brain :size="18" />
        </div>
        <div class="stat-body">
          <span class="stat-label">记忆行数</span>
          <span class="stat-value">{{ memoryLineCount }}</span>
        </div>
      </div>

      <div class="stat-card" style="animation-delay: 0.16s">
        <div class="stat-icon-wrap context">
          <Cpu :size="18" />
        </div>
        <div class="stat-body">
          <span class="stat-label">对话数</span>
          <span class="stat-value">{{ periodData.conversations }}</span>
        </div>
      </div>
    </div>

    <div class="main-content">
      <div class="left-col">
        <div class="section-card" style="animation-delay: 0.10s">
          <div class="section-header">
            <div class="section-title-group">
              <BarChart3 :size="16" class="section-icon" />
              <span class="section-title">API 用量</span>
            </div>
            <Calendar :size="14" class="section-icon-muted" />
          </div>
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
                fill="var(--lumi-primary)"
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
        </div>

        <div class="section-card" style="animation-delay: 0.18s">
          <div class="section-header">
            <div class="section-title-group">
              <Brain :size="16" class="section-icon" />
              <span class="section-title">记忆统计</span>
            </div>
            <div class="agent-selector">
              <Users :size="12" />
              <select v-model="selectedAgentId" class="agent-select" @change="onAgentChange">
                <option v-for="a in memoryStore.memoryAgents" :key="a.id" :value="a.id">
                  {{ a.name }}{{ a.fact_count !== undefined ? ` (${a.fact_count}条)` : '' }}
                </option>
              </select>
            </div>
          </div>

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
                  stroke="var(--lumi-primary)" stroke-width="10"
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
                <span class="legend-dot" style="background: var(--lumi-primary)" />
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
        </div>
      </div>

      <div class="right-col">
        <div class="section-card" style="animation-delay: 0.14s">
          <div class="section-header">
            <div class="section-title-group">
              <Layers :size="16" class="section-icon" />
              <span class="section-title">上下文监控</span>
            </div>
            <Cpu :size="14" class="section-icon-muted" />
          </div>
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
        </div>

        <div class="section-card" style="animation-delay: 0.22s">
          <div class="section-header">
            <div class="section-title-group">
              <Clock :size="16" class="section-icon" />
              <span class="section-title">最近活动</span>
            </div>
            <Database :size="14" class="section-icon-muted" />
          </div>
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
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.data-stats-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px 28px;
  gap: 20px;
  overflow-y: auto;
}

.stats-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  animation: content-fade-up 0.5s cubic-bezier(0.4, 0, 0.2, 1) both;
}

.header-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.header-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.period-tabs {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.period-btn {
  padding: 6px 16px;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast) ease-in-out;
}

.period-btn.active {
  background: var(--surface);
  color: var(--lumi-primary);
  box-shadow: var(--shadow-xs);
}

.period-btn:hover:not(.active) {
  color: var(--text-secondary);
}

.refresh-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast) ease-in-out;
}

.refresh-btn:hover {
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.refresh-btn.spinning {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.spinning {
  animation: spin 1s linear infinite;
}

.top-stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  animation: content-fade-up 0.5s cubic-bezier(0.4, 0, 0.2, 1) both;
  transition: border-color var(--transition-fast) ease-in-out;
}

.stat-card:hover {
  border-color: var(--lumi-primary);
}

.stat-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon-wrap.api {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.stat-icon-wrap.token {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.stat-icon-wrap.memory {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.stat-icon-wrap.context {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.stat-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 11px;
  color: var(--text-muted);
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-trend {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  font-weight: 600;
}

.stat-trend.up {
  color: var(--lumi-success);
}

.stat-trend.down {
  color: var(--lumi-accent);
}

.main-content {
  display: flex;
  gap: 16px;
}

.left-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.right-col {
  width: 380px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-card {
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  padding: 18px;
  animation: content-fade-up 0.5s cubic-bezier(0.4, 0, 0.2, 1) both;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.section-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-icon {
  color: var(--lumi-primary);
}

.section-icon-muted {
  color: var(--text-muted);
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.agent-selector {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 6px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 11px;
}

.agent-select {
  background: transparent;
  border: none;
  color: var(--text);
  font-size: 11px;
  outline: none;
  cursor: pointer;
}

.bar-chart-wrap {
  margin-bottom: 16px;
}

.bar-chart-svg {
  width: 100%;
  height: 100px;
}

.bar-anim {
  transition: opacity var(--transition-normal) ease-in-out;
}

.provider-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.provider-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-light);
  animation: content-fade-up 0.4s cubic-bezier(0.4, 0, 0.2, 1) both;
}

.provider-row:last-child {
  border-bottom: none;
}

.provider-name-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100px;
  flex-shrink: 0;
}

.provider-icon {
  color: var(--text-muted);
}

.provider-name {
  font-size: 13px;
  font-weight: 500;
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
  background: var(--lumi-primary);
  transition: width var(--transition-normal) ease-in-out;
}

.provider-stats {
  display: flex;
  gap: 8px;
  width: 110px;
  flex-shrink: 0;
}

.provider-requests,
.provider-tokens {
  font-size: 11px;
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
  gap: 10px;
  margin-bottom: 16px;
}

.memory-stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.memory-stat-label {
  font-size: 11px;
  color: var(--text-muted);
}

.memory-stat-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.donut-section {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 16px;
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
  transition: stroke-dasharray var(--transition-normal) ease-in-out;
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
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.dc-label {
  font-size: 10px;
  color: var(--text-muted);
}

.donut-legend {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-text {
  font-size: 12px;
  color: var(--text-secondary);
}

.legend-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  margin-left: auto;
}

.health-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.health-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.health-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.health-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--lumi-primary);
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
  background: var(--lumi-primary);
  transition: width var(--transition-normal) ease-in-out;
}

.context-metrics {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.context-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  animation: content-fade-up 0.4s cubic-bezier(0.4, 0, 0.2, 1) both;
}

.context-label-row {
  display: flex;
  justify-content: space-between;
}

.context-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

.context-value {
  font-size: 12px;
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
  background: var(--lumi-primary);
  transition: width var(--transition-normal) ease-in-out;
}

.activity-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.activity-item {
  display: flex;
  gap: 12px;
  animation: content-fade-up 0.4s cubic-bezier(0.4, 0, 0.2, 1) both;
  padding: 8px 0;
}

.activity-dot-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 12px;
  flex-shrink: 0;
  padding-top: 4px;
}

.activity-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.activity-dot.api {
  background: var(--lumi-primary);
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
  margin-top: 4px;
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
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

.activity-time {
  font-size: 11px;
  color: var(--text-muted);
}

.activity-detail {
  font-size: 11px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

</style>