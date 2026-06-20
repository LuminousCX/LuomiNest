import { ref, onBeforeUnmount } from 'vue'
import { API_ENDPOINTS } from '../config/api'
import type { ChatStreamChunk } from '../types'

export interface AvatarChatOptions {
  /** Voice identifier passed to the TTS backend (e.g. 'ja-JP-NanamiNeural'). */
  voice: () => string
  /** Drive avatar expression by semantic emotion id (e.g. 'happy'). */
  driveEmotion: (emotionId: string) => void
  /** Drive avatar lip sync by RMS amplitude [0,1]. */
  syncLipParam: (value: number) => void
  /** Called when the first audio segment starts playing. */
  onSpeakStart?: () => void
  /** Called when all queued audio has finished. */
  onSpeakEnd?: () => void
  /** Called when TTS synthesis or playback fails (for user-facing notifications). */
  onTtsError?: (err: Error) => void
  /** Master toggle for TTS playback. */
  ttsEnabled: () => boolean
  /** Master toggle for subtitle display. */
  subtitleEnabled: () => boolean
}

// Sentence-ending characters that trigger a TTS segment flush.
const SENTENCE_ENDINGS = /[。！？.!?\n…]/
// Soft split points (commas) used when a sentence is long.
const SOFT_SPLIT = /[，,、；;]/
// Minimum chars before a soft split is considered.
const MIN_SOFT_SPLIT_LENGTH = 12
// Maximum chars to buffer before forcing a flush.
const MAX_BUFFER_LENGTH = 80

// 防御性正则：匹配 <exp:NAME> 及其各种变体（空格、自闭合等），
// 防止 LLM 输出的非标准格式标签泄漏到 TTS 朗读中
const EMOTION_TAG_RE = /<\s*exp:\s*[a-zA-Z]+\s*\/?\s*>/g

const LUMINEST_SMOOTHING = 0.3
const LUMINEST_SILENCE_THRESHOLD = 0.02
const LUMINEST_RMS_EXPONENT = 1.5
const LUMINEST_ANALYSER_FFT_SIZE = 256
const LUMINEST_SUBTITLE_FADE_DELAY = 2000

