import { contextBridge, ipcRenderer } from 'electron'

export interface TabInfo {
  id: string
  title: string
  url: string
  active: boolean
  loading?: boolean
  error?: string
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
  playwright: {
    createTab: (url?: string) => ipcRenderer.invoke('playwright:createTab', url),
    closeTab: (tabId: string) => ipcRenderer.invoke('playwright:closeTab', tabId),
    navigate: (tabId: string, url: string) => ipcRenderer.invoke('playwright:navigate', tabId, url),
    executeScript: (tabId: string, script: string) => ipcRenderer.invoke('playwright:executeScript', tabId, script),
    clickElement: (tabId: string, selector: string) => ipcRenderer.invoke('playwright:clickElement', tabId, selector),
    fillForm: (tabId: string, selector: string, value: string) => ipcRenderer.invoke('playwright:fillForm', tabId, selector, value),
    screenshot: (tabId: string) => ipcRenderer.invoke('playwright:screenshot', tabId),
    getDom: (tabId: string) => ipcRenderer.invoke('playwright:getDom', tabId),
    getAllTabs: () => ipcRenderer.invoke('playwright:getAllTabs')
  },
  cdp: {
    listTargets: () => ipcRenderer.invoke('cdp:listTargets'),
    sendCommand: (targetId: string, method: string, params?: Record<string, any>) =>
      ipcRenderer.invoke('cdp:sendCommand', targetId, method, params)
  },
  tab: {
    createManaged: (url?: string) => ipcRenderer.invoke('tab:createManaged', url),
    activate: (tabId: string) => ipcRenderer.invoke('tab:activate', tabId),
    closeManaged: (tabId: string) => ipcRenderer.invoke('tab:closeManaged', tabId),
    getAll: () => ipcRenderer.invoke('tab:getAll'),
    getActive: () => ipcRenderer.invoke('tab:getActive'),
    hideAll: () => ipcRenderer.invoke('tab:hideAll'),
    cleanupAll: () => ipcRenderer.invoke('tab:cleanupAll'),
    getCookies: () => ipcRenderer.invoke('tab:getCookies'),
    clearBrowserData: () => ipcRenderer.invoke('tab:clearBrowserData'),
    setBoundsConfig: (config: { sidebarWidth?: number; devPanelHeight?: number }) =>
      ipcRenderer.invoke('tab:setBoundsConfig', config)
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
