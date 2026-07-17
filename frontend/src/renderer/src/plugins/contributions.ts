/**
 * CxContributionRegistry — 前端插件贡献点注册中心。
 *
 * 设计为单一全局响应式注册表，所有插件注册的视图/命令/主题都集中管理。
 * 使用 Vue reactive 系统，组件可直接订阅 pluginViews/pluginCommands/pluginThemes。
 *
 * 命名空间策略：
 * - 视图路由 name 加前缀 `plugin:{pluginId}:` 避免与现有路由冲突
 * - 视图路由 path 统一挂载到 `/plugins/{pluginId}/{path}` 下
 * - 命令 id 加前缀 `{pluginId}.` 避免冲突
 * - 主题 id 加前缀 `plugin-{pluginId}-` 避免冲突
 *
 * 所有注册项都记录所属 pluginId，便于插件停用时批量清理。
 */

import { computed, reactive, readonly } from 'vue'
import type { RouteRecordRaw } from 'vue-router'
import type {
  CxViewContribution,
  CxCommandContribution,
  CxThemeContribution,
} from './types'

// ---------------------------------------------------------------------------
// 内部状态
// ---------------------------------------------------------------------------

interface CxViewRegistryEntry extends CxViewContribution {
  /** 所属插件 ID（由 loader 注入） */
  pluginId: string
  /** 完整路由路径（loader 计算后注入） */
  fullPath: string
  /** 完整路由 name（loader 计算后注入） */
  fullName: string
}

interface CxCommandRegistryEntry extends CxCommandContribution {
  pluginId: string
  fullId: string
}

interface CxThemeRegistryEntry extends CxThemeContribution {
  pluginId: string
  fullId: string
}

const _views = reactive<CxViewRegistryEntry[]>([])
const _commands = reactive<CxCommandRegistryEntry[]>([])
const _themes = reactive<CxThemeRegistryEntry[]>([])

// ---------------------------------------------------------------------------
// 内部辅助：命名空间前缀计算
// ---------------------------------------------------------------------------

const viewFullName = (pluginId: string, name: string) => `plugin:${pluginId}:${name}`
const viewFullPath = (pluginId: string, path: string) => {
  // path 可能以 / 开头或不开头，统一处理
  const cleanPath = path.replace(/^\/+/, '')
  return `/plugins/${pluginId}/${cleanPath}`
}
const commandFullId = (pluginId: string, id: string) => `${pluginId}.${id}`
const themeFullId = (pluginId: string, id: string) => `plugin-${pluginId}-${id}`

// ---------------------------------------------------------------------------
// 注册/注销 API（由 CxPluginContext 调用，loader 间接暴露）
// ---------------------------------------------------------------------------

function registerView(pluginId: string, view: CxViewContribution): CxViewRegistryEntry {
  // 去重：同一插件下同名视图直接覆盖
  const existingIdx = _views.findIndex(
    (v) => v.pluginId === pluginId && v.name === view.name
  )
  const entry: CxViewRegistryEntry = {
    ...view,
    pluginId,
    fullPath: viewFullPath(pluginId, view.path),
    fullName: viewFullName(pluginId, view.name),
  }
  if (existingIdx >= 0) {
    _views[existingIdx] = entry
  } else {
    _views.push(entry)
  }
  return entry
}

function unregisterView(pluginId: string, name: string): void {
  const idx = _views.findIndex(
    (v) => v.pluginId === pluginId && v.name === name
  )
  if (idx >= 0) _views.splice(idx, 1)
}

function unregisterAllViews(pluginId: string): void {
  for (let i = _views.length - 1; i >= 0; i--) {
    if (_views[i].pluginId === pluginId) _views.splice(i, 1)
  }
}

function registerCommand(pluginId: string, command: CxCommandContribution): CxCommandRegistryEntry {
  const existingIdx = _commands.findIndex(
    (c) => c.pluginId === pluginId && c.id === command.id
  )
  const entry: CxCommandRegistryEntry = {
    ...command,
    pluginId,
    fullId: commandFullId(pluginId, command.id),
  }
  if (existingIdx >= 0) {
    _commands[existingIdx] = entry
  } else {
    _commands.push(entry)
  }
  return entry
}

