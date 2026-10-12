/**
 * PromptBar 的对外类型（独立文件便于宿主/composable 导入，
 * 避免 <script setup> 内导出类型的编译器限制）
 */
import type { Component } from 'vue'

export interface PromptBarModelOption {
  key: string
  name: string
  tag?: string
}

export interface PromptBarAttachmentChip {
  key: string
  name: string
}

/** 加号菜单条目：action 为真实能力；disabled=true 为占位条目（点击提示"即将支持"） */
export interface PromptBarMenuItem {
  key: string
  icon?: Component
  name: string
  description?: string
  disabled?: boolean
  action?: () => void
}

export type PromptBarEffort = 'fast' | 'balanced' | 'max'
