import { contextBridge, ipcRenderer } from 'electron'

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
  },

  auth: {
    getToken: () => ipcRenderer.invoke('auth:getToken'),
  },

  config: {
    getTheme: () => ipcRenderer.invoke('config:getTheme'),
    setTheme: (theme: 'light' | 'dark' | 'system') => ipcRenderer.invoke('config:setTheme', theme),
    getTTS: () => ipcRenderer.invoke('config:getTTS'),
    setTTS: (updates: any) => ipcRenderer.invoke('config:setTTS', updates),
    getSTT: () => ipcRenderer.invoke('config:getSTT'),
    setSTT: (updates: any) => ipcRenderer.invoke('config:setSTT', updates),
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
    execute: (action: string, args?: Record<string, any>) =>
      ipcRenderer.invoke('browser:automation', action, args || {})
  },

  avatar: {
    importModel: () => ipcRenderer.invoke('avatar:importModel'),
    listImportedModels: () => ipcRenderer.invoke('avatar:listImportedModels'),
    deleteModel: (modelName: string) => ipcRenderer.invoke('avatar:deleteModel', modelName),
    getImportedModelsPath: () => ipcRenderer.invoke('avatar:getImportedModelsPath')
  },

  desktopPet: {
    open: (modelInfo?: any) => ipcRenderer.invoke('desktop-pet:open', modelInfo),
    close: () => ipcRenderer.invoke('desktop-pet:close'),
    isRunning: () => ipcRenderer.invoke('desktop-pet:isRunning'),
    loadModel: (modelInfo: any) => ipcRenderer.invoke('desktop-pet:loadModel', modelInfo),
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
    hideSubtitle: () => ipcRenderer.invoke('desktop-pet:hideSubtitle')
  },

  backend: {
    subscribeStage: (callback: (data: { stage: string; detail?: string }) => void): (() => void) => {
      const handler = (_event: unknown, data: { stage: string; detail?: string }) => callback(data)
      ipcRenderer.on('backend:stage', handler)
      ipcRenderer.invoke('backend:subscribe')
      return () => ipcRenderer.removeListener('backend:stage', handler)
    }
  }
}

const ALLOWED_SEND_CHANNELS = new Set([
  'desktop-pet:set-ignore-mouse-events',
  'desktop-pet:resize-window',
  'desktop-pet:start-drag',
  'desktop-pet:drag-window',
  'desktop-pet:end-drag',
  'desktop-pet:model-capabilities-response',
  'desktop-pet:show-context-menu',
])

const ALLOWED_ON_CHANNELS = new Set([
  'desktop-pet:load-model',
  'desktop-pet:trigger-motion',
  'desktop-pet:trigger-expression',
  'desktop-pet:lip-sync',
  'desktop-pet:pad-emotion',
  'desktop-pet:set-core-param',
  'desktop-pet:get-model-capabilities',
  'desktop-pet:subtitle',
  'desktop-pet:subtitle-hide',
  'backend:stage'
])

const electronBridge = {
  ipcRenderer: {
    on: (channel: string, listener: (event: any, ...args: any[]) => void) => {
      if (ALLOWED_ON_CHANNELS.has(channel)) {
        ipcRenderer.on(channel, listener)
      } else {
        console.warn(`[Preload] Blocked ipcRenderer.on for unlisted channel: ${channel}`)
      }
    },
    removeListener: (channel: string, listener: (...args: any[]) => void) => {
      if (ALLOWED_ON_CHANNELS.has(channel)) {
        ipcRenderer.removeListener(channel, listener)
      }
    },
    send: (channel: string, ...args: any[]) => {
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
  // @ts-ignore
  window.api = api
  // @ts-ignore
  window.electron = electronBridge
}
