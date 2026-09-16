import { createHash, randomBytes } from 'node:crypto'
import { createLuomiNestLogger } from '../luomi-logger'

const logger = createLuomiNestLogger('CloudAuthClient')

/** OAuth 公共客户端标识（公共客户端，设计上非机密） */
const CLIENT_ID = 'luominest-desktop'

const REQUEST_TIMEOUT_MS = 15000
/** slow_down 后在原 interval 基础上追加的退避时长（秒） */
const SLOW_DOWN_BACKOFF_SECONDS = 5

export interface DeviceAuthorization {
  deviceCode: string
  userCode: string
  verificationUri: string
  verificationUriComplete: string
  /** 授权码有效期（秒） */
  expiresIn: number
  /** 轮询起始间隔（秒） */
  interval: number
}

export interface TokenSet {
  accessToken: string
  refreshToken: string
  /** access token 有效期（秒） */
  expiresIn: number
  /** OIDC ID Token（服务端返回时携带；仅用于解出 sub 存档，不参与鉴权） */
  idToken?: string
}

/** token 端点业务错误（错误码字符串透传，如 authorization_pending / access_denied） */
export class CloudAuthError extends Error {
  readonly code: string

  constructor(code: string, description?: string) {
    super(description ? `${code}: ${description}` : code)
    this.name = 'CloudAuthError'
    this.code = code
  }
}

const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms))

const asString = (value: unknown, field: string): string => {
  if (typeof value !== 'string' || !value) throw new CloudAuthError('invalid_response', field)
  return value
}

const formBody = (fields: Record<string, string>): string => new URLSearchParams(fields).toString()

/** POST form 请求并解析 JSON 响应；非 2xx 按错误码抛 CloudAuthError */
const postForm = async (url: string, body: string): Promise<Record<string, unknown>> => {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body,
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  })
  const data = (await response.json().catch(() => ({}))) as Record<string, unknown>
  if (!response.ok) {
    const code = typeof data.error === 'string' && data.error ? data.error : `http_${response.status}`
    const description = typeof data.error_description === 'string' ? data.error_description : undefined
    throw new CloudAuthError(code, description)
  }
  return data
}

/**
 * 授权 scope 全集（D48：device_authorization 的 scope 就是本次 grant 的上限，
 * 缺省/少写拿到的票不含 coin.read，userinfo 永远拿不到云积分余额）。
 */
const SCOPE = 'openid profile email coin.read'

/** 发起设备授权，获取 user_code 与验证链接 */
export const requestDeviceAuthorization = async (issuer: string): Promise<DeviceAuthorization> => {
  const data = await postForm(
    `${issuer}/oauth2/device_authorization`,
    formBody({ client_id: CLIENT_ID, scope: SCOPE })
  )
  const interval = typeof data.interval === 'number' && data.interval > 0 ? data.interval : 5
  return {
    deviceCode: asString(data.device_code, 'device_code'),
    userCode: asString(data.user_code, 'user_code'),
    verificationUri: asString(data.verification_uri, 'verification_uri'),
    verificationUriComplete:
      typeof data.verification_uri_complete === 'string' && data.verification_uri_complete
        ? data.verification_uri_complete
        : asString(data.verification_uri, 'verification_uri'),
    expiresIn: typeof data.expires_in === 'number' && data.expires_in > 0 ? data.expires_in : 600,
    interval,
  }
}

/** 从 token 响应提取令牌组 */
const toTokenSet = (data: Record<string, unknown>): TokenSet => ({
  accessToken: asString(data.access_token, 'access_token'),
  refreshToken: asString(data.refresh_token, 'refresh_token'),
  expiresIn: typeof data.expires_in === 'number' && data.expires_in > 0 ? data.expires_in : 0,
  idToken: typeof data.id_token === 'string' && data.id_token ? data.id_token : undefined,
})

export interface DeviceTokenPollOptions {
  interval: number
  /** 授权码有效期（秒），超时主动终止轮询 */
  expiresIn: number
  /** 外部取消检查（如用户登出/重新登录），返回 true 时以 cancelled 终止 */
  isCancelled?: () => boolean
}

/**
 * 轮询 token 端点直到授权完成：
 * authorization_pending → 按 interval 重试；slow_down → interval + 5s；
 * expired_token / access_denied 等终态错误直接抛出。
 */
