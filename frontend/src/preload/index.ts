import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron'
import { DesktopPetIpcChannels, IpcChannels } from '@shared/ipc-types'
import type {
  TTSConfig,
  STTConfig,
  PetModelInfo,
  BrowserAutomationAction,
  BackendStageEvent,
  ThemeConfig,
  ElectronApi,
  IpcInvokeChannel,
  IpcSendChannel,
} from '@shared/ipc-types'

export interface Tab {
  id: string
  title: string
  url: string
  favicon?: string
  loading?: boolean
  error?: { code: number; title: string; message: string }
  active?: boolean
}

/**
 * invoke 通道收窄：仅接受 IpcChannels 登记的 invoke 通道，手写未登记的
 * channel 字符串会编译报错，与 main 侧 handleIpc 保持同一常量来源。
 * 返回类型 R 由 api 对象的 ElectronApi 上下文推断。
 */
const invoke = <C extends IpcInvokeChannel, R>(channel: C, ...args: unknown[]): Promise<R> =>
  ipcRenderer.invoke(channel, ...args) as Promise<R>

/** send 通道收窄（renderer → main 单向），与 main 侧 onIpc 保持同一常量来源 */
const send = <C extends IpcSendChannel>(channel: C, ...args: unknown[]): void => {
  ipcRenderer.send(channel, ...args)
}

