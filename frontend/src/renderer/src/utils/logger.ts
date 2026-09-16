/**
 * LuomiNest 渲染进程统一日志器
 *
 * 渲染进程无 Node.js 访问能力（contextIsolation: true），因此做 console 薄封装。
 * 按 scope 缓存，通过 import.meta.env.DEV 控制级别。
 *
 * Dev 模式：info/warn/error/debug 全部输出
 * Prod 模式：info/warn/error 输出，debug 静默
 *
 * 统一日志系统：所有输出在 console 之外同步进入批量上报队列，经
 * window.api.log.append（log:append，fire-and-forget）送到主进程 log-hub
 * 内存环形缓冲（source='renderer'）。队列 500ms 或满 20 条即刷；IPC 未就绪
 * （preload 缺失 / 早期窗口）时静默丢弃，绝不阻塞业务。
 *
 * 另挂 window error / unhandledrejection 全局捕获，以 level='error' 上报，
 * 保证脚本异常也进入统一日志页。
 *
 * 格式：[LEVEL][Scope] message
 * 示例：[INFO][LuomiNestLive2D] 模型加载完成
 */

import type { LogEntry, LogLevel } from '@shared/ipc-types'

export interface LuomiNestRendererLogger {
  info: (...args: unknown[]) => void
  warn: (...args: unknown[]) => void
  error: (...args: unknown[]) => void
  debug: (...args: unknown[]) => void
}

const isDev = import.meta.env.DEV

const loggerCache = new Map<string, LuomiNestRendererLogger>()

/** 格式化日志参数：在前面插入 [LEVEL][Scope] 前缀 */
const formatArgs = (level: string, scope: string, args: unknown[]): unknown[] => {
  if (args.length > 0 && typeof args[0] === 'string') {
    return [`[${level}][${scope}] ${args[0]}`, ...args.slice(1)]
  }
  return [`[${level}][${scope}]`, ...args]
}

/* ============================================================================
 * 主进程 log-hub 批量上报（fire-and-forget）
 * ========================================================================== */

const FLUSH_INTERVAL_MS = 500
const FLUSH_BATCH_SIZE = 20
const MAX_QUEUE_SIZE = 500

const pendingEntries: LogEntry[] = []
let flushTimer: ReturnType<typeof setTimeout> | null = null

const serializeArg = (arg: unknown): string => {
  if (typeof arg === 'string') return arg
  if (arg instanceof Error) return arg.stack || `${arg.name}: ${arg.message}`
  if (typeof arg === 'object' && arg !== null) {
    try {
      const seen = new WeakSet<object>()
      return (
        JSON.stringify(arg, (_key, value) => {
          if (typeof value === 'object' && value !== null) {
            if (seen.has(value)) return '[Circular]'
            seen.add(value)
          }
          return value
        }) ?? String(arg)
      )
    } catch {
      return String(arg)
    }
  }
  return String(arg)
}

const serializeArgs = (args: unknown[]): string => args.map(serializeArg).join(' ')

const flushQueue = (): void => {
  flushTimer = null
  if (pendingEntries.length === 0) return
  const batch = pendingEntries.splice(0, pendingEntries.length)
  try {
    // preload 未就绪 / 上下文缺失时直接吞掉，避免日志系统反噬业务
    void window.api?.log?.append(batch)?.catch(() => {})
  } catch {
    // 静默丢弃
  }
}

const enqueueLogEntry = (level: LogLevel, scope: string, args: unknown[]): void => {
  const entry: LogEntry = {
    seq: 0, // 主进程 log-hub 统一分配，渲染层占位
    ts: new Date().toISOString(),
    level,
    source: 'renderer',
    scope,
    message: serializeArgs(args),
  }
  pendingEntries.push(entry)
  // 队列超限时丢弃最旧的条目（日志系统自身不应无界占用内存）
  if (pendingEntries.length > MAX_QUEUE_SIZE) {
    pendingEntries.splice(0, pendingEntries.length - MAX_QUEUE_SIZE)
  }
  if (pendingEntries.length >= FLUSH_BATCH_SIZE) {
    if (flushTimer) {
      clearTimeout(flushTimer)
    }
    flushQueue()
    return
  }
  if (!flushTimer) {
    flushTimer = setTimeout(flushQueue, FLUSH_INTERVAL_MS)
  }
}

/* ============================================================================
 * 全局错误捕获（window error / unhandledrejection）
 * ========================================================================== */

const GLOBAL_ERROR_SCOPE = 'Window'

const installGlobalErrorHandlers = (): void => {
  if (typeof window === 'undefined') return
  window.addEventListener('error', (event) => {
    const where = event.filename ? ` @ ${event.filename}:${event.lineno}:${event.colno}` : ''
    enqueueLogEntry('error', GLOBAL_ERROR_SCOPE, [`${event.message}${where}`])
  })
  window.addEventListener('unhandledrejection', (event) => {
    const reason = (event as PromiseRejectionEvent).reason
    enqueueLogEntry('error', GLOBAL_ERROR_SCOPE, [
      'Unhandled promise rejection:',
      reason instanceof Error ? reason.stack || reason.message : reason,
    ])
  })
}

let globalHandlersInstalled = false

/* ============================================================================
 * scoped 日志器
 * ========================================================================== */

/**
 * 创建带 scope 的 LuomiNest 渲染进程日志器
 *
 * @param scope - 日志前缀，如 'LuomiNestLive2D'、'LuomiNestBrowser'、'Workspace'
 * @returns LuomiNestRendererLogger 实例（按 scope 缓存）
 *
 * @example
 * const logger = createLuomiNestRendererLogger('LuomiNestLive2D')
 * logger.info('模型加载完成')  // 输出: [INFO][LuomiNestLive2D] 模型加载完成
 */
export const createLuomiNestRendererLogger = (scope: string): LuomiNestRendererLogger => {
  const cached = loggerCache.get(scope)
  if (cached) return cached

  // 首个日志器创建时挂一次全局错误捕获（模块顶层挂会过早，窗口上下文此时可能未稳定）
  if (!globalHandlersInstalled) {
    globalHandlersInstalled = true
    installGlobalErrorHandlers()
  }

  const logger: LuomiNestRendererLogger = {
    info: (...args: unknown[]) => {
      console.info(...formatArgs('INFO', scope, args))
      enqueueLogEntry('info', scope, args)
    },
    warn: (...args: unknown[]) => {
      console.warn(...formatArgs('WARN', scope, args))
      enqueueLogEntry('warn', scope, args)
    },
    error: (...args: unknown[]) => {
      console.error(...formatArgs('ERROR', scope, args))
      enqueueLogEntry('error', scope, args)
    },
    debug: (...args: unknown[]) => {
      if (isDev) console.debug(...formatArgs('DEBUG', scope, args))
      // debug 仅 dev 记入 hub（与主进程 file transport 的 dev=debug 级别对齐），prod 静默
      if (isDev) enqueueLogEntry('debug', scope, args)
    },
  }

  loggerCache.set(scope, logger)
  return logger
}
