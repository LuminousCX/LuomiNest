/**
 * LuomiNest 背景预设定义
 * 参照 Cyrene-Agent 多层氛围背景理念，提供渐变/图案/图片三类预设。
 * value 字段直接作为 CSS background-image 或 background 使用。
 */

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
  { id: 'none', name: '无', type: 'gradient', value: '' },
  {
    id: 'blue',
    name: '辰汐蓝',
    type: 'gradient',
    value: 'linear-gradient(135deg, #147EBC 0%, #5BA4D4 50%, #0d5f8a 100%)'
  },
  {
    id: 'purple',
    name: '紫罗兰',
    type: 'gradient',
    value: 'linear-gradient(135deg, #7C3AED 0%, #A78BFA 50%, #5B21B6 100%)'
  },
  {
    id: 'red',
    name: '中国红',
    type: 'gradient',
    value: 'linear-gradient(135deg, #C0392B 0%, #E74C3C 50%, #922B21 100%)'
  },
  {
    id: 'green',
    name: '翡翠绿',
    type: 'gradient',
    value: 'linear-gradient(135deg, #059669 0%, #34D399 50%, #047857 100%)'
  },
  {
    id: 'orange',
    name: '暖橘橙',
    type: 'gradient',
    value: 'linear-gradient(135deg, #EA580C 0%, #FB923C 50%, #C2410C 100%)'
  },
  {
    id: 'dream-pink',
    name: '梦幻粉',
    type: 'gradient',
    value: 'linear-gradient(135deg, #ec4899 0%, #9f7aea 100%)'
  },
  {
    id: 'dream-pink-hot',
    name: '霓虹粉',
    type: 'gradient',
    value: 'linear-gradient(135deg, #ff6ec7 0%, #ec4899 50%, #9f7aea 100%)'
  },
  {
    id: 'deep-space',
    name: '深空',
    type: 'gradient',
    value: 'radial-gradient(ellipse at top, #181432 0%, #08070f 60%)'
  },
  {
    id: 'ocean',
    name: '海洋',
    type: 'gradient',
    value: 'linear-gradient(135deg, #0ea5e9 0%, #06b6d4 50%, #0891b2 100%)'
  },
  {
    id: 'sunset',
    name: '落日',
    type: 'gradient',
    value: 'linear-gradient(135deg, #f59e0b 0%, #f43f5e 50%, #0ea5e9 100%)'
  },
  {
    id: 'aurora',
    name: '极光',
    type: 'gradient',
    value: 'linear-gradient(135deg, #10b981 0%, #3b82f6 50%, #0ea5e9 100%)'
  },
  {
    id: 'dots',
    name: '网点',
    type: 'pattern',
    value:
      'radial-gradient(circle, color-mix(in srgb, var(--lumi-primary) 20%, transparent) 1.5px, transparent 1.5px)',
    thumb: 'radial-gradient(circle, var(--lumi-primary) 1.5px, transparent 1.5px)'
  },
  {
    id: 'grid',
    name: '网格',
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
