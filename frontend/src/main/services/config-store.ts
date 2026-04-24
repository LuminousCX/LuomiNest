import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs'
import { PATHS } from './paths'

interface WindowBounds {
  x?: number
  y?: number
  width: number
  height: number
  isMaximized: boolean
}

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
}

let cachedConfig: AppConfig | null = null

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

  getAll: (): AppConfig => loadConfig(),

  reset: (): void => {
    cachedConfig = { ...DEFAULT_CONFIG }
    saveConfig(cachedConfig)
  },
}

export type { AppConfig, WindowBounds }
