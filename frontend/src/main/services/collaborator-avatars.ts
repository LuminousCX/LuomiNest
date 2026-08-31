import { join } from 'path'
import { readdirSync, renameSync, rmSync, statSync, writeFileSync } from 'fs'
import { ipcMain } from 'electron'
import { PATHS } from './paths'
import { createLuomiNestLogger } from './luomi-logger'

const logger = createLuomiNestLogger('CollabAvatar')

/**
 * 项目前期合作者的 GitHub 头像来源。
 * 每次启动时尝试从 GitHub 拉取最新头像写入本地缓存，
 * 下载失败时保留上一次的缓存文件（首次启动无缓存则回退到前端打包的静态资源）。
 */
const COLLABORATOR_AVATARS: { key: string; githubUrl: string }[] = [
  { key: 'luminous-ChenXi', githubUrl: 'https://github.com/luminous-ChenXi.png' },
  { key: 'kipbbsjsjs', githubUrl: 'https://github.com/kipbbsjsjs.png' },
  { key: 'NoobL696', githubUrl: 'https://github.com/NoobL696.png' },
]

const REQUEST_TIMEOUT_MS = 10_000

/** 头像缓存 URL 前缀（协议见 avatar-protocol.ts 的 cached 分支） */
const CACHED_PROTOCOL_PREFIX = 'luominest-avatar://cached/'

const extFromContentType = (contentType: string | null): string => {
  if (!contentType) return 'png'
  if (contentType.includes('jpeg')) return 'jpg'
  if (contentType.includes('webp')) return 'webp'
  if (contentType.includes('gif')) return 'gif'
  return 'png'
}

const downloadAvatar = async (key: string, githubUrl: string, destDir: string): Promise<boolean> => {
  const tmpPath = join(destDir, `.${key}.tmp`)
  try {
    const res = await fetch(`${githubUrl}?size=160`, {
      redirect: 'follow',
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      headers: { 'user-agent': 'LuomiNest' }
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const buffer = Buffer.from(await res.arrayBuffer())
    if (buffer.length === 0) throw new Error('Empty response')

    const ext = extFromContentType(res.headers.get('content-type'))
    writeFileSync(tmpPath, buffer)
    // 先写临时文件再原子重命名，避免下载中断导致缓存文件损坏
    renameSync(tmpPath, join(destDir, `${key}.${ext}`))
    logger.info(`Avatar updated: ${key} (${buffer.length}B, ${ext})`)
    return true
  } catch (err) {
    rmSync(tmpPath, { force: true })
    const message = err instanceof Error ? err.message : String(err)
    logger.warn(`Avatar update failed (reuse previous): ${key} - ${message}`)
    return false
  }
}

const findCachedFileName = (key: string, dir: string): string | null => {
  try {
    const entry = readdirSync(dir).find((name) => name.startsWith(`${key}.`))
    return entry ?? null
  } catch {
    return null
  }
}

let updatePromise: Promise<Record<string, boolean>> | null = null

/**
 * 更新所有协作者头像缓存（并发下载）。
 * 更新过程中重复调用会复用同一个进行中的 Promise，避免重复下载。
 */
export const updateCollaboratorAvatars = (): Promise<Record<string, boolean>> => {
  if (!updatePromise) {
    updatePromise = (async () => {
      const results: Record<string, boolean> = {}
      await Promise.all(
        COLLABORATOR_AVATARS.map(async (item) => {
          results[item.key] = await downloadAvatar(item.key, item.githubUrl, PATHS.avatarCache)
        })
      )
      return results
    })().finally(() => {
      updatePromise = null
    })
  }
  return updatePromise
}

/**
 * 获取指定协作者的头像缓存 URL。
 * 缓存文件存在时返回 luominest-avatar://cached/ 协议 URL，否则返回 null（由渲染端回退到打包资源）。
 */
export const getCollaboratorAvatarUrl = (key: string): string | null => {
  const dir = PATHS.avatarCache
  const fileName = findCachedFileName(key, dir)
  if (!fileName) return null
  const filePath = join(dir, fileName)
  try {
    if (!statSync(filePath).isFile()) return null
  } catch {
    return null
  }
  return `${CACHED_PROTOCOL_PREFIX}${encodeURIComponent(fileName)}`
}

export const registerCollaboratorAvatarIpc = (): void => {
  ipcMain.handle('avatar:getCollaboratorAvatar', (_event, key: string) => {
    return { key, url: typeof key === 'string' ? getCollaboratorAvatarUrl(key) : null }
  })

  ipcMain.handle('avatar:updateCollaboratorAvatars', () => updateCollaboratorAvatars())
}
