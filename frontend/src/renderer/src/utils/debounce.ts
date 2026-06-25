export const debounce = <T extends (...args: Parameters<T>) => ReturnType<T>>(
  fn: T,
  wait: number,
): ((...args: Parameters<T>) => void) => {
  let timer: ReturnType<typeof setTimeout> | null = null

  return (...args: Parameters<T>) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      fn(...args)
    }, wait)
  }
}

export const throttle = <T extends (...args: Parameters<T>) => ReturnType<T>>(
  fn: T,
  wait: number,
): ((...args: Parameters<T>) => void) => {
  let lastTime = 0
  let timer: ReturnType<typeof setTimeout> | null = null

  return (...args: Parameters<T>) => {
    const now = Date.now()
    const remaining = wait - (now - lastTime)

    if (remaining <= 0) {
      if (timer) {
        clearTimeout(timer)
        timer = null
      }
      lastTime = now
      fn(...args)
    } else if (!timer) {
      timer = setTimeout(() => {
        lastTime = Date.now()
        timer = null
        fn(...args)
      }, remaining)
    }
  }
}
