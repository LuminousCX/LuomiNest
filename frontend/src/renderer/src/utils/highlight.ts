/**
 * 搜索结果片段高亮工具（会话搜索等场景共用）。
 *
 * 先 HTML 转义再对关键词做 <mark> 包裹，避免 v-html 注入。
 */

const HTML_ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}

export function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch] ?? ch)
}

export function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** 转义 snippet 并高亮关键词（大小写不敏感）；snippet 为空返回空串。 */
export function highlightSnippet(snippet: string, keyword: string): string {
  if (!snippet) return ''
  const escaped = escapeHtml(snippet)
  const q = (keyword || '').trim()
  if (!q) return escaped
  const regex = new RegExp(`(${escapeRegExp(q)})`, 'gi')
  return escaped.replace(regex, '<mark>$1</mark>')
}
