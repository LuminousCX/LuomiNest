import { i18n } from '../i18n'

const RELATIVE_THRESHOLD = 7 * 24 * 60 * 60 * 1000

const isValidDate = (d: Date): boolean => !isNaN(d.getTime())

const formatDateRelative = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (!isValidDate(date)) return '—'

  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 0) return date.toLocaleDateString(i18n.global.locale.value)

  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return i18n.global.t('common.time.justNow')
  if (minutes < 60) return i18n.global.t('common.time.minutesAgo', { n: minutes })
  if (hours < 24) return i18n.global.t('common.time.hoursAgo', { n: hours })
  if (days < 7) return i18n.global.t('common.time.daysAgo', { n: days })

  return date.toLocaleDateString(i18n.global.locale.value, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

const formatFileSize = (bytes: number): string => {
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return bytes + ' B'
}

/** 下载量缩写（与 formatCount 同规则） */
const formatDownloadCount = (n: number): string => formatCount(n)

/** 计数缩写：中文用「w（万）」，其他语言用 k/m 千分位习惯 */
const formatCount = (n: number): string => {
  const zh = i18n.global.locale.value === 'zh-CN'
  if (zh && n >= 10000) return (n / 10000).toFixed(1) + 'w'
  if (!zh && n >= 1000000) return (n / 1000000).toFixed(1) + 'm'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

const formatTime = (dateStr: string, options?: { seconds?: boolean }): string => {
  const date = new Date(dateStr)
  if (!isValidDate(date)) return '--:--'
  // 跟随界面语言（小时制显式指定 24h，避免 en 下出现 12 小时制）
  return date.toLocaleTimeString(i18n.global.locale.value, {
    hour: '2-digit',
    minute: '2-digit',
    second: options?.seconds ? '2-digit' : undefined,
    hour12: false,
  })
}

const formatDateTime = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (!isValidDate(date)) return '—'
  // 月份短语随界面语言（原硬编码 'zh-CN'，en-US 下会显示中文日期）
  return `${date.toLocaleDateString(i18n.global.locale.value, { month: 'short', day: 'numeric' })} ${formatTime(dateStr)}`
}

const formatShortDateTime = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (!isValidDate(date)) return ''
  // 跟随界面语言（原硬编码 'zh-CN'，en-US 下会显示中文日期）
  return date.toLocaleString(i18n.global.locale.value, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

const formatSpeed = (bytesPerSec: number): string => {
  if (bytesPerSec <= 0) return ''
  if (bytesPerSec < 1024) return `${Math.round(bytesPerSec)} B/s`
  if (bytesPerSec < 1048576) return `${(bytesPerSec / 1024).toFixed(1)} KB/s`
  return `${(bytesPerSec / 1048576).toFixed(1)} MB/s`
}

const formatDateCalendar = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (!isValidDate(date)) return '—'

  const locale = i18n.global.locale.value
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const diffDays = Math.floor((today.getTime() - target.getTime()) / 86400000)

  if (diffDays <= 0) return formatTime(dateStr)
  if (diffDays === 1) return `${i18n.global.t('common.time.yesterday')} ${formatTime(dateStr)}`
  // 星期与月日文案用 Intl 按界面语言本地化（zh: 周六 / 7月12日；en: Sat / July 12；ja: 土 / 7月12日）
  if (diffDays <= 7) {
    return `${date.toLocaleDateString(locale, { weekday: 'short' })} ${formatTime(dateStr)}`
  }
  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString(locale, { month: 'long', day: 'numeric' })
  }
  return date.toLocaleDateString(locale, { year: 'numeric', month: 'long', day: 'numeric' })
}

const formatTokens = (n: number): string => {
  if (!n || n <= 0) return '0'
  return n.toLocaleString('en-US')
}

const formatDuration = (ms: number | null): string => {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}min`
}

export {
  formatDateRelative,
  formatFileSize,
  formatDownloadCount,
  formatCount,
  formatTime,
  formatDateTime,
  formatDateCalendar,
  formatShortDateTime,
  formatSpeed,
  formatDuration,
  formatTokens,
  RELATIVE_THRESHOLD,
}
