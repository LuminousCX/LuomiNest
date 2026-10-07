<script lang="ts">
import type { Component } from 'vue'

export interface BranchedMenuChild {
  /** 唯一取值，select 事件回传 */
  value: string
  label: string
  icon?: Component
  /** 右侧呼吸点（如任务派发等待态） */
  pending?: boolean
}

export interface BranchedMenuItem {
  label: string
  icon?: Component
  /** 顶层叶子的取值；提供 children 时该条目作为可折叠分组 */
  value?: string
  pending?: boolean
  children?: BranchedMenuChild[]
}
</script>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { ChevronRight } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    items: BranchedMenuItem[]
    /** 初始展开的分组下标，-1 表示全不展开 */
    defaultOpen?: number | number[]
    /** 非受控时的初始激活值 */
    defaultActive?: string
    /** 受控激活值（路由驱动）：传入后以它为准 */
    active?: string
    /** 手风琴：同一时刻只展开一个分组 */
    accordion?: boolean
    /** 墨色（文字），可传 CSS 变量 */
    color?: string
    /** 强调色（激活行文字与 reach 引流线），可传 CSS 变量 */
    accentColor?: string
    /** 枝干线颜色，可传 CSS 变量 */
    lineColor?: string
    width?: number
    rowHeight?: number
    /** 子行文字缩进（枝线画到 indent-8 处） */
    indent?: number
    /** 干线距左缘的距离 */
    trunk?: number
    radius?: number
    lineWidth?: number
    /** 可传字符串令牌，如 'var(--text-base)' */
    fontSize?: number | string
    iconSize?: number
    /** 激活切换时 reach 线的描线时长 */
    drawDuration?: number
    /** 折叠/展开高度动画时长 */
    foldDuration?: number
  }>(),
  {
    defaultOpen: 0,
    defaultActive: '',
    accordion: false,
    color: '',
    accentColor: '',
    lineColor: '',
    width: undefined,
    rowHeight: 34,
    indent: 44,
    trunk: 14,
    radius: 10,
    lineWidth: 1.5,
    fontSize: 'var(--text-base)',
    iconSize: 15,
    drawDuration: 400,
    foldDuration: 300,
  },
)

const emit = defineEmits<{
  select: [value: string, item: BranchedMenuItem | BranchedMenuChild]
}>()

const FOLD_EASE = 'cubic-bezier(0.4, 0, 0.2, 1)'
/** 分组头旁滑动 marker 的高度（px） */
const MARK = 16

const ink = computed(() => props.color || 'var(--text-primary)')
const accent = computed(() => props.accentColor || 'var(--nav-item-active-color, var(--lumi-brand))')
const line = computed(() => props.lineColor || 'var(--border)')

const isLeaf = (item: BranchedMenuItem): boolean => !item.children?.length

const openSet = ref<Set<number>>(new Set())

const initOpen = (): Set<number> => {
  const raw = props.defaultOpen
  const list = Array.isArray(raw) ? raw : [raw]
  const next = new Set<number>()
  for (const i of list) {
    if (i >= 0 && props.items[i] && !isLeaf(props.items[i])) next.add(i)
  }
  return next
}
openSet.value = initOpen()

const isOpen = (index: number): boolean => openSet.value.has(index)

const internalActive = ref(props.defaultActive)
const effectiveActive = computed(() => props.active ?? internalActive.value)

const ownerIndexOf = (value: string): number =>
  props.items.findIndex((it) => it.children?.some((c) => c.value === value))

const openSection = (index: number): void => {
  if (isLeaf(props.items[index])) return
  openSet.value = props.accordion ? new Set([index]) : new Set([...openSet.value, index])
}

const toggleSection = (index: number): void => {
  if (isOpen(index)) {
    const next = new Set(openSet.value)
    next.delete(index)
    openSet.value = next
  } else {
    openSection(index)
  }
}

