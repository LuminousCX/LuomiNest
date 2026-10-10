<script lang="ts">
import type { Component } from 'vue'

/** 单个分段选项；icon 传 lucide-vue-next 图标组件（可选），badge 为可选角标（数字 / 短文本） */
export interface SegmentTabOption<T extends string = string> {
  value: T
  label: string
  icon?: Component
  badge?: string | number
}
</script>

<script setup lang="ts" generic="T extends string">
/**
 * SegmentTabs — 全局胶囊分段器（移植自 vue-bits RubberSegment，MIT）
 *
 * 白色药丸滑块 + 橡皮筋弹性动画（弹簧 overshoot、拖拽阻尼、甩动惯性），参数照搬上游：
 * 点击 → 拉伸(DILATE)后松手回弹(spring momentum)；按住滑块可拖拽，越界有橡皮筋阻尼，
 * 快速甩动按速度惯性投掷落点。颜色全部取自主题变量：底座 --bg-secondary、滑块 --surface +
 * --shadow-xs、未选中 --text-muted、滑块上 --text，深浅主题自动适配。
 *
 * 尺寸两档：lg（页面级主 tab，高 36px / --text-base）、sm（面板内小切换，高 26px / --text-xs）。
 * 键盘可达：role=tablist/tab、roving tabindex、←/→/Home/End；
 * prefers-reduced-motion 时动画降级为直接切换。选项过多时整条横向滚动（不换行）。
 */
import { animate, motion, motionValue, useReducedMotion, useTransform, type MotionValue } from 'motion-v'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = withDefaults(
  defineProps<{
    options: SegmentTabOption<T>[]
    modelValue: T
    size?: 'lg' | 'sm'
    disabled?: boolean
    ariaLabel?: string
  }>(),
  { size: 'lg', disabled: false, ariaLabel: '' }
)

const emit = defineEmits<{ 'update:modelValue': [value: T] }>()

defineOptions({ name: 'SegmentTabs' })

const { t } = useI18n()

/* ── 弹簧 / 橡皮筋参数（vue-bits 原样移植） ─────────────────────────────── */
type Sample = [number, number]
type DragState = {
  id: number
  x0: number
  slot: number
  onThumb: boolean
  live: boolean
  offset: number
  w: number
  hist: Sample[]
}

const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1]
const SPRING_UI = { type: 'spring' as const, duration: 0.3, bounce: 0 }
const SPRING_MOMENTUM = { type: 'spring' as const, duration: 0.4, bounce: 0.2 }
const SPRING_RELAX = { type: 'spring' as const, duration: 0.16, bounce: 0 }
const DILATE = 0.19
const HANDOFF = 0.15
const FLICK = 110
const MAX_VELOCITY = 2000
const DEADZONE = 4
const SLOP = 10
const RUBBER = 0.55

/** 两档尺寸：总高/字号/内衬走 CSS 变量（见 style），JS 只需要内衬像素值与图标尺寸 */
const PRESETS = {
  lg: { inset: 3, icon: 14 },
  sm: { inset: 2, icon: 12 },
} as const

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))
/** 越界阻尼：超出越多阻力越大（橡皮筋手感） */
const rubber = (over: number, dim: number) => (over * dim * RUBBER) / (dim + RUBBER * Math.abs(over))
/** 甩动速度 → 惯性投掷距离 */
const project = (v: number, glide = 75) => {
  const d = 1 - 0.1 * Math.pow(0.05, glide / 100)
  return ((v / 1000) * d) / (1 - d)
}
const velocityOf = (hist: Sample[], now: number) => {
  const recent = hist.filter(([time]) => now - time <= 100)
  if (recent.length < 2) return 0
  const [t0, x0] = recent[0]
  const [t1, x1] = recent[recent.length - 1]
  return t1 - t0 >= 8 ? ((x1 - x0) / (t1 - t0)) * 1000 : 0
}
const nearestSlot = (slotList: Slot[], x: number) => {
  let best = 0
  for (let i = 1; i < slotList.length; i++) {
    if (Math.abs((slotList[i].l + slotList[i].r) / 2 - x) < Math.abs((slotList[best].l + slotList[best].r) / 2 - x))
      best = i
  }
  return best
}

