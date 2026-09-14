import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs'
import { PATHS } from './paths'
import type { ThemeConfig, CloudRoutingMode } from '@shared/ipc-types'

interface WindowBounds {
  x?: number
  y?: number
  width: number
  height: number
  isMaximized: boolean
}

/** 云端通行证接入配置（默认指向生产公开端点；本地联调用环境变量覆盖，见 resolveCloudConfig） */
interface CloudConfig {
  /** 通行证签发方（issuer）基础地址 */
  issuer: string
  /** 云端 API 基础地址 */
  baseUrl: string
  /** 云端资源路由模式 */
  routingMode: CloudRoutingMode
}

/* ── 云端公开服务端点（公开服务域名，随分发是允许且必需的；不含任何密钥/内部路径）── */
const CLOUD_ISSUER_PROD = 'https://passport.luminouschenxi.com'
const CLOUD_BASE_URL_PROD = 'https://luominest.luminouschenxi.com'
/** 旧版默认本机端点（历史默认值，仅用于迁移检测） */
const CLOUD_ISSUER_LEGACY = 'http://localhost:8080'
const CLOUD_BASE_URL_LEGACY = 'http://localhost:18001'

interface AppConfig {
  theme: 'light' | 'dark' | 'system'
  tts: {
    provider: string
    model: string
    voice: string
    speed: number
    baseUrl: string
  }
  stt: {
    provider: string
    model: string
    language: string
    autoSend: boolean
    autoSendDelay: number
    baseUrl: string
  }
  window: WindowBounds
  sidebarCollapsed: boolean
  lastActiveRoute: string
  cacheMaxSizeMB: number
  telemetry: {
    enabled: boolean
  }
  autoLaunch: boolean
  installPath: string
  installed: boolean
  installDate: string
  /** 欢迎向导是否已完成（首次启动显示一次，之后跳过） */
  welcomeCompleted: boolean
  /** 关闭窗口最小化到托盘的首次提示是否已展示 */
  closeToTrayPrompted: boolean
  /** 界面语言（zh-CN / en-US / ja-JP），渲染层 stores/locale.ts 经 IPC 读写 */
  locale: string
  /** 云端通行证接入配置 */
  cloud: CloudConfig
}

const DEFAULT_CONFIG: AppConfig = {
  theme: 'system',
  tts: {
    provider: '',
    model: 'tts-1',
    voice: 'alloy',
    speed: 1.0,
    baseUrl: '',
  },
  stt: {
    provider: '',
    model: 'whisper-1',
    language: 'zh-CN',
    autoSend: false,
    autoSendDelay: 2000,
    baseUrl: '',
  },
  window: {
    width: 1280,
    height: 820,
    isMaximized: false,
  },
  sidebarCollapsed: false,
  lastActiveRoute: '/welcome',
  cacheMaxSizeMB: 5120,
  telemetry: {
    enabled: false,
  },
  autoLaunch: false,
  installPath: '',
  installed: false,
  installDate: '',
  welcomeCompleted: false,
  closeToTrayPrompted: false,
  locale: 'zh-CN',
  cloud: {
    issuer: CLOUD_ISSUER_PROD,
    baseUrl: CLOUD_BASE_URL_PROD,
    routingMode: 'off',
  },
}

let cachedConfig: AppConfig | null = null

/**
 * 云端端点解析（迁移 + dev 覆盖）：
 * 1. 迁移：旧版默认 localhost 端点（历史上无设置入口，出现即代表用户从未显式配置）
 *    升级为生产默认，发行版开箱即可连接生产云；
 * 2. dev 覆盖：本地联调可用环境变量 LUOMINEST_CLOUD_ISSUER / LUOMINEST_CLOUD_BASE_URL
 *    把端点指回本机服务（优先级最高，覆盖配置文件）。
 */
const resolveCloudConfig = (stored: Partial<CloudConfig> | undefined): CloudConfig => {
  const merged = { ...DEFAULT_CONFIG.cloud, ...stored }
  if (merged.issuer === CLOUD_ISSUER_LEGACY) merged.issuer = CLOUD_ISSUER_PROD
  if (merged.baseUrl === CLOUD_BASE_URL_LEGACY) merged.baseUrl = CLOUD_BASE_URL_PROD
  const envIssuer = process.env.LUOMINEST_CLOUD_ISSUER
  const envBaseUrl = process.env.LUOMINEST_CLOUD_BASE_URL
  if (envIssuer) merged.issuer = envIssuer
  if (envBaseUrl) merged.baseUrl = envBaseUrl
  return merged
}

