import { app, BrowserWindow, ipcMain, shell, Menu, Tray, nativeImage, NativeImage, MenuItemConstructorOptions, dialog, protocol, screen } from 'electron'
import { join, dirname, basename } from 'path'
import { platform } from 'os'
import { copyFileSync, mkdirSync, existsSync, readdirSync, readFileSync, writeFileSync, rmSync, statSync } from 'fs'
import { tabManager } from './services/browser'
import { setupNetworkConfig } from './services/browser/view'
import { startBackend, stopBackend, getBackendUrl } from './services/backend'
import { PATHS, initAppPaths } from './services/paths'
import { configStore } from './services/config-store'
import { cacheManager } from './services/cache-manager'

if (platform() === 'win32') {
  process.stdout.write('\x1b[?65001h')
}

setupNetworkConfig()

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
let desktopPetWindow: BrowserWindow | null = null

const isDev = !app.isPackaged
const isMac = platform() === 'darwin'

const builtinBasePath = isDev
  ? join(app.getAppPath(), 'src/renderer/public/live2d')
  : join(process.resourcesPath, 'live2d')

const cubismCoreBasePath = isDev
  ? join(app.getAppPath(), 'resources/cubism-core')
  : join(process.resourcesPath, 'cubism-core')

interface ImportedModelRecord {
  id: string
  name: string
  url: string
  scale: number
  type: string
  tags: string[]
}

const loadImportedModels = (): ImportedModelRecord[] => {
  const filePath = PATHS.importedModelsPath
  if (!existsSync(filePath)) return []
  try {
    const data = readFileSync(filePath, 'utf-8')
    return JSON.parse(data) as ImportedModelRecord[]
  } catch {
    return []
  }
}

const saveImportedModels = (models: ImportedModelRecord[]): void => {
  mkdirSync(PATHS.live2d, { recursive: true })
  writeFileSync(PATHS.importedModelsPath, JSON.stringify(models, null, 2), 'utf-8')
}

const copyDirRecursive = (src: string, dst: string): void => {
  mkdirSync(dst, { recursive: true })
  const entries = readdirSync(src, { withFileTypes: true })
  for (const entry of entries) {
    const srcPath = join(src, entry.name)
    const dstPath = join(dst, entry.name)
    if (entry.isDirectory()) {
      copyDirRecursive(srcPath, dstPath)
    } else if (entry.isFile()) {
      copyFileSync(srcPath, dstPath)
    }
  }
}

const saveWindowState = (): void => {
  if (!mainWindow || mainWindow.isDestroyed()) return
  try {
    const bounds = mainWindow.getBounds()
    const isMaximized = mainWindow.isMaximized()
    configStore.setWindowState({
      x: bounds.x,
      y: bounds.y,
      width: bounds.width,
      height: bounds.height,
      isMaximized,
    })
  } catch {
  }
}

