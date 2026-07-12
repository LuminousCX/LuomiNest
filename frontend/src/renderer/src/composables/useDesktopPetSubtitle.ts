/**
 * LuomiNest 桌面宠物字幕 composable
 *
 * 管理字幕文本的显示/隐藏/淡出计时。
 * 从 DesktopPetView.vue 拆分，逻辑原样保留。
 */
import { ref } from 'vue'

/** 字幕隐藏前的淡出延迟（ms），与原实现保持一致 */
const LUMINEST_PET_SUBTITLE_FADE_DELAY = 2000

export const useDesktopPetSubtitle = () => {
  const subtitleText = ref('')
  const subtitleVisible = ref(false)
  let subtitleFadeTimer: ReturnType<typeof setTimeout> | null = null

  const clearSubtitleFade = (): void => {
    if (subtitleFadeTimer !== null) {
      clearTimeout(subtitleFadeTimer)
      subtitleFadeTimer = null
    }
  }

  const showSubtitle = (text: string): void => {
    if (!text.trim()) return
    clearSubtitleFade()
    subtitleText.value = text.trim()
    subtitleVisible.value = true
  }

  const hideSubtitle = (): void => {
    clearSubtitleFade()
    subtitleFadeTimer = setTimeout(() => {
      subtitleVisible.value = false
      subtitleFadeTimer = null
    }, LUMINEST_PET_SUBTITLE_FADE_DELAY)
  }

  return {
    subtitleText,
    subtitleVisible,
    showSubtitle,
    hideSubtitle,
    clearSubtitleFade
  }
}
