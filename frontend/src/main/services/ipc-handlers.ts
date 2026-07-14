import { ipcMain, BrowserWindow, IpcMainInvokeEvent, app } from 'electron'
import { PATHS } from './paths'
import { configStore } from './config-store'
import { cacheManager } from './cache-manager'
import { tabManager, luomiAutomationExecutor } from './browser'
import { getLumiAuthToken } from './backend/auth-token'
import { subscribeBackendStage } from './backend'
import type { TTSConfig, STTConfig } from '@shared/ipc-types'

let _mainWindow: BrowserWindow | null = null

export function setMainWindow(win: BrowserWindow | null): void {
  _mainWindow = win
}

function getMainWindow(): BrowserWindow | null {
  return _mainWindow
}

export function registerIpcHandlers(mainWindow: BrowserWindow | null): void {
  setMainWindow(mainWindow)

  const assertTrustedSender = (event: IpcMainInvokeEvent): boolean => {
    const win = getMainWindow()
    if (!win || event.sender !== win.webContents) {
      return false
    }
    return true
  }

  ipcMain.handle('window:minimize', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    getMainWindow()?.minimize()
  })
  ipcMain.handle('window:maximize', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    const win = getMainWindow()
    if (win?.isMaximized()) {
      win.unmaximize()
    } else {
      win?.maximize()
    }
  })
  ipcMain.handle('window:close', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    getMainWindow()?.close()
  })
  ipcMain.handle('window:isMaximized', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return false
    return getMainWindow()?.isMaximized() ?? false
  })

  ipcMain.handle('app:getVersion', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return app.getVersion()
  })
  ipcMain.handle('app:getName', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return app.getName()
  })

  ipcMain.handle('app:getPaths', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return {
      userData: PATHS.userData,
      cache: PATHS.cache,
      data: PATHS.data,
      config: PATHS.config,
      logs: PATHS.logs,
      live2d: PATHS.live2d,
    }
  })

  ipcMain.handle('app:getWelcomeCompleted', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return configStore.getWelcomeCompleted()
  })

  ipcMain.handle('app:setWelcomeCompleted', (event: IpcMainInvokeEvent, value: boolean) => {
    if (!assertTrustedSender(event)) return
    if (typeof value !== 'boolean') return
    configStore.setWelcomeCompleted(value)
  })

  ipcMain.handle('auth:getToken', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return getLumiAuthToken()
  })

  ipcMain.handle('config:getTheme', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return configStore.getTheme()
  })
  ipcMain.handle('config:setTheme', (event: IpcMainInvokeEvent, theme: 'light' | 'dark' | 'system') => {
    if (!assertTrustedSender(event)) return
    configStore.setTheme(theme)
  })
  ipcMain.handle('config:getTTS', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return configStore.getTTSConfig()
  })
  ipcMain.handle('config:setTTS', (event: IpcMainInvokeEvent, updates: Partial<TTSConfig>) => {
    if (!assertTrustedSender(event)) return
    configStore.setTTSConfig(updates)
  })
  ipcMain.handle('config:getSTT', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return configStore.getSTTConfig()
  })
  ipcMain.handle('config:setSTT', (event: IpcMainInvokeEvent, updates: Partial<STTConfig>) => {
    if (!assertTrustedSender(event)) return
    configStore.setSTTConfig(updates)
  })
  ipcMain.handle('config:getAll', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return configStore.getAll()
  })

  ipcMain.handle('cache:getSize', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return cacheManager.getCacheSizeMB()
  })
  ipcMain.handle('cache:getBreakdown', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return cacheManager.getCacheBreakdown()
  })
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
  ipcMain.handle('tab:getAll', async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return tabManager.getAllTabs()
  })
  ipcMain.handle('tab:getActive', async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return tabManager.getActiveTab()
  })
  ipcMain.handle('tab:reload', async (event: IpcMainInvokeEvent, tabId?: string) => {
    if (!assertTrustedSender(event)) return
    return tabManager.reloadTab(tabId)
  })
  ipcMain.handle('tab:navigate', async (event: IpcMainInvokeEvent, url: string, tabId?: string) => {
    if (!assertTrustedSender(event)) return
    return tabManager.navigateTo(url, tabId)
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
    return await browserSearch(query, getMainWindow())
  })

  ipcMain.handle('browser:fetchUrl', async (event: IpcMainInvokeEvent, url: string) => {
    if (!assertTrustedSender(event)) return
    if (typeof url !== 'string' || !url.trim()) return
    const { fetchUrl } = await import('./browser')
    return await fetchUrl(url, getMainWindow())
  })

  ipcMain.handle('browser:automation', async (event: IpcMainInvokeEvent, action: string, args: Record<string, any>) => {
    if (!assertTrustedSender(event)) {
      return { success: false, error: '未授权的调用方' }
    }
    if (typeof action !== 'string' || !action) {
      return { success: false, error: '缺少 action 参数' }
    }
    return await luomiAutomationExecutor.execute(action, args || {})
  })

  ipcMain.handle('backend:subscribe', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    const win = event.sender
    const unsubscribe = subscribeBackendStage((stage, detail) => {
      if (!win.isDestroyed()) {
        win.send('backend:stage', { stage, detail })
      }
    })
    win.once('destroyed', () => unsubscribe())
  })
}
