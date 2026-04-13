import { app, BrowserWindow, ipcMain, shell, Menu, Tray, nativeImage, NativeImage, MenuItemConstructorOptions } from 'electron'
import { join } from 'path'
import { platform } from 'os'
import { tabManager } from './services/browser'
import { setupNetworkConfig } from './services/browser/view'

setupNetworkConfig()

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null

const isDev = !app.isPackaged

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

function registerIpcHandlers(): void {
  // Window controls
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
  
  // App info
  ipcMain.handle('app:getVersion', () => app.getVersion())
  ipcMain.handle('app:getName', () => app.getName())

  // Tab management
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
}

app.whenReady().then(() => {
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
