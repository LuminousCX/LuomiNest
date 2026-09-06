import { ref, watch, type Ref } from 'vue'

/**
 * 防抖搜索 composable（竞态守卫 + 请求取消）。
 *
 * - `isSearching` 仅在防抖结束、真正发起请求后才置 true（避免每个按键都闪 loading）
 * - 新请求发起前会 abort 上一个 AbortController；`searchFn` 可选接收 signal 透传给 fetch
 * - 空查询立即清空结果并取消在途请求
 */
export function useDebouncedSearch<T extends unknown[]>(
  query: Ref<string>,
  searchFn: (q: string, signal?: AbortSignal) => Promise<T>,
  wait = 300,
): {
  results: Ref<T>
  isSearching: Ref<boolean>
} {
  const results = ref([]) as unknown as Ref<T>
  const isSearching = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null
  let seq = 0
  let controller: AbortController | null = null

  watch(
    query,
    (q) => {
      if (timer) clearTimeout(timer)
      const trimmed = q.trim()
      seq++
      if (!trimmed) {
        controller?.abort()
        controller = null
        results.value = [] as unknown as T
        isSearching.value = false
        return
      }
      const currentSeq = seq
      timer = setTimeout(async () => {
        controller?.abort()
        controller = new AbortController()
        const signal = controller.signal
        isSearching.value = true
        try {
          const data = await searchFn(trimmed, signal)
          if (currentSeq === seq) {
            results.value = data
          }
        } catch {
          if (currentSeq === seq) {
            results.value = [] as unknown as T
          }
        } finally {
          if (currentSeq === seq) {
            isSearching.value = false
          }
        }
      }, wait)
    },
    { immediate: true },
  )

  return { results, isSearching }
}
