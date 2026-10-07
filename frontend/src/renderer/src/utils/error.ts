/**
 * 统一的错误消息提取工具。
 * 全仓 catch 块里的 `e instanceof Error ? e.message : String(e)` 一律改用这里，
 * 避免 60+ 处内联重复（调查报告：文档/2026年10月8日前端清理调查/重复造轮子清查报告.md §N4）。
 */

/** 基础提取：Error 取 message，其余 String() 化（与历史内联写法语义完全一致） */
export function toErrorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}

/**
 * HTTP 错误提取：优先取 axios 形状的 response.data.detail（useApi 抛错的友好信息），
 * 其次 message，最后 fallback。
 */
export function toHttpErrorMessage(e: unknown, fallback: string): string {
  const err = e as { response?: { data?: { detail?: string } }; message?: string }
  return err?.response?.data?.detail || err?.message || fallback
}
