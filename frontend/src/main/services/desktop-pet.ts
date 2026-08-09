import { BrowserWindow, ipcMain, Menu, screen, IpcMainInvokeEvent, app } from 'electron'
import { join } from 'path'
import { platform } from 'os'
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'fs'
import { PATHS } from './paths'
import { createLuomiNestLogger } from './luomi-logger'

const logger = createLuomiNestLogger('DesktopPet')

const isDev = !app.isPackaged
const isMac = platform() === 'darwin'
const supportsForwardedMouseMove = isMac || platform() === 'win32'

const MIN_WIDTH = 280
const MIN_HEIGHT = 400
const MAX_WIDTH = 1200
const MAX_HEIGHT = 1600

const CSP_DEV = "default-src 'self' luominest-avatar: luominest-bg:; script-src 'self' 'unsafe-inline' 'unsafe-eval' luominest-avatar:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: https: http: blob: luominest-avatar: luominest-bg:; media-src 'self' blob: luominest-avatar:; connect-src 'self' blob: luominest-avatar: luominest-bg: https://fonts.googleapis.com https://fonts.gstatic.com https: http: wss:; worker-src 'self' blob:"
const CSP_PROD = "default-src 'self' luominest-avatar: luominest-bg:; script-src 'self' 'unsafe-inline' luominest-avatar:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: https: http: blob: luominest-avatar: luominest-bg:; media-src 'self' blob: luominest-avatar:; connect-src 'self' blob: luominest-avatar: luominest-bg: https://fonts.googleapis.com https://fonts.gstatic.com https: http: wss:; worker-src 'self' blob:"

export interface ImportedModelRecord {
  id: string
  name: string
  url: string
  scale: number
  type: string
  tags: string[]
}

export const LUOMINEST_BUILTIN_MODELS: ImportedModelRecord[] = [
  { id: 'llny', name: 'Llny', url: 'luominest-avatar://llny/llny.model3.json', scale: 0.25, type: 'live2d', tags: ['Default', 'Cubism4', 'Built-in'] },
  { id: 'hiyori', name: 'Hiyori', url: 'luominest-avatar://hiyori/Hiyori.model3.json', scale: 0.25, type: 'live2d', tags: ['Cubism4', 'Built-in'] }
]

export const loadImportedModels = (): ImportedModelRecord[] => {
  const filePath = PATHS.importedModelsPath
  if (!existsSync(filePath)) return []
  try {
    const data = readFileSync(filePath, 'utf-8')
    return JSON.parse(data) as ImportedModelRecord[]
  } catch {
    return []
  }
}

export const saveImportedModels = (models: ImportedModelRecord[]): void => {
  mkdirSync(PATHS.live2d, { recursive: true })
  writeFileSync(PATHS.importedModelsPath, JSON.stringify(models, null, 2), 'utf-8')
}

let desktopPetWindow: BrowserWindow | null = null
let desktopPetChatWindow: BrowserWindow | null = null

export const getDesktopPetWindow = (): BrowserWindow | null => desktopPetWindow

const loadAuxiliaryRoute = async (window: BrowserWindow, route: string): Promise<void> => {
  if (isDev && process.env['ELECTRON_RENDERER_URL']) {
    const baseUrl = process.env['ELECTRON_RENDERER_URL'].replace(/\/$/, '')
    await window.loadURL(`${baseUrl}/#/${route}`)
  } else {
    await window.loadFile(join(__dirname, '../renderer/index.html'), { hash: `/${route}` })
  }
}

