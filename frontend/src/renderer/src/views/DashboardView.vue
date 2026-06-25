<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useMemoryStore } from '../stores/memory'
import LumiButton from '../components/common/LumiButton.vue'
import LumiCard from '../components/common/LumiCard.vue'
import LumiInput from '../components/common/LumiInput.vue'
import DashboardStatCard from '../components/dashboard/DashboardStatCard.vue'
import DashboardModelPanel from '../components/dashboard/DashboardModelPanel.vue'
import DashboardUsagePanel from '../components/dashboard/DashboardUsagePanel.vue'
import DashboardPersonaPanel from '../components/dashboard/DashboardPersonaPanel.vue'
import DashboardConsolePanel from '../components/dashboard/DashboardConsolePanel.vue'
import DashboardModelConfigTab from '../components/dashboard/DashboardModelConfigTab.vue'
import DashboardPersonaWorkshopTab from '../components/dashboard/DashboardPersonaWorkshopTab.vue'
import {
  LayoutDashboard,
  Cpu,
  Palette,
  BarChart3,
  Terminal,
  Settings2,
  RefreshCw,
  Sparkles,
  Database,
  Brain,
  Layers,
  Play,
  Square,
  RotateCcw,
  Download,
} from 'lucide-vue-next'
import type { ModelProvider, PersonaConfig, UsageMetric, LogEntry } from '../components/dashboard/types'
import { generateId } from '../utils/id'

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
  refreshMemoryMetrics()
})

onUnmounted(() => {
  if (timeInterval) clearInterval(timeInterval)
})

const modelProviders = ref<ModelProvider[]>([
  { id: 'openai', name: 'OpenAI', icon: 'OAI', status: 'active', model: 'GPT-4o', endpoint: 'https://api.openai.com/v1', requests: 12847, latency: 234, color: 'var(--lumi-success)' },
  { id: 'anthropic', name: 'Anthropic', icon: 'ANT', status: 'active', model: 'Claude 3.5 Sonnet', endpoint: 'https://api.anthropic.com/v1', requests: 8234, latency: 189, color: 'var(--lumi-warning)' },
  { id: 'deepseek', name: 'DeepSeek', icon: 'DSK', status: 'active', model: 'DeepSeek-V3', endpoint: 'https://api.deepseek.com/v1', requests: 5621, latency: 312, color: 'var(--lumi-info)' },
  { id: 'ollama', name: 'Ollama Local', icon: 'OLL', status: 'inactive', model: 'Llama 3.1', endpoint: 'http://localhost:11434', requests: 0, latency: 0, color: 'var(--text-muted)' },
])

const personas = ref<PersonaConfig[]>([
  { id: 'p1', name: '辰汐 · 默认', avatar: '默认形象', style: '温柔知性', voice: '甜美女声', tone: '温暖亲切', active: true },
  { id: 'p2', name: '辰汐 · 活泼', avatar: '活力少女', style: '元气满满', voice: '活泼女声', tone: '开朗热情', active: false },
  { id: 'p3', name: '辰汐 · 冷静', avatar: '高冷御姐', style: '简约优雅', voice: '成熟女声', tone: '沉稳冷静', active: false },
])

const apiUsageMetrics = ref<UsageMetric[]>([
  { label: '今日请求', value: 26702, unit: '次', change: 12.5, trend: 'up', color: 'var(--lumi-primary)' },
  { label: 'Token 消耗', value: '2.84M', unit: '', change: 8.3, trend: 'up', color: 'var(--lumi-success)' },
  { label: '平均延迟', value: 245, unit: 'ms', change: -5.2, trend: 'down', color: 'var(--lumi-warning)' },
  { label: '成功率', value: 99.7, unit: '%', change: 0.3, trend: 'up', color: 'var(--task-purple)' },
])

const memoryStore = useMemoryStore()

const memoryMetrics = ref<UsageMetric[]>([
  { label: '工作记忆', value: 0, unit: '/100', change: 0, trend: 'up', color: 'var(--lumi-warning)' },
  { label: '情景记忆', value: 0, unit: '/50', change: 0, trend: 'up', color: 'var(--lumi-success)' },
  { label: '语义记忆', value: 0, unit: '/500', change: 0, trend: 'up', color: 'var(--task-purple)' },
  { label: '记忆健康度', value: 0, unit: '%', change: 0, trend: 'up', color: 'var(--lumi-primary)' },
])

