<script setup lang="ts">
/**
 * 全站统一的聊天输入框（移植自 vue-bits PromptBar）。
 *
 * 结构：圆角大输入卡（placeholder 在卡内顶部）+ 底部工具行 =
 * 加号（附件菜单）+ 模型选择 + 响应档位（effort）+ [工具插槽] + 发送圆钮。
 *
 * 移植适配说明：
 * - hugeicons → lucide-vue-next；Tailwind → scoped CSS，颜色全部走主题变量（深浅主题自适应）
 * - 发送钮箭头↔方块 morph、max 档位火花粒子、effort 弹簧游标均用 motion-v 实现
 * - effort 固定 3 档：fast（快速响应主模型）/ balanced（均衡·自动）/ max（深度推理模型），
 *   仅 emit + localStorage 落地，档位→后端模型路由能力后端尚不存在（不造假路由）
 * - 参考实现的 @来源 / /命令 令牌机制依赖虚构数据源，未移植；加号菜单条目由宿主注入
 */
import { animate, motionValue, useReducedMotion, type AnimationPlaybackControls } from 'motion-v'
import { Check, ChevronDown, CircleHelp, File, Plus, Sparkles, X } from 'lucide-vue-next'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '../../composables/useToast'
import type { PromptBarAttachmentChip, PromptBarEffort, PromptBarMenuItem, PromptBarModelOption } from './prompt-bar'

const props = withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    disabled?: boolean
    /** 流式生成中：发送钮 morph 为停止方块，点击 emit stop */
    busy?: boolean
    /** 外部发送可用性（后端就绪/引用/附件等）；不传则按"有文字或附件"内部判断 */
    canSend?: boolean
    models?: PromptBarModelOption[]
    /** 当前选中模型 key（v-model:model） */
    modelKey?: string
    /** 响应档位（v-model:effort）：fast | balanced | max */
    effort?: string
    attachments?: PromptBarAttachmentChip[]
    menuItems?: PromptBarMenuItem[]
    /** 模型菜单底部"前往设置管理模型"入口（如工作台的全局模型收口） */
    showModelSettings?: boolean
  }>(),
  {
    placeholder: '',
    disabled: false,
    busy: false,
    canSend: undefined,
    models: () => [],
    modelKey: '',
    effort: 'balanced',
    attachments: () => [],
    menuItems: () => [],
    showModelSettings: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: []
  stop: []
  'update:model': [key: string]
  'update:effort': [key: PromptBarEffort]
  'remove-attachment': [key: string]
  'model-settings': []
}>()

const { t } = useI18n()
const toast = useToast()
const reduce = useReducedMotion()

// ── effort 档位定义（固定 3 档，用户拍板）──────────────────────────
const EFFORT_LEVELS: { key: PromptBarEffort; labelKey: string }[] = [
  { key: 'fast', labelKey: 'chat.effort.fast' },
  { key: 'balanced', labelKey: 'chat.effort.balanced' },
  { key: 'max', labelKey: 'chat.effort.max' },
]
const EFFORT_EDGE = 11 // 滑轨两端留白（与参考实现一致）

const rootRef = ref<HTMLDivElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)
const glowRef = ref<HTMLSpanElement | null>(null)
const sparkRef = ref<HTMLCanvasElement | null>(null)
const sendSvgRef = ref<SVGSVGElement | null>(null)
const sendPathRef = ref<SVGPathElement | null>(null)
const effortCursorRef = ref<HTMLSpanElement | null>(null)
const effortFillRef = ref<HTMLSpanElement | null>(null)
const rowRefs: (HTMLButtonElement | null)[] = []
const setRowRef = (el: unknown, i: number) => {
  rowRefs[i] = el as HTMLButtonElement | null
}
let lastOpenKind: string | null = null
let suppressFocusClose = false

const draft = computed({
  get: () => props.modelValue,
  set: (v: string) => emit('update:modelValue', v),
})

const plusOpen = ref(false)
const modelOpen = ref(false)
const effortOpen = ref(false)
const active = ref(0)
const pressed = ref(false)

type Row = PromptBarMenuItem & { tag?: string }

const selectedModel = computed(() => props.models.find((m) => m.key === props.modelKey) ?? null)
const effortIndex = computed(() => {
  const i = EFFORT_LEVELS.findIndex((l) => l.key === props.effort)
  return i >= 0 ? i : 1
})
const effortLevel = computed(() => EFFORT_LEVELS[effortIndex.value])
const effortLevelLabel = computed(() => t(effortLevel.value.labelKey))
const maxed = computed(() => effortIndex.value === EFFORT_LEVELS.length - 1)

