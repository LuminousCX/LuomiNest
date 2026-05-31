<script setup lang="ts">
import { ref, computed } from 'vue'
import { BarChart3, TrendingUp, TrendingDown, Database, Brain, Clock, Zap, Activity, ArrowUpRight, ArrowDownRight, Calendar } from 'lucide-vue-next'

const period = ref<'day' | 'week' | 'month'>('week')

const usageData = computed(() => {
  const base = {
    day: { tokens: 12500, requests: 89, cost: 2.35, memory: 340 },
    week: { tokens: 87500, requests: 623, cost: 16.45, memory: 2380 },
    month: { tokens: 375000, requests: 2680, cost: 70.20, memory: 10200 },
  }
  return base[period.value]
})

const apiProviders = ref([
  { name: 'OpenAI', requests: 456, tokens: 52000, cost: 12.50, trend: 'up' },
  { name: 'Anthropic', requests: 234, tokens: 38000, cost: 8.30, trend: 'up' },
  { name: 'Google AI', requests: 89, tokens: 12000, cost: 2.10, trend: 'down' },
  { name: '本地模型', requests: 567, tokens: 95000, cost: 0, trend: 'up' },
])

const memoryUsage = ref([
  { type: '短期记忆', used: 128, total: 256, unit: 'KB' },
  { type: '长期记忆', used: 45, total: 100, unit: 'MB' },
  { type: '上下文窗口', used: 8192, total: 32768, unit: 'tokens' },
])

const recentActivity = ref([
  { time: '10:32', action: 'API 调用', detail: 'GPT-4o → 生成回复 (2,340 tokens)', type: 'api' },
  { time: '10:28', action: '记忆存储', detail: '保存对话摘要至长期记忆', type: 'memory' },
  { time: '10:15', action: '上下文压缩', detail: '窗口从 12K 压缩至 8K tokens', type: 'context' },
  { time: '09:55', action: 'API 调用', detail: 'Claude 3.5 → 代码分析 (1,890 tokens)', type: 'api' },
  { time: '09:30', action: '记忆检索', detail: '从长期记忆中检索 3 条相关记录', type: 'memory' },
])
</script>

<template>
  <div class="usage-view">
    <div class="usage-header">
      <div class="header-info">
        <h1 class="header-title">用量统计</h1>
        <p class="header-desc">API 用量、记忆用量、上下文消耗概览</p>
      </div>
      <div class="period-tabs">
        <button :class="['period-btn', { active: period === 'day' }]" @click="period = 'day'">今日</button>
        <button :class="['period-btn', { active: period === 'week' }]" @click="period = 'week'">本周</button>
        <button :class="['period-btn', { active: period === 'month' }]" @click="period = 'month'">本月</button>
      </div>
    </div>

    <div class="stats-row">
      <div class="stat-card" style="animation-delay: 0.04s">
        <div class="stat-icon-wrap tokens"><Zap :size="18" /></div>
        <div class="stat-body">
          <span class="stat-label">Token 消耗</span>
          <span class="stat-value">{{ usageData.tokens.toLocaleString() }}</span>
        </div>
        <div class="stat-trend up"><ArrowUpRight :size="14" /> 12%</div>
      </div>
      <div class="stat-card" style="animation-delay: 0.08s">
        <div class="stat-icon-wrap requests"><Activity :size="18" /></div>
        <div class="stat-body">
          <span class="stat-label">请求次数</span>
          <span class="stat-value">{{ usageData.requests.toLocaleString() }}</span>
        </div>
        <div class="stat-trend up"><ArrowUpRight :size="14" /> 8%</div>
      </div>
      <div class="stat-card" style="animation-delay: 0.12s">
        <div class="stat-icon-wrap cost"><BarChart3 :size="18" /></div>
        <div class="stat-body">
          <span class="stat-label">费用 (CNY)</span>
          <span class="stat-value">¥{{ usageData.cost.toFixed(2) }}</span>
        </div>
        <div class="stat-trend down"><ArrowDownRight :size="14" /> 3%</div>
      </div>
      <div class="stat-card" style="animation-delay: 0.16s">
        <div class="stat-icon-wrap memory"><Brain :size="18" /></div>
        <div class="stat-body">
          <span class="stat-label">记忆条目</span>
          <span class="stat-value">{{ usageData.memory }}</span>
        </div>
        <div class="stat-trend up"><ArrowUpRight :size="14" /> 15%</div>
      </div>
    </div>

    <div class="usage-content">
      <div class="left-col">
        <div class="section-card" style="animation-delay: 0.10s">
          <div class="section-header">
            <span class="section-title">供应商用量</span>
            <Calendar :size="14" class="section-icon" />
          </div>
          <div class="provider-list">
            <div v-for="(p, idx) in apiProviders" :key="p.name" class="provider-row" :style="{ animationDelay: (0.14 + idx * 0.03) + 's' }">
              <div class="provider-name">{{ p.name }}</div>
              <div class="provider-stats">
                <span class="provider-requests">{{ p.requests }} 次</span>
                <span class="provider-tokens">{{ (p.tokens / 1000).toFixed(1) }}K tokens</span>
              </div>
              <div class="provider-cost">¥{{ p.cost.toFixed(2) }}</div>
              <div :class="['provider-trend', p.trend]">
                <TrendingUp v-if="p.trend === 'up'" :size="12" />
                <TrendingDown v-else :size="12" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="right-col">
        <div class="section-card" style="animation-delay: 0.12s">
          <div class="section-header">
            <span class="section-title">记忆与上下文</span>
            <Database :size="14" class="section-icon" />
          </div>
          <div class="memory-bars">
            <div v-for="(m, idx) in memoryUsage" :key="m.type" class="memory-item" :style="{ animationDelay: (0.16 + idx * 0.03) + 's' }">
              <div class="memory-label-row">
                <span class="memory-type">{{ m.type }}</span>
                <span class="memory-value">{{ m.used }} / {{ m.total }} {{ m.unit }}</span>
              </div>
              <div class="memory-bar-bg">
                <div class="memory-bar-fill" :style="{ width: (m.used / m.total * 100) + '%' }"></div>
              </div>
            </div>
          </div>
        </div>

        <div class="section-card" style="animation-delay: 0.18s">
          <div class="section-header">
            <span class="section-title">最近活动</span>
            <Clock :size="14" class="section-icon" />
          </div>
          <div class="activity-list">
            <div v-for="(a, idx) in recentActivity" :key="a.time + a.action" class="activity-item" :style="{ animationDelay: (0.22 + idx * 0.03) + 's' }">
              <span class="activity-time">{{ a.time }}</span>
              <span :class="['activity-badge', a.type]">{{ a.action }}</span>
              <span class="activity-detail">{{ a.detail }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.usage-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px 28px;
  gap: 20px;
  overflow-y: auto;
}