const refreshMemoryMetrics = async () => {
  try {
    await memoryStore.fetchMemory()
    const factCount = memoryStore.facts.length
    const latestFacts = memoryStore.facts.filter(f => f.is_latest !== false).length
    const profileName = memoryStore.profile.name
    memoryMetrics.value[0].value = Math.min(latestFacts, 100)
    memoryMetrics.value[1].value = profileName ? 50 : Math.min(latestFacts, 50)
    memoryMetrics.value[2].value = Math.min(factCount, 500)
    const health = factCount > 0 ? Math.round((latestFacts / factCount) * 100) : 0
    memoryMetrics.value[3].value = factCount > 0 ? Math.max(health, 50) : 0
  } catch {
    // 保持默认值
  }
}

const contextMetrics = ref<UsageMetric[]>([
  { label: '当前上下文', value: 8192, unit: 'tokens', change: 12.0, trend: 'up', color: 'var(--lumi-primary)' },
  { label: '窗口使用率', value: 68, unit: '%', change: -3.5, trend: 'down', color: 'var(--lumi-warning)' },
  { label: '对话轮次', value: 24, unit: '轮', change: 8.0, trend: 'up', color: 'var(--lumi-success)' },
  { label: '压缩次数', value: 3, unit: '次', change: 0, trend: 'up', color: 'var(--task-purple)' },
])

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
    info: { bg: 'var(--lumi-primary-light)', text: 'var(--lumi-primary)', dot: 'var(--lumi-primary)' },
    warn: { bg: 'var(--lumi-warning-light)', text: 'var(--lumi-warning)', dot: 'var(--lumi-warning)' },
    error: { bg: 'var(--lumi-danger-light)', text: 'var(--lumi-danger)', dot: 'var(--lumi-danger)' },
    success: { bg: 'var(--lumi-success-light)', text: 'var(--lumi-success)', dot: 'var(--lumi-success)' },
  }
  return map[level] || map.info
}

