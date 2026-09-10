/**
 * vue-i18n 实例（全局唯一）
 *
 * 语言包组织：
 * - 根级整包 locales/<lang>.json：核心域（common / welcome / nav / settings / splash / login）
 * - 按域拆分 locales/<lang>/<domain>.json：M3 起各领域迁移时增量添加（workspace / avatar / …）
 *   两者都会被下方 glob 收集合并，顶层 key 全局唯一（各域互不重叠）。
 * fallback 为中文，保证任何缺失 key 不白屏；初始语言同步读 localStorage，避免非中文用户首屏闪中文。
 */
import { createI18n, type DefaultLocaleMessageSchema } from 'vue-i18n'

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

/** 收集某个语言的全部 JSON（根级整包 + 按域拆分文件），合并为一个 messages 对象 */
function collectLocaleMessages(locale: AppLocale): Record<string, unknown> {
  const modules = import.meta.glob('./locales/**/*.json', { eager: true }) as Record<
    string,
    { default: Record<string, unknown> }
  >
  const merged: Record<string, unknown> = {}
  for (const [path, mod] of Object.entries(modules)) {
    // './locales/zh-CN.json' → 'zh-CN.json'；'./locales/zh-CN/chat.json' → 'zh-CN/chat.json'
    const rest = path.replace('./locales/', '')
    const parts = rest.split('/')
    // 根级文件取文件名去后缀；子目录文件取第一段目录名
    const fileLocale = parts.length === 1 ? parts[0].replace(/\.json$/, '') : parts[0]
    if (fileLocale !== locale) continue
    Object.assign(merged, mod.default)
  }
  return merged
}

// glob 收集的 messages 是宽类型（Record<string, unknown>），断言为 vue-i18n 的消息 schema，
// 保证 Composer 泛型推断正常（i18n.global.locale 保持可写的 Ref 而非退化为 string）
export const i18n = createI18n({
  legacy: false,
  locale: getInitialLocale(),
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': collectLocaleMessages('zh-CN') as DefaultLocaleMessageSchema,
    'en-US': collectLocaleMessages('en-US') as DefaultLocaleMessageSchema,
    'ja-JP': collectLocaleMessages('ja-JP') as DefaultLocaleMessageSchema,
  },
  missingWarn: false,
  fallbackWarn: false,
})