.usage-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.header-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
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
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.period-btn.active {
  background: var(--surface);
  color: var(--lumi-primary);
  box-shadow: var(--shadow-xs);
}

.stats-row {
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
}

.stat-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon-wrap.tokens {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.stat-icon-wrap.requests {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.stat-icon-wrap.cost {
  background: var(--task-yellow-soft);
  color: var(--lumi-warning);
}

.stat-icon-wrap.memory {
  background: var(--task-purple-soft);
  color: var(--task-purple);
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

.usage-content {
  flex: 1;
  display: flex;
  gap: 16px;
  min-height: 0;
}

.left-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.right-col {
  width: 360px;
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
  flex: 1;
  animation: content-fade-up 0.5s cubic-bezier(0.4, 0, 0.2, 1) both;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.section-icon {
  color: var(--text-muted);
}

.provider-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.provider-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-light);
  animation: content-fade-up 0.4s cubic-bezier(0.4, 0, 0.2, 1) both;
}

.provider-row:last-child {
  border-bottom: none;
}

.provider-name {
  width: 100px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.provider-stats {
  flex: 1;
  display: flex;
  gap: 12px;
}

.provider-requests, .provider-tokens {
  font-size: 12px;
  color: var(--text-muted);
}

.provider-cost {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  width: 70px;
  text-align: right;
}

.provider-trend {
  display: flex;
  align-items: center;
}

.provider-trend.up {
  color: var(--lumi-success);
}

.provider-trend.down {
  color: var(--lumi-accent);
}

.memory-bars {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.memory-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  animation: content-fade-up 0.4s cubic-bezier(0.4, 0, 0.2, 1) both;
}

.memory-label-row {
  display: flex;
  justify-content: space-between;
}

.memory-type {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

.memory-value {
  font-size: 11px;
  color: var(--text-muted);
}

.memory-bar-bg {
  height: 6px;
  border-radius: 3px;
  background: var(--bg-secondary);
  overflow: hidden;
}

.memory-bar-fill {
  height: 100%;
  border-radius: 3px;
  background: var(--lumi-primary);
  transition: width var(--transition-normal);
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.activity-item {
  display: flex;
  animation: content-fade-up 0.4s cubic-bezier(0.4, 0, 0.2, 1) both;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}

.activity-time {
  font-size: 11px;
  color: var(--text-muted);
  width: 40px;
  flex-shrink: 0;
}

.activity-badge {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
  width: 60px;
  text-align: center;
  flex-shrink: 0;
}

.activity-badge.api {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.activity-badge.memory {
  background: rgba(139, 92, 246, 0.1);
  color: var(--task-purple);
}

.activity-badge.context {
  background: var(--task-yellow-soft);
  color: var(--lumi-warning);
}

.activity-detail {
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
