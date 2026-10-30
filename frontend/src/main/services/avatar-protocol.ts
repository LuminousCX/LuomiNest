import { app, dialog, protocol, IpcMainInvokeEvent } from 'electron'
import { join, dirname, basename, resolve, sep } from 'path'
import { existsSync, readdirSync, readFileSync, writeFileSync, mkdirSync, rmSync, statSync, copyFileSync } from 'fs'
import { PATHS } from './paths'
import { ImportedModelRecord, loadImportedModels, saveImportedModels } from './desktop-pet'
import { createLuomiNestLogger } from './luomi-logger'
import { handleIpc } from './typed-ipc'
import { IpcChannels } from '@shared/ipc-types'
import type { AvatarResourceCheck, AvatarDiagnosticsResult } from '@shared/ipc-types'

const logger = createLuomiNestLogger('Avatar')

const isDev = !app.isPackaged

const builtinBasePath = isDev
  ? join(app.getAppPath(), 'src/renderer/public/live2d')
  : join(process.resourcesPath, 'live2d')

const MIME_MAP: Record<string, string> = {
  json: 'application/json',
  moc3: 'application/octet-stream',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  mtn: 'application/octet-stream',
  exp3: 'application/json',
  physics3: 'application/json',
  pose3: 'application/json',
  motion3: 'application/json',
  cdi3: 'application/json',
  userdata3: 'application/json',
  js: 'application/javascript',
  wasm: 'application/wasm',
  txt: 'text/plain',
  // 多模型扩展：VRM / Spine / glTF 支持
  vrm: 'application/octet-stream',
  glb: 'model/gltf-binary',
  gltf: 'model/gltf+json',
  atlas: 'text/plain',
  skel: 'application/octet-stream',
  webp: 'image/webp',
  gif: 'image/gif',
  svg: 'image/svg+xml'
}

// 已知的模型类型前缀（用于 hostname 路由）
const MODEL_TYPE_PREFIXES = ['live2d', 'vrm', 'pixel', 'spine', 'png'] as const
type ModelTypePrefix = typeof MODEL_TYPE_PREFIXES[number]

const isModelTypePrefix = (s: string): s is ModelTypePrefix => {
  return (MODEL_TYPE_PREFIXES as readonly string[]).includes(s)
}

// 各模型类型的 builtin 基础路径（相对于 public/ 或 resourcesPath/）
const getBuiltinBasePath = (type: ModelTypePrefix): string => {
  return isDev
    ? join(app.getAppPath(), 'src/renderer/public', type)
    : join(process.resourcesPath, type)
}

// 各模型类型的 imported 基础路径（userData/avatar/{type}/）
const getImportedBasePath = (type: ModelTypePrefix): string => {
  return join(PATHS.avatar, type)
}

const isPathSafe = (baseDir: string, targetPath: string): boolean => {
  const resolved = resolve(baseDir, targetPath)
  const resolvedBase = resolve(baseDir) + sep
  return resolved.startsWith(resolvedBase)
}

