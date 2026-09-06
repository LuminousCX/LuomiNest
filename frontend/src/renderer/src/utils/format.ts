const RELATIVE_THRESHOLD = 7 * 24 * 60 * 60 * 1000

const isValidDate = (d: Date): boolean => !isNaN(d.getTime())

const formatDateRelative = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (!isValidDate(date)) return '—'

  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 0) return date.toLocaleDateString('zh-CN')

  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (hours < 24) return `${hours} 小时前`
  if (days < 7) return `${days} 天前`

  return date.toLocaleDateString('zh-CN', {
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

const formatDownloadCount = (n: number): string => {
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return n.toString()
}

const formatCount = (n: number): string => {
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

const formatTime = (dateStr: string, options?: { seconds?: boolean }): string => {
  const date = new Date(dateStr)
  if (!isValidDate(date)) return '--:--'
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: options?.seconds ? '2-digit' : undefined,
    hour12: false,
  })
}

const formatDateTime = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (!isValidDate(date)) return '—'
  return `${date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })} ${formatTime(dateStr)}`
}

const formatShortDateTime = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (!isValidDate(date)) return ''
  return date.toLocaleString('zh-CN', {
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

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const formatDateCalendar = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (!isValidDate(date)) return '—'

  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const diffDays = Math.floor((today.getTime() - target.getTime()) / 86400000)

  if (diffDays <= 0) return formatTime(dateStr)
  if (diffDays === 1) return `昨天 ${formatTime(dateStr)}`
  if (diffDays <= 7) return `${WEEKDAYS[date.getDay()]} ${formatTime(dateStr)}`
  if (date.getFullYear() === now.getFullYear()) return `${date.getMonth() + 1}月${date.getDate()}日`
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`
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
  RELATIVE_THRESHOLD,
}
