const RELATIVE_THRESHOLD = 7 * 24 * 60 * 60 * 1000

const formatDateRelative = (dateStr: string): string => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return '—'

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

export { formatDateRelative, formatFileSize, formatDownloadCount, RELATIVE_THRESHOLD }
