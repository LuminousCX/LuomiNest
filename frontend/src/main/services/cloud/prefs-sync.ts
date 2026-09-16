/**
 * 显示偏好云同步（客户端侧，v1）
 *
 * 隐私原则（最小必要）：本服务只同步「显示偏好」——界面语言（locale）、主题模式（theme）、
 * 首启协议同意记录（onboarding 的协议/隐私版本与同意时间）。
 * 明确绝不同步：聊天记录、记忆、皮套资产、平台凭证、任何密钥/令牌。
 *
 * 服务端契约（端点未上线时客户端必须优雅降级）：
 * - GET  {baseUrl}/api/v1/user/preferences（Bearer 令牌）
 *        响应兼容裸对象与 { data: {...} } 包裹两种形态，数据语义：{ prefs: object, updatedAt: string(ISO) }
 * - PUT  {baseUrl}/api/v1/user/preferences，body { prefs: object, updatedAt: string }
 *        服务端按 updatedAt 最后写胜出。
 *
 * 触发时机：
 * 1. 云登录成功后拉取一次（比本地新则应用 locale/theme，下次启动生效）；
 * 2. 本地对应项变更时节流上传（变更后 3s 防抖）；
 * 3. 登录态下每 6 小时定时对齐一次。
 *
 * 失败策略：所有失败静默不阻塞 UI；端点 404/501 视为服务端未上线，debug 日志后本次会话禁用。
 */
import { BrowserWindow } from 'electron'
import { configStore } from '../config-store'
import { loadCloudTokens } from './token-store'
import { createLuomiNestLogger } from '../luomi-logger'
import { IpcChannels } from '@shared/ipc-types'
import type { RemotePrefsAppliedEvent } from '@shared/ipc-types'

const logger = createLuomiNestLogger('CloudPrefsSync')

/** 云端用户偏好端点（拼在 baseUrl 之后） */
const PREFS_PATH = '/api/v1/user/preferences'
const REQUEST_TIMEOUT_MS = 10_000
/** 本地偏好变更后的上传防抖 */
const UPLOAD_DEBOUNCE_MS = 3_000
/** 登录态下的定时对齐间隔（6 小时） */
const ALIGN_INTERVAL_MS = 6 * 60 * 60 * 1000
/**
 * 远程应用抑制窗口（防回环上传）：
 * 应用远端 locale/theme 后，渲染层会经 setLocale/setTheme IPC 把同一值回写本地，
 * 该回写会触发 ipc-handlers 里的 notifyLocalPrefChange → 防抖上传，形成
 * 「远端 → 本地 → 上传 → 远端 updatedAt 变新」的无谓回环。
 * 窗口期内忽略本地变更通知（窗口取 10s，覆盖渲染层收到推送后异步回写的延迟）；
 * 用户在窗口期内的真实手动改动会顺延到下次变更或 6h 定时对齐时上传。
 */
const REMOTE_APPLY_GUARD_MS = 10_000

/** 合法显示偏好值域（与渲染层 stores/locale.ts、stores/theme.ts 的取值收敛一致） */
const VALID_LOCALES = new Set(['zh-CN', 'en-US', 'ja-JP'])
const VALID_THEMES = new Set(['light', 'dark', 'system'])

/** v1 同步内容：仅显示偏好 + 协议同意记录（版本与时间） */
interface SyncedPrefs {
  locale?: string
  theme?: string
  onboarding?: {
    agreementVersion?: string
    privacyVersion?: string
    agreedAt?: string
  }
}

/** 服务端偏好载荷语义 */
interface RemotePrefs {
  prefs: SyncedPrefs
  updatedAt: string
}

