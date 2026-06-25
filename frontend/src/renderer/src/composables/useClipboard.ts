import { ref } from 'vue'
import { copyToClipboard } from '../utils/clipboard'

export function useClipboard(timeout = 2000) {
  const copiedId = ref<string | null>(null)

  const copy = async (id: string, text: string) => {
    try {
      await copyToClipboard(text)
      copiedId.value = id
      setTimeout(() => { copiedId.value = null }, timeout)
    } catch {
      // ignore
    }
  }

  return {
    copiedId,
    copy,
  }
}