const openKind = computed<'plus' | 'model' | 'effort' | null>(() => {
  if (plusOpen.value) return 'plus'
  if (effortOpen.value) return 'effort'
  if (modelOpen.value) return 'model'
  return null
})

const list = computed<Row[]>(() => {
  if (openKind.value === 'plus') return props.menuItems
  if (openKind.value === 'model') return props.models
  return []
})
const cursor = computed(() => Math.min(active.value, Math.max(0, list.value.length - 1)))

const internalCanSend = computed(
  () => draft.value.trim().length > 0 || props.attachments.length > 0,
)
const canSend = computed(() => (props.canSend !== undefined ? props.canSend : internalCanSend.value))
const armed = computed(() => props.busy || (canSend.value && !props.disabled))

const menuLabel = computed(() => {
  if (openKind.value === 'plus') return t('chat.promptBar.menuAttachments')
  if (openKind.value === 'model') return t('chat.promptBar.chooseModel')
  return t('chat.effort.title')
})

const focusInput = () => {
  // 程序化聚焦时抑制 onInputFocus 的"聚焦即收起菜单"（否则首次打开菜单会立即被关闭）
  suppressFocusClose = true
  inputRef.value?.focus({ preventScroll: true })
  nextTick(() => {
    suppressFocusClose = false
  })
}

/** textarea 聚焦（用户点击空白处/Tab 进入）时收起菜单；程序化聚焦除外 */
const onInputFocus = () => {
  if (suppressFocusClose) return
  closeMenus()
}

const closeMenus = () => {
  plusOpen.value = false
  modelOpen.value = false
  effortOpen.value = false
}

// ── 菜单悬浮高亮条（跟随 active 行移动）────────────────────────────
watch(
  [openKind, cursor, list],
  () => {
    const glow = glowRef.value
    if (!glow || !openKind.value || openKind.value === 'effort') {
      if (glow) glow.style.opacity = '0'
      return
    }
    const row = rowRefs[cursor.value]
    if (!row) {
      glow.style.opacity = '0'
      return
    }
    const fresh = lastOpenKind !== openKind.value
    lastOpenKind = openKind.value
    if (fresh) glow.style.transition = 'none'
    glow.style.top = `${row.offsetTop}px`
    glow.style.height = `${row.offsetHeight}px`
    glow.style.opacity = '1'
    if (fresh) {
      void glow.offsetHeight
      glow.style.transition = ''
    }
  },
  { flush: 'post' },
)
watch(openKind, (k) => {
  if (!k) lastOpenKind = null
})

// 任一菜单打开时：点击外部关闭
watch([plusOpen, modelOpen, effortOpen], (_n, _p, onCleanup) => {
  if (!plusOpen.value && !modelOpen.value && !effortOpen.value) return
  const onDown = (e: PointerEvent) => {
    if (!rootRef.value?.contains(e.target as Node)) closeMenus()
  }
  document.addEventListener('pointerdown', onDown)
  onCleanup(() => document.removeEventListener('pointerdown', onDown))
})

// ── textarea 自适应高度（最多 5 行）────────────────────────────────
const LINE = 22
const MAX_ROWS = 5
const fitInput = () => {
  const el = inputRef.value
  if (!el) return
  el.style.height = '0px'
  const max = LINE * MAX_ROWS
  el.style.height = `${Math.min(el.scrollHeight, max)}px`
  el.style.overflowY = el.scrollHeight > max ? 'auto' : 'hidden'
}
watch([draft, () => props.disabled], fitInput, { flush: 'post' })

// ── 发送钮：箭头 ↔ 方块 morph（motion-value 直写 svg path）────────
const ARROW_UP = [12, 4.5, 18.5, 11, 14.25, 11, 14.25, 19.5, 9.75, 19.5, 9.75, 11, 5.5, 11]
const SQUARE = [12, 6, 18, 6, 18, 12, 18, 18, 6, 18, 6, 12, 6, 6]
const EASE_IN_OUT: [number, number, number, number] = [0.77, 0, 0.175, 1]
const mix = (a: number, b: number, k: number) => a + (b - a) * k
const pathAt = (a: number[], b: number[], k: number) => {
  let d = ''
  for (let i = 0; i < a.length; i += 2) {
    d += `${i ? 'L' : 'M'}${mix(a[i], b[i], k).toFixed(2)} ${mix(a[i + 1], b[i + 1], k).toFixed(2)}`
  }
  return `${d}Z`
}
const MORPH_MS = 240
const SQUASH = 0.12
const TILT = 8
const sendT = motionValue(props.busy ? 1 : 0)
let sendDir = props.busy ? 1 : -1
let sendControls: AnimationPlaybackControls | null = null
let offSend: (() => void) | undefined

