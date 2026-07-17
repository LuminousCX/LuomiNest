/**
 * CxFrontendPlugin 类型定义 — LuomiNest 前端插件系统数据契约。
 *
 * 设计与后端 backend/app/models/plugin.py 对齐，使用 Cx 前缀（LuminousChenXi 品牌）。
 * 本模块定义前端插件系统的核心数据结构：
 * - 枚举：CxFrontendPluginStatus / CxFrontendPluginCategory / CxPermission
 * - Manifest：CxFrontendPluginManifest（含贡献点声明）
 * - 贡献点：CxViewContribution / CxCommandContribution / CxThemeContribution
 * - 运行时：CxFrontendPluginInstance / CxPluginContext
 *
 * 与后端的差异：
 * - 前端插件不涉及 NETWORK/FILE_SYSTEM/SYSTEM_COMMAND 等后端权限
 * - 前端插件核心能力是"贡献点"（contributions）— 向 UI 注入视图、命令、主题
 * - 前端插件通过 import.meta.glob 在构建时发现，运行时激活
 */

import type { Component } from 'vue'

// ---------------------------------------------------------------------------
// 状态与枚举
// ---------------------------------------------------------------------------

export type CxFrontendPluginStatus =
  | 'discovered'    // 已发现（manifest 解析成功）
  | 'active'        // 已激活（activate() 执行成功）
  | 'inactive'      // 已停用（deactivate() 执行成功，或用户手动禁用）
  | 'error'         // 激活失败

export type CxFrontendPluginCategory =
  | 'ui'            // UI 增强（视图、面板）
  | 'theme'         // 主题/外观
  | 'integration'   // 第三方服务集成（前端侧）
  | 'tool'          // 工具/能力扩展
  | 'automation'    // 自动化规则

/**
 * 前端插件可用权限（子集，仅限前端安全范围内）。
 * 后端敏感权限（NETWORK/FILE_SYSTEM/SYSTEM_COMMAND）不暴露给前端插件。
 */
export type CxPermission =
  | 'basic'         // 基础运行能力（默认授予）
  | 'clipboard'     // 访问剪贴板
  | 'notification'  // 显示系统通知
  | 'storage'       // 本地存储访问（localStorage / IndexedDB）
  | 'ipc'           // 受限 IPC 调用（白名单通道）

// ---------------------------------------------------------------------------
// Manifest 数据模型
// ---------------------------------------------------------------------------

export interface CxPluginDependencies {
  /** 最低应用版本（语义化版本号，如 "0.7.6"） */
  appVersion?: string
  /** 依赖的其他插件 ID 列表 */
  plugins?: string[]
}

/**
 * 配置项声明 — 供插件管理 UI 渲染配置表单。
 * 与后端 backend/app/models/plugin.py 中 settings 字段对齐。
 */
export interface CxSettingDeclaration {
  type: 'string' | 'number' | 'boolean' | 'select' | 'color'
  label?: string
  description?: string
  default?: unknown
  options?: Array<{ label: string; value: string | number }>
  min?: number
  max?: number
  step?: number
}

export interface CxFrontendPluginManifest {
  /** 插件 ID（kebab-case，全局唯一） */
  id: string
  /** 类型标识，固定为 'frontend-plugin' */
  type: 'frontend-plugin'
  /** 显示名称 */
  name: string
  /** 语义化版本号 */
  version: string
  description: string
  author: string
  license?: string
  /** 主页/仓库 URL */
  homepage?: string
  /** Lucide 图标名（用于设置面板展示） */
  icon?: string
  category: CxFrontendPluginCategory
  tags?: string[]
  /** 最低兼容应用版本 */
  minAppVersion?: string
  /** 入口模块相对路径（默认 'index'，对应 index.ts） */
  entry?: string
  /** 权限声明 */
  permissions?: CxPermission[]
  /** 依赖声明 */
  dependencies?: CxPluginDependencies
  /** 配置项声明（UI 渲染表单） */
  settings?: Record<string, CxSettingDeclaration>
  /** 贡献点声明（静态声明，供 loader 预解析） */
  contributes?: CxContributesDeclaration
  /** 是否为内置插件（内置插件不可卸载） */
  builtin?: boolean
}

// ---------------------------------------------------------------------------
// 贡献点（Contributions）— 插件向 UI 注入能力的方式
// ---------------------------------------------------------------------------

/**
 * 视图贡献点 — 向路由表注入一个页面。
 * 插件通过此贡献点添加自定义页面到应用中。
 */
