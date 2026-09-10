/**
 * LuomiNest 背景预设定义
 * 参照 Cyrene-Agent 多层氛围背景理念，提供渐变/图案/图片三类预设。
 * value 字段直接作为 CSS background-image 或 background 使用。
 *
 * name 使用 getter 惰性求值（经 i18n.global.t），随语言切换实时翻译。
 */
import { i18n } from '../i18n'

export type BackgroundPresetType = 'gradient' | 'pattern' | 'image'

export interface BackgroundPreset {
  id: string
  name: string
  type: BackgroundPresetType
  /** CSS background-image 值（gradient/url）或完整 background 简写（pattern） */
  value: string
  /** 缩略图用 CSS 背景值；省略时复用 value */
  thumb?: string
}

/** 预设背景列表 */
export const BACKGROUND_PRESETS: BackgroundPreset[] = [
  { id: 'none', get name() { return i18n.global.t('theme.backgrounds.none') }, type: 'gradient', value: '' },
  {
    id: 'blue',
    get name() { return i18n.global.t('theme.backgrounds.blue') },
    type: 'gradient',
    value: 'linear-gradient(135deg, #147EBC 0%, #5BA4D4 50%, #0d5f8a 100%)'
  },
  {
    id: 'purple',
    get name() { return i18n.global.t('theme.backgrounds.purple') },
    type: 'gradient',
    value: 'linear-gradient(135deg, #7C3AED 0%, #A78BFA 50%, #5B21B6 100%)'
  },
  {
    id: 'red',
    get name() { return i18n.global.t('theme.backgrounds.red') },
    type: 'gradient',
    value: 'linear-gradient(135deg, #C0392B 0%, #E74C3C 50%, #922B21 100%)'
  },
  {
    id: 'green',
    get name() { return i18n.global.t('theme.backgrounds.green') },
    type: 'gradient',
    value: 'linear-gradient(135deg, #059669 0%, #34D399 50%, #047857 100%)'
  },
  {
    id: 'orange',
    get name() { return i18n.global.t('theme.backgrounds.orange') },
    type: 'gradient',
    value: 'linear-gradient(135deg, #EA580C 0%, #FB923C 50%, #C2410C 100%)'
  },
  {
    id: 'dream-pink',
    get name() { return i18n.global.t('theme.backgrounds.dreamPink') },
    type: 'gradient',
    value: 'linear-gradient(135deg, #ec4899 0%, #9f7aea 100%)'
  },
  {
    id: 'dream-pink-hot',
    get name() { return i18n.global.t('theme.backgrounds.dreamPinkHot') },
    type: 'gradient',
    value: 'linear-gradient(135deg, #ff6ec7 0%, #ec4899 50%, #9f7aea 100%)'
  },
  {
    id: 'deep-space',
    get name() { return i18n.global.t('theme.backgrounds.deepSpace') },
    type: 'gradient',
    value: 'radial-gradient(ellipse at top, #181432 0%, #08070f 60%)'
  },
  {
    id: 'ocean',
    get name() { return i18n.global.t('theme.backgrounds.ocean') },
    type: 'gradient',
    value: 'linear-gradient(135deg, #0ea5e9 0%, #06b6d4 50%, #0891b2 100%)'
  },
  {
    id: 'sunset',
    get name() { return i18n.global.t('theme.backgrounds.sunset') },
    type: 'gradient',
    value: 'linear-gradient(135deg, #f59e0b 0%, #f43f5e 50%, #0ea5e9 100%)'
  },
  {
    id: 'aurora',
    get name() { return i18n.global.t('theme.backgrounds.aurora') },
    type: 'gradient',
    value: 'linear-gradient(135deg, #10b981 0%, #3b82f6 50%, #0ea5e9 100%)'
  },
  {
    id: 'dots',
    get name() { return i18n.global.t('theme.backgrounds.dots') },
    type: 'pattern',
    value:
      'radial-gradient(circle, color-mix(in srgb, var(--lumi-primary) 20%, transparent) 1.5px, transparent 1.5px)',
    thumb: 'radial-gradient(circle, var(--lumi-primary) 1.5px, transparent 1.5px)'
  },
  {
    id: 'grid',
    get name() { return i18n.global.t('theme.backgrounds.grid') },
    type: 'pattern',
    value:
      'linear-gradient(to right, color-mix(in srgb, var(--lumi-primary) 12%, transparent) 1px, transparent 1px), linear-gradient(to bottom, color-mix(in srgb, var(--lumi-primary) 12%, transparent) 1px, transparent 1px)',
    thumb:
      'linear-gradient(to right, var(--lumi-primary) 1px, transparent 1px), linear-gradient(to bottom, var(--lumi-primary) 1px, transparent 1px)'
  }
]

/** 根据 value 查找预设 ID，未找到返回 'custom' */
export const findPresetIdByValue = (value: string | null): string => {
  if (!value) return 'none'
  return BACKGROUND_PRESETS.find((p) => p.value === value)?.id ?? 'custom'
}

/** 根据 ID 查找预设 */
export const findPresetById = (id: string): BackgroundPreset | undefined =>
  BACKGROUND_PRESETS.find((p) => p.id === id)
