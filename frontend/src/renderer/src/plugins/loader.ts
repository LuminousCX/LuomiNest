/**
 * CxFrontendPluginLoader — LuomiNest 前端插件加载器。
 *
 * 职责：
 * 1. 构建时通过 import.meta.glob 发现 builtin 插件目录
 * 2. 解析并校验 manifest.json
 * 3. 维护插件实例注册表（CxFrontendPluginInstance）
 * 4. 激活/停用插件：调用模块的 activate/deactivate，管理贡献点生命周期
 * 5. 持久化用户禁用偏好（localStorage）
 *
 * 插件目录约定：
 *   builtin/{plugin-id}/manifest.json   — 元数据（必需）
 *   builtin/{plugin-id}/index.ts        — 入口模块（必需，导出 activate/deactivate）
 *
 * 用户安装的运行时插件（userData/plugins/）暂未实现，预留接口。
 */

import { reactive } from 'vue'
import type {
  CxFrontendPluginInstance,
  CxFrontendPluginManifest,
  CxPluginContext,
  CxPluginModule,
  CxViewContribution,
  CxCommandContribution,
  CxThemeContribution,
} from './types'
import { cxContributionRegistry } from './contributions'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('CxPluginLoader')

// ---------------------------------------------------------------------------
// 构建时发现：builtin 插件的 manifest 与入口模块
// ---------------------------------------------------------------------------

// eager: true — manifest 是小 JSON，立即加载便于启动时建立索引
const manifestModules = import.meta.glob<{ default: CxFrontendPluginManifest }>(
  './builtin/*/manifest.json',
  { eager: true }
)

// 懒加载入口模块：仅在激活时 import，避免启动时加载所有插件代码
const pluginModuleLoaders = import.meta.glob<CxPluginModule>(
  './builtin/*/index.ts'
)

// ---------------------------------------------------------------------------
// 持久化：用户禁用的插件 ID 列表
// ---------------------------------------------------------------------------

const DISABLED_STORAGE_KEY = 'cx_frontend_plugin_disabled_ids'

const loadDisabledIds = (): Set<string> => {
  try {
    const raw = localStorage.getItem(DISABLED_STORAGE_KEY)
    if (!raw) return new Set()
    const arr = JSON.parse(raw)
    return Array.isArray(arr) ? new Set(arr.map(String)) : new Set()
  } catch {
    return new Set()
  }
}

const persistDisabledIds = (ids: Set<string>) => {
  try {
    localStorage.setItem(DISABLED_STORAGE_KEY, JSON.stringify([...ids]))
  } catch (e) {
    logger.warn('Failed to persist disabled plugin ids:', e)
  }
}

// ---------------------------------------------------------------------------
// 注册表
// ---------------------------------------------------------------------------

const _instances = reactive<Record<string, CxFrontendPluginInstance>>({})
const _modules = new Map<string, CxPluginModule>()
const _disabledIds = loadDisabledIds()

// ---------------------------------------------------------------------------
// Manifest 校验
// ---------------------------------------------------------------------------

const validateManifest = (manifest: unknown): manifest is CxFrontendPluginManifest => {
  if (!manifest || typeof manifest !== 'object') return false
  const m = manifest as Record<string, unknown>
  if (typeof m.id !== 'string' || !m.id) {
    logger.error('Invalid manifest: missing or invalid "id"')
    return false
  }
  if (typeof m.name !== 'string' || !m.name) {
    logger.error(`Invalid manifest [${m.id}]: missing or invalid "name"`)
    return false
  }
  if (typeof m.version !== 'string' || !m.version) {
    logger.error(`Invalid manifest [${m.id}]: missing or invalid "version"`)
    return false
  }
  return true
}

// ---------------------------------------------------------------------------
// 发现 builtin 插件
// ---------------------------------------------------------------------------

