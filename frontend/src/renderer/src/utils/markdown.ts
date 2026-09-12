import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { stripEmotionTags } from './emotionTagInterceptor'

marked.setOptions({
  breaks: true,
  gfm: true,
})

export const renderMarkdown = (text: string): string => {
  if (!text) return ''
  const cleaned = stripEmotionTags(text)
  const raw = marked.parse(cleaned) as string
  return DOMPurify.sanitize(raw)
}

/* ============================================================================
 * 流式 markdown 渲染缓存 + 节流（按消息维度）
 * ========================================================================== */

/** 流式期间 markdown 重解析的最小间隔（ms）：窗口内复用上次渲染结果 */
const STREAM_RENDER_INTERVAL = 120
/** 渲染缓存上限（按插入序 FIFO 淘汰），key 为消息维度（内容+reasoning 各一条） */
const RENDER_CACHE_MAX = 300

interface RenderCacheEntry {
  /** 缓存对应的输入文本（内容一致即命中，与消息 id 无关，避免跨会话/版本串扰） */
  content: string
  html: string
  /** 上次实际重解析时间（节流窗口判定） */
  at: number
}

const renderCache = new Map<string, RenderCacheEntry>()

/**
 * 带缓存与节流的 markdown 渲染（流式消息专用）。
 *
 * - isDone（已完成）：内容与缓存一致直接复用（renderMarkdown 确定性，输出逐字节一致）；
 *   内容变化则精确重渲染，保证最终 HTML 与全量渲染完全相同。
 * - 流式（!isDone）：STREAM_RENDER_INTERVAL 窗口内返回上次渲染结果，
 *   避免每个 token 都对全文做 marked + DOMPurify 重解析（O(全文)/token）。
 * - render 可注入前置变换（如 reasoning 的 beautifyThinking），缓存比较针对原始输入。
 */
export const renderMarkdownThrottled = (
  cacheKey: string,
  content: string,
  isDone: boolean,
  render: (text: string) => string = renderMarkdown,
): string => {
  const cached = renderCache.get(cacheKey)
  if (cached && cached.content === content) return cached.html
  if (!isDone && cached && Date.now() - cached.at < STREAM_RENDER_INTERVAL) {
    return cached.html
  }
  const html = render(content)
  // 先删后写让重复访问的 key 重新排队（近似 LRU）
  if (cached) renderCache.delete(cacheKey)
  else if (renderCache.size >= RENDER_CACHE_MAX) {
    const oldest = renderCache.keys().next().value
    if (oldest !== undefined) renderCache.delete(oldest)
  }
  renderCache.set(cacheKey, { content, html, at: Date.now() })
  return html
}
