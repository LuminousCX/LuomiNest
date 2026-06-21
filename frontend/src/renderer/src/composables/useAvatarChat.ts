import { ref, onBeforeUnmount } from 'vue'
import { API_ENDPOINTS } from '../config/api'
import { filterTtsText } from '../utils/ttsTextFilter'
import { interceptEmotionTags } from '../utils/emotionTagInterceptor'
import type { ChatStreamChunk } from '../types'

export interface AvatarChatOptions {
  /** Voice identifier passed to the TTS backend (e.g. 'zh-CN-XiaoxiaoNeural'). */
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
  // TTS 段队列：每段携带对应的 emotion，播放时才驱动 Live2D
  const ttsQueue: Array<{ text: string; emotion: string | null }> = []
  let isProcessingQueue = false
  // 暂存最近接收到的 emotion，等待下一段 TTS 文本提取时附加
  let pendingEmotion: string | null = null

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

  /** Extract complete sentences from the buffer, leaving any trailing partial.
   *  每段附加当前的 pendingEmotion，用于播放时同步驱动 Live2D 表情。 */
  const extractSegments = (): Array<{ text: string; emotion: string | null }> => {
    const segments: Array<{ text: string; emotion: string | null }> = []
    while (textBuffer.length > 0) {
      const match = textBuffer.match(SENTENCE_ENDINGS)
      if (match && match.index !== undefined) {
        const end = match.index + match[0].length
        const segment = textBuffer.slice(0, end).trim()
        if (segment) segments.push({ text: segment, emotion: pendingEmotion })
        textBuffer = textBuffer.slice(end)
        continue
      }
      // No hard ending. Try soft split if buffer is long enough.
      if (textBuffer.length >= MAX_BUFFER_LENGTH) {
        const softMatch = textBuffer.match(SOFT_SPLIT)
        if (softMatch && softMatch.index !== undefined && softMatch.index >= MIN_SOFT_SPLIT_LENGTH) {
          const end = softMatch.index + softMatch[0].length
          const segment = textBuffer.slice(0, end).trim()
          if (segment) segments.push({ text: segment, emotion: pendingEmotion })
          textBuffer = textBuffer.slice(end)
          continue
        }
        // Force flush if buffer is too long without any split point.
        const segment = textBuffer.trim()
        if (segment) segments.push({ text: segment, emotion: pendingEmotion })
        textBuffer = ''
        break
      }
      break
    }
    return segments
  }

  const playSegment = async (segment: { text: string; emotion: string | null }): Promise<void> => {
    const { text, emotion } = segment
    if (!text.trim() || !options.ttsEnabled()) return

    // 同步驱动 Live2D 表情：在播放该段 TTS 前切换到对应表情
    if (emotion && emotion !== currentEmotion.value) {
      currentEmotion.value = emotion
      options.driveEmotion(emotion)
    }

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

  /** 对话结束后回归正常表情（neutral） */
  const resetEmotionToNeutral = () => {
    if (currentEmotion.value !== 'idle') {
      currentEmotion.value = 'idle'
      options.driveEmotion('idle')
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
    // 流已结束，回归正常表情
    if (!streamActive) {
      resetEmotionToNeutral()
    }
    if (options.subtitleEnabled()) {
      scheduleSubtitleFadeOut()
    }
    options.onSpeakEnd?.()
  }

  /** Feed a stream chunk. Drives expression and queues TTS segments.
   *  emotion 不立即驱动 Live2D，而是暂存为 pendingEmotion，
   *  等待对应 TTS 段播放时才同步切换表情。 */
  const feedChunk = (chunk: ChatStreamChunk) => {
    streamActive = true

    // 侦听器：暂存后端解析的 chunk.emotion，等待下一段 TTS 文本提取时附加
    if (chunk.emotion) {
      pendingEmotion = chunk.emotion
    }

    if (chunk.content) {
      // 拦截器：主动扫描 content 中的 <exp:xxx> 标签（兜底）
      // 如果后端 EmotionStreamParser 漏解析了标签变体，此处兜底提取表情
      const { cleanText, emotion: interceptedEmotion } = interceptEmotionTags(chunk.content)
      if (interceptedEmotion) {
        pendingEmotion = interceptedEmotion
      }
      if (!cleanText) return
      textBuffer += cleanText
      const segments = extractSegments()
      for (const seg of segments) {
        // 过滤 markdown/emoji/特殊符号，只保留适合朗读的纯文本
        const filtered = filterTtsText(seg.text)
        if (filtered) {
          ttsQueue.push({ text: filtered, emotion: seg.emotion })
        }
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
      // 推入队列前必须过滤，防止纯标签/符号文本导致后端 400
      const filtered = filterTtsText(textBuffer.trim())
      if (filtered) {
        ttsQueue.push({ text: filtered, emotion: pendingEmotion })
      }
      textBuffer = ''
    }
    if (ttsQueue.length > 0 && !isProcessingQueue) {
      processQueue()
    } else if (!isProcessingQueue) {
      // 队列为空且无正在处理的播放，直接结束并回归正常表情
      isSpeaking.value = false
      options.syncLipParam(0)
      resetEmotionToNeutral()
      if (options.subtitleEnabled()) {
        scheduleSubtitleFadeOut()
      }
      options.onSpeakEnd?.()
    }
  }

  /** Stop all playback and clear queues. */
  const stop = () => {
    streamActive = false
    ttsQueue.length = 0
    textBuffer = ''
    pendingEmotion = null
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
