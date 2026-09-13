import { BrowserWindow, app, shell } from 'electron'
import { configStore } from '../config-store'
import { getBackendUrl, subscribeBackendStage } from '../backend'
import { getLumiAuthToken } from '../backend/auth-token'
import { createLuomiNestLogger } from '../luomi-logger'
import { IpcChannels } from '@shared/ipc-types'
import type { CloudAccountInfo, CloudAuthStatus, CloudRoutingMode } from '@shared/ipc-types'
import {
  CloudAuthError,
  pollForDeviceToken,
  refreshAccessToken,
  requestDeviceAuthorization,
} from './auth-client'
import type { DeviceAuthorization } from './auth-client'
import { clearCloudTokens, loadCloudTokens, saveCloudTokens } from './token-store'
import type { StoredCloudTokens } from './token-store'

const logger = createLuomiNestLogger('CloudAuth')

/** access token 到期前提前量（到期前 60s 静默续期） */
const REFRESH_AHEAD_MS = 60_000
/** 续期定时器最小间隔兜底 */
const MIN_REFRESH_DELAY_MS = 5_000
/** 注入与账户信息请求超时 */
const API_TIMEOUT_MS = 10_000

let status: CloudAuthStatus = { state: 'loggedOut' }
let refreshTimer: NodeJS.Timeout | null = null
/** 会话代际：login/logout 递增，用于丢弃过期的异步结果（旧轮询/旧续期） */
let sessionGeneration = 0
/** 当前 pendingAuth 的授权页地址（「打开授权页」用） */
let verificationUrl: string | null = null

const setStatus = (next: CloudAuthStatus): void => {
  status = next
  broadcastStatus()
}

const broadcastStatus = (): void => {
  for (const win of BrowserWindow.getAllWindows()) {
    if (!win.isDestroyed()) {
      win.webContents.send(IpcChannels.cloud.push.status, status)
    }
  }
}

const stopRefreshTimer = (): void => {
  if (refreshTimer) {
    clearTimeout(refreshTimer)
    refreshTimer = null
  }
}

const describeError = (err: unknown): string => {
  if (err instanceof CloudAuthError) return err.code
  if (err instanceof Error && (err.name === 'AbortError' || err.name === 'TimeoutError')) return 'network'
  if (err instanceof TypeError) return 'network'
  return 'unknown'
}

/* ── 令牌持久化 ── */

const persistTokens = (tokens: StoredCloudTokens): void => {
  saveCloudTokens(tokens)
}

/* ── 定时续期 ── */

const scheduleRefresh = (tokens: StoredCloudTokens, generation: number): void => {
  stopRefreshTimer()
  const delay = Math.max(tokens.accessExpiresAt - REFRESH_AHEAD_MS - Date.now(), MIN_REFRESH_DELAY_MS)
  refreshTimer = setTimeout(() => {
    void renewTokens(generation)
  }, delay)
}

/** 用 refresh_token 续期；失效（撤销/过期）则回退到未登录并清存储 */
const renewTokens = async (generation: number): Promise<void> => {
  const { issuer } = configStore.getCloudConfig()
  const current = loadCloudTokens()
  if (!current?.refreshToken) return
  try {
    const next = await refreshAccessToken(issuer, current.refreshToken)
    if (generation !== sessionGeneration) return
    const merged: StoredCloudTokens = {
      accessToken: next.accessToken,
      refreshToken: next.refreshToken ?? current.refreshToken,
      accessExpiresAt: Date.now() + next.expiresIn * 1000,
    }
    persistTokens(merged)
    scheduleRefresh(merged, generation)
    await injectToBackend()
  } catch (err) {
    if (generation !== sessionGeneration) return
    logger.warn('Cloud token refresh failed, signing out:', err instanceof Error ? err.message : err)
    signOutLocally()
    await injectToBackend()
  }
}

/** 清空本地登录态（不清 config，不动 in-flight IPC） */
const signOutLocally = (): void => {
  stopRefreshTimer()
  sessionGeneration += 1
  verificationUrl = null
  clearCloudTokens()
  setStatus({ state: 'loggedOut' })
}

/* ── 云端账户摘要组装 ── */

