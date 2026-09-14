import { BrowserWindow, app, shell } from 'electron'
import { configStore } from '../config-store'
import { getBackendUrl, subscribeBackendStage } from '../backend'
import { getLumiAuthToken } from '../backend/auth-token'
import { createLuomiNestLogger } from '../luomi-logger'
import { IpcChannels } from '@shared/ipc-types'
import type {
  CloudAccountInfo,
  CloudAuthStatus,
  CloudBackendStatus,
  CloudModelInfo,
  CloudRoutingMode,
} from '@shared/ipc-types'
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
/** 登录态下账户摘要定时刷新间隔（余额/额度变化同步到 UI） */
const ACCOUNT_REFRESH_INTERVAL_MS = 60_000

/**
 * 云端 API 路径常量表：
 * - 主站路径拼在 issuer（通行证签发方）之后，如 OIDC 标准 /userinfo；
 * - 从站路径拼在 baseUrl（云端网关）之后，如 /api/v1/llm/*；
 * - 本地后端路径拼在 127.0.0.1:18000 之后。
 */
const CLOUD_PATHS = {
  /** 主站 OIDC 标准用户信息端点（coin_balance / tier / nickname / avatar 的权威来源） */
  userinfo: '/userinfo',
  /** 从站：用户资料 */
  profile: '/api/v1/user/profile',
  /** 从站：权益信息 */
  benefits: '/api/v1/benefits',
  /** 从站：LLM 剩余额度 */
  llmQuota: '/api/v1/llm/quota',
  /** 从站：LLM 可用模型目录 */
  llmModels: '/api/v1/llm/models',
  /** 本地后端：令牌注入 */
  backendToken: '/api/v1/cloud/token',
  /** 本地后端：注入状态查询 */
  backendStatus: '/api/v1/cloud/status',
} as const

let status: CloudAuthStatus = { state: 'loggedOut' }
let refreshTimer: NodeJS.Timeout | null = null
/** 账户摘要定时刷新器（登录态下周期性同步余额/额度） */
let accountTimer: NodeJS.Timeout | null = null
/** refreshAccount 防并发重入标记（续期/定时器可能同时触发） */
let accountRefreshInFlight = false
/** 会话代际：login/logout 递增，用于丢弃过期的异步结果（旧轮询/旧续期） */
let sessionGeneration = 0
/** 当前 pendingAuth 的授权页地址（「打开授权页」用） */
let verificationUrl: string | null = null
/** 通行证账户唯一标识（id_token.sub 的内存副本，随登录态建立/清除，不外发 renderer） */
let passportSub: string | null = null

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

const stopAccountTimer = (): void => {
  if (accountTimer) {
    clearInterval(accountTimer)
    accountTimer = null
  }
}

/** 登录态下启动账户摘要定时刷新（代际失效时自停） */
const startAccountTimer = (generation: number): void => {
  stopAccountTimer()
  accountTimer = setInterval(() => {
    if (generation !== sessionGeneration || status.state !== 'authorized') {
      stopAccountTimer()
      return
    }
    void refreshAccount(generation)
  }, ACCOUNT_REFRESH_INTERVAL_MS)
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

/**
 * 从 id_token 解出 sub（JWT 第二段 base64url decode JSON，仅存档用，无需验签）。
 * 供后续云同步/对账定位账户；解不出（无 id_token / 格式异常）返回 undefined。
 */
const extractPassportSub = (idToken: unknown): string | undefined => {
  if (typeof idToken !== 'string' || !idToken) return undefined
  const parts = idToken.split('.')
  if (parts.length < 2 || !parts[1]) return undefined
  try {
    const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf-8')) as { sub?: unknown }
    return typeof payload.sub === 'string' && payload.sub ? payload.sub : undefined
  } catch {
    return undefined
  }
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
      // 新票带 id_token 则更新 sub 存档，否则沿用旧值
      passportSub: extractPassportSub(next.idToken) ?? current.passportSub,
    }
    if (merged.passportSub) passportSub = merged.passportSub
    persistTokens(merged)
    scheduleRefresh(merged, generation)
    await injectToBackend()
    // 续期成功后刷新账户摘要，余额/额度即时同步到 UI
    await refreshAccount(generation)
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
  stopAccountTimer()
  sessionGeneration += 1
  verificationUrl = null
  passportSub = null
  clearCloudTokens()
  setStatus({ state: 'loggedOut' })
}

