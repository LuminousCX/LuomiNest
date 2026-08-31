import { ref } from 'vue'
import type { ChatStreamChunk } from '../types'
import { API_ENDPOINTS } from '../config/api'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('Api')

const getApiUrl = (path: string) => `${API_ENDPOINTS.V1}${path}`

// HTTP 状态码到中文友好提示的映射
const HTTP_STATUS_MESSAGES: Record<number, string> = {
  400: '请求参数错误，请检查输入',
  401: '未授权，请检查 API Key 配置',
  403: '无权限访问该资源',
  404: '请求的资源不存在',
  408: '请求超时，请检查网络后重试',
  429: '请求过于频繁，请稍后重试',
  500: '服务器内部错误，请查看后端日志',
  502: '网关错误，后端服务可能未启动',
  503: '服务暂不可用，请稍后重试',
  504: '网关超时，请检查后端服务状态',
}

// 后端 err_code 到中文友好提示的映射
const ERR_CODE_MESSAGES: Record<string, string> = {
  LLM_ALL_PROVIDERS_FAILED: '所有 AI 模型均不可用，请在设置中检查模型配置',
  LLM_PROVIDER_UNAUTHORIZED: 'AI 模型授权失败，请检查 API Key',
  LLM_PROVIDER_UNAVAILABLE: 'AI 模型服务暂不可用，请稍后重试',
  LLM_RATE_LIMITED: 'AI 模型请求过于频繁，请稍后重试',
  TTS_NO_ENGINE: '未安装语音合成引擎，语音功能不可用',
  TTS_SYNTHESIS_FAILED: '语音合成失败',
  TTS_MODEL_NOT_FOUND: '语音模型未下载，请参考后端日志安装',
  MEMORY_NOT_FOUND: '记忆数据不存在',
  MEMORY_FACT_NOT_FOUND: '记忆条目不存在',
  MEMORY_CATEGORY_INVALID: '记忆分类无效',
  CONVERSATION_NOT_FOUND: '对话不存在，可能已被删除',
  AGENT_NOT_FOUND: 'Agent 不存在',
  AGENT_LIMIT_REACHED: 'Agent 数量已达上限（10 个）',
  AGENT_NAME_DUPLICATED: 'Agent 名称已存在，请换一个名称',
  A2A_MAX_DEPTH_EXCEEDED: '已达到最大 Agent 调用深度，无法继续递归调用',
  MCP_SERVER_NOT_FOUND: 'MCP 服务器不存在',
  MCP_CONFIG_INVALID: 'MCP 配置无效，请检查参数',
  MCP_OPERATION_FAILED: 'MCP 操作失败，请查看后端日志',
  MARKETPLACE_ITEM_NOT_FOUND: '市场条目不存在',
  MARKETPLACE_ALREADY_INSTALLED: '该内容已安装，无需重复安装',
  MARKETPLACE_UNINSTALL_FAILED: '卸载失败，请查看后端日志',
  MARKETPLACE_SNAPSHOT_FAILED: '生成快照失败，请查看后端日志',
  MARKETPLACE_SOURCE_NOT_FOUND: '发布源不存在',
  MARKETPLACE_SOURCE_DISABLED: '该发布源已被禁用，无法切换',
  MARKETPLACE_SOURCE_UNAVAILABLE: '发布源当前不可用，请检查网络',
  MARKETPLACE_SOURCE_SWITCH_FAILED: '切换发布源失败，请稍后重试',
  WORKFLOW_SESSION_NOT_FOUND: '工作流会话不存在或已结束',
  WORKFLOW_RECORD_NOT_FOUND: '工具调用记录不存在',
  WORKFLOW_TEMPLATE_NOT_FOUND: '工作流模板不存在',
  SCHEDULER_TASK_NOT_FOUND: '定时任务不存在',
  SCHEDULER_NOT_RUNNING: '调度器未启动，请稍后重试',
  SCHEDULER_TASK_INVALID: '定时任务配置无效，请检查表达式',
  SUBMARKET_NOT_FOUND: '子市场不存在',
}

const statusToMessage = (status: number): string =>
  HTTP_STATUS_MESSAGES[status] || `请求失败 (${status})`

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
  // 1. 统一信封 error.code（LuomiNestError 家族 + HTTPException 兜底信封均产出）
  const errCode = typeof data.error === 'object' ? data.error?.code : undefined
  if (errCode && ERR_CODE_MESSAGES[errCode]) {
    return ERR_CODE_MESSAGES[errCode]
  }

  // 2. 兼容 error 为字符串的情况（TTS 接口等）
  let errMsg: unknown = ''
  if (typeof data.error === 'string') {
    errMsg = data.error
  } else {
    errMsg = data.error?.message || data.detail || data.message || ''
  }

  // 3. 数组形式（FastAPI 校验错误）
  if (Array.isArray(errMsg)) {
    errMsg = errMsg.map((e: unknown) => {
      if (typeof e === 'object' && e !== null) {
        const obj = e as { msg?: string; message?: string }
        return obj.msg || obj.message || JSON.stringify(e)
      }
      return JSON.stringify(e)
    }).join('; ')
  } else if (typeof errMsg === 'object' && errMsg !== null) {
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
    } = {}
  ): Promise<T> => {
    const { method = 'GET', body, timeout = 15000 } = options
    
    loading.value = true
    error.value = null
    
    try {
      const authHeaders = await getAuthHeaders()
      const headers: Record<string, string> = { ...authHeaders }
      if (body) {
        headers['Content-Type'] = 'application/json'
      }

      const fetchOptions: RequestInit = {
        method,
        signal: AbortSignal.timeout(timeout),
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

  const apiGet = <T>(path: string): Promise<T> => request<T>(path)

  const apiPost = <T>(path: string, body?: unknown): Promise<T> =>
    request<T>(path, { method: 'POST', body })

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
  ) => {
    const controller = new AbortController()
    abortController.value = controller

    const signal = externalAbortSignal
      ? AbortSignal.any([controller.signal, externalAbortSignal])
      : controller.signal

    try {
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
      if (!reader) throw new Error('无法读取响应流，请检查后端服务')

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
            await handlers.onDone()
            return
          }
        }
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
            iteration: raw.iteration ?? undefined,
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
    }, externalAbortSignal)
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
