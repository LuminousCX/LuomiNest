import { ref } from 'vue'
import type { ChatStreamChunk } from '../types'
import { API_ENDPOINTS } from '../config/api'
import { i18n } from '../i18n'
import { whenBackendReady } from './useBackendGate'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('Api')

const getApiUrl = (path: string) => `${API_ENDPOINTS.V1}${path}`

// HTTP 状态码与后端 err_code 的用户可见文案迁移至 i18n（api.http.* / api.codes.*）。
// te() 检查 key 是否存在：不存在的状态码/错误码走 fallback，保证后端新增码不会显示 key 本身。
const statusToMessage = (status: number): string =>
  i18n.global.te(`api.http.${status}`)
    ? i18n.global.t(`api.http.${status}`)
    : i18n.global.t('api.requestFailed', { status })

/**
 * 云端业务错误码 → 本地化文案（与后端 CloudProxyProvider 的接口约定：
 * errCode 为数字字符串，如 "13005" 余额不足 / "12001" 额度用尽 / "11001" 登录失效）。
 * 未收录/缺失返回 null，调用方回退后端 message 原文。
 * 供 REST 错误响应（extractErrorMessage）与 SSE 错误 chunk（chat store）共用。
 */
export const cloudErrCodeMessage = (errCode: unknown): string | null => {
  if (typeof errCode !== 'string' && typeof errCode !== 'number') return null
  const key = `api.cloudErrors.${String(errCode)}`
  return i18n.global.te(key) ? i18n.global.t(key) : null
}

/**
 * 后端 done chunk 的 usage 归一化：wire 格式为 snake_case（与 ChatStreamChunk
 * 其余字段单一事实源对齐，由 providers 归一化产出，见 anthropic_messages._normalize_usage）；
 * 前端内部统一 camelCase（chat.lastUsage / ChatMessage.usage 消费形状）。
 * 容忍 camelCase 直传（对齐后端 usage_tracker 的双格式兼容）；
 * 三值全缺时返回 undefined（provider 未上报 usage，如部分中转）。
 */
const normalizeUsage = (raw: unknown): ChatStreamChunk['usage'] | undefined => {
  if (!raw || typeof raw !== 'object') return undefined
  const u = raw as Record<string, unknown>
  const num = (v: unknown): number | undefined =>
    typeof v === 'number' && Number.isFinite(v) ? v : undefined
  const promptTokens = num(u.promptTokens) ?? num(u.prompt_tokens)
  const completionTokens = num(u.completionTokens) ?? num(u.completion_tokens)
  let totalTokens = num(u.totalTokens) ?? num(u.total_tokens)
  if (totalTokens === undefined && (promptTokens !== undefined || completionTokens !== undefined)) {
    totalTokens = (promptTokens ?? 0) + (completionTokens ?? 0)
  }
  if (promptTokens === undefined && completionTokens === undefined && totalTokens === undefined) {
    return undefined
  }
  return { promptTokens, completionTokens, totalTokens }
}

let cachedAuthToken: string | null | undefined

const getAuthHeaders = async (): Promise<Record<string, string>> => {
  if (cachedAuthToken === undefined) {
    try {
      cachedAuthToken = await window.api.auth.getToken()
    } catch {
      cachedAuthToken = null
    }
  }
  return cachedAuthToken ? { Authorization: `Bearer ${cachedAuthToken}` } : {}
}

/** 后端错误响应体（兼容多种错误格式） */
interface ApiErrorBody {
  error?: string | { code?: string; message?: string }
  detail?: unknown
  message?: string
}

const extractErrorMessage = (errData: unknown, status: number): string => {
  const data = (errData ?? {}) as ApiErrorBody
  // 1. 统一信封 error.code（LuomiNestError 家族 + HTTPException 兜底信封均产出）；
  //    i18n 中已收录的错误码给出本地化文案，未收录的保持原样走后端 message
  const errCode = typeof data.error === 'object' ? data.error?.code : undefined
  if (errCode && i18n.global.te(`api.codes.${errCode}`)) {
    return i18n.global.t(`api.codes.${errCode}`)
  }

  // 1.5 云端业务错误码（CloudProxyProvider 透传的 errCode，位于 detail/error 对象）；
  //     命中映射表显示本地化文案，未命中继续走后端 message 原文
  const errSource: Record<string, unknown> | undefined =
    typeof data.error === 'object' && data.error !== null
      ? (data.error as Record<string, unknown>)
      : typeof data.detail === 'object' && data.detail !== null
        ? (data.detail as Record<string, unknown>)
        : undefined
  const cloudMsg = errSource ? cloudErrCodeMessage(errSource.errCode) : null
  if (cloudMsg) return cloudMsg

  // 2. 兼容 error 为字符串的情况（TTS 接口等）
  let errMsg: unknown = ''
  if (typeof data.error === 'string') {
    errMsg = data.error
  } else {
    errMsg = data.error?.message || data.detail || data.message || ''
  }

  // 3. 兜底：对象形式序列化（后端 422 校验错误已由 RequestValidationError
  //    handler 统一转信封，不再出现裸 {"detail": [...]} 数组形式）
  if (typeof errMsg === 'object' && errMsg !== null) {
    errMsg = JSON.stringify(errMsg)
  }

  // 4. 无具体消息时，按 HTTP 状态码返回友好提示
  return (typeof errMsg === 'string' ? errMsg : '') || statusToMessage(status)
}