const syncSend = () => {
  const target = props.busy ? 1 : 0
  sendDir = props.busy ? 1 : -1
  if (sendT.get() === target) return
  sendControls?.stop()
  sendControls = animate(
    sendT,
    target,
    reduce.value ? { duration: 0 } : { duration: MORPH_MS / 1000, ease: EASE_IN_OUT },
  )
}
watch([() => props.busy, reduce], syncSend)

// ── max 档位火花粒子（canvas，颜色取主题 --lumi-primary）──────────
type Spark = { x: number; y: number; r: number; vy: number; sway: number; phase: number; life: number; span: number }
const typing = { energy: 0, strokes: 0 }
let stopSpark: (() => void) | null = null

const resolveSparkColor = (): string => {
  const el = rootRef.value
  if (!el) return '#8b7cf6'
  const v = getComputedStyle(el).getPropertyValue('--lumi-primary').trim()
  return v || '#8b7cf6'
}

const startSpark = () => {
  const canvas = sparkRef.value
  if (!canvas) return null
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  const sparkColor = resolveSparkColor()
  typing.strokes = 0
  let raf = 0
  let last = performance.now()
  let w = 0
  let h = 0
  let due = 0
  let speed = 1
  let pulse = 0
  const parts: Spark[] = []
  const resize = () => {
    const rect = canvas.getBoundingClientRect()
    const dpr = Math.min(2, window.devicePixelRatio || 1)
    w = rect.width
    h = rect.height
    canvas.width = Math.round(w * dpr)
    canvas.height = Math.round(h * dpr)
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }
  const spawn = (burst: boolean) => {
    parts.push({
      x: Math.random() * w,
      y: burst ? h * (0.2 + Math.random() * 0.8) : h + 3,
      r: 0.9 + Math.random() * 1.1,
      vy: -(7 + Math.random() * 9),
      sway: (Math.random() - 0.5) * 10,
      phase: Math.random() * Math.PI * 2,
      life: burst ? Math.random() * 1.2 : 0,
      span: 2.4 + Math.random() * 2.4,
    })
  }
  const tick = (now: number) => {
    const dt = Math.min(0.05, (now - last) / 1000)
    last = now
    typing.energy *= Math.exp(-dt / 0.8)
    pulse *= Math.exp(-dt / 0.16)
    if (typing.strokes > 0) {
      typing.strokes = 0
      pulse = 1
    }
    const energy = typing.energy
    speed += (1 + energy * 6 - speed) * (1 - Math.exp(-dt / 0.15))
    due += dt
    while (due > 0.14) {
      due -= 0.14
      if (parts.length < 30) spawn(false)
    }
    ctx.clearRect(0, 0, w, h)
    ctx.fillStyle = sparkColor
    ctx.shadowColor = sparkColor
    ctx.shadowBlur = 6 + energy * 10 + pulse * 6
    for (let i = parts.length - 1; i >= 0; i -= 1) {
      const p = parts[i]
      p.life += dt
      if (p.life > p.span) {
        parts.splice(i, 1)
        continue
      }
      const k = p.life / p.span
      const twinkle = 0.7 + 0.3 * Math.sin((now / 160) * (1 + energy) + p.phase)
      p.y += p.vy * dt * speed
      if (p.y < -4) {
        p.y = h + 3
        p.x = Math.random() * w
      }
      const edge = Math.min(1, Math.max(0, p.y / 14), Math.max(0, (h - p.y) / 14))
      ctx.globalAlpha = Math.min(1, Math.sin(k * Math.PI) * (0.9 + energy * 0.25) * twinkle) * edge
      ctx.beginPath()
      ctx.arc(
        p.x + Math.sin((now / 900) * (1 + energy * 0.8) + p.phase) * p.sway,
        p.y,
        p.r * twinkle * (1 + energy * 0.35),
        0,
        Math.PI * 2,
      )
      ctx.fill()
    }
    raf = requestAnimationFrame(tick)
  }
  resize()
  for (let i = 0; i < 26; i += 1) spawn(true)
  const ro = new ResizeObserver(resize)
  ro.observe(canvas)
  raf = requestAnimationFrame(tick)
  return () => {
    cancelAnimationFrame(raf)
    ro.disconnect()
    ctx.clearRect(0, 0, w, h)
  }
}
const syncSpark = () => {
  stopSpark?.()
  stopSpark = null
  if (!maxed.value || reduce.value || props.disabled) return
  stopSpark = startSpark()
}
watch([maxed, reduce, () => props.disabled], syncSpark, { flush: 'post' })