const api: ElectronApi = {
  window: {
    minimize: () => invoke(IpcChannels.window.invoke.minimize),
    maximize: () => invoke(IpcChannels.window.invoke.maximize),
    close: () => invoke(IpcChannels.window.invoke.close),
    isMaximized: () => invoke(IpcChannels.window.invoke.isMaximized)
  },

  app: {
    getVersion: () => invoke(IpcChannels.app.invoke.getVersion),
    getName: () => invoke(IpcChannels.app.invoke.getName),
    getPaths: () => invoke(IpcChannels.app.invoke.getPaths),
    getWelcomeCompleted: () => invoke(IpcChannels.app.invoke.getWelcomeCompleted),
    setWelcomeCompleted: (value: boolean) => invoke(IpcChannels.app.invoke.setWelcomeCompleted, value),
  },

  auth: {
    getToken: () => invoke(IpcChannels.auth.invoke.getToken),
  },

  config: {
    getTheme: () => invoke(IpcChannels.config.invoke.getTheme),
    setTheme: (theme: 'light' | 'dark' | 'system') => invoke(IpcChannels.config.invoke.setTheme, theme),
    getThemeConfig: () => invoke(IpcChannels.config.invoke.getThemeConfig),
    setThemeConfig: (config: ThemeConfig) => invoke(IpcChannels.config.invoke.setThemeConfig, config),
    getTTS: () => invoke(IpcChannels.config.invoke.getTTS),
    setTTS: (updates: Partial<TTSConfig>) => invoke(IpcChannels.config.invoke.setTTS, updates),
    getSTT: () => invoke(IpcChannels.config.invoke.getSTT),
    setSTT: (updates: Partial<STTConfig>) => invoke(IpcChannels.config.invoke.setSTT, updates),
    getLocale: () => invoke(IpcChannels.config.invoke.getLocale),
    setLocale: (locale: string) => invoke(IpcChannels.config.invoke.setLocale, locale),
    getAll: () => invoke(IpcChannels.config.invoke.getAll),
  },

  cache: {
    getSize: () => invoke(IpcChannels.cache.invoke.getSize),
    getBreakdown: () => invoke(IpcChannels.cache.invoke.getBreakdown),
    clearAll: () => invoke(IpcChannels.cache.invoke.clearAll),
    clearDir: (dirName: string) => invoke(IpcChannels.cache.invoke.clearDir, dirName),
  },

  tab: {
    create: (url?: string) => invoke(IpcChannels.tab.invoke.create, url),
    activate: (tabId: string) => invoke(IpcChannels.tab.invoke.activate, tabId),
    close: (tabId: string) => invoke(IpcChannels.tab.invoke.close, tabId),
    getAll: () => invoke(IpcChannels.tab.invoke.getAll),
    getActive: () => invoke(IpcChannels.tab.invoke.getActive),
    reload: (tabId?: string) => invoke(IpcChannels.tab.invoke.reload, tabId),
    navigate: (url: string, tabId?: string) => invoke(IpcChannels.tab.invoke.navigate, url, tabId),
    goBack: (tabId?: string) => invoke(IpcChannels.tab.invoke.goBack, tabId),
    goForward: (tabId?: string) => invoke(IpcChannels.tab.invoke.goForward, tabId),
    getNavigationState: (tabId?: string) => invoke(IpcChannels.tab.invoke.getNavigationState, tabId),
    hideAll: () => invoke(IpcChannels.tab.invoke.hideAll),
    showActive: () => invoke(IpcChannels.tab.invoke.showActive),
    setBoundsConfig: (config: { sidebarWidth?: number; devPanelHeight?: number }) =>
      invoke(IpcChannels.tab.invoke.setBoundsConfig, config),
    cleanup: () => invoke(IpcChannels.tab.invoke.cleanup),
    getCookies: () => invoke(IpcChannels.tab.invoke.getCookies),
    clearData: () => invoke(IpcChannels.tab.invoke.clearData)
  },

  browserSearch: {
    search: (query: string) => invoke(IpcChannels.browser.invoke.search, query),
    fetchUrl: (url: string) => invoke(IpcChannels.browser.invoke.fetchUrl, url)
  },

  browserAutomation: {
    execute: (action: BrowserAutomationAction, args?: Record<string, unknown>) =>
      invoke(IpcChannels.browser.invoke.automation, action, args || {})
  },

  avatar: {
    importModel: () => invoke(IpcChannels.avatar.invoke.importModel),
    listImportedModels: () => invoke(IpcChannels.avatar.invoke.listImportedModels),
    deleteModel: (modelName: string) => invoke(IpcChannels.avatar.invoke.deleteModel, modelName),
    getImportedModelsPath: () => invoke(IpcChannels.avatar.invoke.getImportedModelsPath),
    getCollaboratorAvatar: (key: string) => invoke(IpcChannels.avatar.invoke.getCollaboratorAvatar, key),
    updateCollaboratorAvatars: () => invoke(IpcChannels.avatar.invoke.updateCollaboratorAvatars),
  },

  desktopPet: {
    open: (modelInfo?: PetModelInfo) => invoke(IpcChannels.desktopPet.invoke.open, modelInfo),
    close: () => invoke(IpcChannels.desktopPet.invoke.close),
    isRunning: () => invoke(IpcChannels.desktopPet.invoke.isRunning),
    loadModel: (modelInfo: PetModelInfo) => invoke(IpcChannels.desktopPet.invoke.loadModel, modelInfo),
    show: () => invoke(IpcChannels.desktopPet.invoke.show),
    hide: () => invoke(IpcChannels.desktopPet.invoke.hide),
    triggerMotion: (group: string, index: number) => invoke(IpcChannels.desktopPet.invoke.triggerMotion, group, index),
    triggerExpression: (name: string) => invoke(IpcChannels.desktopPet.invoke.triggerExpression, name),
    setPosition: (x: number, y: number) => invoke(IpcChannels.desktopPet.invoke.setPosition, x, y),
    setScale: (scale: number) => invoke(IpcChannels.desktopPet.invoke.setScale, scale),
    driveLipSync: (value: number) => invoke(IpcChannels.desktopPet.invoke.driveLipSync, value),
    drivePadEmotion: (pleasure: number, arousal: number, dominance: number) =>
      invoke(IpcChannels.desktopPet.invoke.drivePadEmotion, pleasure, arousal, dominance),
    setCoreParam: (paramId: string, value: number) =>
      invoke(IpcChannels.desktopPet.invoke.setCoreParam, paramId, value),
    getModelCapabilities: () => invoke(IpcChannels.desktopPet.invoke.getModelCapabilities),
    sendSubtitle: (text: string) => invoke(IpcChannels.desktopPet.invoke.sendSubtitle, text),
    hideSubtitle: () => invoke(IpcChannels.desktopPet.invoke.hideSubtitle),
    setStreamingState: (isStreaming: boolean) => invoke(IpcChannels.desktopPet.invoke.setStreamingState, isStreaming),
  },

  // 桌宠窗口内的聊天：桌宠窗口 → 主进程 → 主应用窗口
  // 主应用窗口通过 onDesktopPetChatMessage / onDesktopPetChatCancel 监听。
  desktopPetChat: {
    sendMessage: (text: string) => send(IpcChannels.desktopPet.send.sendChatMessage, text),
    cancel: () => send(IpcChannels.desktopPet.send.cancelChat),
  },

  dialog: {
    selectBackgroundImage: () => invoke(IpcChannels.dialog.invoke.selectBackgroundImage),
    deleteBackgroundImage: (imageUrl: string) => invoke(IpcChannels.dialog.invoke.deleteBackgroundImage, imageUrl),
  },

  // 主应用窗口监听桌宠窗口转发的聊天请求
  onDesktopPetChatMessage: (callback: (text: string) => void): (() => void) => {
    const handler = (_event: IpcRendererEvent, text: string) => callback(text)
    ipcRenderer.on(IpcChannels.desktopPet.push.chatMessage, handler)
    return () => ipcRenderer.removeListener(IpcChannels.desktopPet.push.chatMessage, handler as never)
  },

  onDesktopPetChatCancel: (callback: () => void): (() => void) => {
    const handler = () => callback()
    ipcRenderer.on(IpcChannels.desktopPet.push.chatCancel, handler)
    return () => ipcRenderer.removeListener(IpcChannels.desktopPet.push.chatCancel, handler as never)
  },

  backend: {
    subscribeStage: (callback: (data: BackendStageEvent) => void): (() => void) => {
      const handler = (_event: IpcRendererEvent, data: BackendStageEvent) => callback(data)
      ipcRenderer.on(IpcChannels.backend.push.stage, handler)
      invoke(IpcChannels.backend.invoke.subscribe).catch((err: unknown) => {
        console.error('[Preload] Failed to subscribe to backend stage:', err)
      })
      return () => ipcRenderer.removeListener(IpcChannels.backend.push.stage, handler as never)
    }
  }
}