const getJson = async (path: string, accessToken: string): Promise<Record<string, unknown> | null> => {
  const { baseUrl } = configStore.getCloudConfig()
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      headers: { authorization: `Bearer ${accessToken}` },
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    })
    if (!response.ok) return null
    const data: unknown = await response.json()
    return data && typeof data === 'object' && !Array.isArray(data) ? (data as Record<string, unknown>) : null
  } catch {
    return null
  }
}

/** 兼容裸对象与 { data: {...} } 包裹两种响应形态 */
const unwrap = (payload: Record<string, unknown> | null): Record<string, unknown> => {
  if (!payload) return {}
  const data = payload.data
  return data && typeof data === 'object' && !Array.isArray(data) ? (data as Record<string, unknown>) : payload
}

const pickString = (source: Record<string, unknown>, keys: string[]): string => {
  for (const key of keys) {
    const value = source[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
    if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  }
  return ''
}

const pickNumber = (source: Record<string, unknown>, keys: string[]): number => {
  for (const key of keys) {
    const value = source[key]
    if (typeof value === 'number' && Number.isFinite(value)) return value
  }
  return 0
}

const fetchAccount = async (accessToken: string): Promise<CloudAccountInfo> => {
  const [me, benefits, quota] = await Promise.all([
    getJson('/api/v1/user/profile', accessToken),
    getJson('/api/v1/benefits', accessToken),
    getJson('/api/v1/llm/quota', accessToken),
  ])
  const meData = unwrap(me)
  const benefitsData = unwrap(benefits)
  // 从站 /llm/quota 返回 { quota: QuotaVo }，真正字段在下一层
  const quotaRaw = unwrap(quota)
  const quotaData =
    quotaRaw.quota && typeof quotaRaw.quota === 'object' && !Array.isArray(quotaRaw.quota)
      ? (quotaRaw.quota as Record<string, unknown>)
      : quotaRaw
  return {
    nickname: pickString(meData, ['nickname', 'displayName', 'display_name', 'username']) || '—',
    tier: pickString(benefitsData, ['tier', 'currentTier', 'current_tier']) || '—',
    coinBalance: pickNumber(benefitsData, ['coinBalance', 'coin_balance', 'balance']),
    quotaRemaining:
      pickNumber(quotaData, ['freeRemaining', 'free_remaining']) +
      pickNumber(quotaData, ['bonusRemaining', 'bonus_remaining']),
  }
}

/** 拉取账户摘要并广播；部分接口失败以占位值兜底，不影响登录态 */
const refreshAccount = async (generation: number): Promise<void> => {
  const tokens = loadCloudTokens()
  if (!tokens?.accessToken) return
  const account = await fetchAccount(tokens.accessToken)
  if (generation !== sessionGeneration || status.state !== 'authorized') return
  setStatus({ state: 'authorized', account })
}

/* ── 令牌注入本地后端 ── */

/**
 * 把最新云端令牌与路由配置注入本地后端（127.0.0.1:18000）。
 * 打包模式本地后端开启令牌校验，附带本地 Bearer；dev 模式 NO_AUTH 无需。
 * 失败仅告警（后端未就绪时会由 ready push 触发重注入）。
 */
const injectToBackend = async (): Promise<void> => {
  const cloud = configStore.getCloudConfig()
  const tokens = loadCloudTokens()
  const headers: Record<string, string> = { 'content-type': 'application/json' }
  if (app.isPackaged) {
    headers.authorization = `Bearer ${getLumiAuthToken()}`
  }
  try {
    const response = await fetch(`${getBackendUrl()}/api/v1/cloud/token`, {
      method: 'PUT',
      headers,
      body: JSON.stringify({
        accessToken: tokens?.accessToken ?? '',
        cloudBaseUrl: cloud.baseUrl,
        routingMode: cloud.routingMode,
      }),
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    })
    if (!response.ok) {
      logger.warn(`Cloud token inject failed with HTTP ${response.status}`)
    } else {
      logger.info(`Cloud token injected (routingMode=${cloud.routingMode})`)
    }
  } catch (err) {
    logger.warn('Cloud token inject failed:', err instanceof Error ? err.message : err)
  }
}

/* ── 登录流程 ── */

/** 后台完成轮询并落盘令牌 */
const completeLogin = async (generation: number, deviceAuth: DeviceAuthorization): Promise<void> => {
  const { issuer } = configStore.getCloudConfig()
  try {
    const tokens = await pollForDeviceToken(issuer, deviceAuth.deviceCode, {
      interval: deviceAuth.interval,
      expiresIn: deviceAuth.expiresIn,
      isCancelled: () => generation !== sessionGeneration,
    })
    if (generation !== sessionGeneration) return
    const persisted: StoredCloudTokens = {
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      accessExpiresAt: Date.now() + tokens.expiresIn * 1000,
    }
    persistTokens(persisted)
    verificationUrl = null
    setStatus({ state: 'authorized', account: null })
    scheduleRefresh(persisted, generation)
    await injectToBackend()
    await refreshAccount(generation)
  } catch (err) {
    if (generation !== sessionGeneration) return
    if (err instanceof CloudAuthError && err.code === 'cancelled') return
    logger.warn('Device flow login failed:', err instanceof Error ? err.message : err)
    stopRefreshTimer()
    clearCloudTokens()
    setStatus({ state: 'error', error: describeError(err) })
  }
}

const login = async (): Promise<CloudAuthStatus> => {
  if (status.state === 'pendingAuth') return status
  const { issuer } = configStore.getCloudConfig()

  stopRefreshTimer()
  sessionGeneration += 1
  const generation = sessionGeneration
  setStatus({ state: 'pendingAuth' })

  try {
    const deviceAuth = await requestDeviceAuthorization(issuer)
    if (generation !== sessionGeneration) return status
    verificationUrl = deviceAuth.verificationUriComplete
    setStatus({ state: 'pendingAuth', userCode: deviceAuth.userCode })
    // 优先自动打开系统浏览器授权页；失败时用户可在设置页手动打开
    void shell.openExternal(deviceAuth.verificationUriComplete).catch((err: unknown) => {
      logger.warn('Failed to open verification page:', err instanceof Error ? err.message : err)
    })
    void completeLogin(generation, deviceAuth)
  } catch (err) {
    logger.warn('Device authorization request failed:', err instanceof Error ? err.message : err)
    setStatus({ state: 'error', error: describeError(err) })
  }
  return status
}

const logout = async (): Promise<CloudAuthStatus> => {
  signOutLocally()
  await injectToBackend()
  return status
}

/* ── 对外接口 ── */

const getStatus = (): CloudAuthStatus => status

const openVerificationPage = async (): Promise<boolean> => {
  if (!verificationUrl) return false
  try {
    await shell.openExternal(verificationUrl)
    return true
  } catch (err) {
    logger.warn('Failed to open verification page:', err instanceof Error ? err.message : err)
    return false
  }
}

const getRoutingMode = (): CloudRoutingMode => configStore.getCloudConfig().routingMode

const setRoutingMode = (mode: CloudRoutingMode): void => {
  configStore.setCloudRoutingMode(mode)
  // 模式变化即时同步到本地后端
  void injectToBackend()
}

/** 启动时恢复上次登录态：令牌未过期直接进入 authorized，仅剩 refresh_token 则尝试续期 */
const restoreSession = (): void => {
  const tokens = loadCloudTokens()
  if (!tokens?.accessToken) return
  const generation = sessionGeneration
  if (tokens.accessExpiresAt > Date.now()) {
    setStatus({ state: 'authorized', account: null })
    scheduleRefresh(tokens, generation)
    void refreshAccount(generation)
    return
  }
  if (tokens.refreshToken) {
    void renewTokens(generation)
    return
  }
  clearCloudTokens()
}

export const initCloudAuth = (): void => {
  // 后端就绪（含重启后的 ready push）时重注入，Python 重启无感
  subscribeBackendStage((stage) => {
    if (stage === 'ready') void injectToBackend()
  })
  restoreSession()
}

export const cloudAuth = {
  login,
  logout,
  getStatus,
  openVerificationPage,
  getRoutingMode,
  setRoutingMode,
}
