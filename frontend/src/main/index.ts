import { app, BrowserWindow, ipcMain, shell, Menu, Tray, nativeImage, NativeImage, MenuItemConstructorOptions, dialog, protocol, screen } from 'electron'
import { join, dirname, basename } from 'path'
import { platform } from 'os'
import { copyFileSync, mkdirSync, existsSync, readdirSync, readFileSync, writeFileSync, unlinkSync, rmSync, statSync } from 'fs'
import { tabManager } from './services/browser'
import { setupNetworkConfig } from './services/browser/view'

if (platform() === 'win32') {
  process.stdout.write('\x1b[?65001h')
}

setupNetworkConfig()

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
let desktopPetWindow: BrowserWindow | null = null

const isDev = !app.isPackaged
const isMac = platform() === 'darwin'

let live2dBasePath = ''

interface ImportedModelRecord {
  id: string
  name: string
  url: string
  scale: number
  type: string
  tags: string[]
}

const IMPORTED_MODELS_FILE = 'imported-models.json'

const loadImportedModels = (): ImportedModelRecord[] => {
  const filePath = join(live2dBasePath, IMPORTED_MODELS_FILE)
  if (!existsSync(filePath)) return []
  try {
    const data = readFileSync(filePath, 'utf-8')
    return JSON.parse(data) as ImportedModelRecord[]
  } catch {
    return []
  }
}

const saveImportedModels = (models: ImportedModelRecord[]): void => {
  mkdirSync(live2dBasePath, { recursive: true })
  const filePath = join(live2dBasePath, IMPORTED_MODELS_FILE)
  writeFileSync(filePath, JSON.stringify(models, null, 2), 'utf-8')
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

const createWindow = (): void => {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
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

  mainWindow.webContents.setWindowOpenHandler((details: { url: string }) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  if (isDev) {
    mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
      callback({
        responseHeaders: {
          ...details.responseHeaders,
          'Content-Security-Policy': [
            "default-src 'self' luominest-avatar:; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: https: http: blob: luominest-avatar:; connect-src 'self' blob: luominest-avatar: https://fonts.googleapis.com https://fonts.gstatic.com https: http: wss:; worker-src 'self' blob:"
          ]
        }
      })
    })
  }

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

const createDesktopPet = (modelInfo?: ImportedModelRecord): void => {
  if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
    desktopPetWindow.show()
    if (modelInfo) {
      desktopPetWindow.webContents.send('desktop-pet:load-model', modelInfo)
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
      nodeIntegration: false
    }
  })

  desktopPetWindow.setVisibleOnAllWorkspaces(true)
  desktopPetWindow.setAlwaysOnTop(true, 'screen-saver')
  if (isMac) {
    desktopPetWindow.setIgnoreMouseEvents(true)
  } else {
    desktopPetWindow.setIgnoreMouseEvents(true, { forward: true })
  }

  const petContextMenu = Menu.buildFromTemplate([
    { label: 'Show Main Window', click: () => { mainWindow?.show(); mainWindow?.focus() } },
    { type: 'separator' },
    { label: 'Switch Model', submenu: [
      ...LUOMINEST_BUILTIN_MODELS.map(m => ({
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
      }, 500)
    }
  })
}

const LUOMINEST_BUILTIN_MODELS = [
  { id: 'hiyori', name: 'Hiyori', url: '/live2d/hiyori/Hiyori.model3.json', scale: 0.25, type: 'live2d', tags: ['Default', 'Cubism4', 'Built-in'] },
  { id: 'shizuku', name: 'Shizuku', url: '/live2d/shizuku/shizuku.model3.json', scale: 0.25, type: 'live2d', tags: ['Cubism4', 'Built-in'] }
]

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

      const destDir = join(live2dBasePath, modelName)

      if (existsSync(destDir)) {
        rmSync(destDir, { recursive: true, force: true })
      }

      mkdirSync(live2dBasePath, { recursive: true })
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
      const destDir = join(live2dBasePath, modelName)
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
    return live2dBasePath
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

  ipcMain.handle('dialog:showOpenDialog', async (_e, options?: {
    title?: string
    defaultPath?: string
    filters?: { name: string; extensions: string[] }[]
    properties?: string[]
  }) => {
    const result = await dialog.showOpenDialog(mainWindow!, {
      title: options?.title || '选择文件',
      filters: options?.filters,
      properties: options?.properties as any
    })
    return result
  })

  ipcMain.handle('skill:upload', async (_e, config: { filePath: string; name: string; overwrite?: boolean }) => {
    const skillsDir = join(app.getPath('userData'), 'skills')
    mkdirSync(skillsDir, { recursive: true })
    const destDir = join(skillsDir, config.name)
    if (existsSync(destDir) && !config.overwrite) {
      return { success: false, error: '同名技能已存在，请勾选覆盖选项' }
    }
    if (existsSync(destDir)) {
      rmSync(destDir, { recursive: true, force: true })
    }
    const srcStat = statSync(config.filePath)
    if (srcStat.isDirectory()) {
      copyDirRecursive(config.filePath, destDir)
    } else {
      mkdirSync(destDir, { recursive: true })
      copyFileSync(config.filePath, join(destDir, basename(config.filePath)))
    }
    return { success: true, path: destDir }
  })
}

app.whenReady().then(() => {
  const userDataPath = app.getPath('userData')
  app.setPath('cache', join(userDataPath, 'Cache'))

  live2dBasePath = join(userDataPath, 'live2d')
  mkdirSync(live2dBasePath, { recursive: true })

  protocol.handle('luominest-avatar', (request) => {
    const url = new URL(request.url)
    const modelDir = url.hostname
    const relativePath = decodeURIComponent(url.pathname).replace(/^\/+/, '')
    const filePath = join(live2dBasePath, modelDir, relativePath)

    if (!existsSync(filePath) || !statSync(filePath).isFile()) {
      return new Response('Not Found', { status: 404 })
    }

    const ext = filePath.split('.').pop()?.toLowerCase()
    const mimeMap: Record<string, string> = {
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
      userdata3: 'application/json'
    }
    const mimeType = mimeMap[ext ?? ''] ?? 'application/octet-stream'
    const data = readFileSync(filePath)
    return new Response(data, {
      headers: { 'content-type': mimeType, 'access-control-allow-origin': '*' }
    })
  })

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
    tray?.destroy()
    app.quit()
  }
})

app.on('before-quit', () => {
  tabManager.cleanup()
})
