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
  BookOpen,
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
} from 'lucide-vue-next'
import { useMemoryStore } from '../../stores/memory'
import { useAgentStore } from '../../stores/agent'
import { useStatsStore } from '../../stores/stats'
import type { MemoryFact } from '../../stores/memory'

const router = useRouter()
const memoryStore = useMemoryStore()
const agentStore = useAgentStore()
const statsStore = useStatsStore()

const period = ref<7 | 30 | 90>(7)

const userSpaceFacts = computed(() => memoryStore.memoryData?.user_space?.facts || [])
const agentFacts = computed(() => memoryStore.memoryData?.agent_memory?.agent_facts || [])
const agentEvents = computed(() => memoryStore.memoryData?.agent_memory?.agent_events || [])
const episodicEvents = computed(() => memoryStore.memoryData?.user_space?.episodic_events || [])
const workingMemory = computed(() => memoryStore.memoryData?.agent_memory?.working_memory || null)
const distilled = computed(() => memoryStore.memoryData?.user_space?.distilled || null)
const profile = computed(() => memoryStore.memoryData?.user_space?.profile || null)
const userContext = computed(() => memoryStore.memoryData?.user_space?.user || null)
const domainSummary = computed(() => memoryStore.memoryData?.agent_memory?.domain_summary || '')

const hasProfile = computed(() => {
  const p = profile.value
  if (!p) return false
  return !!(p.name || p.nickname || p.occupation || p.location || (p.interests && p.interests.length > 0) || (p.hobbies && p.hobbies.length > 0))
})

const hasDistilled = computed(() => {
  const d = distilled.value
  return d && (d.core_identity || d.long_term || d.temporary || d.events_timeline)
})

const totalMemoryRecords = computed(() => {
  return userSpaceFacts.value.length + agentFacts.value.length + episodicEvents.value.length
})

const totalUserFacts = computed(() => userSpaceFacts.value.length)
const totalAgentFacts = computed(() => agentFacts.value.length)
const totalEvents = computed(() => episodicEvents.value.length + agentEvents.value.length)

const userSpaceFactsByTier = computed(() => {
  const groups: Record<string, MemoryFact[]> = {}
  for (const fact of userSpaceFacts.value) {
    if (!groups[fact.tier]) groups[fact.tier] = []
    groups[fact.tier].push(fact)
  }
  return groups
})

const memoryDistribution = computed(() => {
  const working = userSpaceFacts.value.filter(f => f.tier === 'temporary_context').length
  const episodic = episodicEvents.value.length
  const semantic = userSpaceFacts.value.filter(f => f.tier === 'long_term_preference' || f.tier === 'core_identity').length
  const total = working + episodic + semantic || 1
  return { working, episodic, semantic, total }
})

const donutSegments = computed(() => {
  const { working, episodic, semantic, total } = memoryDistribution.value
  const circumference = 2 * Math.PI * 40
  const workingDash = (working / total) * circumference
  const episodicDash = (episodic / total) * circumference
  const semanticDash = (semantic / total) * circumference
  let offset = 0
  const segments = []
  if (working > 0) {
    segments.push({ dasharray: `${workingDash} ${circumference - workingDash}`, dashoffset: -offset, color: 'var(--lumi-primary)' })
    offset += workingDash
  }
  if (episodic > 0) {
    segments.push({ dasharray: `${episodicDash} ${circumference - episodicDash}`, dashoffset: -offset, color: 'var(--lumi-success)' })
    offset += episodicDash
  }
  if (semantic > 0) {
    segments.push({ dasharray: `${semanticDash} ${circumference - semanticDash}`, dashoffset: -offset, color: 'var(--lumi-warning)' })
  }
  return segments
})

