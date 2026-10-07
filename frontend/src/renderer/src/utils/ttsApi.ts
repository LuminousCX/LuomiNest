import { API_ENDPOINTS } from '../config/api'

export interface TtsSynthesizeError extends Error {
  /** 服务端错误码（如 LANG_NOT_SUPPORTED） */
  code?: string
  /** HTTP 状态码 */
  status?: number
}

/**
 * TTS 合成请求统一入口（原 4 处手写 fetch 拷贝收口，见调查报告 §N2）。
 *
 * @param body   POST /chat/tts/synthesize 请求体（text/voice/engine/model/speed/...）
 * @param options.signal 透传给 fetch 的中止信号
 * @param options.fallbackMessage 错误信封解析不出可读文案时的兜底（通常传 i18n 文案；
 *                                 文案中的 {status} 占位符会被替换为真实 HTTP 状态码）
 * @returns 音频 Blob
 * @throws TtsSynthesizeError 非 2xx 时抛出（信封兼容 string / {code,message} / detail / message 四种形状）
 */
export async function synthesizeTts(
  body: Record<string, unknown>,
  options: { signal?: AbortSignal; fallbackMessage?: string } = {},
): Promise<Blob> {
  const token = await window.api.auth.getToken()
  const response = await fetch(API_ENDPOINTS.TTS_SYNTHESIZE, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal: options.signal,
  })

  if (!response.ok) {
    const errJson: unknown = await response.json().catch(() => null)
    const ej = errJson as {
      error?: string | { code?: string; message?: string }
      message?: string
      detail?: string
    } | null
    const fallback = (options.fallbackMessage || `TTS request failed (${response.status})`).replace(
      '{status}',
      String(response.status),
    )
    const err = new Error(
      !ej
        ? fallback
        : typeof ej.error === 'string'
          ? ej.error
          : ej.error?.message || ej.detail || ej.message || fallback,
    ) as TtsSynthesizeError
    err.code = ej && typeof ej.error === 'object' ? ej.error?.code : undefined
    err.status = response.status
    throw err
  }

  return response.blob()
}
