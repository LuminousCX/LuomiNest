<script setup lang="ts">
/**
 * ThoughtLine —— AI 思考动画行（移植自 vue-bits 的 ThoughtLine，MIT）
 *
 * 呼吸/流光 "思考中… 1.4s" + 可折叠思考步骤列表，settle 后过渡为 "思考了 X.Xs"。
 * 相对上游的适配：
 * - 图标：@hugeicons → lucide-vue-next（Sparkles / ChevronDown / Check）
 * - 样式：Tailwind 工具类 → scoped CSS，颜色全部走主题变量（--tl-* 锚定 --text-*），
 *   禁止硬编码色值；动画参数（cubic-bezier / 时长 / grid-template-rows 折叠 / shimmer）与上游一致
 * - 步骤列表允许换行 + 纵向滚动上限（聊天场景思考文本较长），上游为营销页短步骤的 nowrap
 * - label/doneLabel 由调用方经 i18n 传入（sr-only 播报直接复用 fmt 的 "12.3s"，语言中立）
 * - 移除上游的 renderLabel / className / glyph 插槽（本项目无使用场景）
 */
import { Check, ChevronDown, Sparkles } from 'lucide-vue-next'
import { animate, useReducedMotion, type AnimationPlaybackControls } from 'motion-v'
import { computed, nextTick, onMounted, ref, watch, type CSSProperties } from 'vue'

type ThoughtLineGlyph = 'sparkle' | 'dot' | 'none'

interface ThoughtLineProps {
  /** 进行中的标签文案（i18n 后传入，如"思考中…"） */
  label?: string
  /** 结束后的标签文案（如"思考了"，后接计时） */
  doneLabel?: string
  glyph?: ThoughtLineGlyph
  steps?: string[]
  collapsible?: boolean
  collapseOnSettle?: boolean
  /** 主题变量形式的颜色锚点，如 'var(--text-secondary)' */
  color?: string
  glyphColor?: string
  fontSize?: number
  breathPeriod?: number
  breathDepth?: number
  shimmer?: boolean
  shimmerDuration?: number
  settleDuration?: number
  settleBlur?: number
  working?: boolean
  /** working 保持超过该秒数后自动 settle */
  settleAfter?: number
  /** 外部计时（秒）；提供时不内部计 */
  elapsed?: number
  showTimer?: boolean
}

const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1]
const EASE_IN_OUT: [number, number, number, number] = [0.77, 0, 0.175, 1]
const GLYPH_DONE = 0.55

// 计时以 0.1s 为最小单位（ds = deciseconds），超过 1 分钟切换为 "Xm Y.Ys"
const fmt = (ds: number) =>
  ds < 600 ? `${(ds / 10).toFixed(1)}s` : `${Math.floor(ds / 600)}m ${((ds % 600) / 10).toFixed(1)}s`

const props = withDefaults(defineProps<ThoughtLineProps>(), {
  label: 'Thinking…',
  doneLabel: '',
  glyph: 'sparkle',
  steps: () => [],
  collapsible: true,
  collapseOnSettle: true,
  color: 'var(--text-secondary)',
  glyphColor: '',
  fontSize: 16,
  breathPeriod: 1.6,
  breathDepth: 0.45,
  shimmer: true,
  shimmerDuration: 1.8,
  settleDuration: 350,
  settleBlur: 2,
  working: true,
  settleAfter: 0,
  elapsed: undefined,
  showTimer: true
})

const emit = defineEmits<{ settle: [seconds: number] }>()

const reduce = useReducedMotion()
const autoSettled = ref(false)
const open = ref(true)
const isWorking = computed(() => props.working && !autoSettled.value)
const doneText = computed(() => props.doneLabel || (props.showTimer ? 'Thought for' : 'Done thinking'))
const hasTrace = computed(() => props.steps.length > 0)
const depth = computed(() => (reduce.value ? Math.min(props.breathDepth, 0.2) : props.breathDepth))
const period = computed(() => (reduce.value ? props.breathPeriod * 1.5 : props.breathPeriod))
const trough = computed(() => 1 - depth.value)
const sheen = computed(() => props.shimmer && !reduce.value)
const toggle = computed(() => hasTrace.value && props.collapsible)
const hasGlyph = computed(() => props.glyph !== 'none')

// post watchers 依赖的 refs 挂载后才存在，用 mounted 标记守护
const mounted = ref(false)
onMounted(() => (mounted.value = true))
const glyphRef = ref<HTMLElement | null>(null)
const breathRef = ref<HTMLElement | null>(null)
const timerRef = ref<HTMLElement | null>(null)
const stackRef = ref<HTMLElement | null>(null)
const workRef = ref<HTMLElement | null>(null)
const doneRef = ref<HTMLElement | null>(null)
let ds = 0
let prevWorking = isWorking.value
const announce = ref(props.label)

