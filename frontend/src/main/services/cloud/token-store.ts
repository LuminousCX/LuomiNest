import { safeStorage } from 'electron'
import { join } from 'path'
import { readFileSync, writeFileSync, existsSync, unlinkSync } from 'fs'
import { PATHS } from '../paths'
import { createLuomiNestLogger } from '../luomi-logger'

const logger = createLuomiNestLogger('CloudTokenStore')

/** 云端令牌（仅 main 进程内存/磁盘持有，renderer 永不接触） */
export interface StoredCloudTokens {
  accessToken: string
  refreshToken: string
  /** access token 过期时间（epoch ms） */
  accessExpiresAt: number
}

/** 落盘格式：payload 为加密 base64 或明文 JSON 字符串，由 encrypted 标记区分 */
interface TokenFile {
  encrypted: boolean
  payload: string
}

const tokensFilePath = (): string => join(PATHS.config, 'cloud-tokens.json')

const isEncryptionAvailable = (): boolean => {
  try {
    return safeStorage.isEncryptionAvailable()
  } catch {
    return false
  }
}

export const loadCloudTokens = (): StoredCloudTokens | null => {
  const filePath = tokensFilePath()
  if (!existsSync(filePath)) return null
  try {
    const file = JSON.parse(readFileSync(filePath, 'utf-8')) as TokenFile
    if (typeof file.payload !== 'string' || !file.payload) return null
    const raw = file.encrypted ? safeStorage.decryptString(Buffer.from(file.payload, 'base64')) : file.payload
    const parsed = JSON.parse(raw) as Partial<StoredCloudTokens>
    if (typeof parsed.accessToken !== 'string' || !parsed.accessToken) return null
    return {
      accessToken: parsed.accessToken,
      refreshToken: typeof parsed.refreshToken === 'string' ? parsed.refreshToken : '',
      accessExpiresAt: typeof parsed.accessExpiresAt === 'number' ? parsed.accessExpiresAt : 0,
    }
  } catch (err) {
    logger.warn('Failed to load cloud tokens, treat as signed out:', err instanceof Error ? err.message : err)
    return null
  }
}

export const saveCloudTokens = (tokens: StoredCloudTokens): void => {
  const json = JSON.stringify(tokens)
  let file: TokenFile
  if (isEncryptionAvailable()) {
    file = { encrypted: true, payload: safeStorage.encryptString(json).toString('base64') }
  } else {
    // safeStorage 不可用（如无系统 keyring）：明文退化，v1 接受
    console.warn('[CloudTokenStore] safeStorage unavailable, falling back to plaintext token storage')
    file = { encrypted: false, payload: json }
  }
  writeFileSync(tokensFilePath(), JSON.stringify(file), 'utf-8')
}

export const clearCloudTokens = (): void => {
  const filePath = tokensFilePath()
  try {
    if (existsSync(filePath)) unlinkSync(filePath)
  } catch (err) {
    logger.warn('Failed to clear cloud tokens:', err instanceof Error ? err.message : err)
  }
}
