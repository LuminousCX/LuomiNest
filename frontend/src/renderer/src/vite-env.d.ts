/// <reference types="vite/client" />

export interface TabInfo {
  id: string
  title: string
  url: string
  active: boolean
  loading?: boolean
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
  playwright: {
    createTab: (url?: string) => Promise<TabInfo>
    closeTab: (tabId: string) => Promise<void>
    navigate: (tabId: string, url: string) => Promise<TabInfo>
    executeScript: (tabId: string, script: string) => Promise<any>
    clickElement: (tabId: string, selector: string) => Promise<void>
    fillForm: (tabId: string, selector: string, value: string) => Promise<void>
    screenshot: (tabId: string) => Promise<string>
    getDom: (tabId: string) => Promise<string>
    getAllTabs: () => Promise<TabInfo[]>
  }
  cdp: {
    listTargets: () => Promise<any[]>
    sendCommand: (targetId: string, method: string, params?: Record<string, any>) => Promise<any>
  }
  tab: {
    createManaged: (url?: string) => Promise<TabInfo>
    activate: (tabId: string) => Promise<void>
    closeManaged: (tabId: string) => Promise<void>
    getAll: () => Promise<TabInfo[]>
    getActive: () => Promise<TabInfo | undefined>
    hideAll: () => Promise<void>
    cleanupAll: () => Promise<void>
    getCookies: () => Promise<Electron.Cookie[]>
    clearBrowserData: () => Promise<void>
    setBoundsConfig: (config: { sidebarWidth?: number; devPanelHeight?: number }) => Promise<void>
  }
}

declare global {
  interface Window {
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
