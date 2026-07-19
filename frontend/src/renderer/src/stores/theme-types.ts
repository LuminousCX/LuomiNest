/**
 * 主题类型定义 - 从共享 IPC 类型导入，避免重复定义
 * 本文件仅 re-export 供 renderer store 使用
 */
export type {
  ColorTheme,
  ThemeColorSet,
  BackgroundConfig,
  ThemeConfig,
} from '@shared/ipc-types'

/** 预设主题 ID 常量 */
export const PRESET_THEME_IDS = ['blue', 'purple', 'red', 'green', 'orange'] as const
export type PresetThemeId = typeof PRESET_THEME_IDS[number]

/** 自定义主题数量上限 */
export const MAX_CUSTOM_THEMES = 5
