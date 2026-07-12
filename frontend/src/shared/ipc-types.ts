/**
 * LuomiNest 跨进程 IPC 类型契约（唯一真相源）
 *
 * 本文件被 main / preload / renderer 三端共用，定义：
 * 1. IPC channel 常量（消除 preload 中的魔法字符串）
 * 2. window.api / window.electron 的类型签名（ElectronApi）
 * 3. 跨进程传递的数据结构（PetModelInfo / TabInfo / AppConfig 等）
 *
 * 修改本文件时必须同步检查三端使用点，避免类型不一致。
 */

/* ============================================================================
 * 桌面宠物 / Live2D 相关
 * ========================================================================== */

export type LuomiNestModelType = 'live2d' | 'vrm' | 'pixel'

/** 桌面宠物 / 工作台 Live2D 模型信息（替代 4 处重复定义） */
export interface PetModelInfo {
  id: string
  name: string
  url: string
  scale: number
  type: string
  tags: string[]
}

/** 模型能力扫描结果 */
export interface ModelCapabilities {
  motions: string[]
  expressions: string[]
  modelName: string
  isReady: boolean
}

/* ============================================================================
 * 配置 / TTS / STT
 * ========================================================================== */

export interface TTSConfig {
  provider?: string
  model?: string
  voice?: string
  speed?: number
  baseUrl?: string
  apiKeySet?: boolean
  /** 引擎 ID，与 provider 同义（edge-tts / sherpa-onnx / local / auto 等） */
  engine?: string
  /** 云端引擎 API Key（仅前端暂存标记，明文不回传） */
  apiKey?: string
}

export interface STTConfig {
  provider?: string
  model?: string
  language?: string
  autoSend?: boolean
  autoSendDelay?: number
  baseUrl?: string
  apiKeySet?: boolean
  engine?: string
}

export interface AppConfig {
  theme?: string
  provider?: string
  model?: string
  temperature?: number
  maxTokens?: number
  topP?: number
  reasonerProvider?: string
  reasonerModel?: string
  reasonerTemperature?: number
  reasonerMaxTokens?: number
  reasonerEffort?: string
  tts?: TTSConfig
  stt?: STTConfig
}

/* ============================================================================
 * 浏览器 / 标签页
 * ========================================================================== */

export interface TabErrorInfo {
  code: number
  title: string
  message: string
}

export interface TabInfo {
  id: string
  title: string
  url: string
  active: boolean
  loading?: boolean
  favicon?: string
  error?: TabErrorInfo
  captchaDetected?: boolean
  sleeping?: boolean
}

export interface CookieInfo {
  name: string
  value: string
  domain?: string
  path?: string
  secure?: boolean
  httpOnly?: boolean
  expirationDate?: number
}

export interface NavigationStateInfo {
  canGoBack: boolean
  canGoForward: boolean
}

export interface BrowserSearchResultItem {
  title: string
  snippet: string
  url: string
}

/** 浏览器自动化动作字面量联合（从 automation-executor.ts handlers.keys 提取） */
export type BrowserAutomationAction =
  | 'navigate'
  | 'go_back'
  | 'go_forward'
  | 'reload'
  | 'get_url'
  | 'click'
  | 'type'
  | 'press_key'
  | 'scroll'
  | 'hover'
  | 'get_dom_tree'
  | 'get_text'
  | 'screenshot'
  | 'get_page_title'
  | 'execute_js'
  | 'wait_for_load'
  | 'double_click'
  | 'right_click'
  | 'clear_input'
  | 'select_option'
  | 'get_attribute'
  | 'get_html'
  | 'wait_for_element'
  | 'wait_for_url'
  | 'get_history'

/** 浏览器自动化统一返回结构 */
export interface BrowserAutomationResult {
  success: boolean
  error?: string
  data?: Record<string, unknown>
}

/* ============================================================================
 * 后端启动阶段
 * ========================================================================== */

export type BackendStage = 'spawning' | 'waiting' | 'ready' | 'failed'

export interface BackendStageEvent {
  stage: BackendStage
  detail?: string
}

/* ============================================================================
 * 应用路径（app:getPaths 返回结构）
 * ========================================================================== */

export interface AppPathsInfo {
  userData: string
  cache: string
  data: string
  config: string
  logs: string
  live2d: string
}

/* ============================================================================
 * 桌面宠物 IPC channel 常量
 * ========================================================================== */

/**
 * 桌面宠物窗口的 IPC channel 白名单。
 *
 * SEND：renderer → main（通过 ipcRenderer.send，由 desktop-pet.ts 用 ipcMain.on 注册）
 * ON：main → renderer（通过 webContents.send，由 DesktopPetView 用 ipcRenderer.on 监听）
 *
 * preload/index.ts 的 ALLOWED_SEND_CHANNELS / ALLOWED_ON_CHANNELS 必须引用本常量，
 * 避免魔法字符串散落。
 */
export const DesktopPetIpcChannels = {
  SEND: [
    'desktop-pet:set-ignore-mouse-events',
    'desktop-pet:set-always-on-top',
    'desktop-pet:resize-window',
    'desktop-pet:start-drag',
    'desktop-pet:drag-window',
    'desktop-pet:end-drag',
    'desktop-pet:model-capabilities-response',
    'desktop-pet:show-context-menu',
  ] as const,
  ON: [
    'desktop-pet:load-model',
    'desktop-pet:trigger-motion',
    'desktop-pet:trigger-expression',
    'desktop-pet:lip-sync',
    'desktop-pet:pad-emotion',
    'desktop-pet:set-core-param',
    'desktop-pet:get-model-capabilities',
    'desktop-pet:subtitle',
    'desktop-pet:subtitle-hide',
    'backend:stage',
    'tab:updated',
    'tab:new-tab-request',
    'tab:navigation-state',
  ] as const,
} as const

