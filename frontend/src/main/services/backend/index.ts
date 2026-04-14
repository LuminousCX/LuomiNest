import { spawn, ChildProcess } from 'child_process'
import { app } from 'electron'
import { join } from 'path'
import { existsSync } from 'fs'
import { platform } from 'os'

let backendProcess: ChildProcess | null = null
let backendReady = false
const BACKEND_PORT = 18000
const BACKEND_HOST = '127.0.0.1'
const MAX_STARTUP_WAIT = 30000
const CHECK_INTERVAL = 500

const getBackendExecutablePath = (): string => {
  const isDev = !app.isPackaged
  const os = platform()
  
  if (isDev) {
    const projectRoot = join(__dirname, '../../../../..')
    if (os === 'win32') {
      return join(projectRoot, 'backend', '.venv', 'Scripts', 'python.exe')
    }
    return join(projectRoot, 'backend', '.venv', 'bin', 'python')
  }
  
  const resourcesPath = process.resourcesPath
  if (os === 'win32') {
    return join(resourcesPath, 'backend', 'luominest-backend.exe')
  }
  return join(resourcesPath, 'backend', 'luominest-backend')
}

const getBackendMainPath = (): string => {
  const isDev = !app.isPackaged
  
  if (isDev) {
    const projectRoot = join(__dirname, '../../../../..')
    return join(projectRoot, 'backend', 'main.py')
  }
  
  return ''
}

const getBackendCwd = (): string => {
  const isDev = !app.isPackaged
  
  if (isDev) {
    const projectRoot = join(__dirname, '../../../../..')
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
        console.log('[BackendService] Backend is ready!')
        return true
      }
    } catch {
      await new Promise(resolve => setTimeout(resolve, CHECK_INTERVAL))
    }
  }
  
  console.error('[BackendService] Backend startup timeout')
  return false
}

export const startBackend = async (): Promise<boolean> => {
  if (backendProcess) {
    console.log('[BackendService] Backend already running')
    return true
  }
  
  const isDev = !app.isPackaged
  const backendPath = getBackendExecutablePath()
  const mainPath = getBackendMainPath()
  const cwd = getBackendCwd()
  
  if (!existsSync(backendPath)) {
    console.error('[BackendService] Backend executable not found:', backendPath)
    return false
  }
  
  console.log('[BackendService] Starting backend...')
  console.log('[BackendService] Executable:', backendPath)
  console.log('[BackendService] Working directory:', cwd)
  
  const args = isDev 
    ? [mainPath, '--host', BACKEND_HOST, '--port', String(BACKEND_PORT)]
    : ['--host', BACKEND_HOST, '--port', String(BACKEND_PORT)]
  
  backendProcess = spawn(backendPath, args, {
    cwd,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: '1',
      LUOMINEST_DATA_DIR: join(app.getPath('userData'), 'data')
    },
    stdio: ['ignore', 'pipe', 'pipe']
  })
  
  backendProcess.stdout?.on('data', (data) => {
    console.log('[Backend]', data.toString().trim())
  })
  
  backendProcess.stderr?.on('data', (data) => {
    console.error('[Backend Error]', data.toString().trim())
  })
  
  backendProcess.on('error', (err) => {
    console.error('[BackendService] Process error:', err)
    backendProcess = null
    backendReady = false
  })
  
  backendProcess.on('exit', (code, signal) => {
    console.log(`[BackendService] Process exited with code ${code}, signal ${signal}`)
    backendProcess = null
    backendReady = false
  })
  
  return waitForBackend()
}

export const stopBackend = (): void => {
  if (backendProcess) {
    console.log('[BackendService] Stopping backend...')
    
    if (platform() === 'win32') {
      spawn('taskkill', ['/pid', String(backendProcess.pid), '/f', '/t'])
    } else {
      backendProcess.kill('SIGTERM')
    }
    
    backendProcess = null
    backendReady = false
  }
}

export const restartBackend = async (): Promise<boolean> => {
  stopBackend()
  await new Promise(resolve => setTimeout(resolve, 1000))
  return startBackend()
}