let uploadTimer: NodeJS.Timeout | null = null
let alignTimer: NodeJS.Timeout | null = null
/** 会话代际：登出/重新登录递增，丢弃过期的对齐定时器与在途结果 */
let generation = 0
let syncInFlight = false
/** 最近一次与服务器达成一致的时间戳（成功上传的时间或应用的远端 updatedAt），仅会话内有效 */
let lastSyncAnchor = ''
/** 本地偏好最近一次变更时刻（epoch ms），用于拉取时判断「本地是否有未上传的新改动」 */
let localDirtyAt = 0
/** 服务端端点可用性：null=未探测，false=404/501 已判定未上线（本次会话静默禁用） */
let serverSupported: boolean | null = null
/** 远程应用抑制窗口截止时刻（epoch ms），见 REMOTE_APPLY_GUARD_MS 注释 */
let remoteApplyGuardUntil = 0

/* ── 本地偏好读写 ── */

/** 组装本地上传载荷（白名单挑字段，绝不夹带其他配置） */
const buildLocalPrefs = (): SyncedPrefs => {
  const onboarding = configStore.getOnboarding()
  return {
    locale: configStore.getLocale(),
    theme: configStore.getTheme(),
    onboarding: {
      agreementVersion: onboarding.agreementVersion || undefined,
      privacyVersion: onboarding.privacyVersion || undefined,
      agreedAt: onboarding.agreedAt || undefined,
    },
  }
}

/** 清洗远端下发数据：仅接受白名单字段且值合法，防止脏数据写入本地配置 */
const sanitizeRemotePrefs = (raw: unknown): SyncedPrefs => {
  const result: SyncedPrefs = {}
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return result
  const source = raw as Record<string, unknown>
  if (typeof source.locale === 'string' && VALID_LOCALES.has(source.locale)) result.locale = source.locale
  if (typeof source.theme === 'string' && VALID_THEMES.has(source.theme)) result.theme = source.theme
  if (source.onboarding && typeof source.onboarding === 'object' && !Array.isArray(source.onboarding)) {
    const ob = source.onboarding as Record<string, unknown>
    result.onboarding = {
      agreementVersion: typeof ob.agreementVersion === 'string' ? ob.agreementVersion : undefined,
      privacyVersion: typeof ob.privacyVersion === 'string' ? ob.privacyVersion : undefined,
      agreedAt: typeof ob.agreedAt === 'string' ? ob.agreedAt : undefined,
    }
  }
  return result
}

/** 远端偏好与本地是否一致（避免无意义回写） */
const sameAsLocal = (prefs: SyncedPrefs): boolean => {
  const local = buildLocalPrefs()
  if (prefs.locale && prefs.locale !== local.locale) return false
  if (prefs.theme && prefs.theme !== local.theme) return false
  if (prefs.onboarding) {
    const lo = local.onboarding ?? {}
    if (prefs.onboarding.agreementVersion && prefs.onboarding.agreementVersion !== lo.agreementVersion) return false
    if (prefs.onboarding.privacyVersion && prefs.onboarding.privacyVersion !== lo.privacyVersion) return false
    if (prefs.onboarding.agreedAt && prefs.onboarding.agreedAt !== lo.agreedAt) return false
  }
  return true
}

/** 把远端偏好应用的变更广播到全部窗口（渲染层 locale/theme store 监听后即时生效） */
const broadcastRemotePrefsApplied = (applied: RemotePrefsAppliedEvent): void => {
  if (!applied.locale && !applied.theme) return
  for (const win of BrowserWindow.getAllWindows()) {
    if (win.isDestroyed()) continue
    try {
      win.webContents.send(IpcChannels.app.push.remotePrefsApplied, applied)
    } catch {
      // 单窗口推送失败不影响其他窗口
    }
  }
}

