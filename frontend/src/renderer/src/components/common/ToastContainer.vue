<template>
  <Teleport to="body">
    <div class="toast-viewport">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="toast-slot"
        :data-variant="toast.type"
        :data-phase="phases[toast.id] ?? 'open'"
        :data-mounted="mountedOf[toast.id] ? 'true' : 'false'"
        :data-fuse="toast.duration > 0 ? 'bottom' : 'none'"
        :data-instant="instantOf[toast.id] ? '' : undefined"
      >
        <div class="toast-slot-inner">
          <div class="toast-slide">
            <div
              :ref="(el) => setCardRef(toast, el)"
              class="toast-card"
              role="status"
              aria-live="polite"
              aria-atomic="true"
              tabindex="0"
              @pointerdown="onPointerDown($event, toast)"
              @pointermove="onPointerMove"
              @pointerup="onPointerUp"
              @pointercancel="onPointerUp"
              @pointerenter="onPointerEnter($event, toast)"
              @pointerleave="onPointerLeave($event, toast)"
              @focusin="onFocusIn(toast)"
              @focusout="onFocusOut($event, toast)"
              @keydown="onKeyDown($event, toast)"
            >
              <span class="toast-icon" aria-hidden="true">
                <CheckCircle v-if="toast.type === 'success'" :size="18" :stroke-width="2" />
                <XCircle v-else-if="toast.type === 'error'" :size="18" :stroke-width="2" />
                <AlertTriangle v-else-if="toast.type === 'warning'" :size="18" :stroke-width="2" />
                <Info v-else :size="18" :stroke-width="2" />
              </span>
              <span class="toast-body">
                <span class="toast-title">{{ toast.message }}</span>
                <span v-if="toast.description" class="toast-desc">{{ toast.description }}</span>
              </span>
              <button
                v-if="toast.action"
                type="button"
                class="toast-action"
                @click="onAction(toast)"
              >
                {{ toast.action.label }}
              </button>
              <button
                type="button"
                class="toast-close"
                :aria-label="t('toast.close')"
                @click="onCloseClick(toast)"
              >
                <X :size="12" :stroke-width="2.5" />
              </button>
              <i :ref="(el) => setFuseRef(toast, el)" class="toast-fuse" aria-hidden="true" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * 右下角通知容器（SwipeToast 移植版）
 *
 * 交互全部移植自 vue-bits SwipeToast（MIT）：
 * - 弹簧物理进场（translateY 100% → 0，cubic-bezier(0.23,1,0.32,1) / 400ms）与离场塌陷
 *   （grid-template-rows 1fr → 0fr，兄弟条目随之平滑上移）；
 * - 按住卡片可纵向拖拽，越过阈值或快速挥出（flick）则弹簧滑出关闭，未过阈值弹回；
 * - fuse 进度条驱动自动关闭，hover / 拖拽 / 聚焦 / 页面隐藏时暂停；
 * - Escape（聚焦时）、关闭按钮、action 按钮均可关闭；
 * - 尊重 prefers-reduced-motion（退化为纯透明度过渡）。
 *
 * 主题适配：底色 --surface-elevated、文字 --text/--text-secondary、阴影 --shadow-lg、
 * 语义色仅用于图标与 fuse 点缀（--lumi-success/danger/warning/info）。
 */
import { animate, motionValue, useReducedMotion, type MotionValue } from 'motion-v'
import { AlertTriangle, CheckCircle, Info, X, XCircle } from 'lucide-vue-next'
import { onMounted, onUnmounted, reactive, watch } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast, type ToastItem } from '../../composables/useToast'

type CloseReason = 'timeout' | 'swipe' | 'action' | 'close' | 'escape' | 'programmatic'
type Phase = 'open' | 'closing'

type Sample = [number, number]

interface Drag {
  id: number
  startY: number
  grab: number | null
  moved: boolean
  hist: Sample[]
}

interface Runtime {
  y: MotionValue<number>
  fade: MotionValue<number>
  phase: Phase
  cardEl: HTMLDivElement | null
  fuseEl: HTMLElement | null
  fuseAnim: Animation | null
  closeTimer: ReturnType<typeof setTimeout> | undefined
  drag: Drag | null
  leaving: boolean
  lastInput: 'pointer' | 'keyboard'
  pendingClose: CloseReason | null
  offs: (() => void)[]
  flags: { hover: boolean; interacting: boolean; focus: boolean; hidden: boolean }
}

