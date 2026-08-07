import { ref, watch, type Ref } from 'vue'

export function useDebouncedSearch<T extends unknown[]>(
  query: Ref<string>,
  searchFn: (q: string) => Promise<T>,
  wait = 300,
): {
  results: Ref<T>
  isSearching: Ref<boolean>
} {
  const results = ref([]) as unknown as Ref<T>
  const isSearching = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null
  let seq = 0

  watch(
    query,
    (q) => {
      if (timer) clearTimeout(timer)
      const trimmed = q.trim()
      if (!trimmed) {
        results.value = [] as unknown as T
        isSearching.value = false
        return
      }
      isSearching.value = true
      seq++
      const currentSeq = seq
      timer = setTimeout(async () => {
        try {
          const data = await searchFn(trimmed)
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

  return { results: results as Ref<T>, isSearching }
}
