import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron'
import { join } from 'path'
import { readFileSync, existsSync, mkdirSync, copyFileSync, readdirSync, statSync, rmSync } from 'fs'
import { execFile, spawn } from 'child_process'

let installerWindow: BrowserWindow | null = null

const isDev = !app.isPackaged

const getAssetPath = (...paths: string[]): string => {
  if (isDev) {
    return join(__dirname, '..', '..', '..', '..', 'src', 'renderer', 'installer', ...paths)
  }
  return join(process.resourcesPath, ...paths)
}

const LICENSE_TEXT = (() => {
  try {
    const licensePath = isDev
      ? join(__dirname, '..', '..', '..', '..', '..', 'LICENSE')
      : join(process.resourcesPath, 'LICENSE')
    if (existsSync(licensePath)) {
      return readFileSync(licensePath, 'utf-8')
    }
  } catch {
    // ignore
  }
  return ''
})()

const getDefaultInstallPath = (): string => {
  const productName = 'LuomiNest'
  if (process.platform === 'win32') {
    const { env } = process
    const localAppData = env.LOCALAPPDATA || join(env.USERPROFILE || '', 'AppData', 'Local')
    return join(localAppData, 'Programs', productName)
  }
  if (process.platform === 'darwin') {
    return join('/Applications', `${productName}.app`)
  }
  return join(process.env.HOME || '/usr/local', `${productName.toLowerCase()}`)
}

