import { join } from 'path'
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs'
import { randomBytes } from 'crypto'
import { PATHS } from '../paths'
import { createLuomiNestLogger } from '../luomi-logger'

const logger = createLuomiNestLogger('Backend')

let cachedToken: string | null = null

export const getLumiAuthToken = (): string => {
  if (cachedToken) return cachedToken

  const configDir = join(PATHS.backendData, 'config')
  const tokenPath = join(configDir, 'auth_token')

  if (existsSync(tokenPath)) {
    cachedToken = readFileSync(tokenPath, 'utf-8').trim()
    if (cachedToken) return cachedToken
  }

  mkdirSync(configDir, { recursive: true })
  cachedToken = randomBytes(32).toString('base64url')
  writeFileSync(tokenPath, cachedToken, 'utf-8')
  logger.info('Generated local auth token at', tokenPath)
  return cachedToken
}
