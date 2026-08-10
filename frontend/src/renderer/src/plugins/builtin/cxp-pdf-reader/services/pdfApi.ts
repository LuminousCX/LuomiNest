/**
 * pdfApi — CxPlugin PDF 智能阅读器后端 API 封装。
 *
 * 统一加 /plugins/cxp-pdf-reader 前缀，并解析后端 ApiResponse 信封
 * （{code, message, data}，code===0 表示成功，符合工作区规则：API 响应必须包含错误码）。
 */

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
// 统一请求与 ApiResponse 信封解析
// ---------------------------------------------------------------------------

/** 后端 ApiResponse 信封（{code, message, data}，code===0 表示成功） */
interface CxPdfApiResponse<T> {
  code: number
  message?: string
  data?: T
}

/** 成功码（与后端 CODE_OK 对齐） */
const PDF_API_SUCCESS_CODE = 0

/**
 * 统一 PDF 插件请求：附带鉴权头并解析 ApiResponse 信封。
 *
 * - HTTP 非 2xx：抛出友好错误信息（保留 HTTP 错误处理）
 * - 信封 code===0：返回 data 负载
 * - 信封 code!==0：抛出 message（即使 HTTP 状态为 200）
 * - 非信封格式：原样返回（向后兼容）
 */
const pdfRequest = async <T>(
  path: string,
  options: {
    method?: 'GET' | 'POST'
    json?: unknown
    form?: FormData
    timeout?: number
  } = {},
): Promise<T> => {
  const { method = 'GET', json, form, timeout = 15000 } = options
  const { API_ENDPOINTS } = await import('../../../../config/api')

  // 鉴权头（与 useApi 内部逻辑保持一致）
  const headers: Record<string, string> = {}
  try {
    const token = await window.api?.auth?.getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  } catch {
    // ignore — 未登录情况下不带 token
  }

  let body: BodyInit | undefined
  if (form) {
    body = form
  } else if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  }

  const resp = await fetch(`${API_ENDPOINTS.V1}${PLUGIN_API_BASE}${path}`, {
    method,
    headers,
    body,
    signal: AbortSignal.timeout(timeout),
  })

  if (!resp.ok) {
    const errData = await resp.json().catch(() => null)
    const msg = (errData as { detail?: string; message?: string })?.detail
      || (errData as { message?: string })?.message
      || `请求失败 (${resp.status})`
    throw new Error(msg)
  }

  const parsed = (await resp.json()) as CxPdfApiResponse<T> | T
  if (
    parsed &&
    typeof parsed === 'object' &&
    typeof (parsed as CxPdfApiResponse<T>).code === 'number'
  ) {
    const envelope = parsed as CxPdfApiResponse<T>
    if (envelope.code === PDF_API_SUCCESS_CODE) {
      return envelope.data as T
    }
    throw new Error(envelope.message || `操作失败 (code: ${envelope.code})`)
  }
  return parsed as T
}

// ---------------------------------------------------------------------------
// API 调用函数
// ---------------------------------------------------------------------------

/**
 * 提交文件到后端进行文本/大纲提取。
 * 使用 multipart/form-data，提取结果直接暴露 fileId/fileName/pageCount 等字段。
 */
const extractDocument = (file: File): Promise<CxPdfExtractResult> => {
  const formData = new FormData()
  formData.append('file', file)
  return pdfRequest<CxPdfExtractResult>('/extract', {
    method: 'POST',
    form: formData,
    timeout: 60000,
  })
}

/** 调用 AI 总结文档 */
const summarizeDocument = (
  fileId: string,
  maxLength?: number,
): Promise<CxPdfSummarizeResult> => {
  const body: Record<string, unknown> = { file_id: fileId }
  if (typeof maxLength === 'number') body.max_length = maxLength
  return pdfRequest<CxPdfSummarizeResult>('/summarize', { method: 'POST', json: body })
}

/** 调用 AI 翻译文档 */
const translateDocument = (
  fileId: string,
  targetLang: string,
  pageRange?: string,
): Promise<CxPdfTranslateResult> => {
  const body: Record<string, unknown> = {
    file_id: fileId,
    target_lang: targetLang,
  }
  if (pageRange) body.page_range = pageRange
  return pdfRequest<CxPdfTranslateResult>('/translate', { method: 'POST', json: body })
}

/** 与文档进行问答对话 */
const chatWithDocument = (
  fileId: string,
  question: string,
  history?: CxPdfChatMessage[],
): Promise<CxPdfChatResult> => {
  const body: Record<string, unknown> = {
    file_id: fileId,
    question,
  }
  if (history && history.length > 0) body.history = history
  return pdfRequest<CxPdfChatResult>('/chat', { method: 'POST', json: body })
}

/** 获取文档大纲 */
const getOutline = (fileId: string): Promise<CxPdfOutlineResult> =>
  pdfRequest<CxPdfOutlineResult>(`/outline/${fileId}`)

/** 在文档中搜索文本 */
const searchInDocument = (
  fileId: string,
  query: string,
): Promise<CxPdfSearchResult> =>
  pdfRequest<CxPdfSearchResult>('/search', {
    method: 'POST',
    json: { file_id: fileId, query },
  })

/** 获取指定页的纯文本 */
const getPageText = (
  fileId: string,
  pageNum: number,
): Promise<CxPdfPageTextResult> =>
  pdfRequest<CxPdfPageTextResult>('/page-text', {
    method: 'POST',
    json: { file_id: fileId, page_num: pageNum },
  })

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