const createDesktopPetChat = (mainWindow: BrowserWindow | null): BrowserWindow => {
  if (desktopPetChatWindow && !desktopPetChatWindow.isDestroyed()) {
    desktopPetChatWindow.show()
    desktopPetChatWindow.focus()
    return desktopPetChatWindow
  }

  const petBounds = desktopPetWindow?.getBounds()
  const display = screen.getDisplayNearestPoint({
    x: petBounds?.x ?? screen.getCursorScreenPoint().x,
    y: petBounds?.y ?? screen.getCursorScreenPoint().y,
  })
  const width = 460
  const height = 76
  const x = Math.max(display.workArea.x, Math.min(
    display.workArea.x + display.workArea.width - width,
    (petBounds?.x ?? display.workArea.x + display.workArea.width - width - 32) - width - 18,
  ))
  const y = Math.max(display.workArea.y, Math.min(
    display.workArea.y + display.workArea.height - height,
    petBounds?.y ?? display.workArea.y + display.workArea.height - height - 32,
  ))

  desktopPetChatWindow = new BrowserWindow({
    width,
    height,
    x,
    y,
    minWidth: 320,
    minHeight: 76,
    maxHeight: 76,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    hasShadow: true,
    resizable: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    show: false,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  })
  desktopPetChatWindow.setAlwaysOnTop(true, 'floating')
  desktopPetChatWindow.setVisibleOnAllWorkspaces(true)
  desktopPetChatWindow.once('ready-to-show', () => desktopPetChatWindow?.show())
  desktopPetChatWindow.on('closed', () => { desktopPetChatWindow = null })
  void loadAuxiliaryRoute(desktopPetChatWindow, 'desktop-pet-chat').catch(error => {
    logger.error('Failed to load desktop pet chat window:', error)
  })
  return desktopPetChatWindow
}