// 路由驱动的激活值变化时，自动展开所在分组（手风琴下自动收起其他分组）
watch(
  effectiveActive,
  (val) => {
    if (!val) return
    const i = ownerIndexOf(val)
    if (i >= 0 && !openSet.value.has(i)) openSection(i)
  },
  { immediate: true },
)

const isActive = (value?: string): boolean => !!value && effectiveActive.value === value

/* ===== 滑动 marker：贴在激活子项所在分组的分组头旁 ===== */

const navRef = ref<HTMLElement | null>(null)
const markerRef = ref<HTMLSpanElement | null>(null)
const heads: (HTMLButtonElement | null)[] = []
let resizeObserver: ResizeObserver | null = null

const activeSection = computed(() => ownerIndexOf(effectiveActive.value))
const markerShown = computed(() => activeSection.value >= 0 && isOpen(activeSection.value))

const place = (glide: boolean): void => {
  const m = markerRef.value
  const el = heads[activeSection.value]
  if (!m) return
  const on = markerShown.value && !!el
  if (!glide) m.style.transition = 'none'
  // 分组头位于 position:relative 的 .bm-section 内，offsetTop 不相对菜单根，
  // 因此用 getBoundingClientRect 差值求菜单坐标系下的纵位
  if (on && el && navRef.value) {
    const relTop = el.getBoundingClientRect().top - navRef.value.getBoundingClientRect().top
    m.style.top = `${relTop + (el.offsetHeight - MARK) / 2}px`
  }
  m.toggleAttribute('data-on', on)
  if (!glide) {
    void m.offsetHeight
    m.style.transition = ''
  }
}

const bindMarker = (): void => {
  resizeObserver?.disconnect()
  place(true)
  let first = true
  resizeObserver = new ResizeObserver(() => {
    // 首次回调与初始 place 重复，跳过避免闪烁
    if (first) {
      first = false
      return
    }
    place(false)
  })
  if (navRef.value) resizeObserver.observe(navRef.value)
}

onMounted(bindMarker)
onUnmounted(() => resizeObserver?.disconnect())
watch(
  () => [activeSection.value, markerShown.value, props.items, props.fontSize, props.rowHeight],
  () => bindMarker(),
  { flush: 'post' },
)

/* ===== 选择与折叠 ===== */

const onHeaderClick = (item: BranchedMenuItem, index: number): void => {
  if (isLeaf(item)) {
    if (item.value) {
      internalActive.value = item.value
      emit('select', item.value, item)
    }
    return
  }
  toggleSection(index)
}

const onChildClick = (child: BranchedMenuChild): void => {
  internalActive.value = child.value
  emit('select', child.value, child)
}

/* ===== 枝线几何（与 vue-bits BranchedMenu 官方实现同构） =====
 * 每个分组一张 SVG：干段 + 每行灰色分叉 + 每行强调色 reach 引流线。
 * reach 从容器顶延伸到当前行，激活切换时旧线收回、新线画出，
 * 因此激活行下方的干线不再残留点亮。 */
const r = computed(() => Math.min(props.radius, props.rowHeight / 2 - 2))
const endX = computed(() => props.indent - 8)
const rowY = (k: number): number => k * props.rowHeight + props.rowHeight / 2

const branchPath = (k: number): string =>
  `M ${props.trunk} ${rowY(k) - r.value} A ${r.value} ${r.value} 0 0 0 ${props.trunk + r.value} ${rowY(k)} H ${endX.value}`

const reachPath = (k: number): string =>
  `M ${props.trunk} 0 V ${rowY(k) - r.value} A ${r.value} ${r.value} 0 0 0 ${props.trunk + r.value} ${rowY(k)} H ${endX.value}`

const reachLength = (k: number): number =>
  rowY(k) - r.value + (Math.PI * r.value) / 2 + (endX.value - props.trunk - r.value)

const childrenTrunkPath = (count: number): string => `M ${props.trunk} 0 V ${rowY(count - 1) - r.value}`

