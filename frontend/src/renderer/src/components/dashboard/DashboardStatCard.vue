<script setup lang="ts">
import { ArrowUpRight, ArrowDownRight } from 'lucide-vue-next'
import type { UsageMetric } from './types'

interface Props {
  metrics: UsageMetric[]
}

defineProps<Props>()
</script>

<template>
  <div class="stat-cards-row">
    <div
      v-for="(metric, idx) in metrics"
      :key="metric.label"
      class="stat-card lumi-card"
      :style="{ '--card-delay': `${idx * 0.08}s`, '--accent-color': metric.color }"
    >
      <div class="stat-card-header">
        <span class="stat-label">{{ metric.label }}</span>
        <component
          :is="metric.trend === 'up' ? ArrowUpRight : ArrowDownRight"
          :size="16"
          :class="['trend-icon', metric.trend]"
        />
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
</template>

<style scoped>
.stat-cards-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}

.stat-card {
  position: relative;
  padding: var(--space-5);
  overflow: hidden;
  opacity: 0;
  animation: statCardIn var(--duration-enter) var(--ease-out-expo) both;
  animation-delay: var(--card-delay);
  transition: all var(--transition-normal);
}

@keyframes statCardIn {
  from { opacity: 0; transform: translateY(var(--space-3)); }
  to { opacity: 1; transform: translateY(0); }
}

.stat-card:hover {
  border-color: var(--accent-color);
  box-shadow: var(--shadow-md);
  transform: translateY(calc(var(--space-1) / -2));
}

.stat-card-glow {
  position: absolute;
  top: calc(var(--space-8) * -1);
  right: calc(var(--space-8) * -1);
  width: calc(var(--space-8) * 2.5);
  height: calc(var(--space-8) * 2.5);
  border-radius: var(--radius-full);
  background: radial-gradient(circle, color-mix(in srgb, var(--accent-color) 12%, transparent) 0%, transparent 70%);
  pointer-events: none;
}

.stat-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: var(--font-medium);
}

.trend-icon {
  color: var(--text-muted);
}

.trend-icon.up { color: var(--lumi-success); }
.trend-icon.down { color: var(--lumi-danger); }

.stat-card-body {
  display: flex;
  align-items: baseline;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
}

.stat-value {
  font-size: var(--text-4xl);
  font-weight: var(--font-bold);
  color: var(--text);
  line-height: var(--leading-none);
}

.stat-unit {
  font-size: var(--text-base);
  color: var(--text-muted);
}

.stat-card-footer {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.change-badge {
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
  padding: var(--badge-padding);
  border-radius: var(--radius-xs);
}

.change-badge.up { background: var(--task-green-soft); color: var(--lumi-success); }
.change-badge.down { background: var(--task-red-soft); color: var(--lumi-danger); }

.change-label {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}
</style>
