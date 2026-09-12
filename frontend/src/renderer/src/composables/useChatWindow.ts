import { computed, nextTick, ref, watch, type Ref } from 'vue'

/**
 * 聊天消息列表窗口化渲染（保守方案：原生滚动条 + 尾部窗口）
 *
 * 长会话全量 v-for 会让 DOM 随历史线性增长；这里只把消息数组"尾部窗口"挂载到
 * DOM，向上滚动接近顶部时向前分批扩展窗口，并对挂载做滚动位置补偿。
 * 刻意不做严格虚拟化（无定高估算/测量裁剪），从而完整保留：
 * - 原生滚动条与惯性
 * - TransitionGroup 入场动画（历史行抑制，新消息行照常播放）
 * - 流式贴底（useChatScroll 的 ResizeObserver 跟随 / useAutoScroll）
 * - 搜索定位（需要时可展开全量后按 DOM 文本定位）
 *
 * 窗口只减不增（不做顶部裁剪）：流式追加发生在窗口下方、用户在历史区时
 * 追加也不影响视口锚定，因此仅在"向上挂载"时需要一次 scrollTop 补偿。
 */

/** 初始仅渲染最近 N 条消息 */
export const CHAT_WINDOW_INITIAL = 40
/** 距顶部小于该距离（px）时向上加载一批 */
export const CHAT_WINDOW_LOAD_TRIGGER_PX = 800
/** 每次向上加载的消息条数 */
export const CHAT_WINDOW_LOAD_STEP = 30

export const useChatWindow = <T extends { id: string }>(options: {
  /** 完整消息数组（响应式来源） */
  messages: () => T[]
  /** 滚动容器 */
  container: Ref<HTMLElement | null>
  /** 消息行元素选择器（滚动位置补偿时用于定位"原首行"） */
  rowSelector: string
}) => {
  /** 窗口起始索引（只减不增，0 表示全量） */
  const renderedStart = ref(0)
  /** 入场动画分界索引：小于该值的行是"加载时已在历史里"的行，挂载不播放入场动画 */
  const historyBoundary = ref(0)

  const visibleMessages = computed(() => {
    const msgs = options.messages()
    return renderedStart.value > 0 ? msgs.slice(renderedStart.value) : msgs
  })

  const resetWindow = (): void => {
    const msgs = options.messages()
    renderedStart.value = Math.max(0, msgs.length - CHAT_WINDOW_INITIAL)
    historyBoundary.value = renderedStart.value
  }

  // 会话变更检测：清空、初始化（0 → N）或首条消息 id 变化（切换到其他会话，
  // 含已缓存会话）时重置窗口。流式输出为就地追加（首条 id 与长度不减）、
  // 发送为尾部追加，均不触发重置；删除消息只会命中已挂载窗口内的行，
  // 不改变首条 id，也不需要重置。
  watch(
    () => {
      const msgs = options.messages()
      return { len: msgs.length, firstId: msgs[0]?.id }
    },
    (next, prev) => {
      if (!prev || next.len === 0 || prev.len === 0 || next.firstId !== prev.firstId) {
        resetWindow()
      }
    },
    { immediate: true },
  )

  let prepending = false

  /** 行元素相对滚动容器内容顶部的绝对偏移 */
  const contentOffsetTop = (el: HTMLElement, row: HTMLElement): number =>
    row.getBoundingClientRect().top - el.getBoundingClientRect().top + el.scrollTop

  /**
   * 向前扩展窗口并补偿滚动位置：挂载完成后按"原首行新偏移 - 原首行旧偏移"
   * 校正 scrollTop，视口内容保持不动。
   */
  const loadOlder = (): void => {
    const el = options.container.value
    if (!el || prepending || renderedStart.value <= 0) return
    const prevStart = renderedStart.value
    const prevFirstRow = el.querySelector(options.rowSelector) as HTMLElement | null
    const prevFirstTop = prevFirstRow ? contentOffsetTop(el, prevFirstRow) : null
    prepending = true
    renderedStart.value = Math.max(0, prevStart - CHAT_WINDOW_LOAD_STEP)
    nextTick(() => {
      prepending = false
      if (prevFirstTop === null) return
      // 挂载前渲染的首行现在排在第 mountedCount 个，用它度量内容整体下移量
      const mountedCount = prevStart - renderedStart.value
      const anchorRow = el.querySelectorAll(options.rowSelector)[mountedCount] as HTMLElement | undefined
      if (!anchorRow) return
      el.scrollTop += contentOffsetTop(el, anchorRow) - prevFirstTop
    })
  }

  /** 滚动事件钩子：接近顶部时向上加载一批（组件在自身 scroll 处理中调用） */
  const maybeLoadOlder = (): void => {
    const el = options.container.value
    if (!el || renderedStart.value <= 0) return
    if (el.scrollTop < CHAT_WINDOW_LOAD_TRIGGER_PX) loadOlder()
  }

  return {
    /** 当前窗口起始索引（供"行是否为历史行"与搜索展开全量使用） */
    renderedStart,
    /** 历史行动画分界索引 */
    historyBoundary,
    /** 实际渲染的消息切片 */
    visibleMessages,
    /** 重置窗口（会话切换；由 watch 自动触发，一般无需手动调用） */
    resetWindow,
    /** 接近顶部时向上加载一批并补偿滚动位置 */
    maybeLoadOlder,
    /** 立即向上加载一批（无视触发距离） */
    loadOlder,
  }
}