const memoryHealth = computed(() => {
  const { working, episodic, semantic, total } = memoryDistribution.value
  if (total === 0) return 0
  const balance = 1 - (Math.abs(working - episodic) + Math.abs(episodic - semantic) + Math.abs(semantic - working)) / (2 * total || 1)
  return Math.min(100, Math.round(balance * 100))
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

interface LayerTab {
  id: string
  name: string
  sub: string
  icon: typeof Brain
  color: string
  desc: string
}

const layerTabs = ref<LayerTab[]>([
  { id: 'user-space', name: '用户空间', sub: 'UserSpace', icon: Globe, color: '#8b5cf6', desc: '全局共享 · 所有Agent可见' },
  { id: 'agent-memory', name: 'Agent记忆', sub: 'AgentMemory', icon: Bot, color: '#0ea5e9', desc: 'Agent私有 · 仅当前Agent可见' },
  { id: 'thread-memory', name: '对话记忆', sub: 'ThreadMemory', icon: MessageSquare, color: '#f59e0b', desc: '当前对话上下文 · 短期' },
])

const activeTab = ref('user-space')

const searchQuery = ref('')
const isSearching = ref(false)
const showSearchResults = ref(false)
const searchMemoryResults = ref<Array<{ id: string; content: string; category: string; tier: string; layer: string; confidence: number }>>([])

const showAddDialog = ref(false)
const newFactContent = ref('')
const newFactCategory = ref('context')
const newFactLayer = ref('user')
const isAdding = ref(false)

const editingFactId = ref<string | null>(null)
const editingContent = ref('')

const categoryOptions = [
  { value: 'preference', label: '偏好' },
  { value: 'knowledge', label: '知识' },
  { value: 'context', label: '上下文' },
  { value: 'behavior', label: '行为' },
  { value: 'goal', label: '目标' },
  { value: 'correction', label: '纠正' },
]

const tierOptions = [
  { value: 'core_identity', label: '核心身份', color: '#8b5cf6' },
  { value: 'long_term_preference', label: '长期偏好', color: '#22c55e' },
  { value: 'temporary_context', label: '临时上下文', color: '#f59e0b' },
]

function getCategoryLabel(cat: string) {
  return categoryOptions.find(c => c.value === cat)?.label || cat
}

function getTierLabel(tier: string) {
  return tierOptions.find(t => t.value === tier)?.label || tier
}

function getTierColor(tier: string) {
  return tierOptions.find(t => t.value === tier)?.color || '#888'
}

function formatTimeAgo(isoStr: string) {
  if (!isoStr) return '未知'
  try {
    const d = new Date(isoStr)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)
    if (diffMins < 1) return '刚刚'
    if (diffMins < 60) return `${diffMins}分钟前`
    if (diffHours < 24) return `${diffHours}小时前`
    if (diffDays < 30) return `${diffDays}天前`
    return '长期'
  } catch {
    return '未知'
  }
}

function switchTab(tabId: string) {
  activeTab.value = tabId
}

async function handleSearch() {
  if (!searchQuery.value.trim()) return
  isSearching.value = true
  showSearchResults.value = true
  try {
    searchMemoryResults.value = await memoryStore.searchMemory(searchQuery.value, 10)
  } catch {
    searchMemoryResults.value = []
  } finally {
    isSearching.value = false
  }
}

function clearSearch() {
  searchQuery.value = ''
  showSearchResults.value = false
  searchMemoryResults.value = []
}

function chatAboutMemory(text: string) {
  const event = new CustomEvent('luominest:memory-chat-trigger', { detail: { text } })
  window.dispatchEvent(event)
  router.push('/workspace')
}

async function handleAddFact() {
  if (!newFactContent.value.trim()) return
  isAdding.value = true
  try {
    await memoryStore.addFact(
      newFactContent.value.trim(),
      newFactCategory.value,
      0.8,
      agentStore.activeAgent?.id,
      'manual',
      newFactLayer.value,
    )
    newFactContent.value = ''
    newFactCategory.value = 'context'
    showAddDialog.value = false
  } finally {
    isAdding.value = false
  }
}

function startEdit(factId: string, content: string) {
  editingFactId.value = factId
  editingContent.value = content
}

function cancelEdit() {
  editingFactId.value = null
  editingContent.value = ''
}

async function saveEdit() {
  if (!editingFactId.value || !editingContent.value.trim()) return
  try {
    await memoryStore.updateFact(editingFactId.value, editingContent.value.trim(), undefined, undefined, agentStore.activeAgent?.id)
    editingFactId.value = null
    editingContent.value = ''
  } catch (e) {
    console.error('[DataStatsView] 保存失败:', e)
  }
}

async function handleDeleteFact(factId: string) {
  try {
    await memoryStore.deleteFact(factId, agentStore.activeAgent?.id)
  } catch (e) {
    console.error('[DataStatsView] 删除失败:', e)
  }
}

const handleRefresh = async () => {
  isRefreshing.value = true
  const agentId = agentStore.activeAgent?.id
  await Promise.all([
    memoryStore.fetchMemory(agentId),
    memoryStore.fetchSummary(agentId),
    statsStore.fetchAll(period.value),
  ])
  setTimeout(() => { isRefreshing.value = false }, 600)
}

async function loadData() {
  const agentId = agentStore.activeAgent?.id
  await Promise.all([
    memoryStore.fetchMemory(agentId),
    memoryStore.fetchSummary(agentId),
    statsStore.fetchAll(period.value),
  ])
}

onMounted(() => { loadData() })
watch(() => agentStore.activeAgent?.id, () => { loadData() })
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
          <span class="stat-label">记忆条目</span>
          <span class="stat-value">{{ totalMemoryRecords }}</span>
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
            <Shield :size="14" class="section-icon-muted" />
          </div>

          <div class="memory-stats-grid">
            <div class="memory-stat-item">
              <span class="memory-stat-label">用户空间事实</span>
              <span class="memory-stat-value">{{ userSpaceFacts.length }}</span>
            </div>
            <div class="memory-stat-item">
              <span class="memory-stat-label">Agent 事实</span>
              <span class="memory-stat-value">{{ agentFacts.length }}</span>
            </div>
            <div class="memory-stat-item">
              <span class="memory-stat-label">情景事件</span>
              <span class="memory-stat-value">{{ episodicEvents.length }}</span>
            </div>
            <div class="memory-stat-item">
              <span class="memory-stat-label">工作记忆</span>
              <span class="memory-stat-value">{{ workingMemory ? 'Active' : 'Idle' }}</span>
            </div>
          </div>

          <div class="donut-section">
            <div class="donut-wrap">
              <svg viewBox="0 0 100 100" class="donut-chart">
                <circle cx="50" cy="50" r="40" fill="none" stroke="var(--border)" stroke-width="10" />
                <circle
                  v-for="(seg, idx) in donutSegments"
                  :key="idx"
                  cx="50"
                  cy="50"
                  r="40"
                  fill="none"
                  :stroke="seg.color"
                  stroke-width="10"
                  :stroke-dasharray="seg.dasharray"
                  :stroke-dashoffset="seg.dashoffset"
                  class="donut-anim"
                  :style="{ animationDelay: `${idx * 0.3}s` }"
                />
              </svg>
              <div class="donut-center">
                <span class="dc-value">{{ totalMemoryRecords }}</span>
                <span class="dc-label">总记录</span>
              </div>
            </div>
            <div class="donut-legend">
              <div class="legend-item">
                <span class="legend-dot" style="background: var(--lumi-primary)" />
                <span class="legend-text">工作记忆</span>
                <span class="legend-count">{{ memoryDistribution.working }}</span>
              </div>
              <div class="legend-item">
                <span class="legend-dot" style="background: var(--lumi-success)" />
                <span class="legend-text">情景记忆</span>
                <span class="legend-count">{{ memoryDistribution.episodic }}</span>
              </div>
              <div class="legend-item">
                <span class="legend-dot" style="background: var(--lumi-warning)" />
                <span class="legend-text">语义记忆</span>
                <span class="legend-count">{{ memoryDistribution.semantic }}</span>
              </div>
            </div>
          </div>

          <div class="health-section">
            <div class="health-header">
              <span class="health-label">记忆健康度</span>
              <span class="health-value">{{ memoryHealth }}%</span>
            </div>
            <div class="health-bar-bg">
              <div
                class="health-bar-fill"
                :style="{ width: memoryHealth + '%' }"
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

    <div class="memory-section">
      <div class="memory-section-header">
        <div class="memory-section-left">
          <Brain :size="20" class="section-icon" />
          <h2 class="memory-section-title">记忆中枢</h2>
          <span class="memory-section-badge">v3 · 三层记忆架构</span>
        </div>
        <div class="memory-section-actions">
          <div class="memory-search-bar" :class="{ 'search-expanded': showSearchResults }">
            <Search :size="14" class="search-icon" />
            <input v-model="searchQuery" type="text" placeholder="搜索记忆..." @keydown.enter="handleSearch" />
            <button v-if="showSearchResults" class="search-clear-btn" @click="clearSearch"><X :size="12" /></button>
            <Loader2 v-if="isSearching" :size="13" class="spinning" />
            <button v-else class="search-trigger-btn" @click="handleSearch" :disabled="!searchQuery.trim()"><Search :size="13" /></button>
          </div>
          <button class="memory-h-btn primary" @click="showAddDialog = true">
            <Plus :size="15" /> 添加记忆
          </button>
        </div>
      </div>

      <div class="memory-layer-tabs">
        <div
          v-for="tab in layerTabs"
          :key="tab.id"
          :class="['layer-tab-card', { active: activeTab === tab.id }]"
          :style="{ '--tab-color': tab.color }"
          @click="switchTab(tab.id)"
        >
          <div class="layer-tab-top">
            <div class="layer-tab-icon-wrap" :style="{ background: tab.color + '18' }">
              <component :is="tab.icon" :size="18" :style="{ color: tab.color }" />
            </div>
            <div class="layer-tab-meta">
              <span class="layer-tab-name">{{ tab.name }}</span>
              <span class="layer-tab-sub">{{ tab.sub }}</span>
            </div>
          </div>
          <p class="layer-tab-desc">{{ tab.desc }}</p>
          <div class="layer-tab-stats">
            <span v-if="tab.id === 'user-space'" class="layer-tab-stat">{{ totalUserFacts }} 条事实 · {{ totalEvents }} 条事件</span>
            <span v-else-if="tab.id === 'agent-memory'" class="layer-tab-stat">{{ totalAgentFacts }} 条事实</span>
            <span v-else class="layer-tab-stat">{{ workingMemory?.recent_conversations?.length || 0 }} 条对话</span>
          </div>
        </div>

        <div class="layer-flow">
          <div class="flow-step"><Globe :size="12" /> 全局</div>
          <div class="flow-arrow-line"></div>
          <div class="flow-step"><Lock :size="12" /> 私有</div>
          <div class="flow-arrow-line"></div>
          <div class="flow-step"><MessageSquare :size="12" /> 临时</div>
        </div>
      </div>

      <div class="memory-detail">
        <div v-if="showSearchResults && searchMemoryResults.length > 0" class="search-results-section">
          <div class="memo-section-title">搜索结果 · {{ searchMemoryResults.length }}条</div>
          <div class="memo-items">
            <div v-for="(result, idx) in searchMemoryResults" :key="`search-${idx}`" class="memo-item" :style="{ '--item-delay': `${idx * 0.05}s` }">
              <div class="memo-dot" :style="{ background: getTierColor(result.tier) }"></div>
              <div class="memo-content">
                <p class="memo-text">{{ result.content }}</p>
                <div class="memo-footer">
                  <span class="memo-tag" :style="{ background: getTierColor(result.tier) + '18', color: getTierColor(result.tier) }">{{ getTierLabel(result.tier) }}</span>
                  <span class="memo-tag layer-tag">{{ result.layer === 'user' ? '全局' : '私有' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <template v-if="activeTab === 'user-space'">
          <div class="detail-header">
            <Globe :size="22" :style="{ color: '#8b5cf6' }" />
            <h3>用户空间</h3>
            <span class="detail-sub">UserSpace · 所有Agent共享</span>
          </div>

          <div v-if="hasProfile" class="profile-card">
            <div class="profile-top">
              <div class="profile-avatar">{{ profile?.name?.[0] || '?' }}</div>
              <div class="profile-info">
                <span class="profile-name">{{ profile?.name || '未知用户' }}</span>
                <span v-if="profile?.occupation" class="profile-occ">{{ profile.occupation }}</span>
              </div>
            </div>
            <div class="profile-tags">
              <span v-if="profile?.location" class="p-tag"><Tag :size="10" /> {{ profile.location }}</span>
              <span v-if="profile?.gender" class="p-tag"><Tag :size="10" /> {{ profile.gender }}</span>
              <span v-if="profile?.age" class="p-tag"><Tag :size="10" /> {{ profile.age }}</span>
            </div>
            <div v-if="profile?.interests?.length || profile?.hobbies?.length" class="profile-interests">
              <BookOpen :size="12" />
              <span v-for="i in [...(profile?.interests || []), ...(profile?.hobbies || [])]" :key="i" class="i-tag">{{ i }}</span>
            </div>
          </div>

          <div v-if="userContext && (userContext.work_context?.summary || userContext.personal_context?.summary || userContext.top_of_mind?.summary)" class="context-card">
            <div class="context-card-title"><Activity :size="14" /> 当前上下文</div>
            <div v-if="userContext.work_context?.summary" class="context-row">
              <span class="context-row-label">工作</span>
              <span class="context-row-value">{{ userContext.work_context.summary }}</span>
            </div>
            <div v-if="userContext.personal_context?.summary" class="context-row">
              <span class="context-row-label">个人</span>
              <span class="context-row-value">{{ userContext.personal_context.summary }}</span>
            </div>
            <div v-if="userContext.top_of_mind?.summary" class="context-row">
              <span class="context-row-label">关注</span>
              <span class="context-row-value">{{ userContext.top_of_mind.summary }}</span>
            </div>
          </div>

          <div v-if="hasDistilled" class="distilled-card">
            <div class="distilled-title"><Sparkles :size="14" /> 蒸馏摘要</div>
            <div v-if="distilled?.core_identity" class="distilled-section">
              <span class="distilled-label" :style="{ color: '#8b5cf6' }">核心身份</span>
              <p class="distilled-text">{{ distilled.core_identity }}</p>
            </div>
            <div v-if="distilled?.long_term" class="distilled-section">
              <span class="distilled-label" :style="{ color: '#22c55e' }">长期偏好</span>
              <p class="distilled-text">{{ distilled.long_term }}</p>
            </div>
            <div v-if="distilled?.temporary" class="distilled-section">
              <span class="distilled-label" :style="{ color: '#f59e0b' }">临时上下文</span>
              <p class="distilled-text">{{ distilled.temporary }}</p>
            </div>
            <div v-if="distilled?.events_timeline" class="distilled-section">
              <span class="distilled-label" :style="{ color: '#0ea5e9' }">事件时间线</span>
              <p class="distilled-text">{{ distilled.events_timeline }}</p>
            </div>
          </div>

          <div class="facts-section">
            <div class="memo-section-title">事实记忆 · {{ totalUserFacts }}条</div>
            <div v-if="totalUserFacts === 0" class="empty-section">
              <Archive :size="28" />
              <p>暂无事实记忆</p>
              <p class="empty-hint">对话后AI会自动提取并存储</p>
            </div>
            <template v-else>
              <div v-for="tier in tierOptions" :key="tier.value">
                <div v-if="userSpaceFactsByTier[tier.value]?.length" class="tier-group">
                  <div class="tier-header" :style="{ color: tier.color }">
                    <div class="tier-dot" :style="{ background: tier.color }"></div>
                    {{ tier.label }} · {{ userSpaceFactsByTier[tier.value].length }}条
                  </div>
                  <div class="memo-items">
                    <div v-for="(fact, idx) in userSpaceFactsByTier[tier.value]" :key="fact.id" class="memo-item" :style="{ '--item-delay': `${idx * 0.04}s` }">
                      <div class="memo-dot" :style="{ background: tier.color }"></div>
                      <div class="memo-content">
                        <template v-if="editingFactId === fact.id">
                          <textarea v-model="editingContent" class="edit-textarea" rows="2"></textarea>
                          <div class="edit-actions">
                            <button class="edit-btn save" @click="saveEdit" :disabled="!editingContent.trim()"><Save :size="12" /> 保存</button>
                            <button class="edit-btn cancel" @click="cancelEdit"><X :size="12" /> 取消</button>
                          </div>
                        </template>
                        <template v-else>
                          <p class="memo-text">{{ fact.content }}</p>
                          <div class="memo-footer">
                            <span class="memo-tag" :style="{ background: tier.color + '18', color: tier.color }">{{ tier.label }}</span>
                            <span class="memo-tag category-tag">{{ getCategoryLabel(fact.category) }}</span>
                            <span class="memo-time">{{ formatTimeAgo(fact.created_at) }}</span>
                          </div>
                        </template>
                      </div>
                      <div v-if="editingFactId !== fact.id" class="memo-actions">
                        <button class="memo-action-btn" title="就此对话" @click="chatAboutMemory(fact.content)"><MessageSquare :size="13" /></button>
                        <button class="memo-action-btn" title="编辑" @click="startEdit(fact.id, fact.content)"><Edit3 :size="13" /></button>
                        <button class="memo-action-btn danger" title="删除" @click="handleDeleteFact(fact.id)"><Trash2 :size="13" /></button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <div v-if="episodicEvents.length > 0" class="events-section">
            <div class="memo-section-title">情景事件 · {{ episodicEvents.length }}条</div>
            <div class="memo-items">
              <div v-for="(event, idx) in episodicEvents.slice(0, 15)" :key="event.id" class="memo-item event-item" :style="{ '--item-delay': `${idx * 0.04}s` }">
                <div class="memo-dot" :style="{ background: '#0ea5e9' }"></div>
                <div class="memo-content">
                  <p class="memo-text">{{ event.core_goal }}</p>
                  <div class="memo-footer">
                    <span v-if="event.key_information" class="memo-info">{{ event.key_information }}</span>
                    <span class="memo-time">{{ formatTimeAgo(event.timestamp) }}</span>
                    <span v-for="tag in (event.scene_tags || []).slice(0, 2)" :key="tag" class="memo-tag scene-tag">{{ tag }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <template v-if="activeTab === 'agent-memory'">
          <div class="detail-header">
            <Bot :size="22" :style="{ color: '#0ea5e9' }" />
            <h3>Agent记忆</h3>
            <span class="detail-sub">AgentMemory · {{ agentStore.activeAgent?.name || '未选择' }}</span>
          </div>

          <div v-if="domainSummary" class="distilled-card">
            <div class="distilled-title"><Sparkles :size="14" /> 领域经验摘要</div>
            <p class="distilled-text">{{ domainSummary }}</p>
          </div>

          <div class="facts-section">
            <div class="memo-section-title">Agent专属事实 · {{ totalAgentFacts }}条</div>
            <div v-if="totalAgentFacts === 0" class="empty-section">
              <Archive :size="28" />
              <p>暂无Agent专属记忆</p>
              <p class="empty-hint">对话中提取的Agent特有知识会存放在这里</p>
            </div>
            <div v-else class="memo-items">
              <div v-for="(fact, idx) in agentFacts" :key="fact.id" class="memo-item" :style="{ '--item-delay': `${idx * 0.04}s` }">
                <div class="memo-dot" :style="{ background: '#0ea5e9' }"></div>
                <div class="memo-content">
                  <template v-if="editingFactId === fact.id">
                    <textarea v-model="editingContent" class="edit-textarea" rows="2"></textarea>
                    <div class="edit-actions">
                      <button class="edit-btn save" @click="saveEdit" :disabled="!editingContent.trim()"><Save :size="12" /> 保存</button>
                      <button class="edit-btn cancel" @click="cancelEdit"><X :size="12" /> 取消</button>
                    </div>
                  </template>
                  <template v-else>
                    <p class="memo-text">{{ fact.content }}</p>
                    <div class="memo-footer">
                      <span class="memo-tag" :style="{ background: '#0ea5e918', color: '#0ea5e9' }">{{ getTierLabel(fact.tier) }}</span>
                      <span class="memo-tag category-tag">{{ getCategoryLabel(fact.category) }}</span>
                      <span class="memo-time">{{ formatTimeAgo(fact.created_at) }}</span>
                    </div>
                  </template>
                </div>
                <div v-if="editingFactId !== fact.id" class="memo-actions">
                  <button class="memo-action-btn" title="就此对话" @click="chatAboutMemory(fact.content)"><MessageSquare :size="13" /></button>
                  <button class="memo-action-btn" title="编辑" @click="startEdit(fact.id, fact.content)"><Edit3 :size="13" /></button>
                  <button class="memo-action-btn danger" title="删除" @click="handleDeleteFact(fact.id)"><Trash2 :size="13" /></button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="agentEvents.length > 0" class="events-section">
            <div class="memo-section-title">Agent情景事件 · {{ agentEvents.length }}条</div>
            <div class="memo-items">
              <div v-for="(event, idx) in agentEvents.slice(0, 10)" :key="event.id" class="memo-item event-item" :style="{ '--item-delay': `${idx * 0.04}s` }">
                <div class="memo-dot" :style="{ background: '#0ea5e9' }"></div>
                <div class="memo-content">
                  <p class="memo-text">{{ event.core_goal }}</p>
                  <div class="memo-footer">
                    <span v-if="event.key_information" class="memo-info">{{ event.key_information }}</span>
                    <span class="memo-time">{{ formatTimeAgo(event.timestamp) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <template v-if="activeTab === 'thread-memory'">
          <div class="detail-header">
            <MessageSquare :size="22" :style="{ color: '#f59e0b' }" />
            <h3>对话记忆</h3>
            <span class="detail-sub">ThreadMemory · 当前对话上下文</span>
          </div>

          <div v-if="workingMemory?.core_goal" class="context-card">
            <div class="context-card-title"><Flame :size="14" /> 核心目标</div>
            <p class="context-row-value">{{ workingMemory.core_goal }}</p>
          </div>

          <div v-if="workingMemory?.conversation_summary" class="context-card">
            <div class="context-card-title"><BookOpen :size="14" /> 对话摘要</div>
            <p class="context-row-value">{{ workingMemory.conversation_summary }}</p>
          </div>

          <div v-if="workingMemory?.current_state" class="context-card">
            <div class="context-card-title"><Activity :size="14" /> 当前状态</div>
            <p class="context-row-value">{{ workingMemory.current_state }}</p>
          </div>

          <div v-if="workingMemory?.recent_conversations?.length" class="facts-section">
            <div class="memo-section-title">近期对话 · {{ workingMemory.recent_conversations.length }}条</div>
            <div class="memo-items">
              <div v-for="(msg, idx) in workingMemory.recent_conversations.slice(-10)" :key="`conv-${idx}`" class="memo-item" :style="{ '--item-delay': `${idx * 0.04}s` }">
                <div class="memo-dot" :style="{ background: msg.role === 'user' ? '#8b5cf6' : '#0ea5e9' }"></div>
                <div class="memo-content">
                  <p class="memo-text">{{ msg.role === 'user' ? '用户' : '助手' }}: {{ msg.content }}</p>
                  <div class="memo-footer">
                    <span class="memo-time">{{ formatTimeAgo(msg.timestamp) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="!workingMemory?.core_goal && !workingMemory?.recent_conversations?.length" class="empty-section">
            <Archive :size="28" />
            <p>暂无对话记忆</p>
            <p class="empty-hint">开始对话后，工作记忆会自动记录</p>
          </div>
        </template>
      </div>
    </div>

    <Transition name="dialog-fade">
      <div v-if="showAddDialog" class="dialog-overlay" @click.self="showAddDialog = false">
        <div class="dialog-card">
          <div class="dialog-header">
            <Plus :size="16" />
            <span>添加记忆</span>
            <button class="dialog-close-btn" @click="showAddDialog = false"><X :size="16" /></button>
          </div>
          <div class="dialog-body">
            <textarea v-model="newFactContent" placeholder="输入记忆内容..." rows="3" class="dialog-textarea"></textarea>
            <div class="dialog-row">
              <div class="dialog-field">
                <span class="field-label">分类</span>
                <select v-model="newFactCategory" class="field-select">
                  <option v-for="opt in categoryOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </div>
              <div class="dialog-field">
                <span class="field-label">层级</span>
                <select v-model="newFactLayer" class="field-select">
                  <option value="user">用户空间（全局共享）</option>
                  <option value="agent">Agent记忆（私有）</option>
                </select>
              </div>
            </div>
          </div>
          <div class="dialog-footer">
            <button class="dialog-btn cancel" @click="showAddDialog = false">取消</button>
            <button class="dialog-btn confirm" @click="handleAddFact" :disabled="isAdding || !newFactContent.trim()">
              <Loader2 v-if="isAdding" :size="14" class="spinning" />
              <Plus v-else :size="14" />
              添加
            </button>
          </div>
        </div>
      </div>
    </Transition>
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

.memory-section {
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  padding: 20px;
  animation: content-fade-up 0.6s cubic-bezier(0.4, 0, 0.2, 1) both;
  animation-delay: 0.3s;
}

.memory-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.memory-section-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.memory-section-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.memory-section-badge {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 20px;
  background: var(--task-purple-soft);
  color: var(--task-purple);
  font-weight: 500;
}

.memory-section-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.memory-search-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  border-radius: 10px;
  background: var(--bg);
  border: 1px solid var(--border);
  transition: all 300ms ease-in-out;
}

.memory-search-bar:focus-within,
.memory-search-bar.search-expanded {
  border-color: var(--task-purple);
  box-shadow: 0 0 0 2px var(--task-purple-soft);
}

.memory-search-bar .search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.memory-search-bar input {
  width: 140px;
  font-size: 13px;
  background: transparent;
  color: var(--text);
  border: none;
  outline: none;
}

.memory-search-bar input::placeholder {
  color: var(--text-muted);
}

.search-clear-btn,
.search-trigger-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms;
}

.search-clear-btn:hover,
.search-trigger-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.search-trigger-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.memory-h-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  white-space: nowrap;
}

.memory-h-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.memory-h-btn.primary {
  color: var(--text);
  background: var(--task-purple-soft);
  border: 1px solid var(--task-purple-border);
}

.memory-h-btn.primary:hover {
  background: var(--task-purple-soft);
}

.memory-layer-tabs {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  align-items: stretch;
}

.layer-tab-card {
  flex: 1;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--bg);
  cursor: pointer;
  transition: all 300ms ease-in-out;
}

.layer-tab-card:hover {
  border-color: var(--tab-color);
  box-shadow: 0 4px 20px color-mix(in srgb, var(--tab-color) 10%, transparent);
}

.layer-tab-card.active {
  border-color: var(--tab-color);
  background: color-mix(in srgb, var(--tab-color) 4%, transparent);
}

.layer-tab-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.layer-tab-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.layer-tab-meta {
  flex: 1;
  min-width: 0;
}

.layer-tab-name {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.layer-tab-sub {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
}

.layer-tab-desc {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.5;
  margin-bottom: 6px;
}

.layer-tab-stats {
  font-size: 11px;
  color: var(--text-muted);
  font-family: monospace;
}

.layer-tab-stat {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--surface);
}

.layer-flow {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--task-purple-soft);
  flex-shrink: 0;
  align-self: center;
}

.flow-step {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: var(--text-muted);
  white-space: nowrap;
}

.flow-arrow-line {
  flex: 1;
  height: 1px;
  background: var(--border);
  min-width: 12px;
}

.memory-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.detail-header h3 {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  margin: 0;
}

.detail-sub {
  font-size: 12px;
  color: var(--text-muted);
}

.profile-card {
  padding: 18px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--task-purple-soft), var(--lumi-sky-soft));
  border: 1px solid var(--border);
}

.profile-top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.profile-avatar {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: var(--lumi-accent-glow);
  color: var(--task-purple);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  flex-shrink: 0;
}

.profile-info {
  display: flex;
  flex-direction: column;
}

.profile-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}

