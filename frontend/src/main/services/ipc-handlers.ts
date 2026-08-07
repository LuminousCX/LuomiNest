import { ipcMain, BrowserWindow, IpcMainInvokeEvent, app, dialog, type OpenDialogOptions, nativeImage } from 'electron'
import { PATHS } from './paths'
import { toBackgroundUrl } from './bg-protocol'
import { configStore } from './config-store'
import { cacheManager } from './cache-manager'
import { tabManager, luomiAutomationExecutor } from './browser'
import { getLumiAuthToken } from './backend/auth-token'
import { subscribeBackendStage } from './backend'
import { createLuomiNestLogger } from './luomi-logger'
import type { TTSConfig, STTConfig, ThemeConfig } from '@shared/ipc-types'
import * as fs from 'fs'
import * as path from 'path'

const logger = createLuomiNestLogger('IpcHandlers')

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
  ipcMain.handle('config:getThemeConfig', (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return null
    return configStore.getThemeConfig()
  })
  ipcMain.handle('config:setThemeConfig', (event: IpcMainInvokeEvent, config: ThemeConfig) => {
    if (!assertTrustedSender(event)) return
    configStore.setThemeConfig(config)
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

  ipcMain.handle('dialog:selectBackgroundImage', async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return { success: false, error: '未授权的调用方' }

    const parentWindow = getMainWindow()
    const dialogOptions: OpenDialogOptions = {
      title: '选择背景图片',
      properties: ['openFile'],
      filters: [{ name: '图片', extensions: ['jpg', 'jpeg', 'png', 'gif', 'webp'] }]
    }
    const result = parentWindow
      ? await dialog.showOpenDialog(parentWindow, dialogOptions)
      : await dialog.showOpenDialog(dialogOptions)
    if (result.canceled || result.filePaths.length === 0) {
      return { success: false, error: '用户取消选择' }
    }

    const sourcePath = result.filePaths[0]
    // 背景图片统一保存到用户数据目录（userData/Backgrounds），与安装目录隔离
    const bgDir = PATHS.backgrounds

    try {
      if (!fs.existsSync(sourcePath)) {
        return { success: false, error: '源文件不存在' }
      }

      const stats = fs.statSync(sourcePath)
      const MAX_BG_SIZE = 10 * 1024 * 1024 // 10MB
      if (!stats.isFile()) {
        return { success: false, error: '选择的不是文件' }
      }
      if (stats.size === 0) {
        return { success: false, error: '选择的文件为空' }
      }
      if (stats.size > MAX_BG_SIZE) {
        return { success: false, error: '图片大小超过 10MB 限制' }
      }

      // 扩展名 + MIME 双重校验
      const ext = path.extname(sourcePath).toLowerCase()
      const allowedExts = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
      if (!allowedExts.includes(ext)) {
        return { success: false, error: '不支持的图片格式，请选择 jpg/png/gif/webp' }
      }

      fs.mkdirSync(bgDir, { recursive: true })

      // 生成安全文件名：只保留中英文/数字/下划线/连字符，避免特殊字符导致协议或路径问题
      const rawBase = path.basename(sourcePath, ext)
        .replace(/[^\u4e00-\u9fa5a-zA-Z0-9_-]/g, '_')
        .slice(0, 40)
      const baseName = rawBase || 'upload'
      const destName = `bg-${baseName}-${Date.now()}${ext}`
      const destPath = path.join(bgDir, destName)

      // 若极短概率下文件名冲突，追加随机后缀
      let finalDestPath = destPath
      let finalDestName = destName
      if (fs.existsSync(finalDestPath)) {
        const randomSuffix = Math.random().toString(36).slice(2, 8)
        finalDestName = `bg-${baseName}-${Date.now()}-${randomSuffix}${ext}`
        finalDestPath = path.join(bgDir, finalDestName)
      }

      fs.copyFileSync(sourcePath, finalDestPath)
      logger.info(`[dialog:selectBackgroundImage] 背景图片已保存: ${finalDestPath}`)

      // 读取图片实际分辨率，过小则提示用户
      let width = 0
      let height = 0
      let warning: string | undefined
      try {
        const image = nativeImage.createFromPath(finalDestPath)
        const size = image.getSize()
        width = size.width
        height = size.height
        if (width < 1280 || height < 720) {
          warning = `图片分辨率较低（${width}×${height}），作为全屏背景可能会模糊，建议使用高清原图`
          logger.warn(`[dialog:selectBackgroundImage] ${warning}`)
        }
      } catch (err) {
        logger.warn('[dialog:selectBackgroundImage] 无法读取图片尺寸:', err)
      }

      return { success: true, url: toBackgroundUrl(finalDestName), width, height, warning }
    } catch (err) {
      const message = err instanceof Error ? err.message : '复制背景图片失败'
      logger.error('[dialog:selectBackgroundImage] 处理失败:', message)
      return { success: false, error: message }
    }
  })

  ipcMain.handle('dialog:deleteBackgroundImage', async (event: IpcMainInvokeEvent, imageUrl: string) => {
    if (!assertTrustedSender(event)) return { success: false, error: '未授权的调用方' }
    if (typeof imageUrl !== 'string' || !imageUrl.startsWith('luominest-bg://')) {
      return { success: false, error: '无效的背景图片地址' }
    }

    try {
      // 兼容旧的双斜杠格式与新三斜杠格式：统一移除协议前缀及所有前导斜杠
      const fileName = decodeURIComponent(
        imageUrl.replace(/^luominest-bg:\/+/, '').replace(/^bg\//, '')
      )
      if (!fileName) {
        return { success: false, error: '无效的文件名' }
      }
      const filePath = path.join(PATHS.backgrounds, fileName)
      const resolvedBgDir = path.resolve(PATHS.backgrounds)
      if (!filePath.startsWith(resolvedBgDir + path.sep)) {
        return { success: false, error: '非法的文件路径' }
      }
      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath)
        logger.info(`[dialog:deleteBackgroundImage] 背景图片已删除: ${filePath}`)
      }
      return { success: true }
    } catch (err) {
      const message = err instanceof Error ? err.message : '删除背景图片失败'
      logger.error('[dialog:deleteBackgroundImage] 处理失败:', message)
      return { success: false, error: message }
    }
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
