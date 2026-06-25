import type { Component } from 'vue'
import type { LuomiNestModelInfo } from '@/config/luominest-models'

export interface AvatarMode {
  id: string
  label: string
  desc: string
  active: boolean
}

export interface AvatarEmotion {
  id: string
  icon: Component
  label: string
  color: string
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
