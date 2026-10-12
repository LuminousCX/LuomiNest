<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { TimelineTaskEntry, TimelineUnplacedTask } from './types'

/**
 * 24 小时全天时间轴（定时任务视图专用，展示层组件）
 *
 * - 横轴 0-23 时，每小时刻度；当前小时列高亮
 * - 任务按触发时刻在轴上打点，同一小时多个任务堆叠计数
 * - 当前时刻竖线（每 30s 由父组件刷新 now）
 * - hour 字段为 `*` 的任务以"每小时"横带呈现
 * - 无法定位到固定小时的任务（interval / once）在轴下方以弱化条目列出
 *
 * 视觉约束：hairline 轴线、--text-muted 刻度、任务点单色 --lumi-brand，无彩色堆砌。
 */
const props = defineProps<{
  entries: TimelineTaskEntry[]
  unplaced: TimelineUnplacedTask[]
  /** hour 为 `*`（每小时触发）的任务数 */
  hourlyCount: number
  now: Date
}>()

const { t } = useI18n()

interface HourGroup {
  hour: number
  items: TimelineTaskEntry[]
}

const hourGroups = computed<HourGroup[]>(() => {
  const map = new Map<number, TimelineTaskEntry[]>()
  for (const entry of props.entries) {
    const list = map.get(entry.hour)
    if (list) list.push(entry)
    else map.set(entry.hour, [entry])
  }
  return [...map.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([hour, items]) => ({
      hour,
      items: [...items].sort((a, b) => a.minute - b.minute)
    }))
})

const hasTimelineContent = computed(() => hourGroups.value.length > 0 || props.hourlyCount > 0)

/** 小时列中心点（含半列偏移） */
const hourCenter = (hour: number): string => `${((hour + 0.5) / 24) * 100}%`

const currentHour = computed(() => props.now.getHours())

const nowLineLeft = computed(() => {
  const ratio = (props.now.getHours() * 60 + props.now.getMinutes()) / 1440
  return `${ratio * 100}%`
})

const nowLabel = computed(() => {
  const h = String(props.now.getHours()).padStart(2, '0')
  const m = String(props.now.getMinutes()).padStart(2, '0')
  return `${h}:${m}`
})

const entryTime = (entry: TimelineTaskEntry): string => {
  if (entry.minute > 0) {
    return `${String(entry.hour).padStart(2, '0')}:${String(entry.minute).padStart(2, '0')}`
  }
  return `${String(entry.hour).padStart(2, '0')}:00`
}

const tooltipMax = 8
const tipOverflow = (group: HourGroup): TimelineTaskEntry[] => group.items.slice(tooltipMax)
</script>

<template>
  <section class="tl-card">
    <header class="tl-header">
      <div class="tl-title">
        <span>{{ t('tasks.scheduled.timelineTitle') }}</span>
        <span v-if="entries.length > 0" class="tl-count">{{ entries.length }}</span>
      </div>
      <div class="tl-header-side">
        <span v-if="hourlyCount > 0" class="tl-hourly-tag">{{ t('tasks.scheduled.timelineHourlyTag', { n: hourlyCount }) }}</span>
      </div>
    </header>

    <div class="tl-plot">
      <!-- 当前小时列底色 -->
      <div class="tl-nowband" :style="{ left: `${(currentHour / 24) * 100}%`, width: `${100 / 24}%` }"></div>

      <!-- 每小时（hour = *）任务横带 -->
      <div v-if="hourlyCount > 0" class="tl-hourly-band"></div>

      <!-- 小时刻度 -->
      <div class="tl-ticks">
        <span v-for="h in 25" :key="h" class="tl-tick" :style="{ left: `${((h - 1) / 24) * 100}%` }"></span>
      </div>

      <!-- 基线 -->
      <div class="tl-baseline"></div>

      <!-- 空态 -->
      <div v-if="!hasTimelineContent" class="tl-empty">{{ t('tasks.scheduled.timelineEmptyHint') }}</div>

      <!-- 任务打点 -->
      <div
        v-for="group in hourGroups"
        :key="group.hour"
        class="tl-group"
        :style="{ left: hourCenter(group.hour) }"
      >
        <span class="tl-stem" :class="{ stacked: group.items.length > 1 }"></span>
        <span class="tl-dot" :class="{ stacked: group.items.length > 1 }">{{ group.items.length > 1 ? group.items.length : '' }}</span>
        <div class="tl-tip" :class="{ 'tl-tip--left': group.hour <= 2, 'tl-tip--right': group.hour >= 21 }">
          <div v-for="item in group.items.slice(0, tooltipMax)" :key="item.id" class="tl-tip-row">
            <span class="tl-tip-time">{{ entryTime(item) }}</span>
            <span class="tl-tip-name">{{ item.name }}</span>
            <span class="tl-tip-summary">{{ item.summary }}</span>
          </div>
          <div v-if="tipOverflow(group).length > 0" class="tl-tip-more">
            {{ t('tasks.scheduled.timelineMore', { n: tipOverflow(group).length }) }}
          </div>
        </div>
      </div>

      <!-- 当前时刻线 -->
      <div class="tl-now" :style="{ left: nowLineLeft }">
        <span class="tl-now-label">{{ t('tasks.scheduled.timelineNow') }} {{ nowLabel }}</span>
      </div>
    </div>

    <!-- 0-23 刻度标签 -->
    <div class="tl-scale">
      <span
        v-for="h in 24"
        :key="h"
        :class="['tl-scale-label', { 'is-current': h - 1 === currentHour }]"
      >{{ String(h - 1).padStart(2, '0') }}</span>
    </div>

    <!-- 无法定位固定时刻的任务 -->
    <footer v-if="unplaced.length > 0" class="tl-unplaced">
      <span class="tl-unplaced-title">{{ t('tasks.scheduled.unplacedTitle') }}</span>
      <div class="tl-unplaced-list">
        <span
          v-for="item in unplaced"
          :key="item.id"
          :class="['tl-unplaced-chip', { dim: item.dim }]"
          :title="item.name"
        >
          <span class="tl-unplaced-name">{{ item.name }}</span>
          <span class="tl-unplaced-note">{{ item.note }}</span>
        </span>
      </div>
    </footer>
  </section>
