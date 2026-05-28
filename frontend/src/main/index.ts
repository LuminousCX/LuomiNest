import { app, BrowserWindow, shell, Menu, Tray, nativeImage, MenuItemConstructorOptions } from 'electron'
import { join } from 'path'
import { platform } from 'os'
import { tabManager } from './services/browser'
import { setupNetworkConfig } from './services/browser/view'
import { startBackend, stopBackend, getBackendUrl } from './services/backend'
import { PATHS, initAppPaths } from './services/paths'
import { configStore } from './services/config-store'
import { registerIpcHandlers } from './services/ipc-handlers'
import { createDesktopPet, getDesktopPetWindow, registerDesktopPetIpc } from './services/desktop-pet'
import { registerAvatarProtocol, verifyAvatarResources, registerAvatarIpc } from './services/avatar-protocol'

if (platform() === 'win32') {
  process.stdout.write('\x1b[?65001h')
}

setupNetworkConfig()

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null

const isDev = !app.isPackaged
const isMac = platform() === 'darwin'

if (isDev) {
  process.env.ELECTRON_DISABLE_SECURITY_WARNINGS = 'true'
}

const CSP_DEV = "default-src 'self' luominest-avatar:; script-src 'self' 'unsafe-inline' 'unsafe-eval' luominest-avatar:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: https: http: blob: luominest-avatar:; connect-src 'self' blob: luominest-avatar: https://fonts.googleapis.com https://fonts.gstatic.com https: http: wss:; worker-src 'self' blob:"
const CSP_PROD = "default-src 'self' luominest-avatar:; script-src 'self' 'unsafe-inline' luominest-avatar:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: https: http: blob: luominest-avatar:; connect-src 'self' blob: luominest-avatar: https://fonts.googleapis.com https://fonts.gstatic.com https: http: wss:; worker-src 'self' blob:"

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

  const appIcon = nativeImage.createFromPath(join(__dirname, '../../resources/icon.png'))

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
    backgroundColor: '#F5F8FB',
    show: false,
    autoHideMenuBar: true,
    icon: appIcon,
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
  const icon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 })
  tray = new Tray(icon)
  const desktopPet = getDesktopPetWindow()
  const contextMenu = Menu.buildFromTemplate([
    { label: '显示窗口', click: () => { mainWindow?.show(); mainWindow?.focus() } },
    { label: '隐藏窗口', click: () => mainWindow?.hide() },
    { type: 'separator' },
    { label: '显示桌面宠物', click: () => { createDesktopPet(mainWindow) } },
    { label: '隐藏桌面宠物', click: () => { if (desktopPet && !desktopPet.isDestroyed()) desktopPet.hide() } },
    { type: 'separator' },
    { label: '退出', click: () => { tray?.destroy(); app.quit() } }
  ])
  tray.setToolTip('LuomiNest')
  tray.setContextMenu(contextMenu)
  tray.on('double-click', () => { mainWindow?.show(); mainWindow?.focus() })
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

app.whenReady().then(async () => {
  initAppPaths()

  verifyAvatarResources()
  registerAvatarProtocol()

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

  registerIpcHandlers(mainWindow)
  registerDesktopPetIpc()
  registerAvatarIpc()

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
