<script setup lang="ts">
import LumiCard from '../common/LumiCard.vue'
import {
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-vue-next'
import type { UsageMetric } from './types'

interface Props {
  apiMetrics: UsageMetric[]
  contextMetrics: UsageMetric[]
}

defineProps<Props>()
</script>

<template>
  <LumiCard class="panel-card chart-panel" padding="none">
    <template #title>
      <div class="panel-title-group">
        <BarChart3 :size="18" class="panel-icon shrink-0" style="color: var(--lumi-success)" />
        <h3>用量统计</h3>
        <span class="panel-badge green">Live</span>
      </div>
    </template>
    <template #header>
      <div class="chart-period-selector">
        <button class="period-btn active">7天</button>
        <button class="period-btn">30天</button>
        <button class="period-btn">90天</button>
      </div>
    </template>
    <div class="chart-area">
      <div class="big-chart-svg-wrap">
        <svg viewBox="0 0 400 160" class="area-chart" preserveAspectRatio="none">
          <defs>
            <linearGradient id="chartGrad1" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="var(--lumi-primary)" stop-opacity="0.3" />
              <stop offset="100%" stop-color="var(--lumi-primary)" stop-opacity="0.02" />
            </linearGradient>
            <linearGradient id="chartGrad2" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="var(--lumi-success)" stop-opacity="0.25" />
              <stop offset="100%" stop-color="var(--lumi-success)" stop-opacity="0.02" />
            </linearGradient>
          </defs>
          <path
            d="M0,140 Q40,120 80,100 T160,70 T240,90 T320,50 T400,35 L400,160 L0,160 Z"
            fill="url(#chartGrad1)"
            class="chart-area-fill"
          />
          <path
            d="M0,140 Q40,120 80,100 T160,70 T240,90 T320,50 T400,35"
            fill="none"
            stroke="var(--lumi-primary)"
            stroke-width="2.5"
            stroke-linecap="round"
            class="chart-line animate-draw"
          />
          <path
            d="M0,150 Q50,135 100,125 T200,110 T300,95 T400,80 L400,160 L0,160 Z"
            fill="url(#chartGrad2)"
            class="chart-area-fill"
            style="animation-delay: 0.3s"
          />
          <path
            d="M0,150 Q50,135 100,125 T200,110 T300,95 T400,80"
            fill="none"
            stroke="var(--lumi-success)"
            stroke-width="2"
            stroke-linecap="round"
            class="chart-line animate-draw"
            style="animation-delay: 0.3s"
          />
          <circle cx="400" cy="35" r="4" fill="var(--lumi-primary)" class="chart-dot pulse-dot" />
          <circle
            cx="400"
            cy="80"
            r="4"
            fill="var(--lumi-success)"
            class="chart-dot pulse-dot"
            style="animation-delay: 0.5s"
          />
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
      <div
        v-for="m in [...apiMetrics, ...contextMetrics].slice(0, 4)"
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
            :style="{
              width: typeof m.value === 'number'
                ? Math.min(100, m.value / (m.unit.includes('ms') ? 500 : m.unit.includes('%') ? 100 : m.unit.includes('tokens') ? 16384 : 100)) + '%'
                : '65%',
              background: m.color,
            }"
          />
        </div>
        <span class="umi-value">{{ m.value }}{{ m.unit }}</span>
      </div>
    </div>
  </LumiCard>
</template>

<style scoped>
.panel-card {
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-card :deep(.lumi-card__body) {
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

.panel-badge.green { background: var(--task-green-soft); color: var(--lumi-success); }

.chart-panel {
  flex: 1.2;
}

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
</style>
