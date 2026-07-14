import { ref } from 'vue'

/** 音频引擎 + RMS 唇同步 + 字幕淡出——useAvatarTTS / useAvatarChat 共享基础。 */
export interface AvatarAudioEngineOptions {
  syncLipParam: (value: number) => void
  onSpeakStart?: () => void
  onSpeakEnd?: () => void
}

// ── 共享常量 ──────────────────────────────────────────────
export const LUMINEST_SMOOTHING = 0.3
export const LUMINEST_SILENCE_THRESHOLD = 0.02
export const LUMINEST_RMS_EXPONENT = 1.5
export const LUMINEST_ANALYSER_FFT_SIZE = 256
export const LUMINEST_SUBTITLE_FADE_DELAY = 2000

export const useAvatarAudioEngine = (options: AvatarAudioEngineOptions) => {
  const isSpeaking = ref(false)
  const isSynthesizing = ref(false)
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

  // ── 清理 ──────────────────────────────────────────────
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

  const dismissSubtitle = () => {
    clearSubtitleFade()
    subtitleVisible.value = false
    subtitleText.value = ''
  }

  // ── RMS / 唇同步 ─────────────────────────────────────
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

  // ── 音频图创建（复用 AudioContext）─────────────────────
  const ensureAudioGraph = (): {
    context: AudioContext
    analyser: AnalyserNode
    source: MediaElementAudioSourceNode
    element: HTMLAudioElement
    url: string
  } | null => {
    if (!audioContext) {
      audioContext = new AudioContext()
      analyserNode = audioContext.createAnalyser()
      analyserNode.fftSize = LUMINEST_ANALYSER_FFT_SIZE
      analyserNode.smoothingTimeConstant = 0.4
    }
    return null // 由调用方创建 element 后再 connect
  }

  const connectElementThroughAnalyser = (element: HTMLAudioElement) => {
    if (!audioContext || !analyserNode) return
    sourceNode = audioContext.createMediaElementSource(element)
    sourceNode.connect(analyserNode)
    analyserNode.connect(audioContext.destination)
  }

  const onPlaybackStart = () => {
    isSpeaking.value = true
    options.onSpeakStart?.()
    if (analyserNode) {
      smoothedRms = 0
      startLipSyncLoop(analyserNode)
    }
  }

  const stopSpeaking = () => {
    if (currentAbortController) {
      currentAbortController.abort()
      currentAbortController = null
    }
    cleanupAudio()
    clearSubtitleFade()
    isSpeaking.value = false
    isSynthesizing.value = false
    options.syncLipParam(0)
    scheduleSubtitleFadeOut()
    options.onSpeakEnd?.()
  }

  const getAudioContext = (): AudioContext | null => audioContext
  const getAnalyserNode = (): AnalyserNode | null => analyserNode
  const getSmoothedRms = () => smoothedRms
  const setSmoothedRms = (v: number) => { smoothedRms = v }
  const setAudioElement = (el: HTMLAudioElement | null) => { audioElement = el }
  const getAudioElement = () => audioElement
  const setCurrentAudioUrl = (url: string | null) => { currentAudioUrl = url }
  const getCurrentAudioUrl = () => currentAudioUrl
  const setCurrentAbortController = (c: AbortController | null) => { currentAbortController = c }
  const getCurrentAbortController = () => currentAbortController

  return {
    // refs
    isSpeaking,
    isSynthesizing,
    subtitleText,
    subtitleVisible,
    // audio graph helpers
    ensureAudioGraph,
    connectElementThroughAnalyser,
    getAudioContext,
    getAnalyserNode,
    getSmoothedRms,
    setSmoothedRms,
    setAudioElement,
    getAudioElement,
    setCurrentAudioUrl,
    getCurrentAudioUrl,
    setCurrentAbortController,
    getCurrentAbortController,
    // playback
    onPlaybackStart,
    cleanupAudio,
    stopSpeaking,
    // subtitle
    clearSubtitleFade,
    scheduleSubtitleFadeOut,
    dismissSubtitle,
  }
}
