import { protocol } from 'electron'
import { join, resolve, sep } from 'path'
import { readFileSync, existsSync, statSync } from 'fs'
import { PATHS } from './paths'
import { createLuomiNestLogger } from './luomi-logger'

const logger = createLuomiNestLogger('BgProtocol')

const BG_MIME_MAP: Record<string, string> = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  gif: 'image/gif',
  webp: 'image/webp',
  svg: 'image/svg+xml'
}

const isPathSafe = (baseDir: string, targetPath: string): boolean => {
  const resolved = resolve(baseDir, targetPath)
  const resolvedBase = resolve(baseDir) + sep
  return resolved.startsWith(resolvedBase)
}

/**
 * 注册 luominest-bg: 自定义协议
 * URL 格式: luominest-bg://filename.ext
 * 实际文件路径: PATHS.backgrounds/filename.ext
 */
export function registerBackgroundProtocol(): void {
  protocol.handle('luominest-bg', (request) => {
    try {
      const url = new URL(request.url)
      // luominest-bg://filename 中 filename 被解析为 hostname，pathname 为 / 或空
      const fileName = url.hostname
        ? decodeURIComponent(url.hostname)
        : decodeURIComponent(url.pathname.replace(/^\/+/, ''))

      if (!fileName) {
        return new Response('Bad Request: missing filename', { status: 400 })
      }

      // 安全检查：防止路径穿越
      if (!isPathSafe(PATHS.backgrounds, fileName)) {
        logger.warn(`Path traversal blocked: ${fileName}`)
        return new Response('Forbidden', { status: 403 })
      }

      const filePath = join(PATHS.backgrounds, fileName)

      if (!existsSync(filePath) || !statSync(filePath).isFile()) {
        logger.warn(`Background not found: ${fileName}`)
        return new Response('Not Found', { status: 404 })
      }

      const ext = filePath.split('.').pop()?.toLowerCase() ?? ''
      const mimeType = BG_MIME_MAP[ext] ?? 'application/octet-stream'
      const data = readFileSync(filePath)

      return new Response(data, {
        headers: {
          'content-type': mimeType,
          'access-control-allow-origin': '*',
          'cache-control': 'no-cache',
          'content-length': String(data.byteLength)
        }
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      logger.error('Protocol handler error:', message)
      return new Response('Internal Server Error', { status: 500 })
    }
  })

  logger.info('Protocol "luominest-bg" registered successfully')
}

/**
 * 将背景文件名转换为 luominest-bg: 协议 URL
 */
export function toBackgroundUrl(fileName: string): string {
  return `luominest-bg://${fileName}`
}

/**
 * 判断一个背景图片值是否是 luominest-bg: 协议 URL
 */
export function isBackgroundProtocolUrl(value: string): boolean {
  return value.startsWith('luominest-bg:')
}

/**
 * 判断一个背景图片值是否是预设 CSS 渐变（非文件路径）
 */
export function isCssGradient(value: string): boolean {
  return value.startsWith('linear-gradient') || value.startsWith('radial-gradient') || value.startsWith('conic-gradient')
}