const ALLOWED_SEND_CHANNELS: Set<string> = new Set(DesktopPetIpcChannels.SEND)

const ALLOWED_ON_CHANNELS: Set<string> = new Set(DesktopPetIpcChannels.ON)

const electronBridge = {
  ipcRenderer: {
    on: (channel: string, listener: (event: IpcRendererEvent, ...args: unknown[]) => void) => {
      if (ALLOWED_ON_CHANNELS.has(channel)) {
        ipcRenderer.on(channel, listener)
      } else {
        console.warn(`[Preload] Blocked ipcRenderer.on for unlisted channel: ${channel}`)
      }
    },
    removeListener: (channel: string, listener: (event: IpcRendererEvent, ...args: unknown[]) => void) => {
      if (ALLOWED_ON_CHANNELS.has(channel)) {
        ipcRenderer.removeListener(channel, listener as never)
      }
    },
    send: (channel: string, ...args: unknown[]) => {
      if (ALLOWED_SEND_CHANNELS.has(channel)) {
        // 白名单桥的底层实现必须直连 ipcRenderer.send（动态 channel，不走常量收窄）
        ipcRenderer.send(channel, ...args)
      } else {
        console.warn(`[Preload] Blocked ipcRenderer.send for unlisted channel: ${channel}`)
      }
    }
  }
}

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('api', api)
    contextBridge.exposeInMainWorld('electron', electronBridge)
  } catch (error) {
    console.error('[ERROR][LuomiNestPreload] Failed to expose electron bridge:', error)
  }
} else {
  const globalObj = globalThis as Record<string, unknown>
  globalObj.api = api
  globalObj.electron = electronBridge
}
