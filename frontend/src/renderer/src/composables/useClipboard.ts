import { ref } from 'vue'
import { copyToClipboard } from '../utils/clipboard'

export function useClipboard(timeout = 2000) {
  const copiedId = ref<string | null>(null)
  // 设备码/链接等"是否已复制"布尔态（StepLogin / SettingsCloudSection 收口）
  const copied = ref(false)
  let copiedTimer: ReturnType<typeof setTimeout> | null = null

  const copy = async (id: string, text: string) => {
    try {
      await copyToClipboard(text)
      copiedId.value = id
      setTimeout(() => { copiedId.value = null }, timeout)
    } catch {
      // ignore
    }
  }

  /** 复制文本并维护 copied 态（timeout 后复位），返回是否成功 */
  const copyText = async (text: string): Promise<boolean> => {
    try {
      await copyToClipboard(text)
      copied.value = true
      if (copiedTimer) clearTimeout(copiedTimer)
      copiedTimer = setTimeout(() => { copied.value = false }, timeout)
      return true
    } catch {
      return false
    }
  }

  /** 取消挂起的复位定时器（onUnmounted 时调用） */
  const dispose = (): void => {
    if (copiedTimer) {
      clearTimeout(copiedTimer)
      copiedTimer = null
    }
    copied.value = false
  }

  return {
    copiedId,
    copied,
    copy,
    copyText,
    dispose,
  }
}