onMounted(() => {
  offSend = sendT.on('change', (v) => {
    sendPathRef.value?.setAttribute('d', pathAt(ARROW_UP, SQUARE, v))
    const goo = reduce.value ? 0 : Math.sin(v * Math.PI)
    const sx = 1 - SQUASH * goo
    if (sendSvgRef.value) {
      sendSvgRef.value.style.transform = goo
        ? `rotate(${sendDir * TILT * goo}deg) scale(${sx}, ${1 / sx})`
        : ''
    }
  })
  fitInput()
  syncSpark()
  syncEffortCursor(false)
})

onBeforeUnmount(() => {
  stopSpark?.()
  offSend?.()
  sendControls?.stop()
  effortControls?.stop()
})

// ── effort 滑块：3 档刻度 + 弹簧游标（motion-v spring）─────────────
let effortControls: AnimationPlaybackControls | null = null
const effortPct = motionValue(effortIndex.value * 50)

/** 档位 k(0..1) → 轨道内坐标：两端各留 EFFORT_EDGE 留白 */
const stepAt = (k: number) => `calc(${EFFORT_EDGE}px + (100% - ${EFFORT_EDGE * 2}px) * ${k})`

const writeEffortStyles = (pct: number) => {
  const k = pct / 100
  if (effortCursorRef.value) effortCursorRef.value.style.left = stepAt(k)
  if (effortFillRef.value) {
    effortFillRef.value.style.width = pct >= 99.5 ? '100%' : `calc(${stepAt(k)} + 7px)`
  }
}

/** 同步游标到当前档位；animate=false 时直接落位（初始化/外部变更） */
const syncEffortCursor = (animateFlag: boolean) => {
  const pct = effortIndex.value * 50
  if (!animateFlag || reduce.value) {
    effortControls?.stop()
    effortPct.set(pct)
    writeEffortStyles(pct)
    return
  }
  effortControls?.stop()
  effortControls = animate(effortPct, pct, { type: 'spring', stiffness: 380, damping: 32 })
}
watch(effortIndex, () => syncEffortCursor(true))
// 外部 props.effort 变化也走弹簧（effortIndex watch 已覆盖；此处兜底同值重挂）
onMounted(() => {
  effortPct.on('change', writeEffortStyles)
})

const setEffort = (i: number) => {
  const next = Math.max(0, Math.min(EFFORT_LEVELS.length - 1, i))
  if (next === effortIndex.value) return
  emit('update:effort', EFFORT_LEVELS[next].key)
}
const effortFromPointer = (e: PointerEvent) => {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const k = (e.clientX - rect.left - EFFORT_EDGE) / Math.max(1, rect.width - 2 * EFFORT_EDGE)
  setEffort(Math.round(Math.max(0, Math.min(1, k)) * (EFFORT_LEVELS.length - 1)))
}
const onEffortDown = (e: PointerEvent) => {
  if (e.button !== 0) return
  const el = e.currentTarget as HTMLElement
  try {
    el.setPointerCapture(e.pointerId)
  } catch {
    // 指针捕获不可用时忽略
  }
  el.focus({ preventScroll: true })
  effortFromPointer(e)
}
const onEffortMove = (e: PointerEvent) => {
  if (e.buttons & 1) effortFromPointer(e)
}
const onEffortKey = (e: KeyboardEvent) => {
  const step =
    e.key === 'ArrowRight' || e.key === 'ArrowUp' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowDown' ? -1 : 0
  if (step) {
    e.preventDefault()
    setEffort(effortIndex.value + step)
  } else if (e.key === 'Home') {
    e.preventDefault()
    setEffort(0)
  } else if (e.key === 'End') {
    e.preventDefault()
    setEffort(EFFORT_LEVELS.length - 1)
  } else if (e.key === 'Escape') {
    effortOpen.value = false
    focusInput()
  }
}
const tickLeft = (i: number) => stepAt(i / (EFFORT_LEVELS.length - 1))

// ── 菜单条目选择 ───────────────────────────────────────────────────
const pick = (row: Row) => {
  if (openKind.value === 'model') {
    emit('update:model', row.key)
    modelOpen.value = false
    focusInput()
    return
  }
  const item = row as PromptBarMenuItem
  plusOpen.value = false
  if (item.disabled) {
    toast.info(t('chat.promptBar.comingSoon', { name: item.name }))
    focusInput()
    return
  }
  item.action?.()
  focusInput()
}

const onSend = () => {
  if (!canSend.value || props.busy || props.disabled) return
  emit('send')
}
const onSendClick = () => {
  if (props.disabled) return
  closeMenus()
  if (props.busy) emit('stop')
  else onSend()
}
const removeAttachment = (key: string) => emit('remove-attachment', key)

