<script setup lang="ts">
import { ChevronRight } from 'lucide-vue-next'
import type { SectionActionItem, SectionItem, SectionTimeRangeItem, SectionValue } from './types'

defineProps<{
  section: string
  items: SectionItem[]
}>()

const emit = defineEmits<{
  /** 值控件变更事件：key + 新值，由父组件更新数据源并持久化 */
  change: [key: string, value: SectionValue]
  /** 动作行点击事件：由父组件处理导航或对应功能 */
  select: [key: string]
}>()

/** 动作行缺省文案（按 type 推断，可用 item.actionText 覆盖） */
const ACTION_DEFAULT_TEXT: Record<SectionActionItem['type'], string> = {
  list: '查看',
  button: '前往',
  connect: '连接',
  action: '配置'
}

function isActionItem(item: SectionItem): item is SectionActionItem {
  return item.type === 'list' || item.type === 'button' || item.type === 'connect' || item.type === 'action'
}

function actionText(item: SectionItem): string {
  if (!isActionItem(item)) return ACTION_DEFAULT_TEXT.action
  return item.actionText ?? ACTION_DEFAULT_TEXT[item.type]
}

/** 时间段拆分为 [开始, 结束]，允许空值 */
function splitTimeRange(item: SectionTimeRangeItem): [string, string] {
  const [start = '', end = ''] = (item.value || '').split('-')
  return [start, end]
}

function updateTimeRange(item: SectionTimeRangeItem, part: 'start' | 'end', value: string): void {
  const [start, end] = splitTimeRange(item)
  emit('change', item.key, part === 'start' ? `${value}-${end}` : `${start}-${value}`)
}

function readControlValue(event: Event): string {
  return (event.target as HTMLInputElement | HTMLSelectElement).value
}
</script>

<template>
  <div class="settings-panel animate-slide-up">
    <section class="settings-card">
      <div class="settings-card__body settings-card__body--compact">
        <div
          v-for="item in items"
          :key="item.key"
          class="settings-list-row"
        >
          <div class="settings-list-row__info">
            <span class="settings-list-row__title">{{ item.label }}</span>
            <span class="settings-list-row__desc">{{ item.desc }}</span>
          </div>
          <div class="settings-list-row__control">
            <!-- 开关：真实 switch 按钮，支持 Enter/Space -->
            <button
              v-if="item.type === 'toggle'"
              type="button"
              role="switch"
              class="lumi-toggle"
              :class="{ 'is-active': item.value }"
              :aria-checked="item.value"
              :aria-label="item.label"
              @click="emit('change', item.key, !item.value)"
            />

            <!-- 下拉选择 -->
            <select
              v-else-if="item.type === 'select'"
              class="settings-form-select settings-row-field"
              :value="item.value"
              :aria-label="item.label"
              @change="emit('change', item.key, readControlValue($event))"
            >
              <option v-for="opt in item.options" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>

            <!-- 文本 / 密码输入 -->
            <input
              v-else-if="item.type === 'input' || item.type === 'password'"
              :type="item.type"
              class="settings-form-input settings-row-field"
              :value="item.value"
              :placeholder="item.placeholder ?? (item.type === 'password' ? '请输入密码' : '请输入')"
              :aria-label="item.label"
              autocomplete="off"
              @change="emit('change', item.key, readControlValue($event))"
            />

            <!-- 滑块 -->
            <div v-else-if="item.type === 'slider'" class="settings-row-slider">
              <input
                type="range"
                :value="item.value"
                :min="item.min"
                :max="item.max"
                :step="item.step ?? 1"
                :aria-label="item.label"
                @input="emit('change', item.key, Number(readControlValue($event)))"
              />
              <span class="settings-row-slider__value">{{ item.value }}{{ item.unit ?? '' }}</span>
            </div>

            <!-- 时间段 -->
            <div v-else-if="item.type === 'time'" class="settings-row-time">
              <input
                type="time"
                class="settings-form-input settings-row-field settings-row-field--time"
                :value="splitTimeRange(item)[0]"
                :aria-label="`${item.label}开始时间`"
                @change="updateTimeRange(item, 'start', readControlValue($event))"
              />
              <span class="settings-row-time__sep">至</span>
              <input
                type="time"
                class="settings-form-input settings-row-field settings-row-field--time"
                :value="splitTimeRange(item)[1]"
                :aria-label="`${item.label}结束时间`"
                @change="updateTimeRange(item, 'end', readControlValue($event))"
              />
            </div>

            <!-- 动作行：真实按钮，触发 select 事件 -->
            <button
              v-else
              type="button"
              class="settings-row-control settings-row-control--action"
              @click="emit('select', item.key)"
            >
              <span>{{ actionText(item) }}</span>
              <ChevronRight :size="14" />
            </button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings-list-row__title {
  font-weight: 500;
}

/* 行内值控件统一宽度，避免不同控件撑开不一致 */
.settings-row-field {
  width: 160px;
}

.settings-row-field--time {
  width: 104px;
}

.settings-row-slider {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.settings-row-slider input[type='range'] {
  width: 120px;
  accent-color: var(--lumi-brand);
}

.settings-row-slider__value {
  min-width: 40px;
  text-align: right;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.settings-row-time {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.settings-row-time__sep {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

/* 动作行是可点击按钮：在占位控件样式基础上恢复指针与键盘焦点样式 */
.settings-row-control--action {
  cursor: pointer;
  font-family: inherit;
  font-weight: 500;
}

.settings-row-control--action:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 2px;
}
</style>
