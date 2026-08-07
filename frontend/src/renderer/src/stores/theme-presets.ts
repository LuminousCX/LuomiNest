import type { ColorTheme } from './theme-types'

/**
 * 5 个预设主题 - 莫兰迪风格三色配色
 * 每个主题包含 light/dark 两套完整变量
 */
export const presetThemes: ColorTheme[] = [
  // ────────────────────────────────────────────
  // 1. 默认蓝 (Blue)
  // ────────────────────────────────────────────
  {
    id: 'blue',
    name: '默认蓝',
    type: 'preset',
    light: {
      primary: '#147EBC',
      secondary: '#5BA4D4',
      accent: '#f43f5e',
      primaryHover: '#116DA3',
      primaryLight: 'rgba(20, 126, 188, 0.1)',
      secondaryHover: '#4A93C3',
      secondaryLight: 'rgba(91, 164, 212, 0.1)',
      accentHover: '#E11D48',
      accentLight: 'rgba(244, 63, 94, 0.1)',
      shadowBrand: 'rgba(20, 126, 188, 0.15)',
      gradientBrand: 'linear-gradient(135deg, #147EBC, #5BA4D4)'
    },
    dark: {
      primary: '#3BA4D8',
      secondary: '#7BBCE4',
      accent: '#FB7185',
      primaryHover: '#5BB8E4',
      primaryLight: 'rgba(59, 164, 216, 0.15)',
      secondaryHover: '#8FC8EC',
      secondaryLight: 'rgba(123, 188, 228, 0.12)',
      accentHover: '#FDA4AF',
      accentLight: 'rgba(251, 113, 133, 0.15)',
      shadowBrand: 'rgba(59, 164, 216, 0.2)',
      gradientBrand: 'linear-gradient(135deg, #3BA4D8, #7BBCE4)'
    }
  },

  // ────────────────────────────────────────────
  // 2. 紫罗兰 (Purple)
  // ────────────────────────────────────────────
  {
    id: 'purple',
    name: '紫罗兰',
    type: 'preset',
    light: {
      primary: '#7C3AED',
      secondary: '#A78BFA',
      accent: '#EC4899',
      primaryHover: '#6D28D9',
      primaryLight: 'rgba(124, 58, 237, 0.1)',
      secondaryHover: '#8B6CF6',
      secondaryLight: 'rgba(167, 139, 250, 0.1)',
      accentHover: '#DB2777',
      accentLight: 'rgba(236, 72, 153, 0.1)',
      shadowBrand: 'rgba(124, 58, 237, 0.15)',
      gradientBrand: 'linear-gradient(135deg, #7C3AED, #A78BFA)'
    },
    dark: {
      primary: '#A78BFA',
      secondary: '#C4B5FD',
      accent: '#F472B6',
      primaryHover: '#B9A0FC',
      primaryLight: 'rgba(167, 139, 250, 0.15)',
      secondaryHover: '#D4C8FD',
      secondaryLight: 'rgba(196, 181, 253, 0.12)',
      accentHover: '#F9A8D4',
      accentLight: 'rgba(244, 114, 182, 0.15)',
      shadowBrand: 'rgba(167, 139, 250, 0.2)',
      gradientBrand: 'linear-gradient(135deg, #A78BFA, #C4B5FD)'
    }
  },

  // ────────────────────────────────────────────
  // 3. 中国红 (Red)
  // ────────────────────────────────────────────
  {
    id: 'red',
    name: '中国红',
    type: 'preset',
    light: {
      primary: '#C0392B',
      secondary: '#E74C3C',
      accent: '#F59E0B',
      primaryHover: '#A93226',
      primaryLight: 'rgba(192, 57, 43, 0.1)',
      secondaryHover: '#D44332',
      secondaryLight: 'rgba(231, 76, 60, 0.1)',
      accentHover: '#D97706',
      accentLight: 'rgba(245, 158, 11, 0.1)',
      shadowBrand: 'rgba(192, 57, 43, 0.15)',
      gradientBrand: 'linear-gradient(135deg, #C0392B, #E74C3C)'
    },
    dark: {
      primary: '#E74C3C',
      secondary: '#F07169',
      accent: '#FBBF24',
      primaryHover: '#EC6B5E',
      primaryLight: 'rgba(231, 76, 60, 0.15)',
      secondaryHover: '#F48D86',
      secondaryLight: 'rgba(240, 113, 105, 0.12)',
      accentHover: '#FCD34D',
      accentLight: 'rgba(251, 191, 36, 0.15)',
      shadowBrand: 'rgba(231, 76, 60, 0.2)',
      gradientBrand: 'linear-gradient(135deg, #E74C3C, #F07169)'
    }
  },

  // ────────────────────────────────────────────
  // 4. 翡翠绿 (Green)
  // ────────────────────────────────────────────
  {
    id: 'green',
    name: '翡翠绿',
    type: 'preset',
    light: {
      primary: '#059669',
      secondary: '#34D399',
      accent: '#8B5CF6',
      primaryHover: '#047857',
      primaryLight: 'rgba(5, 150, 105, 0.1)',
      secondaryHover: '#28C08A',
      secondaryLight: 'rgba(52, 211, 153, 0.1)',
      accentHover: '#7C3AED',
      accentLight: 'rgba(139, 92, 246, 0.1)',
      shadowBrand: 'rgba(5, 150, 105, 0.15)',
      gradientBrand: 'linear-gradient(135deg, #059669, #34D399)'
    },
    dark: {
      primary: '#34D399',
      secondary: '#6EE7B7',
      accent: '#A78BFA',
      primaryHover: '#52E0AD',
      primaryLight: 'rgba(52, 211, 153, 0.15)',
      secondaryHover: '#8AEDCA',
      secondaryLight: 'rgba(110, 231, 183, 0.12)',
      accentHover: '#B9A0FC',
      accentLight: 'rgba(167, 139, 250, 0.15)',
      shadowBrand: 'rgba(52, 211, 153, 0.2)',
      gradientBrand: 'linear-gradient(135deg, #34D399, #6EE7B7)'
    }
  },

  // ────────────────────────────────────────────
  // 5. 暖橘橙 (Orange)
  // ────────────────────────────────────────────
  {
    id: 'orange',
    name: '暖橘橙',
    type: 'preset',
    light: {
      primary: '#EA580C',
      secondary: '#FB923C',
      accent: '#0EA5E9',
      primaryHover: '#D44E0A',
      primaryLight: 'rgba(234, 88, 12, 0.1)',
      secondaryHover: '#F58025',
      secondaryLight: 'rgba(251, 146, 60, 0.1)',
      accentHover: '#0284C7',
      accentLight: 'rgba(14, 165, 233, 0.1)',
      shadowBrand: 'rgba(234, 88, 12, 0.15)',
      gradientBrand: 'linear-gradient(135deg, #EA580C, #FB923C)'
    },
    dark: {
      primary: '#FB923C',
      secondary: '#FDBA74',
      accent: '#38BDF8',
      primaryHover: '#FCA656',
      primaryLight: 'rgba(251, 146, 60, 0.15)',
      secondaryHover: '#FDCA92',
      secondaryLight: 'rgba(253, 186, 116, 0.12)',
      accentHover: '#7DD3FC',
      accentLight: 'rgba(56, 189, 248, 0.15)',
      shadowBrand: 'rgba(251, 146, 60, 0.2)',
      gradientBrand: 'linear-gradient(135deg, #FB923C, #FDBA74)'
    }
  }
]

/** 预设主题 ID → 名称映射 */
export const presetThemeNames: Record<string, string> = {
  blue: '辰汐蓝',
  purple: '紫罗兰',
  red: '中国红',
  green: '翡翠绿',
  orange: '暖橘橙'
}

/** 预设主题 ID → 三色预览色（primary / secondary / accent） */
export const presetThemeColors: Record<string, [string, string, string]> = {
  blue:   ['#147EBC', '#5BA4D4', '#f43f5e'],
  purple: ['#7C3AED', '#A78BFA', '#EC4899'],
  red:    ['#C0392B', '#E74C3C', '#F59E0B'],
  green:  ['#059669', '#34D399', '#8B5CF6'],
  orange: ['#EA580C', '#FB923C', '#0EA5E9']
}

/** 获取色彩主题的预览色 */
export function getThemePreviewColors(themeId: string): [string, string, string] {
  return presetThemeColors[themeId] ?? ['#147EBC', '#5BA4D4', '#f43f5e']
}
