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
    getName: () => ipcRenderer.invoke('app:getName')
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
  }
}

const electronBridge = {
  ipcRenderer: {
    on: (channel: string, listener: (event: any, ...args: any[]) => void) => {
      ipcRenderer.on(channel, listener)
    },
    removeListener: (channel: string, listener: (...args: any[]) => void) => {
      ipcRenderer.removeListener(channel, listener)
    },
    send: (channel: string, ...args: any[]) => {
      ipcRenderer.send(channel, ...args)
    }
  }
}

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('api', api)
    contextBridge.exposeInMainWorld('electron', electronBridge)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore
  window.api = api
  // @ts-ignore
  window.electron = electronBridge
}