.profile-occ {
  font-size: 12px;
  color: var(--text-muted);
}

.profile-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.p-tag {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 8px;
  background: var(--task-purple-soft);
  color: var(--task-purple-light);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;
}

.profile-interests {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.profile-interests > svg {
  color: var(--text-muted);
  flex-shrink: 0;
}

.i-tag {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 8px;
  background: var(--surface);
  color: var(--text-muted);
}

.context-card {
  padding: 16px;
  border-radius: 12px;
  background: var(--bg);
  border: 1px solid var(--border);
}

.context-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 10px;
}

.context-card-title svg {
  color: var(--task-purple);
}

.context-row {
  display: flex;
  gap: 10px;
  margin-bottom: 6px;
  font-size: 13px;
}

.context-row-label {
  color: var(--text-muted);
  flex-shrink: 0;
  min-width: 32px;
}

.context-row-value {
  color: var(--text);
  line-height: 1.5;
}

.distilled-card {
  padding: 16px;
  border-radius: 12px;
  background: var(--bg);
  border: 1px solid var(--border);
}

.distilled-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 12px;
}

.distilled-title svg {
  color: var(--lumi-amber);
}

.distilled-section {
  margin-bottom: 10px;
}

.distilled-label {
  font-size: 12px;
  font-weight: 600;
  display: block;
  margin-bottom: 4px;
}

