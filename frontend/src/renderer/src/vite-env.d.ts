/// <reference types="vite/client" />

import type { ElectronApi, ExposedIpcRenderer } from '@shared/ipc-types'

declare global {
  interface Window {
    /** Live2D Cubism Core 原生库（第三方，无 TypeScript 类型声明） */
    Live2DCubismCore: any
    /** preload 通过 contextBridge 暴露的 API */
    api: ElectronApi
    /** preload 通过 contextBridge 暴露的受限 ipcRenderer */
    electron?: {
      ipcRenderer: ExposedIpcRenderer
    }
  }
}