export const createInstallerWindow = (): BrowserWindow => {
  if (installerWindow && !installerWindow.isDestroyed()) {
    installerWindow.focus()
    return installerWindow
  }

  installerWindow = new BrowserWindow({
    width: 720,
    height: 580,
    minWidth: 640,
    minHeight: 480,
    frame: false,
    transparent: false,
    resizable: true,
    maximizable: false,
    minimizable: true,
    titleBarStyle: 'hidden',
    trafficLightPosition: { x: 16, y: 16 },
    backgroundColor: '#1a1a2e',
    show: false,
    webPreferences: {
      preload: join(__dirname, '../preload/installer.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  })

  const installerHtmlPath = getAssetPath('index.html')

  if (isDev) {
    installerWindow.loadURL(`http://localhost:5174/installer`)
  } else {
    installerWindow.loadFile(installerHtmlPath)
  }

  installerWindow.once('ready-to-show', () => {
    installerWindow?.show()
  })

  return installerWindow
}

export const closeInstallerWindow = (): void => {
  if (installerWindow && !installerWindow.isDestroyed()) {
    installerWindow.close()
    installerWindow = null
  }
}

ipcMain.handle('installer:get-license', async () => {
  return LICENSE_TEXT
})

ipcMain.handle('installer:get-default-path', async () => {
  return getDefaultInstallPath()
})

ipcMain.handle('installer:browse-directory', async (_event, defaultPath?: string) => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory'],
    defaultPath: defaultPath || getDefaultInstallPath(),
    buttonLabel: '选择此目录',
    title: '选择安装位置'
  })
  if (result.canceled || result.filePaths.length === 0) {
    return null
  }
  return result.filePaths[0]
})

ipcMain.handle('installer:get-disk-space', async (_event, path: string) => {
  try {
    const { statfs } = await import('node:fs/promises')
    const stats = await statfs(path)
    return {
      free: stats.bfree * stats.bsize,
      total: stats.blocks * stats.bsize
    }
  } catch {
    return { free: 0, total: 0 }
  }
})

ipcMain.handle('installer:validate-path', async (_event, targetPath: string) => {
  const errors: string[] = []

  if (!targetPath || targetPath.trim().length === 0) {
    errors.push('安装路径不能为空')
    return { valid: false, errors }
  }

  if (existsSync(targetPath)) {
    const stat = statSync(targetPath)
    if (!stat.isDirectory()) {
      errors.push('目标路径不是一个有效的目录')
    } else {
      const contents = readdirSync(targetPath)
      if (contents.length > 0) {
        errors.push('目标目录不为空，安装可能会覆盖现有文件')
      }
    }
  }

  const parentDir = join(targetPath, '..')
  if (!existsSync(parentDir)) {
    errors.push('父目录不存在')
  }

  return { valid: errors.length === 0, errors }
})

ipcMain.handle('installer:start-installation', async (
  _event,
  options: {
    installPath: string
    agreeLicense: boolean
    allowTelemetry: boolean
    createShortcut: boolean
    autoLaunch: boolean
  }
): Promise<{ success: boolean; error?: string }> => {
  const { installPath, allowTelemetry, createShortcut, autoLaunch } = options

  try {
    await new Promise<void>((resolve, reject) => {
      let progress = 0
      const totalSteps = 5
      const reportProgress = (step: number, message: string) => {
        progress = Math.round((step / totalSteps) * 100)
        installerWindow?.webContents.send('installer:progress', {
          progress,
          step,
          totalSteps,
          message
        })
      }

      const doStep = async (stepNum: number, msg: string, fn: () => void | Promise<void>) => {
        reportProgress(stepNum, msg)
        await fn()
        await new Promise(r => setTimeout(r, 300))
      }

      ;(async () => {
        try {
          await doStep(1, '正在准备安装环境...', async () => {
            if (!existsSync(installPath)) {
              mkdirSync(installPath, { recursive: true })
            }
          })

          await doStep(2, '正在复制应用程序文件...', async () => {
            const sourcePath = isDev
              ? join(__dirname, '..', '..', '..')
              : app.getAppPath()

            const copyDir = (src: string, dest: string) => {
              mkdirSync(dest, { recursive: true })
              const entries = readdirSync(src, { withFileTypes: true })
              for (const entry of entries) {
                const srcPath = join(src, entry.name)
                const destPath = join(dest, entry.name)
                if (entry.isDirectory()) {
                  copyDir(srcPath, destPath)
                } else {
                  copyFileSync(srcPath, destPath)
                }
              }
            }

            copyDir(sourcePath, installPath)
          })

          await doStep(3, '正在配置系统...', async () => {
            if (createShortcut && process.platform === 'win32') {
              const shellLinkPath = join(
                process.env.APPDATA || '',
                'Microsoft',
                'Windows',
                'Start Menu',
                'Programs',
                'LuomiNest.lnk'
              )
              try {
                const { shell: shellModule } = await import('electron')
                shellModule.writeShortcutLink(shellLinkPath, {
                  target: join(installPath, 'LuomiNest.exe'),
                  description: 'LuomiNest - Distributed AI Companion Platform',
                  icon: join(installPath, 'resources', 'icon.ico'),
                  iconIndex: 0,
                  workingDirectory: installPath
                })
              } catch {
                // shortcut creation is non-critical
              }
            }
          })

          await doStep(4, '正在保存用户配置...', async () => {
            const configStore = await import('../services/config-store').then(m => m.default)
            configStore.set('telemetry.enabled', allowTelemetry)
            configStore.set('autoLaunch', autoLaunch)
            configStore.set('installPath', installPath)
            configStore.set('installed', true)
            configStore.set('installDate', new Date().toISOString())
          })

          await doStep(5, '安装完成！', async () => {})

          resolve()
        } catch (err) {
          reject(err)
        }
      })()
    })

    return { success: true }
  } catch (error) {
    return { success: false, error: String(error) }
  }
})

ipcMain.handle('installer:launch-app', async () => {
  if (isDev) {
    return
  }

  const exePath = process.platform === 'win32'
    ? join(app.getPath('exe'), '..', 'LuomiNest.exe')
    : app.getPath('exe')

  try {
    if (process.platform === 'win32') {
      execFile(exePath, [], { detached: true }, () => {})
    } else {
      spawn(exePath, [], { detached: true, stdio: 'ignore' }).unref()
    }
  } catch {
    // ignore launch errors
  }

  app.quit()
})

ipcMain.handle('installer:open-url', async (_event, url: string) => {
  shell.openExternal(url)
})

ipcMain.handle('installer:minimize', () => {
  installerWindow?.minimize()
})

ipcMain.handle('installer:close', () => {
  app.quit()
})
