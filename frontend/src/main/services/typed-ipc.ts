import { ipcMain, type IpcMainEvent, type IpcMainInvokeEvent } from 'electron'
import type { IpcInvokeChannel, IpcSendChannel } from '@shared/ipc-types'

/**
 * 带通道类型收窄的 IPC 注册辅助。
 *
 * channel 参数收窄到 shared/ipc-types.ts 中 IpcChannels 派生的字面量联合，
 * main 侧手写未登记的 channel 字符串会直接编译报错，与 preload 端的
 * invoke / send 收窄保持同一常量来源，避免两端隐式契约漂移。
 */

/** ipcMain.handle + invoke 通道收窄（renderer → main 请求应答） */
export const handleIpc = (
  channel: IpcInvokeChannel,
  listener: (event: IpcMainInvokeEvent, ...args: any[]) => unknown
): void => {
  ipcMain.handle(channel, listener)
}

/** ipcMain.on + 单向 send 通道收窄（renderer → main 单向） */
export const onIpc = (channel: IpcSendChannel, listener: (event: IpcMainEvent, ...args: any[]) => void): void => {
  ipcMain.on(channel, listener)
}
