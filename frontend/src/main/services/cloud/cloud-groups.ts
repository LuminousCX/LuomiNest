/**
 * 云端群聊客户端（v1）
 *
 * 服务端端点已在 luominest-cloud 实现，但可能尚未部署到生产——调用方必须优雅降级。
 *
 * 服务端契约（全部登录态 Bearer，Result 信封，兼容裸对象与 { data: {...} } 包裹）：
 * - POST {baseUrl}/api/v1/cloud-groups                          body {name}          → GroupVo
 * - GET  {baseUrl}/api/v1/cloud-groups                                               → GroupVo[]
 * - POST {baseUrl}/api/v1/cloud-groups/{id}/members             body {userId}        → 成员Vo（仅群主/管理员；幂等）
 * - GET  {baseUrl}/api/v1/cloud-groups/{id}/messages?sinceId=0&limit=50              → GroupMessageVo[]（id 升序，limit≤200）
 * - POST {baseUrl}/api/v1/cloud-groups/{id}/messages            body {content≤2000}  → GroupMessageVo
 *
 * GroupVo: { id(字符串雪花), name, ownerId, memberCount, myRole }
 * GroupMessageVo: { id, senderId, senderName, content, createdAt }
 *
 * 错误策略（结构化返回，不抛异常到调用栈外）：
 * - 401：走现有令牌续期路径（renewCloudTokensNow）后重试一次，仍 401 → 'unauthorized'；
 * - 404/501：服务端端点未上线 → 'unavailable'（renderer 显示「云端群聊服务暂未开通」空态，不重试轰炸）；
 * - 403：非成员/无权限 → 'forbidden'；429：频控 → 'rate_limited'；
 * - 未登录 → 'not_logged_in'；网络/超时 → 'network'；其余非 2xx → 'server'。
 */
import { configStore } from '../config-store'
import { loadCloudTokens } from './token-store'
import { renewCloudTokensNow } from './index'
import { createLuomiNestLogger } from '../luomi-logger'

const logger = createLuomiNestLogger('CloudGroups')

/** 云端群聊端点（拼在 baseUrl 之后） */
const GROUPS_PATH = '/api/v1/cloud-groups'
const REQUEST_TIMEOUT_MS = 10_000
/** 消息分页上限（服务端契约：limit ≤ 200） */
export const CLOUD_GROUP_MESSAGE_LIMIT_MAX = 200

/** 云端群（服务端 GroupVo） */
export interface CloudGroupVo {
  id: string
  name: string
  ownerId: string
  memberCount: number
  myRole: string
}

/** 云端群消息（服务端 GroupMessageVo） */
export interface CloudGroupMessageVo {
  id: string
  senderId: string
  senderName: string
  content: string
  createdAt: string
}

/** 结构化错误类别（renderer 按 kind 映射本地化文案 / 降级空态） */
export type CloudGroupErrorKind =
  | 'not_logged_in'
  | 'unavailable'
  | 'unauthorized'
  | 'forbidden'
  | 'not_found'
  | 'rate_limited'
  | 'network'
  | 'server'

/** 结构化错误（可跨 IPC 序列化） */
export interface CloudGroupErrorInfo {
  kind: CloudGroupErrorKind
  status?: number
  message?: string
}

/** 所有客户端函数的统一返回：成功带数据，失败带结构化错误 */
export type CloudGroupResult<T> = { ok: true; data: T } | { ok: false; error: CloudGroupErrorInfo }

/* ── 响应解析（照抄 prefs-sync 的 Envelope 兼容范式） ── */

/** 兼容裸对象与 { data: {...} } 包裹两种响应形态 */
const unwrapObject = (payload: Record<string, unknown> | null): Record<string, unknown> => {
  if (!payload) return {}
  const data = payload.data
  return data && typeof data === 'object' && !Array.isArray(data) ? (data as Record<string, unknown>) : payload
}

/** 兼容裸数组与 { data: [...] } 包裹两种响应形态 */
const unwrapArray = (payload: Record<string, unknown> | null): unknown[] => {
  if (!payload) return []
  if (Array.isArray(payload)) return payload
  const data = payload.data
  return Array.isArray(data) ? data : []
}