function unregisterCommand(pluginId: string, id: string): void {
  const idx = _commands.findIndex(
    (c) => c.pluginId === pluginId && c.id === id
  )
  if (idx >= 0) _commands.splice(idx, 1)
}

function unregisterAllCommands(pluginId: string): void {
  for (let i = _commands.length - 1; i >= 0; i--) {
    if (_commands[i].pluginId === pluginId) _commands.splice(i, 1)
  }
}

function registerTheme(pluginId: string, theme: CxThemeContribution): CxThemeRegistryEntry {
  const existingIdx = _themes.findIndex(
    (t) => t.pluginId === pluginId && t.id === theme.id
  )
  const entry: CxThemeRegistryEntry = {
    ...theme,
    pluginId,
    fullId: themeFullId(pluginId, theme.id),
  }
  if (existingIdx >= 0) {
    _themes[existingIdx] = entry
  } else {
    _themes.push(entry)
  }
  return entry
}

function unregisterTheme(pluginId: string, id: string): void {
  const idx = _themes.findIndex(
    (t) => t.pluginId === pluginId && t.id === id
  )
  if (idx >= 0) _themes.splice(idx, 1)
}

function unregisterAllThemes(pluginId: string): void {
  for (let i = _themes.length - 1; i >= 0; i--) {
    if (_themes[i].pluginId === pluginId) _themes.splice(i, 1)
  }
}

/** 注销指定插件的所有贡献点（停用/卸载时调用） */
function unregisterAllByPlugin(pluginId: string): void {
  unregisterAllViews(pluginId)
  unregisterAllCommands(pluginId)
  unregisterAllThemes(pluginId)
}

// ---------------------------------------------------------------------------
// 查询 API（供组件消费）
// ---------------------------------------------------------------------------

/** 所有已注册的插件视图（只读响应式） */
const pluginViews = readonly(_views)

/** 所有已注册的插件命令（只读响应式） */
const pluginCommands = readonly(_commands)

/** 所有已注册的插件主题（只读响应式） */
const pluginThemes = readonly(_themes)

/** 获取应在侧边栏显示的插件视图（响应式 computed） */
const sidebarPluginViews = computed(() =>
  readonly(_views.filter((v) => v.showInSidebar !== false))
)

/** 按命令 fullId 执行命令 */
function executeCommand(fullId: string, ...args: unknown[]): unknown {
  const entry = _commands.find((c) => c.fullId === fullId)
  if (!entry?.handler) {
    console.warn(`[CxContribution] Command not found or no handler: ${fullId}`)
    return undefined
  }
  return entry.handler(...args)
}

/** 将插件视图转换为 vue-router RouteRecordRaw（供 router.addRoute 使用） */
function viewEntryToRoute(entry: CxViewRegistryEntry): RouteRecordRaw {
  return {
    path: entry.fullPath,
    name: entry.fullName,
    component: entry.component as never,
    meta: {
      title: `${entry.title} - LuomiNest`,
      icon: entry.icon,
      pluginView: true,
      pluginId: entry.pluginId,
    },
  }
}

/** 获取所有插件视图对应的路由记录 */
function getAllViewRoutes(): RouteRecordRaw[] {
  return _views
    .filter((v) => v.component)
    .map(viewEntryToRoute)
}

export const cxContributionRegistry = {
  // 注册/注销
  registerView,
  unregisterView,
  unregisterAllViews,
  registerCommand,
  unregisterCommand,
  unregisterAllCommands,
  registerTheme,
  unregisterTheme,
  unregisterAllThemes,
  unregisterAllByPlugin,
  // 查询
  pluginViews,
  pluginCommands,
  pluginThemes,
  sidebarPluginViews,
  executeCommand,
  getAllViewRoutes,
  viewEntryToRoute,
}

export type CxContributionRegistry = typeof cxContributionRegistry
export type { CxViewRegistryEntry, CxCommandRegistryEntry, CxThemeRegistryEntry }
