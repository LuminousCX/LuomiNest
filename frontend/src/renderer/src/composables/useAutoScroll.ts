import { nextTick, watch, type Ref, type WatchSource } from 'vue'

interface AutoScrollOptions {
  /** 深度监听 source（消息数组内部变更时也触发） */
  deep?: boolean
  /** 平滑滚动，默认直接跳到底部 */
  smooth?: boolean
}

/**
 * 监听 source 变化，DOM 更新完成后把容器滚动到底部。
 * 返回 scrollToBottom 供需要手动触发的场景调用。
 */
export function useAutoScroll(
  containerRef: Ref<HTMLElement | null>,
  source: WatchSource<unknown>,
  options: AutoScrollOptions = {}
) {
  const scrollToBottom = () => {
    const el = containerRef.value
    if (!el) return
    if (options.smooth) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    } else {
      el.scrollTop = el.scrollHeight
    }
  }

  watch(source, () => {
    nextTick(scrollToBottom)
  }, { deep: options.deep, flush: 'post' })

  return { scrollToBottom }
}
