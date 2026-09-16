import { spawn, ChildProcess } from 'child_process'
import { app } from 'electron'
import { join } from 'path'
import { existsSync } from 'fs'
import { platform } from 'os'
import { PATHS } from '../paths'
import { createLuomiNestLogger } from '../luomi-logger'
import { withHubSource } from '../log-hub'
import type { LogLevel } from '@shared/ipc-types'
import { getLumiAuthToken } from './auth-token'

const logger = createLuomiNestLogger('Backend')

let backendProcess: ChildProcess | null = null
let backendReady = false

type BackendStage = 'spawning' | 'waiting' | 'ready' | 'failed'
let backendStage: BackendStage = 'spawning'
const stageListeners = new Set<(stage: BackendStage, detail?: string) => void>()

const emitStage = (stage: BackendStage, detail?: string): void => {
  backendStage = stage
  for (const listener of stageListeners) {
    try {
      listener(stage, detail)
    } catch {
      // ignore listener error
    }
  }
}

export const subscribeBackendStage = (listener: (stage: BackendStage, detail?: string) => void): (() => void) => {
  stageListeners.add(listener)
  try {
    listener(backendStage)
  } catch {
    // ignore
  }
  return () => {
    stageListeners.delete(listener)
  }
}

const BACKEND_PORT = 18000
const BACKEND_HOST = '127.0.0.1'
const MAX_STARTUP_WAIT = 30000
const CHECK_INTERVAL = 500

const LOG_LEVEL_PATTERN = /\|\s*(DEBUG|INFO|SUCCESS|WARNING|ERROR|CRITICAL)\s*\|/

const routeBackendLog = (data: Buffer, source: 'stdout' | 'stderr') => {
  const text = data.toString('utf8').trim()
  if (!text) return

  // 统一日志：转发 electron-log 的同时以 source='backend' 收录进 log-hub。
  // 用 withHubSource 打标，避免该条日志被 electron-log hook 以 'main' 来源重复收录。
  const logTo = (level: LogLevel, fn: (msg: string) => void) => {
    withHubSource('backend', () => fn(text))
  }

  if (source === 'stdout') {
    logTo('info', logger.info)
    return
  }

  const match = text.match(LOG_LEVEL_PATTERN)
  if (!match) {
    logTo('info', logger.info)
    return
  }

  const level = match[1]
  switch (level) {
    case 'DEBUG':
    case 'INFO':
    case 'SUCCESS':
      logTo('info', logger.info)
      break
    case 'WARNING':
      logTo('warn', logger.warn)
      break
    case 'ERROR':
    case 'CRITICAL':
      logTo('error', logger.error)
      break
    default:
      logTo('info', logger.info)
  }
}

const getBackendExecutableName = (): string => {
  const os = platform()
  if (os === 'win32') return 'luominest-backend.exe'
  return 'luominest-backend'
}

const getBackendExecutablePath = (): string => {
  const isDev = !app.isPackaged
  const os = platform()

  if (isDev) {
    const projectRoot = join(__dirname, '../../..')
    if (os === 'win32') {
      return join(projectRoot, 'backend', '.venv', 'Scripts', 'python.exe')
    }
    return join(projectRoot, 'backend', '.venv', 'bin', 'python')
  }

  const resourcesPath = process.resourcesPath
  return join(resourcesPath, 'backend', getBackendExecutableName())
}

const getBackendMainPath = (): string => {
  const isDev = !app.isPackaged

  if (isDev) {
    const projectRoot = join(__dirname, '../../..')
    return join(projectRoot, 'backend', 'main.py')
  }

  return ''
}

const getBackendCwd = (): string => {
  const isDev = !app.isPackaged

  if (isDev) {
    const projectRoot = join(__dirname, '../../..')
    return join(projectRoot, 'backend')
  }
  
  const resourcesPath = process.resourcesPath
  return join(resourcesPath, 'backend')
}

export const isBackendReady = (): boolean => backendReady

export const getBackendUrl = (): string => `http://${BACKEND_HOST}:${BACKEND_PORT}`