const childrenHeight = (count: number): number => count * props.rowHeight

const reachStyle = (k: number, childValue: string): Record<string, string> => ({
  strokeDasharray: `${reachLength(k)}`,
  strokeDashoffset: childValue === effectiveActive.value ? '0' : `${reachLength(k)}`,
})

/* ===== 折叠动画（JS 高度过渡，等价于官方 grid-rows 0fr/1fr 方案） ===== */

const prefersReducedMotion = (): boolean =>
  typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const foldMs = (): number => (prefersReducedMotion() ? 0 : props.foldDuration)

const onFoldEnter = (el: Element, done: () => void): void => {
  const node = el as HTMLElement
  const ms = foldMs()
  if (!ms) {
    done()
    return
  }
  node.style.overflow = 'hidden'
  node.style.transition = `height ${ms}ms ${FOLD_EASE}, opacity ${Math.round(ms * 0.6)}ms ${FOLD_EASE}`
  node.style.height = '0'
  node.style.opacity = '0'
  void node.offsetHeight
  node.style.height = `${node.scrollHeight}px`
  node.style.opacity = '1'
  window.setTimeout(done, ms)
}

const onFoldAfterEnter = (el: Element): void => {
  const node = el as HTMLElement
  node.style.transition = ''
  node.style.height = ''
  node.style.overflow = ''
  node.style.opacity = ''
}

const onFoldLeave = (el: Element, done: () => void): void => {
  const node = el as HTMLElement
  const ms = foldMs()
  if (!ms) {
    done()
    return
  }
  node.style.overflow = 'hidden'
  node.style.transition = `height ${ms}ms ${FOLD_EASE}, opacity ${Math.round(ms * 0.6)}ms ${FOLD_EASE}`
  node.style.height = `${node.scrollHeight}px`
  node.style.opacity = '1'
  void node.offsetHeight
  node.style.height = '0'
  node.style.opacity = '0'
  window.setTimeout(done, ms)
}

const onFoldAfterLeave = onFoldAfterEnter

defineExpose({ openSection })

const rootStyle = computed(() => ({
  '--bm-ink': ink.value,
  '--bm-accent': accent.value,
  '--bm-line': line.value,
  '--bm-row-h': `${props.rowHeight}px`,
  '--bm-indent': `${props.indent}px`,
  '--bm-trunk': `${props.trunk}px`,
  '--bm-radius': `${props.radius}px`,
  '--bm-line-w': `${props.lineWidth}px`,
  '--bm-icon-size': `${props.iconSize}px`,
  '--bm-draw-ms': `${props.drawDuration}ms`,
  width: props.width ? `${props.width}px` : '100%',
  fontSize: typeof props.fontSize === 'number' ? `${props.fontSize}px` : props.fontSize,
}))
</script>