export const useAvatarChat = (options: AvatarChatOptions) => {
  const isSpeaking = ref(false)
  const isSynthesizing = ref(false)
  const subtitleText = ref('')
  const subtitleVisible = ref(false)
  const currentEmotion = ref<string | null>(null)

  let textBuffer = ''
  const ttsQueue: string[] = []
  let isProcessingQueue = false

  let audioContext: AudioContext | null = null
  let analyserNode: AnalyserNode | null = null
  let sourceNode: MediaElementAudioSourceNode | null = null
  let audioElement: HTMLAudioElement | null = null
  let animFrameId: number | null = null
  let currentAbortController: AbortController | null = null
  let currentAudioUrl: string | null = null
  let smoothedRms = 0
  let subtitleFadeTimer: ReturnType<typeof setTimeout> | null = null
  let streamActive = false
  let lastTtsErrorTime = 0

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

  const clearSubtitleFade = () => {
    if (subtitleFadeTimer !== null) {
      clearTimeout(subtitleFadeTimer)
      subtitleFadeTimer = null
    }
  }

  const scheduleSubtitleFadeOut = () => {
    clearSubtitleFade()
    subtitleFadeTimer = setTimeout(() => {
      subtitleVisible.value = false
      subtitleFadeTimer = null
    }, LUMINEST_SUBTITLE_FADE_DELAY)
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
      options.syncLipParam(mouthValue)
      animFrameId = requestAnimationFrame(tick)
    }
    animFrameId = requestAnimationFrame(tick)
  }

  /** Extract complete sentences from the buffer, leaving any trailing partial. */
  const extractSegments = (): string[] => {
    const segments: string[] = []
    while (textBuffer.length > 0) {
      const match = textBuffer.match(SENTENCE_ENDINGS)
      if (match && match.index !== undefined) {
        const end = match.index + match[0].length
        const segment = textBuffer.slice(0, end).trim()
        if (segment) segments.push(segment)
        textBuffer = textBuffer.slice(end)
        continue
      }
      // No hard ending. Try soft split if buffer is long enough.
      if (textBuffer.length >= MAX_BUFFER_LENGTH) {
        const softMatch = textBuffer.match(SOFT_SPLIT)
        if (softMatch && softMatch.index !== undefined && softMatch.index >= MIN_SOFT_SPLIT_LENGTH) {
          const end = softMatch.index + softMatch[0].length
          const segment = textBuffer.slice(0, end).trim()
          if (segment) segments.push(segment)
          textBuffer = textBuffer.slice(end)
          continue
        }
        // Force flush if buffer is too long without any split point.
        const segment = textBuffer.trim()
        if (segment) segments.push(segment)
        textBuffer = ''
        break
      }
      break
    }
    return segments
  }

  const playSegment = async (text: string): Promise<void> => {
    if (!text.trim() || !options.ttsEnabled()) return

    const controller = new AbortController()
    currentAbortController = controller
    isSynthesizing.value = true

    try {
      const response = await fetch(`${API_ENDPOINTS.V1}/chat/tts/synthesize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text.trim(), voice: options.voice() }),
        signal: controller.signal,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        const ttsErr = typeof errorData?.error === 'string'
          ? errorData.error
          : errorData?.error?.message || errorData?.detail || `语音合成请求失败 (${response.status})`
        throw new Error(ttsErr)
      }

      const audioBlob = await response.blob()
      if (controller.signal.aborted) return

      isSynthesizing.value = false

      // Reuse AudioContext across segments for smoother playback.
      if (!audioContext) {
        audioContext = new AudioContext()
        analyserNode = audioContext.createAnalyser()
        analyserNode.fftSize = LUMINEST_ANALYSER_FFT_SIZE
        analyserNode.smoothingTimeConstant = 0.4
      }

      const audioUrl = URL.createObjectURL(audioBlob)
      currentAudioUrl = audioUrl

      audioElement = new Audio(audioUrl)
      audioElement.crossOrigin = 'anonymous'

      // Connect through analyser for lip sync.
      sourceNode = audioContext.createMediaElementSource(audioElement)
      if (analyserNode) {
        sourceNode.connect(analyserNode)
        analyserNode.connect(audioContext.destination)
      } else {
        sourceNode.connect(audioContext.destination)
      }

      if (options.subtitleEnabled()) {
        subtitleText.value = text.trim()
        subtitleVisible.value = true
        clearSubtitleFade()
      }

      return new Promise<void>((resolve) => {
        if (!audioElement) { resolve(); return }

        audioElement.onplay = () => {
          isSpeaking.value = true
          options.onSpeakStart?.()
          if (analyserNode) {
            smoothedRms = 0
            startLipSyncLoop(analyserNode)
          }
        }

        audioElement.onended = () => {
          cleanupAudio()
          resolve()
        }

        audioElement.onerror = () => {
          cleanupAudio()
          resolve()
        }

        audioElement.play().catch((e) => {
          if (e.name !== 'AbortError') {
            console.warn('[LuomiNest AvatarChat] Playback failed:', e)
          }
          cleanupAudio()
          resolve()
        })
      })
    } catch (e) {
      if (controller.signal.aborted || (e instanceof DOMException && e.name === 'AbortError')) {
        return
      }
      console.warn('[LuomiNest AvatarChat] TTS error:', e)
      isSynthesizing.value = false
      // 节流：5 秒内只通知一次，避免每个分段都弹 toast
      const now = Date.now()
      if (options.onTtsError && now - lastTtsErrorTime > 5000) {
        lastTtsErrorTime = now
        options.onTtsError(e instanceof Error ? e : new Error(String(e)))
      }
    } finally {
      if (currentAbortController === controller) {
        currentAbortController = null
      }
    }
  }

  const processQueue = async () => {
    if (isProcessingQueue) return
    isProcessingQueue = true

    while (ttsQueue.length > 0) {
      const segment = ttsQueue.shift()!
      await playSegment(segment)
      if (!streamActive && ttsQueue.length === 0) break
    }

    isProcessingQueue = false
    isSpeaking.value = false
    options.syncLipParam(0)
    if (options.subtitleEnabled()) {
      scheduleSubtitleFadeOut()
    }
    options.onSpeakEnd?.()
  }

  /** Feed a stream chunk. Drives expression and queues TTS segments. */
  const feedChunk = (chunk: ChatStreamChunk) => {
    streamActive = true

    if (chunk.emotion) {
      currentEmotion.value = chunk.emotion
      options.driveEmotion(chunk.emotion)
    }

    if (chunk.content) {
      // 防御性过滤：剥离可能残留的 <exp:...> 标签，防止 TTS 朗读
      const cleanContent = chunk.content.replace(EMOTION_TAG_RE, '')
      if (!cleanContent) return
      textBuffer += cleanContent
      const segments = extractSegments()
      for (const seg of segments) {
        ttsQueue.push(seg)
      }
      if (ttsQueue.length > 0 && !isProcessingQueue) {
        processQueue()
      }
    }
  }

  /** Flush any remaining buffered text and mark stream as done. */
  const finishStream = () => {
    streamActive = false
    if (textBuffer.trim()) {
      ttsQueue.push(textBuffer.trim())
      textBuffer = ''
    }
    if (ttsQueue.length > 0 && !isProcessingQueue) {
      processQueue()
    }
  }

  /** Stop all playback and clear queues. */
  const stop = () => {
    streamActive = false
    ttsQueue.length = 0
    textBuffer = ''
    if (currentAbortController) {
      currentAbortController.abort()
      currentAbortController = null
    }
    cleanupAudio()
    clearSubtitleFade()
    isSpeaking.value = false
    isSynthesizing.value = false
    isProcessingQueue = false
    options.syncLipParam(0)
    subtitleVisible.value = false
    subtitleText.value = ''
  }

  const dismissSubtitle = () => {
    clearSubtitleFade()
    subtitleVisible.value = false
    subtitleText.value = ''
  }

  onBeforeUnmount(() => {
    stop()
  })

  return {
    isSpeaking,
    isSynthesizing,
    subtitleText,
    subtitleVisible,
    currentEmotion,
    feedChunk,
    finishStream,
    stop,
    dismissSubtitle,
  }
}