const createWindow = (): void => {
  const savedState = configStore.getWindowState()

  mainWindow = new BrowserWindow({
    width: savedState.width || 1280,
    height: savedState.height || 820,
    x: savedState.x,
    y: savedState.y,
    minWidth: 960,
    minHeight: 640,
    frame: false,
    titleBarStyle: 'hidden',
    titleBarOverlay: false,
    trafficLightPosition: { x: 12, y: 10 },
    backgroundColor: '#fafaf9',
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  if (savedState.isMaximized) {
    mainWindow.maximize()
  }

  tabManager.setWindow(mainWindow)

  tabManager.setCallbacks(
    (tabId, updates) => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('tab:updated', { tabId, updates })
      }
    },
    (event, data) => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send(`tab:${event}`, data)
      }
    }
  )

  mainWindow.on('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.on('resize', () => {
    tabManager.handleResize()
  })

  mainWindow.on('close', () => {
    saveWindowState()
  })

  mainWindow.webContents.setWindowOpenHandler((details: { url: string }) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  const CSP_DEV = "default-src 'self' luominest-avatar:; script-src 'self' 'unsafe-eval' luominest-avatar:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: https: http: blob: luominest-avatar:; connect-src 'self' blob: luominest-avatar: https://fonts.googleapis.com https://fonts.gstatic.com https: http: wss:; worker-src 'self' blob:"
  const CSP_PROD = "default-src 'self' luominest-avatar:; script-src 'self' luominest-avatar:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: https: http: blob: luominest-avatar:; connect-src 'self' blob: luominest-avatar: https://fonts.googleapis.com https://fonts.gstatic.com https: http: wss:; worker-src 'self' blob:"
  const CSP_POLICY = isDev ? CSP_DEV : CSP_PROD

  mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [CSP_POLICY]
      }
    })
  })

  if (isDev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

const createTray = (): void => {
  const iconPath = join(__dirname, '../../resources/icon.png')
  let icon: NativeImage
  try {
    icon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 })
  } catch {
    icon = nativeImage.createFromBuffer(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAADCSURBVDiNY/j//z8DAwMDw38GKjAwjDgIYNIBA6xMLUAYTYJRBhBHNoDH8PqgFQJYRn+BKAoYAhWcGjAySDB8PxQbBBhBGJgM5AwhOZiYmBkYGJiYoBiYkDUD+Vwg0KpAMkxBaALMBDRANaA0UA0QzIAwmBjIGBgZGBiYgGJiQNQP5XCDQqkAzEFlgLwwDQDdANCBsQYGRiZ/wxgjI2Pwf2BgYGLi/+DIyPg/AwMDw38Gi4DA8P8AAmk4ZunS0qsAAAAASUVORK5CYII=', 'base64'))
  }
  tray = new Tray(icon)
  const contextMenu = Menu.buildFromTemplate([
    { label: '显示窗口', click: () => { mainWindow?.show(); mainWindow?.focus() } },
    { label: '隐藏窗口', click: () => mainWindow?.hide() },
    { type: 'separator' },
    { label: '显示桌面宠物', click: () => { createDesktopPet() } },
    { label: '隐藏桌面宠物', click: () => { if (desktopPetWindow && !desktopPetWindow.isDestroyed()) desktopPetWindow.hide() } },
    { type: 'separator' },
    { label: '退出', click: () => { tray?.destroy(); app.quit() } }
  ])
  tray.setToolTip('LuomiNest')
  tray.setContextMenu(contextMenu)
  tray.on('double-click', () => { mainWindow?.show(); mainWindow?.focus() })
}

const LUOMINEST_BUILTIN_MODELS = [
  { id: 'llny', name: 'Llny', url: 'luominest-avatar://llny/llny.model3.json', scale: 0.25, type: 'live2d', tags: ['Default', 'Cubism4', 'Built-in'] },
  { id: 'hiyori', name: 'Hiyori', url: 'luominest-avatar://hiyori/Hiyori.model3.json', scale: 0.25, type: 'live2d', tags: ['Cubism4', 'Built-in'] },
  { id: 'shizuku', name: 'Shizuku', url: 'luominest-avatar://shizuku/shizuku.model3.json', scale: 0.25, type: 'live2d', tags: ['Cubism4', 'Built-in'] }
]

