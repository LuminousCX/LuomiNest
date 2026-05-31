<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  LayoutDashboard,
  Cpu,
  Key,
  Globe,
  Palette,
  Mic,
  Music,
  BarChart3,
  Activity,
  Database,
  Terminal,
  Zap,
  Server,
  Shield,
  ChevronRight,
  Play,
  Square,
  RotateCcw,
  Copy,
  Download,
  Settings2,
  Sparkles,
  Brain,
  Layers,
  ArrowUpRight,
  ArrowDownRight,
  MoreHorizontal,
  RefreshCw,
  Volume2,
  Wand2,
  UserCircle,
} from 'lucide-vue-next'

const currentTime = ref(new Date())
let timeInterval: ReturnType<typeof setInterval>

const greeting = computed(() => {
  const hour = currentTime.value.getHours()
  if (hour < 6) return '夜深了'
  if (hour < 9) return '早上好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  if (hour < 22) return '晚上好'
  return '夜深了'
})

const formattedDate = computed(() => {
  const d = currentTime.value
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ${weekdays[d.getDay()]}`
})

onMounted(() => {
  timeInterval = setInterval(() => { currentTime.value = new Date() }, 1000)
})

onUnmounted(() => {
  if (timeInterval) clearInterval(timeInterval)
})

interface ModelProvider {
  id: string
  name: string
  icon: string
  status: 'active' | 'inactive' | 'error'
  model: string
  endpoint: string
  requests: number
  latency: number
  color: string
}

const modelProviders = ref<ModelProvider[]>([
  { id: 'openai', name: 'OpenAI', icon: 'OAI', status: 'active', model: 'GPT-4o', endpoint: 'https://api.openai.com/v1', requests: 12847, latency: 234, color: '#10a37f' },
  { id: 'anthropic', name: 'Anthropic', icon: 'ANT', status: 'active', model: 'Claude 3.5 Sonnet', endpoint: 'https://api.anthropic.com/v1', requests: 8234, latency: 189, color: '#d4a574' },
  { id: 'deepseek', name: 'DeepSeek', icon: 'DSK', status: 'active', model: 'DeepSeek-V3', endpoint: 'https://api.deepseek.com/v1', requests: 5621, latency: 312, color: '#4d6bfe' },
  { id: 'ollama', name: 'Ollama Local', icon: 'OLL', status: 'inactive', model: 'Llama 3.1', endpoint: 'http://localhost:11434', requests: 0, latency: 0, color: '#6c757d' },
])

interface PersonaConfig {
  id: string
  name: string
  avatar: string
  style: string
  voice: string
  tone: string
  active: boolean
}

const personas = ref<PersonaConfig[]>([
  { id: 'p1', name: '辰汐 · 默认', avatar: '默认形象', style: '温柔知性', voice: '甜美女声', tone: '温暖亲切', active: true },
  { id: 'p2', name: '辰汐 · 活泼', avatar: '活力少女', style: '元气满满', voice: '活泼女声', tone: '开朗热情', active: false },
  { id: 'p3', name: '辰汐 · 冷静', avatar: '高冷御姐', style: '简约优雅', voice: '成熟女声', tone: '沉稳冷静', active: false },
])

interface UsageMetric {
  label: string
  value: number | string
  unit: string
  change: number
  trend: 'up' | 'down'
  color: string
}

const apiUsageMetrics = ref<UsageMetric[]>([
  { label: '今日请求', value: 26702, unit: '次', change: 12.5, trend: 'up', color: 'var(--lumi-primary)' },
  { label: 'Token 消耗', value: '2.84M', unit: '', change: 8.3, trend: 'up', color: '#22c55e' },
  { label: '平均延迟', value: 245, unit: 'ms', change: -5.2, trend: 'down', color: '#f59e0b' },
  { label: '成功率', value: 99.7, unit: '%', change: 0.3, trend: 'up', color: '#8b5cf6' },
])

const memoryMetrics = ref<UsageMetric[]>([
  { label: '工作记忆', value: 67, unit: '/100', change: 3.1, trend: 'up', color: '#f59e0b' },
  { label: '情景记忆', value: 34, unit: '/50', change: -2.0, trend: 'down', color: '#22c55e' },
  { label: '语义记忆', value: 428, unit: '/500', change: 15.6, trend: 'up', color: '#8b5cf6' },
  { label: '记忆健康度', value: 94, unit: '%', change: 1.2, trend: 'up', color: 'var(--lumi-primary)' },
])

const contextMetrics = ref<UsageMetric[]>([
  { label: '当前上下文', value: 8192, unit: 'tokens', change: 12.0, trend: 'up', color: 'var(--lumi-primary)' },
  { label: '窗口使用率', value: 68, unit: '%', change: -3.5, trend: 'down', color: '#f59e0b' },
  { label: '对话轮次', value: 24, unit: '轮', change: 8.0, trend: 'up', color: '#22c55e' },
  { label: '压缩次数', value: 3, unit: '次', change: 0, trend: 'up', color: '#8b5cf6' },
])

interface LogEntry {
  id: number
  timestamp: string
  level: 'info' | 'warn' | 'error' | 'success'
  source: string
  message: string
}

const consoleLogs = ref<LogEntry[]>([
  { id: 1, timestamp: '14:32:01', level: 'info', source: 'Core', message: '[LuomiNest] 系统初始化完成，所有模块已加载' },
  { id: 2, timestamp: '14:32:03', level: 'success', source: 'Memory', message: '[MemCell] 记忆引擎就绪 · 三层架构已激活' },
  { id: 3, timestamp: '14:32:05', level: 'info', source: 'Model', message: '[Provider] OpenAI GPT-4o 连接成功 · latency=234ms' },
  { id: 4, timestamp: '14:32:06', level: 'info', source: 'Model', message: '[Provider] Anthropic Claude 3.5 连接成功 · latency=189ms' },
  { id: 5, timestamp: '14:32:08', level: 'success', source: 'Avatar', message: '[Live2D] 皮套渲染器初始化完成 · 模型=v2.1' },
  { id: 6, timestamp: '14:33:15', level: 'info', source: 'Chat', message: '[Session] 新建会话 #conv-a7x9k · Agent=辰汐' },
  { id: 7, timestamp: '14:33:42', level: 'info', source: 'LLM', message: '[Request] POST /v1/chat/completions · tokens_in=128 tokens_out=512' },
  { id: 8, timestamp: '14:34:18', level: 'warn', source: 'Memory', message: '[Episodic] 工作记忆容量达到 67%，建议进行记忆压缩' },
  { id: 9, timestamp: '14:35:02', level: 'info', source: 'RAG', message: '[Vector] 向量检索完成 · 命中 3 条相关记忆 · score>0.85' },
  { id: 10, timestamp: '14:35:30', level: 'success', source: 'Core', message: '[Health] 系统运行正常 · uptime=2h34m · CPU=23% MEM=45%' },
])

const consoleInput = ref('')
const isConsoleRunning = ref(false)

const activeTab = ref('overview')
const tabs = [
  { id: 'overview', label: '总览', icon: LayoutDashboard },
  { id: 'model', label: '模型配置', icon: Cpu },
  { id: 'persona', label: '皮套工坊', icon: Palette },
  { id: 'usage', label: '用量统计', icon: BarChart3 },
  { id: 'console', label: '控制台', icon: Terminal },
]

function getLogLevelStyle(level: string) {
  const map: Record<string, { bg: string; text: string; dot: string }> = {
    info: { bg: 'rgba(20,126,188,0.1)', text: 'var(--lumi-primary)', dot: 'var(--lumi-primary)' },
    warn: { bg: 'rgba(234,179,8,0.1)', text: '#eab308', dot: '#eab308' },
    error: { bg: 'rgba(244,63,94,0.1)', text: '#ef4444', dot: '#ef4444' },
    success: { bg: 'rgba(34,197,94,0.1)', text: '#22c55e', dot: '#22c55e' },
  }
  return map[level] || map.info
}

function handleConsoleCommand() {
  if (!consoleInput.value.trim()) return
  consoleLogs.value.push({
    id: Date.now(),
    timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
    level: 'info',
    source: 'CMD',
    message: `> ${consoleInput.value}`,
  })
  consoleInput.value = ''
}

function clearConsole() {
  consoleLogs.value = []
}
</script>

<template>
  <div class="dashboard-view">
    <div class="dash-header">
      <div class="header-left">
        <div class="greeting-block">
          <div class="greeting-icon">
            <Sparkles :size="18" />
          </div>
          <div class="greeting-text">
            <span class="greeting-label">{{ greeting }}，LuminousChenXi</span>
            <span class="greeting-date">{{ formattedDate }}</span>
          </div>
        </div>
      </div>
      <div class="header-center">
        <div class="tab-nav">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            :class="['tab-btn', { active: activeTab === tab.id }]"
            @click="activeTab = tab.id"
          >
            <component :is="tab.icon" :size="15" />
            <span>{{ tab.label }}</span>
          </button>
        </div>
      </div>
      <div class="header-right">
        <button class="header-action-btn" title="刷新数据">
          <RefreshCw :size="16" />
        </button>
        <button class="header-action-btn" title="设置">
          <Settings2 :size="16" />
        </button>
      </div>
    </div>

    <div class="dash-body">
      <div v-show="activeTab === 'overview'" class="tab-content animate-fade-in">
        <section class="dash-section overview-top">
          <div class="stat-cards-row">
            <div v-for="(metric, idx) in [...apiUsageMetrics.slice(0, 2), ...memoryMetrics.slice(0, 2)]" :key="metric.label"
              class="stat-card" :style="{ '--card-delay': `${idx * 0.08}s`, '--accent-color': metric.color }">
              <div class="stat-card-header">
                <span class="stat-label">{{ metric.label }}</span>
                <component :is="metric.trend === 'up' ? ArrowUpRight : ArrowDownRight" :size="16"
                  :class="['trend-icon', metric.trend]" />
              </div>
              <div class="stat-card-body">
                <span class="stat-value">{{ metric.value }}</span>
                <span class="stat-unit">{{ metric.unit }}</span>
              </div>
              <div class="stat-card-footer">
                <span :class="['change-badge', metric.trend]">
                  {{ metric.trend === 'up' ? '+' : '' }}{{ metric.change }}%
                </span>
                <span class="change-label">较昨日</span>
              </div>
              <div class="stat-card-glow" />
            </div>
          </div>
        </section>

        <section class="dash-section main-grid">
          <div class="grid-left">
            <div class="panel-card model-panel">
              <div class="panel-header">
                <div class="panel-title-group">
                  <Cpu :size="18" class="panel-icon" style="color: var(--lumi-primary)" />
                  <h3>模型配置</h3>
                  <span class="panel-badge">Model Providers</span>
                </div>
                <button class="panel-action-btn">
                  <Settings2 :size="14" />
                </button>
              </div>
              <div class="provider-list">
                <div v-for="provider in modelProviders" :key="provider.id"
                  :class="['provider-item', { inactive: provider.status !== 'active' }]"
                  :style="{ '--provider-color': provider.color }">
                  <div class="provider-avatar">
                    <span>{{ provider.icon }}</span>
                  </div>
                  <div class="provider-info">
                    <div class="provider-name-row">
                      <span class="provider-name">{{ provider.name }}</span>
                      <span :class="['status-dot', provider.status]" />
                    </div>
                    <span class="provider-model">{{ provider.model }}</span>
                  </div>
                  <div class="provider-stats">
                    <div class="mini-stat">
                      <Globe :size="11" />
                      <span>{{ provider.requests.toLocaleString() }}</span>
                    </div>
                    <div class="mini-stat">
                      <Zap :size="11" />
                      <span>{{ provider.latency }}ms</span>
                    </div>
                  </div>
                  <ChevronRight :size="16" class="provider-arrow" />
                </div>
              </div>
            </div>

            <div class="panel-card persona-panel">
              <div class="panel-header">
                <div class="panel-title-group">
                  <Palette :size="18" class="panel-icon" style="color: #ec4899" />
                  <h3>皮套工坊</h3>
                  <span class="panel-badge pink">Avatar Studio</span>
                </div>
                <button class="panel-action-btn primary">
                  <Wand2 :size="14" />
                  <span>自定义</span>
                </button>
              </div>
              <div class="persona-grid">
                <div v-for="p in personas" :key="p.id" :class="['persona-card', { active: p.active }]">
                  <div class="persona-avatar-preview">
                    <UserCircle :size="36" />
                    <div v-if="p.active" class="active-ring" />
                  </div>
                  <div class="persona-detail">
                    <span class="persona-name">{{ p.name }}</span>
                    <div class="persona-tags">
                      <span class="p-tag"><Mic :size="10" /> {{ p.voice }}</span>
                      <span class="p-tag"><Music :size="10" /> {{ p.tone }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="grid-right">
            <div class="panel-card chart-panel">
              <div class="panel-header">
                <div class="panel-title-group">
                  <BarChart3 :size="18" class="panel-icon" style="color: #22c55e" />
                  <h3>用量统计</h3>
                  <span class="panel-badge green">Live</span>
                </div>
                <div class="chart-period-selector">
                  <button class="period-btn active">7天</button>
                  <button class="period-btn">30天</button>
                  <button class="period-btn">90天</button>
                </div>
              </div>

              <div class="chart-area">
                <div class="big-chart-svg-wrap">
                  <svg viewBox="0 0 400 160" class="area-chart" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="chartGrad1" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="var(--lumi-primary)" stop-opacity="0.3" />
                        <stop offset="100%" stop-color="var(--lumi-primary)" stop-opacity="0.02" />
                      </linearGradient>
                      <linearGradient id="chartGrad2" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="#22c55e" stop-opacity="0.25" />
                        <stop offset="100%" stop-color="#22c55e" stop-opacity="0.02" />
                      </linearGradient>
                    </defs>
                    <path d="M0,140 Q40,120 80,100 T160,70 T240,90 T320,50 T400,35 L400,160 L0,160 Z"
                      fill="url(#chartGrad1)" class="chart-area-fill" />
                    <path d="M0,140 Q40,120 80,100 T160,70 T240,90 T320,50 T400,35"
                      fill="none" stroke="var(--lumi-primary)" stroke-width="2.5" stroke-linecap="round"
                      class="chart-line animate-draw" />
                    <path d="M0,150 Q50,135 100,125 T200,110 T300,95 T400,80 L400,160 L0,160 Z"
                      fill="url(#chartGrad2)" class="chart-area-fill" style="animation-delay: 0.3s" />
                    <path d="M0,150 Q50,135 100,125 T200,110 T300,95 T400,80"
                      fill="none" stroke="#22c55e" stroke-width="2" stroke-linecap="round"
                      class="chart-line animate-draw" style="animation-delay: 0.3s" />
                    <circle cx="400" cy="35" r="4" fill="var(--lumi-primary)" class="chart-dot pulse-dot" />
                    <circle cx="400" cy="80" r="4" fill="#22c55e" class="chart-dot pulse-dot" style="animation-delay: 0.5s" />
                  </svg>
                  <div class="chart-overlay-stats">
                    <div class="overlay-stat primary">
                      <span class="os-label">API 请求</span>
                      <span class="os-value">26,702</span>
                      <span class="os-trend up">+12.5%</span>
                    </div>
                    <div class="overlay-stat success">
                      <span class="os-label">Token 消耗</span>
                      <span class="os-value">2.84M</span>
                      <span class="os-trend up">+8.3%</span>
                    </div>
                  </div>
                </div>

                <div class="chart-x-axis">
                  <span v-for="day in ['周一', '周二', '周三', '周四', '周五', '周六', '周日']" :key="day">{{ day }}</span>
                </div>
              </div>

              <div class="usage-mini-grid">
                <div v-for="m in [...apiUsageMetrics, ...contextMetrics].slice(0, 4)" :key="m.label"
                  class="usage-mini-item">
                  <div class="umi-top">
                    <span class="umi-label">{{ m.label }}</span>
                    <span :class="['umi-change', m.trend]">
                      <component :is="m.trend === 'up' ? ArrowUpRight : ArrowDownRight" :size="11" />
                      {{ Math.abs(m.change) }}%
                    </span>
                  </div>
                  <div class="umi-bar-track">
                    <div class="umi-bar-fill" :style="{ width: typeof m.value === 'number' ? Math.min(100, m.value / (m.unit.includes('ms') ? 500 : m.unit.includes('%') ? 100 : m.unit.includes('tokens') ? 16384 : 100)) + '%' : '65%', background: m.color }" />
                  </div>
                  <span class="umi-value">{{ m.value }}{{ m.unit }}</span>
                </div>
              </div>
            </div>

            <div class="panel-card console-panel">
              <div class="panel-header">
                <div class="panel-title-group">
                  <Terminal :size="18" class="panel-icon" style="color: #f59e0b" />
                  <h3>控制台</h3>
                  <span class="panel-badge yellow">Real-time</span>
                </div>
                <div class="console-actions">
                  <button class="panel-action-btn" title="清空日志" @click="clearConsole">
                    <RotateCcw :size="13" />
                  </button>
                  <button class="panel-action-btn" title="复制全部">
                    <Copy :size="13" />
                  </button>
                </div>
              </div>
              <div class="console-log-area">
                <div v-for="log in consoleLogs" :key="log.id" class="log-entry"
                  :style="{ '--log-bg': getLogLevelStyle(log.level).bg, '--log-text': getLogLevelStyle(log.level).text, '--log-dot': getLogLevelStyle(log.level).dot }">
                  <span class="log-time">{{ log.timestamp }}</span>
                  <span class="log-level-dot" />
                  <span class="log-source">[{{ log.source }}]</span>
                  <span class="log-message">{{ log.message }}</span>
                </div>
              </div>
              <div class="console-input-row">
                <span class="console-prompt">$ luominest</span>
                <input v-model="consoleInput" type="text" class="console-input"
                  placeholder="输入命令... (help 查看帮助)" @keydown.enter="handleConsoleCommand" />
                <button class="console-send-btn" @click="handleConsoleCommand" :disabled="!consoleInput.trim()">
                  <Play :size="14" />
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div v-show="activeTab === 'model'" class="tab-content animate-fade-in">
        <section class="dash-section full-panel">
          <div class="panel-card full-height">
            <div class="panel-header">
              <div class="panel-title-group">
                <Cpu :size="20" class="panel-icon" style="color: var(--lumi-primary)" />
                <h3>模型配置中心</h3>
              </div>
              <button class="panel-action-btn primary">
                <Plus :size="14" /> 添加供应商
              </button>
            </div>
            <div class="model-config-grid">
              <div v-for="provider in modelProviders" :key="provider.id"
                :class="['model-config-card', `status-${provider.status}`]"
                :style="{ '--pc-color': provider.color }">
                <div class="mc-header">
                  <div class="mc-brand" :style="{ background: provider.color + '15' }">
                    <span :style="{ color: provider.color }">{{ provider.icon }}</span>
                  </div>
                  <div class="mc-meta">
                    <span class="mc-name">{{ provider.name }}</span>
                    <span :class="['mc-status', provider.status]">
                      {{ provider.status === 'active' ? '在线' : provider.status === 'error' ? '异常' : '离线' }}
                    </span>
                  </div>
                  <MoreHorizontal :size="16" class="mc-menu" />
                </div>
                <div class="mc-fields">
                  <div class="mc-field">
                    <label><Key :size="12" /> API Key</label>
                    <div class="mc-input-mock">sk-••••••••••••••••a7x9k</div>
                  </div>
                  <div class="mc-field">
                    <label><Globe :size="12" /> 端点地址</label>
                    <div class="mc-input-mock">{{ provider.endpoint }}</div>
                  </div>
                  <div class="mc-field">
                    <label><Server :size="12" /> 当前模型</label>
                    <div class="mc-input-mock highlight">{{ provider.model }}</div>
                  </div>
                  <div class="mc-field">
                    <label><Shield :size="12" /> 请求方式</label>
                    <div class="mc-input-mock">REST API · Stream</div>
                  </div>
                  <div class="mc-field">
                    <label><Layers :size="12" /> 上下文窗口</label>
                    <div class="mc-progress-bar">
                      <div class="mc-progress-fill" :style="{ width: '68%', background: provider.color }" />
                      <span>128K · 已用 68%</span>
                    </div>
                  </div>
                </div>
                <div class="mc-footer">
                  <div class="mc-footer-stat">
                    <Activity :size="13" />
                    <span>{{ provider.requests.toLocaleString() }} 次请求</span>
                  </div>
                  <div class="mc-footer-stat">
                    <Zap :size="13" />
                    <span>{{ provider.latency }}ms 延迟</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div v-show="activeTab === 'persona'" class="tab-content animate-fade-in">
        <section class="dash-section full-panel">
          <div class="panel-card full-height">
            <div class="panel-header">
              <div class="panel-title-group">
                <Palette :size="20" class="panel-icon" style="color: #ec4899" />
                <h3>皮套工坊</h3>
                <span class="panel-badge pink">Avatar Workshop</span>
              </div>
              <button class="panel-action-btn primary">
                <Wand2 :size="14" /> 创建新皮套
              </button>
            </div>
            <div class="persona-workshop-grid">
              <div v-for="p in personas" :key="p.id" :class="['pw-card', { active: p.active }]">
                <div class="pw-visual">
                  <div class="pw-avatar-large">
                    <UserCircle :size="64" />
                  </div>
                  <div v-if="p.active" class="pw-active-badge">
                    <Sparkles :size="12" /> 使用中
                  </div>
                </div>
                <div class="pw-info">
                  <h4>{{ p.name }}</h4>
                  <p>{{ p.style }} 风格</p>
                </div>
                <div class="pw-config-list">
                  <div class="pw-config-item">
                    <UserCircle :size="14" />
                    <span>形象：{{ p.avatar }}</span>
                  </div>
                  <div class="pw-config-item">
                    <Volume2 :size="14" />
                    <span>语音：{{ p.voice }}</span>
                  </div>
                  <div class="pw-config-item">
                    <Music :size="14" />
                    <span>音色：{{ p.tone }}</span>
                  </div>
                </div>
                <button :class="['pw-action-btn', { active: p.active }]">
                  {{ p.active ? '正在使用' : '切换使用' }}
                </button>
              </div>
              <div class="pw-card add-new">
                <div class="add-new-content">
                  <Plus :size="32" />
                  <span>创建新皮套</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div v-show="activeTab === 'usage'" class="tab-content animate-fade-in">
        <section class="dash-section full-panel">
          <div class="panel-card full-height">
            <div class="panel-header">
              <div class="panel-title-group">
                <BarChart3 :size="20" class="panel-icon" style="color: #22c55e" />
                <h3>用量统计分析</h3>
              </div>
              <div class="chart-period-selector">
                <button class="period-btn">今天</button>
                <button class="period-btn active">7天</button>
                <button class="period-btn">30天</button>
                <button class="period-btn">自定义</button>
              </div>
            </div>
            <div class="usage-detail-grid">
              <div class="ud-card">
                <div class="ud-header">
                  <Database :size="18" style="color: var(--lumi-primary)" />
                  <h4>API 用量</h4>
                </div>
                <div class="ud-chart-placeholder large">
                  <svg viewBox="0 0 300 120" class="bar-chart-svg">
                    <rect v-for="(h, i) in [45, 72, 58, 88, 64, 95, 78]" :key="i"
                      :x="i * 38 + 10" :y="120 - h" width="24" :height="h" rx="4"
                      fill="var(--lumi-primary)" :opacity="0.3 + (i * 0.1)"
                      class="bar-anim" :style="{ animationDelay: `${i * 0.1}s` }" />
                  </svg>
                </div>
                <div class="ud-stats-row">
                  <div v-for="m in apiUsageMetrics" :key="m.label" class="ud-stat">
                    <span class="ud-stat-label">{{ m.label }}</span>
                    <span class="ud-stat-value" :style="{ color: m.color }">{{ m.value }}{{ m.unit }}</span>
                    <span :class="['ud-stat-trend', m.trend]">
                      {{ m.trend === 'up' ? '+' : '' }}{{ m.change }}%
                    </span>
                  </div>
                </div>
              </div>
              <div class="ud-card">
                <div class="ud-header">
                  <Brain :size="18" style="color: #8b5cf6" />
                  <h4>记忆用量</h4>
                </div>
                <div class="ud-chart-placeholder donut-wrap">
                  <svg viewBox="0 0 100 100" class="donut-chart">
                    <circle cx="50" cy="50" r="40" fill="none" stroke="var(--border)" stroke-width="10" />
                    <circle cx="50" cy="50" r="40" fill="none" stroke="#f59e0b" stroke-width="10"
                      stroke-dasharray="167 251" stroke-dashoffset="0" class="donut-anim" />
                    <circle cx="50" cy="50" r="40" fill="none" stroke="#22c55e" stroke-width="10"
                      stroke-dasharray="107 251" stroke-dashoffset="-167" class="donut-anim" style="animation-delay: 0.3s" />
                    <circle cx="50" cy="50" r="40" fill="none" stroke="#8b5cf6" stroke-width="10"
                      stroke-dasharray="215 251" stroke-dashoffset="-274" class="donut-anim" style="animation-delay: 0.6s" />
                  </svg>
                  <div class="donut-center">
                    <span class="dc-value">529</span>
                    <span class="dc-label">总记录</span>
                  </div>
                </div>
                <div class="ud-legend">
                  <div class="legend-item"><span class="legend-dot" style="background:#f59e0b" />工作 67</div>
                  <div class="legend-item"><span class="legend-dot" style="background:#22c55e" />情景 34</div>
                  <div class="legend-item"><span class="legend-dot" style="background:#8b5cf6" />语义 428</div>
                </div>
              </div>
              <div class="ud-card wide">
                <div class="ud-header">
                  <Layers :size="18" style="color: #f59e0b" />
                  <h4>上下文监控</h4>
                </div>
                <div class="ctx-bars">
                  <div v-for="m in contextMetrics" :key="m.label" class="ctx-bar-item">
                    <div class="cbi-labels">
                      <span class="cbi-name">{{ m.label }}</span>
                      <span class="cbi-val">{{ m.value }}{{ m.unit }}</span>
                    </div>
                    <div class="cbi-bar-track">
                      <div class="cbi-bar-fill" :style="{
                        width: typeof m.value === 'number' ? Math.min(100, m.value / (m.unit.includes('tokens') ? 16384 : m.unit.includes('%') ? 100 : 50)) + '%' : '60%',
                        background: m.color
                      }" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div v-show="activeTab === 'console'" class="tab-content animate-fade-in">
        <section class="dash-section full-panel">
          <div class="panel-card full-height console-full">
            <div class="panel-header">
              <div class="panel-title-group">
                <Terminal :size="20" class="panel-icon" style="color: #f59e0b" />
                <h3>系统控制台</h3>
                <span class="panel-badge yellow">{{ consoleLogs.length }} 条日志</span>
              </div>
              <div class="console-toolbar">
                <button class="panel-action-btn" @click="clearConsole">
                  <RotateCcw :size="14" /> 清空
                </button>
                <button class="panel-action-btn">
                  <Download :size="14" /> 导出
                </button>
                <button :class="['panel-action-btn', { running: isConsoleRunning }]" @click="isConsoleRunning = !isConsoleRunning">
                  <component :is="isConsoleRunning ? Square : Play" :size="14" />
                  {{ isConsoleRunning ? '暂停' : '实时' }}
                </button>
              </div>
            </div>
            <div class="console-main">
              <div class="console-log-area full-log">
                <div v-for="log in consoleLogs" :key="log.id" class="log-entry"
                  :style="{ '--log-bg': getLogLevelStyle(log.level).bg, '--log-text': getLogLevelStyle(log.level).text, '--log-dot': getLogLevelStyle(log.level).dot }">
                  <span class="log-time">{{ log.timestamp }}</span>
                  <span class="log-level-badge" :class="log.level">{{ log.level.toUpperCase() }}</span>
                  <span class="log-source">[{{ log.source }}]</span>
                  <span class="log-message">{{ log.message }}</span>
                </div>
              </div>
            </div>
            <div class="console-input-area">
              <div class="console-input-row full-width">
                <span class="console-prompt">$ luominest<span class="prompt-blink">_</span></span>
                <input v-model="consoleInput" type="text" class="console-input flex-grow"
                  placeholder="输入命令或查询... 按 Enter 执行，Tab 自动补全" @keydown.enter="handleConsoleCommand" />
                <button class="console-send-btn" @click="handleConsoleCommand" :disabled="!consoleInput.trim()">
                  <Play :size="14" />
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  overflow: hidden;
}

.dash-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  background: var(--surface);
  gap: 20px;
}

.header-left {
  flex-shrink: 0;
}

.greeting-block {
  display: flex;
  align-items: center;
  gap: 12px;
}

.greeting-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--lumi-primary), var(--lumi-primary-soft));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-inverse);
  box-shadow: 0 4px 12px var(--lumi-primary-border);
}

.greeting-text {
  display: flex;
  flex-direction: column;
}

.greeting-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.greeting-date {
  font-size: 11px;
  color: var(--text-muted);
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.tab-nav {
  display: flex;
  gap: 2px;
  background: var(--bg-secondary);
  border-radius: 10px;
  padding: 3px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 250ms ease-in-out;
  white-space: nowrap;
}

.tab-btn:hover {
  color: var(--text-secondary);
  background: var(--surface-hover);
}

.tab-btn.active {
  color: var(--lumi-primary);
  background: var(--surface);
  box-shadow: var(--shadow-xs);
}

.header-right {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.header-action-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms ease-in-out;
}

.header-action-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.dash-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.dash-section {
  display: flex;
  flex-direction: column;
}

.stat-cards-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  position: relative;
  padding: 20px;
  border-radius: 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  overflow: hidden;
  opacity: 0;
  animation: statCardIn 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: var(--card-delay);
  transition: all 250ms ease-in-out;
}

@keyframes statCardIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.stat-card:hover {
  border-color: var(--accent-color);
  box-shadow: 0 4px 20px color-mix(in srgb, var(--accent-color) 10%, transparent);
  transform: translateY(-2px);
}

.stat-card-glow {
  position: absolute;
  top: -40px;
  right: -40px;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: radial-gradient(circle, color-mix(in srgb, var(--accent-color) 12%, transparent) 0%, transparent 70%);
  pointer-events: none;
}

.stat-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.trend-icon {
  color: var(--text-muted);
}

.trend-icon.up { color: var(--lumi-success); }
.trend-icon.down { color: var(--lumi-danger); }

.stat-card-body {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 12px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text);
  line-height: 1;
}

.stat-unit {
  font-size: 13px;
  color: var(--text-muted);
}

.stat-card-footer {
  display: flex;
  align-items: center;
  gap: 8px;
}

.change-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
}

.change-badge.up { background: var(--task-green-soft); color: var(--lumi-success); }
.change-badge.down { background: var(--task-red-soft); color: var(--lumi-danger); }

.change-label {
  font-size: 11px;
  color: var(--text-muted);
}

.main-grid {
  display: grid;
  grid-template-columns: 1fr 1.3fr;
  gap: 20px;
}

.grid-left {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.grid-right {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.panel-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.panel-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-icon {
  flex-shrink: 0;
}

.panel-title-group h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.panel-badge {
  font-size: 10px;
  padding: 2px 10px;
  border-radius: 20px;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  font-weight: 500;
  letter-spacing: 0.3px;
}

.panel-badge.pink { background: var(--lumi-accent-light); color: var(--task-pink); }
.panel-badge.green { background: var(--task-green-soft); color: var(--lumi-success); }
.panel-badge.yellow { background: var(--lumi-amber-soft); color: var(--lumi-amber); }

.panel-action-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms ease-in-out;
  white-space: nowrap;
}

.panel-action-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.panel-action-btn.primary {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  border: 1px solid var(--lumi-primary-glow);
}

.panel-action-btn.primary:hover {
  background: var(--lumi-primary-glow);
}

.panel-action-btn.running {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.model-panel {
  flex: 1;
}

.provider-list {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.provider-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 250ms ease-in-out;
  border: 1px solid transparent;
}

.provider-item:hover {
  background: var(--bg-secondary);
  border-color: var(--provider-color);
}

.provider-item.inactive {
  opacity: 0.5;
}

.provider-avatar {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: var(--provider-color);
  background: color-mix(in srgb, var(--provider-color) 10%, transparent);
  flex-shrink: 0;
}

.provider-info {
  flex: 1;
  min-width: 0;
}

.provider-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
}

.provider-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.active { background: var(--lumi-success); box-shadow: 0 0 6px var(--task-green-border); }
.status-dot.inactive { background: var(--text-muted); }
.status-dot.error { background: var(--lumi-danger); box-shadow: 0 0 6px var(--task-red-border); }

.provider-model {
  font-size: 11px;
  color: var(--text-muted);
}

.provider-stats {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

.mini-stat {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.provider-arrow {
  color: var(--text-muted);
  opacity: 0;
  transition: all 200ms;
}

.provider-item:hover .provider-arrow {
  opacity: 1;
  color: var(--provider-color);
}

.persona-panel {
  flex: 1;
}

.persona-grid {
  padding: 14px 16px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.persona-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all 250ms ease-in-out;
}

.persona-card:hover {
  border-color: var(--task-pink);
  background: var(--lumi-accent-light);
}

.persona-card.active {
  border-color: var(--task-pink);
  background: var(--lumi-accent-glow);
}

.persona-avatar-preview {
  position: relative;
  flex-shrink: 0;
  color: var(--text-muted);
}

.active-ring {
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  border: 2px solid var(--task-pink);
  animation: ringPulse 2s ease-in-out infinite;
}

@keyframes ringPulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.1); }
}

.persona-detail {
  flex: 1;
  min-width: 0;
}

.persona-name {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 4px;
}

.persona-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.p-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 6px;
  background: var(--bg-secondary);
  color: var(--text-muted);
}

.chart-panel {
  flex: 1.2;
}

.chart-period-selector {
  display: flex;
  gap: 2px;
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 2px;
}

.period-btn {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 11px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms;
}

.period-btn:hover { color: var(--text-secondary); }
.period-btn.active {
  background: var(--surface);
  color: var(--text);
  font-weight: 500;
  box-shadow: var(--shadow-xs);
}

.chart-area {
  padding: 16px 20px 0;
}

.big-chart-svg-wrap {
  position: relative;
  height: 180px;
  border-radius: 12px;
  background: linear-gradient(180deg, var(--lumi-primary-subtle) 0%, transparent 100%);
}

.area-chart {
  width: 100%;
  height: 100%;
}

.chart-area-fill {
  opacity: 0;
  animation: fadeAreaIn 0.8s ease-out 0.5s both;
}

@keyframes fadeAreaIn { to { opacity: 1; } }

.chart-line {
  stroke-dasharray: 800;
  stroke-dashoffset: 800;
  animation: drawLine 1.5s cubic-bezier(0.4, 0, 0.2, 1) 0.3s both;
}

@keyframes drawLine { to { stroke-dashoffset: 0; } }

.chart-dot {
  opacity: 0;
  animation: dotIn 0.4s ease-out 1.5s both;
}

@keyframes dotIn { to { opacity: 1; } }

.pulse-dot {
  animation: dotPulse 2s ease-in-out infinite;
}

@keyframes dotPulse {
  0%, 100% { r: 4; }
  50% { r: 6; }
}

.chart-overlay-stats {
  position: absolute;
  top: 16px;
  right: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.overlay-stat {
  text-align: right;
}

.os-label {
  font-size: 10px;
  color: var(--text-muted);
}

.os-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}

.os-trend {
  font-size: 11px;
  font-weight: 600;
  margin-left: 4px;
}

.os-trend.up { color: var(--lumi-success); }
.os-trend.down { color: var(--lumi-danger); }

.overlay-stat.primary .os-value { color: var(--lumi-primary); }
.overlay-stat.success .os-value { color: var(--lumi-success); }

.chart-x-axis {
  display: flex;
  justify-content: space-between;
  padding: 8px 8px 0;
}

.chart-x-axis span {
  font-size: 10px;
  color: var(--text-muted);
}

.usage-mini-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 12px 20px 16px;
  border-top: 1px solid var(--border-light);
}

.usage-mini-item {
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--bg-secondary);
}

.umi-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.umi-label {
  font-size: 11px;
  color: var(--text-muted);
}

.umi-change {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 10px;
  font-weight: 600;
}

.umi-change.up { color: var(--lumi-success); }
.umi-change.down { color: var(--lumi-danger); }

.umi-bar-track {
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 6px;
}

.umi-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 1s cubic-bezier(0.22, 1, 0.36, 1);
}

.umi-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.console-panel {
  flex: 1;
  min-height: 240px;
}

.console-actions {
  display: flex;
  gap: 4px;
}

.console-log-area {
  flex: 1;
  padding: 12px 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 11px;
  min-height: 180px;
  max-height: 220px;
}

.log-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  border-radius: 6px;
  background: var(--log-bg);
  transition: all 150ms ease-in-out;
}

.log-entry:hover {
  filter: brightness(1.05);
}

.log-time {
  color: var(--text-muted);
  flex-shrink: 0;
  font-family: inherit;
}

.log-level-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--log-dot);
  flex-shrink: 0;
}

.log-source {
  color: var(--log-text);
  font-weight: 600;
  flex-shrink: 0;
  font-family: inherit;
}

.log-message {
  color: var(--text-secondary);
  font-family: inherit;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-level-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
  letter-spacing: 0.5px;
}

.log-level-badge.info { background: var(--lumi-primary-light); color: var(--lumi-primary); }
.log-level-badge.warn { background: var(--task-yellow-soft); color: var(--lumi-warning); }
.log-level-badge.error { background: var(--task-red-soft); color: var(--lumi-danger); }
.log-level-badge.success { background: var(--task-green-soft); color: var(--lumi-success); }

.console-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid var(--border-light);
  background: var(--bg-secondary);
}

.console-prompt {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 12px;
  font-weight: 600;
  color: var(--lumi-primary);
  flex-shrink: 0;
}

.prompt-blink {
  animation: blink 1s step-end infinite;
}

@keyframes blink { 50% { opacity: 0; } }

.console-input {
  flex: 1;
  padding: 6px 10px;
  border-radius: 8px;
  background: var(--surface);
  border: 1px solid transparent;
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  color: var(--text);
  transition: all 200ms;
}

.console-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 2px var(--lumi-primary-glow);
}

.console-input::placeholder {
  color: var(--text-muted);
}

.console-send-btn {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--lumi-primary);
  color: var(--text-inverse);
  cursor: pointer;
  transition: all 200ms;
  flex-shrink: 0;
}

.console-send-btn:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.console-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.full-panel {
  flex: 1;
}

.full-height {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.model-config-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  padding: 20px;
  flex: 1;
  overflow-y: auto;
  align-content: start;
}

.model-config-card {
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--bg);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  transition: all 250ms ease-in-out;
  opacity: 0;
  animation: cardSlideUp 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes cardSlideUp {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

.model-config-card:hover {
  border-color: var(--pc-color);
  box-shadow: 0 4px 24px color-mix(in srgb, var(--pc-color) 8%, transparent);
}

.model-config-card.status-error { border-color: var(--lumi-danger); }

.mc-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mc-brand {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}

.mc-meta {
  flex: 1;
}

.mc-name {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.mc-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  margin-top: 2px;
  display: inline-block;
}

.mc-status.active { background: var(--task-green-soft); color: var(--lumi-success); }
.mc-status.inactive { background: var(--surface-hover); color: var(--text-muted); }
.mc-status.error { background: var(--task-red-soft); color: var(--lumi-danger); }

.mc-menu {
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  transition: all 200ms;
}

.mc-menu:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.mc-fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mc-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mc-field label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
}

.mc-input-mock {
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  font-size: 12px;
  color: var(--text-secondary);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.mc-input-mock.highlight {
  color: var(--pc-color);
  font-weight: 600;
}

.mc-progress-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
}

.mc-progress-fill {
  height: 5px;
  border-radius: 3px;
  flex: 1;
  max-width: 120px;
  transition: width 1s cubic-bezier(0.22, 1, 0.36, 1);
}

.mc-progress-bar span {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}

.mc-footer {
  display: flex;
  gap: 20px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

.mc-footer-stat {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.mc-footer-stat svg { color: var(--lumi-primary); }

.persona-workshop-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  padding: 20px;
  flex: 1;
  overflow-y: auto;
  align-content: start;
}

.pw-card {
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--bg);
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  transition: all 250ms ease-in-out;
  text-align: center;
}

.pw-card:hover {
  border-color: var(--task-pink);
  box-shadow: 0 4px 24px var(--lumi-accent-light);
}

.pw-card.active {
  border-color: var(--task-pink);
  background: linear-gradient(180deg, var(--lumi-accent-glow) 0%, transparent 100%);
}

.pw-visual {
  position: relative;
}

.pw-avatar-large {
  color: var(--text-muted);
  transition: all 250ms;
}

.pw-card:hover .pw-avatar-large,
.pw-card.active .pw-avatar-large {
  color: var(--task-pink);
}

.pw-active-badge {
  position: absolute;
  bottom: -4px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 10px;
  background: var(--task-pink);
  color: var(--text-inverse);
  white-space: nowrap;
}

.pw-info h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.pw-info p {
  font-size: 11px;
  color: var(--text-muted);
}

.pw-config-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.pw-config-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-secondary);
  padding: 5px 10px;
  border-radius: 8px;
  background: var(--surface);
}

.pw-config-item svg { color: var(--text-muted); flex-shrink: 0; }

.pw-action-btn {
  width: 100%;
  padding: 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 200ms;
  background: var(--surface);
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.pw-action-btn:hover {
  border-color: var(--task-pink);
  color: var(--task-pink);
  background: var(--lumi-accent-glow);
}

.pw-action-btn.active {
  background: var(--task-pink);
  color: var(--text-inverse);
  border-color: var(--task-pink);
}

.add-new {
  border-style: dashed;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 260px;
  cursor: pointer;
}

.add-new:hover {
  border-color: var(--lumi-primary);
  background: var(--lumi-primary-subtle);
}

.add-new-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
}

.add-new-content span {
  font-size: 13px;
  font-weight: 500;
}

.usage-detail-grid {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr 1fr;
  gap: 16px;
  padding: 20px;
  flex: 1;
  overflow-y: auto;
}

.ud-card {
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--bg);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ud-card.wide {
  grid-column: span 1;
}

.ud-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ud-header h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.ud-chart-placeholder {
  border-radius: 12px;
  background: var(--surface);
  overflow: hidden;
}

.ud-chart-placeholder.large {
  height: 160px;
}

.bar-chart-svg {
  width: 100%;
  height: 100%;
  padding: 16px;
}

.bar-anim {
  transform-origin: bottom;
  animation: barGrow 0.8s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes barGrow {
  from { transform: scaleY(0); }
  to { transform: scaleY(1); }
}

.donut-wrap {
  position: relative;
  height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.donut-chart {
  width: 120px;
  height: 120px;
}

.donut-anim {
  stroke-dasharray: 0 251;
  animation: donutDraw 1s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes donutDraw {
  to { stroke-dasharray: attr(stroke-dasharray); }
}

.donut-center {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.dc-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
}

.dc-label {
  font-size: 10px;
  color: var(--text-muted);
}

.ud-legend {
  display: flex;
  justify-content: center;
  gap: 16px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--text-secondary);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}

.ud-stats-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.ud-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--surface);
}

.ud-stat-label {
  font-size: 10px;
  color: var(--text-muted);
}

.ud-stat-value {
  font-size: 16px;
  font-weight: 700;
}

.ud-stat-trend {
  font-size: 11px;
  font-weight: 600;
}

.ud-stat-trend.up { color: var(--lumi-success); }
.ud-stat-trend.down { color: var(--lumi-danger); }

.ctx-bars {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ctx-bar-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cbi-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.cbi-name {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.cbi-val {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.cbi-bar-track {
  height: 8px;
  background: var(--surface);
  border-radius: 4px;
  overflow: hidden;
}

.cbi-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 1.2s cubic-bezier(0.22, 1, 0.36, 1);
}

.console-full {
  min-height: 0;
}

.console-main {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.full-log {
  max-height: none;
  flex: 1;
}

.console-input-area {
  flex-shrink: 0;
}

.console-input-row.full-width {
  padding: 14px 20px;
}

.console-input.flex-grow {
  flex: 1;
}

.console-toolbar {
  display: flex;
  gap: 6px;
}

::-webkit-scrollbar {
  width: 4px;
  height: 4px;
}

::-webkit-scrollbar-thumb {
  background: var(--workspace-border);
  border-radius: 4px;
}
</style>