<template>
  <nav ref="navRef" class="bm-menu" :style="rootStyle">
    <span ref="markerRef" class="bm-marker" aria-hidden="true"></span>
    <div
      v-for="(item, index) in items"
      :key="item.value || item.label"
      :class="['bm-section', { 'bm-section--open': isOpen(index) }]"
    >
      <!-- 分组头 / 顶层叶子 -->
      <button
        v-if="!isLeaf(item)"
        :ref="(el) => (heads[index] = el as HTMLButtonElement | null)"
        type="button"
        class="bm-header"
        :aria-expanded="isOpen(index)"
        @click="onHeaderClick(item, index)"
      >
        <component :is="item.icon" v-if="item.icon" :size="iconSize" class="bm-icon" />
        <span class="bm-label">{{ item.label }}</span>
        <ChevronRight :size="13" class="bm-chevron" :class="{ open: isOpen(index) }" />
      </button>
      <button
        v-else
        type="button"
        :class="['bm-row', 'bm-row--leaf', { active: isActive(item.value) }]"
        @click="onHeaderClick(item, index)"
      >
        <component :is="item.icon" v-if="item.icon" :size="iconSize" class="bm-icon" />
        <span class="bm-label">{{ item.label }}</span>
        <span v-if="item.pending" class="bm-pending"></span>
      </button>

      <!-- 子行（折叠动画；SVG 内含干段 + 分叉 + reach 引流线） -->
      <Transition :css="false" @enter="onFoldEnter" @after-enter="onFoldAfterEnter" @leave="onFoldLeave" @after-leave="onFoldAfterLeave">
        <div v-if="isOpen(index)" class="bm-children">
          <svg
            class="bm-branches"
            :width="indent"
            :height="childrenHeight(item.children!.length)"
            aria-hidden="true"
          >
            <path class="bm-stroke" :d="childrenTrunkPath(item.children!.length)" />
            <path v-for="(child, k) in item.children" :key="`b-${child.value}`" class="bm-stroke" :d="branchPath(k)" />
            <path
              v-for="(child, k) in item.children"
              :key="`r-${child.value}`"
              class="bm-stroke bm-stroke--reach"
              :d="reachPath(k)"
              :style="reachStyle(k, child.value)"
            />
          </svg>
          <button
            v-for="child in item.children"
            :key="child.value"
            type="button"
            :class="['bm-row', { active: isActive(child.value) }]"
            @click="onChildClick(child)"
          >
            <span class="bm-icon-slot">
              <component :is="child.icon" v-if="child.icon" :size="iconSize" class="bm-icon" />
            </span>
            <span class="bm-label">{{ child.label }}</span>
            <span v-if="child.pending" class="bm-pending"></span>
          </button>
        </div>
      </Transition>
    </div>
  </nav>
</template>

<style scoped>
.bm-menu {
  position: relative;
  color: var(--bm-ink);
  user-select: none;
}

/* ===== 滑动 marker：激活子项所在分组的“当前位置”指示 ===== */
.bm-marker {
  position: absolute;
  left: 0;
  top: 0;
  z-index: 1;
  width: calc(var(--bm-line-w) + 0.5px);
  height: 16px;
  border-radius: 1px;
  background: var(--bm-accent);
  opacity: 0;
  transition:
    top 220ms cubic-bezier(0.23, 1, 0.32, 1),
    opacity 150ms ease;
}

.bm-marker[data-on] {
  opacity: 1;
}

/* ===== 分组容器与头部干段 ===== */
.bm-section {
  position: relative;
}

/* 干段只覆盖分组头一行；子项区域的干段由 SVG 的 childrenTrunk 承接 */
.bm-section::before {
  content: '';
  position: absolute;
  left: calc(var(--bm-trunk) - var(--bm-line-w) / 2);
  top: 0;
  height: var(--bm-row-h);
  width: var(--bm-line-w);
  border-radius: var(--bm-line-w);
  background: var(--bm-line);
}

.bm-section + .bm-section {
  margin-top: var(--space-1, 4px);
}

/* ===== 分组头 / 顶层叶子 ===== */
.bm-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--space-2, 8px);
  height: var(--bm-row-h);
  padding: 0 var(--space-2, 8px) 0 calc(var(--bm-trunk) + 8px);
  border: none;
  background: transparent;
  border-radius: var(--bm-radius);
  cursor: pointer;
  color: inherit;
  font: inherit;
  text-align: left;
  transition: background var(--transition-fast, 150ms) ease;
}

.bm-header:hover {
  background: var(--nav-item-hover-bg, var(--surface-hover));
}

.bm-header .bm-label {
  color: color-mix(in srgb, var(--bm-ink) 62%, transparent);
  font-weight: var(--font-semibold, 600);
  transition: color var(--transition-fast, 150ms) ease;
}

/* 展开的分组头提亮为墨色（与官方 open 态一致） */
.bm-section--open > .bm-header .bm-label {
  color: var(--bm-ink);
}

.bm-icon {
  flex-shrink: 0;
  color: inherit;
}

