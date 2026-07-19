import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron'
import { DesktopPetIpcChannels } from '@shared/ipc-types'
import type {
  TTSConfig,
  STTConfig,
  PetModelInfo,
  BrowserAutomationAction,
  BackendStageEvent,
  ThemeConfig,
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

const api = {
  window: {
    minimize: () => ipcRenderer.invoke('window:minimize'),
    maximize: () => ipcRenderer.invoke('window:maximize'),
    close: () => ipcRenderer.invoke('window:close'),
    isMaximized: () => ipcRenderer.invoke('window:isMaximized')
  },

  app: {
    getVersion: () => ipcRenderer.invoke('app:getVersion'),
    getName: () => ipcRenderer.invoke('app:getName'),
    getPaths: () => ipcRenderer.invoke('app:getPaths'),
    getWelcomeCompleted: () => ipcRenderer.invoke('app:getWelcomeCompleted'),
    setWelcomeCompleted: (value: boolean) => ipcRenderer.invoke('app:setWelcomeCompleted', value),
  },

  auth: {
    getToken: () => ipcRenderer.invoke('auth:getToken'),
  },

  config: {
    getTheme: () => ipcRenderer.invoke('config:getTheme'),
    setTheme: (theme: 'light' | 'dark' | 'system') => ipcRenderer.invoke('config:setTheme', theme),
    getThemeConfig: () => ipcRenderer.invoke('config:getThemeConfig'),
    setThemeConfig: (config: ThemeConfig) => ipcRenderer.invoke('config:setThemeConfig', config),
    getTTS: () => ipcRenderer.invoke('config:getTTS'),
    setTTS: (updates: Partial<TTSConfig>) => ipcRenderer.invoke('config:setTTS', updates),
    getSTT: () => ipcRenderer.invoke('config:getSTT'),
    setSTT: (updates: Partial<STTConfig>) => ipcRenderer.invoke('config:setSTT', updates),
    getAll: () => ipcRenderer.invoke('config:getAll'),
  },

  cache: {
    getSize: () => ipcRenderer.invoke('cache:getSize'),
    getBreakdown: () => ipcRenderer.invoke('cache:getBreakdown'),
    clearAll: () => ipcRenderer.invoke('cache:clearAll'),
    clearDir: (dirName: string) => ipcRenderer.invoke('cache:clearDir', dirName),
  },

  tab: {
    create: (url?: string) => ipcRenderer.invoke('tab:create', url),
    activate: (tabId: string) => ipcRenderer.invoke('tab:activate', tabId),
    close: (tabId: string) => ipcRenderer.invoke('tab:close', tabId),
    getAll: () => ipcRenderer.invoke('tab:getAll'),
    getActive: () => ipcRenderer.invoke('tab:getActive'),
    reload: (tabId?: string) => ipcRenderer.invoke('tab:reload', tabId),
    navigate: (url: string, tabId?: string) => ipcRenderer.invoke('tab:navigate', url, tabId),
    goBack: (tabId?: string) => ipcRenderer.invoke('tab:goBack', tabId),
    goForward: (tabId?: string) => ipcRenderer.invoke('tab:goForward', tabId),
    getNavigationState: (tabId?: string) => ipcRenderer.invoke('tab:getNavigationState', tabId),
    hideAll: () => ipcRenderer.invoke('tab:hideAll'),
    showActive: () => ipcRenderer.invoke('tab:showActive'),
    setBoundsConfig: (config: { sidebarWidth?: number; devPanelHeight?: number }) =>
      ipcRenderer.invoke('tab:setBoundsConfig', config),
    cleanup: () => ipcRenderer.invoke('tab:cleanup'),
    getCookies: () => ipcRenderer.invoke('tab:getCookies'),
    clearData: () => ipcRenderer.invoke('tab:clearData')
  },

  browserSearch: {
    search: (query: string) => ipcRenderer.invoke('browser:search', query),
    fetchUrl: (url: string) => ipcRenderer.invoke('browser:fetchUrl', url)
  },

  browserAutomation: {
    execute: (action: BrowserAutomationAction, args?: Record<string, unknown>) =>
      ipcRenderer.invoke('browser:automation', action, args || {})
  },

  avatar: {
    importModel: () => ipcRenderer.invoke('avatar:importModel'),
    listImportedModels: () => ipcRenderer.invoke('avatar:listImportedModels'),
    deleteModel: (modelName: string) => ipcRenderer.invoke('avatar:deleteModel', modelName),
    getImportedModelsPath: () => ipcRenderer.invoke('avatar:getImportedModelsPath')
  },

  desktopPet: {
    open: (modelInfo?: PetModelInfo) => ipcRenderer.invoke('desktop-pet:open', modelInfo),
    close: () => ipcRenderer.invoke('desktop-pet:close'),
    isRunning: () => ipcRenderer.invoke('desktop-pet:isRunning'),
    loadModel: (modelInfo: PetModelInfo) => ipcRenderer.invoke('desktop-pet:loadModel', modelInfo),
    show: () => ipcRenderer.invoke('desktop-pet:show'),
    hide: () => ipcRenderer.invoke('desktop-pet:hide'),
    triggerMotion: (group: string, index: number) => ipcRenderer.invoke('desktop-pet:triggerMotion', group, index),
    triggerExpression: (name: string) => ipcRenderer.invoke('desktop-pet:triggerExpression', name),
    setPosition: (x: number, y: number) => ipcRenderer.invoke('desktop-pet:setPosition', x, y),
    setScale: (scale: number) => ipcRenderer.invoke('desktop-pet:setScale', scale),
    driveLipSync: (value: number) => ipcRenderer.invoke('desktop-pet:driveLipSync', value),
    drivePadEmotion: (pleasure: number, arousal: number, dominance: number) =>
      ipcRenderer.invoke('desktop-pet:drivePadEmotion', pleasure, arousal, dominance),
    setCoreParam: (paramId: string, value: number) =>
      ipcRenderer.invoke('desktop-pet:setCoreParam', paramId, value),
    getModelCapabilities: () => ipcRenderer.invoke('desktop-pet:getModelCapabilities'),
    sendSubtitle: (text: string) => ipcRenderer.invoke('desktop-pet:sendSubtitle', text),
    hideSubtitle: () => ipcRenderer.invoke('desktop-pet:hideSubtitle'),
    setStreamingState: (isStreaming: boolean) => ipcRenderer.invoke('desktop-pet:setStreamingState', isStreaming),
  },

  // 桌宠窗口内的聊天：桌宠窗口 → 主进程 → 主应用窗口
  // 主应用窗口通过 onDesktopPetChatMessage / onDesktopPetChatCancel 监听。
  desktopPetChat: {
    sendMessage: (text: string) => ipcRenderer.send('desktop-pet:send-chat-message', text),
    cancel: () => ipcRenderer.send('desktop-pet:cancel-chat'),
  },

  dialog: {
    selectBackgroundImage: () => ipcRenderer.invoke('dialog:selectBackgroundImage'),
  },

  // 主应用窗口监听桌宠窗口转发的聊天请求
  onDesktopPetChatMessage: (callback: (text: string) => void): (() => void) => {
    const handler = (_event: IpcRendererEvent, text: string) => callback(text)
    ipcRenderer.on('desktop-pet:chat-message', handler)
    return () => ipcRenderer.removeListener('desktop-pet:chat-message', handler as never)
  },

  onDesktopPetChatCancel: (callback: () => void): (() => void) => {
    const handler = () => callback()
    ipcRenderer.on('desktop-pet:chat-cancel', handler)
    return () => ipcRenderer.removeListener('desktop-pet:chat-cancel', handler as never)
  },

  backend: {
    subscribeStage: (callback: (data: BackendStageEvent) => void): (() => void) => {
      const handler = (_event: IpcRendererEvent, data: BackendStageEvent) => callback(data)
      ipcRenderer.on('backend:stage', handler)
      ipcRenderer.invoke('backend:subscribe').catch((err: unknown) => {
        console.error('[Preload] Failed to subscribe to backend stage:', err)
      })
      return () => ipcRenderer.removeListener('backend:stage', handler as never)
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
