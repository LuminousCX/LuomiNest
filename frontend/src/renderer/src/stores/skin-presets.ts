import type { Skin } from './theme-types'

/**
 * LuomiNest 皮肤包预设
 * 每套皮肤 = 色彩主题 + 背景 + 毛玻璃/氛围光强度
 * 参考 Codex 的沉浸式设计，提供从极简到情感化的多种氛围
 */
export const presetSkins: Skin[] = [
  // ────────────────────────────────────────────
  // 1. 经典系列：保留现有 5 个纯色主题，无背景
  // ────────────────────────────────────────────
  {
    id: 'skin-classic-blue',
    name: '辰汐蓝',
    type: 'preset',
    colorThemeId: 'blue',
    mode: 'system',
    background: { image: null, blur: 0, opacity: 100, fit: 'cover' },
    glassIntensity: 35,
    ambientIntensity: 30,
    radiusTendency: 50
  },
  {
    id: 'skin-classic-purple',
    name: '紫罗兰',
    type: 'preset',
    colorThemeId: 'purple',
    mode: 'system',
    background: { image: null, blur: 0, opacity: 100, fit: 'cover' },
    glassIntensity: 35,
    ambientIntensity: 30,
    radiusTendency: 50
  },
  {
    id: 'skin-classic-red',
    name: '中国红',
    type: 'preset',
    colorThemeId: 'red',
    mode: 'system',
    background: { image: null, blur: 0, opacity: 100, fit: 'cover' },
    glassIntensity: 35,
    ambientIntensity: 30,
    radiusTendency: 50
  },
  {
    id: 'skin-classic-green',
    name: '翡翠绿',
    type: 'preset',
    colorThemeId: 'green',
    mode: 'system',
    background: { image: null, blur: 0, opacity: 100, fit: 'cover' },
    glassIntensity: 35,
    ambientIntensity: 30,
    radiusTendency: 50
  },
  {
    id: 'skin-classic-orange',
    name: '暖橘橙',
    type: 'preset',
    colorThemeId: 'orange',
    mode: 'system',
    background: { image: null, blur: 0, opacity: 100, fit: 'cover' },
    glassIntensity: 35,
    ambientIntensity: 30,
    radiusTendency: 50
  },

  // ────────────────────────────────────────────
  // 2. Codex 风格情感化皮肤
  // ────────────────────────────────────────────
  {
    id: 'skin-pearl-white',
    name: '珍珠白',
    type: 'preset',
    colorThemeId: 'blue',
    mode: 'light',
    background: {
      image: 'linear-gradient(135deg, #faf9f7 0%, #f2f0ec 50%, #e8e4de 100%)',
      blur: 0,
      opacity: 100,
      fit: 'cover'
    },
    glassIntensity: 55,
    ambientIntensity: 20,
    radiusTendency: 65
  },
  {
    id: 'skin-rose-dream',
    name: '玫瑰梦境',
    type: 'preset',
    colorThemeId: 'purple',
    mode: 'light',
    background: {
      image: 'linear-gradient(135deg, #fdf2f8 0%, #fce7f3 40%, #fbcfe8 100%)',
      blur: 0,
      opacity: 100,
      fit: 'cover'
    },
    glassIntensity: 60,
    ambientIntensity: 35,
    radiusTendency: 70
  },
  {
    id: 'skin-midnight-aurora',
    name: '深夜极光',
    type: 'preset',
    colorThemeId: 'green',
    mode: 'dark',
    background: {
      image: 'radial-gradient(ellipse at 80% 20%, rgba(16, 185, 129, 0.18) 0%, transparent 50%), radial-gradient(ellipse at 20% 80%, rgba(59, 130, 246, 0.14) 0%, transparent 45%), #0a0a0a',
      blur: 0,
      opacity: 100,
      fit: 'cover'
    },
    glassIntensity: 45,
    ambientIntensity: 55,
    radiusTendency: 55
  },
  {
    id: 'skin-soft-sunset',
    name: '柔光落日',
    type: 'preset',
    colorThemeId: 'orange',
    mode: 'system',
    background: {
      image: 'linear-gradient(135deg, #fff7ed 0%, #ffedd5 50%, #fed7aa 100%)',
      blur: 0,
      opacity: 100,
      fit: 'cover'
    },
    glassIntensity: 55,
    ambientIntensity: 40,
    radiusTendency: 65
  },
  {
    id: 'skin-deep-space',
    name: '深空星云',
    type: 'preset',
    colorThemeId: 'blue',
    mode: 'dark',
    background: {
      image: 'radial-gradient(ellipse at 30% 20%, rgba(59, 130, 246, 0.22) 0%, transparent 50%), radial-gradient(ellipse at 70% 80%, rgba(124, 58, 237, 0.18) 0%, transparent 45%), #020617',
      blur: 0,
      opacity: 100,
      fit: 'cover'
    },
    glassIntensity: 40,
    ambientIntensity: 60,
    radiusTendency: 50
  },

  // ────────────────────────────────────────────
  // 3. 动态氛围皮肤（以渐变营造背景）
  // ────────────────────────────────────────────
  {
    id: 'skin-ocean-breeze',
    name: '海风轻拂',
    type: 'preset',
    colorThemeId: 'blue',
    mode: 'light',
    background: {
      image: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 50%, #bae6fd 100%)',
      blur: 0,
      opacity: 100,
      fit: 'cover'
    },
    glassIntensity: 50,
    ambientIntensity: 30,
    radiusTendency: 60
  },
  {
    id: 'skin-sakura-rain',
    name: '樱花雨',
    type: 'preset',
    colorThemeId: 'red',
    mode: 'light',
    background: {
      image: 'linear-gradient(135deg, #fff1f2 0%, #ffe4e6 50%, #fecdd3 100%)',
      blur: 0,
      opacity: 100,
      fit: 'cover'
    },
    glassIntensity: 55,
    ambientIntensity: 35,
    radiusTendency: 70
  },
  {
    id: 'skin-forest-mist',
    name: '林间薄雾',
    type: 'preset',
    colorThemeId: 'green',
    mode: 'dark',
    background: {
      image: 'radial-gradient(ellipse at 50% 0%, rgba(34, 197, 94, 0.14) 0%, transparent 55%), #0c0a09',
      blur: 0,
      opacity: 100,
      fit: 'cover'
    },
    glassIntensity: 45,
    ambientIntensity: 45,
    radiusTendency: 55
  }
]

/** 预设皮肤 ID → 皮肤映射 */
export const presetSkinMap: Record<string, Skin> = Object.fromEntries(
  presetSkins.map((s) => [s.id, s])
)

/** 根据色彩主题 ID 生成默认皮肤 ID */
export function getDefaultSkinIdForColorTheme(colorThemeId: string): string {
  return `skin-classic-${colorThemeId}`
}

/** 查找预设皮肤 */
export function findPresetSkinById(id: string): Skin | undefined {
  return presetSkinMap[id]
}