export const createDesktopPet = (mainWindow: BrowserWindow | null, modelInfo?: ImportedModelRecord): void => {
  if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
    desktopPetWindow.show()
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

  // Target ~75% of screen height so the full character is clearly visible
  const petHeight = Math.min(900, Math.round(screenHeight * 0.75))
  const petWidth = Math.round(petHeight * 0.68)
  const petX = screenWidth - petWidth - 40
  const petY = screenHeight - petHeight - 40

  const windowConfig: Electron.BrowserWindowConstructorOptions = {
    width: petWidth,
    height: petHeight,
    // width / height 明确表示网页可用内容区，避免开发环境与安装包环境因
    // 系统边框度量不同而让 Pixi renderer 比透明窗口少一截。
    useContentSize: true,
    x: petX,
    y: petY,
    show: false,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    hasShadow: false,
    resizable: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    minWidth: MIN_WIDTH,
    minHeight: MIN_HEIGHT,
    maxWidth: MAX_WIDTH,
    maxHeight: MAX_HEIGHT,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: true
    }
  }

  if (isMac) {
    windowConfig.titleBarStyle = 'hidden'
    ;(windowConfig as Electron.BrowserWindowConstructorOptions & { type?: string }).type = 'panel'
  }

  desktopPetWindow = new BrowserWindow(windowConfig)

  desktopPetWindow.setVisibleOnAllWorkspaces(true, { makeKey: false } as Electron.VisibleOnAllWorkspacesOptions)
  desktopPetWindow.setAlwaysOnTop(true, 'screen-saver')
  desktopPetWindow.setFullScreenable(false)

  if (isMac) {
    desktopPetWindow.setWindowButtonVisibility(false)
  }

  const CSP_PET_WINDOW = isDev ? CSP_DEV : CSP_PROD
  desktopPetWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [CSP_PET_WINDOW]
      }
    })
  })

  // Keep the window clickable by default so users can interact with the pet.
  // The renderer will request mouse passthrough explicitly when needed.
  desktopPetWindow.setIgnoreMouseEvents(false)

  const allModels = [...LUOMINEST_BUILTIN_MODELS, ...loadImportedModels()]

  const petContextMenu = Menu.buildFromTemplate([
    { label: '打开对话框', click: () => { createDesktopPetChat(mainWindow) } },
    { type: 'separator' },
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
    { label: 'Quit', click: () => { app.quit() } }
  ])

  desktopPetWindow.webContents.on('context-menu', () => {
    petContextMenu.popup({ window: desktopPetWindow ?? undefined })
  })

  const handleSetIgnoreMouseEvents = (_event: unknown, ignore: boolean) => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      if (ignore && supportsForwardedMouseMove) {
        desktopPetWindow.setIgnoreMouseEvents(ignore, { forward: true })
      } else {
        desktopPetWindow.setIgnoreMouseEvents(ignore)
      }
    }
  }

  const handleSetAlwaysOnTop = (_event: unknown, onTop: boolean) => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.setAlwaysOnTop(onTop, 'screen-saver')
    }
  }

  const handleShowContextMenu = () => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      petContextMenu.popup({ window: desktopPetWindow })
    }
  }

  let dragOffsetX = 0
  let dragOffsetY = 0

  const handleStartDrag = (_event: unknown, mouseX: number, mouseY: number) => {
    if (!desktopPetWindow || desktopPetWindow.isDestroyed()) return
    const [x, y] = desktopPetWindow.getPosition()
    dragOffsetX = mouseX - x
    dragOffsetY = mouseY - y
  }

  const handleDragWindow = (_event: unknown, mouseX: number, mouseY: number) => {
    if (!desktopPetWindow || desktopPetWindow.isDestroyed()) return
    desktopPetWindow.setPosition(mouseX - dragOffsetX, mouseY - dragOffsetY)
  }

  const handleEndDrag = () => {
    if (!desktopPetWindow || desktopPetWindow.isDestroyed()) return
    // Refresh the transparent surface once the drag finishes to work around
    // Windows DWM occasionally leaving a white background after setPosition.
    const currentOpacity = desktopPetWindow.getOpacity()
    desktopPetWindow.setOpacity(0.99)
    desktopPetWindow.setOpacity(currentOpacity)
  }

  ipcMain.on('desktop-pet:set-ignore-mouse-events', handleSetIgnoreMouseEvents)
  ipcMain.on('desktop-pet:set-always-on-top', handleSetAlwaysOnTop)
  ipcMain.on('desktop-pet:show-context-menu', handleShowContextMenu)
  ipcMain.on('desktop-pet:start-drag', handleStartDrag)
  ipcMain.on('desktop-pet:drag-window', handleDragWindow)
  ipcMain.on('desktop-pet:end-drag', handleEndDrag)

  // 桌宠窗口 → 主进程 → 主应用窗口：转发聊天消息
  // 桌宠窗口的 webContents !== mainWindow.webContents，无法通过 invoke 的 assertTrustedSender 校验，
  // 故用 ipcMain.on（单向）接收，再通过 mainWindow.webContents.send 转发给主应用。
  const handleSendChatMessage = (_event: unknown, text: string) => {
    if (typeof text !== 'string' || !text.trim()) return
    mainWindow?.webContents.send('desktop-pet:chat-message', text)
  }

  const handleCancelChat = () => {
    mainWindow?.webContents.send('desktop-pet:chat-cancel')
  }

  ipcMain.on('desktop-pet:send-chat-message', handleSendChatMessage)
  ipcMain.on('desktop-pet:cancel-chat', handleCancelChat)

  const loadPetWindow = async () => {
    if (isDev && process.env['ELECTRON_RENDERER_URL']) {
      const baseUrl = process.env['ELECTRON_RENDERER_URL']
      const url = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl
      try {
        await desktopPetWindow!.loadURL(`${url}/#/desktop-pet`)
      } catch (err: unknown) {
        const error = err instanceof Error ? err : new Error(String(err))
        if ('code' in error && (error as { code?: string }).code === 'ERR_ABORTED') {
          logger.warn('Navigation aborted, hash route may have loaded correctly')
        } else {
          logger.error('Failed to load URL:', error)
        }
      }
    } else {
      const indexPath = join(__dirname, '../renderer/index.html')
      await desktopPetWindow!.loadFile(indexPath, { hash: '/desktop-pet' })
    }
  }

  loadPetWindow()

  desktopPetWindow.on('closed', () => {
    ipcMain.removeListener('desktop-pet:set-ignore-mouse-events', handleSetIgnoreMouseEvents)
    ipcMain.removeListener('desktop-pet:set-always-on-top', handleSetAlwaysOnTop)
    ipcMain.removeListener('desktop-pet:show-context-menu', handleShowContextMenu)
    ipcMain.removeListener('desktop-pet:start-drag', handleStartDrag)
    ipcMain.removeListener('desktop-pet:drag-window', handleDragWindow)
    ipcMain.removeListener('desktop-pet:end-drag', handleEndDrag)
    ipcMain.removeListener('desktop-pet:send-chat-message', handleSendChatMessage)
    ipcMain.removeListener('desktop-pet:cancel-chat', handleCancelChat)
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

  // 窗口可见性检测：隐藏时通知渲染进程降低帧率，显示时恢复正常帧率
  const handleWindowShow = () => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.webContents.send('desktop-pet:visibility-changed', { visible: true })
      logger.info('Desktop pet window shown, notifying renderer to resume full FPS')
    }
  }

  const handleWindowHide = () => {
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.webContents.send('desktop-pet:visibility-changed', { visible: false })
      logger.info('Desktop pet window hidden, notifying renderer to reduce FPS')
    }
  }

  desktopPetWindow.on('show', handleWindowShow)
  desktopPetWindow.on('hide', handleWindowHide)

  desktopPetWindow.webContents.on('did-finish-load', () => {
    if (modelInfo) {
      desktopPetWindow?.webContents.send('desktop-pet:load-model', modelInfo)
    }
  })
}