type Slot = { l: number; r: number }

/* ── 选中态与测量 ───────────────────────────────────────────────────────── */
const index = computed(() => Math.max(0, props.options.findIndex((opt) => opt.value === props.modelValue)))
const reduce = useReducedMotion()
const iconSize = computed(() => PRESETS[props.size].icon)
const insetOf = () => PRESETS[props.size].inset

const trackRef = ref<HTMLDivElement | null>(null)
const itemEls: (HTMLButtonElement | null)[] = []
let slots: Slot[] = []
let box: DOMRect | null = null
let committed = index.value
let handoff: ReturnType<typeof setTimeout> | undefined
let drag: DragState | null = null
let gen = 0
let observer: ResizeObserver | null = null

const edgeL = motionValue(0)
const edgeR = motionValue(0)
const innerW = motionValue(0)
// 药丸几何与揭示裁剪都由这两个边沿运动值驱动，动画只作用于它们
const thumbW = useTransform([edgeL, edgeR] as MotionValue<number>[], ([l, r]: number[]) => Math.max(0, r - l))
const clipPath = useTransform(
  [edgeL, edgeR, innerW] as MotionValue<number>[],
  ([l, r, w]: number[]) => `inset(0 ${Math.max(0, w - r)}px 0 ${Math.max(0, l)}px round var(--st-thumb-radius))`
)

const jumpTo = (i: number) => {
  const s = slots[i]
  if (!s) return
  clearTimeout(handoff)
  gen += 1
  edgeL.jump(s.l)
  edgeR.jump(s.r)
}

const measure = () => {
  const track = trackRef.value
  if (!track) return
  const rect = track.getBoundingClientRect()
  const inset = insetOf()
  slots = props.options.map((_, i) => {
    const el = itemEls[i]
    if (!el) return { l: 0, r: 0 }
    const r = el.getBoundingClientRect()
    return { l: r.left - rect.left - inset, r: r.right - rect.left - inset }
  })
  innerW.set(rect.width - inset * 2)
  jumpTo(committed)
}

const optionsKey = computed(() =>
  props.options.map((o) => `${o.value}\u0000${o.label}\u0000${o.badge ?? ''}`).join('|')
)

onMounted(() => {
  measure()
  observer = new ResizeObserver(measure)
  if (trackRef.value) observer.observe(trackRef.value)
  if (typeof document !== 'undefined' && document.fonts) document.fonts.ready.then(measure)
})

watch([optionsKey, () => props.size], measure, { flush: 'post' })

// 外部 v-model 变化 → 滑块直接就位（交互内部的动画由 travel/land 负责）
watch(
  index,
  (next) => {
    if (!drag && committed !== next) {
      committed = next
      jumpTo(next)
    }
  },
  { flush: 'post' }
)

onUnmounted(() => {
  observer?.disconnect()
  clearTimeout(handoff)
  edgeL.stop()
  edgeR.stop()
})

const commit = (i: number) => {
  committed = i
  if (i === index.value) return
  const opt = props.options[i]
  if (opt) emit('update:modelValue', opt.value)
}