export const waitForBackend = async (): Promise<boolean> => {
  const startTime = Date.now()

  while (Date.now() - startTime < MAX_STARTUP_WAIT) {
    try {
      const response = await fetch(`http://${BACKEND_HOST}:${BACKEND_PORT}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(CHECK_INTERVAL)
      })
      if (response.ok) {
        backendReady = true
        logger.info('Backend is ready!')
        return true
      }
      // 非 OK 状态同样需要等待，避免高频请求（busy-wait）
      await new Promise(resolve => setTimeout(resolve, CHECK_INTERVAL))
    } catch {
      await new Promise(resolve => setTimeout(resolve, CHECK_INTERVAL))
    }
  }

  logger.error('Backend startup timeout')
  return false
}

export const startBackend = async (): Promise<boolean> => {
  if (backendProcess) {
    logger.info('Backend already running')
    return true
  }
  
  const isDev = !app.isPackaged
  const backendPath = getBackendExecutablePath()
  const mainPath = getBackendMainPath()
  const cwd = getBackendCwd()
  
  if (!existsSync(backendPath)) {
    logger.error('Backend executable not found:', backendPath)
    return false
  }

  logger.info('Starting backend...')
  logger.info('Platform:', platform())
  logger.info('Executable:', backendPath)
  logger.info('Working directory:', cwd)
  
  const args = isDev 
    ? [mainPath, '--host', BACKEND_HOST, '--port', String(BACKEND_PORT)]
    : ['--host', BACKEND_HOST, '--port', String(BACKEND_PORT)]
  
  // 认证策略：
  // - 开发模式：LUOMINEST_NO_AUTH=1，便于快速迭代，无需令牌即可调用本地后端
  // - 打包模式：注入 LUOMINEST_AUTH_TOKEN（与渲染进程 window.api.auth.getToken 同源），
  //   后端启用令牌校验，防止本机其他进程未授权调用 127.0.0.1:18000（为后续 JWT/无头模式做准备）
  const env: Record<string, string | undefined> = {
    ...process.env,
    PYTHONUNBUFFERED: '1',
    PYTHONIOENCODING: 'utf-8',
    LUOMINEST_DATA_DIR: PATHS.backendData,
    // 统一日志：后端 loguru 据此把日志落盘到 userData/Logs/backend.log（打包与 dev 均传）
    LUOMINEST_LOG_DIR: PATHS.logs,
  }

  if (isDev) {
    env.LUOMINEST_NO_AUTH = '1'
  } else {
    env.LUOMINEST_AUTH_TOKEN = getLumiAuthToken()
  }

  if (platform() === 'linux' || platform() === 'darwin') {
    if (!isDev) {
      env.LD_LIBRARY_PATH = [
        join(cwd, 'lib'),
        process.env.LD_LIBRARY_PATH || ''
      ].filter(Boolean).join(':')
    }
  }
  
  backendProcess = spawn(backendPath, args, {
    cwd,
    env,
    stdio: ['ignore', 'pipe', 'pipe']
  })
  emitStage('waiting', 'Backend process spawned, waiting for health check')

  backendProcess.stdout?.on('data', (data) => {
    routeBackendLog(data, 'stdout')
  })

  backendProcess.stderr?.on('data', (data) => {
    routeBackendLog(data, 'stderr')
  })
  
  backendProcess.on('error', (err) => {
    logger.error('Process error:', err)
    backendProcess = null
    backendReady = false
  })

  backendProcess.on('exit', (code, signal) => {
    logger.info(`Process exited with code ${code}, signal ${signal}`)
    backendProcess = null
    backendReady = false
  })
  
  return waitForBackend()
}

export const stopBackend = (): void => {
  if (!backendProcess) {
    return
  }

  logger.info('Stopping backend...')

  if (platform() === 'win32') {
    if (backendProcess.pid === undefined) {
      backendProcess.kill('SIGKILL')
      backendProcess = null
      backendReady = false
      return
    }

    const pid = backendProcess.pid
    try {
      const tk = spawn('taskkill', ['/pid', String(pid), '/f', '/t'])
      tk.on('error', (err) => {
        logger.error('taskkill failed:', err.message)
        try { process.kill(pid) } catch {}
        backendProcess = null
        backendReady = false
      })
      tk.on('close', (exitCode) => {
        if (exitCode !== 0) {
          logger.error('taskkill exited with code:', exitCode)
          try { process.kill(pid) } catch {}
        }
        backendProcess = null
        backendReady = false
      })
    } catch (err) {
      logger.error('taskkill spawn failed:', err)
      try { process.kill(pid) } catch {}
      backendProcess = null
      backendReady = false
    }
  } else {
    backendProcess.kill('SIGTERM')
    backendProcess = null
    backendReady = false
  }
}

export const restartBackend = async (): Promise<boolean> => {
  stopBackend()
  await new Promise(resolve => setTimeout(resolve, 1000))
  return startBackend()
}

export const startBackendInBackground = (): void => {
  if (backendProcess) {
    logger.info('Backend already running')
    return
  }
  emitStage('spawning')
  void startBackend().then((ok) => {
    if (ok) {
      emitStage('ready')
    } else {
      emitStage('failed', 'Backend startup timeout or executable missing')
    }
  })
}
