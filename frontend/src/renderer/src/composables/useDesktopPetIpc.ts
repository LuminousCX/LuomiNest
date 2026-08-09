/**
 * LuomiNest 桌面宠物 IPC 监听器集中管理 composable
 *
 * 从 DesktopPetView.vue 拆分，集中注册/移除桌宠 IPC 监听器。
 * - 用类型化 handler 接口消除 `event: any`
 * - 用命名常量消除魔法字符串（通道字面量见 DesktopPetIpcChannels.ON）
 */
import type { PetModelInfo } from '@shared/ipc-types'

/** IPC 监听器函数签名（与 ExposedIpcRenderer.on 的 listener 一致） */
type IpcListener = (event: unknown, ...args: unknown[]) => void

/** PAD 情绪向量 */
interface PadVector {
  pleasure: number
  arousal: number
  dominance: number
}

/**
 * 桌面宠物 IPC handler 契约。
 * 每个 handler 只接收业务参数（不含 IPC event），由 composable 内部解包。
 */
export interface DesktopPetIpcHandlers {
  onLoadModel: (modelInfo: PetModelInfo) => void | Promise<void>
  onTriggerMotion: (group: string, index: number) => void | Promise<void>
  onTriggerExpression: (name: string) => void | Promise<void>
  onSetScale: (scale: number) => void
  onLipSync: (value: number) => void
  onPadEmotion: (pad: PadVector) => void
  onSetCoreParam: (paramId: string, value: number) => void
  onGetModelCapabilities: (requestId: string) => void
  onSubtitle: (text: string) => void
  onSubtitleHide: () => void
  onStreamingState: (isStreaming: boolean) => void
  /** 窗口可见性变化：visible=false 时降低帧率，visible=true 时恢复正常帧率 */
  onVisibilityChanged: (visible: boolean) => void
}

/** 通道名与对应 handler 的映射条目 */
interface IpcBinding {
  channel: string
  listener: IpcListener
}

export const useDesktopPetIpc = (handlers: DesktopPetIpcHandlers) => {
  let bindings: IpcBinding[] = []

  const setupIpc = (): void => {
    // 见 DesktopPetIpcChannels.ON
    bindings = [
      {
        channel: 'desktop-pet:load-model',
        listener: (_e, ...args) => { void handlers.onLoadModel(args[0] as PetModelInfo) }
      },
      {
        channel: 'desktop-pet:trigger-motion',
        listener: (_e, ...args) => { void handlers.onTriggerMotion(args[0] as string, args[1] as number) }
      },
      {
        channel: 'desktop-pet:trigger-expression',
        listener: (_e, ...args) => { void handlers.onTriggerExpression(args[0] as string) }
      },
      {
        channel: 'desktop-pet:set-scale',
        listener: (_e, ...args) => { handlers.onSetScale(args[0] as number) }
      },
      {
        channel: 'desktop-pet:lip-sync',
        listener: (_e, ...args) => { handlers.onLipSync(args[0] as number) }
      },
      {
        channel: 'desktop-pet:pad-emotion',
        listener: (_e, ...args) => { handlers.onPadEmotion(args[0] as PadVector) }
      },
      {
        channel: 'desktop-pet:set-core-param',
        listener: (_e, ...args) => { handlers.onSetCoreParam(args[0] as string, args[1] as number) }
      },
      {
        channel: 'desktop-pet:get-model-capabilities',
        listener: (_e, ...args) => { handlers.onGetModelCapabilities(args[0] as string) }
      },
      {
        channel: 'desktop-pet:subtitle',
        listener: (_e, ...args) => { handlers.onSubtitle(args[0] as string) }
      },
      {
        channel: 'desktop-pet:subtitle-hide',
        listener: () => { handlers.onSubtitleHide() }
      },
      {
        channel: 'desktop-pet:streaming-state',
        listener: (_e, ...args) => { handlers.onStreamingState(args[0] as boolean) }
      },
      {
        channel: 'desktop-pet:visibility-changed',
        listener: (_e, ...args) => { handlers.onVisibilityChanged((args[0] as { visible: boolean }).visible) }
      }
    ]

    for (const { channel, listener } of bindings) {
      window.electron?.ipcRenderer.on(channel, listener as Parameters<typeof window.electron.ipcRenderer.on>[1])
    }
  }

  const cleanupIpc = (): void => {
    for (const { channel, listener } of bindings) {
      window.electron?.ipcRenderer.removeListener(channel, listener as Parameters<typeof window.electron.ipcRenderer.removeListener>[1])
    }
    bindings = []
  }

  return {
    setupIpc,
    cleanupIpc
  }
}