const onInput = (e: Event) => {
  draft.value = (e.target as HTMLTextAreaElement).value
  typing.energy = Math.min(1.6, typing.energy + 0.22)
  typing.strokes = Math.min(4, typing.strokes + 1)
  closeMenus()
  active.value = 0
}

const onKeyDown = (e: KeyboardEvent) => {
  if (openKind.value && list.value.length) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      active.value = (cursor.value + (e.key === 'ArrowDown' ? 1 : list.value.length - 1)) % list.value.length
      return
    }
    if ((e.key === 'Enter' && !e.shiftKey) || e.key === 'Tab') {
      e.preventDefault()
      pick(list.value[cursor.value])
      return
    }
  }
  if (e.key === 'Escape') {
    if (openKind.value) {
      e.preventDefault()
      closeMenus()
    }
    return
  }
  // 中文输入法组词期间的回车是选字，不触发发送
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    onSend()
  }
}

const togglePlus = () => {
  modelOpen.value = false
  effortOpen.value = false
  active.value = 0
  plusOpen.value = !plusOpen.value
  focusInput()
}
const toggleModels = () => {
  plusOpen.value = false
  effortOpen.value = false
  active.value = Math.max(
    0,
    props.models.findIndex((m) => m.key === (selectedModel.value?.key ?? props.modelKey)),
  )
  modelOpen.value = !modelOpen.value
  focusInput()
}
const toggleEffort = () => {
  plusOpen.value = false
  modelOpen.value = false
  effortOpen.value = !effortOpen.value
  syncEffortCursor(false)
  focusInput()
}
const onBoxDown = (e: PointerEvent) => {
  if (e.target === e.currentTarget || e.target === inputRef.value) closeMenus()
}
const down = (e: PointerEvent) => {
  if (e.button !== 0 || !armed.value) return
  pressed.value = true
}
const up = () => (pressed.value = false)

defineExpose({
  focus: focusInput,
})
</script>