const createDesktopPet = (modelInfo?: ImportedModelRecord): void => {
  if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
    desktopPetWindow.show()
    desktopPetWindow.setFocusable(true)
    desktopPetWindow.setAlwaysOnTop(true, 'screen-saver')
    if (modelInfo) {
      setTimeout(() => {
        desktopPetWindow?.webContents.send('desktop-pet:load-model', modelInfo)
      }, 300)
    }
    return
  }

  const display = screen.getPrimaryDisplay()
  const { width: screenWidth, height: screenHeight } = display.workAreaSize

  desktopPetWindow = new BrowserWindow({
    width: screenWidth,
    height: screenHeight,
    x: 0,
    y: 0,
    transparent: true,
    frame: false,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: false,
    show: false,
    focusable: false,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false
    }
  })

  desktopPetWindow.setVisibleOnAllWorkspaces(true, { makeKey: false })
  desktopPetWindow.setAlwaysOnTop(true, 'screen-saver')

  if (isMac) {
    desktopPetWindow.setIgnoreMouseEvents(true)
  } else {
    desktopPetWindow.setIgnoreMouseEvents(true, { forward: true })
  }

  const allModels = [...LUOMINEST_BUILTIN_MODELS, ...loadImportedModels()]

  const petContextMenu = Menu.buildFromTemplate([
    { label: 'Show Main Window', click: () => { mainWindow?.show(); mainWindow?.focus() } },
    { type: 'separator' },
    { label: 'Switch Model', submenu: [
      ...allModels.map(m => ({
        label: m.name,
        click: () => {
          desktopPetWindow?.webContents.send('desktop-pet:load-model', m)
        }
      }))
    ]},
    { type: 'separator' },
    { label: 'Play Motion', submenu: [
      { label: 'Idle', click: () => desktopPetWindow?.webContents.send('desktop-pet:trigger-motion', 'Idle', 0) },
      { label: 'TapBody', click: () => desktopPetWindow?.webContents.send('desktop-pet:trigger-motion', 'TapBody', 0) }
    ]},
    { label: 'Set Emotion', submenu: [
      { label: 'Happy', click: () => desktopPetWindow?.webContents.send('desktop-pet:trigger-expression', 'happy') },
      { label: 'Sad', click: () => desktopPetWindow?.webContents.send('desktop-pet:trigger-expression', 'sad') },
      { label: 'Neutral', click: () => desktopPetWindow?.webContents.send('desktop-pet:trigger-expression', 'neutral') },
      { label: 'Angry', click: () => desktopPetWindow?.webContents.send('desktop-pet:trigger-expression', 'angry') },
      { label: 'Surprise', click: () => desktopPetWindow?.webContents.send('desktop-pet:trigger-expression', 'surprise') }
    ]},
    { type: 'separator' },
    { label: 'Hide Pet', click: () => desktopPetWindow?.hide() },
    { label: 'Show Pet', click: () => { desktopPetWindow?.show(); desktopPetWindow?.setAlwaysOnTop(true, 'screen-saver') } },
    { type: 'separator' },
    { label: 'Close Desktop Pet', click: () => { desktopPetWindow?.close(); desktopPetWindow = null } },
    { type: 'separator' },
    { label: 'Quit', click: () => { tray?.destroy(); app.quit() } }
  ])

  desktopPetWindow.webContents.on('context-menu', () => {
    petContextMenu.popup()
  })

  ipcMain.removeAllListeners('desktop-pet:set-ignore-mouse-events')
  ipcMain.on('desktop-pet:set-ignore-mouse-events', (_event, ignore: boolean) => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      if (isMac) {
        desktopPetWindow.setIgnoreMouseEvents(ignore)
      } else {
        desktopPetWindow.setIgnoreMouseEvents(ignore, { forward: true })
      }
    }
  })

  ipcMain.on('desktop-pet:show-context-menu', () => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      petContextMenu.popup({ window: desktopPetWindow })
    }
  })

  if (isDev && process.env['ELECTRON_RENDERER_URL']) {
    desktopPetWindow.loadURL(process.env['ELECTRON_RENDERER_URL'] + '#/desktop-pet')
  } else {
    desktopPetWindow.loadFile(join(__dirname, '../renderer/index.html'), { hash: '/desktop-pet' })
  }

  desktopPetWindow.on('closed', () => {
    desktopPetWindow = null
  })

  desktopPetWindow.once('ready-to-show', () => {
    desktopPetWindow?.show()
    if (modelInfo) {
      setTimeout(() => {
        desktopPetWindow?.webContents.send('desktop-pet:load-model', modelInfo)
      }, 800)
    }
  })

  desktopPetWindow.webContents.on('did-finish-load', () => {
    if (modelInfo) {
      desktopPetWindow?.webContents.send('desktop-pet:load-model', modelInfo)
    }
  })
}

