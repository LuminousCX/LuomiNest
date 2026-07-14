/**
 * LuomiNest 全局 TTS 引擎 Store
 *
 * 从 useAvatarChat.ts 提取，作为全局单例 Pinia store：
 * - 音频引擎（AudioContext + AnalyserNode + RMS 唇同步）
 * - TTS 段队列（按句切分，每段携带 emotion 同步驱动 Live2D）
 * - 字幕显示与淡出
 *
 * 全局化的目的：桌宠模式下切换页面时 TTS 不中断（陪伴优先）。
 * 驱动回调（driveEmotion / syncLipParam）和配置（voice / engine / ttsConfig）
 * 由调用方动态设置，store 不感知具体 Live2D 实例或桌宠 IPC。
 *
 * 生命周期：
 * - stop() 由调用方按场景调用（普通模式切页时调用，桌宠模式不调用）
 * - feedChunk / finishStream 由 LLM 流式输出的 onChunk 回调驱动
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { API_ENDPOINTS } from '../config/api'
import { filterTtsText } from '../utils/ttsTextFilter'
import { interceptEmotionTags } from '../utils/emotionTagInterceptor'
import type { ChatStreamChunk } from '../types'
import { createLuomiNestRendererLogger } from '../utils/logger'
import {
  useAvatarAudioEngine,
} from '../composables/useAvatarAudioEngine'

const logger = createLuomiNestRendererLogger('TtsEngine')

// 句子切分常量（与原 useAvatarChat 一致）
const SENTENCE_ENDINGS = /[。！？.!?\n…]/
const SOFT_SPLIT = /[，,、；;]/
const MIN_SOFT_SPLIT_LENGTH = 12
const MAX_BUFFER_LENGTH = 80

export const useTtsEngineStore = defineStore('ttsEngine', () => {
  // ── 响应式状态（UI 绑定） ──────────────────────────────
  const isSpeaking = ref(false)
  const isSynthesizing = ref(false)
  const subtitleText = ref('')
  const subtitleVisible = ref(false)
  const currentEmotion = ref<string | null>(null)

  // ── 音频引擎（模块级单例，非响应式） ──────────────────
  const engine = useAvatarAudioEngine({
    syncLipParam: (value: number) => drivers.syncLipParam?.(value),
    onSpeakStart: undefined,
    onSpeakEnd: undefined,
  })

  // ── 驱动回调（由调用方设置） ──────────────────────────
  const drivers = {
    driveEmotion: null as ((emotionId: string) => void) | null,
    syncLipParam: null as ((value: number) => void) | null,
    onTtsError: null as ((err: Error) => void) | null,
  }

  // ── 配置回调（由调用方设置） ──────────────────────────
  const config = {
    voice: null as (() => string) | null,
    engine: null as (() => string) | null,
    ttsConfig: null as (() => { model?: string; speed?: number; apiKey?: string; baseUrl?: string }) | null,
    ttsEnabled: null as (() => boolean) | null,
    subtitleEnabled: null as (() => boolean) | null,
  }

  // ── TTS 队列与缓冲（模块级，非响应式） ────────────────
  let textBuffer = ''
  const ttsQueue: Array<{ text: string; emotion: string | null }> = []
  let isProcessingQueue = false
  let pendingEmotion: string | null = null
  let streamActive = false
  let lastTtsErrorTime = 0
  let ttsUnavailable = false

  // ── 设置驱动回调 ──────────────────────────────────────
  const setDrivers = (opts: {
    driveEmotion?: (emotionId: string) => void
    syncLipParam?: (value: number) => void
    onTtsError?: (err: Error) => void
  }): void => {
    if (opts.driveEmotion !== undefined) drivers.driveEmotion = opts.driveEmotion
    if (opts.syncLipParam !== undefined) drivers.syncLipParam = opts.syncLipParam
    if (opts.onTtsError !== undefined) drivers.onTtsError = opts.onTtsError
  }

  // ── 设置配置回调 ──────────────────────────────────────
  const setConfig = (opts: {
    voice?: () => string
    engine?: () => string
    ttsConfig?: () => { model?: string; speed?: number; apiKey?: string; baseUrl?: string }
    ttsEnabled?: () => boolean
    subtitleEnabled?: () => boolean
  }): void => {
    if (opts.voice !== undefined) config.voice = opts.voice
    if (opts.engine !== undefined) config.engine = opts.engine
    if (opts.ttsConfig !== undefined) config.ttsConfig = opts.ttsConfig
    if (opts.ttsEnabled !== undefined) config.ttsEnabled = opts.ttsEnabled
    if (opts.subtitleEnabled !== undefined) config.subtitleEnabled = opts.subtitleEnabled
  }

  // ── 句子切分 ──────────────────────────────────────────
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
      if (textBuffer.length >= MAX_BUFFER_LENGTH) {
        const softMatch = textBuffer.match(SOFT_SPLIT)
        if (softMatch && softMatch.index !== undefined && softMatch.index >= MIN_SOFT_SPLIT_LENGTH) {
          const end = softMatch.index + softMatch[0].length
          const segment = textBuffer.slice(0, end).trim()
          if (segment) segments.push({ text: segment, emotion: pendingEmotion })
          textBuffer = textBuffer.slice(end)
          continue
        }
        const segment = textBuffer.trim()
        if (segment) segments.push({ text: segment, emotion: pendingEmotion })
        textBuffer = ''
        break
      }
      break
    }
    return segments
  }

  // ── 播放单段 TTS ──────────────────────────────────────
  const playSegment = async (segment: { text: string; emotion: string | null }): Promise<void> => {
    const { text, emotion } = segment
    if (!text.trim()) return
    if (!config.ttsEnabled || !config.ttsEnabled()) return
    if (ttsUnavailable) return

    // 同步驱动 Live2D 表情：在播放该段 TTS 前切换到对应表情
    if (emotion && emotion !== currentEmotion.value) {
      currentEmotion.value = emotion
      drivers.driveEmotion?.(emotion)
    }

    const controller = new AbortController()
    engine.setCurrentAbortController(controller)
    engine.isSynthesizing.value = true

    try {
      const cfg = config.ttsConfig ? config.ttsConfig() : {}
      const token = await window.api.auth.getToken()
      const response = await fetch(`${API_ENDPOINTS.V1}/chat/tts/synthesize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          text: text.trim(),
          voice: config.voice ? config.voice() : 'zh-CN-XiaoxiaoNeural',
          engine: config.engine ? config.engine() : 'auto',
          model: cfg.model || '',
          speed: cfg.speed ?? 1.0,
          apiKey: cfg.apiKey || '',
          baseUrl: cfg.baseUrl || '',
        }),
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

      engine.isSynthesizing.value = false
      engine.ensureAudioGraph()

      const audioUrl = URL.createObjectURL(audioBlob)
      engine.setCurrentAudioUrl(audioUrl)

      const audioElement = new Audio(audioUrl)
      audioElement.crossOrigin = 'anonymous'
      engine.setAudioElement(audioElement)
      engine.connectElementThroughAnalyser(audioElement)

      if (config.subtitleEnabled && config.subtitleEnabled()) {
        engine.subtitleText.value = text.trim()
        engine.subtitleVisible.value = true
        engine.clearSubtitleFade()
      }

      return new Promise<void>((resolve) => {
        if (!engine.getAudioElement()) { resolve(); return }

        audioElement.onplay = () => {
          engine.onPlaybackStart()
        }

        audioElement.onended = () => {
          engine.cleanupAudio()
          resolve()
        }

        audioElement.onerror = () => {
          engine.cleanupAudio()
          resolve()
        }

        audioElement.play().catch((e) => {
          if (e.name !== 'AbortError') {
            logger.warn('Playback failed:', e)
          }
          engine.cleanupAudio()
          resolve()
        })
      })
    } catch (e) {
      if (controller.signal.aborted || (e instanceof DOMException && e.name === 'AbortError')) {
        return
      }
      logger.warn('TTS error:', e)
      engine.isSynthesizing.value = false
      const errMsg = e instanceof Error ? e.message : String(e)
      if (errMsg.includes('503') || errMsg.includes('未安装') || errMsg.includes('not installed') || errMsg.includes('Service Unavailable')) {
        ttsUnavailable = true
        ttsQueue.length = 0
        textBuffer = ''
        streamActive = false
        logger.warn('TTS 引擎不可用，已停止后续 TTS 请求')
      }
      const now = Date.now()
      if (drivers.onTtsError && now - lastTtsErrorTime > 5000) {
        lastTtsErrorTime = now
        drivers.onTtsError(e instanceof Error ? e : new Error(String(e)))
      }
    } finally {
      if (engine.getCurrentAbortController() === controller) {
        engine.setCurrentAbortController(null)
      }
    }
  }

  // ── 对话结束后回归正常表情 ────────────────────────────
  const resetEmotionToNeutral = (): void => {
    if (currentEmotion.value !== 'idle') {
      currentEmotion.value = 'idle'
      drivers.driveEmotion?.('idle')
    }
  }

  // ── 队列处理 ──────────────────────────────────────────
  const processQueue = async (): Promise<void> => {
    if (isProcessingQueue) return
    isProcessingQueue = true

    while (ttsQueue.length > 0) {
      const segment = ttsQueue.shift()!
      await playSegment(segment)
      if (!streamActive && ttsQueue.length === 0) break
    }

    isProcessingQueue = false
    engine.isSpeaking.value = false
    drivers.syncLipParam?.(0)
    if (!streamActive) {
      resetEmotionToNeutral()
    }
    if (config.subtitleEnabled && config.subtitleEnabled()) {
      engine.scheduleSubtitleFadeOut()
    }
  }

  // ── Feed 流式 chunk ───────────────────────────────────
  const feedChunk = (chunk: ChatStreamChunk): void => {
    streamActive = true

    if (ttsUnavailable) {
      if (chunk.emotion) {
        pendingEmotion = chunk.emotion
      }
      return
    }

    if (chunk.emotion) {
      pendingEmotion = chunk.emotion
    }

    if (chunk.content) {
      const { cleanText, emotion: interceptedEmotion } = interceptEmotionTags(chunk.content)
      if (interceptedEmotion) {
        pendingEmotion = interceptedEmotion
      }
      if (!cleanText) return
      textBuffer += cleanText
      const segments = extractSegments()
      for (const seg of segments) {
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

  // ── Flush 剩余缓冲 ────────────────────────────────────
  const finishStream = (): void => {
    streamActive = false
    if (ttsUnavailable) {
      engine.isSpeaking.value = false
      drivers.syncLipParam?.(0)
      resetEmotionToNeutral()
      return
    }
    if (textBuffer.trim()) {
      const filtered = filterTtsText(textBuffer.trim())
      if (filtered) {
        ttsQueue.push({ text: filtered, emotion: pendingEmotion })
      }
      textBuffer = ''
    }
    if (ttsQueue.length > 0 && !isProcessingQueue) {
      processQueue()
    } else if (!isProcessingQueue) {
      engine.isSpeaking.value = false
      drivers.syncLipParam?.(0)
      resetEmotionToNeutral()
      if (config.subtitleEnabled && config.subtitleEnabled()) {
        engine.scheduleSubtitleFadeOut()
      }
    }
  }

  // ── 停止所有播放 ──────────────────────────────────────
  const stop = (): void => {
    streamActive = false
    ttsQueue.length = 0
    textBuffer = ''
    pendingEmotion = null
    engine.stopSpeaking()
    isProcessingQueue = false
    engine.subtitleVisible.value = false
    engine.subtitleText.value = ''
  }

  // ── 关闭字幕 ──────────────────────────────────────────
  const dismissSubtitle = (): void => {
    engine.dismissSubtitle()
  }

  return {
    // 响应式状态
    isSpeaking,
    isSynthesizing,
    subtitleText,
    subtitleVisible,
    currentEmotion,
    // 配置
    setDrivers,
    setConfig,
    // TTS 操作
    feedChunk,
    finishStream,
    stop,
    dismissSubtitle,
  }
})
