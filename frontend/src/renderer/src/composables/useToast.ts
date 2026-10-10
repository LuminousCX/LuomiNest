import { ref } from 'vue'

/**
 * 全局通知队列（右下角 SwipeToast 容器消费）。
 *
 * 兼容性说明：
 * - 历史签名 toast.success(msg) / toast.error(msg, 5000)（数字 duration）完全保留；
 * - 第二参数现为 `ToastOptions | number`，推荐传对象以使用 description / action。
 *
 * 自动关闭计时由 ToastContainer 内的 fuse 进度条驱动（hover / 拖拽 / 聚焦 / 页面隐藏时
 * 暂停），store 层不再挂 setTimeout——否则 hover 暂停无法实现。
 */

/** toast 上的操作按钮（如"重试/撤销"），点击后默认关闭该条 toast */
export interface ToastAction {
  label: string
  handler: () => void
}

export interface ToastOptions {
  /** 次行说明文案：建议怎么操作 / 技术细节（错误场景） */
  description?: string
  /** 自动关闭毫秒数；0 表示不自动关闭 */
  duration?: number
  /** 操作按钮（如"重试"） */
  action?: ToastAction
}

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface ToastItem {
  id: number
  type: ToastType
  message: string
  description?: string
  action?: ToastAction
  duration: number
}

const toasts = ref<ToastItem[]>([])
let nextId = 0

/** 同时可见上限，超出时丢弃最旧的，防止错误风暴堆满屏幕 */
const MAX_VISIBLE = 5

/** 各变体默认自动关闭时长：error 最长，给用户足够时间读建议 */
const DEFAULT_DURATION: Record<ToastType, number> = {
  success: 3000,
  info: 3000,
  warning: 4000,
  error: 6500,
}

function addToast(type: ToastType, message: string, options: ToastOptions | number = {}) {
  const opts: ToastOptions = typeof options === 'number' ? { duration: options } : options
  const duration = opts.duration ?? DEFAULT_DURATION[type]
  const id = nextId++
  toasts.value.push({
    id,
    type,
    message,
    description: opts.description,
    action: opts.action,
    duration,
  })
  if (toasts.value.length > MAX_VISIBLE) {
    toasts.value.splice(0, toasts.value.length - MAX_VISIBLE)
  }
}

function removeToast(id: number) {
  const idx = toasts.value.findIndex(t => t.id === id)
  if (idx !== -1) toasts.value.splice(idx, 1)
}

export function useToast() {
  return {
    toasts,
    success: (msg: string, options?: ToastOptions | number) => addToast('success', msg, options),
    error: (msg: string, options?: ToastOptions | number) => addToast('error', msg, options),
    warning: (msg: string, options?: ToastOptions | number) => addToast('warning', msg, options),
    info: (msg: string, options?: ToastOptions | number) => addToast('info', msg, options),
    remove: removeToast,
  }
}
