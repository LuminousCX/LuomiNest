import type { Ref } from 'vue'
import type { ChatMessage } from '../types'

/** 滚动容器度量（scrollTop/scrollHeight/clientHeight） */
export interface ScrollMetrics {
  scrollTop: number
  scrollHeight: number
  clientHeight: number
}

/** 贴底判定阈值（px）：距底部小于该值视为贴底 */
export const SCROLL_BOTTOM_THRESHOLD = 120

/**
 * 聊天消息区滚动控制（工作台/对话页共用）
 *
 * 收纳 scrollToBottom、ResizeObserver 内容增高跟随、贴底判定、
 * "回到底部"按钮可见性更新。isNearBottom 的权威来源由调用方决定：
 * - WorkspaceAgentChat：组件本地 ref，滚动时由本 composable 直接写入
 * - WorkbenchChatArea：来自 props（父级 useWorkbenchMessages 持有），
 *   组件内经"读取 props、写入吞掉"的 computed 桥接，度量同时 emit 给父级重算
 */
export const useChatScroll = (options: {
  /** 滚动容器 */
  container: Ref<HTMLElement | null>
  /** 是否贴底（可写 ref / 可写 computed） */
  isNearBottom: Ref<boolean>
  /** "回到底部"按钮可见性；不传则滚动时不更新该状态 */
  showScrollToBottomBtn?: Ref<boolean>
  /** 消息数量（按钮仅在存在消息时显示） */
  getMessageCount?: () => number
}) => {
  const getMetrics = (): ScrollMetrics | null => {
    if (!options.container.value) return null
    const { scrollTop, scrollHeight, clientHeight } = options.container.value
    return { scrollTop, scrollHeight, clientHeight }
  }

  const scrollToBottom = (force = false): void => {
    if (!options.container.value) return
    if (!force && !options.isNearBottom.value) return
    options.container.value.scrollTo({
      top: options.container.value.scrollHeight,
      behavior: force ? 'auto' : 'smooth',
    })
  }

  let resizeObserver: ResizeObserver | null = null

  const setupResizeObserver = (): void => {
    if (!options.container.value) return
    const inner = options.container.value.querySelector('.messages-container') as HTMLElement
    if (!inner) return
    resizeObserver = new ResizeObserver(() => {
      if (options.isNearBottom.value) {
        scrollToBottom(true)
      }
    })
    resizeObserver.observe(inner)
  }

  const teardownResizeObserver = (): void => {
    resizeObserver?.disconnect()
    resizeObserver = null
  }

  /**
   * 滚动事件处理：更新贴底状态与按钮可见性，返回本次度量供调用方继续消费
   * （如 WorkbenchChatArea 需要把同一份 metrics emit 给父级）。
   * 可传入外部度量（父级已算好的场景），不传则从容器读取。
   */
  const handleScroll = (metrics?: ScrollMetrics): ScrollMetrics | null => {
    const m = metrics ?? getMetrics()
    if (!m) return null
    if (options.showScrollToBottomBtn) {
      updateScrollBottomState(m, options.isNearBottom, options.showScrollToBottomBtn, options.getMessageCount?.() ?? 0)
    } else {
      const distanceFromBottom = m.scrollHeight - m.scrollTop - m.clientHeight
      options.isNearBottom.value = distanceFromBottom < SCROLL_BOTTOM_THRESHOLD
    }
    return m
  }

  return {
    getMetrics,
    scrollToBottom,
    setupResizeObserver,
    teardownResizeObserver,
    handleScroll,
  }
}

/** 根据滚动度量更新贴底状态与"回到底部"按钮可见性 */
export const updateScrollBottomState = (
  metrics: ScrollMetrics,
  isNearBottom: Ref<boolean>,
  showScrollToBottomBtn: Ref<boolean>,
  messageCount: number,
): void => {
  const distanceFromBottom = metrics.scrollHeight - metrics.scrollTop - metrics.clientHeight
  isNearBottom.value = distanceFromBottom < SCROLL_BOTTOM_THRESHOLD
  showScrollToBottomBtn.value = !isNearBottom.value && messageCount > 0
}

/**
 * 是否为最后一条 assistant 消息（用于"重新生成"等操作按钮的显隐）。
 * 存在未完成的 assistant 消息（正在流式输出）时一律返回 false。
 */
export const isLastAssistantMessage = (msgs: ChatMessage[], msgId: string): boolean => {
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant' && !msgs[i].done) return false
  }
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant') {
      return msgs[i].id === msgId
    }
  }
  return false
}