// —— vue-bits SwipeToast 原始动画参数 ——
const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1]
const FLICK = 0.11
const DEAD_ZONE = 3
const RESIST_PX = 24
const SLIDE_MS = 400
const SETTLE_BOUNCE = 0.2
const SWIPE_DISTANCE = 40
const EXIT = 0.7
const COLLAPSE_MS = 200
const BURN = [{ transform: 'scaleX(1)' }, { transform: 'scaleX(0)' }]

const rubberband = (over: number, dim: number, c = 0.55) =>
  (over * dim * c) / (dim + c * Math.abs(over))
const velocityOf = (hist: Sample[]) => {
  if (hist.length < 2) return 0
  const [t0, y0] = hist[0]
  const [t1, y1] = hist[hist.length - 1]
  return performance.now() - t1 > 100 ? 0 : (y1 - y0) / Math.max(1, t1 - t0)
}

const { toasts, remove } = useToast()
const { t } = useI18n()
const reduce = useReducedMotion()

/** 每个 toast 的命令式运行时（拖拽/弹簧/fuse），key 为 toast.id */
const runtimes = new Map<number, Runtime>()
/** 模板需要的响应式投影（data-* 属性驱动 CSS 状态机） */
const phases = reactive<Record<number, Phase>>({})
const mountedOf = reactive<Record<number, boolean>>({})
const instantOf = reactive<Record<number, boolean>>({})

let dragToast: ToastItem | null = null

function ensureRuntime(toast: ToastItem): Runtime {
  let rt = runtimes.get(toast.id)
  if (!rt) {
    rt = {
      y: motionValue(0),
      fade: motionValue(1),
      phase: 'open',
      cardEl: null,
      fuseEl: null,
      fuseAnim: null,
      closeTimer: undefined,
      drag: null,
      leaving: false,
      lastInput: 'pointer',
      pendingClose: null,
      offs: [],
      flags: { hover: false, interacting: false, focus: false, hidden: false },
    }
    runtimes.set(toast.id, rt)
    phases[toast.id] = 'open'
    mountedOf[toast.id] = false
    instantOf[toast.id] = false
  }
  return rt
}

const syncFuse = (rt: Runtime) => {
  const a = rt.fuseAnim
  if (!a) return
  if (rt.flags.hover || rt.flags.interacting || rt.flags.focus || rt.flags.hidden) a.pause()
  else if (a.playState === 'paused') a.play()
}

function startFuse(toast: ToastItem, rt: Runtime) {
  rt.fuseAnim?.cancel()
  rt.fuseAnim = null
  if (rt.phase !== 'open' || toast.duration <= 0 || !rt.fuseEl) return
  const a = rt.fuseEl.animate(BURN, {
    duration: toast.duration,
    easing: 'linear',
    fill: 'forwards',
  })
  a.onfinish = () => close(toast, 'timeout')
  rt.fuseAnim = a
  syncFuse(rt)
}

function cleanupRuntime(id: number) {
  const rt = runtimes.get(id)
  if (!rt) return
  runtimes.delete(id)
  clearTimeout(rt.closeTimer)
  if (rt.fuseAnim) {
    rt.fuseAnim.onfinish = null
    rt.fuseAnim.cancel()
  }
  rt.offs.forEach((off) => off())
  rt.y.stop()
  rt.fade.stop()
  delete phases[id]
  delete mountedOf[id]
  delete instantOf[id]
  if (dragToast && dragToast.id === id) dragToast = null
}

function finishToast(id: number) {
  cleanupRuntime(id)
  remove(id)
}

/** 关闭一条 toast：进入塌陷动画，动画结束后从队列移除 */
function close(toast: ToastItem, why: CloseReason) {
  const rt = runtimes.get(toast.id)
  if (!rt || rt.phase !== 'open' || rt.leaving) return
  if (rt.drag) {
    rt.pendingClose = why
    return
  }
  rt.fuseAnim?.pause()
  const now = why === 'escape' || ((why === 'action' || why === 'close') && rt.lastInput === 'keyboard')
  instantOf[toast.id] = now
  rt.phase = 'closing'
  phases[toast.id] = 'closing'
  clearTimeout(rt.closeTimer)
  rt.closeTimer = setTimeout(
    () => finishToast(toast.id),
    now ? 0 : SLIDE_MS * EXIT + 60
  )
}

