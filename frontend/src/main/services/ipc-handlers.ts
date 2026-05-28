import { ipcMain, BrowserWindow } from 'electron'
import { PATHS } from './paths'
import { configStore } from './config-store'
import { cacheManager } from './cache-manager'
import { tabManager } from './browser'

export function registerIpcHandlers(mainWindow: BrowserWindow | null): void {
  ipcMain.handle('window:minimize', () => mainWindow?.minimize())
  ipcMain.handle('window:maximize', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize()
    } else {
      mainWindow?.maximize()
    }
  })
  ipcMain.handle('window:close', () => mainWindow?.close())
  ipcMain.handle('window:isMaximized', () => mainWindow?.isMaximized() ?? false)

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
  ipcMain.handle('config:setTheme', (_e, theme: 'light' | 'dark' | 'system') => configStore.setTheme(theme))
  ipcMain.handle('config:getTTS', () => configStore.getTTSConfig())
  ipcMain.handle('config:setTTS', (_e, updates: any) => configStore.setTTSConfig(updates))
  ipcMain.handle('config:getSTT', () => configStore.getSTTConfig())
  ipcMain.handle('config:setSTT', (_e, updates: any) => configStore.setSTTConfig(updates))
  ipcMain.handle('config:getAll', () => configStore.getAll())

  ipcMain.handle('cache:getSize', () => cacheManager.getCacheSizeMB())
  ipcMain.handle('cache:getBreakdown', () => cacheManager.getCacheBreakdown())
  ipcMain.handle('cache:clearAll', () => { cacheManager.clearAllCache(); return true })
  ipcMain.handle('cache:clearDir', (_e, dirName: string) => cacheManager.clearCacheDir(dirName))

  ipcMain.handle('tab:create', async (_e, url?: string) => {
    return tabManager.createTab(url)
  })
  ipcMain.handle('tab:activate', async (_e, tabId: string) => {
    return tabManager.activateTab(tabId)
  })
  ipcMain.handle('tab:close', async (_e, tabId: string) => {
    return tabManager.closeTab(tabId)
  })
  ipcMain.handle('tab:getAll', async () => {
    return tabManager.getAllTabs()
  })
  ipcMain.handle('tab:getActive', async () => {
    return tabManager.getActiveTab()
  })
  ipcMain.handle('tab:reload', async (_e, tabId?: string) => {
    return tabManager.reloadTab(tabId)
  })
  ipcMain.handle('tab:goBack', async (_e, tabId?: string) => {
    return tabManager.goBack(tabId)
  })
  ipcMain.handle('tab:goForward', async (_e, tabId?: string) => {
    return tabManager.goForward(tabId)
  })
  ipcMain.handle('tab:getNavigationState', async (_e, tabId?: string) => {
    return tabManager.getNavigationState(tabId)
  })
  ipcMain.handle('tab:hideAll', async () => {
    return tabManager.hideAll()
  })
  ipcMain.handle('tab:showActive', async () => {
    return tabManager.showActive()
  })
  ipcMain.handle('tab:setBoundsConfig', async (_e, config) => {
    return tabManager.setBoundsConfig(config)
  })
  ipcMain.handle('tab:cleanup', async () => {
    return tabManager.cleanup()
  })
  ipcMain.handle('tab:getCookies', async () => {
    const { getCookies } = await import('./browser')
    return getCookies()
  })
  ipcMain.handle('tab:clearData', async () => {
    const { clearBrowserData } = await import('./browser')
    return clearBrowserData()
  })

  ipcMain.handle('browser:search', async (_e, query: string) => {
    const { browserSearch } = await import('./browser')
    return await browserSearch(query, mainWindow)
  })
}