export interface CxViewContribution {
  /** 路由路径（如 'my-plugin/panel'，会被 loader 加前缀 '/plugins/{id}/'） */
  path: string
  /** 路由名称（全局唯一，loader 会自动加前缀避免冲突） */
  name: string
  /** 路由 meta.title，用于页面标题与侧边栏显示 */
  title: string
  /** Lucide 图标名（侧边栏展示） */
  icon?: string
  /** 是否在侧边栏显示入口（默认 true） */
  showInSidebar?: boolean
  /** 侧边栏分组（与现有 SidebarNav 分组对齐） */
  sidebarGroup?: 'top' | 'middle' | 'bottom'
  /** Vue 组件（由 loader 通过动态 import 注入） */
  component?: Component
  /** 组件模块相对路径（loader 解析为动态 import） */
  componentPath?: string
}

/**
 * 命令贡献点 — 注册一个可被全局调用的命令。
 * 命令可通过命令面板（Ctrl+Shift+P）或代码触发。
 */
export interface CxCommandContribution {
  /** 命令 ID（全局唯一，loader 自动加插件 ID 前缀） */
  id: string
  /** 显示名称 */
  title: string
  /** 快捷键（Electron accelerator 格式，如 'CmdOrCtrl+Shift+P'） */
  keybinding?: string
  /** 命令处理函数（由插件入口模块提供） */
  handler?: (...args: unknown[]) => unknown
}

/**
 * 主题贡献点 — 注册一组 CSS 变量覆盖。
 * 用户可在设置中切换到插件提供的主题。
 */
export interface CxThemeContribution {
  /** 主题 ID（全局唯一） */
  id: string
  /** 显示名称 */
  name: string
  /** 是否深色主题 */
  isDark?: boolean
  /** CSS 变量键值对（注入到 :root[data-theme="{id}"]） */
  variables: Record<string, string>
}

/**
 * Manifest 中的静态贡献点声明。
 * 每个贡献点可声明 path/name/title 等"静态字段"，
 * 实际的组件/处理函数由插件入口模块在 activate() 时动态注册。
 */
export interface CxContributesDeclaration {
  views?: Array<Omit<CxViewContribution, 'component' | 'componentPath'>>
  commands?: Array<Omit<CxCommandContribution, 'handler'>>
  themes?: CxThemeContribution[]
}

// ---------------------------------------------------------------------------
// 运行时类型
// ---------------------------------------------------------------------------

/**
 * 插件入口模块接口 — 每个前端插件的 index.ts 必须实现。
 * 设计参考了 VSCode 扩展 API 的 activate/deactivate 模式，但实现为原创。
 */
export interface CxPluginModule {
  /**
   * 插件激活时调用 — 注册贡献点、初始化资源。
   * @param context 插件运行时上下文，提供 registerView/registerCommand/registerTheme 等 API
   */
  activate: (context: CxPluginContext) => void | Promise<void>
  /**
   * 插件停用时调用 — 清理资源、注销贡献点。
   * 必须确保所有副作用都可逆。
   */
  deactivate?: () => void | Promise<void>
}

/**
 * 插件运行时上下文 — 暴露给插件使用的 API 接口。
 * 由 loader 在激活插件时创建并传入 activate()。
 */
export interface CxPluginContext {
  /** 插件 ID */
  pluginId: string
  /** 插件 manifest */
  manifest: CxFrontendPluginManifest
  /** 读取插件配置项（合并默认值与用户设置） */
  getConfig: <T = unknown>(key: string, defaultValue?: T) => T
  /** 写入插件配置项（持久化到 localStorage） */
  setConfig: (key: string, value: unknown) => void
  /** 注册视图贡献点 */
  registerView: (view: CxViewContribution) => void
  /** 注册命令贡献点 */
  registerCommand: (command: CxCommandContribution) => void
  /** 注册主题贡献点 */
  registerTheme: (theme: CxThemeContribution) => void
  /** 获取插件专属 logger */
  getLogger: () => {
    debug: (...args: unknown[]) => void
    info: (...args: unknown[]) => void
    warn: (...args: unknown[]) => void
    error: (...args: unknown[]) => void
  }
}

/**
 * 前端插件运行时实例 — loader 注册表中存储的条目。
 */
export interface CxFrontendPluginInstance {
  manifest: CxFrontendPluginManifest
  /** 入口模块相对路径 */
  modulePath: string
  status: CxFrontendPluginStatus
  /** 激活时间戳（ISO 字符串） */
  activatedAt?: string
  /** 错误信息（status === 'error' 时） */
  errorMessage?: string
  /** 已注册的贡献点 ID 列表（用于停用时清理） */
  registeredViewIds: string[]
  registeredCommandIds: string[]
  registeredThemeIds: string[]
}