/** 关闭中被打断（重新按住卡片）：复位并重新计时 */
function rescue(toast: ToastItem, rt: Runtime) {
  clearTimeout(rt.closeTimer)
  instantOf[toast.id] = false
  rt.y.set(0)
  rt.fade.set(1)
  rt.phase = 'open'
  phases[toast.id] = 'open'
  startFuse(toast, rt)
}

const swipeOut = (toast: ToastItem, rt: Runtime, dy: number, v: number) => {
  rt.fuseAnim?.pause()
  rt.leaving = true
  rt.pendingClose = null
  if (!reduce.value && rt.cardEl) {
    animate(rt.y, dy + rt.cardEl.offsetHeight, {
      type: 'spring',
      duration: 0.3,
      bounce: 0,
      velocity: v * 1000,
    })
  }
  animate(rt.fade, 0, { duration: 0.2, ease: EASE_OUT }).then(() => {
    // 挥出完成后走塌陷离场，让下方（下方为屏幕边缘时为上方）兄弟条目平滑合拢
    rt.leaving = false
    if (rt.phase === 'open') {
      instantOf[toast.id] = false
      rt.phase = 'closing'
      phases[toast.id] = 'closing'
      clearTimeout(rt.closeTimer)
      rt.closeTimer = setTimeout(() => finishToast(toast.id), COLLAPSE_MS)
    }
  })
}

function onPointerDown(e: PointerEvent, toast: ToastItem) {
  const rt = runtimes.get(toast.id)
  if (!rt) return
  rt.lastInput = 'pointer'
  if (e.button !== 0 || rt.drag || rt.leaving || (e.target as HTMLElement).closest('button')) return
  if (rt.phase === 'closing') rescue(toast, rt)
  try {
    rt.cardEl?.setPointerCapture(e.pointerId)
  } catch {
    // capture unavailable
  }
  rt.y.stop()
  rt.drag = {
    id: e.pointerId,
    startY: e.clientY,
    grab: null,
    moved: false,
    hist: [[performance.now(), rt.y.get()]],
  }
  dragToast = toast
  rt.flags.interacting = true
  syncFuse(rt)
}

function onPointerMove(e: PointerEvent) {
  const toast = dragToast
  if (!toast) return
  const rt = runtimes.get(toast.id)
  const d = rt?.drag
  if (!rt || !d || d.id !== e.pointerId) return
  if (d.grab === null) {
    if (Math.abs(e.clientY - d.startY) < DEAD_ZONE) return
    d.grab = e.clientY - rt.y.get()
    if (rt.cardEl) rt.cardEl.dataset.swiping = ''
  }
  const raw = e.clientY - d.grab
  // 向上拖出受橡皮筋阻力，向下（屏幕边缘方向）可挥出
  const next = raw >= 0 ? raw : rubberband(raw, RESIST_PX)
  rt.y.set(next)
  d.moved = true
  d.hist.push([performance.now(), next])
  if (d.hist.length > 4) d.hist.shift()
}

function onPointerUp(e: PointerEvent) {
  const toast = dragToast
  if (!toast) return
  const rt = runtimes.get(toast.id)
  const d = rt?.drag
  if (!rt || !d || d.id !== e.pointerId) return
  rt.drag = null
  dragToast = null
  if (rt.cardEl) delete rt.cardEl.dataset.swiping
  try {
    rt.cardEl?.releasePointerCapture(e.pointerId)
  } catch {
    // already released
  }
  rt.flags.interacting = false
  const dy = rt.y.get()
  const v = velocityOf(d.hist)
  if (dy > 0 && (v > FLICK || (dy >= SWIPE_DISTANCE && v >= 0))) {
    swipeOut(toast, rt, dy, v)
    return
  }
  if (d.moved) {
    animate(
      rt.y,
      0,
      reduce.value
        ? { duration: 0.2, ease: EASE_OUT }
        : { type: 'spring', duration: 0.5, bounce: SETTLE_BOUNCE, velocity: v * 1000 }
    )
  }
  const queued = rt.pendingClose
  rt.pendingClose = null
  if (queued) close(toast, queued)
  else syncFuse(rt)
}

function onPointerEnter(e: PointerEvent, toast: ToastItem) {
  const rt = runtimes.get(toast.id)
  if (!rt || e.pointerType !== 'mouse') return
  rt.flags.hover = true
  syncFuse(rt)
}

function onPointerLeave(e: PointerEvent, toast: ToastItem) {
  const rt = runtimes.get(toast.id)
  if (!rt || e.pointerType !== 'mouse') return
  rt.flags.hover = false
  syncFuse(rt)
}

