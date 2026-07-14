import type { Component } from 'vue'
import type { LuomiNestModelInfo } from '@/config/luominest-models'

export interface AvatarMode {
  id: string
  label: string
  desc: string
  active: boolean
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

export interface SkinItem {
  name: string
  type: string
  tags: string[]
  modelInfo: LuomiNestModelInfo | null
}
