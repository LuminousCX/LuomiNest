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
  CONVERSATION_NOT_FOUND: '对话不存在，可能已被删除',
  AGENT_NOT_FOUND: 'Agent 不存在',
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

const extractErrorMessage = (errData: any, status: number): string => {
  // 1. 优先处理 err_code（符合工作区规则 "API 响应必须包含错误码"）
  const errCode = errData?.err_code ?? errData?.error?.code
  if (errCode && ERR_CODE_MESSAGES[errCode]) {
    return ERR_CODE_MESSAGES[errCode]
  }

  // 2. 兼容 error 为字符串的情况（TTS 接口等）
  let errMsg = ''
  if (typeof errData?.error === 'string') {
    errMsg = errData.error
  } else {
    errMsg = errData?.error?.message || errData?.detail || errData?.message || ''
  }

  // 3. 数组形式（FastAPI 校验错误）
  if (Array.isArray(errMsg)) {
    errMsg = errMsg.map((e: any) => e.msg || e.message || JSON.stringify(e)).join('; ')
  } else if (typeof errMsg === 'object' && errMsg !== null) {
    errMsg = JSON.stringify(errMsg)
  }

  // 4. 无具体消息时，按 HTTP 状态码返回友好提示
  return errMsg || statusToMessage(status)
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
      body?: any
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
      return JSON.parse(text)
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  const apiGet = <T>(path: string): Promise<T> => request<T>(path)

  const apiPost = <T>(path: string, body?: any): Promise<T> =>
    request<T>(path, { method: 'POST', body })

  const apiPut = <T>(path: string, body: any): Promise<T> =>
    request<T>(path, { method: 'PUT', body })

  const apiPatch = <T>(path: string, body?: any): Promise<T> =>
    request<T>(path, { method: 'PATCH', body })

  const apiDelete = <T = void>(path: string): Promise<T | void> =>
    request<T>(path, { method: 'DELETE' })

  const truncateMessages = (convId: string, keepCount: number): Promise<void> =>
    apiPatch(`/chat/conversations/${convId}/messages`, { keep_count: keepCount })

  const deleteMessage = (convId: string, messageId: string): Promise<void> =>
    apiDelete(`/chat/conversations/${convId}/messages/${messageId}`)

  const apiStream = async (
    path: string,
    body: any,
    onChunk: (chunk: ChatStreamChunk) => void,
    onDone: () => void | Promise<void>,
    onError: (err: string) => void,
    externalAbortSignal?: AbortSignal
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

      const processLine = (line: string): boolean => {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data: ')) return false
        const dataStr = trimmed.slice(6)
        if (!dataStr.trim()) return false
        if (dataStr.trim() === '[DONE]') {
          return true
        }

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
      }

      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          if (value) {
            buffer += decoder.decode(value, { stream: false })
          } else {
            buffer += decoder.decode()
          }
          const lines = buffer.split('\n')
          for (const line of lines) {
            if (processLine(line)) {
              await onDone()
              return
            }
          }
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (processLine(line)) {
            await onDone()
            return
          }
        }
      }

      await onDone()
    } catch (e: any) {
      if (e.name === 'AbortError') {
        return
      }
      onError(e.message)
    } finally {
      abortController.value = null
    }
  }

  const apiSseStream = async <T = unknown>(
    path: string,
    body: Record<string, unknown>,
    onEvent: (event: T) => void,
    onDone: () => void | Promise<void>,
    onError: (err: string) => void,
    externalAbortSignal?: AbortSignal
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
          if (value) {
            buffer += decoder.decode(value, { stream: false })
          } else {
            buffer += decoder.decode()
          }
          const lines = buffer.split('\n')
          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed.startsWith('data: ')) continue
            const dataStr = trimmed.slice(6)
            if (!dataStr.trim()) continue
            try {
              const event: T = JSON.parse(dataStr)
              onEvent(event)
            } catch {
              continue
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

          try {
            const event: T = JSON.parse(dataStr)
            onEvent(event)
          } catch {
            continue
          }
        }
      }

      await onDone()
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === 'AbortError') {
        throw e
      }
      const message = e instanceof Error ? e.message : String(e)
      onError(message)
    } finally {
      abortController.value = null
    }
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
