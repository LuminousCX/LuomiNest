import { ref } from 'vue'
import type { ChatStreamChunk } from '../types'

const BACKEND_URL = 'http://127.0.0.1:18000/api/v1'

const getApiUrl = (path: string) => `${BACKEND_URL}${path}`

const extractErrorMessage = (errData: any, status: number): string => {
  let errMsg = errData?.error?.message || errData?.detail || ''
  if (Array.isArray(errMsg)) {
    errMsg = errMsg.map((e: any) => e.msg || e.message || JSON.stringify(e)).join('; ')
  } else if (typeof errMsg === 'object' && errMsg !== null) {
    errMsg = JSON.stringify(errMsg)
  }
  return errMsg || `API error: ${status}`
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
      const fetchOptions: RequestInit = {
        method,
        signal: AbortSignal.timeout(timeout),
      }
      
      if (body) {
        fetchOptions.headers = { 'Content-Type': 'application/json' }
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

  const apiPost = <T>(path: string, body: any): Promise<T> =>
    request<T>(path, { method: 'POST', body })

  const apiPut = <T>(path: string, body: any): Promise<T> =>
    request<T>(path, { method: 'PUT', body })

  const apiPatch = <T>(path: string, body: any): Promise<T> =>
    request<T>(path, { method: 'PATCH', body })

  const apiDelete = <T = void>(path: string): Promise<T | void> =>
    request<T>(path, { method: 'DELETE' })

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
      const resp = await fetch(getApiUrl(path), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal,
      })

      if (!resp.ok) {
        const errData = await resp.json().catch(() => null)
        throw new Error(extractErrorMessage(errData, resp.status))
      }

      const reader = resp.body?.getReader()
      if (!reader) throw new Error('No readable stream')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const dataStr = trimmed.slice(6)
          if (!dataStr.trim()) continue
          if (dataStr.trim() === '[DONE]') {
            await onDone()
            return
          }

          try {
            const chunk: ChatStreamChunk = JSON.parse(dataStr)
            onChunk(chunk)
            if (chunk.done) {
              await onDone()
              return
            }
          } catch {
            continue
          }
        }
      }

      await onDone()
    } catch (e: any) {
      if (e.name === 'AbortError') {
        await onDone()
        return
      }
      onError(e.message)
    } finally {
      abortController.value = null
    }
  }

  const apiSseStream = async <T = any>(
    path: string,
    body: any,
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
      const resp = await fetch(getApiUrl(path), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal,
      })

      if (!resp.ok) {
        const errData = await resp.json().catch(() => null)
        throw new Error(extractErrorMessage(errData, resp.status))
      }

      const reader = resp.body?.getReader()
      if (!reader) throw new Error('No readable stream')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

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
    } catch (e: any) {
      if (e.name === 'AbortError') {
        await onDone()
        return
      }
      onError(e.message)
    } finally {
      abortController.value = null
    }
  }

  const checkHealth = async (): Promise<boolean> => {
    try {
      const resp = await fetch('http://127.0.0.1:18000/health', {
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
    checkHealth,
  }
}
