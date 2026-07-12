import { app, dialog, protocol, IpcMainInvokeEvent, ipcMain } from 'electron'
import { join, dirname, basename, resolve, sep } from 'path'
import { existsSync, readdirSync, readFileSync, writeFileSync, mkdirSync, rmSync, statSync, copyFileSync } from 'fs'
import { PATHS } from './paths'
import { ImportedModelRecord, loadImportedModels, saveImportedModels } from './desktop-pet'
import { createLuomiNestLogger } from './luomi-logger'

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
  txt: 'text/plain'
}

const isPathSafe = (baseDir: string, targetPath: string): boolean => {
  const resolved = resolve(baseDir, targetPath)
  const resolvedBase = resolve(baseDir) + sep
  return resolved.startsWith(resolvedBase)
}

const resolveModelFile = (hostname: string, relativePath: string): string | null => {
  const decodedPath = decodeURIComponent(relativePath)

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

export function verifyAvatarResources(): void {
  const verifyResourcePath = (label: string, path: string, sampleFile: string): boolean => {
    const fullPath = join(path, sampleFile)
    const exists = existsSync(fullPath)
    if (!exists) {
      logger.warn(`${label} path check FAILED: ${path} (sample: ${fullPath})`)
    } else {
      logger.info(`${label} path OK: ${path}`)
    }
    return exists
  }

  verifyResourcePath('Builtin Live2D', builtinBasePath, 'llny/llny.model3.json')
}

export function registerAvatarIpc(): void {
  ipcMain.handle('avatar:importModel', async () => {
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

  ipcMain.handle('avatar:listImportedModels', () => {
    return loadImportedModels()
  })

  ipcMain.handle('avatar:deleteModel', async (_e: IpcMainInvokeEvent, modelName: string) => {
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

  ipcMain.handle('avatar:getImportedModelsPath', () => {
    return PATHS.live2d
  })
}