export const pollForDeviceToken = async (
  issuer: string,
  deviceCode: string,
  options: DeviceTokenPollOptions
): Promise<TokenSet> => {
  let intervalSeconds = options.interval
  const deadline = Date.now() + options.expiresIn * 1000

  for (;;) {
    if (options.isCancelled?.()) throw new CloudAuthError('cancelled')
    if (Date.now() >= deadline) throw new CloudAuthError('expired_token')

    await sleep(intervalSeconds * 1000)
    if (options.isCancelled?.()) throw new CloudAuthError('cancelled')

    try {
      const data = await postForm(
        `${issuer}/oauth2/token`,
        formBody({
          client_id: CLIENT_ID,
          grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
          device_code: deviceCode,
        })
      )
      return toTokenSet(data)
    } catch (err) {
      if (err instanceof CloudAuthError) {
        if (err.code === 'authorization_pending') continue
        if (err.code === 'slow_down') {
          intervalSeconds += SLOW_DOWN_BACKOFF_SECONDS
          continue
        }
        throw err
      }
      // 网络抖动等瞬时错误不终止流程，交由 deadline 兜底
      logger.warn('Token poll transient error:', err instanceof Error ? err.message : err)
    }
  }
}

/** 用 refresh_token 静默续期；服务端未返回新 refresh_token 时由调用方沿用旧值 */
export const refreshAccessToken = async (
  issuer: string,
  refreshToken: string
): Promise<Omit<TokenSet, 'refreshToken'> & { refreshToken?: string }> => {
  const data = await postForm(
    `${issuer}/oauth2/token`,
    formBody({
      client_id: CLIENT_ID,
      grant_type: 'refresh_token',
      refresh_token: refreshToken,
    })
  )
  return {
    accessToken: asString(data.access_token, 'access_token'),
    expiresIn: typeof data.expires_in === 'number' && data.expires_in > 0 ? data.expires_in : 0,
    refreshToken: typeof data.refresh_token === 'string' && data.refresh_token ? data.refresh_token : undefined,
    idToken: typeof data.id_token === 'string' && data.id_token ? data.id_token : undefined,
  }
}

/* ── 本地回环直登（授权码 + PKCE，对标 Trae/ZCode 式"直接授权"）──
 * 浏览器授权后 302 回 127.0.0.1 固定端口，本地 HTTP 服务接码换取令牌；
 * 无需手输用户码。Device Flow 保留为回退通道（端口被占/服务端未部署直登时）。
 * 回调地址已在主站 PassportClientSeeder 按精确 URI 注册（2026-09-16）。 */

export const LOOPBACK_PORT = 17870
export const LOOPBACK_REDIRECT = `http://127.0.0.1:${LOOPBACK_PORT}/callback`

export interface AuthorizeStart {
  /** 授权页完整地址（含 PKCE challenge/state，可直接 shell.openExternal） */
  url: string
  /** CSRF 防护随机值（回环回调时必须原样带回） */
  state: string
  /** PKCE verifier：仅存本地，换码时上送以证明本机发起 */
  verifier: string
}

const b64url = (input: Buffer): string => input.toString('base64url')

/** 构造授权码流程的授权页地址（PKCE S256 强制，public client 无密钥） */
export const buildAuthorizeUrl = (issuer: string): AuthorizeStart => {
  const verifier = b64url(randomBytes(32))
  const challenge = b64url(createHash('sha256').update(verifier).digest())
  const state = b64url(randomBytes(16))
  const url = new URL('/oauth2/authorize', issuer)
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('client_id', CLIENT_ID)
  url.searchParams.set('redirect_uri', LOOPBACK_REDIRECT)
  url.searchParams.set('scope', SCOPE)
  url.searchParams.set('state', state)
  url.searchParams.set('code_challenge', challenge)
  url.searchParams.set('code_challenge_method', 'S256')
  return { url: url.toString(), state, verifier }
}

/** 授权码换令牌（code 60 秒一次性；verifier 与 challenge 校验绑定同一次登录） */
export const exchangeAuthorizationCode = async (
  issuer: string,
  code: string,
  verifier: string
): Promise<TokenSet> => {
  const data = await postForm(
    `${issuer}/oauth2/token`,
    formBody({
      client_id: CLIENT_ID,
      grant_type: 'authorization_code',
      code,
      redirect_uri: LOOPBACK_REDIRECT,
      code_verifier: verifier,
    })
  )
  return toTokenSet(data)
}
