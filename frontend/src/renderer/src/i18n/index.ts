/**
 * vue-i18n 实例（全局唯一）
 *
 * 语言包按域拆分 key（common / welcome / nav / settings / splash / login），
 * 三语言全量打包（M1 规模小，无需懒加载）；fallback 为中文，保证任何缺失 key 不白屏。
 * 初始语言同步读 localStorage，避免非中文用户首屏闪中文。
 */
import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN.json'
import enUS from './locales/en-US.json'
import jaJP from './locales/ja-JP.json'

export const DEFAULT_LOCALE: AppLocale = 'zh-CN'

/** localStorage 持久化 key（stores/locale.ts 与本文件共用） */
export const LOCALE_STORAGE_KEY = 'luominest-locale'

/** 支持的语言列表（欢迎向导 / 设置页语言选择共用，name 为该语言的自称） */
export const SUPPORTED_LOCALES = [
  { code: 'zh-CN', name: '中文', flag: '中' },
  { code: 'en-US', name: 'English', flag: 'EN' },
  { code: 'ja-JP', name: '日本語', flag: '日' },
] as const

export type AppLocale = (typeof SUPPORTED_LOCALES)[number]['code']

/** 任意来源（localStorage / IPC / 旧数据）的语言值收敛到合法 AppLocale */
export function normalizeLocale(value: unknown): AppLocale {
  return SUPPORTED_LOCALES.some((l) => l.code === value) ? (value as AppLocale) : DEFAULT_LOCALE
}

function getInitialLocale(): AppLocale {
  try {
    return normalizeLocale(localStorage.getItem(LOCALE_STORAGE_KEY))
  } catch {
    return DEFAULT_LOCALE
  }
}

export const i18n = createI18n({
  legacy: false,
  locale: getInitialLocale(),
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
    'ja-JP': jaJP,
  },
  missingWarn: false,
  fallbackWarn: false,
})
