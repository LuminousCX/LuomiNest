import type { Directive } from 'vue'

interface Binding {
  handler: (e: MouseEvent) => void
  capture: boolean
}

const bindings = new WeakMap<HTMLElement, Binding>()

/**
 * 点击元素外部时触发回调。
 * 用法：vClickOutside="handler"；需要 capture 阶段监听时用 vClickOutside.capture。
 * 点击目标在元素内部时不触发；打开状态等守卫由调用方在 handler 内自行判断。
 */
export const vClickOutside: Directive<HTMLElement, (e: MouseEvent) => void> = {
  mounted(el, binding) {
    const capture = !!binding.modifiers.capture
    const handler = (e: MouseEvent) => {
      if (el.contains(e.target as Node)) return
      binding.value?.(e)
    }
    bindings.set(el, { handler, capture })
    document.addEventListener('click', handler, capture)
  },
  unmounted(el) {
    const binding = bindings.get(el)
    if (binding) {
      document.removeEventListener('click', binding.handler, binding.capture)
      bindings.delete(el)
    }
  }
}