// ---------------------------------------------------------------------------
// 后端插件/技能 API 响应类型（与 backend/app/api/v1/endpoints/plugin.py 对齐）
// ---------------------------------------------------------------------------

/** 后端 ApiResponse 包装格式 */
export interface CxApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

/** 后端插件状态（与 CxPluginStatus 对齐） */
export type CxBackendPluginStatus = 'loaded' | 'enabled' | 'disabled' | 'error' | 'unloaded'

/** 后端插件元数据（API 响应） */
export interface CxBackendPlugin {
  id: string
  type: string
  name: string
  version: string
  description: string
  author: string
  entry: string
  minAppVersion: string
  capabilities: string[]
  permissions: string[]
  icon: string
  category: string
  tags: string[]
  license: string
  platform: string
  dependencies: Record<string, unknown>
  settings: Record<string, CxSettingDeclaration>
  hooks: Record<string, string>
  status: CxBackendPluginStatus
  loaded_at: string
  error_message: string
  reserved: boolean
  is_active: boolean
}

/** 后端技能状态（与 SkillStatus 对齐） */
export type CxSkillStatus = 'active' | 'disabled' | 'error'

/** 后端技能元数据（API 响应） */
export interface CxBackendSkill {
  id: string
  name: string
  description: string
  summary?: string
  version: string
  author?: string
  license?: string
  icon?: string
  category?: string
  tags?: string[]
  status: CxSkillStatus
  is_active: boolean
  source_format?: string
  trigger_keywords?: string[]
  body?: string
  manifest_path?: string
}

/** 插件系统统计信息 */
export interface CxPluginStats {
  total: number
  active: number
  disabled: number
  disabled_ids: string[]
}

/** 技能系统统计信息 */
export interface CxSkillStats {
  total: number
  active: number
  disabled: number
  disabled_ids: string[]
}

// ---------------------------------------------------------------------------
// Skill 写入 / 校验 / 删除（与 backend/app/api/v1/endpoints/plugin.py 对齐）
// ---------------------------------------------------------------------------

/** POST /skills/write 响应 */
export interface CxSkillWriteResult {
  skill_id: string
  path: string
  created: boolean
  loaded: boolean
}

/** POST /skills/delete 响应 */
export interface CxSkillDeleteResult {
  skill_id: string
  deleted: boolean
}

/** POST /skills/validate 响应 */
export interface CxSkillValidateResult {
  valid: boolean
  errors: string[]
  frontmatter: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// PluginConfigAssistant 类型（与 backend/app/services/plugin_config_assistant.py 对齐）
// ---------------------------------------------------------------------------

/** 配置 patch 操作类型 */
export type CxSettingPatchOp = 'set' | 'remove' | 'reset'

/** 单个配置 patch */
export interface CxSettingPatch {
  op: CxSettingPatchOp
  key: string
  value?: unknown
  reason?: string
  validation_error?: string
}

/** LLM 配置建议 */
export interface CxConfigSuggestion {
  plugin_id: string
  user_request: string
  patches: CxSettingPatch[]
  summary: string
  confidence: number
  created_at: string
}

/** 应用配置 patch 结果 */
export interface CxConfigApplyResult {
  plugin_id: string
  applied: number
  skipped: number
  errors: string[]
  config: Record<string, unknown>
}

/** 插件当前配置（合并 manifest 默认值与 KV 存储值） */
export interface CxPluginConfigResult {
  plugin_id: string
  /** 当前生效配置（manifest 默认值 + KV 存储值合并） */
  settings: Record<string, unknown>
  /** manifest 中声明的配置项定义（含 type/default/description 等） */
  declarations: Record<string, unknown>
}

/** 配置重置结果（与 CxPluginConfigResult 结构一致，重置后返回最新配置） */
export interface CxPluginConfigResetResult {
  plugin_id: string
  settings: Record<string, unknown>
  declarations: Record<string, unknown>
}

/** LLM 配置解释 */
export interface CxPluginConfigExplain {
  plugin_id: string
  explanation: string
  settings?: Array<{
    key: string
    label: string
    current_value: unknown
    description: string
  }>
}

/** 脚手架生成结果 */
export interface CxPluginScaffold {
  plugin_id: string
  name: string
  description: string
  files: Record<string, string>
  created_at: string
  notes: string[]
}

/** 脚手架写入磁盘结果 */
export interface CxPluginScaffoldWriteResult {
  plugin_id: string
  path: string
  files_written: number
}

export {}