const createMenu = (): void => {
  const template: MenuItemConstructorOptions[] = [
    { label: '文件', submenu: [{ role: 'quit' as const, label: '退出' }] },
    {
      label: '编辑',
      submenu: [
        { role: 'undo' as const, label: '撤销' },
        { role: 'redo' as const, label: '重做' },
        { type: 'separator' as const },
        { role: 'cut' as const, label: '剪切' },
        { role: 'copy' as const, label: '复制' },
        { role: 'paste' as const, label: '粘贴' }
      ]
    },
    {
      label: '视图',
      submenu: [
        { role: 'reload' as const, label: '刷新' },
        { role: 'forceReload' as const, label: '强制刷新' },
        { type: 'separator' as const },
        { role: 'resetZoom' as const, label: '重置缩放' },
        { role: 'zoomIn' as const, label: '放大' },
        { role: 'zoomOut' as const, label: '缩小' },
        { type: 'separator' as const },
        { role: 'togglefullscreen' as const, label: '全屏' }
      ] as MenuItemConstructorOptions[]
    },
    {
      label: '帮助',
      submenu: [{
        label: '关于 LuomiNest',
        click: async () => {
          const { dialog } = await import('electron')
          dialog.showMessageBox(mainWindow!, {
            type: 'info',
            title: '关于 LuomiNest',
            message: 'LuomiNest 辰汐分布式AI伴侣平台',
            detail: `版本: ${app.getVersion()}\n基于 Electron + Vue3 构建`
          })
        }
      }]
    }
  ]

  if (isDev) {
    const viewMenu = template[2].submenu as MenuItemConstructorOptions[]
    viewMenu.push({ type: 'separator' as const }, { role: 'toggleDevTools' as const, label: '开发者工具' })
  }

  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

function registerIpcHandlers(): void {
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

  ipcMain.handle('app:getVersion', () => app.getVersion())
  ipcMain.handle('app:getName', () => app.getName())

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
    const { getCookies } = await import('./services/browser')
    return getCookies()
  })

  ipcMain.handle('tab:clearData', async () => {
    const { clearBrowserData } = await import('./services/browser')
    return clearBrowserData()
  })

  ipcMain.handle('avatar:importModel', async () => {
    try {
      const result = await dialog.showOpenDialog({
        title: 'Import LuomiNest Avatar Model',
        filters: [
          { name: 'Live2D Model', extensions: ['model3.json'] }
        ],
        properties: ['openFile']
      })

      if (result.canceled || result.filePaths.length === 0) {
        return { success: false, error: 'Cancelled' }
      }

      const selectedFile = result.filePaths[0]
      const modelDir = dirname(selectedFile)
      const modelFileName = basename(selectedFile)
      const modelName = modelFileName.replace('.model3.json', '')

      const destDir = join(PATHS.live2d, modelName)

      if (existsSync(destDir)) {
        rmSync(destDir, { recursive: true, force: true })
      }

      mkdirSync(PATHS.live2d, { recursive: true })
      copyDirRecursive(modelDir, destDir)

      const modelJsonPath = join(destDir, modelFileName)
      if (!existsSync(modelJsonPath)) {
        rmSync(destDir, { recursive: true, force: true })
        return { success: false, error: `Model file "${modelFileName}" not found after copy` }
      }

      try {
        const modelJsonContent = readFileSync(modelJsonPath, 'utf-8')
        const modelJson = JSON.parse(modelJsonContent)
        if (!modelJson.FileReferences || !modelJson.FileReferences.Moc) {
          rmSync(destDir, { recursive: true, force: true })
          return { success: false, error: 'Invalid model3.json: missing FileReferences.Moc' }
        }
      } catch {
        rmSync(destDir, { recursive: true, force: true })
        return { success: false, error: 'Invalid model3.json: parse error' }
      }

      const modelUrl = `luominest-avatar://${modelName}/${modelFileName}`

      const modelRecord: ImportedModelRecord = {
        id: `imported-${Date.now()}`,
        name: modelName,
        url: modelUrl,
        scale: 0.25,
        type: 'live2d',
        tags: ['Imported']
      }

      const models = loadImportedModels()
      const existingIdx = models.findIndex(m => m.name === modelName)
      if (existingIdx >= 0) {
        models[existingIdx] = modelRecord
      } else {
        models.push(modelRecord)
      }
      saveImportedModels(models)

      console.info(`[INFO][LuomiNestAvatar] Model imported: ${modelName} -> ${destDir}`)

      return {
        success: true,
        modelInfo: modelRecord
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      console.error('[ERROR][LuomiNestAvatar] Import failed:', message)
      return { success: false, error: message }
    }
  })

  ipcMain.handle('avatar:listImportedModels', () => {
    return loadImportedModels()
  })

  ipcMain.handle('avatar:deleteModel', async (_e, modelName: string) => {
    try {
      const destDir = join(PATHS.live2d, modelName)
      if (existsSync(destDir)) {
        rmSync(destDir, { recursive: true, force: true })
      }

      const models = loadImportedModels()
      const filtered = models.filter(m => m.name !== modelName)
      saveImportedModels(filtered)

      console.info(`[INFO][LuomiNestAvatar] Model deleted: ${modelName}`)
      return { success: true }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      console.error('[ERROR][LuomiNestAvatar] Delete failed:', message)
      return { success: false, error: message }
    }
  })

  ipcMain.handle('avatar:getImportedModelsPath', () => {
    return PATHS.live2d
  })

  ipcMain.handle('desktop-pet:open', async (_e, modelInfo?: ImportedModelRecord) => {
    createDesktopPet(modelInfo)
    return { success: true }
  })

  ipcMain.handle('desktop-pet:close', async () => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.close()
      desktopPetWindow = null
    }
    return { success: true }
  })

  ipcMain.handle('desktop-pet:isRunning', async () => {
    return desktopPetWindow !== null && !desktopPetWindow.isDestroyed()
  })

  ipcMain.handle('desktop-pet:loadModel', async (_e, modelInfo: ImportedModelRecord) => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.webContents.send('desktop-pet:load-model', modelInfo)
      return { success: true }
    }
    return { success: false, error: 'Desktop pet window not running' }
  })

  ipcMain.handle('desktop-pet:show', async () => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.show()
      desktopPetWindow.setAlwaysOnTop(true, 'screen-saver')
    }
    return { success: true }
  })

  ipcMain.handle('desktop-pet:hide', async () => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.hide()
    }
    return { success: true }
  })

  ipcMain.handle('desktop-pet:triggerMotion', async (_e, group: string, index: number) => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.webContents.send('desktop-pet:trigger-motion', group, index)
      return { success: true }
    }
    return { success: false }
  })

  ipcMain.handle('desktop-pet:triggerExpression', async (_e, name: string) => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.webContents.send('desktop-pet:trigger-expression', name)
      return { success: true }
    }
    return { success: false }
  })

  ipcMain.handle('desktop-pet:setPosition', async (_e, x: number, y: number) => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.webContents.send('desktop-pet:set-position', x, y)
      return { success: true }
    }
    return { success: false }
  })

  ipcMain.handle('desktop-pet:setScale', async (_e, scale: number) => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.webContents.send('desktop-pet:set-scale', scale)
      return { success: true }
    }
    return { success: false }
  })

  ipcMain.handle('desktop-pet:driveLipSync', async (_e, value: number) => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.webContents.send('desktop-pet:lip-sync', value)
      return { success: true }
    }
    return { success: false }
  })

  ipcMain.handle('desktop-pet:drivePadEmotion', async (_e, pleasure: number, arousal: number, dominance: number) => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.webContents.send('desktop-pet:pad-emotion', { pleasure, arousal, dominance })
      return { success: true }
    }
    return { success: false }
  })

  ipcMain.handle('desktop-pet:setCoreParam', async (_e, paramId: string, value: number) => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.webContents.send('desktop-pet:set-core-param', paramId, value)
      return { success: true }
    }
    return { success: false }
  })

  ipcMain.handle('desktop-pet:getModelCapabilities', async () => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      return new Promise((resolve) => {
        const requestId = `cap-${Date.now()}`
        let handled = false
        const handler = (_event: any, id: string, capabilities: any) => {
          if (id === requestId && !handled) {
            handled = true
            ipcMain.removeListener('desktop-pet:model-capabilities-response', handler)
            clearTimeout(timeoutId)
            resolve(capabilities)
          }
        }
        ipcMain.on('desktop-pet:model-capabilities-response', handler)
        desktopPetWindow!.webContents.send('desktop-pet:get-model-capabilities', requestId)
        const timeoutId = setTimeout(() => {
          if (!handled) {
            handled = true
            ipcMain.removeListener('desktop-pet:model-capabilities-response', handler)
            resolve(null)
          }
        }, 3000)
      })
    }
    return null
  })
}