const resolveModelFile = (hostname: string, relativePath: string): string | null => {
  const decodedPath = decodeURIComponent(relativePath)

  // 协作者头像缓存：hostname 为 cached，映射到 userData/Cache/avatars/
  // 例如：luominest-avatar://cached/luminous-ChenXi.png
  if (hostname === 'cached') {
    if (!isPathSafe(PATHS.avatarCache, decodedPath)) {
      logger.warn(`Path traversal blocked: cached:${decodedPath}`)
      return null
    }
    const filePath = resolve(PATHS.avatarCache, decodedPath)
    if (existsSync(filePath) && statSync(filePath).isFile()) return filePath
    logger.warn(`Resource not found: cached/${relativePath}`)
    return null
  }

  // 新格式：hostname 是模型类型前缀（live2d/vrm/pixel/spine/png）
  // 例如：luominest-avatar://pixel/default-pet/manifest.json
  if (isModelTypePrefix(hostname)) {
    const typeBase = hostname
    const searchPaths: { label: string; base: string; sub: string }[] = [
      { label: `imported-${typeBase}`, base: getImportedBasePath(typeBase), sub: decodedPath },
      { label: `builtin-${typeBase}`, base: getBuiltinBasePath(typeBase), sub: decodedPath }
    ]
    for (const sp of searchPaths) {
      try {
        if (!isPathSafe(sp.base, sp.sub)) {
          logger.warn(`Path traversal blocked: ${sp.label}:${sp.sub}`)
          continue
        }
        const filePath = resolve(sp.base, sp.sub)
        if (existsSync(filePath) && statSync(filePath).isFile()) return filePath
      } catch {
        continue
      }
    }
    logger.warn(`Resource not found: ${hostname}/${relativePath}`)
    logger.warn(`  Searched: ${searchPaths.map(s => s.label + ':' + resolve(s.base, s.sub)).join(' | ')}`)
    return null
  }

  // 旧格式回退：hostname 是 Live2D 模型名（如 llny / hiyori）
  // 例如：luominest-avatar://llny/llny.model3.json
  // 保留原逻辑以确保现有 Live2D 模型 URL 完全不受影响
  const searchPaths: { label: string; base: string; sub: string }[] = [
    { label: 'imported', base: PATHS.live2d, sub: join(hostname, decodedPath) },
    { label: 'builtin', base: builtinBasePath, sub: join(hostname, decodedPath) }
  ]

  for (const sp of searchPaths) {
    try {
      if (!isPathSafe(sp.base, sp.sub)) {
        logger.warn(`Path traversal blocked: ${sp.label}:${sp.sub}`)
        continue
      }
      const filePath = resolve(sp.base, sp.sub)
      if (existsSync(filePath) && statSync(filePath).isFile()) return filePath
    } catch {
      continue
    }
  }

  logger.warn(`Resource not found: ${hostname}/${relativePath}`)
  logger.warn(`  Searched: ${searchPaths.map(s => s.label + ':' + resolve(s.base, s.sub)).join(' | ')}`)
  return null
}

const copyDirRecursive = (src: string, dst: string): void => {
  mkdirSync(dst, { recursive: true })
  const entries = readdirSync(src, { withFileTypes: true })
  for (const entry of entries) {
    const srcPath = join(src, entry.name)
    const dstPath = join(dst, entry.name)
    if (entry.isDirectory()) {
      copyDirRecursive(srcPath, dstPath)
    } else if (entry.isFile()) {
      copyFileSync(srcPath, dstPath)
    }
  }
}