.bm-chevron {
  margin-left: auto;
  flex-shrink: 0;
  opacity: 0.45;
  transition: transform var(--transition-fast, 150ms) ease, opacity var(--transition-fast, 150ms) ease;
}

.bm-header:hover .bm-chevron {
  opacity: 0.8;
}

.bm-chevron.open {
  transform: rotate(90deg);
}

/* ===== 子行 ===== */
.bm-children {
  position: relative;
  min-height: 0;
}

.bm-row {
  position: relative;
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--space-2, 8px);
  height: var(--bm-row-h);
  padding: 0 var(--space-2, 8px) 0 var(--bm-indent);
  border: none;
  background: transparent;
  border-radius: var(--bm-radius);
  cursor: pointer;
  color: inherit;
  font: inherit;
  text-align: left;
  transition: background var(--transition-fast, 150ms) ease, color var(--transition-fast, 150ms) ease;
}

.bm-row .bm-label {
  color: color-mix(in srgb, var(--bm-ink) 62%, transparent);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color var(--transition-fast, 150ms) ease;
}

.bm-row:hover {
  background: var(--nav-item-hover-bg, var(--surface-hover));
}

.bm-row:hover .bm-label {
  color: var(--bm-ink);
}

.bm-row.active .bm-label {
  color: var(--bm-accent);
  font-weight: var(--font-semibold, 600);
}

.bm-row.active .bm-icon {
  color: var(--bm-accent);
}

/* ===== 枝线 SVG =====
 * 展开时整体淡入（官方为 opacity + 延迟，此处用 backwards 动画等效） */
.bm-branches {
  position: absolute;
  left: 0;
  top: 0;
  overflow: visible;
  pointer-events: none;
  animation: bm-branches-in 250ms ease 100ms backwards;
}

@keyframes bm-branches-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.bm-stroke {
  fill: none;
  stroke: var(--bm-line);
  stroke-width: var(--bm-line-w);
  stroke-linecap: round;
  stroke-linejoin: round;
}

/* reach 引流线：从容器顶画到激活行，切换时旧线收回/新线画出 */
.bm-stroke--reach {
  stroke: var(--bm-accent);
  transition: stroke-dashoffset var(--bm-draw-ms) cubic-bezier(0.23, 1, 0.32, 1);
}

/* 图标占位：固定宽度，保证无图标行与有图标行的文字对齐 */
.bm-icon-slot {
  width: var(--bm-icon-size);
  height: var(--bm-icon-size);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* 待处理呼吸点 */
.bm-pending {
  position: absolute;
  top: 50%;
  right: var(--space-2, 8px);
  transform: translateY(-50%);
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--bm-accent);
  box-shadow: 0 0 0 2px var(--surface, transparent);
  animation: bm-pending-pulse 1.6s ease-in-out infinite;
}

@keyframes bm-pending-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

/* 顶层叶子行与分组头视觉一致 */
.bm-row--leaf {
  padding-left: calc(var(--bm-trunk) + 8px);
}

.bm-row--leaf .bm-label {
  color: color-mix(in srgb, var(--bm-ink) 78%, transparent);
}

.bm-row--leaf.active .bm-label {
  color: var(--bm-accent);
}

.bm-row--leaf.active {
  background: var(--nav-item-active-bg, transparent);
}

/* 焦点可见性 */
.bm-header:focus-visible,
.bm-row:focus-visible {
  outline: 2px solid var(--focus-ring, var(--lumi-brand));
  outline-offset: -2px;
}

/* 减少动态效果：跳过淡入/引流/呼吸动画，直接呈现最终态 */
@media (prefers-reduced-motion: reduce) {
  .bm-branches {
    animation: none;
  }

  .bm-stroke--reach {
    transition: none;
  }

  .bm-marker {
    transition: opacity 150ms ease;
  }

  .bm-pending {
    animation: none;
  }
}
</style>