const MIME_MAP: Record<string, string> = {
  json: 'application/json',
  moc3: 'application/octet-stream',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  mtn: 'application/octet-stream',
  exp3: 'application/json',
  physics3: 'application/json',
  pose3: 'application/json',
  motion3: 'application/json',
  cdi3: 'application/json',
  userdata3: 'application/json',
  js: 'application/javascript'
}

const resolveModelFile = (hostname: string, relativePath: string): string | null => {
  if (hostname === 'cubism-core') {
    const filePath = join(cubismCoreBasePath, relativePath)
    if (existsSync(filePath) && statSync(filePath).isFile()) return filePath
    return null
  }

  const importedPath = join(PATHS.live2d, hostname, relativePath)
  if (existsSync(importedPath) && statSync(importedPath).isFile()) return importedPath

  const builtinPath = join(builtinBasePath, hostname, relativePath)
  if (existsSync(builtinPath) && statSync(builtinPath).isFile()) return builtinPath

  return null
}

app.whenReady().then(async () => {
  initAppPaths()

  protocol.handle('luominest-avatar', (request) => {
    const url = new URL(request.url)
    const hostname = url.hostname
    const relativePath = decodeURIComponent(url.pathname).replace(/^\/+/, '')

    const filePath = resolveModelFile(hostname, relativePath)
    if (!filePath) {
      console.warn(`[WARNING][LuomiNestAvatar] Resource not found: ${hostname}/${relativePath}`)
      return new Response('Not Found', { status: 404 })
    }

    const ext = filePath.split('.').pop()?.toLowerCase()
    const mimeType = MIME_MAP[ext ?? ''] ?? 'application/octet-stream'
    const data = readFileSync(filePath)
    return new Response(data, {
      headers: {
        'content-type': mimeType,
        'access-control-allow-origin': '*',
        'cache-control': 'no-cache'
      }
    })
  })

  console.info(`[INFO][LuomiNestAvatar] Protocol registered. Builtin path: ${builtinBasePath}`)
  console.info(`[INFO][LuomiNestAvatar] Cubism core path: ${cubismCoreBasePath}`)

  console.log('[Main] Starting backend service...')
  const backendStarted = await startBackend()
  if (!backendStarted) {
    console.error('[Main] Failed to start backend service')
  } else {
    console.log('[Main] Backend service started at:', getBackendUrl())
  }

  createWindow()
  createMenu()
  createTray()
  registerIpcHandlers()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (platform() !== 'darwin') {
    tabManager.cleanup()
    stopBackend()
    tray?.destroy()
    app.quit()
  }
})

app.on('before-quit', () => {
  saveWindowState()
  tabManager.cleanup()
  stopBackend()
})