<template>
  <div ref="rootRef" class="pb-root" :class="{ 'pb-root--disabled': disabled }" :data-max="maxed ? '' : undefined">
    <!-- 弹层：附件菜单 / 模型菜单 / effort 档位 -->
    <div
      v-if="openKind"
      class="pb-pop"
      :class="[`pb-pop--${openKind}`]"
      :role="openKind === 'effort' ? 'dialog' : 'listbox'"
      :aria-label="menuLabel"
    >
      <template v-if="openKind === 'effort'">
        <div class="pb-effort-head">
          <span class="pb-muted">{{ t('chat.effort.title') }}</span>
          <span class="pb-effort-level">{{ effortLevelLabel }}</span>
          <span class="pb-muted pb-effort-help" :title="t('chat.effort.hint')">
            <CircleHelp :size="14" :stroke-width="1.8" />
          </span>
        </div>
        <div class="pb-effort-ends pb-muted">
          <span>{{ t('chat.effort.fast') }}</span>
          <span>{{ t('chat.effort.max') }}</span>
        </div>
        <div
          class="pb-effort-slider"
          :class="{ 'pb-effort-slider--max': maxed }"
          role="slider"
          tabindex="0"
          :aria-label="t('chat.effort.title')"
          :aria-valuemin="0"
          :aria-valuemax="EFFORT_LEVELS.length - 1"
          :aria-valuenow="effortIndex"
          :aria-valuetext="effortLevelLabel"
          @pointerdown="onEffortDown"
          @pointermove="onEffortMove"
          @keydown="onEffortKey"
        >
          <span ref="effortFillRef" class="pb-effort-fill" />
          <i
            v-for="(lv, i) in EFFORT_LEVELS"
            :key="lv.key"
            class="pb-effort-tick"
            :style="{ left: tickLeft(i) }"
          />
          <span ref="effortCursorRef" class="pb-effort-cursor" />
        </div>
      </template>
      <template v-else>
        <span ref="glowRef" class="pb-glow" aria-hidden="true" />
        <button
          v-for="(row, i) in list"
          :key="row.key"
          :ref="(el) => setRowRef(el, i)"
          type="button"
          role="option"
          :aria-selected="i === cursor"
          class="pb-row"
          :class="{ 'pb-row--disabled': row.disabled }"
          @mousedown.prevent
          @pointerenter="active = i"
          @click="pick(row)"
        >
          <span v-if="openKind === 'plus' && row.icon" class="pb-row-icon">
            <component :is="row.icon" :size="15" :stroke-width="1.8" />
          </span>
          <span class="pb-row-name">{{ row.name }}</span>
          <span v-if="row.description" class="pb-row-desc pb-muted">{{ row.description }}</span>
          <template v-if="openKind === 'model'">
            <span v-if="row.tag" class="pb-row-tag pb-muted">{{ row.tag }}</span>
            <span class="pb-row-check" :class="{ 'pb-row-check--on': row.key === (selectedModel?.key ?? modelKey) }">
              <Check :size="13" :stroke-width="2.5" />
            </span>
          </template>
        </button>
        <button
          v-if="openKind === 'model' && showModelSettings"
          type="button"
          class="pb-model-settings pb-muted"
          @mousedown.prevent
          @click="emit('model-settings')"
        >
          {{ t('chat.promptBar.modelSettings') }}
        </button>
      </template>
    </div>

    <!-- 输入卡 -->
    <div class="pb-card" role="presentation" @pointerdown="onBoxDown" @click="focusInput">
      <canvas ref="sparkRef" class="pb-spark" aria-hidden="true" />
      <div class="pb-card-inner">
        <!-- 宿主注入的卡内顶部区域（技能选择 / 引用预览等） -->
        <div v-if="$slots.top" class="pb-top">
          <slot name="top" />
        </div>

        <div v-if="attachments.length > 0" class="pb-attachments">
          <span v-for="file in attachments" :key="file.key" class="pb-chip">
            <File :size="12" :stroke-width="2" />
            <span class="pb-chip-name">{{ file.name }}</span>
            <button
              type="button"
              class="pb-chip-remove"
              :aria-label="t('chat.promptBar.removeFile', { name: file.name })"
              @click.stop="removeAttachment(file.key)"
            >
              <X :size="10" :stroke-width="2.5" />
            </button>
          </span>
        </div>

        <textarea
          ref="inputRef"
          class="pb-input"
          rows="1"
          :value="modelValue"
          :placeholder="placeholder"
          :disabled="disabled"
          :aria-label="t('chat.promptBar.inputLabel')"
          @input="onInput"
          @focus="onInputFocus"
          @keydown="onKeyDown"
        />

        <div class="pb-toolbar">
          <button
            v-if="menuItems.length > 0"
            type="button"
            class="pb-icon-btn"
            :aria-label="t('chat.promptBar.addAttachment')"
            :aria-expanded="plusOpen"
            :class="{ 'pb-btn--on': plusOpen }"
            :disabled="disabled"
            @mousedown.prevent
            @click="togglePlus"
          >
            <Plus :size="16" :stroke-width="2" />
          </button>
          <button
            v-if="models.length > 0"
            type="button"
            class="pb-tool-btn"
            :aria-label="t('chat.promptBar.chooseModel')"
            :aria-expanded="modelOpen"
            :class="{ 'pb-btn--on': modelOpen }"
            :disabled="disabled"
            @mousedown.prevent
            @click="toggleModels"
          >
            <span class="pb-tool-btn-text">{{ selectedModel?.name || modelKey || t('chat.promptBar.chooseModel') }}</span>
            <ChevronDown :size="12" :stroke-width="2.4" />
          </button>
          <button
            type="button"
            class="pb-tool-btn"
            :aria-label="t('chat.promptBar.chooseEffort')"
            :aria-expanded="effortOpen"
            :class="{ 'pb-btn--on': effortOpen, 'pb-tool-btn--max': maxed }"
            :disabled="disabled"
            @mousedown.prevent
            @click="toggleEffort"
          >
            <Sparkles :size="13" :stroke-width="2" />
            <span>{{ effortLevelLabel }}</span>
          </button>

          <!-- 宿主注入的工具位（专业模式切换等） -->
          <slot name="tools" />

          <span class="pb-spacer" />
          <button
            type="button"
            class="pb-send-btn"
            :disabled="!armed"
            :aria-label="busy ? t('chat.promptBar.stop') : t('chat.promptBar.send')"
            :class="{ 'pb-send-btn--pressed': pressed }"
            @mousedown.prevent
            @pointerdown="down"
            @pointerup="up"
            @pointercancel="up"
            @pointerleave="up"
            @click="onSendClick"
          >
            <svg ref="sendSvgRef" class="pb-send-svg" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linejoin="round">
              <path ref="sendPathRef" :d="pathAt(ARROW_UP, SQUARE, props.busy ? 1 : 0)" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pb-root {
  position: relative;
  width: 100%;
  font-size: 14px;
  line-height: 22px;
  color: var(--text-primary);
}

.pb-root--disabled {
  opacity: 0.6;
}