export function registerAvatarProtocol(): void {
  protocol.handle('luominest-avatar', (request) => {
    try {
      const url = new URL(request.url)
      const hostname = url.hostname
      const relativePath = url.pathname.replace(/^\/+/, '')

      if (!hostname || !relativePath) {
        return new Response('Bad Request: invalid URL', { status: 400 })
      }

      const filePath = resolveModelFile(hostname, relativePath)
      if (!filePath) {
        logger.warn(`404: ${hostname}/${relativePath}`)
        return new Response('Not Found', { status: 404 })
      }

      const ext = filePath.split('.').pop()?.toLowerCase()
      const mimeType = MIME_MAP[ext ?? ''] ?? 'application/octet-stream'
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

  logger.info('Protocol "luominest-avatar" registered successfully')
  logger.info(`  builtinBasePath -> ${builtinBasePath}`)
  logger.info(`  isPackaged -> ${app.isPackaged}`)
  logger.info(`  resourcesPath -> ${process.resourcesPath}`)
}

/**
 * 后端 PyInstaller 产物内的 avatar-manifest.json 路径（工坊 UI 的单一真相源）。
 *
 * 历史根因（v0.8.0）：该文件未随打包落盘 → 后端 /avatar/manifest 返回空清单 →
 * 打包版内置模型全部不可见。诊断把它列为第一检查项，让"装包缺文件"一眼可见：
 * - 打包态：resources/backend/_internal/app/data/avatar-manifest.json（spec 的 ('app/data') 打入 _internal）
 * - 开发态：仓库根 backend/app/data/avatar-manifest.json（__dirname = out/main，'../../..' 到仓库根，
 *   与 services/backend/index.ts 的 projectRoot 推导保持一致）
 */
const getBackendManifestPath = (): string => {
  return isDev
    ? join(__dirname, '../../..', 'backend', 'app', 'data', 'avatar-manifest.json')
    : join(process.resourcesPath, 'backend', '_internal', 'app', 'data', 'avatar-manifest.json')
}

/** 按 luominest-avatar:// 协议相同解析顺序（imported → builtin）返回某相对路径的候选绝对路径 */
const resolveManifestResourceCandidates = (relPath: string): string[] => {
  let decodedPath: string
  try {
    decodedPath = decodeURIComponent(relPath)
  } catch {
    decodedPath = relPath
  }

  const firstSeg = decodedPath.split('/')[0]
  if (isModelTypePrefix(firstSeg)) {
    const rest = decodedPath.slice(firstSeg.length + 1)
    return [
      resolve(getImportedBasePath(firstSeg), rest),
      resolve(getBuiltinBasePath(firstSeg), rest)
    ]
  }

  // 旧格式回退："{model}/{file}"（与 resolveModelFile 的 legacy 分支一致）
  return [
    resolve(PATHS.live2d, decodedPath),
    resolve(builtinBasePath, decodedPath)
  ]
}

const runResourceCheck = (label: string, candidates: string[]): AvatarResourceCheck => {
  let ok = false
  for (const p of candidates) {
    try {
      if (existsSync(p) && statSync(p).isFile()) {
        ok = true
        break
      }
    } catch {
      // 单个候选不可访问不判定失败，继续下一个候选
    }
  }
  if (!ok) {
    logger.warn(`Avatar diagnose MISS: ${label} (searched: ${candidates.join(' | ')})`)
  }
  return { label, ok, paths: candidates }
}

/**
 * 内置资源一键诊断（工坊错误卡片"一键诊断"按钮 / 启动自检共用）。
 *
 * 检查三层（对齐审计 §1.4-3"失败显式化"）：
 * 1. 后端 avatar-manifest.json 是否随包落盘（缺失 = 打包版内置模型全部不可见的历史根因）
 * 2. 内置 Live2D 样例（llny.model3.json）是否在位
 * 3. 渲染层上报的 manifest 模型 path/thumbnail 逐项是否存在
 */
export function diagnoseAvatarResources(modelPaths: string[] = []): AvatarDiagnosticsResult {
  const checks: AvatarResourceCheck[] = [
    runResourceCheck('backend/avatar-manifest.json', [getBackendManifestPath()]),
    runResourceCheck('live2d builtin sample: llny/llny.model3.json', [
      resolve(builtinBasePath, 'llny', 'llny.model3.json')
    ]),
    ...modelPaths.map(p => runResourceCheck(p, resolveManifestResourceCandidates(p)))
  ]
  const missing = checks.filter(c => !c.ok)
  return {
    ok: missing.length === 0,
    isPackaged: app.isPackaged,
    builtinBasePath,
    manifestModelCount: modelPaths.length,
    checks,
    missing
  }
}

/**
 * 启动自检（main/index.ts 启动时调用）。行为与历史版本兼容：结果仅写日志、
 * 不弹 UI；结构化结果经 avatar:diagnoseResources IPC 提供给渲染层主动查询。
 */
export function verifyAvatarResources(): AvatarDiagnosticsResult {
  const result = diagnoseAvatarResources([])
  if (!result.ok) {
    logger.warn(`Avatar resource self-check FAILED: ${result.missing.length} item(s) missing`)
    for (const m of result.missing) {
      logger.warn(`  missing: ${m.label}`)
    }
  } else {
    logger.info('Avatar resource self-check OK')
  }
  return result
}

export function registerAvatarIpc(): void {
  handleIpc(IpcChannels.avatar.invoke.importModel, async () => {
    try {
      const result = await dialog.showOpenDialog({
        title: 'Import LuomiNest Avatar Model',
        filters: [
          { name: 'Live2D Model', extensions: ['model3.json'] }
        ],
        properties: ['openFile']
      })

      if (result.canceled || result.filePaths.length === 0) {
        return { success: false, error: 'Cancelled' }
      }

      const selectedFile = result.filePaths[0]
      const modelDir = dirname(selectedFile)
      const modelFileName = basename(selectedFile)
      const modelName = modelFileName.replace('.model3.json', '')

      const destDir = join(PATHS.live2d, modelName)

      if (existsSync(destDir)) {
        rmSync(destDir, { recursive: true, force: true })
      }

      mkdirSync(PATHS.live2d, { recursive: true })
      copyDirRecursive(modelDir, destDir)

      const modelJsonPath = join(destDir, modelFileName)
      if (!existsSync(modelJsonPath)) {
        rmSync(destDir, { recursive: true, force: true })
        return { success: false, error: `Model file "${modelFileName}" not found after copy` }
      }

      try {
        const modelJsonContent = readFileSync(modelJsonPath, 'utf-8')
        const modelJson = JSON.parse(modelJsonContent)
        if (!modelJson.FileReferences || !modelJson.FileReferences.Moc) {
          rmSync(destDir, { recursive: true, force: true })
          return { success: false, error: 'Invalid model3.json: missing FileReferences.Moc' }
        }
      } catch {
        rmSync(destDir, { recursive: true, force: true })
        return { success: false, error: 'Invalid model3.json: parse error' }
      }

      const modelUrl = `luominest-avatar://${modelName}/${modelFileName}`

      const modelRecord: ImportedModelRecord = {
        id: `imported-${Date.now()}`,
        name: modelName,
        url: modelUrl,
        scale: 0.25,
        type: 'live2d',
        tags: ['Imported']
      }

      const models = loadImportedModels()
      const existingIdx = models.findIndex(m => m.name === modelName)
      if (existingIdx >= 0) {
        models[existingIdx] = modelRecord
      } else {
        models.push(modelRecord)
      }
      saveImportedModels(models)

      logger.info(`Model imported: ${modelName} -> ${destDir}`)

      return {
        success: true,
        modelInfo: modelRecord
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      logger.error('Import failed:', message)
      return { success: false, error: message }
    }
  })

  handleIpc(IpcChannels.avatar.invoke.listImportedModels, () => {
    return loadImportedModels()
  })

  handleIpc(IpcChannels.avatar.invoke.deleteModel, async (_e: IpcMainInvokeEvent, modelName: string) => {
    try {
      const destDir = resolve(PATHS.live2d, modelName)
      if (!destDir.startsWith(resolve(PATHS.live2d) + sep)) {
        return { success: false, error: 'Invalid model name' }
      }
      if (existsSync(destDir)) {
        rmSync(destDir, { recursive: true, force: true })
      }

      const models = loadImportedModels()
      const filtered = models.filter(m => m.name !== modelName)
      saveImportedModels(filtered)

      logger.info(`Model deleted: ${modelName}`)
      return { success: true }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      logger.error('Delete failed:', message)
      return { success: false, error: message }
    }
  })

  handleIpc(IpcChannels.avatar.invoke.getImportedModelsPath, () => {
    return PATHS.live2d
  })

  // 一键诊断：渲染层传 manifest 模型的 path/thumbnail 相对路径（可为空 = 只查样例与后端清单），
  // 主进程按协议解析顺序逐项核对文件存在性，结果供工坊错误卡片展示
  handleIpc(IpcChannels.avatar.invoke.diagnoseResources, (_e: IpcMainInvokeEvent, modelPaths?: unknown) => {
    const paths = Array.isArray(modelPaths)
      ? modelPaths.filter((p): p is string => typeof p === 'string' && p.length > 0)
      : []
    return diagnoseAvatarResources(paths)
  })
}