function handleConsoleCommand() {
  if (!consoleInput.value.trim()) return
  consoleLogs.value.push({
    id: generateId(),
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
      <div class="header-left shrink-0">
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
        <LumiButton variant="ghost" size="sm" icon-only aria-label="刷新数据">
          <template #icon>
            <RefreshCw :size="16" />
          </template>
        </LumiButton>
        <LumiButton variant="ghost" size="sm" icon-only aria-label="设置">
          <template #icon>
            <Settings2 :size="16" />
          </template>
        </LumiButton>
      </div>
    </div>

    <div class="dash-body">
      <div v-show="activeTab === 'overview'" class="tab-content animate-fade-in">
        <section class="dash-section overview-top">
          <DashboardStatCard :metrics="[...apiUsageMetrics.slice(0, 2), ...memoryMetrics.slice(0, 2)]" />
        </section>

        <section class="dash-section main-grid">
          <div class="grid-left">
            <DashboardModelPanel :providers="modelProviders" />
            <DashboardPersonaPanel :personas="personas" />
          </div>

          <div class="grid-right">
            <DashboardUsagePanel :api-metrics="apiUsageMetrics" :context-metrics="contextMetrics" />
            <DashboardConsolePanel
              v-model:input="consoleInput"
              :logs="consoleLogs"
              @enter="handleConsoleCommand"
              @clear="clearConsole"
            />
          </div>
        </section>
      </div>

      <div v-show="activeTab === 'model'" class="tab-content animate-fade-in">
        <DashboardModelConfigTab :providers="modelProviders" />
      </div>

      <div v-show="activeTab === 'persona'" class="tab-content animate-fade-in">
        <DashboardPersonaWorkshopTab :personas="personas" />
      </div>

      <div v-show="activeTab === 'usage'" class="tab-content animate-fade-in">
        <section class="dash-section full-panel">
          <LumiCard class="full-height" padding="none">
            <template #title>
              <div class="panel-title-group">
                <BarChart3 :size="20" class="panel-icon shrink-0" style="color: var(--lumi-success)" />
                <h3>用量统计分析</h3>
              </div>
            </template>
            <template #header>
              <div class="chart-period-selector">
                <button class="period-btn">今天</button>
                <button class="period-btn active">7天</button>
                <button class="period-btn">30天</button>
                <button class="period-btn">自定义</button>
              </div>
            </template>
            <div class="usage-detail-grid">
              <div class="ud-card lumi-card">
                <div class="ud-header">
                  <Database :size="18" style="color: var(--lumi-primary)" />
                  <h4>API 用量</h4>
                </div>
                <div class="ud-chart-placeholder large">
                  <svg viewBox="0 0 300 120" class="bar-chart-svg">
                    <rect
                      v-for="(h, i) in [45, 72, 58, 88, 64, 95, 78]"
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
              <div class="ud-card lumi-card">
                <div class="ud-header">
                  <Brain :size="18" style="color: var(--task-purple)" />
                  <h4>记忆用量</h4>
                </div>
                <div class="ud-chart-placeholder donut-wrap">
                  <svg viewBox="0 0 100 100" class="donut-chart">
                    <circle cx="50" cy="50" r="40" fill="none" stroke="var(--border)" stroke-width="10" />
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="none"
                      stroke="var(--lumi-warning)"
                      stroke-width="10"
                      stroke-dasharray="167 251"
                      stroke-dashoffset="0"
                      class="donut-anim"
                    />
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="none"
                      stroke="var(--lumi-success)"
                      stroke-width="10"
                      stroke-dasharray="107 251"
                      stroke-dashoffset="-167"
                      class="donut-anim"
                      style="animation-delay: 0.3s"
                    />
                    <circle
                      cx="50"
                      cy="50"
                      r="40"
                      fill="none"
                      stroke="var(--task-purple)"
                      stroke-width="10"
                      stroke-dasharray="215 251"
                      stroke-dashoffset="-274"
                      class="donut-anim"
                      style="animation-delay: 0.6s"
                    />
                  </svg>
                  <div class="donut-center">
                    <span class="dc-value">529</span>
                    <span class="dc-label">总记录</span>
                  </div>
                </div>
                <div class="ud-legend">
                  <div class="legend-item"><span class="legend-dot" style="background: var(--lumi-warning)" />工作 67</div>
                  <div class="legend-item"><span class="legend-dot" style="background: var(--lumi-success)" />情景 34</div>
                  <div class="legend-item"><span class="legend-dot" style="background: var(--task-purple)" />语义 428</div>
                </div>
              </div>
              <div class="ud-card lumi-card wide">
                <div class="ud-header">
                  <Layers :size="18" style="color: var(--lumi-warning)" />
                  <h4>上下文监控</h4>
                </div>
                <div class="ctx-bars">
                  <div v-for="m in contextMetrics" :key="m.label" class="ctx-bar-item">
                    <div class="cbi-labels">
                      <span class="cbi-name">{{ m.label }}</span>
                      <span class="cbi-val">{{ m.value }}{{ m.unit }}</span>
                    </div>
                    <div class="cbi-bar-track">
                      <div
                        class="cbi-bar-fill"
                        :style="{
                          width: typeof m.value === 'number' ? Math.min(100, m.value / (m.unit.includes('tokens') ? 16384 : m.unit.includes('%') ? 100 : 50)) + '%' : '60%',
                          background: m.color,
                        }"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </LumiCard>
        </section>
      </div>

      <div v-show="activeTab === 'console'" class="tab-content animate-fade-in">
        <section class="dash-section full-panel">
          <LumiCard class="full-height console-full" padding="none">
            <template #title>
              <div class="panel-title-group">
                <Terminal :size="20" class="panel-icon shrink-0" style="color: var(--lumi-warning)" />
                <h3>系统控制台</h3>
                <span class="panel-badge yellow">{{ consoleLogs.length }} 条日志</span>
              </div>
            </template>
            <template #header>
              <div class="console-toolbar">
                <LumiButton variant="ghost" size="sm" @click="clearConsole">
                  <template #icon>
                    <RotateCcw :size="14" />
                  </template>
                  清空
                </LumiButton>
                <LumiButton variant="ghost" size="sm">
                  <template #icon>
                    <Download :size="14" />
                  </template>
                  导出
                </LumiButton>
                <LumiButton variant="ghost" size="sm" :class="{ running: isConsoleRunning }" @click="isConsoleRunning = !isConsoleRunning">
                  <template #icon>
                    <component :is="isConsoleRunning ? Square : Play" :size="14" />
                  </template>
                  {{ isConsoleRunning ? '暂停' : '实时' }}
                </LumiButton>
              </div>
            </template>
            <div class="console-main">
              <div class="console-log-area full-log">
                <div
                  v-for="log in consoleLogs"
                  :key="log.id"
                  class="log-entry"
                  :style="{ '--log-bg': getLogLevelStyle(log.level).bg, '--log-text': getLogLevelStyle(log.level).text, '--log-dot': getLogLevelStyle(log.level).dot }"
                >
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
                <LumiInput v-model="consoleInput" class="console-input flex-grow"
                  placeholder="输入命令或查询... 按 Enter 执行，Tab 自动补全" @enter="handleConsoleCommand" />
                <LumiButton variant="primary" size="sm" icon-only :disabled="!consoleInput.trim()" @click="handleConsoleCommand">
                  <template #icon>
                    <Play :size="14" />
                  </template>
                </LumiButton>
              </div>
            </div>
          </LumiCard>
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
  padding: var(--space-3) var(--space-6);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  background: var(--surface);
  gap: var(--space-5);
}

.greeting-block {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.greeting-icon {
  width: var(--space-8);
  height: var(--space-8);
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--lumi-primary), var(--lumi-primary-soft));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-inverse);
  box-shadow: var(--shadow-md);
}