export const closeDesktopPet = (): void => {
  if (desktopPetChatWindow && !desktopPetChatWindow.isDestroyed()) {
    desktopPetChatWindow.close()
    desktopPetChatWindow = null
  }
  if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
    desktopPetWindow.close()
    desktopPetWindow = null
  }
}

export const isDesktopPetRunning = (): boolean => {
  return desktopPetWindow !== null && !desktopPetWindow.isDestroyed()
}

export const sendToDesktopPet = (channel: string, ...args: unknown[]): boolean => {
  if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
    desktopPetWindow.webContents.send(channel, ...args)
    return true
  }
  return false
}

export function registerDesktopPetIpc(mainWindow: BrowserWindow | null): void {
  const assertTrustedSender = (event: IpcMainInvokeEvent): boolean => {
    if (!mainWindow || event.sender !== mainWindow.webContents) {
      return false
    }
    return true
  }

  ipcMain.handle('desktop-pet:open', async (event: IpcMainInvokeEvent, modelInfo?: ImportedModelRecord) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    createDesktopPet(mainWindow, modelInfo)
    return { success: true }
  })

  ipcMain.handle('desktop-pet:close', async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    closeDesktopPet()
    return { success: true }
  })

  ipcMain.handle('desktop-pet:isRunning', async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    return isDesktopPetRunning()
  })

  ipcMain.handle('desktop-pet:loadModel', async (event: IpcMainInvokeEvent, modelInfo: ImportedModelRecord) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    return sendToDesktopPet('desktop-pet:load-model', modelInfo)
      ? { success: true }
      : { success: false, error: 'Desktop pet window not running' }
  })

  ipcMain.handle('desktop-pet:show', async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.show()
      desktopPetWindow.setAlwaysOnTop(true, 'screen-saver')
    }
    return { success: true }
  })

  ipcMain.handle('desktop-pet:hide', async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      desktopPetWindow.hide()
    }
    return { success: true }
  })

  ipcMain.handle('desktop-pet:triggerMotion', async (event: IpcMainInvokeEvent, group: string, index: number) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    return sendToDesktopPet('desktop-pet:trigger-motion', group, index)
      ? { success: true }
      : { success: false }
  })

  ipcMain.handle('desktop-pet:triggerExpression', async (event: IpcMainInvokeEvent, name: string) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    return sendToDesktopPet('desktop-pet:trigger-expression', name)
      ? { success: true }
      : { success: false }
  })

  ipcMain.handle('desktop-pet:setPosition', async (event: IpcMainInvokeEvent, x: number, y: number) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return { success: false, error: 'Invalid position: x and y must be finite numbers' }
    }
    const clampedX = Math.max(-10000, Math.min(10000, x))
    const clampedY = Math.max(-10000, Math.min(10000, y))
    return sendToDesktopPet('desktop-pet:set-position', clampedX, clampedY)
      ? { success: true }
      : { success: false, error: 'Desktop pet window not running' }
  })

  ipcMain.handle('desktop-pet:setScale', async (event: IpcMainInvokeEvent, scale: number) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    if (!Number.isFinite(scale)) {
      return { success: false, error: 'Invalid scale: must be a finite number' }
    }
    const clampedScale = Math.max(0.1, Math.min(10, scale))
    return sendToDesktopPet('desktop-pet:set-scale', clampedScale)
      ? { success: true }
      : { success: false, error: 'Desktop pet window not running' }
  })

  ipcMain.handle('desktop-pet:sendSubtitle', async (event: IpcMainInvokeEvent, text: string) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    if (typeof text !== 'string') {
      return { success: false, error: 'Invalid subtitle text: must be a string' }
    }
    return sendToDesktopPet('desktop-pet:subtitle', text)
      ? { success: true }
      : { success: false, error: 'Desktop pet window not running' }
  })

  ipcMain.handle('desktop-pet:hideSubtitle', async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    return sendToDesktopPet('desktop-pet:subtitle-hide')
      ? { success: true }
      : { success: false, error: 'Desktop pet window not running' }
  })

  ipcMain.handle('desktop-pet:setStreamingState', async (event: IpcMainInvokeEvent, isStreaming: boolean) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    sendToDesktopPet('desktop-pet:streaming-state', isStreaming)
    desktopPetChatWindow?.webContents.send('desktop-pet:streaming-state', isStreaming)
    return { success: true }
  })

  ipcMain.handle('desktop-pet:driveLipSync', async (event: IpcMainInvokeEvent, value: number) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    if (!Number.isFinite(value)) {
      return { success: false, error: 'Invalid lip-sync value: must be a finite number' }
    }
    const clampedValue = Math.max(-1, Math.min(1, value))
    return sendToDesktopPet('desktop-pet:lip-sync', clampedValue)
      ? { success: true }
      : { success: false, error: 'Desktop pet window not running' }
  })

  ipcMain.handle('desktop-pet:drivePadEmotion', async (event: IpcMainInvokeEvent, pleasure: number, arousal: number, dominance: number) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    if (!Number.isFinite(pleasure) || !Number.isFinite(arousal) || !Number.isFinite(dominance)) {
      return { success: false, error: 'Invalid PAD values: all must be finite numbers' }
    }
    const clampedPleasure = Math.max(-1, Math.min(1, pleasure))
    const clampedArousal = Math.max(-1, Math.min(1, arousal))
    const clampedDominance = Math.max(-1, Math.min(1, dominance))
    return sendToDesktopPet('desktop-pet:pad-emotion', { pleasure: clampedPleasure, arousal: clampedArousal, dominance: clampedDominance })
      ? { success: true }
      : { success: false, error: 'Desktop pet window not running' }
  })

  ipcMain.handle('desktop-pet:setCoreParam', async (event: IpcMainInvokeEvent, paramId: string, value: number) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    const ALLOWED_PARAMS = new Set([
      'ParamAngleX', 'ParamAngleY', 'ParamAngleZ',
      'ParamEyeLOpen', 'ParamEyeROpen',
      'ParamEyeBallX', 'ParamEyeBallY',
      'ParamBrowLY', 'ParamBrowRY',
      'ParamBrowLAngle', 'ParamBrowRAngle',
      'ParamBrowLForm', 'ParamBrowRForm',
      'ParamMouthOpenY', 'ParamMouthForm',
      'ParamCheek', 'ParamBreath',
      'ParamBodyAngleX', 'ParamBodyAngleY', 'ParamBodyAngleZ',
      'Param14'
    ])
    if (typeof paramId !== 'string' || !ALLOWED_PARAMS.has(paramId)) {
      return { success: false, error: `Invalid paramId: "${paramId}" is not in the allowed whitelist` }
    }
    if (!Number.isFinite(value)) {
      return { success: false, error: 'Invalid param value: must be a finite number' }
    }
    return sendToDesktopPet('desktop-pet:set-core-param', paramId, value)
      ? { success: true }
      : { success: false, error: 'Desktop pet window not running' }
  })

  ipcMain.handle('desktop-pet:getModelCapabilities', async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return { success: false, error: 'Unauthorized sender' }
    if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
      return new Promise((resolve) => {
        const requestId = `cap-${Date.now()}`
        let handled = false
        const handler = (_event: unknown, id: string, capabilities: unknown) => {
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
