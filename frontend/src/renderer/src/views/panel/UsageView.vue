<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Database,
  Brain,
  Clock,
  Zap,
  Activity,
  Calendar,
} from 'lucide-vue-next'
import LumiCard from '../../components/common/LumiCard.vue'

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
      <LumiCard
        v-for="(stat, idx) in [
          { key: 'tokens', icon: Zap, label: 'Token 消耗', value: usageData.tokens.toLocaleString(), trend: 'up', trendValue: '12%' },
          { key: 'requests', icon: Activity, label: '请求次数', value: usageData.requests.toLocaleString(), trend: 'up', trendValue: '8%' },
          { key: 'cost', icon: BarChart3, label: '费用 (CNY)', value: '¥' + usageData.cost.toFixed(2), trend: 'down', trendValue: '3%' },
          { key: 'memory', icon: Brain, label: '记忆条目', value: usageData.memory, trend: 'up', trendValue: '15%' },
        ]"
        :key="stat.key"
        class="stat-card"
        :style="{ animationDelay: `${(idx + 1) * 0.04}s` }"
        padding="md"
      >
        <div class="stat-icon-wrap" :class="stat.key">
          <component :is="stat.icon" :size="18" />
        </div>
        <div class="stat-body">
          <span class="stat-label">{{ stat.label }}</span>
          <span class="stat-value">{{ stat.value }}</span>
        </div>
        <div :class="['stat-trend', stat.trend]">
          <TrendingUp v-if="stat.trend === 'up'" :size="14" />
          <TrendingDown v-else :size="14" />
          {{ stat.trendValue }}
        </div>
      </LumiCard>
    </div>

    <div class="usage-content">
      <div class="left-col">
        <LumiCard class="section-card" :style="{ animationDelay: '0.10s' }" padding="md">
          <template #title>
            <Calendar :size="16" />
            <span>供应商用量</span>
          </template>
          <template #header>
            <BarChart3 :size="14" class="section-icon" />
          </template>
          <div class="provider-list">
            <div
              v-for="(p, idx) in apiProviders"
              :key="p.name"
              class="provider-row"
              :style="{ animationDelay: (0.14 + idx * 0.03) + 's' }"
            >
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
        </LumiCard>
      </div>

      <div class="right-col">
        <LumiCard class="section-card" :style="{ animationDelay: '0.12s' }" padding="md">
          <template #title>
            <Database :size="16" />
            <span>记忆与上下文</span>
          </template>
          <template #header>
            <Brain :size="14" class="section-icon" />
          </template>
          <div class="memory-bars">
            <div
              v-for="(m, idx) in memoryUsage"
              :key="m.type"
              class="memory-item"
              :style="{ animationDelay: (0.16 + idx * 0.03) + 's' }"
            >
              <div class="memory-label-row">
                <span class="memory-type">{{ m.type }}</span>
                <span class="memory-value">{{ m.used }} / {{ m.total }} {{ m.unit }}</span>
              </div>
              <div class="memory-bar-bg">
                <div class="memory-bar-fill" :style="{ width: (m.used / m.total * 100) + '%' }"></div>
              </div>
            </div>
          </div>
        </LumiCard>

        <LumiCard class="section-card" :style="{ animationDelay: '0.18s' }" padding="md">
          <template #title>
            <Clock :size="16" />
            <span>最近活动</span>
          </template>
          <template #header>
            <Activity :size="14" class="section-icon" />
          </template>
          <div class="activity-list">
            <div
              v-for="(a, idx) in recentActivity"
              :key="a.time + a.action"
              class="activity-item"
              :style="{ animationDelay: (0.22 + idx * 0.03) + 's' }"
            >
              <span class="activity-time">{{ a.time }}</span>
              <span :class="['activity-badge', a.type]">{{ a.action }}</span>
              <span class="activity-detail">{{ a.detail }}</span>
            </div>
          </div>
        </LumiCard>
      </div>
    </div>
  </div>
</template>

<style scoped>
.usage-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--space-6) var(--space-7);
  gap: var(--space-5);
  overflow-y: auto;
}

.usage-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.header-desc {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
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

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
}

.stat-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  animation: lumi-content-fade-up var(--duration-enter) var(--ease-default) both;
}

.stat-icon-wrap {
  width: var(--space-8);
  height: var(--space-8);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon-wrap.tokens {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
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

.usage-content {
  flex: 1;
  display: flex;
  gap: var(--space-4);
  min-height: 0;
}

.left-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.right-col {
  width: 360px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.section-card {
  flex: 1;
  animation: lumi-content-fade-up var(--duration-enter) var(--ease-default) both;
}

.section-icon {
  color: var(--text-muted);
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

.provider-name {
  width: 100px;
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  flex-shrink: 0;
}

.provider-stats {
  flex: 1;
  display: flex;
  gap: var(--space-3);
}

.provider-requests,
.provider-tokens {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.provider-cost {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  width: 70px;
  text-align: right;
  flex-shrink: 0;
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

.memory-bars {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.memory-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  animation: lumi-content-fade-up var(--duration-slow) var(--ease-default) both;
}

.memory-label-row {
  display: flex;
  justify-content: space-between;
}

.memory-type {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.memory-value {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.memory-bar-bg {
  height: 6px;
  border-radius: var(--radius-xs);
  background: var(--bg-secondary);
  overflow: hidden;
}

.memory-bar-fill {
  height: 100%;
  border-radius: var(--radius-xs);
  background: var(--lumi-brand);
  transition: width var(--transition-normal);
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.activity-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) 0;
  animation: lumi-content-fade-up var(--duration-slow) var(--ease-default) both;
}

.activity-time {
  font-size: var(--text-xs);
  color: var(--text-muted);
  width: var(--space-8);
  flex-shrink: 0;
}

.activity-badge {
  padding: 2px var(--space-1);
  border-radius: var(--radius-xs);
  font-size: var(--text-2xs);
  font-weight: var(--font-medium);
  width: 60px;
  text-align: center;
  flex-shrink: 0;
}

.activity-badge.api {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.activity-badge.memory {
  background: var(--task-purple-soft);
  color: var(--task-purple);
}

.activity-badge.context {
  background: var(--task-yellow-soft);
  color: var(--lumi-warning);
}

.activity-detail {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

</style>