.distilled-text {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.6;
  margin: 0;
}

.memo-section-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text);
}

.empty-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--text-muted);
}

.empty-section svg {
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-section p {
  font-size: 14px;
  margin-bottom: 4px;
}

.empty-hint {
  font-size: 12px !important;
  opacity: 0.7;
}

.tier-group {
  margin-bottom: 16px;
}

.tier-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
}

.tier-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.memo-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.memo-item {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--bg);
  border: 1px solid transparent;
  transition: all 300ms ease-in-out;
  opacity: 0;
  animation: memo-in 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: var(--item-delay);
}

@keyframes memo-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

.memo-item:hover {
  border-color: var(--border);
}

.memo-item:hover .memo-actions {
  opacity: 1;
}

.memo-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  margin-top: 7px;
  flex-shrink: 0;
}

.memo-content {
  flex: 1;
  min-width: 0;
}

.memo-text {
  font-size: 13px;
  color: var(--text);
  line-height: 1.5;
  margin-bottom: 4px;
}

.memo-footer {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.memo-tag {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 8px;
  background: var(--task-purple-soft);
  color: var(--task-purple);
  font-weight: 500;
}

.memo-tag.category-tag {
  background: var(--lumi-amber-soft);
  color: var(--lumi-amber-dark);
}

.memo-tag.layer-tag {
  background: var(--lumi-sky-soft);
  color: var(--lumi-sky);
}

.memo-tag.scene-tag {
  background: var(--task-green-soft);
  color: var(--lumi-success-dark);
}

.memo-info {
  font-size: 11px;
  color: var(--text-muted);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.memo-time {
  font-size: 11px;
  color: var(--text-muted);
}

.memo-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  opacity: 0;
  transition: opacity 200ms;
  flex-shrink: 0;
}

.memo-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms;
}

