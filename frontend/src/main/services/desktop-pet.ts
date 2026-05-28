import { BrowserWindow, ipcMain, Menu, screen } from 'electron'
import { join } from 'path'
import { platform } from 'os'
import { existsSync, readdirSync, readFileSync, writeFileSync, mkdirSync, rmSync } from 'fs'
import { PATHS } from './paths'

const isDev = !require('electron').app.isPackaged
const isMac = platform() === 'darwin'

const CSP_DEV = "default-src 'self' luominest-avatar:; script-src 'self' 'unsafe-inline' 'unsafe-eval' luominest-avatar:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: https: http: blob: luominest-avatar:; connect-src 'self' blob: luominest-avatar: https://fonts.googleapis.com https://fonts.gstatic.com https: http: wss:; worker-src 'self' blob:"
const CSP_PROD = "default-src 'self' luominest-avatar:; script-src 'self' 'unsafe-inline' luominest-avatar:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: https: http: blob: luominest-avatar:; connect-src 'self' blob: luominest-avatar: https://fonts.googleapis.com https://fonts.gstatic.com https: http: wss:; worker-src 'self' blob:"

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
  { id: 'hiyori', name: 'Hiyori', url: 'luominest-avatar://hiyori/Hiyori.model3.json', scale: 0.25, type: 'live2d', tags: ['Cubism4', 'Built-in'] },
  { id: 'shizuku', name: 'Shizuku', url: 'luominest-avatar://shizuku/shizuku.model3.json', scale: 0.25, type: 'live2d', tags: ['Cubism4', 'Built-in'] }
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

export const getDesktopPetWindow = (): BrowserWindow | null => desktopPetWindow

export const createDesktopPet = (mainWindow: BrowserWindow | null, modelInfo?: ImportedModelRecord): void => {
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
      backgroundThrottling: false,
      partition: 'persist:desktop-pet'
    }
  })

  desktopPetWindow.setVisibleOnAllWorkspaces(true)
  desktopPetWindow.setAlwaysOnTop(true, 'screen-saver')

  const CSP_PET_WINDOW = isDev ? CSP_DEV : CSP_PROD
  desktopPetWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [CSP_PET_WINDOW]
      }
    })
  })

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
    { label: 'Quit', click: () => { require('electron').app.quit() } }
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

export const closeDesktopPet = (): void => {
  if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
    desktopPetWindow.close()
    desktopPetWindow = null
  }
}

export const isDesktopPetRunning = (): boolean => {
  return desktopPetWindow !== null && !desktopPetWindow.isDestroyed()
}

export const sendToDesktopPet = (channel: string, ...args: any[]): boolean => {
  if (desktopPetWindow && !desktopPetWindow.isDestroyed()) {
    desktopPetWindow.webContents.send(channel, ...args)
    return true
  }
  return false
}

export function registerDesktopPetIpc(): void {
  const { ipcMain } = require('electron')

  ipcMain.handle('desktop-pet:open', async (_e, modelInfo?: ImportedModelRecord) => {
    createDesktopPet(null, modelInfo)
    return { success: true }
  })

  ipcMain.handle('desktop-pet:close', async () => {
    closeDesktopPet()
    return { success: true }
  })

  ipcMain.handle('desktop-pet:isRunning', async () => {
    return isDesktopPetRunning()
  })

  ipcMain.handle('desktop-pet:loadModel', async (_e, modelInfo: ImportedModelRecord) => {
    return sendToDesktopPet('desktop-pet:load-model', modelInfo)
      ? { success: true }
      : { success: false, error: 'Desktop pet window not running' }
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
    return sendToDesktopPet('desktop-pet:trigger-motion', group, index)
      ? { success: true }
      : { success: false }
  })

  ipcMain.handle('desktop-pet:triggerExpression', async (_e, name: string) => {
    return sendToDesktopPet('desktop-pet:trigger-expression', name)
      ? { success: true }
      : { success: false }
  })

  ipcMain.handle('desktop-pet:setPosition', async (_e, x: number, y: number) => {
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return { success: false, error: 'Invalid position: x and y must be finite numbers' }
    }
    const clampedX = Math.max(-10000, Math.min(10000, x))
    const clampedY = Math.max(-10000, Math.min(10000, y))
    return sendToDesktopPet('desktop-pet:set-position', clampedX, clampedY)
      ? { success: true }
      : { success: false, error: 'Desktop pet window not running' }
  })

  ipcMain.handle('desktop-pet:setScale', async (_e, scale: number) => {
    if (!Number.isFinite(scale)) {
      return { success: false, error: 'Invalid scale: must be a finite number' }
    }
    const clampedScale = Math.max(0.1, Math.min(10, scale))
    return sendToDesktopPet('desktop-pet:set-scale', clampedScale)
      ? { success: true }
      : { success: false, error: 'Desktop pet window not running' }
  })

  ipcMain.handle('desktop-pet:driveLipSync', async (_e, value: number) => {
    if (!Number.isFinite(value)) {
      return { success: false, error: 'Invalid lip-sync value: must be a finite number' }
    }
    const clampedValue = Math.max(-1, Math.min(1, value))
    return sendToDesktopPet('desktop-pet:lip-sync', clampedValue)
      ? { success: true }
      : { success: false, error: 'Desktop pet window not running' }
  })

  ipcMain.handle('desktop-pet:drivePadEmotion', async (_e, pleasure: number, arousal: number, dominance: number) => {
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

  ipcMain.handle('desktop-pet:setCoreParam', async (_e, paramId: string, value: number) => {
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
