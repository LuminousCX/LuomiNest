import type { Component } from 'vue'
import type { LuomiNestModelInfo } from '@/config/luominest-models'
import type { AvatarRendererType } from '@/types/avatar'

/**
 * 皮套工坊模式按钮（模型类型切换器）
 *
 * 注意：这里的 `id` 是 AvatarRendererType（live2d/vrm/pixel/spine/png），
 * 不是单个模型的 ID。切换模式 = 切换渲染器类型。
 */
export interface AvatarMode {
  id: AvatarRendererType
  label: string
  desc: string
  /** 是否已实现（未实现的禁用切换） */
  implemented: boolean
}

// 模型原生表情（从 model3.json 的 FileReferences.Expressions 动态读取）
// id 即模型原生表情名，点击直接触发该表情
export interface AvatarEmotion {
  id: string
  icon?: Component
  label: string
  color: string
}

// 模型原生动作（从 model3.json 的 FileReferences.Motions 动态读取）
// id 即 motion group 名，点击触发该组第 0 个动作
export interface AvatarMotion {
  id: string
  label: string
}

export interface IdleAnimation {
  name: string
  status: 'running' | 'paused'
  progress: number
}

/**
 * 侧边栏模型卡片项
 *
 * modelInfo 可能为 null（占位卡片），UI 应处理空值。
 */
export interface SkinItem {
  name: string
  /** 显示类型标签（Live2D / VRM / PixelPet 等） */
  type: string
  tags: string[]
  modelInfo: LuomiNestModelInfo | null
}

/**
 * 侧边栏模型卡片项（基于后端 manifest 的新版本）
 *
 * 与 SkinItem 并存：SkinItem 用于兼容旧 IPC 导入的模型，
 * ManifestSkinItem 用于后端 manifest 模型。
 */
export interface ManifestSkinItem {
  id: string
  name: string
  type: AvatarRendererType
  source: 'builtin' | 'imported'
  tags: string[]
  thumbnail?: string | null
  /** 模型能力摘要（用于卡片展示） */
  capabilities: {
    expressionCount: number
    motionCount: number
    stateCount: number
    lipSync: boolean
    focusTracking: boolean
  }
}