/* ── 弹层（附件 / 模型 / effort）──────────────────────────────── */
.pb-pop {
  position: absolute;
  bottom: calc(100% + 8px);
  inset-inline: 0;
  z-index: 6;
  padding: 4px;
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  box-shadow: var(--shadow-lg);
  transform-origin: bottom;
  animation: pb-pop 180ms cubic-bezier(0.23, 1, 0.32, 1) both;
}

.pb-pop--effort {
  inset-inline: auto;
  left: 0;
  width: 248px;
  padding: 12px 14px 14px;
}

.pb-pop--model {
  inset-inline: auto;
  left: 0;
  width: 220px;
}

@media (prefers-reduced-motion: reduce) {
  .pb-pop {
    animation: none;
  }
}

@keyframes pb-pop {
  from {
    opacity: 0;
    transform: translateY(4px) scale(0.98);
  }
}

.pb-muted {
  color: color-mix(in srgb, var(--text-primary) 55%, transparent);
}

/* 菜单行悬浮高亮条 */
.pb-glow {
  position: absolute;
  inset-inline: 4px;
  opacity: 0;
  pointer-events: none;
  background: color-mix(in srgb, var(--text-primary) 8%, transparent);
  border-radius: 8px;
  transition:
    top 220ms cubic-bezier(0.23, 1, 0.32, 1),
    height 220ms cubic-bezier(0.23, 1, 0.32, 1),
    opacity 150ms ease;
}

@media (prefers-reduced-motion: reduce) {
  .pb-glow {
    transition: opacity 150ms ease;
  }
}

.pb-row {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 36px;
  padding: 0 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  outline: none;
  -webkit-tap-highlight-color: transparent;
}

.pb-row--disabled {
  cursor: default;
}

.pb-row--disabled .pb-row-name,
.pb-row--disabled .pb-row-desc,
.pb-row--disabled .pb-row-icon {
  opacity: 0.5;
}

.pb-row-icon {
  display: inline-flex;
  justify-content: center;
  flex: none;
  width: 20px;
  color: color-mix(in srgb, var(--text-primary) 70%, transparent);
}

.pb-row-name {
  flex: none;
  font-size: 13px;
  font-weight: 500;
}

.pb-row-desc {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pb-row-tag {
  flex: none;
  margin-left: auto;
  font-size: 11px;
}

.pb-row-check {
  display: inline-flex;
  justify-content: center;
  flex: none;
  width: 16px;
  opacity: 0;
  color: var(--lumi-primary);
}

.pb-row-check--on {
  opacity: 1;
}

.pb-model-settings {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  width: 100%;
  height: 30px;
  padding: 0 8px;
  margin-top: 2px;
  border: 0;
  border-top: 1px solid var(--border-light);
  border-radius: 0 0 8px 8px;
  background: transparent;
  font-size: 12px;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: color 150ms ease;
}

.pb-model-settings:hover {
  color: var(--lumi-primary);
}

/* ── effort 弹层内容 ──────────────────────────────────────────── */
.pb-effort-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  line-height: 18px;
}

.pb-effort-level {
  font-weight: 500;
}

.pb-effort-help {
  display: inline-flex;
  margin-left: auto;
  cursor: help;
}

.pb-effort-ends {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
  font-size: 12px;
  line-height: 16px;
}

.pb-effort-slider {
  position: relative;
  height: 22px;
  margin-top: 8px;
  border-radius: 11px;
  background: color-mix(in srgb, var(--text-primary) 8%, transparent);
  cursor: pointer;
  touch-action: none;
  user-select: none;
  outline: none;
}

.pb-effort-slider:focus-visible {
  box-shadow: 0 0 0 3px var(--focus-ring);
}

/* 内坐标空间：游标/刻度/填充的 left 由 stepAt(k) 以 calc(11px + (100% - 22px)*k) 直写 */
.pb-effort-fill {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: calc(11px + (100% - 22px) * 0.5 + 7px);
  border-radius: 11px;
  background: color-mix(in srgb, var(--text-primary) 18%, transparent);
  transition: background-color 300ms ease;
}

.pb-effort-slider--max .pb-effort-fill {
  background: color-mix(in srgb, var(--lumi-primary) 35%, transparent);
}

.pb-effort-tick {
  position: absolute;
  top: 50%;
  width: 4px;
  height: 4px;
  margin: -2px 0 0 -2px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--text-primary) 30%, transparent);
}

.pb-effort-cursor {
  position: absolute;
  top: -3px;
  width: 14px;
  height: 28px;
  margin-left: -7px;
  border-radius: 7px;
  background: var(--text-primary);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
  transition: background-color 300ms ease;
}

.pb-effort-slider--max .pb-effort-cursor {
  background: var(--lumi-primary);
}

