import { ref } from 'vue'
import { useModelStore } from '../stores/model'
import { API_ENDPOINTS } from '../config/api'

const isSpeaking = ref(false)
const speakingMessageId = ref<string | null>(null)
let currentAudio: HTMLAudioElement | null = null
let currentAudioUrl: string | null = null
let currentAbortController: AbortController | null = null

function revokeCurrentAudioUrl() {
  if (currentAudioUrl) {
    URL.revokeObjectURL(currentAudioUrl)
    currentAudioUrl = null
  }
}

function cleanTextForTTS(text: string): string {
  return text
    // 表情标签 <exp:xxx> → 删除（必须在最前面，防止标签被朗读）
    .replace(/<\s*exp[:=]\s*[a-zA-Z]+\s*\/?\s*>/g, '')
    .replace(/```[\s\S]*?```/g, '，代码块，')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/#{1,6}\s/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/[-*+]\s/g, '')
    .replace(/\n{2,}/g, '。')
    .replace(/\n/g, '，')
    .replace(/\s+/g, ' ')
    .trim()
}

function speakWithWebAPI(text: string, messageId: string): boolean {
  if (!window.speechSynthesis) return false

  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = 1.0

  utterance.onstart = () => {
    isSpeaking.value = true
    speakingMessageId.value = messageId
  }
  utterance.onend = () => stopSpeaking()
  utterance.onerror = () => stopSpeaking()

  window.speechSynthesis.speak(utterance)
  return true
}

async function speakWithEdgeTTS(text: string, messageId: string): Promise<boolean> {
  const modelStore = useModelStore()
  const ttsConfig = modelStore.ttsConfig
  const voice = ttsConfig.voice || 'zh-CN-XiaoxiaoNeural'

  if (currentAbortController) {
    currentAbortController.abort()
  }
  const controller = new AbortController()
  currentAbortController = controller
  const timeoutId = setTimeout(() => controller.abort(), 30000)

  try {
    const response = await fetch(`${API_ENDPOINTS.V1}/chat/tts/synthesize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice }),
      signal: controller.signal,
    })

    if (!response.ok) throw new Error('TTS request failed')

    const audioBlob = await response.blob()
    clearTimeout(timeoutId)

    revokeCurrentAudioUrl()
    const audioUrl = URL.createObjectURL(audioBlob)
    currentAudioUrl = audioUrl

    currentAudio = new Audio(audioUrl)
    currentAudio.onplay = () => {
      isSpeaking.value = true
      speakingMessageId.value = messageId
    }
    currentAudio.onended = () => stopSpeaking()
    currentAudio.onerror = () => stopSpeaking()
    await currentAudio.play()
    return true
  } catch (e) {
    clearTimeout(timeoutId)
    if (controller.signal.aborted || (e instanceof DOMException && e.name === 'AbortError')) {
      console.warn('[TTS] Edge TTS request aborted')
    } else {
      console.warn('[TTS] Edge TTS failed, falling back to Web Speech API:', e)
    }
    return false
  } finally {
    if (currentAbortController === controller) {
      currentAbortController = null
    }
  }
}

async function speak(rawText: string, messageId: string) {
  if (speakingMessageId.value === messageId && isSpeaking.value) {
    stopSpeaking()
    return
  }

  stopSpeaking()

  const text = cleanTextForTTS(rawText)
  if (!text) return

  const modelStore = useModelStore()
  const ttsConfig = modelStore.ttsConfig

  if (ttsConfig.provider) {
    const success = await speakWithEdgeTTS(text, messageId)
    if (success) return
  }

  speakWithWebAPI(text, messageId)
}

function stopSpeaking() {
  if (currentAbortController) {
    currentAbortController.abort()
    currentAbortController = null
  }
  if (currentAudio) {
    currentAudio.pause()
    currentAudio.currentTime = 0
    currentAudio = null
  }
  revokeCurrentAudioUrl()
  window.speechSynthesis?.cancel()
  isSpeaking.value = false
  speakingMessageId.value = null
}

export function useTTS() {
  return {
    isSpeaking,
    speakingMessageId,
    speak,
    stopSpeaking,
  }
}
