/**
 * LuomiNest 渲染进程统一日志器
 *
 * 渲染进程无 Node.js 访问能力（contextIsolation: true），因此仅做 console 薄封装。
 * 按 scope 缓存，通过 import.meta.env.DEV 控制级别。
 *
 * Dev 模式：info/warn/error/debug 全部输出
 * Prod 模式：info/warn/error 输出，debug 静默
 *
 * 格式：[LEVEL][Scope] message
 * 示例：[INFO][LuomiNestLive2D] 模型加载完成
 */

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

  const logger: LuomiNestRendererLogger = {
    info: (...args: unknown[]) => console.info(...formatArgs('INFO', scope, args)),
    warn: (...args: unknown[]) => console.warn(...formatArgs('WARN', scope, args)),
    error: (...args: unknown[]) => console.error(...formatArgs('ERROR', scope, args)),
    debug: (...args: unknown[]) => {
      if (isDev) console.debug(...formatArgs('DEBUG', scope, args))
    },
  }

  loggerCache.set(scope, logger)
  return logger
}