/** 是否设置了云端端点环境变量覆盖（dev 联调时覆盖值不回写落盘，避免污染正式配置） */
const hasCloudEnvOverride = (): boolean =>
  Boolean(process.env.LUOMINEST_CLOUD_ISSUER || process.env.LUOMINEST_CLOUD_BASE_URL)

const loadConfig = (): AppConfig => {
  if (cachedConfig) return cachedConfig

  const filePath = PATHS.configFilePath
  if (!existsSync(filePath)) {
    cachedConfig = { ...DEFAULT_CONFIG }
    saveConfig(cachedConfig)
    return cachedConfig
  }

  try {
    const raw = readFileSync(filePath, 'utf-8')
    const parsed = JSON.parse(raw) as Partial<AppConfig>
    cachedConfig = {
      ...DEFAULT_CONFIG,
      ...parsed,
      tts: { ...DEFAULT_CONFIG.tts, ...parsed.tts },
      stt: { ...DEFAULT_CONFIG.stt, ...parsed.stt },
      window: { ...DEFAULT_CONFIG.window, ...parsed.window },
      cloud: resolveCloudConfig(parsed.cloud),
    }
    // 旧默认端点升级后回写落盘，避免下次启动重复迁移（dev 环境变量覆盖不落盘）
    if (!hasCloudEnvOverride() && JSON.stringify(cachedConfig.cloud) !== JSON.stringify(parsed.cloud)) {
      saveConfig(cachedConfig)
    }
    return cachedConfig
  } catch {
    cachedConfig = { ...DEFAULT_CONFIG }
    return cachedConfig
  }
}

const saveConfig = (config: AppConfig): void => {
  const filePath = PATHS.configFilePath
  mkdirSync(PATHS.config, { recursive: true })
  writeFileSync(filePath, JSON.stringify(config, null, 2), 'utf-8')
  cachedConfig = config
}

export const configStore = {
  get: <K extends keyof AppConfig>(key: K): AppConfig[K] => {
    return loadConfig()[key]
  },

  set: <K extends keyof AppConfig>(key: K, value: AppConfig[K]): void => {
    const config = loadConfig()
    config[key] = value
    saveConfig(config)
  },

  getTheme: (): string => loadConfig().theme,
  setTheme: (theme: 'light' | 'dark' | 'system'): void => {
    configStore.set('theme', theme)
  },

  getThemeConfig: (): ThemeConfig | null => {
    const filePath = PATHS.themeConfigFilePath
    if (!existsSync(filePath)) return null
    try {
      const raw = readFileSync(filePath, 'utf-8')
      return JSON.parse(raw) as ThemeConfig
    } catch {
      return null
    }
  },

  setThemeConfig: (config: ThemeConfig): void => {
    mkdirSync(PATHS.config, { recursive: true })
    writeFileSync(PATHS.themeConfigFilePath, JSON.stringify(config, null, 2), 'utf-8')
  },

  getTTSConfig: () => loadConfig().tts,
  setTTSConfig: (updates: Partial<AppConfig['tts']>): void => {
    const config = loadConfig()
    config.tts = { ...config.tts, ...updates }
    saveConfig(config)
  },

  getSTTConfig: () => loadConfig().stt,
  setSTTConfig: (updates: Partial<AppConfig['stt']>): void => {
    const config = loadConfig()
    config.stt = { ...config.stt, ...updates }
    saveConfig(config)
  },

  getWindowState: (): WindowBounds => loadConfig().window,
  setWindowState: (state: WindowBounds): void => {
    configStore.set('window', state)
  },

  getWelcomeCompleted: (): boolean => loadConfig().welcomeCompleted,
  setWelcomeCompleted: (value: boolean): void => {
    configStore.set('welcomeCompleted', value)
  },

  getCloseToTrayPrompted: (): boolean => loadConfig().closeToTrayPrompted,
  setCloseToTrayPrompted: (value: boolean): void => {
    configStore.set('closeToTrayPrompted', value)
  },

  getLocale: (): string => loadConfig().locale,
  setLocale: (locale: string): void => {
    configStore.set('locale', locale)
  },

  getCloudConfig: (): CloudConfig => loadConfig().cloud,
  setCloudRoutingMode: (mode: CloudRoutingMode): void => {
    const config = loadConfig()
    config.cloud = { ...config.cloud, routingMode: mode }
    saveConfig(config)
  },

  getAll: (): AppConfig => loadConfig(),

  reset: (): void => {
    cachedConfig = { ...DEFAULT_CONFIG }
    saveConfig(cachedConfig)
  },
}

export type { AppConfig, WindowBounds, CloudConfig }
