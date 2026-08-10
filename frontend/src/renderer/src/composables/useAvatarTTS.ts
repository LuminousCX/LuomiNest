import { ref, onBeforeUnmount } from 'vue'
import { useModelStore } from '../stores/model'
import { API_ENDPOINTS } from '../config/api'
import { stripEmotionTags } from '../utils/emotionTagInterceptor'
import { createLuomiNestRendererLogger } from '../utils/logger'
import {
  LUOMINEST_DEFAULT_TTS_VOICE,
  LUOMINEST_SUBTITLE_CHAR_INTERVAL_MS,
  LUOMINEST_SUBTITLE_MIN_CHAR_INTERVAL_MS,
} from '../constants'
import {
  useAvatarAudioEngine,
} from './useAvatarAudioEngine'

const logger = createLuomiNestRendererLogger('AvatarTTS')

export interface AvatarTTSOptions {
  syncLipParam?: (value: number) => void
  onSpeakStart?: () => void
  onSpeakEnd?: () => void
}

export const useAvatarTTS = (options: AvatarTTSOptions = {}) => {
  const error = ref<string | null>(null)

  const noopLip = () => {}
  const engine = useAvatarAudioEngine({
    syncLipParam: options.syncLipParam ?? noopLip,
    onSpeakStart: options.onSpeakStart,
    onSpeakEnd: options.onSpeakEnd,
  })

  let subtitleCharTimer: ReturnType<typeof setInterval> | null = null

  const cleanupTimers = () => {
    if (subtitleCharTimer !== null) {
      clearInterval(subtitleCharTimer)
      subtitleCharTimer = null
    }
  }

  const animateSubtitleChars = (text: string) => {
    engine.subtitleText.value = ''
    engine.subtitleVisible.value = true
    if (subtitleCharTimer !== null) clearInterval(subtitleCharTimer)

    let charIndex = 0
    const interval = Math.max(
      LUOMINEST_SUBTITLE_MIN_CHAR_INTERVAL_MS,
      LUOMINEST_SUBTITLE_CHAR_INTERVAL_MS - text.length * 2
    )

    subtitleCharTimer = setInterval(() => {
      if (charIndex < text.length) {
        engine.subtitleText.value += text[charIndex]
        charIndex++
      } else {
        if (subtitleCharTimer !== null) {
          clearInterval(subtitleCharTimer)
          subtitleCharTimer = null
        }
      }
    }, interval)
  }

  const stopSpeaking = () => {
    cleanupTimers()
    engine.stopSpeaking()
  }

  const speak = async (text: string) => {
    const cleanedText = stripEmotionTags(text)
    if (!cleanedText.trim()) return

    stopSpeaking()

    const modelStore = useModelStore()
    const ttsConfig = modelStore.ttsConfig
    const voice = ttsConfig.voice || LUOMINEST_DEFAULT_TTS_VOICE

    const controller = new AbortController()
    engine.setCurrentAbortController(controller)
    engine.isSynthesizing.value = true
    error.value = null

    try {
      const token = await window.api.auth.getToken()
      const response = await fetch(API_ENDPOINTS.TTS_SYNTHESIZE, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ text: cleanedText.trim(), voice }),
        signal: controller.signal,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || `TTS request failed (${response.status})`)
      }

      const audioBlob = await response.blob()
      if (controller.signal.aborted) return

      engine.isSynthesizing.value = false

      const audioUrl = URL.createObjectURL(audioBlob)
      engine.setCurrentAudioUrl(audioUrl)

      engine.ensureAudioGraph()

      const audioElement = new Audio(audioUrl)
      audioElement.crossOrigin = 'anonymous'
      engine.setAudioElement(audioElement)

      engine.connectElementThroughAnalyser(audioElement)

      return new Promise<void>((resolve) => {
        if (!engine.getAudioElement()) { resolve(); return }

        audioElement.onplay = () => {
          engine.onPlaybackStart()
          animateSubtitleChars(cleanedText.trim())
        }

        audioElement.onended = () => {
          stopSpeaking()
          resolve()
        }

        audioElement.onerror = () => {
          stopSpeaking()
          resolve()
        }

        audioElement.play().catch((e) => {
          if (e.name !== 'AbortError') {
            logger.warn('Playback failed:', e)
          }
          stopSpeaking()
          resolve()
        })
      })
    } catch (e) {
      if (controller.signal.aborted || (e instanceof DOMException && e.name === 'AbortError')) {
        return
      }
      error.value = e instanceof Error ? e.message : 'TTS failed'
      logger.warn('TTS error:', e)
      engine.isSynthesizing.value = false
    } finally {
      if (engine.getCurrentAbortController() === controller) {
        engine.setCurrentAbortController(null)
      }
    }
  }

  const dismissSubtitle = () => {
    cleanupTimers()
    engine.dismissSubtitle()
  }

  onBeforeUnmount(() => {
    stopSpeaking()
    dismissSubtitle()
  })

  return {
    isSpeaking: engine.isSpeaking,
    isSynthesizing: engine.isSynthesizing,
    error,
    subtitleText: engine.subtitleText,
    subtitleVisible: engine.subtitleVisible,
    speak,
    stopSpeaking,
    dismissSubtitle,
  }
}
