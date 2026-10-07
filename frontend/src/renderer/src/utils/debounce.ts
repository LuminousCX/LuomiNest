export const debounce = <T extends (...args: Parameters<T>) => ReturnType<T>>(
  fn: T,
  wait: number,
): ((...args: Parameters<T>) => void) & { cancel: () => void } => {
  let timer: ReturnType<typeof setTimeout> | null = null

  const debounced = (...args: Parameters<T>): void => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      fn(...args)
    }, wait)
  }

  /** 取消挂起的调用（组件卸载时清理） */
  debounced.cancel = (): void => {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  return debounced
}