</template>

<style scoped>
.tl-card {
  padding: var(--space-3) var(--space-4) var(--space-4);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  /* 窄窗口横向滚动，轴与刻度保持整体 */
  overflow-x: auto;
}

.tl-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.tl-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text);
}

.tl-count {
  font-size: var(--text-2xs);
  font-weight: 500;
  color: var(--text-muted);
  padding: 1px var(--space-2);
  background: var(--workspace-hover);
  border-radius: var(--radius-full);
}

.tl-header-side {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.tl-hourly-tag {
  font-size: var(--text-2xs);
  color: var(--lumi-brand);
  padding: 1px var(--space-2);
  background: var(--lumi-brand-light);
  border-radius: var(--radius-full);
}

/* ===== 轴区 ===== */
.tl-plot {
  position: relative;
  height: 96px;
  min-width: 640px;
}

.tl-nowband {
  position: absolute;
  top: 12px;
  bottom: 0;
  background: var(--workspace-hover);
  opacity: 0.55;
  border-radius: 2px 2px 0 0;
  pointer-events: none;
}

.tl-hourly-band {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 5px;
  background: var(--lumi-brand-light);
  border-radius: var(--radius-xs);
  pointer-events: none;
}

.tl-ticks {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.tl-tick {
  position: absolute;
  bottom: 0;
  width: 1px;
  height: 5px;
  background: var(--workspace-border);
}

.tl-baseline {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  background: var(--workspace-border);
  pointer-events: none;
}

.tl-empty {
  position: absolute;
  inset: 12px 0 1px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
  color: var(--text-muted);
}

/* ===== 任务打点 ===== */
.tl-group {
  position: absolute;
  bottom: 0;
  width: 20px;
  height: 100%;
  transform: translateX(-50%);
  cursor: default;
  z-index: 2;
}

.tl-group:hover {
  z-index: 5;
}

.tl-stem {
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 1px;
  height: 34px;
  background: var(--lumi-brand);
  opacity: 0.35;
}

.tl-stem.stacked {
  height: 46px;
}

.tl-dot {
  position: absolute;
  bottom: 31px;
  left: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 7px;
  height: 7px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
  font-size: 10px;
  font-weight: 600;
  line-height: 1;
  color: var(--text-inverse);
  transform: translateX(-50%);
  transition: transform var(--duration-fast) var(--ease-in-out);
}

.tl-dot.stacked {
  bottom: 37px;
  width: 18px;
  height: 18px;
}

.tl-group:hover .tl-dot {
  transform: translateX(-50%) scale(1.2);
}

/* ===== tooltip ===== */
.tl-tip {
  position: absolute;
  bottom: 66px;
  left: 50%;
  transform: translateX(-50%);
  min-width: 160px;
  max-width: 260px;
  padding: var(--space-2) var(--space-3);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-md);
  opacity: 0;
  visibility: hidden;
  transition: opacity var(--duration-fast) var(--ease-in-out);
  pointer-events: none;
  z-index: 6;
}

.tl-group:hover .tl-tip {
  opacity: 1;
  visibility: visible;
}

.tl-tip--left {
  left: 0;
  transform: translateX(-12%);
}

.tl-tip--right {
  left: auto;
  right: 0;
  transform: translateX(12%);
}

.tl-tip-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  padding: 2px 0;
  min-width: 0;
}

.tl-tip-row + .tl-tip-row {
  border-top: 1px solid var(--workspace-border);
}

.tl-tip-time {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--lumi-brand);
  flex-shrink: 0;
}

.tl-tip-name {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.tl-tip-summary {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  flex-shrink: 0;
}

.tl-tip-more {
  padding-top: var(--space-1);
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

/* ===== 当前时刻线 ===== */
.tl-now {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--lumi-brand);
  opacity: 0.6;
  pointer-events: none;
  z-index: 3;
}

.tl-now-label {
  position: absolute;
  top: 0;
  left: 4px;
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 500;
  line-height: 1.4;
  white-space: nowrap;
  color: var(--lumi-brand);
  background: var(--workspace-card);
  border: 1px solid var(--lumi-brand);
  border-radius: var(--radius-full);
  transform: translateX(-4px);
}

/* ===== 0-23 刻度标签 ===== */
.tl-scale {
  display: grid;
  grid-template-columns: repeat(24, 1fr);
  margin-top: var(--space-2);
  min-width: 640px;
}

.tl-scale-label {
  text-align: center;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
  line-height: 1;
}

.tl-scale-label.is-current {
  color: var(--lumi-brand);
  font-weight: 600;
}

/* ===== 不定时任务 ===== */
.tl-unplaced {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px dashed var(--workspace-border);
}

.tl-unplaced-title {
  flex-shrink: 0;
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.tl-unplaced-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  min-width: 0;
}

.tl-unplaced-chip {
  display: inline-flex;
  align-items: baseline;
  gap: var(--space-2);
  max-width: 100%;
  padding: 2px var(--space-2);
  background: var(--workspace-hover);
  border-radius: var(--radius-xs);
}

.tl-unplaced-chip.dim {
  opacity: 0.55;
}

.tl-unplaced-name {
  font-size: var(--text-xs);
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.tl-unplaced-note {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  white-space: nowrap;
}
</style>