export type DesktopPetSendChannel = (typeof DesktopPetIpcChannels.SEND)[number]
export type DesktopPetOnChannel = (typeof DesktopPetIpcChannels.ON)[number]

/* ============================================================================
 * window.electron.ipcRenderer 类型
 * ========================================================================== */

/**
 * preload 暴露的受限 ipcRenderer（contextBridge）。
 *
 * 注意：on/removeListener/send 都会在白名单内校验 channel，非白名单 channel 会被静默拦截。
 *
 * listener 的 ...args 已收紧为 unknown[]（通过泛型 T 约束），调用方可使用具体类型注册监听器，
 * 编译期由 TS 推断 T，运行期仍需对 IPC 数据使用类型守卫或断言。
 */
export interface ExposedIpcRenderer {
  on: <T extends unknown[]>(channel: string, listener: (event: unknown, ...args: T) => void) => void
  removeListener: <T extends unknown[]>(channel: string, listener: (event: unknown, ...args: T) => void) => void
  send: (channel: string, ...args: unknown[]) => void
}

/* ============================================================================
 * window.api 类型（ElectronApi）
 * ========================================================================== */

export interface AvatarImportResult {
  success: boolean
  error?: string
  modelInfo?: PetModelInfo
}

export interface AvatarDeleteResult {
  success: boolean
  error?: string
}

export interface DesktopPetResult {
  success: boolean
  error?: string
}

export interface ElectronApi {
  window: {
    minimize: () => Promise<void>
    maximize: () => Promise<void>
    close: () => Promise<void>
    isMaximized: () => Promise<boolean>
  }
  app: {
    getVersion: () => Promise<string>
    getName: () => Promise<string>
    getPaths: () => Promise<AppPathsInfo>
  }
  auth: {
    getToken: () => Promise<string | undefined>
  }
  config: {
    getTheme: () => Promise<string>
    setTheme: (theme: 'light' | 'dark' | 'system') => Promise<void>
    getTTS: () => Promise<TTSConfig>
    setTTS: (updates: Partial<TTSConfig>) => Promise<void>
    getSTT: () => Promise<STTConfig>
    setSTT: (updates: Partial<STTConfig>) => Promise<void>
    getAll: () => Promise<AppConfig>
  }
  cache: {
    getSize: () => Promise<number>
    getBreakdown: () => Promise<Record<string, unknown>>
    clearAll: () => Promise<boolean>
    clearDir: (dirName: string) => Promise<void | boolean>
  }
  tab: {
    create: (url?: string) => Promise<TabInfo>
    activate: (tabId: string) => Promise<void>
    close: (tabId: string) => Promise<void>
    getAll: () => Promise<TabInfo[]>
    getActive: () => Promise<TabInfo | undefined>
    reload: (tabId?: string) => Promise<void>
    goBack: (tabId?: string) => Promise<void>
    goForward: (tabId?: string) => Promise<void>
    getNavigationState: (tabId?: string) => Promise<NavigationStateInfo>
    hideAll: () => Promise<void>
    showActive: () => Promise<void>
    setBoundsConfig: (config: { sidebarWidth?: number; devPanelHeight?: number }) => Promise<void>
    cleanup: () => Promise<void>
    getCookies: () => Promise<CookieInfo[]>
    clearData: () => Promise<void>
  }
  browserSearch: {
    search: (query: string) => Promise<BrowserSearchResultItem[]>
    fetchUrl: (url: string) => Promise<string>
  }
  browserAutomation: {
    execute: (action: BrowserAutomationAction, args?: Record<string, unknown>) => Promise<BrowserAutomationResult>
  }
  avatar: {
    importModel: () => Promise<AvatarImportResult>
    listImportedModels: () => Promise<PetModelInfo[]>
    deleteModel: (modelName: string) => Promise<AvatarDeleteResult>
    getImportedModelsPath: () => Promise<string>
  }
  desktopPet: {
    open: (modelInfo?: PetModelInfo) => Promise<DesktopPetResult>
    close: () => Promise<DesktopPetResult>
    isRunning: () => Promise<boolean>
    loadModel: (modelInfo: PetModelInfo) => Promise<DesktopPetResult>
    show: () => Promise<DesktopPetResult>
    hide: () => Promise<DesktopPetResult>
    triggerMotion: (group: string, index: number) => Promise<DesktopPetResult>
    triggerExpression: (name: string) => Promise<DesktopPetResult>
    setPosition: (x: number, y: number) => Promise<DesktopPetResult>
    setScale: (scale: number) => Promise<DesktopPetResult>
    driveLipSync: (value: number) => Promise<DesktopPetResult>
    drivePadEmotion: (pleasure: number, arousal: number, dominance: number) => Promise<DesktopPetResult>
    setCoreParam: (paramId: string, value: number) => Promise<DesktopPetResult>
    getModelCapabilities: () => Promise<ModelCapabilities | null>
    sendSubtitle: (text: string) => Promise<DesktopPetResult>
    hideSubtitle: () => Promise<DesktopPetResult>
  }
  backend: {
    subscribeStage: (callback: (data: BackendStageEvent) => void) => () => void
  }
}