/** 把远端偏好应用到本地配置，并推送渲染层实时生效（不再等下次启动） */
const applyRemotePrefs = (prefs: SyncedPrefs): void => {
  const applied: RemotePrefsAppliedEvent = {}
  if (prefs.locale && prefs.locale !== configStore.getLocale()) {
    configStore.setLocale(prefs.locale)
    applied.locale = prefs.locale
    logger.info(`Applied remote locale: ${prefs.locale}`)
  }
  if (prefs.theme && prefs.theme !== configStore.getTheme()) {
    configStore.setTheme(prefs.theme as 'light' | 'dark' | 'system')
    applied.theme = prefs.theme
    logger.info(`Applied remote theme: ${prefs.theme}`)
  }
  if (prefs.onboarding) {
    const local = configStore.getOnboarding()
    const updates: Record<string, string> = {}
    if (prefs.onboarding.agreementVersion && prefs.onboarding.agreementVersion !== local.agreementVersion) {
      updates.agreementVersion = prefs.onboarding.agreementVersion
    }
    if (prefs.onboarding.privacyVersion && prefs.onboarding.privacyVersion !== local.privacyVersion) {
      updates.privacyVersion = prefs.onboarding.privacyVersion
    }
    if (prefs.onboarding.agreedAt && prefs.onboarding.agreedAt !== local.agreedAt) {
      updates.agreedAt = prefs.onboarding.agreedAt
    }
    if (Object.keys(updates).length > 0) {
      configStore.setOnboarding(updates)
      logger.info('Applied remote onboarding consent record')
    }
  }
  if (applied.locale || applied.theme) {
    // 开启防回环抑制窗口：渲染层应用推送后的同值回写不触发上传
    remoteApplyGuardUntil = Date.now() + REMOTE_APPLY_GUARD_MS
    broadcastRemotePrefsApplied(applied)
  }
}

/* ── 服务端请求（照抄 cloud/index.ts 的请求/降级模式） ── */

/** 兼容裸对象与 { data: {...} } 包裹两种响应形态 */
const unwrap = (payload: Record<string, unknown> | null): Record<string, unknown> => {
  if (!payload) return {}
  const data = payload.data
  return data && typeof data === 'object' && !Array.isArray(data) ? (data as Record<string, unknown>) : payload
}

/**
 * GET 远端偏好。任何失败返回 null：
 * - 404/501：服务端端点未上线，debug 日志后置 serverSupported=false（本次会话静默禁用）；
 * - 其他非 2xx / 网络 / 解析失败：debug 日志，保留 serverSupported 以便下次触发重试。
 */
const fetchRemotePrefs = async (accessToken: string): Promise<RemotePrefs | null> => {
  const { baseUrl } = configStore.getCloudConfig()
  try {
    const response = await fetch(`${baseUrl}${PREFS_PATH}`, {
      headers: { authorization: `Bearer ${accessToken}` },
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    })
    if (response.status === 404 || response.status === 501) {
      logger.debug(`Preferences endpoint not implemented (HTTP ${response.status}); cloud pref sync disabled`)
      serverSupported = false
      return null
    }
    if (!response.ok) {
      logger.debug(`Preferences fetch failed with HTTP ${response.status}`)
      return null
    }
    const data = (await response.json().catch(() => null)) as Record<string, unknown> | null
    if (!data || typeof data !== 'object' || Array.isArray(data)) return null
    const body = unwrap(data)
    const prefs = sanitizeRemotePrefs(body.prefs)
    if (Object.keys(prefs).length === 0) return null
    return {
      prefs,
      updatedAt: typeof body.updatedAt === 'string' ? body.updatedAt : '',
    }
  } catch (err) {
    logger.debug('Preferences fetch failed:', err instanceof Error ? err.message : err)
    return null
  }
}