.memo-action-btn:hover {
  background: var(--surface-hover);
  color: var(--lumi-primary);
}

.memo-action-btn.danger:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.edit-textarea {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  resize: vertical;
  font-family: inherit;
  outline: none;
}

.edit-textarea:focus {
  border-color: var(--task-purple);
}

.edit-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.edit-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 200ms;
}

.edit-btn.save {
  background: var(--task-purple-soft);
  color: var(--task-purple);
}

.edit-btn.save:hover {
  background: var(--task-purple-border);
}

.edit-btn.save:disabled {
  opacity: 0.5;
  cursor: default;
}

.edit-btn.cancel {
  background: var(--surface-hover);
  color: var(--text-muted);
}

.edit-btn.cancel:hover {
  color: var(--text);
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: var(--overlay-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.dialog-card {
  width: 480px;
  max-width: 90vw;
  background: var(--bg);
  border-radius: 16px;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.dialog-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.dialog-close-btn {
  margin-left: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
}

.dialog-close-btn:hover {
  background: var(--surface-hover);
}

.dialog-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dialog-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  resize: none;
  font-family: inherit;
  outline: none;
}

.dialog-textarea:focus {
  border-color: var(--task-purple);
}

.dialog-textarea::placeholder {
  color: var(--text-muted);
}

.dialog-row {
  display: flex;
  gap: 12px;
}

.dialog-field {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 12px;
  color: var(--text-muted);
}

.field-select {
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  outline: none;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 14px 20px;
  border-top: 1px solid var(--border);
}

.dialog-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 200ms;
}

.dialog-btn.cancel {
  background: var(--surface);
  color: var(--text-muted);
}

.dialog-btn.cancel:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.dialog-btn.confirm {
  background: var(--task-purple-soft);
  color: var(--task-purple);
  border: 1px solid var(--task-purple-border);
}

.dialog-btn.confirm:hover {
  background: var(--task-purple-border);
}

.dialog-btn.confirm:disabled {
  opacity: 0.5;
  cursor: default;
}

.dialog-fade-enter-active {
  animation: fade-in 0.25s ease-out;
}

.dialog-fade-enter-active .dialog-card {
  animation: scale-in 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.dialog-fade-leave-active {
  animation: fade-in 0.2s ease-out reverse;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes scale-in {
  from { opacity: 0; transform: scale(0.92); }
  to { opacity: 1; transform: scale(1); }
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
</style>