/* ── 滑块动画：拉伸 → 弹簧落点（可带惯性/挤压） ─────────────────────────── */
const land = (to: number, v: number | null, flick: boolean, withSquash: boolean) => {
  const b = slots[to]
  if (!b) return
  const g = ++gen
  const dir = Math.sign((b.l + b.r) / 2 - (edgeL.get() + edgeR.get()) / 2) || 1
  const [lead, leadTo, trail, trailTo] = dir > 0 ? [edgeR, b.r, edgeL, b.l] : [edgeL, b.l, edgeR, b.r]
  const velocityFor = (mv: MotionValue<number>) => clamp(v === null ? mv.getVelocity() : v, -MAX_VELOCITY, MAX_VELOCITY)
  animate(lead, leadTo, {
    ...(flick ? SPRING_MOMENTUM : SPRING_UI),
    duration: flick ? 0.4 : 0.3,
    velocity: velocityFor(lead)
  })
  const trailVelocity = velocityFor(trail)
  if (!withSquash) {
    animate(trail, trailTo, { ...SPRING_UI, duration: 0.3, velocity: trailVelocity })
    return
  }
  // 后沿先轻微过冲再放松 → 药丸被"挤压"一下的橡皮筋质感
  animate(trail, trailTo + dir * 3, { ...SPRING_UI, duration: 0.3, velocity: trailVelocity }).then(() => {
    if (gen === g) animate(trail, trailTo, { ...SPRING_RELAX, duration: 0.16 })
  })
}

const travel = (from: number, to: number) => {
  const a = slots[from]
  const b = slots[to]
  if (!a || !b) return
  clearTimeout(handoff)
  gen += 1
  if (reduce.value) {
    edgeL.jump(b.l)
    edgeR.jump(b.r)
    return
  }
  // 先把药丸拉长覆盖起点→终点（0.19s），再交给弹簧收缩落位
  const tween = { duration: DILATE, ease: EASE_OUT }
  animate(edgeL, b.l + (Math.min(a.l, b.l) - b.l) * 1, tween)
  animate(edgeR, b.r + (Math.max(a.r, b.r) - b.r) * 1, tween)
  handoff = setTimeout(() => land(to, null, false, true), HANDOFF * 1000)
}

/* ── 指针交互：点击 / 拖拽滑块（带橡皮筋阻尼）/ 甩动 ─────────────────────── */
const localX = (e: { clientX: number }) => e.clientX - (box ? box.left : 0) - insetOf()

const onPointerDown = (e: PointerEvent, i: number) => {
  if (props.disabled || drag || e.button !== 0) return
  box = trackRef.value?.getBoundingClientRect() ?? null
  const el = e.currentTarget as HTMLElement
  try {
    el.setPointerCapture(e.pointerId)
  } catch {
    // capture 不可用时忽略
  }
  const x = localX(e)
  const onThumb = x >= edgeL.get() && x <= edgeR.get()
  drag = { id: e.pointerId, x0: x, slot: i, onThumb, live: false, offset: 0, w: 0, hist: [[e.timeStamp, x]] }
  if (onThumb) {
    clearTimeout(handoff)
    gen += 1
    edgeL.stop()
    edgeR.stop()
  } else if (!reduce.value) {
    el.dataset.pressed = ''
  }
}

const onPointerMove = (e: PointerEvent) => {
  const d = drag
  if (!d || e.pointerId !== d.id || !d.onThumb) return
  const x = localX(e)
  d.hist.push([e.timeStamp, x])
  if (d.hist.length > 8) d.hist.shift()
  if (!d.live) {
    if (Math.abs(x - d.x0) < DEADZONE) return
    d.live = true
    d.offset = x - edgeL.get()
    d.w = edgeR.get() - edgeL.get()
    trackRef.value?.setAttribute('data-held', '')
  }
  const width = innerW.get()
  const l = x - d.offset
  const maxL = width - d.w
  if (reduce.value) {
    const c = clamp(l, 0, maxL)
    edgeL.set(c)
    edgeR.set(c + d.w)
  } else if (l < 0) {
    edgeL.set(0)
    edgeR.set(d.w - rubber(-l, d.w))
  } else if (l > maxL) {
    edgeR.set(width)
    edgeL.set(maxL + rubber(l - maxL, d.w))
  } else {
    edgeL.set(l)
    edgeR.set(l + d.w)
  }
}