/** PUT 本地偏好（body { prefs, updatedAt }，服务端按 updatedAt 最后写胜出）；成功返回服务端已采纳的时间戳 */
const pushLocalPrefs = async (accessToken: string): Promise<boolean> => {
  const { baseUrl } = configStore.getCloudConfig()
  const updatedAt = new Date().toISOString()
  try {
    const response = await fetch(`${baseUrl}${PREFS_PATH}`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json', authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({ prefs: buildLocalPrefs(), updatedAt }),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    })
    if (response.status === 404 || response.status === 501) {
      logger.debug(`Preferences endpoint not implemented (HTTP ${response.status}); cloud pref sync disabled`)
      serverSupported = false
      return false
    }
    if (!response.ok) {
      logger.debug(`Preferences upload failed with HTTP ${response.status}`)
      return false
    }
    lastSyncAnchor = updatedAt
    localDirtyAt = 0
    return true
  } catch (err) {
    logger.debug('Preferences upload failed:', err instanceof Error ? err.message : err)
    return false
  }
}

/* ── 同步主流程 ── */

/**
 * 对齐一次：拉取远端并按「最后写胜出」决定应用方向。
 * - 本地有未上传的改动（localDirtyAt 晚于上次对齐）→ 以上传本地为准（用户刚在本机改过）；
 * - 否则远端 updatedAt 比上次对齐锚点新 → 应用远端 locale/theme；
 * - 远端无记录（新账户）→ 直接上传本地。
 * 全程静默：任何失败仅 debug 日志。
 */
const syncNow = async (trigger: 'login' | 'periodic'): Promise<void> => {
  if (syncInFlight) return
  if (!configStore.getPrefSyncEnabled()) return
  const tokens = loadCloudTokens()
  if (!tokens?.accessToken) return
  syncInFlight = true
  try {
    const remote = await fetchRemotePrefs(tokens.accessToken)
    if (serverSupported === false) return
    if (!remote) return

    const hasLocalDirty = localDirtyAt > (Date.parse(lastSyncAnchor) || 0)
    if (!remote.updatedAt) {
      // 远端无记录（新账户/未上传过）：上传本地作为初始值
      await pushLocalPrefs(tokens.accessToken)
      return
    }
    if (hasLocalDirty) {
      await pushLocalPrefs(tokens.accessToken)
      return
    }
    const remoteNewer = Date.parse(remote.updatedAt) > (Date.parse(lastSyncAnchor) || 0)
    if (remoteNewer && !sameAsLocal(remote.prefs)) {
      applyRemotePrefs(remote.prefs)
    }
    lastSyncAnchor = remote.updatedAt
    if (trigger === 'login') logger.debug('Cloud pref sync aligned on login')
  } finally {
    syncInFlight = false
  }
}

/* ── 对外钩子（cloud/index.ts 与 ipc-handlers 调用） ── */

/** 本地显示偏好变更（renderer 经 setLocale/setTheme/setOnboarding IPC 写入）后调用：3s 防抖上传 */
const notifyLocalPrefChange = (): void => {
  // 防回环：远程应用引发的渲染层同值回写，不计为本地改动、不触发上传
  if (Date.now() < remoteApplyGuardUntil) return
  if (!configStore.getPrefSyncEnabled()) return
  const tokens = loadCloudTokens()
  if (!tokens?.accessToken) return
  localDirtyAt = Date.now()
  if (serverSupported === false) return
  if (uploadTimer) clearTimeout(uploadTimer)
  uploadTimer = setTimeout(() => {
    uploadTimer = null
    const current = loadCloudTokens()
    if (current?.accessToken) void pushLocalPrefs(current.accessToken)
  }, UPLOAD_DEBOUNCE_MS)
}

/** 云登录成功（含启动时恢复会话）后调用：重探端点 + 立即对齐 + 启动 6h 定时器 */
const onCloudAuthorized = (): void => {
  // 重新登录时重置端点判定，给未上线端点再次探测的机会
  serverSupported = null
  const currentGeneration = generation
  void syncNow('login')
  if (alignTimer) clearInterval(alignTimer)
  alignTimer = setInterval(() => {
    if (currentGeneration !== generation) {
      if (alignTimer) {
        clearInterval(alignTimer)
        alignTimer = null
      }
      return
    }
    void syncNow('periodic')
  }, ALIGN_INTERVAL_MS)
}

/** 云登出后调用：停止定时器与待上传任务，重置会话状态 */
const onCloudSignedOut = (): void => {
  generation += 1
  if (uploadTimer) {
    clearTimeout(uploadTimer)
    uploadTimer = null
  }
  if (alignTimer) {
    clearInterval(alignTimer)
    alignTimer = null
  }
  lastSyncAnchor = ''
  localDirtyAt = 0
  serverSupported = null
}

export const cloudPrefsSync = {
  notifyLocalPrefChange,
  onCloudAuthorized,
  onCloudSignedOut,
}