/** Result 信封的业务错误码：非 0 视为业务失败（HTTP 可能仍是 200） */
const envelopeError = (payload: Record<string, unknown> | null): CloudGroupErrorInfo | null => {
  if (!payload) return null
  const code = payload.code
  if (typeof code === 'number' && code !== 0) {
    return {
      kind: 'server',
      message: typeof payload.message === 'string' ? payload.message : `code=${code}`,
    }
  }
  return null
}

/** 字段清洗：宽松解析，缺字段以空值兜底，绝不让脏响应炸掉调用方 */
const parseGroupVo = (raw: unknown): CloudGroupVo | null => {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const source = raw as Record<string, unknown>
  const id = typeof source.id === 'string' ? source.id : typeof source.id === 'number' ? String(source.id) : ''
  if (!id) return null
  return {
    id,
    name: typeof source.name === 'string' ? source.name : '',
    ownerId:
      typeof source.ownerId === 'string'
        ? source.ownerId
        : typeof source.ownerId === 'number'
          ? String(source.ownerId)
          : '',
    memberCount: typeof source.memberCount === 'number' && Number.isFinite(source.memberCount) ? source.memberCount : 0,
    myRole: typeof source.myRole === 'string' ? source.myRole : 'member',
  }
}

const parseMessageVo = (raw: unknown): CloudGroupMessageVo | null => {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const source = raw as Record<string, unknown>
  const id = typeof source.id === 'string' ? source.id : typeof source.id === 'number' ? String(source.id) : ''
  if (!id) return null
  return {
    id,
    senderId:
      typeof source.senderId === 'string'
        ? source.senderId
        : typeof source.senderId === 'number'
          ? String(source.senderId)
          : '',
    senderName: typeof source.senderName === 'string' ? source.senderName : '',
    content: typeof source.content === 'string' ? source.content : '',
    createdAt: typeof source.createdAt === 'string' ? source.createdAt : '',
  }
}

/* ── HTTP 基础设施 ── */

interface RawResponse {
  status: number
  payload: Record<string, unknown> | null
}

/** 单次请求：非 2xx 也返回状态码供调用方分类，网络/解析异常以 status=0 表达 */
const requestOnce = async (
  method: 'GET' | 'POST',
  url: string,
  accessToken: string,
  body?: unknown,
): Promise<RawResponse> => {
  try {
    const response = await fetch(url, {
      method,
      headers: body !== undefined
        ? { 'content-type': 'application/json', authorization: `Bearer ${accessToken}` }
        : { authorization: `Bearer ${accessToken}` },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    })
    const payload = (await response.json().catch(() => null)) as Record<string, unknown> | null
    return { status: response.status, payload: payload && typeof payload === 'object' ? payload : null }
  } catch (err) {
    logger.debug(`Cloud groups request failed (${method} ${url}):`, err instanceof Error ? err.message : err)
    return { status: 0, payload: null }
  }
}

/** 把 HTTP 状态码归类为结构化错误 */
const classifyStatus = (status: number, payload: Record<string, unknown> | null): CloudGroupErrorInfo => {
  const envelope = envelopeError(payload)
  switch (status) {
    case 0:
      return { kind: 'network' }
    case 401:
      return { kind: 'unauthorized', status }
    case 403:
      return { kind: 'forbidden', status }
    case 404:
    case 501:
      // 端点未部署到生产 → 「云端群聊服务暂未开通」降级
      return { kind: 'unavailable', status }
    case 429:
      return { kind: 'rate_limited', status }
    default:
      return envelope ?? { kind: 'server', status }
  }
}

/**
 * 请求 + 401 自愈：401 时走 renewCloudTokensNow（现有令牌过期处理路径）后重试一次。
 * 其余非 2xx 直接归类为结构化错误。
 */
const requestWithRenewal = async (
  method: 'GET' | 'POST',
  path: string,
  body?: unknown,
): Promise<CloudGroupResult<RawResponse>> => {
  const { baseUrl } = configStore.getCloudConfig()
  const url = `${baseUrl}${path}`

  let tokens = loadCloudTokens()
  if (!tokens?.accessToken) {
    return { ok: false, error: { kind: 'not_logged_in' } }
  }

  let result = await requestOnce(method, url, tokens.accessToken, body)
  if (result.status === 401) {
    // 令牌过期：走现有续期路径后用新令牌重试一次（不循环轰炸）
    logger.debug('Cloud groups request got 401; renewing tokens and retrying once')
    const renewed = await renewCloudTokensNow()
    tokens = loadCloudTokens()
    if (renewed && tokens?.accessToken) {
      result = await requestOnce(method, url, tokens.accessToken, body)
    }
  }

  if (result.status < 200 || result.status >= 300) {
    return { ok: false, error: classifyStatus(result.status, result.payload) }
  }
  const envelope = envelopeError(result.payload)
  if (envelope) return { ok: false, error: envelope }
  return { ok: true, data: result }
}

