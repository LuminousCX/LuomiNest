/// <reference types="vite/client" />

import type { ElectronApi, ExposedIpcRenderer } from '@shared/ipc-types'

declare global {
  interface Window {
    /** Live2D Cubism Core 原生库（第三方，无 TypeScript 类型声明） */
    Live2DCubismCore: { [key: string]: unknown }
    /** preload 通过 contextBridge 暴露的 API */
    api: ElectronApi
    /** preload 通过 contextBridge 暴露的受限 ipcRenderer */
    electron?: {
      ipcRenderer: ExposedIpcRenderer
    }
    /** 认证 token 失效时的回調（由 router 注入） */
    __lumiInvalidateAuthToken?: () => void
    /** Web Speech API 语音识别构造器（标准前缀） */
    SpeechRecognition?: new () => SpeechRecognitionInstance
    /** Web Speech API 语音识别构造器（WebKit 前缀） */
    webkitSpeechRecognition?: new () => SpeechRecognitionInstance
  }

  /** Web Speech API 语音识别结果项 */
  interface SpeechRecognitionResult {
    isFinal: boolean
    0: { transcript: string }
    length: number
  }

  /** Web Speech API 语音识别事件 */
  interface SpeechRecognitionEvent {
    resultIndex: number
    results: { length: number; [index: number]: SpeechRecognitionResult }
  }

  /** Web Speech API 语音识别错误事件 */
  interface SpeechRecognitionErrorEvent {
    error: string
  }

  /** Web Speech API 语音识别实例 */
  interface SpeechRecognitionInstance {
    lang: string
    continuous: boolean
    interimResults: boolean
    start: () => void
    stop: () => void
    abort: () => void
    onresult: ((event: SpeechRecognitionEvent) => void) | null
    onerror: ((event: SpeechRecognitionErrorEvent) => void) | null
    onend: (() => void) | null
  }
}
