import { ref, onBeforeUnmount } from 'vue'
import { useModelStore } from '../stores/model'
import { API_ENDPOINTS } from '../config/api'
import { stripEmotionTags } from '../utils/emotionTagInterceptor'

export interface AvatarTTSOptions {
  syncLipParam?: (value: number) => void
  onSpeakStart?: () => void
  onSpeakEnd?: () => void
}

const LUMINEST_SMOOTHING = 0.3
const LUMINEST_SILENCE_THRESHOLD = 0.02
const LUMINEST_RMS_EXPONENT = 1.5
const LUMINEST_ANALYSER_FFT_SIZE = 256
const LUMINEST_SUBTITLE_FADE_DELAY = 2000
const LUMINEST_SUBTITLE_CHAR_INTERVAL = 60

export const useAvatarTTS = (options: AvatarTTSOptions = {}) => {
  const isSpeaking = ref(false)
  const isSynthesizing = ref(false)
  const error = ref<string | null>(null)
  const subtitleText = ref('')
  const subtitleVisible = ref(false)

  let audioContext: AudioContext | null = null
  let analyserNode: AnalyserNode | null = null
  let sourceNode: MediaElementAudioSourceNode | null = null
  let audioElement: HTMLAudioElement | null = null
  let animFrameId: number | null = null
  let currentAbortController: AbortController | null = null
  let currentAudioUrl: string | null = null
  let smoothedRms = 0
  let subtitleFadeTimer: ReturnType<typeof setTimeout> | null = null
  let subtitleCharTimer: ReturnType<typeof setInterval> | null = null

  const cleanupTimers = () => {
    if (subtitleFadeTimer !== null) {
      clearTimeout(subtitleFadeTimer)
      subtitleFadeTimer = null
    }
    if (subtitleCharTimer !== null) {
      clearInterval(subtitleCharTimer)
      subtitleCharTimer = null
    }
  }

  const cleanupAudio = () => {
    if (animFrameId !== null) {
      cancelAnimationFrame(animFrameId)
      animFrameId = null
    }
    if (audioElement) {
      audioElement.pause()
      audioElement.removeAttribute('src')
      audioElement.load()
      audioElement = null
    }
    if (sourceNode) {
      try { sourceNode.disconnect() } catch { /* ignored */ }
      sourceNode = null
    }
    if (analyserNode) {
      try { analyserNode.disconnect() } catch { /* ignored */ }
      analyserNode = null
    }
    if (audioContext && audioContext.state !== 'closed') {
      audioContext.close().catch(() => { /* ignored */ })
      audioContext = null
    }
    if (currentAudioUrl) {
      URL.revokeObjectURL(currentAudioUrl)
      currentAudioUrl = null
    }
    smoothedRms = 0
  }

  const scheduleSubtitleFadeOut = () => {
    if (subtitleFadeTimer !== null) clearTimeout(subtitleFadeTimer)
    subtitleFadeTimer = setTimeout(() => {
      subtitleVisible.value = false
      subtitleFadeTimer = null
    }, LUMINEST_SUBTITLE_FADE_DELAY)
  }

  const animateSubtitleChars = (text: string) => {
    subtitleText.value = ''
    subtitleVisible.value = true
    if (subtitleCharTimer !== null) clearInterval(subtitleCharTimer)

    let charIndex = 0
    const interval = Math.max(30, LUMINEST_SUBTITLE_CHAR_INTERVAL - text.length * 2)

    subtitleCharTimer = setInterval(() => {
      if (charIndex < text.length) {
        subtitleText.value += text[charIndex]
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
    if (currentAbortController) {
      currentAbortController.abort()
      currentAbortController = null
    }
    cleanupAudio()
    cleanupTimers()
    isSpeaking.value = false
    isSynthesizing.value = false
    options.syncLipParam?.(0)
    scheduleSubtitleFadeOut()
    options.onSpeakEnd?.()
  }

  const computeRmsFromAnalyser = (analyser: AnalyserNode): number => {
    const dataArray = new Uint8Array(analyser.frequencyBinCount)
    analyser.getByteFrequencyData(dataArray)

    let sum = 0
    for (let i = 0; i < dataArray.length; i++) {
      const normalized = dataArray[i] / 255
      sum += normalized * normalized
    }
    const rms = Math.sqrt(sum / dataArray.length)
    const shaped = Math.pow(rms, LUMINEST_RMS_EXPONENT)

    smoothedRms = smoothedRms * (1 - LUMINEST_SMOOTHING) + shaped * LUMINEST_SMOOTHING
    return smoothedRms < LUMINEST_SILENCE_THRESHOLD ? 0 : Math.min(1, smoothedRms * 2.5)
  }

  const startLipSyncLoop = (analyser: AnalyserNode) => {
    const tick = () => {
      const mouthValue = computeRmsFromAnalyser(analyser)
      options.syncLipParam?.(mouthValue)
      animFrameId = requestAnimationFrame(tick)
    }
    animFrameId = requestAnimationFrame(tick)
  }

  const speak = async (text: string) => {
    // 拦截器：剥离 <exp:xxx> 表情标签，防止标签被 TTS 朗读
    const cleanedText = stripEmotionTags(text)
    if (!cleanedText.trim()) return

    stopSpeaking()

    const modelStore = useModelStore()
    const ttsConfig = modelStore.ttsConfig
    const voice = ttsConfig.voice || 'zh-CN-XiaoxiaoNeural'

    const controller = new AbortController()
    currentAbortController = controller
    isSynthesizing.value = true
    error.value = null

    try {
      const response = await fetch(`${API_ENDPOINTS.V1}/chat/tts/synthesize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: cleanedText.trim(), voice }),
        signal: controller.signal,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || `TTS request failed (${response.status})`)
      }

      const audioBlob = await response.blob()
      if (controller.signal.aborted) return

      isSynthesizing.value = false

      const audioUrl = URL.createObjectURL(audioBlob)
      currentAudioUrl = audioUrl

      audioContext = new AudioContext()
      analyserNode = audioContext.createAnalyser()
      analyserNode.fftSize = LUMINEST_ANALYSER_FFT_SIZE
      analyserNode.smoothingTimeConstant = 0.4

      audioElement = new Audio(audioUrl)
      audioElement.crossOrigin = 'anonymous'

      sourceNode = audioContext.createMediaElementSource(audioElement)
      sourceNode.connect(analyserNode)
      analyserNode.connect(audioContext.destination)

      return new Promise<void>((resolve) => {
        if (!audioElement) { resolve(); return }

        audioElement.onplay = () => {
          isSpeaking.value = true
          animateSubtitleChars(cleanedText.trim())
          options.onSpeakStart?.()
          if (analyserNode) {
            smoothedRms = 0
            startLipSyncLoop(analyserNode)
          }
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
            console.warn('[LuomiNest AvatarTTS] Playback failed:', e)
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
      console.warn('[LuomiNest AvatarTTS] TTS error:', e)
      isSynthesizing.value = false
    } finally {
      if (currentAbortController === controller) {
        currentAbortController = null
      }
    }
  }

  const dismissSubtitle = () => {
    cleanupTimers()
    subtitleVisible.value = false
    subtitleText.value = ''
  }

  onBeforeUnmount(() => {
    stopSpeaking()
    dismissSubtitle()
  })

  return {
    isSpeaking,
    isSynthesizing,
    error,
    subtitleText,
    subtitleVisible,
    speak,
    stopSpeaking,
    dismissSubtitle,
  }
}