/* ── 输入卡 ───────────────────────────────────────────────────── */
.pb-card {
  position: relative;
  isolation: isolate;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: 16px;
  box-shadow: var(--shadow-sm);
  cursor: text;
  transition: border-color 150ms ease, box-shadow 200ms ease;
}

.pb-card:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

/* max 档位时卡底部的主题色辉光 */
.pb-card::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  border-radius: inherit;
  background: radial-gradient(140% 120% at 0% 100%, color-mix(in srgb, var(--lumi-primary) 26%, transparent), transparent 62%);
  opacity: 0;
  pointer-events: none;
  transition: opacity 500ms ease;
}

.pb-root[data-max] .pb-card::before {
  opacity: 1;
}

.pb-spark {
  position: absolute;
  inset: 0;
  z-index: -1;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  pointer-events: none;
}

.pb-card-inner {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 附件 chips */
.pb-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pb-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  padding: 0 4px 0 8px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--text-primary) 8%, transparent);
  font-size: 12px;
  animation: pb-pop 200ms cubic-bezier(0.23, 1, 0.32, 1) both;
}

@media (prefers-reduced-motion: reduce) {
  .pb-chip {
    animation: none;
  }
}

.pb-chip-name {
  max-width: 144px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pb-chip-remove {
  display: inline-grid;
  place-items: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: inherit;
  opacity: 0.6;
  cursor: pointer;
  transition: opacity 120ms ease, background-color 120ms ease;
}

.pb-chip-remove:hover {
  opacity: 1;
  background: color-mix(in srgb, var(--text-primary) 10%, transparent);
}

/* textarea */
.pb-input {
  display: block;
  width: 100%;
  border: 0;
  outline: none;
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 14px;
  line-height: 22px;
  resize: none;
  overflow-wrap: anywhere;
}

@media (pointer: coarse) {
  .pb-input {
    font-size: 16px;
  }
}

.pb-input::placeholder {
  color: color-mix(in srgb, var(--text-primary) 45%, transparent);
}

.pb-input:disabled {
  cursor: not-allowed;
}

/* ── 工具行 ───────────────────────────────────────────────────── */
.pb-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
}

.pb-icon-btn,
.pb-tool-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex: none;
  height: 28px;
  padding: 0 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: color-mix(in srgb, var(--text-primary) 70%, transparent);
  font: inherit;
  font-size: 12px;
  font-weight: 500;
  outline: none;
  user-select: none;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background-color 150ms ease, color 150ms ease, transform 160ms cubic-bezier(0.23, 1, 0.32, 1);
}

.pb-icon-btn {
  width: 28px;
  padding: 0;
  justify-content: center;
}

.pb-icon-btn:hover:not(:disabled),
.pb-tool-btn:hover:not(:disabled),
.pb-icon-btn.pb-btn--on:not(:disabled),
.pb-tool-btn.pb-btn--on:not(:disabled) {
  background: color-mix(in srgb, var(--text-primary) 8%, transparent);
  color: var(--text-primary);
}

.pb-icon-btn:active:not(:disabled) {
  transform: scale(0.94);
}

@media (prefers-reduced-motion: reduce) {
  .pb-icon-btn:active:not(:disabled) {
    transform: none;
  }
}

.pb-icon-btn:disabled,
.pb-tool-btn:disabled {
  cursor: default;
}

.pb-tool-btn-text {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pb-tool-btn--max {
  color: var(--lumi-primary);
}

.pb-spacer {
  flex: 1;
}

/* 发送圆钮 */
.pb-send-btn {
  position: relative;
  display: inline-grid;
  place-items: center;
  flex: none;
  width: 30px;
  height: 30px;
  padding: 0;
  border: 0;
  border-radius: 9px;
  background: color-mix(in srgb, var(--text-primary) 12%, var(--surface));
  color: color-mix(in srgb, var(--text-primary) 55%, var(--surface));
  font: inherit;
  outline: none;
  user-select: none;
  cursor: pointer;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  transition:
    background-color 200ms ease,
    color 200ms ease,
    transform 160ms cubic-bezier(0.23, 1, 0.32, 1);
}

.pb-send-btn:disabled {
  cursor: default;
}

.pb-send-btn:not(:disabled) {
  background: var(--text-primary);
  color: var(--surface);
}

.pb-send-btn--pressed:not(:disabled) {
  transform: scale(0.94);
}

@media (prefers-reduced-motion: reduce) {
  .pb-send-btn--pressed:not(:disabled) {
    transform: none;
  }
}

.pb-send-svg {
  display: block;
  width: 16px;
  height: 16px;
  transform-origin: center;
}
</style>
