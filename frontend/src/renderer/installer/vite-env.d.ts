/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}

interface Window {
  installerAPI: {
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
}
