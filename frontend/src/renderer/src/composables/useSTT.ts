import { ref, onBeforeUnmount } from 'vue'
import { API_ENDPOINTS } from '../config/api'
import { useModelStore } from '../stores/model'
import { useToast } from './useToast'

/**
 * STT composable - 语音转文字
 *
 * 支持两种模式：
 * 1. 后端引擎（sherpa-onnx / funasr / faster-whisper）：录音后上传音频文件到后端识别
 * 2. 浏览器原生（Web Speech API）：实时识别，无需上传
 *
 * 根据 modelStore.sttConfig.engine 选择模式：
 * - "auto" 或具体引擎 ID → 后端引擎
 * - "__browser__" → 浏览器原生
 */
export const useSTT = () => {
  const modelStore = useModelStore()
  const toast = useToast()

  const isRecording = ref(false)
  const isTranscribing = ref(false)
  const interimText = ref('')

  let mediaRecorder: MediaRecorder | null = null
  let audioChunks: Blob[] = []
  let audioStream: MediaStream | null = null
  let recognition: any = null

  const getSTTMode = (): 'backend' | 'browser' => {
    const engine = modelStore.sttConfig.engine || 'auto'
    if (engine === '__browser__') return 'browser'
    // auto 或具体后端引擎 ID → backend
    return 'backend'
  }

  const startRecording = async (): Promise<boolean> => {
    const mode = getSTTMode()

    if (mode === 'browser') {
      return startBrowserRecognition()
    }

    return startBackendRecording()
  }

  const stopRecording = async (): Promise<string> => {
    const mode = getSTTMode()

    if (mode === 'browser') {
      return stopBrowserRecognition()
    }

    return stopBackendRecording()
  }

  // --- 后端引擎模式 ---

  const startBackendRecording = async (): Promise<boolean> => {
    try {
      audioStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioChunks = []

      // 优先使用 webm/opus，兼容性最好
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : ''

      mediaRecorder = mimeType
        ? new MediaRecorder(audioStream, { mimeType })
        : new MediaRecorder(audioStream)

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunks.push(e.data)
        }
      }

      mediaRecorder.start()
      isRecording.value = true
      return true
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e)
      toast.error(`麦克风启动失败：${errMsg}`)
      return false
    }
  }

  const stopBackendRecording = (): Promise<string> => {
    return new Promise((resolve) => {
      if (!mediaRecorder || !isRecording.value) {
        resolve('')
        return
      }

      mediaRecorder.onstop = async () => {
        isRecording.value = false
        isTranscribing.value = true

        // 停止所有音轨
        if (audioStream) {
          audioStream.getTracks().forEach((t) => t.stop())
          audioStream = null
        }

        try {
          const audioBlob = new Blob(audioChunks, {
            type: mediaRecorder?.mimeType || 'audio/webm',
          })

          if (audioBlob.size === 0) {
            toast.warning('录音为空')
            resolve('')
            return
          }

          const text = await transcribeWithBackend(audioBlob)
          resolve(text)
        } catch (e: unknown) {
          const errMsg = e instanceof Error ? e.message : String(e)
          toast.error(`语音识别失败：${errMsg}`)
          resolve('')
        } finally {
          isTranscribing.value = false
          mediaRecorder = null
          audioChunks = []
        }
      }

      mediaRecorder.stop()
    })
  }

  const transcribeWithBackend = async (audioBlob: Blob): Promise<string> => {
    const formData = new FormData()
    const ext = audioBlob.type.includes('webm') ? 'webm' : 'wav'
    formData.append('audio', audioBlob, `recording.${ext}`)
    formData.append('engine', modelStore.sttConfig.engine || 'auto')
    formData.append('language', modelStore.sttConfig.language || 'auto')

    const token = await window.api.auth.getToken()
    const resp = await fetch(`${API_ENDPOINTS.V1}/chat/stt/transcribe`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
      signal: AbortSignal.timeout(60000),
    })

    if (!resp.ok) {
      const errData = await resp.json().catch(() => null)
      const errMsg = errData?.error || `识别失败 (${resp.status})`
      throw new Error(errMsg)
    }

    const result = await resp.json()
    return result?.data?.text || ''
  }

  // --- 浏览器原生模式 ---

  const startBrowserRecognition = (): boolean => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

    if (!SpeechRecognition) {
      toast.error('浏览器不支持语音识别，请使用后端引擎')
      return false
    }

    recognition = new SpeechRecognition()
    recognition.continuous = false
    recognition.interimResults = true
    recognition.lang = modelStore.sttConfig.language || 'zh-CN'

    recognition.onresult = (event: any) => {
      let interim = ''
      let final = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        if (event.results[i].isFinal) {
          final += transcript
        } else {
          interim += transcript
        }
      }
      interimText.value = interim
      if (final) {
        interimText.value = final
      }
    }

    recognition.onerror = (event: any) => {
      toast.error(`语音识别错误：${event.error}`)
      isRecording.value = false
    }

    recognition.onend = () => {
      isRecording.value = false
    }

    recognition.start()
    isRecording.value = true
    return true
  }

  const stopBrowserRecognition = (): Promise<string> => {
    return new Promise((resolve) => {
      if (!recognition) {
        resolve('')
        return
      }

      const originalOnend = recognition.onend
      recognition.onend = () => {
        isRecording.value = false
        const text = interimText.value
        interimText.value = ''
        recognition = null
        resolve(text)
      }

      recognition.stop()

      // 兜底：如果 onend 没触发，1 秒后返回
      setTimeout(() => {
        if (recognition) {
          const text = interimText.value
          interimText.value = ''
          recognition = null
          resolve(text)
        }
      }, 1000)

      // 防止重复调用
      void originalOnend
    })
  }

  const cancel = () => {
    if (mediaRecorder && isRecording.value) {
      mediaRecorder.onstop = null
      mediaRecorder.stop()
      isRecording.value = false
    }
    if (audioStream) {
      audioStream.getTracks().forEach((t) => t.stop())
      audioStream = null
    }
    if (recognition) {
      recognition.onend = null
      recognition.onerror = null
      recognition.onresult = null
      try {
        recognition.stop()
      } catch {
        // ignore
      }
      recognition = null
    }
    isRecording.value = false
    isTranscribing.value = false
    interimText.value = ''
    audioChunks = []
  }

  onBeforeUnmount(() => {
    cancel()
  })

  return {
    isRecording,
    isTranscribing,
    interimText,
    startRecording,
    stopRecording,
    cancel,
  }
}