export const useApi = () => {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const abortController = ref<AbortController | null>(null)

  const abort = () => {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
  }

  const request = async <T>(
    path: string,
    options: {
      method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
      body?: unknown
      timeout?: number
      signal?: AbortSignal
    } = {}
  ): Promise<T> => {
    const { method = 'GET', body, timeout = 15000, signal } = options

    // 等待后端就绪（启动期门闩）：主进程「先建窗口、后启后端」，
    // 提前发出的请求只会撞 ECONNREFUSED。超时会兜底放行走正常错误路径。
    await whenBackendReady()

    loading.value = true
    error.value = null

    try {
      const authHeaders = await getAuthHeaders()
      const headers: Record<string, string> = { ...authHeaders }
      if (body) {
        headers['Content-Type'] = 'application/json'
      }

      const timeoutSignal = AbortSignal.timeout(timeout)
      const fetchOptions: RequestInit = {
        method,
        signal: signal ? AbortSignal.any([timeoutSignal, signal]) : timeoutSignal,
        headers,
      }

      if (body) {
        fetchOptions.body = JSON.stringify(body)
      }

      const resp = await fetch(getApiUrl(path), fetchOptions)

      if (!resp.ok) {
        const errData = await resp.json().catch(() => null)
        throw new Error(extractErrorMessage(errData, resp.status))
      }

      if (resp.status === 204 || resp.headers.get('content-length') === '0') {
        return undefined as T
      }

      const text = await resp.text()
      if (!text) return undefined as T
      const parsed = JSON.parse(text)
      // 自动解包统一响应信封 ok()/fail()：{code, message, error, data}
      // 仅根据 code（数字）与 data 字段判定为信封，不强制要求 error 字段存在，
      // 兼容部分端点返回 {code, message, data} 的非标准格式。
      // code===0 返回 data 负载；code 非 0 抛出错误并保留后端 message（软错误兜底）。
      // 无 code 字段的裸响应原样返回，保持向后兼容。
      if (
        parsed &&
        typeof parsed === 'object' &&
        typeof parsed.code === 'number' &&
        'data' in parsed
      ) {
        if (parsed.code !== 0) {
          const msg = typeof parsed.message === 'string' && parsed.message
            ? parsed.message
            : statusToMessage(resp.status)
          throw new Error(msg)
        }
        return parsed.data as T
      }
      return parsed as T
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
      throw e
    } finally {
      loading.value = false
    }
  }

  const apiGet = <T>(path: string, options?: { signal?: AbortSignal }): Promise<T> =>
    request<T>(path, options)

  // options 透传（如 timeout）：备份创建/恢复等重操作需要超过默认 15s 的超时
  const apiPost = <T>(path: string, body?: unknown, options?: { timeout?: number }): Promise<T> =>
    request<T>(path, { method: 'POST', body, ...options })

  const apiPut = <T>(path: string, body: unknown): Promise<T> =>
    request<T>(path, { method: 'PUT', body })

  const apiPatch = <T>(path: string, body?: unknown): Promise<T> =>
    request<T>(path, { method: 'PATCH', body })

  const apiDelete = <T = void>(path: string): Promise<T | void> =>
    request<T>(path, { method: 'DELETE' })

  const truncateMessages = (convId: string, keepCount: number): Promise<void> =>
    apiPatch(`/chat/conversations/${convId}/messages`, { keep_count: keepCount })

  const deleteMessage = (convId: string, messageId: string): Promise<void> =>
    apiDelete(`/chat/conversations/${convId}/messages/${messageId}`)

  /**
   * SSE 流式请求的共享核心 —— 统一的 fetch → reader → 按行解析 data: 管线。
   * apiStream 与 apiSseStream 均委托于此，消除 ~80% 的重复代码。
   *
   * opts.requireDoneSignal（chat 流专用）：true 时流必须以 done 信号
   * （done chunk / [DONE] 哨兵，onData 返回 true）收尾；服务端崩溃、代理切断、
   * 网络闪断导致的干净 EOF 视为流意外终止，走 onError 出口而非 onDone，
   * 避免半截回答被标记为成功完成（链路审查 P1-5）。
   * apiSseStream（workflow/social 等长生命周期事件流）以 EOF 为正常结束，
   * 不开启此选项，保持原行为。
   */
  const _fetchSseStream = async (
    path: string,
    body: unknown,
    handlers: {
      onData: (dataStr: string) => boolean | Promise<boolean>
      onDone: () => void | Promise<void>
      onError: (err: string) => void
    },
    externalAbortSignal?: AbortSignal,
    opts?: { requireDoneSignal?: boolean }
  ) => {
    const controller = new AbortController()
    abortController.value = controller

    const signal = externalAbortSignal
      ? AbortSignal.any([controller.signal, externalAbortSignal])
      : controller.signal

    let finishReceived = false

    try {
      // 与 request() 相同的启动期门闩：流式请求同样不能早于后端就绪发出
      await whenBackendReady()
      const authHeaders = await getAuthHeaders()
      const resp = await fetch(getApiUrl(path), {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal,
      })

      if (!resp.ok) {
        const errData = await resp.json().catch(() => null)
        throw new Error(extractErrorMessage(errData, resp.status))
      }

      const reader = resp.body?.getReader()
      if (!reader) throw new Error(i18n.global.t('api.streamReadFailed'))

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          buffer += value
            ? decoder.decode(value, { stream: false })
            : decoder.decode()
          for (const line of buffer.split('\n')) {
            const trimmed = line.trim()
            if (!trimmed.startsWith('data: ')) continue
            const dataStr = trimmed.slice(6)
            if (!dataStr.trim()) continue
            if (await handlers.onData(dataStr)) {
              finishReceived = true
              await handlers.onDone()
              return
            }
          }
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const dataStr = trimmed.slice(6)
          if (!dataStr.trim()) continue
          if (await handlers.onData(dataStr)) {
            finishReceived = true
            await handlers.onDone()
            return
          }
        }
      }

      if (opts?.requireDoneSignal && !finishReceived) {
        // 流意外终止：未收到 done 信号即 EOF，半截回答走错误出口
        handlers.onError(i18n.global.t('api.streamInterrupted'))
        return
      }
      await handlers.onDone()
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') {
        return
      }
      handlers.onError(e instanceof Error ? e.message : String(e))
    } finally {
      abortController.value = null
    }
  }

  const apiStream = async (
    path: string,
    body: unknown,
    onChunk: (chunk: ChatStreamChunk) => void,
    onDone: () => void | Promise<void>,
    onError: (err: string) => void,
    externalAbortSignal?: AbortSignal
  ) => {
    await _fetchSseStream(path, body, {
      onData: (dataStr) => {
        if (dataStr.trim() === '[DONE]') return true
        try {
          const raw = JSON.parse(dataStr)
          const chunk: ChatStreamChunk = {
            id: raw.id,
            content: raw.content || '',
            reasoning_content: raw.reasoning_content || raw.reasoningContent || '',
            model: raw.model || '',
            provider: raw.provider || '',
            done: !!raw.done,
            suggested_questions: raw.suggested_questions || undefined,
            emotion: raw.emotion || undefined,
            tool_calls: raw.tool_calls || undefined,
            tool_event: raw.tool_event || undefined,
            subagent_event: raw.subagent_event || undefined,
            task_event: raw.task_event || undefined,
            permission_request: raw.permission_request || undefined,
            iteration: raw.iteration ?? undefined,
            context_tokens: typeof raw.context_tokens === 'number' ? raw.context_tokens : undefined,
            context_max_tokens: typeof raw.context_max_tokens === 'number' ? raw.context_max_tokens : undefined,
            // 模型路由通知（如专业模式推理模型退化为主模型）：chat store 统一 toast（P1-2）
            notice: typeof raw.notice === 'string' && raw.notice ? raw.notice : undefined,
            usage: normalizeUsage(raw.usage),
            errCode: typeof raw.errCode === 'string' ? raw.errCode : undefined,
            // 落库消息持久 id（仅 done chunk 携带）：chat store 用其替换本地占位 id
            message_id: typeof raw.message_id === 'string' && raw.message_id ? raw.message_id : undefined,
            user_message_id: typeof raw.user_message_id === 'string' && raw.user_message_id ? raw.user_message_id : undefined,
          }
          onChunk(chunk)
          return chunk.done
        } catch (parseErr) {
          logger.warn('Stream chunk parse failed:', dataStr, parseErr)
          return false
        }
      },
      onDone,
      onError,
    }, externalAbortSignal, { requireDoneSignal: true })
  }

  const apiSseStream = async <T = unknown>(
    path: string,
    body: Record<string, unknown>,
    onEvent: (event: T) => void,
    onDone: () => void | Promise<void>,
    onError: (err: string) => void,
    externalAbortSignal?: AbortSignal
  ) => {
    await _fetchSseStream(path, body, {
      onData: (dataStr) => {
        try {
          onEvent(JSON.parse(dataStr) as T)
        } catch {
          // 忽略无法解析的行
        }
        return false
      },
      onDone,
      onError,
    }, externalAbortSignal)
  }

  const checkHealth = async (): Promise<boolean> => {
    try {
      const resp = await fetch(API_ENDPOINTS.HEALTH, {
        signal: AbortSignal.timeout(3000),
      })
      return resp.ok
    } catch {
      return false
    }
  }

  return {
    loading,
    error,
    abortController,
    abort,
    apiGet,
    apiPost,
    apiPut,
    apiPatch,
    apiDelete,
    apiStream,
    apiSseStream,
    truncateMessages,
    deleteMessage,
    checkHealth,
  }
}