watch(
  () => props.working,
  (on) => {
    if (on) autoSettled.value = false
  }
)
watch(
  [isWorking, () => props.collapseOnSettle],
  () => {
    if (isWorking.value) open.value = true
    else if (props.collapseOnSettle) open.value = false
  },
  { immediate: true }
)

// 呼吸 + settle 的命令式动画（motion-v animate），随依赖变化重建
watch(
  [mounted, isWorking, period, depth, trough, () => props.settleDuration, sheen, hasGlyph],
  (_v, _o, onCleanup) => {
    const glyphEl = glyphRef.value
    const breathEl = breathRef.value
    if (!breathEl) return
    const s = props.settleDuration / 1000
    const tr = trough.value
    const loop = (el: HTMLElement, delay: number) =>
      animate(el, { opacity: [tr, 1, tr] }, { duration: period.value, ease: EASE_IN_OUT, repeat: Infinity, delay })
    let cancelled = false
    const running: AnimationPlaybackControls[] = []
    if (isWorking.value) {
      if (depth.value > 0) {
        if (sheen.value) running.push(animate(breathEl, { opacity: 1 }, { duration: 0.2, ease: EASE_OUT }))
        if (glyphEl) {
          const lead = animate(glyphEl, { opacity: tr }, { duration: 0.2, ease: EASE_OUT })
          running.push(lead)
          lead.then(() => {
            if (cancelled) return
            running.push(loop(glyphEl, 0))
            if (!sheen.value) running.push(loop(breathEl, 0.14))
          })
        } else if (!sheen.value) {
          running.push(loop(breathEl, 0.14))
        }
      } else {
        if (glyphEl) running.push(animate(glyphEl, { opacity: 1 }, { duration: 0.2, ease: EASE_OUT }))
        running.push(animate(breathEl, { opacity: 1 }, { duration: 0.2, ease: EASE_OUT }))
      }
    } else {
      if (glyphEl) running.push(animate(glyphEl, { opacity: GLYPH_DONE }, { duration: s, ease: EASE_OUT }))
      running.push(animate(breathEl, { opacity: 1 }, { duration: s, ease: EASE_OUT }))
    }
    onCleanup(() => {
      cancelled = true
      running.forEach((a) => a.stop())
    })
  },
  { flush: 'post' }
)

// 计时器手写 textContent：每秒 10 次更新不触发组件重渲染
const paint = (next: number) => {
  ds = next
  if (timerRef.value) timerRef.value.textContent = fmt(next)
}
watch(
  [mounted, isWorking, () => props.elapsed, () => props.settleAfter, () => props.showTimer],
  (_v, _o, onCleanup) => {
    if (props.elapsed != null) {
      paint(Math.round(props.elapsed * 10))
      return
    }
    if (!isWorking.value) {
      paint(ds)
      return
    }
    const startedAt = performance.now()
    paint(0)
    const id = setInterval(() => {
      const now = Math.floor((performance.now() - startedAt) / 100)
      paint(now)
      if (props.settleAfter > 0 && now >= Math.round(props.settleAfter * 10)) autoSettled.value = true
    }, 100)
    onCleanup(() => clearInterval(id))
  },
  { flush: 'post' }
)

// 计时器始终紧贴"当前激活标签"的右缘：work/done 两段宽度不同，切换时横向滑动过渡
watch(
  [mounted, isWorking, () => props.label, doneText, () => props.fontSize, () => props.showTimer],
  (_v, _o, onCleanup) => {
    const t = timerRef.value
    const stack = stackRef.value
    if (!t || !stack) return
    const place = (glide: boolean) => {
      const active = isWorking.value ? workRef.value : doneRef.value
      if (!active) return
      const shift = active.offsetWidth - stack.offsetWidth
      if (!glide) t.style.transition = 'none'
      t.style.transform = `translateX(${shift}px)`
      if (!glide) {
        void t.offsetWidth
        t.style.transition = ''
      }
    }
    place(prevWorking !== isWorking.value)
    prevWorking = isWorking.value
    const ro = new ResizeObserver(() => place(false))
    if (workRef.value) ro.observe(workRef.value)
    if (doneRef.value) ro.observe(doneRef.value)
    onCleanup(() => ro.disconnect())
  },
  { flush: 'post' }
)

// sr-only 播报：thinking 期间报 label，settle 后报 "doneLabel X.Xs"（fmt 语言中立）
watch(
  [mounted, isWorking],
  ([, working]) => {
    if (working) {
      announce.value = props.label
      return
    }
    announce.value = props.showTimer ? `${doneText.value} ${fmt(ds)}` : doneText.value
    emit('settle', ds / 10)
  },
  { flush: 'post' }
)