const release = (d: DragState) => {
  drag = null
  trackRef.value?.removeAttribute('data-held')
  const el = itemEls[d.slot]
  if (el) delete el.dataset.pressed
}

const onPointerUp = (e: PointerEvent) => {
  const d = drag
  if (!d || e.pointerId !== d.id) return
  release(d)
  const x = localX(e)
  if (!d.live) {
    // 原地点击（未进入拖拽）：轻微位移容差内视为选择
    if (Math.abs(x - d.x0) <= SLOP && d.slot !== committed) {
      const from = committed
      commit(d.slot)
      travel(from, d.slot)
    }
    return
  }
  const v = velocityOf(d.hist, e.timeStamp)
  const flick = Math.abs(v) > FLICK
  let to = nearestSlot(slots, (edgeL.get() + edgeR.get()) / 2 + project(v))
  if (flick && to === committed) to = clamp(to + Math.sign(v), 0, props.options.length - 1)
  commit(to)
  if (reduce.value) jumpTo(to)
  else land(to, v, flick, flick)
}

const onPointerCancel = (e: PointerEvent) => {
  const d = drag
  if (!d || e.pointerId !== d.id) return
  release(d)
  if (!d.live) return
  if (reduce.value) jumpTo(committed)
  else land(committed, null, false, false)
}

/* ── 键盘：水平 tablist 的方向键 / Home / End ────────────────────────────── */
const onKeyDown = (e: KeyboardEvent) => {
  if (props.disabled) return
  const last = props.options.length - 1
  let next: number | null = null
  if (e.key === 'ArrowRight') next = Math.min(last, index.value + 1)
  else if (e.key === 'ArrowLeft') next = Math.max(0, index.value - 1)
  else if (e.key === 'Home') next = 0
  else if (e.key === 'End') next = last
  if (next === null) return
  e.preventDefault()
  if (next === index.value) return
  const from = committed
  commit(next)
  if (reduce.value) jumpTo(next)
  else travel(from, next)
  itemEls[next]?.focus()
  itemEls[next]?.scrollIntoView({ inline: 'nearest', block: 'nearest' })
}
</script>

<template>
  <div class="segment-tabs">
    <div
      ref="trackRef"
      class="st-tabs"
      :class="[`size-${size}`, { 'is-disabled': disabled }]"
      role="tablist"
      :aria-label="ariaLabel || t('common.segmentedControl')"
      :aria-disabled="disabled || undefined"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerCancel"
      @lostpointercapture="onPointerCancel"
    >
      <button
        v-for="(opt, i) in options"
        :key="opt.value"
        :ref="(el) => (itemEls[i] = el as HTMLButtonElement | null)"
        type="button"
        role="tab"
        class="st-tab"
        :aria-selected="i === index"
        :tabindex="i === index ? 0 : -1"
        :disabled="disabled"
        @pointerdown="onPointerDown($event, i)"
        @keydown="onKeyDown"
      >
        <component :is="opt.icon" v-if="opt.icon" :size="iconSize" :stroke-width="2" class="st-icon" />
        <span class="st-label">{{ opt.label }}</span>
        <span v-if="opt.badge !== undefined && opt.badge !== ''" class="st-badge">{{ opt.badge }}</span>
      </button>

      <!-- 药丸滑块：几何实时跟随 edgeL/edgeR（弹簧 overshoot / 拖拽阻尼都作用在这两个值上） -->
      <motion.div class="st-thumb" aria-hidden="true" :style="{ x: edgeL, width: thumbW }" />

      <!-- 选中态揭示层：clip-path 跟随滑块圆角窗口，文字/图标/角标在药丸上反色显示 -->
      <motion.div class="st-thumb-labels" aria-hidden="true" :style="{ clipPath }">
        <span v-for="opt in options" :key="opt.value" class="st-tab is-ghost">
          <component :is="opt.icon" v-if="opt.icon" :size="iconSize" :stroke-width="2" class="st-icon" />
          <span class="st-label">{{ opt.label }}</span>
          <span v-if="opt.badge !== undefined && opt.badge !== ''" class="st-badge">{{ opt.badge }}</span>
        </span>
      </motion.div>
    </div>
  </div>