function onFocusIn(toast: ToastItem) {
  const rt = runtimes.get(toast.id)
  if (!rt) return
  rt.flags.focus = true
  syncFuse(rt)
}

function onFocusOut(e: FocusEvent, toast: ToastItem) {
  const rt = runtimes.get(toast.id)
  if (!rt) return
  if (!(e.currentTarget as HTMLElement).contains(e.relatedTarget as Node | null)) {
    rt.flags.focus = false
    syncFuse(rt)
  }
}

function onKeyDown(e: KeyboardEvent, toast: ToastItem) {
  const rt = runtimes.get(toast.id)
  if (!rt) return
  if (e.key === 'Enter' || e.key === ' ') rt.lastInput = 'keyboard'
  if (e.key === 'Escape') {
    e.stopPropagation()
    close(toast, 'escape')
  }
}

function onAction(toast: ToastItem) {
  const rt = runtimes.get(toast.id)
  if (rt) rt.lastInput = 'pointer'
  toast.action?.handler()
  close(toast, 'action')
}

function onCloseClick(toast: ToastItem) {
  const rt = runtimes.get(toast.id)
  if (rt) rt.lastInput = 'pointer'
  close(toast, 'close')
}

// —— function refs：挂载卡片 / fuse 元素并初始化运行时 ——

function setCardRef(toast: ToastItem, el: Element | ComponentPublicInstance | null) {
  const rt = ensureRuntime(toast)
  rt.cardEl = (el as HTMLDivElement | null)
  if (el && rt.offs.length === 0) {
    // 卡片的 transform / opacity 由 motionValue 直接写入，拖拽不触发 Vue 渲染
    rt.offs.push(
      rt.y.on('change', (v: number) => {
        if (rt.cardEl) rt.cardEl.style.transform = `translateY(${v}px)`
      }),
      rt.fade.on('change', (v: number) => {
        if (rt.cardEl) rt.cardEl.style.opacity = String(v)
      })
    )
    // 进场：下一帧再置为 mounted，触发 translateY(100%) → 0 过渡
    requestAnimationFrame(() => {
      if (runtimes.has(toast.id)) mountedOf[toast.id] = true
    })
  }
}

function setFuseRef(toast: ToastItem, el: Element | ComponentPublicInstance | null) {
  const rt = ensureRuntime(toast)
  rt.fuseEl = (el as HTMLElement | null)
  // function ref 每次重渲染都会被调用：仅首次挂载时启动 fuse，避免新增 toast 触发
  // 重渲染导致已有条目的倒计时被重置
  if (el && !rt.fuseAnim && rt.phase === 'open' && toast.duration > 0) {
    startFuse(toast, rt)
  }
}

// store 侧移除（如超出可见上限丢弃最旧条目）时同步清理运行时
watch(toasts, (list) => {
  for (const id of [...runtimes.keys()]) {
    if (!list.some((t) => t.id === id)) cleanupRuntime(id)
  }
})

const onVisibilityChange = () => {
  for (const rt of runtimes.values()) {
    rt.flags.hidden = document.hidden
    syncFuse(rt)
  }
}

onMounted(() => {
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onUnmounted(() => {
  document.removeEventListener('visibilitychange', onVisibilityChange)
  for (const id of [...runtimes.keys()]) cleanupRuntime(id)
})
</script>

<style scoped>
/* ============ 视口：固定右下角，纵向堆叠（新的在最下，贴近屏幕边缘） ============ */
.toast-viewport {
  position: fixed;
  bottom: var(--space-5);
  right: var(--space-5);
  z-index: var(--z-toast);
  display: flex;
  flex-direction: column;
  width: min(360px, calc(100vw - 64px));
  pointer-events: none;
}

/* ============ 进出场状态机（移植 inline 模式：grid-rows 塌陷 + 滑动淡出） ============ */
.toast-slot {
  display: grid;
  grid-template-rows: 1fr;
  transition: grid-template-rows 400ms cubic-bezier(0.23, 1, 0.32, 1);
}

.toast-slot[data-phase='closing'] {
  grid-template-rows: 0fr;
  transition-duration: 280ms; /* SLIDE_MS * 0.7 */
}

.toast-slot-inner {
  min-height: 0;
}

.toast-slide {
  margin-top: 10px;
  transform: translateY(0);
  opacity: 1;
  transition:
    transform 400ms cubic-bezier(0.23, 1, 0.32, 1),
    opacity 240ms ease;
}

.toast-slot[data-mounted='false'] .toast-slide,
.toast-slot[data-phase='closing'] .toast-slide {
  transform: translateY(100%);
  opacity: 0;
}

.toast-slot[data-phase='closing'] .toast-slide {
  transition:
    transform 280ms cubic-bezier(0.23, 1, 0.32, 1),
    opacity 200ms ease;
}

.toast-slot[data-instant] {
  transition-duration: 0s;
}

.toast-slot[data-instant] .toast-slide {
  transition-duration: 0s;
}

/* ============ 卡片 ============ */
.toast-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4);
  overflow: hidden;
  outline: none;
  background: var(--surface-elevated);
  color: var(--text);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  font-size: var(--text-base);
  line-height: var(--leading-normal);
  cursor: grab;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  -webkit-touch-callout: none;
  touch-action: none;
  pointer-events: auto;
}