function discoverBuiltinPlugins(): void {
  for (const [path, mod] of Object.entries(manifestModules)) {
    const manifest = (mod as { default?: CxFrontendPluginManifest }).default
    if (!validateManifest(manifest)) {
      logger.warn(`Skipping invalid manifest: ${path}`)
      continue
    }
    // 标记为内置插件
    const finalManifest: CxFrontendPluginManifest = {
      ...manifest,
      type: 'frontend-plugin',
      builtin: true,
    }
    // 计算入口模块路径（与 manifest.json 同目录的 index.ts）
    const modulePath = path.replace(/manifest\.json$/, 'index.ts')
    const hasModule = modulePath in pluginModuleLoaders
    if (!hasModule) {
      logger.warn(`Plugin [${finalManifest.id}] has no entry module at ${modulePath}, skipping`)
      continue
    }
    if (_instances[finalManifest.id]) {
      logger.warn(`Duplicate plugin id: ${finalManifest.id}, skipping ${path}`)
      continue
    }
    _instances[finalManifest.id] = {
      manifest: finalManifest,
      modulePath,
      status: 'discovered',
      registeredViewIds: [],
      registeredCommandIds: [],
      registeredThemeIds: [],
    }
    logger.debug(`Discovered builtin plugin: ${finalManifest.id} v${finalManifest.version}`)
  }
}

// ---------------------------------------------------------------------------
// 配置读写（每个插件独立 namespace）
// ---------------------------------------------------------------------------

const configKey = (pluginId: string, key: string) => `cx_plugin_config:${pluginId}:${key}`

const getPluginConfig = <T = unknown>(pluginId: string, key: string, defaultValue?: T): T => {
  try {
    const raw = localStorage.getItem(configKey(pluginId, key))
    if (raw === null) return defaultValue as T
    return JSON.parse(raw) as T
  } catch {
    return defaultValue as T
  }
}

const setPluginConfig = (pluginId: string, key: string, value: unknown): void => {
  try {
    localStorage.setItem(configKey(pluginId, key), JSON.stringify(value))
  } catch (e) {
    logger.warn(`Failed to persist config for plugin [${pluginId}]:`, e)
  }
}

// ---------------------------------------------------------------------------
// 创建插件上下文
// ---------------------------------------------------------------------------

const createPluginContext = (instance: CxFrontendPluginInstance): CxPluginContext => {
  const { manifest } = instance
  const pluginLogger = createLuomiNestRendererLogger(`CxPlugin:${manifest.id}`)

  const context: CxPluginContext = {
    pluginId: manifest.id,
    manifest,
    getConfig: <T = unknown>(key: string, defaultValue?: T): T => {
      // 1. 用户写入的配置优先
      const userVal = getPluginConfig<T>(manifest.id, key, defaultValue as T)
      if (userVal !== undefined) return userVal
      // 2. manifest.settings 声明的默认值
      const settingDecl = manifest.settings?.[key]
      if (settingDecl?.default !== undefined) return settingDecl.default as T
      return defaultValue as T
    },
    setConfig: (key: string, value: unknown): void => {
      setPluginConfig(manifest.id, key, value)
    },
    registerView: (view: CxViewContribution): void => {
      cxContributionRegistry.registerView(manifest.id, view)
      if (!instance.registeredViewIds.includes(view.name)) {
        instance.registeredViewIds.push(view.name)
      }
      pluginLogger.debug(`View registered: ${view.name} -> ${view.path}`)
    },
    registerCommand: (command: CxCommandContribution): void => {
      cxContributionRegistry.registerCommand(manifest.id, command)
      if (!instance.registeredCommandIds.includes(command.id)) {
        instance.registeredCommandIds.push(command.id)
      }
      pluginLogger.debug(`Command registered: ${command.id}`)
    },
    registerTheme: (theme: CxThemeContribution): void => {
      cxContributionRegistry.registerTheme(manifest.id, theme)
      if (!instance.registeredThemeIds.includes(theme.id)) {
        instance.registeredThemeIds.push(theme.id)
      }
      pluginLogger.debug(`Theme registered: ${theme.id}`)
    },
    getLogger: () => pluginLogger,
  }
  return context
}

// ---------------------------------------------------------------------------
// 激活/停用
// ---------------------------------------------------------------------------

