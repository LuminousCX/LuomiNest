/**
 * pdfApi — CxPlugin PDF 智能阅读器后端 API 封装。
 *
 * 复用主项目 useApi 的 apiGet/apiPost，统一加 /plugins/cxp-pdf-reader 前缀。
 * 错误码由后端 ApiResponse 包装（符合工作区规则：API 响应必须包含错误码）。
 */

import { useApi } from '../../../../composables/useApi'

// 插件专属 API 路径前缀（与后端 endpoint 对齐）
const PLUGIN_API_BASE = '/plugins/cxp-pdf-reader'

// ---------------------------------------------------------------------------
// 类型定义
// ---------------------------------------------------------------------------

export type CxPdfFileType = 'pdf' | 'docx' | 'txt' | 'unknown'

/** 大纲条目 — 树形结构 */
export interface CxPdfOutlineItem {
  level: number
  title: string
  page: number
  children?: CxPdfOutlineItem[]
}

/** 文档提取响应 */
export interface CxPdfExtractResult {
  fileId: string
  fileName: string
  fileType: CxPdfFileType
  pageCount: number
  outline: CxPdfOutlineItem[]
  textPreview: string
}

/** 总结响应 */
export interface CxPdfSummarizeResult {
  summary: string
  keyPoints: string[]
}

/** 翻译响应 */
export interface CxPdfTranslateResult {
  translation: string
}

/** 问答响应 */
export interface CxPdfChatResult {
  answer: string
  tokensUsed: number
}

/** 聊天历史消息（用于 chatWithDocument） */
export interface CxPdfChatMessage {
  role: 'user' | 'assistant'
  content: string
}

/** 搜索匹配项 */
export interface CxPdfSearchMatch {
  page: number
  snippet: string
  position: number
}

/** 搜索响应 */
export interface CxPdfSearchResult {
  matches: CxPdfSearchMatch[]
  total: number
}

/** 大纲响应 */
export interface CxPdfOutlineResult {
  outline: CxPdfOutlineItem[]
}

/** 单页文本响应 */
export interface CxPdfPageTextResult {
  text: string
}

/** 健康检查响应 */
export interface CxPdfHealthResult {
  status: 'ok' | 'error'
  version: string
}

// ---------------------------------------------------------------------------
// API 调用函数
// ---------------------------------------------------------------------------

/**
 * 提交文件到后端进行文本/大纲提取。
 * 使用 multipart/form-data，因此直接走 fetch（不使用 apiPost 的 JSON body）。
 */
const extractDocument = async (file: File): Promise<CxPdfExtractResult> => {
  const { API_ENDPOINTS } = await import('../../../../config/api')
  const formData = new FormData()
  formData.append('file', file)

  // 获取 token（与 useApi 内部逻辑保持一致）
  let authHeaders: Record<string, string> = {}
  try {
    const token = await window.api?.auth?.getToken()
    if (token) authHeaders = { Authorization: `Bearer ${token}` }
  } catch {
    // ignore — 未登录情况下不带 token
  }

  const resp = await fetch(`${API_ENDPOINTS.V1}${PLUGIN_API_BASE}/extract`, {
    method: 'POST',
    headers: authHeaders,
    body: formData,
    signal: AbortSignal.timeout(60000),
  })

  if (!resp.ok) {
    const errData = await resp.json().catch(() => null)
    const msg = (errData as { detail?: string; message?: string })?.detail
      || (errData as { message?: string })?.message
      || `文件提取失败 (${resp.status})`
    throw new Error(msg)
  }

  return resp.json()
}

/** 调用 AI 总结文档 */
const summarizeDocument = (
  fileId: string,
  maxLength?: number,
): Promise<CxPdfSummarizeResult> => {
  const { apiPost } = useApi()
  const body: Record<string, unknown> = { file_id: fileId }
  if (typeof maxLength === 'number') body.max_length = maxLength
  return apiPost<CxPdfSummarizeResult>(`${PLUGIN_API_BASE}/summarize`, body)
}

/** 调用 AI 翻译文档 */
const translateDocument = (
  fileId: string,
  targetLang: string,
  pageRange?: string,
): Promise<CxPdfTranslateResult> => {
  const { apiPost } = useApi()
  const body: Record<string, unknown> = {
    file_id: fileId,
    target_lang: targetLang,
  }
  if (pageRange) body.page_range = pageRange
  return apiPost<CxPdfTranslateResult>(`${PLUGIN_API_BASE}/translate`, body)
}

/** 与文档进行问答对话 */
const chatWithDocument = (
  fileId: string,
  question: string,
  history?: CxPdfChatMessage[],
): Promise<CxPdfChatResult> => {
  const { apiPost } = useApi()
  const body: Record<string, unknown> = {
    file_id: fileId,
    question,
  }
  if (history && history.length > 0) body.history = history
  return apiPost<CxPdfChatResult>(`${PLUGIN_API_BASE}/chat`, body)
}

/** 获取文档大纲 */
const getOutline = (fileId: string): Promise<CxPdfOutlineResult> => {
  const { apiGet } = useApi()
  return apiGet<CxPdfOutlineResult>(`${PLUGIN_API_BASE}/outline/${fileId}`)
}

/** 在文档中搜索文本 */
const searchInDocument = (
  fileId: string,
  query: string,
): Promise<CxPdfSearchResult> => {
  const { apiPost } = useApi()
  return apiPost<CxPdfSearchResult>(`${PLUGIN_API_BASE}/search`, {
    file_id: fileId,
    query,
  })
}

/** 获取指定页的纯文本 */
const getPageText = (
  fileId: string,
  pageNum: number,
): Promise<CxPdfPageTextResult> => {
  const { apiPost } = useApi()
  return apiPost<CxPdfPageTextResult>(`${PLUGIN_API_BASE}/page-text`, {
    file_id: fileId,
    page_num: pageNum,
  })
}

/** 健康检查（不走 useApi，使用更短超时） */
const healthCheck = async (): Promise<CxPdfHealthResult> => {
  const { API_ENDPOINTS } = await import('../../../../config/api')
  try {
    const resp = await fetch(`${API_ENDPOINTS.V1}${PLUGIN_API_BASE}/health`, {
      signal: AbortSignal.timeout(3000),
    })
    if (!resp.ok) return { status: 'error', version: 'unknown' }
    return resp.json()
  } catch {
    return { status: 'error', version: 'unknown' }
  }
}

// ---------------------------------------------------------------------------
// 导出
// ---------------------------------------------------------------------------

export const cxPdfApi = {
  extractDocument,
  summarizeDocument,
  translateDocument,
  chatWithDocument,
  getOutline,
  searchInDocument,
  getPageText,
  healthCheck,
}

export default cxPdfApi