/* ── 五个客户端函数 ── */

/** 群列表载荷：附带当前用户 id（id_token.sub 存档，用于渲染层区分自己的消息；缺失为空串） */
export interface CloudGroupListPayload {
  groups: CloudGroupVo[]
  meId: string
}

/** GET /cloud-groups → 群列表（附带 meId） */
const list = async (): Promise<CloudGroupResult<CloudGroupListPayload>> => {
  const result = await requestWithRenewal('GET', GROUPS_PATH)
  if (!result.ok) return result
  const groups = unwrapArray(result.data.payload)
    .map(parseGroupVo)
    .filter((item): item is CloudGroupVo => item !== null)
  return { ok: true, data: { groups, meId: loadCloudTokens()?.passportSub ?? '' } }
}

/** POST /cloud-groups {name} → 新群 GroupVo */
const create = async (name: string): Promise<CloudGroupResult<CloudGroupVo>> => {
  const trimmed = name.trim()
  if (!trimmed) return { ok: false, error: { kind: 'server', message: 'group name is empty' } }
  const result = await requestWithRenewal('POST', GROUPS_PATH, { name: trimmed })
  if (!result.ok) return result
  const group = parseGroupVo(unwrapObject(result.data.payload))
  if (!group) {
    return { ok: false, error: { kind: 'server', message: 'invalid GroupVo payload' } }
  }
  return { ok: true, data: group }
}

/** POST /cloud-groups/{id}/members {userId} → 邀请成员（仅群主/管理员；幂等） */
const invite = async (groupId: string, userId: string): Promise<CloudGroupResult<boolean>> => {
  const gid = groupId.trim()
  const uid = userId.trim()
  if (!gid || !uid) return { ok: false, error: { kind: 'server', message: 'groupId/userId is empty' } }
  const result = await requestWithRenewal('POST', `${GROUPS_PATH}/${encodeURIComponent(gid)}/members`, { userId: uid })
  if (!result.ok) return result
  return { ok: true, data: true }
}

/** GET /cloud-groups/{id}/messages?sinceId=&limit= → 消息列表（id 升序） */
const listMessages = async (
  groupId: string,
  sinceId: string,
  limit: number,
): Promise<CloudGroupResult<CloudGroupMessageVo[]>> => {
  const gid = groupId.trim()
  if (!gid) return { ok: false, error: { kind: 'server', message: 'groupId is empty' } }
  const safeLimit = Math.max(1, Math.min(Math.floor(limit) || 50, CLOUD_GROUP_MESSAGE_LIMIT_MAX))
  const query = `sinceId=${encodeURIComponent(sinceId || '0')}&limit=${safeLimit}`
  const result = await requestWithRenewal('GET', `${GROUPS_PATH}/${encodeURIComponent(gid)}/messages?${query}`)
  if (!result.ok) return result
  const messages = unwrapArray(result.data.payload)
    .map(parseMessageVo)
    .filter((item): item is CloudGroupMessageVo => item !== null)
  return { ok: true, data: messages }
}

/** POST /cloud-groups/{id}/messages {content≤2000} → 已落库消息 */
const sendMessage = async (groupId: string, content: string): Promise<CloudGroupResult<CloudGroupMessageVo>> => {
  const gid = groupId.trim()
  const text = content.trim()
  if (!gid || !text) return { ok: false, error: { kind: 'server', message: 'groupId/content is empty' } }
  if (text.length > 2000) {
    return { ok: false, error: { kind: 'server', message: 'content exceeds 2000 chars' } }
  }
  const result = await requestWithRenewal('POST', `${GROUPS_PATH}/${encodeURIComponent(gid)}/messages`, {
    content: text,
  })
  if (!result.ok) return result
  const message = parseMessageVo(unwrapObject(result.data.payload))
  if (!message) {
    return { ok: false, error: { kind: 'server', message: 'invalid GroupMessageVo payload' } }
  }
  return { ok: true, data: message }
}

export const cloudGroups = {
  list,
  create,
  invite,
  listMessages,
  sendMessage,
}