async function activatePlugin(pluginId: string): Promise<boolean> {
  const instance = _instances[pluginId]
  if (!instance) {
    logger.warn(`Cannot activate: plugin not found: ${pluginId}`)
    return false
  }
  if (instance.status === 'active') {
    logger.debug(`Plugin already active: ${pluginId}`)
    return true
  }
  if (instance.status === 'error') {
    logger.warn(`Cannot activate errored plugin: ${pluginId}, deactivate first`)
    return false
  }

  try {
    // 懒加载入口模块
    const loader = pluginModuleLoaders[instance.modulePath]
    if (!loader) {
      throw new Error(`Entry module not found: ${instance.modulePath}`)
    }
    const mod = await loader()
    if (!mod || typeof mod.activate !== 'function') {
      throw new Error('Entry module missing activate() function')
    }
    _modules.set(pluginId, mod)

    const context = createPluginContext(instance)
    await mod.activate(context)

    instance.status = 'active'
    instance.activatedAt = new Date().toISOString()
    instance.errorMessage = undefined
    logger.info(`Plugin activated: ${pluginId} v${instance.manifest.version}`)
    return true
  } catch (e) {
    instance.status = 'error'
    instance.errorMessage = e instanceof Error ? e.message : String(e)
    logger.error(`Failed to activate plugin [${pluginId}]:`, e)
    // 清理可能已注册的部分贡献点
    cxContributionRegistry.unregisterAllByPlugin(pluginId)
    instance.registeredViewIds = []
    instance.registeredCommandIds = []
    instance.registeredThemeIds = []
    return false
  }
}

async function deactivatePlugin(pluginId: string): Promise<boolean> {
  const instance = _instances[pluginId]
  if (!instance) {
    logger.warn(`Cannot deactivate: plugin not found: ${pluginId}`)
    return false
  }
  if (instance.status !== 'active' && instance.status !== 'error') {
    logger.debug(`Plugin not active: ${pluginId} (status=${instance.status})`)
    return true
  }

  // 调用模块的 deactivate（如果提供）
  const mod = _modules.get(pluginId)
  if (mod?.deactivate) {
    try {
      await mod.deactivate()
    } catch (e) {
      logger.warn(`Plugin [${pluginId}] deactivate() threw:`, e)
    }
  }

  // 清理所有贡献点
  cxContributionRegistry.unregisterAllByPlugin(pluginId)
  instance.registeredViewIds = []
  instance.registeredCommandIds = []
  instance.registeredThemeIds = []

  instance.status = 'inactive'
  instance.activatedAt = undefined
  _modules.delete(pluginId)
  logger.info(`Plugin deactivated: ${pluginId}`)
  return true
}

// ---------------------------------------------------------------------------
// 启用/禁用（带持久化）
// ---------------------------------------------------------------------------

async function enablePlugin(pluginId: string): Promise<boolean> {
  _disabledIds.delete(pluginId)
  persistDisabledIds(_disabledIds)
  return activatePlugin(pluginId)
}

async function disablePlugin(pluginId: string): Promise<boolean> {
  _disabledIds.add(pluginId)
  persistDisabledIds(_disabledIds)
  return deactivatePlugin(pluginId)
}

const isDisabled = (pluginId: string): boolean => _disabledIds.has(pluginId)

// ---------------------------------------------------------------------------
// 初始化（应用启动时调用）
// ---------------------------------------------------------------------------

let _initialized = false

async function init(): Promise<{ total: number; active: number }> {
  if (_initialized) {
    logger.debug('Loader already initialized')
    return { total: 0, active: 0 }
  }
  _initialized = true

  discoverBuiltinPlugins()

  // 激活所有未被禁用的插件
  const ids = Object.keys(_instances)
  let activeCount = 0
  for (const id of ids) {
    if (!_disabledIds.has(id)) {
      const ok = await activatePlugin(id)
      if (ok) activeCount++
    } else {
      // 显式标记为 inactive
      _instances[id].status = 'inactive'
      logger.debug(`Plugin [${id}] skipped (disabled by user)`)
    }
  }

  logger.info(`Initialized: ${ids.length} discovered, ${activeCount} active`)
  return { total: ids.length, active: activeCount }
}

// ---------------------------------------------------------------------------
// 查询 API
// ---------------------------------------------------------------------------

const listPlugins = (): CxFrontendPluginInstance[] => Object.values(_instances)

const getPlugin = (pluginId: string): CxFrontendPluginInstance | undefined => _instances[pluginId]

const getStats = () => {
  const all = Object.values(_instances)
  return {
    total: all.length,
    active: all.filter((p) => p.status === 'active').length,
    inactive: all.filter((p) => p.status === 'inactive').length,
    error: all.filter((p) => p.status === 'error').length,
    disabled: _disabledIds.size,
  }
}

export const cxFrontendPluginLoader = {
  init,
  activatePlugin,
  deactivatePlugin,
  enablePlugin,
  disablePlugin,
  isDisabled,
  listPlugins,
  getPlugin,
  getStats,
  /** 内部注册表（只读视图，供 UI 响应式订阅） */
  instances: _instances,
}

export type CxFrontendPluginLoader = typeof cxFrontendPluginLoader