// 步骤列表超出滚动上限时，流式进行中自动跟随最新步骤（对齐旧思考面板的 scroll-follow）
const stepsRef = ref<HTMLElement | null>(null)
watch(
  [mounted, isWorking, () => props.steps.length, () => props.steps[props.steps.length - 1]],
  async () => {
    if (!isWorking.value) return
    await nextTick()
    const el = stepsRef.value
    if (el && el.scrollHeight > el.clientHeight) el.scrollTop = el.scrollHeight
  },
  { flush: 'post' }
)

const onHeadClick = () => {
  if (toggle.value) open.value = !open.value
}

const rootStyle = computed(
  () =>
    ({
      '--tl-font': `${props.fontSize}px`,
      '--tl-color': props.color,
      '--tl-glyph': props.glyphColor || props.color,
      '--tl-settle': `${props.settleDuration}ms`,
      '--tl-blur': `${props.settleBlur}px`,
      '--tl-shimmer': `${props.shimmerDuration}s`
    }) as CSSProperties
)
</script>

<template>
  <div
    class="tl-root"
    :data-working="isWorking ? '' : undefined"
    :data-open="open && hasTrace ? '' : undefined"
    :style="rootStyle"
  >
    <component
      :is="collapsible ? 'button' : 'div'"
      class="tl-head"
      :data-toggle="collapsible && toggle ? '' : undefined"
      :aria-expanded="collapsible && toggle ? open : undefined"
      :tabindex="collapsible ? (toggle ? 0 : -1) : undefined"
      @click="onHeadClick"
    >
      <span v-if="hasGlyph" ref="glyphRef" class="tl-glyph" aria-hidden="true">
        <Sparkles v-if="glyph === 'sparkle'" :stroke-width="2" />
        <span v-else class="tl-glyph-dot" />
      </span>
      <span ref="stackRef" class="tl-stack" aria-hidden="true">
        <span ref="workRef" class="tl-work" :data-active="isWorking ? '' : undefined">
          <span ref="breathRef" class="tl-breath" :data-shimmer="sheen ? '' : undefined">{{ label }}</span>
        </span>
        <span ref="doneRef" class="tl-done" :data-active="isWorking ? undefined : ''">{{ doneText }}</span>
      </span>
      <span
        v-if="showTimer"
        ref="timerRef"
        class="tl-timer"
        :data-done="isWorking ? undefined : ''"
        aria-hidden="true"
      >
        0.0s
      </span>
      <span v-if="collapsible" class="tl-chevron" :data-on="hasTrace ? '' : undefined" aria-hidden="true">
        <ChevronDown :stroke-width="2.2" />
      </span>
      <span class="tl-sr-only" role="status">{{ announce }}</span>
    </component>
    <div
      v-if="hasTrace"
      class="tl-tray"
      :data-open="open ? '' : undefined"
      :aria-hidden="!open"
    >
      <div class="tl-tray-clip">
        <div ref="stepsRef" class="tl-steps">
          <div
            v-for="(text, i) in steps"
            :key="i"
            class="tl-step"
            :data-done="!isWorking || i < steps.length - 1 ? '' : undefined"
          >
            <span class="tl-step-icon" aria-hidden="true">
              <Check v-if="!isWorking || i < steps.length - 1" :stroke-width="2.5" />
              <i v-else class="tl-step-dot" />
            </span>
            <span class="tl-step-text">{{ text }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tl-root {
  --tl-done: 0.55;
  --tl-timer: 1;
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  max-width: 100%;
  font-weight: 500;
  line-height: 1.2;
  color: var(--tl-color);
  font-family: inherit;
  font-size: var(--tl-font);
}

.tl-head {
  position: relative;
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.3em;
  border: 0;
  background: transparent;
  padding: 0;
  cursor: default;
  text-align: left;
  white-space: nowrap;
  color: inherit;
  outline: none;
  font: inherit;
}

.tl-head[data-toggle] {
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.tl-glyph {
  display: inline-flex;
  flex: none;
  margin-right: 0.2em;
  width: 1.1em;
  height: 1.1em;
  color: var(--tl-glyph);
}

.tl-glyph :deep(svg) {
  display: block;
  width: 100%;
  height: 100%;
}

.tl-glyph-dot {
  display: block;
  margin: auto;
  width: 0.5em;
  height: 0.5em;
  border-radius: 9999px;
  background: currentColor;
}

.tl-stack {
  display: inline-grid;
  min-width: 0;
}

/* work/done 两段标签叠放在同一 grid 单元，用 data-active 切换 blur→清晰；
   窄容器（聊天流半宽）下允许 stack 收缩，超宽标签省略号截断，不横向撑破消息列 */
.tl-work,
.tl-done {
  opacity: 0;
  width: max-content;
  max-width: 100%;
  grid-area: 1 / 1;
  overflow: hidden;
  text-overflow: ellipsis;
  filter: blur(var(--tl-blur));
  transition:
    opacity var(--tl-settle) cubic-bezier(0.23, 1, 0.32, 1),
    filter var(--tl-settle) cubic-bezier(0.23, 1, 0.32, 1);
}

.tl-work[data-active] {
  opacity: 1;
  filter: blur(0);
}

.tl-done[data-active] {
  opacity: var(--tl-done);
  filter: blur(0);
}

/* 流光渐变文字：颜色锚点全部来自 --tl-color（主题变量），50% 透明混合保证深浅主题成立 */
.tl-breath {
  display: inline-block;
}

.tl-root[data-working] .tl-breath[data-shimmer] {
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
  background-image: linear-gradient(
    100deg,
    color-mix(in srgb, var(--tl-color) 50%, transparent) 30%,
    var(--tl-color) 50%,
    color-mix(in srgb, var(--tl-color) 50%, transparent) 70%
  );
  background-size: 250% 100%;
  background-position: 125% 0;
  animation: thought-line-shimmer var(--tl-shimmer) linear infinite;
}

.tl-timer {
  flex: none;
  font-variant-numeric: tabular-nums;
  opacity: var(--tl-timer);
  transition:
    opacity var(--tl-settle) ease,
    transform var(--tl-settle) cubic-bezier(0.77, 0, 0.175, 1);
}

.tl-timer[data-done] {
  opacity: var(--tl-done);
}

.tl-chevron {
  display: inline-flex;
  flex: none;
  margin-left: 0.1em;
  opacity: 0;
  transition:
    opacity 200ms ease,
    transform 200ms cubic-bezier(0.23, 1, 0.32, 1);
}

.tl-chevron :deep(svg) {
  display: block;
  width: 1em;
  height: 1em;
}

.tl-chevron[data-on] {
  opacity: 0.55;
}

.tl-root[data-open] .tl-chevron {
  transform: rotate(180deg);
}

/* 可折叠步骤列表：grid-template-rows 0fr→1fr 实现高度折叠动画 */
.tl-tray {
  display: grid;
  width: 0;
  min-width: 100%;
  grid-template-rows: 0fr;
  transition: grid-template-rows var(--tl-settle) cubic-bezier(0.23, 1, 0.32, 1);
}

.tl-tray[data-open] {
  grid-template-rows: 1fr;
}

.tl-tray-clip {
  min-height: 0;
  overflow-x: visible;
  overflow-y: clip;
}

.tl-steps {
  display: flex;
  flex-direction: column;
  gap: 0.45em;
  padding: 0.6em 0 0.2em 1.6em;
  width: 100%;
  font-weight: 400;
  font-size: 0.875em;
  /* 聊天场景思考文本较长：允许换行 + 滚动上限（替代上游营销页的 nowrap） */
  white-space: normal;
  word-break: break-word;
  max-height: 240px;
  overflow-y: auto;
}

.tl-step {
  display: flex;
  align-items: center;
  gap: 0.5em;
  opacity: 1;
  transform: translateY(0);
  transition:
    opacity 200ms cubic-bezier(0.23, 1, 0.32, 1),
    transform 200ms cubic-bezier(0.23, 1, 0.32, 1);
}

/* 新步骤插入时淡入下滑（@starting-style，仅首次渲染生效） */
@starting-style {
  .tl-step {
    opacity: 0;
    transform: translateY(-4px);
  }
}

.tl-step-icon {
  display: inline-grid;
  flex: none;
  place-items: center;
  opacity: 0.55;
  width: 1em;
  height: 1em;
}

.tl-step-icon :deep(svg) {
  display: block;
  width: 100%;
  height: 100%;
}

.tl-step-dot {
  display: block;
  width: 0.4em;
  height: 0.4em;
  border-radius: 9999px;
  background: currentColor;
  animation: thought-line-pulse 1.6s cubic-bezier(0.77, 0, 0.175, 1) infinite;
}

.tl-step[data-done] .tl-step-text {
  opacity: 0.55;
}

.tl-step-text {
  transition: opacity var(--tl-settle) ease;
}

.tl-sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

@keyframes thought-line-pulse {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 1;
  }
}

@keyframes thought-line-shimmer {
  to {
    background-position: -125% 0;
  }
}

/* reduced-motion 降级：去模糊/位移，动画仅保留慢速呼吸与淡入淡出 */
@media (prefers-reduced-motion: reduce) {
  .tl-work,
  .tl-done {
    filter: none !important;
    transition: opacity var(--tl-settle) ease;
  }

  .tl-step {
    transform: none !important;
    transition: opacity 200ms ease;
  }

  .tl-step-dot {
    animation-duration: 2.4s;
  }
}
</style>
