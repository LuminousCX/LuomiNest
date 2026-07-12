/**
 * LuomiNest 主进程统一日志器
 *
 * 基于 electron-log，提供 scoped 日志能力。所有主进程模块应通过
 * createLuomiNestLogger(scope) 获取 logger，替代散落的 console.* 调用。
 *
 * 日志文件位置：PATHS.logs/main.log（由 paths.ts 的 initAppPaths 设置 app logs path）
 * Dev 模式：console（debug+）+ file（debug+）
 * Prod 模式：console（info+）+ file（info+）
 *
 * 统一 scope 映射：
 * - [Backend] / [BackendService] → scope 'Backend'
 * - [LuomiNestAvatar] → scope 'Avatar'
 * - [LuomiNestDesktopPet] → scope 'DesktopPet'
 * - [BrowserWS] / [AutomationExecutor] → scope 'Browser'
 */
import { join } from 'path'
import log from 'electron-log'
import { app } from 'electron'

import { PATHS } from './paths'

const isDev = !app.isPackaged

// 显式指定日志文件路径，确保即使 initAppPaths() 尚未调用也能写入正确位置
log.transports.file.resolvePathFn = () => join(PATHS.logs, 'main.log')
log.transports.file.level = isDev ? 'debug' : 'info'
log.transports.file.format = '[{y}-{m}-{d} {h}:{i}:{s}.{ms}] [{level}] [{scope}] {text}'

log.transports.console.level = isDev ? 'debug' : 'info'
log.transports.console.format = '[{level}][{scope}] {text}'

/** LuomiNest 日志器接口 */
export interface LuomiNestLogger {
  info: (...args: unknown[]) => void
  warn: (...args: unknown[]) => void
  error: (...args: unknown[]) => void
  debug: (...args: unknown[]) => void
}

/**
 * 创建带 scope 的 LuomiNest 主进程日志器
 *
 * @param scope - 日志前缀，如 'Backend'、'Avatar'、'DesktopPet'、'Browser'
 * @returns LuomiNestLogger 实例
 *
 * @example
 * const logger = createLuomiNestLogger('Backend')
 * logger.info('后端服务启动')  // 输出: [info][Backend] 后端服务启动
 */
export const createLuomiNestLogger = (scope: string): LuomiNestLogger => {
  const scoped = log.scope(scope)
  return {
    info: (...args: unknown[]) => scoped.info(...args),
    warn: (...args: unknown[]) => scoped.warn(...args),
    error: (...args: unknown[]) => scoped.error(...args),
    debug: (...args: unknown[]) => scoped.debug(...args),
  }
}
