import { contextBridge, ipcRenderer } from 'electron'

export interface InstallerAPI {
  getLicense: () => Promise<string>
  getDefaultPath: () => Promise<string>
  browseDirectory: (defaultPath?: string) => Promise<string | null>
  getDiskSpace: (path: string) => Promise<{ free: number; total: number }>
  validatePath: (targetPath: string) => Promise<{ valid: boolean; errors: string[] }>
  startInstallation: (options: {
    installPath: string
    agreeLicense: boolean
    allowTelemetry: boolean
    createShortcut: boolean
    autoLaunch: boolean
  }) => Promise<{ success: boolean; error?: string }>
  launchApp: () => Promise<void>
  openUrl: (url: string) => Promise<void>
  minimize: () => void
  close: () => void
  onProgress: (callback: (data: { progress: number; step: number; totalSteps: number; message: string }) => void) => () => void
}

const installerAPI: InstallerAPI = {
  getLicense: () => ipcRenderer.invoke('installer:get-license'),
  getDefaultPath: () => ipcRenderer.invoke('installer:get-default-path'),
  browseDirectory: (defaultPath?: string) => ipcRenderer.invoke('installer:browse-directory', defaultPath),
  getDiskSpace: (path: string) => ipcRenderer.invoke('installer:get-disk-space', path),
  validatePath: (targetPath: string) => ipcRenderer.invoke('installer:validate-path', targetPath),
  startInstallation: (options) => ipcRenderer.invoke('installer:start-installation', options),
  launchApp: () => ipcRenderer.invoke('installer:launch-app'),
  openUrl: (url: string) => ipcRenderer.invoke('installer:open-url', url),
  minimize: () => ipcRenderer.send('installer:minimize'),
  close: () => ipcRenderer.send('installer:close'),
  onProgress: (callback) => {
    const handler = (_event: unknown, data: Parameters<typeof callback>[0]) => callback(data)
    ipcRenderer.on('installer:progress', handler)
    return () => ipcRenderer.removeListener('installer:progress', handler)
  }
}

contextBridge.exposeInMainWorld('installerAPI', installerAPI)
