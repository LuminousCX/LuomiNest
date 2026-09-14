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
  /** 界面语言（zh-CN / en-US / ja-JP） */
  locale?: string
}

/* ============================================================================
 * 主题配置（完整持久化）
 * ========================================================================== */

/** 色彩主题定义 */
export interface ColorTheme {
  id: string
  name: string
  type: 'preset' | 'custom'
  /** 三色主调 - 浅色模式 */
  light: ThemeColorSet
  /** 三色主调 - 深色模式 */
  dark: ThemeColorSet
}

/** 每个主题的三色配色集 */
export interface ThemeColorSet {
  /** 主色 - 品牌/导航/按钮 */
  primary: string
  /** 辅色 - 辅助元素/卡片边框 */
  secondary: string
  /** 强调色 - 高亮/徽章 */
  accent: string
  primaryHover: string
  /** 半透明浅色版本 */
  primaryLight: string
  secondaryHover: string
  secondaryLight: string
  accentHover: string
  accentLight: string
  /** 阴影色（用主色调的半透明） */
  shadowBrand: string
  /** 渐变 */
  gradientBrand: string
}

/** 背景配置（ThemeConfig 与 Skin 共用，fit 为可选以兼容旧配置） */
export interface BackgroundConfig {
  /** 背景图片路径（相对路径或 null） */
  image: string | null
  /** 模糊度 0-20 */
  blur: number
  /** 透明度 0-100 */
  opacity: number
  /** 背景适配方式（仅图片/渐变有效，可选以兼容无 fit 的旧配置） */
  fit?: BackgroundFit
}

/** 背景适配方式 */
export type BackgroundFit = 'cover' | 'contain' | 'center' | 'right'

/** 皮肤包：一套完整的视觉方案 */
export interface Skin {
  id: string
  name: string
  type: 'preset' | 'custom'
  /** 关联的色彩主题 ID */
  colorThemeId: string
  /** 主题模式 */
  mode: 'light' | 'dark' | 'system'
  /** 背景配置 */
  background: BackgroundConfig
  /** 毛玻璃强度 0-100 */
  glassIntensity: number
  /** 氛围光强度 0-100 */
  ambientIntensity: number
  /** 圆角倾向 0-100（影响卡片圆角） */
  radiusTendency?: number
}

