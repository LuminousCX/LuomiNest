/**
 * 聊天消息增强辅助 —— 将搜索意图检测与 URL 内容抓取
 * 从 chat store 的 sendMessage 中解耦，保持核心流程清晰。
 */
import type { ChatMessage } from '../types'
import { i18n } from '../i18n'
import { detectSearchIntent, extractSearchQuery } from './searchIntent'
import { createLuomiNestRendererLogger } from './logger'

const logger = createLuomiNestRendererLogger('ChatSearchHelpers')

/**
 * 搜索意图增强：检测用户消息是否需要联网搜索，
 * 若需要则调用内置浏览器搜索并将结果注入 requestBody.search_results。
 */
export const enrichWithSearchResults = async (
  content: string,
  requestBody: Record<string, unknown>,
): Promise<void> => {
  try {
    const searchNeeded = await detectSearchIntent(content)
    if (searchNeeded) {
      const searchQuery = extractSearchQuery(content)
      const searchResults = await window.api.browserSearch.search(searchQuery)
      if (searchResults && searchResults.length > 0) {
        requestBody.search_results = searchResults
          .map((r: { title: string; snippet: string }) => `${r.title}: ${r.snippet}`)
          .join('\n')
      }
    }
  } catch (err) {
    logger.warn('Browser search failed, continuing without search results:', err)
  }
}

/** URL 匹配正则 —— 提取消息中的 http(s) 链接，最多取 3 个 */
const URL_REGEX = /https?:\/\/[^\s<>"')\]]+/g
const MAX_URLS_TO_FETCH = 3

/**
 * URL 内容增强：检测消息中的 URL，自动 fetch 页面内容并注入 requestBody。
 * 返回期间在 assistant 占位消息上显示加载状态，完成后清空。
 */
export const enrichWithUrlContent = async (
  content: string,
  requestBody: Record<string, unknown>,
  updateLastAssistantMessage: (patch: Partial<ChatMessage>) => void,
): Promise<void> => {
  try {
    const urlMatches = [...content.matchAll(URL_REGEX)].map((m) => m[0])
    const urlsToFetch = urlMatches.slice(0, MAX_URLS_TO_FETCH)
    if (urlsToFetch.length === 0) return

    updateLastAssistantMessage({
      content:
        urlsToFetch.length === 1
          ? i18n.global.t('chat.fetchingUrl')
          : i18n.global.t('chat.fetchingUrls', { n: urlsToFetch.length }),
    })

    for (const url of urlsToFetch) {
      const pageContent = await window.api.browserSearch.fetchUrl(url)
      if (pageContent) {
        requestBody.search_results = requestBody.search_results
          ? `${requestBody.search_results}\n\n[网页内容: ${url}]\n${pageContent}`
          : `[网页内容: ${url}]\n${pageContent}`
      }
    }

    // 清空加载提示，让 stream 正常填充
    updateLastAssistantMessage({ content: '' })
  } catch (err) {
    logger.warn('Fetch URL failed, continuing without page content:', err)
  }
}

/**
 * 在容器内按文本定位目标行并滚动到位、高亮 2 秒（聊天气泡搜索定位的统一实现）。
 *
 * @param options.expand 定位失败时的展开钩子（如窗口化列表先展开全量再重试）
 * @param options.onFail 仍找不到时的回调（如回滚到底部）
 */
export async function scrollToTextMatch(
  container: HTMLElement,
  selector: string,
  keyword: string,
  options: { expand?: () => Promise<void> | void; onFail?: () => void } = {},
): Promise<void> {
  const q = keyword.toLowerCase()
  const findMatch = (): Element | undefined =>
    Array.from(container.querySelectorAll(selector)).find((el) =>
      (el.textContent || '').toLowerCase().includes(q),
    )
  let target = findMatch()
  if (!target && options.expand) {
    await options.expand()
    target = findMatch()
  }
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    target.classList.add('lumi-chat-search-highlight')
    setTimeout(() => target.classList.remove('lumi-chat-search-highlight'), 2000)
    return
  }
  options.onFail?.()
}