.toast-card[data-swiping] {
  cursor: grabbing;
}

/* 变体语义色：仅图标与 fuse 点缀，底色文字保持中性 */
.toast-card[data-variant='success'] {
  --toast-accent: var(--lumi-success);
}
.toast-card[data-variant='error'] {
  --toast-accent: var(--lumi-danger);
}
.toast-card[data-variant='warning'] {
  --toast-accent: var(--lumi-warning);
}
.toast-card[data-variant='info'] {
  --toast-accent: var(--lumi-info);
}

.toast-icon {
  display: inline-flex;
  flex: none;
  width: 18px;
  height: 18px;
  color: var(--toast-accent);
}

.toast-icon svg {
  width: 100%;
  height: 100%;
}

.toast-body {
  display: flex;
  flex-direction: column;
  gap: 1px;
  flex: 1 1 auto;
  min-width: 0;
}

.toast-title {
  font-weight: var(--font-medium);
  overflow-wrap: anywhere;
}

.toast-desc {
  font-weight: normal;
  line-height: 1.4;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

/* ============ action 按钮（如"重试/撤销"）：文字色反转为底 ============ */
.toast-action {
  flex: none;
  height: 24px;
  padding: 0 var(--space-2);
  border: 0;
  border-radius: 5px;
  outline: none;
  background: var(--text);
  color: var(--surface-elevated);
  font-family: inherit;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  transition:
    transform 160ms cubic-bezier(0.23, 1, 0.32, 1),
    opacity 160ms ease;
}

@media (hover: hover) and (pointer: fine) {
  .toast-action:hover {
    opacity: 0.88;
  }
}

.toast-action:active {
  transform: scale(0.97);
}

/* ============ 关闭按钮（含扩大的热区） ============ */
.toast-close {
  position: relative;
  display: grid;
  place-items: center;
  flex: none;
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 5px;
  outline: none;
  background: transparent;
  color: inherit;
  font-family: inherit;
  cursor: pointer;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  transition:
    transform 160ms cubic-bezier(0.23, 1, 0.32, 1),
    background-color 160ms ease;
}

.toast-close::before {
  content: '';
  position: absolute;
  inset: -8px;
}

@media (hover: hover) and (pointer: fine) {
  .toast-close:hover {
    background: color-mix(in srgb, var(--text) 10%, transparent);
  }
}

.toast-close:active {
  transform: scale(0.97);
}

/* ============ fuse 自动关闭进度条（hover/拖拽/聚焦时暂停） ============ */
.toast-fuse {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 2px;
  transform-origin: left;
  pointer-events: none;
  background: linear-gradient(
    90deg,
    transparent 0%,
    color-mix(in srgb, var(--toast-accent) 18%, transparent) 9%,
    color-mix(in srgb, var(--toast-accent) 50%, transparent) 18%,
    color-mix(in srgb, var(--toast-accent) 84%, transparent) 28%,
    var(--toast-accent) 38%,
    var(--toast-accent) 62%,
    color-mix(in srgb, var(--toast-accent) 84%, transparent) 72%,
    color-mix(in srgb, var(--toast-accent) 50%, transparent) 82%,
    color-mix(in srgb, var(--toast-accent) 18%, transparent) 91%,
    transparent 100%
  );
}

.toast-slot[data-fuse='none'] .toast-fuse {
  opacity: 0;
}

/* ============ 减弱动态效果 ============ */
@media (prefers-reduced-motion: reduce) {
  .toast-slot {
    transition-duration: 0s;
  }

  .toast-slide {
    transform: none !important;
    transition: opacity 200ms ease;
  }

  .toast-action:active,
  .toast-close:active {
    transform: none;
  }
}
</style>