/** 完整主题配置（持久化用） */
export interface ThemeConfig {
  activeColorThemeId: string
  activeMode: 'light' | 'dark' | 'system'
  background: BackgroundConfig
  /** 自定义主题，最多 5 个 */
  customThemes: ColorTheme[]
  /** 兼容旧配置：仅有 light/dark 布尔值时使用 */
  isDark?: boolean
  /** 新增：当前激活的皮肤包 ID */
  activeSkinId?: string
  /** 新增：自定义皮肤包 */
  customSkins?: Skin[]
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
 * 云端通行证（Device Flow 登录）
 * ========================================================================== */

/** 云端登录状态机 */
export type CloudAuthState = 'loggedOut' | 'pendingAuth' | 'authorized' | 'error'

/** 云端资源路由模式（off = 仅本地配置，all = 全部走云端） */
export type CloudRoutingMode = 'off' | 'all'

/**
 * 云端账户摘要（由 main 进程组装；renderer 只见摘要，永不接触任何令牌）。
 * 字段缺失时以空串占位，不抛错。
 */
export interface CloudAccountInfo {
  nickname: string
  tier: string
  /** 芙贝币余额（主站 /userinfo 的 coin_balance 为准；拉取失败为 null，界面显示"无法获取"而非假 0） */
  coinBalance: number | null
  quotaRemaining: number
  /** 头像地址（主站 /userinfo 提供，可能缺失） */
  avatar?: string
  /** 称号（主站 honor_title，可能缺失） */
  title?: string
  /** 荣誉等级（影响每日额度加成；拉取失败为 null） */
  honorLevel?: number | null
  /** 邮箱（可能缺失） */
  email?: string
  /** 档位到期时间（ISO 字符串，可能缺失；展示时取日期部分） */
  tierExpiresAt?: string
  /** 注册日期（YYYY-MM-DD，可能缺失） */
  registeredAt?: string
}

/** 云端可用模型目录条目（GET {baseUrl}/api/v1/llm/models 的 models 数组元素） */
export interface CloudModelInfo {
  modelId: string
  displayName: string
}

/** 本地后端云令牌注入状态（GET {backend}/api/v1/cloud/status，令牌只回传末 4 位） */
export interface CloudBackendStatus {
  configured: boolean
  routingMode: CloudRoutingMode
  cloudBaseUrl?: string | null
  tokenTail4?: string | null
}

/** 云端登录状态（cloud:status 应答与 cloud 状态推送共用） */
export interface CloudAuthStatus {
  state: CloudAuthState
  /** pendingAuth 时展示给用户确认的授权码 */
  userCode?: string
  /** authorized 时的账户摘要（账户信息拉取失败时为 null） */
  account?: CloudAccountInfo | null
  /** error 时的错误码（renderer 侧映射为本地化文案，未知码原样展示） */
  error?: string
}

/* ============================================================================
 * 全量 IPC channel 常量（唯一真相源）
 * ========================================================================== */

/**
 * LuomiNest 全量 IPC channel 常量，按域 + 通信方向两级分组：
 * - 域：window / app / config / tab / desktopPet ...（与 preload api 的命名空间对应）
 * - 方向：
 *   - invoke：renderer → main 请求应答（preload ipcRenderer.invoke ↔ main ipcMain.handle）
 *   - send  ：renderer → main 单向（ipcRenderer.send ↔ ipcMain.on）
 *   - push  ：main → renderer 单向（webContents.send ↔ ipcRenderer.on）
 *
 * main / preload 两端禁止手写 channel 字符串，一律引用本常量；并配合下方
 * IpcInvokeChannel / IpcSendChannel / IpcPushChannel 联合类型做编译期收窄，
 * 新增或改名 channel 未登记到本常量时两端直接编译报错，杜绝隐式契约漂移。
 */
export const IpcChannels = {
  window: {
    invoke: {
      minimize: 'window:minimize',
      maximize: 'window:maximize',
      close: 'window:close',
      isMaximized: 'window:isMaximized',
    },
  },
  app: {
    invoke: {
      getVersion: 'app:getVersion',
      getName: 'app:getName',
      getPaths: 'app:getPaths',
      getWelcomeCompleted: 'app:getWelcomeCompleted',
      setWelcomeCompleted: 'app:setWelcomeCompleted',
    },
  },
  auth: {
    invoke: {
      getToken: 'auth:getToken',
    },
  },
  config: {
    invoke: {
      getTheme: 'config:getTheme',
      setTheme: 'config:setTheme',
      getThemeConfig: 'config:getThemeConfig',
      setThemeConfig: 'config:setThemeConfig',
      getTTS: 'config:getTTS',
      setTTS: 'config:setTTS',
      getSTT: 'config:getSTT',
      setSTT: 'config:setSTT',
      getLocale: 'config:getLocale',
      setLocale: 'config:setLocale',
      getAll: 'config:getAll',
    },
  },
  cache: {
    invoke: {
      getSize: 'cache:getSize',
      getBreakdown: 'cache:getBreakdown',
      clearAll: 'cache:clearAll',
      clearDir: 'cache:clearDir',
    },
  },
  tab: {
    invoke: {
      create: 'tab:create',
      activate: 'tab:activate',
      close: 'tab:close',
      getAll: 'tab:getAll',
      getActive: 'tab:getActive',
      reload: 'tab:reload',
      navigate: 'tab:navigate',
      goBack: 'tab:goBack',
      goForward: 'tab:goForward',
      getNavigationState: 'tab:getNavigationState',
      hideAll: 'tab:hideAll',
      showActive: 'tab:showActive',
      setBoundsConfig: 'tab:setBoundsConfig',
      cleanup: 'tab:cleanup',
      getCookies: 'tab:getCookies',
      clearData: 'tab:clearData',
    },
    push: {
      // main/index.ts 通过 tabManager 回调向主窗口广播；new-tab-request / navigation-state
      // 由 tab.ts 以 `tab:${event}` 动态拼接，event 后缀必须与本表保持一致
      updated: 'tab:updated',
      newTabRequest: 'tab:new-tab-request',
      navigationState: 'tab:navigation-state',
    },
  },
  browser: {
    invoke: {
      search: 'browser:search',
      fetchUrl: 'browser:fetchUrl',
      automation: 'browser:automation',
    },
  },
  avatar: {
    invoke: {
      importModel: 'avatar:importModel',
      listImportedModels: 'avatar:listImportedModels',
      deleteModel: 'avatar:deleteModel',
      getImportedModelsPath: 'avatar:getImportedModelsPath',
      // 协作者头像缓存（collaborator-avatars.ts）
      getCollaboratorAvatar: 'avatar:getCollaboratorAvatar',
      updateCollaboratorAvatars: 'avatar:updateCollaboratorAvatars',
    },
  },
  desktopPet: {
    invoke: {
      // 主应用窗口 → main：桌宠窗口生命周期 / 模型与动作控制
      open: 'desktop-pet:open',
      close: 'desktop-pet:close',
      isRunning: 'desktop-pet:isRunning',
      loadModel: 'desktop-pet:loadModel',
      show: 'desktop-pet:show',
      hide: 'desktop-pet:hide',
      triggerMotion: 'desktop-pet:triggerMotion',
      triggerExpression: 'desktop-pet:triggerExpression',
      setPosition: 'desktop-pet:setPosition',
      setScale: 'desktop-pet:setScale',
      driveLipSync: 'desktop-pet:driveLipSync',
      drivePadEmotion: 'desktop-pet:drivePadEmotion',
      setCoreParam: 'desktop-pet:setCoreParam',
      getModelCapabilities: 'desktop-pet:getModelCapabilities',
      sendSubtitle: 'desktop-pet:sendSubtitle',
      hideSubtitle: 'desktop-pet:hideSubtitle',
      setStreamingState: 'desktop-pet:setStreamingState',
    },
    send: {
      // 桌宠窗口 → main 单向（桌宠窗口 preload 白名单 SEND）
      setIgnoreMouseEvents: 'desktop-pet:set-ignore-mouse-events',
      setAlwaysOnTop: 'desktop-pet:set-always-on-top',
      startDrag: 'desktop-pet:start-drag',
      dragWindow: 'desktop-pet:drag-window',
      endDrag: 'desktop-pet:end-drag',
      modelCapabilitiesResponse: 'desktop-pet:model-capabilities-response',
      showContextMenu: 'desktop-pet:show-context-menu',
      // 桌宠窗口 → main → 主应用窗口：聊天消息转发
      sendChatMessage: 'desktop-pet:send-chat-message',
      cancelChat: 'desktop-pet:cancel-chat',
      // 多模型扩展：渲染器向主进程上报就绪状态（向后兼容，旧版不发送无影响，仅白名单登记）
      rendererReady: 'desktop-pet:renderer-ready',
    },
    push: {
      // main → 桌宠窗口 / 主应用窗口单向（桌宠窗口 preload 白名单 ON）
      loadModel: 'desktop-pet:load-model',
      triggerMotion: 'desktop-pet:trigger-motion',
      triggerExpression: 'desktop-pet:trigger-expression',
      setScale: 'desktop-pet:set-scale',
      lipSync: 'desktop-pet:lip-sync',
      padEmotion: 'desktop-pet:pad-emotion',
      setCoreParam: 'desktop-pet:set-core-param',
      getModelCapabilities: 'desktop-pet:get-model-capabilities',
      subtitle: 'desktop-pet:subtitle',
      subtitleHide: 'desktop-pet:subtitle-hide',
      // 主进程 → 桌宠窗口：窗口可见性变化（隐藏时降低帧率 / 显示时恢复）
      visibilityChanged: 'desktop-pet:visibility-changed',
      // 主进程 → 主应用窗口：转发桌宠窗口的聊天请求
      chatMessage: 'desktop-pet:chat-message',
      chatCancel: 'desktop-pet:chat-cancel',
      // 主进程 → 桌宠窗口：流式状态反馈（输入区切换发送/取消按钮）
      streamingState: 'desktop-pet:streaming-state',
      // 多模型扩展：主进程通知渲染器模型能力变更（向后兼容，旧版忽略，仅白名单登记）
      capabilityChanged: 'desktop-pet:capability-changed',
      // 注意：set-position 未列入桌宠窗口 ON 白名单（历史行为，保持不变），仅 main 侧发送使用
      setPosition: 'desktop-pet:set-position',
    },
  },
  dialog: {
    invoke: {
      selectBackgroundImage: 'dialog:selectBackgroundImage',
      deleteBackgroundImage: 'dialog:deleteBackgroundImage',
    },
  },
  backend: {
    invoke: {
      subscribe: 'backend:subscribe',
    },
    push: {
      stage: 'backend:stage',
    },
  },
  cloud: {
    invoke: {
      login: 'cloud:login',
      status: 'cloud:status',
      logout: 'cloud:logout',
      // pendingAuth 下 renderer 请求 main 打开系统浏览器授权页
      openVerification: 'cloud:openVerification',
      getRoutingMode: 'cloud:getRoutingMode',
      setRoutingMode: 'cloud:setRoutingMode',
      // 拉取云端可用模型目录（authorized 态设置页展示，失败静默降级）
      fetchModels: 'cloud:fetchModels',
      // 查询本地后端令牌注入状态（消费 Python GET /api/v1/cloud/status）
      getBackendStatus: 'cloud:getBackendStatus',
    },
    push: {
      // 登录状态机变化时 main 广播（login/status/logout/续期失败等均会触发）
      status: 'cloud:status-changed',
    },
  },
} as const

/** 全部域对象类型的联合 */
type IpcDomain = (typeof IpcChannels)[keyof typeof IpcChannels]

/** 提取域对象中指定方向分组下的 channel 字面量联合（该域未声明该分组时为 never） */
type ChannelsInGroup<T, G extends 'invoke' | 'send' | 'push'> = T extends Record<G, infer C> ? C[keyof C] : never

/** renderer → main 请求应答通道全集（preload ipcRenderer.invoke ↔ main ipcMain.handle） */
export type IpcInvokeChannel = ChannelsInGroup<IpcDomain, 'invoke'>

/** renderer → main 单向通道全集（ipcRenderer.send ↔ ipcMain.on） */
export type IpcSendChannel = ChannelsInGroup<IpcDomain, 'send'>

/** main → renderer 单向通道全集（webContents.send ↔ ipcRenderer.on） */
export type IpcPushChannel = ChannelsInGroup<IpcDomain, 'push'>

/* ============================================================================
 * 桌面宠物窗口 IPC channel 白名单（派生自 IpcChannels.desktopPet）
 * ========================================================================== */

/**
 * 桌面宠物窗口的 IPC channel 白名单（成员与顺序保持既有行为不变）。
 *
 * SEND：renderer → main（通过 ipcRenderer.send，由 desktop-pet.ts 用 ipcMain.on 注册）
 * ON：main → renderer（通过 webContents.send，由 DesktopPetView 用 ipcRenderer.on 监听）
 *
 * preload/index.ts 的 ALLOWED_SEND_CHANNELS / ALLOWED_ON_CHANNELS 必须引用本常量，
 * 避免魔法字符串散落。注意：ON 白名单不含 desktop-pet:set-position（历史行为）。
 */
export const DesktopPetIpcChannels = {
  SEND: [
    IpcChannels.desktopPet.send.setIgnoreMouseEvents,
    IpcChannels.desktopPet.send.setAlwaysOnTop,
    IpcChannels.desktopPet.send.startDrag,
    IpcChannels.desktopPet.send.dragWindow,
    IpcChannels.desktopPet.send.endDrag,
    IpcChannels.desktopPet.send.modelCapabilitiesResponse,
    IpcChannels.desktopPet.send.showContextMenu,
    // 桌宠窗口 → 主进程 → 主应用窗口：聊天消息转发
    IpcChannels.desktopPet.send.sendChatMessage,
    IpcChannels.desktopPet.send.cancelChat,
    // 多模型扩展：渲染器向主进程上报就绪状态（向后兼容，旧版不发送无影响）
    IpcChannels.desktopPet.send.rendererReady,
  ] as const,
  ON: [
    IpcChannels.desktopPet.push.loadModel,
    IpcChannels.desktopPet.push.triggerMotion,
    IpcChannels.desktopPet.push.triggerExpression,
    IpcChannels.desktopPet.push.setScale,
    IpcChannels.desktopPet.push.lipSync,
    IpcChannels.desktopPet.push.padEmotion,
    IpcChannels.desktopPet.push.setCoreParam,
    IpcChannels.desktopPet.push.getModelCapabilities,
    IpcChannels.desktopPet.push.subtitle,
    IpcChannels.desktopPet.push.subtitleHide,
    // 主进程 → 桌宠窗口：窗口可见性变化（隐藏时降低帧率 / 显示时恢复）
    IpcChannels.desktopPet.push.visibilityChanged,
    // 主进程 → 主应用窗口：转发桌宠窗口的聊天请求
    IpcChannels.desktopPet.push.chatMessage,
    IpcChannels.desktopPet.push.chatCancel,
    // 主进程 → 桌宠窗口：流式状态反馈（输入区切换发送/取消按钮）
    IpcChannels.desktopPet.push.streamingState,
    // 多模型扩展：主进程通知渲染器模型能力变更（向后兼容，旧版忽略）
    IpcChannels.desktopPet.push.capabilityChanged,
    IpcChannels.backend.push.stage,
    IpcChannels.tab.push.updated,
    IpcChannels.tab.push.newTabRequest,
    IpcChannels.tab.push.navigationState,
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

/** 协作者头像缓存查询结果：缓存文件存在时 url 为 luominest-avatar://cached/ 协议地址，否则为 null */
export interface CollaboratorAvatarResult {
  key: string
  url: string | null
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
    getWelcomeCompleted: () => Promise<boolean>
    setWelcomeCompleted: (value: boolean) => Promise<void>
    /** 当前操作系统（process.platform），渲染层平台差异用（如 mac 红绿灯避让） */
    platform: 'darwin' | 'win32' | 'linux' | string
  }
  auth: {
    getToken: () => Promise<string | undefined>
  }
  config: {
    getTheme: () => Promise<string>
    setTheme: (theme: 'light' | 'dark' | 'system') => Promise<void>
    getThemeConfig: () => Promise<ThemeConfig | null>
    setThemeConfig: (config: ThemeConfig) => Promise<void>
    getTTS: () => Promise<TTSConfig>
    setTTS: (updates: Partial<TTSConfig>) => Promise<void>
    getSTT: () => Promise<STTConfig>
    setSTT: (updates: Partial<STTConfig>) => Promise<void>
    getLocale: () => Promise<string | undefined>
    setLocale: (locale: string) => Promise<void>
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
    navigate: (url: string, tabId?: string) => Promise<void>
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
    getCollaboratorAvatar: (key: string) => Promise<CollaboratorAvatarResult>
    updateCollaboratorAvatars: () => Promise<Record<string, boolean>>
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
    setStreamingState: (isStreaming: boolean) => Promise<DesktopPetResult>
  }
  /** 桌宠窗口内的聊天发送（桌宠窗口 → 主进程 → 主应用窗口） */
  desktopPetChat: {
    sendMessage: (text: string) => void
    cancel: () => void
  }
  /** 主应用窗口监听桌宠转发的聊天请求 */
  onDesktopPetChatMessage: (callback: (text: string) => void) => () => void
  onDesktopPetChatCancel: (callback: () => void) => () => void
  backend: {
    subscribeStage: (callback: (data: BackendStageEvent) => void) => () => void
  }
  cloud: {
    login: () => Promise<CloudAuthStatus>
    status: () => Promise<CloudAuthStatus>
    logout: () => Promise<CloudAuthStatus>
    /** 用系统浏览器打开当前授权页（仅 pendingAuth 有效） */
    openVerification: () => Promise<boolean>
    getRoutingMode: () => Promise<CloudRoutingMode>
    setRoutingMode: (mode: CloudRoutingMode) => Promise<void>
    /** 拉取云端可用模型目录（未登录/失败时返回空数组，界面静默降级） */
    fetchModels: () => Promise<CloudModelInfo[]>
    /** 查询本地后端令牌注入状态（后端未就绪/失败时返回 null，不阻塞页面） */
    getBackendStatus: () => Promise<CloudBackendStatus | null>
    /** 订阅登录状态推送，返回取消订阅函数 */
    onStatus: (callback: (data: CloudAuthStatus) => void) => () => void
  }
  dialog: {
    selectBackgroundImage: () => Promise<
      { success: true; url: string; width: number; height: number; warning?: string } |
      { success: false; error?: string; cancelled?: boolean }
    >
    deleteBackgroundImage: (imageUrl: string) => Promise<{ success: boolean; error?: string }>
  }
}
