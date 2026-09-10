import type { Skin } from './theme-types'
import { i18n } from '../i18n'

/**
 * LuomiNest 皮肤包预设
 * 每套皮肤 = 色彩主题 + 背景 + 毛玻璃/氛围光强度
 * 参考 Codex 的沉浸式设计，提供从极简到情感化的多种氛围
 *
 * name 使用 getter 惰性求值：每次读取都经过 i18n.global.t，
 * 使消费方（computed / 模板渲染）能随语言切换获得对应翻译。
 */
export const presetSkins: Skin[] = [
  // ────────────────────────────────────────────
  // 1. 经典系列：保留现有 5 个纯色主题，无背景
  // ────────────────────────────────────────────
  {
    id: 'skin-classic-blue',
    get name() { return i18n.global.t('theme.skins.classicBlue') },
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
    get name() { return i18n.global.t('theme.skins.classicPurple') },
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
    get name() { return i18n.global.t('theme.skins.classicRed') },
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
    get name() { return i18n.global.t('theme.skins.classicGreen') },
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
    get name() { return i18n.global.t('theme.skins.classicOrange') },
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
    get name() { return i18n.global.t('theme.skins.pearlWhite') },
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
    get name() { return i18n.global.t('theme.skins.roseDream') },
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
    get name() { return i18n.global.t('theme.skins.midnightAurora') },
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
    get name() { return i18n.global.t('theme.skins.softSunset') },
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
    get name() { return i18n.global.t('theme.skins.deepSpaceNebula') },
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
    get name() { return i18n.global.t('theme.skins.oceanBreeze') },
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
    get name() { return i18n.global.t('theme.skins.sakuraRain') },
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
    get name() { return i18n.global.t('theme.skins.forestMist') },
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
  },

  // ────────────────────────────────────────────
  // 4. 官方默认范例（随仓库内置的背景图片）
  // ────────────────────────────────────────────
  {
    id: 'skin-default-sample',
    get name() { return i18n.global.t('theme.skins.defaultSample') },
    type: 'preset',
    colorThemeId: 'blue',
    mode: 'light',
    background: {
      image: './themes/backgrounds/wallhaven-qz9ykr.webp',
      blur: 0,
      opacity: 100,
      fit: 'cover'
    },
    glassIntensity: 0,
    ambientIntensity: 0,
    radiusTendency: 0
  }
]

/** 预设皮肤 ID → 皮肤映射 */
export const presetSkinMap: Record<string, Skin> = Object.fromEntries(
  presetSkins.map((s) => [s.id, s])
)

/** 根据色彩主题 ID 生成默认皮肤 ID。
 *  校验生成的 classic 皮肤 ID 是否存在于 presetSkinMap，
 *  若无对应预设皮肤（含自定义主题 ID），回退到 skin-classic-blue，
 *  避免返回不存在的皮肤 ID 导致 activeSkin 为空。
 */
export function getDefaultSkinIdForColorTheme(colorThemeId: string): string {
  const id = `skin-classic-${colorThemeId}`
  return presetSkinMap[id] ? id : 'skin-classic-blue'
}

/** 查找预设皮肤 */
export function findPresetSkinById(id: string): Skin | undefined {
  return presetSkinMap[id]
}
