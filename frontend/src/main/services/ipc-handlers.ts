import { ipcMain, BrowserWindow, IpcMainInvokeEvent } from 'electron'
import { PATHS } from './paths'
import { configStore } from './config-store'
import { cacheManager } from './cache-manager'
import { tabManager } from './browser'

export function registerIpcHandlers(mainWindow: BrowserWindow | null): void {
  const assertTrustedSender = (event: IpcMainInvokeEvent): boolean => {
    if (!mainWindow || event.sender !== mainWindow.webContents) {
      return false
    }
    return true
  }

  ipcMain.handle('window:minimize', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    mainWindow?.minimize()
  })
  ipcMain.handle('window:maximize', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize()
    } else {
      mainWindow?.maximize()
    }
  })
  ipcMain.handle('window:close', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    mainWindow?.close()
  })
  ipcMain.handle('window:isMaximized', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return false
    return mainWindow?.isMaximized() ?? false
  })

  ipcMain.handle('app:getVersion', () => require('electron').app.getVersion())
  ipcMain.handle('app:getName', () => require('electron').app.getName())

  ipcMain.handle('app:getPaths', () => ({
    userData: PATHS.userData,
    cache: PATHS.cache,
    data: PATHS.data,
    config: PATHS.config,
    logs: PATHS.logs,
    live2d: PATHS.live2d,
  }))

  ipcMain.handle('config:getTheme', () => configStore.getTheme())
  ipcMain.handle('config:setTheme', (event: IpcMainInvokeEvent, theme: 'light' | 'dark' | 'system') => {
    if (!assertTrustedSender(event)) return
    configStore.setTheme(theme)
  })
  ipcMain.handle('config:getTTS', () => configStore.getTTSConfig())
  ipcMain.handle('config:setTTS', (event: IpcMainInvokeEvent, updates: any) => {
    if (!assertTrustedSender(event)) return
    configStore.setTTSConfig(updates)
  })
  ipcMain.handle('config:getSTT', () => configStore.getSTTConfig())
  ipcMain.handle('config:setSTT', (event: IpcMainInvokeEvent, updates: any) => {
    if (!assertTrustedSender(event)) return
    configStore.setSTTConfig(updates)
  })
  ipcMain.handle('config:getAll', () => configStore.getAll())

  ipcMain.handle('cache:getSize', () => cacheManager.getCacheSizeMB())
  ipcMain.handle('cache:getBreakdown', () => cacheManager.getCacheBreakdown())
  ipcMain.handle('cache:clearAll', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return false
    cacheManager.clearAllCache()
    return true
  })
  ipcMain.handle('cache:clearDir', (event: IpcMainInvokeEvent, dirName: string) => {
    if (!assertTrustedSender(event)) return false
    if (typeof dirName !== 'string' || !dirName.trim()) return false
    cacheManager.clearCacheDir(dirName)
  })

  ipcMain.handle('tab:create', async (event: IpcMainInvokeEvent, url?: string) => {
    if (!assertTrustedSender(event)) return
    return tabManager.createTab(url)
  })
  ipcMain.handle('tab:activate', async (event: IpcMainInvokeEvent, tabId: string) => {
    if (!assertTrustedSender(event)) return
    if (typeof tabId !== 'string' || !tabId.trim()) return
    return tabManager.activateTab(tabId)
  })
  ipcMain.handle('tab:close', async (event: IpcMainInvokeEvent, tabId: string) => {
    if (!assertTrustedSender(event)) return
    if (typeof tabId !== 'string' || !tabId.trim()) return
    return tabManager.closeTab(tabId)
  })
  ipcMain.handle('tab:getAll', async () => {
    return tabManager.getAllTabs()
  })
  ipcMain.handle('tab:getActive', async () => {
    return tabManager.getActiveTab()
  })
  ipcMain.handle('tab:reload', async (event: IpcMainInvokeEvent, tabId?: string) => {
    if (!assertTrustedSender(event)) return
    return tabManager.reloadTab(tabId)
  })
  ipcMain.handle('tab:goBack', async (event: IpcMainInvokeEvent, tabId?: string) => {
    if (!assertTrustedSender(event)) return
    return tabManager.goBack(tabId)
  })
  ipcMain.handle('tab:goForward', async (event: IpcMainInvokeEvent, tabId?: string) => {
    if (!assertTrustedSender(event)) return
    return tabManager.goForward(tabId)
  })
  ipcMain.handle('tab:getNavigationState', async (event: IpcMainInvokeEvent, tabId?: string) => {
    if (!assertTrustedSender(event)) return
    return tabManager.getNavigationState(tabId)
  })
  ipcMain.handle('tab:hideAll', async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    return tabManager.hideAll()
  })
  ipcMain.handle('tab:showActive', async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    return tabManager.showActive()
  })
  ipcMain.handle('tab:setBoundsConfig', async (event: IpcMainInvokeEvent, config) => {
    if (!assertTrustedSender(event)) return
    return tabManager.setBoundsConfig(config)
  })
  ipcMain.handle('tab:cleanup', async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    return tabManager.cleanup()
  })
  ipcMain.handle('tab:getCookies', async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    const { getCookies } = await import('./browser')
    return getCookies()
  })
  ipcMain.handle('tab:clearData', async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    const { clearBrowserData } = await import('./browser')
    return clearBrowserData()
  })

  ipcMain.handle('browser:search', async (event: IpcMainInvokeEvent, query: string) => {
    if (!assertTrustedSender(event)) return
    if (typeof query !== 'string' || !query.trim()) return
    const { browserSearch } = await import('./browser')
    return await browserSearch(query, mainWindow)
  })
}
