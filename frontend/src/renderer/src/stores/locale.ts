/**
 * 语言偏好 store — 全局语言切换的唯一入口
 *
 * 完全复刻 theme.ts 的模式：
 * 1. 初始值同步读 localStorage（i18n 实例创建时已用同一 key 初始化），保证首屏不闪语言
 * 2. 切换时同步更新 vue-i18n 全局 locale + <html lang>（驱动日文字体栈等 CSS 选择器）
 * 3. 双写持久化：localStorage（快速恢复）+ IPC config-store（userData/Config/config.json 权威落盘）
 * 4. 启动后异步从 IPC 读权威配置覆盖（dev/安装版配置一致性）
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { setStringItem } from '../utils/storage'
import { i18n, LOCALE_STORAGE_KEY, normalizeLocale, type AppLocale } from '../i18n'

export const useLocaleStore = defineStore('locale', () => {
  const locale = ref<AppLocale>(normalizeLocale(i18n.global.locale.value))

  /** <html lang> 同步：主题用 data-theme，语言用 lang（CSS 据此切换日文字体栈） */
  function applyToDOM(value: AppLocale): void {
    document.documentElement.setAttribute('lang', value)
  }

  function setLocale(value: AppLocale): void {
    locale.value = value
    i18n.global.locale.value = value
    applyToDOM(value)
    setStringItem(LOCALE_STORAGE_KEY, value)
    window.api?.config?.setLocale?.(value).catch(() => {})
  }

  applyToDOM(locale.value)

  // IPC 权威配置覆盖（与主题 store 的两级恢复一致）
  window.api?.config
    ?.getLocale?.()
    .then((saved) => {
      if (!saved) return
      const normalized = normalizeLocale(saved)
      if (normalized !== locale.value) setLocale(normalized)
    })
    .catch(() => {})

  return {
    locale,
    setLocale,
  }
})