/* ── 云端账户摘要组装 ── */

/** GET JSON（完整 URL）；非 2xx / 网络 / 解析失败一律返回 null */
const getJson = async (url: string, accessToken: string): Promise<Record<string, unknown> | null> => {
  try {
    const response = await fetch(url, {
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

/** GET 从站接口（拼 baseUrl + 常量表路径） */
const getCloudJson = (path: string, accessToken: string): Promise<Record<string, unknown> | null> => {
  const { baseUrl } = configStore.getCloudConfig()
  return getJson(`${baseUrl}${path}`, accessToken)
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

const pickNumber = (source: Record<string, unknown>, keys: string[]): number | null => {
  for (const key of keys) {
    const value = source[key]
    if (typeof value === 'number' && Number.isFinite(value)) return value
  }
  return null
}

const fetchAccount = async (accessToken: string): Promise<CloudAccountInfo> => {
  const { issuer } = configStore.getCloudConfig()
  // 主站 /userinfo（OIDC 标准）与从站三端点并行拉取；
  // 真实芙贝余额/昵称/头像/档位以主站 userinfo 为权威，从站仅作降级兜底
  const [userinfo, me, benefits, quota] = await Promise.all([
    getJson(`${issuer}${CLOUD_PATHS.userinfo}`, accessToken),
    getCloudJson(CLOUD_PATHS.profile, accessToken),
    getCloudJson(CLOUD_PATHS.benefits, accessToken),
    getCloudJson(CLOUD_PATHS.llmQuota, accessToken),
  ])
  const userinfoData = unwrap(userinfo)
  const meData = unwrap(me)
  const benefitsData = unwrap(benefits)
  // 从站 /llm/quota 返回 { quota: QuotaVo }，真正字段在下一层
  const quotaRaw = unwrap(quota)
  const quotaData =
    quotaRaw.quota && typeof quotaRaw.quota === 'object' && !Array.isArray(quotaRaw.quota)
      ? (quotaRaw.quota as Record<string, unknown>)
      : quotaRaw
  const freeQuota = pickNumber(quotaData, ['freeRemaining', 'free_remaining']) ?? 0
  const bonusQuota = pickNumber(quotaData, ['bonusRemaining', 'bonus_remaining']) ?? 0
  return {
    // 主站 userinfo 优先，未拿到时回退从站资料；两者皆失败以占位符展示
    nickname:
      pickString(userinfoData, ['nickname', 'name']) ||
      pickString(meData, ['nickname', 'displayName', 'display_name', 'username']) ||
      '—',
    tier: pickString(userinfoData, ['tier']) || pickString(benefitsData, ['tier', 'currentTier', 'current_tier']) || '—',
    // 芙贝币余额只认主站 userinfo 的 coin_balance；拉取失败为 null（UI 显示"无法获取"，不用假 0）
    coinBalance: pickNumber(userinfoData, ['coin_balance', 'coinBalance']),
    quotaRemaining: freeQuota + bonusQuota,
    avatar: pickString(userinfoData, ['avatar', 'picture']) || undefined,
    // 账户详情（全部来自主站 /userinfo，缺失即不展示对应行）
    title: pickString(userinfoData, ['title']) || undefined,
    honorLevel: pickNumber(userinfoData, ['honor_level', 'honorLevel']),
    email: pickString(userinfoData, ['email']) || undefined,
    tierExpiresAt: pickString(userinfoData, ['tier_expires_at', 'tierExpiresAt']) || undefined,
    registeredAt: pickString(userinfoData, ['registered_at', 'registeredAt']) || undefined,
  }
}

/**
 * 拉取账户摘要并广播；部分接口失败以占位值兜底，不影响登录态。
 * 防并发重入：续期后/定时器可能同时触发，同一时刻只允许一个在途请求。
 */
const refreshAccount = async (generation: number): Promise<void> => {
  if (accountRefreshInFlight) return
  const tokens = loadCloudTokens()
  if (!tokens?.accessToken) return
  accountRefreshInFlight = true
  try {
    const account = await fetchAccount(tokens.accessToken)
    if (generation !== sessionGeneration || status.state !== 'authorized') return
    // 余额拉取失败时保留上一次成功值，避免定时刷新把已有余额闪成"无法获取"
    if (account.coinBalance === null && typeof status.account?.coinBalance === 'number') {
      account.coinBalance = status.account.coinBalance
    }
    setStatus({ state: 'authorized', account })
  } finally {
    accountRefreshInFlight = false
  }
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
    const response = await fetch(`${getBackendUrl()}${CLOUD_PATHS.backendToken}`, {
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
      // id_token.sub 存档（cloud-tokens.json passportSub 字段），登出时随文件清除
      passportSub: extractPassportSub(tokens.idToken),
    }
    passportSub = persisted.passportSub ?? null
    persistTokens(persisted)
    verificationUrl = null
    setStatus({ state: 'authorized', account: null })
    scheduleRefresh(persisted, generation)
    startAccountTimer(generation)
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

/**
 * 拉取云端可用模型目录（GET {baseUrl}/api/v1/llm/models）。
 * 未登录 / 失败一律返回空数组，由设置页静默降级为不展示。
 */
const fetchModels = async (): Promise<CloudModelInfo[]> => {
  const tokens = loadCloudTokens()
  if (!tokens?.accessToken) return []
  const { baseUrl } = configStore.getCloudConfig()
  try {
    const response = await fetch(`${baseUrl}${CLOUD_PATHS.llmModels}`, {
      headers: { authorization: `Bearer ${tokens.accessToken}` },
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    })
    if (!response.ok) return []
    const data = (await response.json().catch(() => null)) as { models?: unknown } | null
    const models = Array.isArray(data?.models) ? data.models : []
    return models
      .map((item: unknown): CloudModelInfo | null => {
        if (!item || typeof item !== 'object') return null
        const record = item as Record<string, unknown>
        const modelId = typeof record.modelId === 'string' ? record.modelId : ''
        if (!modelId) return null
        const displayName =
          typeof record.displayName === 'string' && record.displayName.trim() ? record.displayName.trim() : modelId
        return { modelId, displayName }
      })
      .filter((item): item is CloudModelInfo => item !== null)
  } catch (err) {
    logger.warn('Failed to fetch cloud models:', err instanceof Error ? err.message : err)
    return []
  }
}

/**
 * 查询本地后端云令牌注入状态（GET {backend}/api/v1/cloud/status，令牌仅回传末 4 位）。
 * 后端未就绪 / 失败返回 null，调用方不阻塞页面。
 */
const getBackendCloudStatus = async (): Promise<CloudBackendStatus | null> => {
  const headers: Record<string, string> = {}
  if (app.isPackaged) {
    headers.authorization = `Bearer ${getLumiAuthToken()}`
  }
  try {
    const response = await fetch(`${getBackendUrl()}${CLOUD_PATHS.backendStatus}`, {
      headers,
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    })
    if (!response.ok) return null
    const payload = (await response.json().catch(() => null)) as { data?: unknown } | null
    const data = payload?.data
    if (!data || typeof data !== 'object' || typeof (data as CloudBackendStatus).configured !== 'boolean') {
      return null
    }
    return data as CloudBackendStatus
  } catch {
    return null
  }
}

/** 启动时恢复上次登录态：令牌未过期直接进入 authorized，仅剩 refresh_token 则尝试续期 */
const restoreSession = (): void => {
  const tokens = loadCloudTokens()
  if (!tokens?.accessToken) return
  passportSub = tokens.passportSub ?? null
  const generation = sessionGeneration
  if (tokens.accessExpiresAt > Date.now()) {
    setStatus({ state: 'authorized', account: null })
    scheduleRefresh(tokens, generation)
    startAccountTimer(generation)
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
  fetchModels,
  getBackendCloudStatus,
}
