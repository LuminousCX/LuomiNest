/// <reference types="vite/client" />

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

export interface TabErrorInfo {
  code: number
  title: string
  message: string
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
  avatar: {
    importModel: () => Promise<{
      success: boolean
      error?: string
      modelInfo?: {
        id: string
        name: string
        url: string
        scale: number
        type: string
        tags: string[]
      }
    }>
    listImportedModels: () => Promise<{
      id: string
      name: string
      url: string
      scale: number
      type: string
      tags: string[]
    }[]>
    deleteModel: (modelName: string) => Promise<{ success: boolean; error?: string }>
    getImportedModelsPath: () => Promise<string>
  }
  desktopPet: {
    open: (modelInfo?: { id: string; name: string; url: string; scale: number; type: string; tags: string[] }) => Promise<{ success: boolean }>
    close: () => Promise<{ success: boolean }>
    isRunning: () => Promise<boolean>
    loadModel: (modelInfo: { id: string; name: string; url: string; scale: number; type: string; tags: string[] }) => Promise<{ success: boolean; error?: string }>
    show: () => Promise<{ success: boolean }>
    hide: () => Promise<{ success: boolean }>
    triggerMotion: (group: string, index: number) => Promise<{ success: boolean }>
    triggerExpression: (name: string) => Promise<{ success: boolean }>
  }
}

declare global {
  interface Window {
    Live2DCubismCore: any
    api: ElectronApi
    electron?: {
      ipcRenderer: {
        on: (channel: string, listener: (event: any, ...args: any[]) => void) => void
        removeListener: (channel: string, listener: (...args: any[]) => void) => void
        send: (channel: string, ...args: any[]) => void
      }
    }
  }
}