</template>

<style scoped>
/* 外层视口：选项过多时整条横向滚动，滚动条隐藏 */
.segment-tabs {
  max-width: 100%;
  overflow-x: auto;
  scrollbar-width: none;
  -webkit-tap-highlight-color: transparent;
}

.segment-tabs::-webkit-scrollbar {
  display: none;
}

/* ── 底座（胶囊轨道）── */
.st-tabs {
  --st-h: 36px;
  --st-font: var(--text-base);
  --st-pad: 16px;
  --st-min: 44px;
  --st-inset: 3px;
  --st-gap: 6px;
  --st-radius: calc(var(--st-h) / 2);
  --st-thumb-radius: calc((var(--st-h) - var(--st-inset) * 2) / 2);

  position: relative;
  display: inline-flex;
  align-items: center;
  width: max-content;
  padding: var(--st-inset);
  border-radius: var(--st-radius);
  background: var(--bg-secondary);
  font-family: inherit;
  user-select: none;
  -webkit-user-select: none;
  touch-action: pan-y;
}

/* 小档：面板内切换（高 26px / --text-xs） */
.st-tabs.size-sm {
  --st-h: 26px;
  --st-font: var(--text-xs);
  --st-pad: 10px;
  --st-min: 30px;
  --st-inset: 2px;
  --st-gap: 4px;
}

.st-tabs.is-disabled {
  opacity: 0.5;
  pointer-events: none;
}

.st-tabs[data-held] .st-tab {
  cursor: grabbing;
}

/* ── 分段按钮 ── */
.st-tab {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  gap: var(--st-gap);
  height: calc(var(--st-h) - var(--st-inset) * 2);
  min-width: var(--st-min);
  padding: 0 var(--st-pad);
  border: none;
  border-radius: var(--st-thumb-radius);
  background: transparent;
  font-family: inherit;
  font-size: var(--st-font);
  font-weight: var(--font-medium);
  line-height: 1;
  white-space: nowrap;
  color: var(--text-muted);
  cursor: pointer;
  outline: none;
  transition: color 160ms ease, transform 160ms cubic-bezier(0.23, 1, 0.32, 1);
}

@media (hover: hover) and (pointer: fine) {
  .st-tab:not([aria-selected='true']):hover {
    color: var(--text-secondary);
  }
}

.st-tab[data-pressed] {
  transform: scale(0.96);
}

/* 焦点环与 .lumi-btn 同语言（--focus-ring 半透明品牌色）；box-shadow 跟随药丸圆角，
   且 2px 外扩落在 3px 轨道内衬内——不会被外层 overflow-x:auto 视口裁切（outline 会） */
.st-tab:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--focus-ring);
}

.st-icon {
  flex-shrink: 0;
}

.st-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border-radius: var(--radius-full);
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
  line-height: 1;
  background: color-mix(in srgb, currentColor 16%, transparent);
}

/* ── 药丸滑块（surface + 阴影，深浅主题自适应） ── */
.st-thumb {
  position: absolute;
  top: var(--st-inset);
  left: var(--st-inset);
  height: calc(var(--st-h) - var(--st-inset) * 2);
  border-radius: var(--st-thumb-radius);
  background: var(--surface);
  box-shadow: var(--shadow-xs);
  pointer-events: none;
}

/* ── 选中态标签揭示层 ── */
.st-thumb-labels {
  position: absolute;
  inset: var(--st-inset);
  display: inline-flex;
  align-items: center;
  pointer-events: none;
}

.st-tab.is-ghost {
  cursor: default;
  color: var(--text);
  font-weight: var(--font-semibold);
}

@media (prefers-reduced-motion: reduce) {
  .st-tab {
    transition: color 160ms ease;
  }
}
</style>