.greeting-text {
  display: flex;
  flex-direction: column;
}

.greeting-label {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.greeting-date {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.tab-nav {
  display: flex;
  gap: var(--space-1);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--space-1);
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-sm);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-normal);
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

.tab-btn:focus-visible {
  outline: none;
  box-shadow: var(--input-focus-ring);
}

.header-right {
  display: flex;
  gap: var(--space-1);
  flex-shrink: 0;
}

.dash-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-5) var(--space-6);
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.dash-section {
  display: flex;
  flex-direction: column;
}

.main-grid {
  display: grid;
  grid-template-columns: 1fr 1.3fr;
  gap: var(--space-5);
}

.grid-left,
.grid-right {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.full-panel {
  flex: 1;
}

.full-height {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.full-height :deep(.lumi-card__body) {
  display: contents;
}

.panel-title-group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.panel-title-group h3 {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.panel-badge {
  font-size: var(--text-2xs);
  padding: calc(var(--space-1) / 2) var(--space-3);
  border-radius: var(--radius-full);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  font-weight: var(--font-medium);
  letter-spacing: 0.3px;
}

.panel-badge.pink { background: var(--task-pink-soft); color: var(--task-pink); }
.panel-badge.green { background: var(--task-green-soft); color: var(--lumi-success); }
.panel-badge.yellow { background: var(--lumi-amber-soft); color: var(--lumi-amber); }

.chart-period-selector {
  display: flex;
  gap: var(--space-1);
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  padding: calc(var(--space-1) / 2);
}

.period-btn {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-xs);
  font-size: var(--text-2xs);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.period-btn:hover { color: var(--text-secondary); }
.period-btn.active {
  background: var(--surface);
  color: var(--text);
  font-weight: var(--font-medium);
  box-shadow: var(--shadow-xs);
}

.period-btn:focus-visible {
  outline: none;
  box-shadow: var(--input-focus-ring);
}

.console-log-area {
  flex: 1;
  padding: var(--space-3) var(--space-4);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.log-entry {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-xs);
  background: var(--log-bg);
  transition: all var(--transition-fast);
}

.log-entry:hover {
  filter: brightness(1.05);
}

.log-time {
  color: var(--text-muted);
  flex-shrink: 0;
  font-family: inherit;
}

.log-source {
  color: var(--log-text);
  font-weight: var(--font-semibold);
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
  font-size: var(--text-2xs);
  font-weight: var(--font-bold);
  padding: var(--badge-padding);
  border-radius: var(--radius-xs);
  flex-shrink: 0;
  letter-spacing: 0.5px;
}

.log-level-badge.info { background: var(--lumi-primary-light); color: var(--lumi-primary); }
.log-level-badge.warn { background: var(--lumi-warning-light); color: var(--lumi-warning); }
.log-level-badge.error { background: var(--lumi-danger-light); color: var(--lumi-danger); }
.log-level-badge.success { background: var(--lumi-success-light); color: var(--lumi-success); }

.console-input-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border-light);
  background: var(--bg-secondary);
}

.console-prompt {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--lumi-primary);
  flex-shrink: 0;
}

.prompt-blink {
  animation: blink 1s step-end infinite;
}

@keyframes blink { 50% { opacity: 0; } }

.console-input {
  flex: 1;
}

.console-input :deep(.lumi-input) {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  background: var(--surface);
  border-color: transparent;
}

.console-input :deep(.lumi-input:focus) {
  border-color: var(--lumi-primary);
  box-shadow: var(--input-focus-ring);
}

.console-input :deep(.lumi-input::placeholder) {
  color: var(--text-muted);
}
</style>
