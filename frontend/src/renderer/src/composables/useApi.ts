import { ref } from 'vue'
import type { ChatStreamChunk } from '../types'

const BACKEND_URL = 'http://127.0.0.1:18000/api/v1'

const getApiUrl = (path: string) => `${BACKEND_URL}${path}`

export const useApi = () => {
  const loading = ref(false)
  const error = ref<string | null>(null)

  const apiGet = async <T>(path: string): Promise<T> => {
    loading.value = true
    error.value = null
    try {
      const resp = await fetch(getApiUrl(path), {
        signal: AbortSignal.timeout(15000),
      })
      if (!resp.ok) {
        const errData = await resp.json().catch(() => null)
        let errMsg = errData?.error?.message || errData?.detail || ''
        if (Array.isArray(errMsg)) {
          errMsg = errMsg.map((e: any) => e.msg || e.message || JSON.stringify(e)).join('; ')
        } else if (typeof errMsg === 'object' && errMsg !== null) {
          errMsg = JSON.stringify(errMsg)
        }
        throw new Error(errMsg || `API error: ${resp.status}`)
      }
      return await resp.json()
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  const apiPost = async <T>(path: string, body: any): Promise<T> => {
    loading.value = true
    error.value = null
    try {
      const resp = await fetch(getApiUrl(path), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(15000),
      })
      if (!resp.ok) {
        const errData = await resp.json().catch(() => null)
        let errMsg = errData?.error?.message || errData?.detail || ''
        if (Array.isArray(errMsg)) {
          errMsg = errMsg.map((e: any) => e.msg || e.message || JSON.stringify(e)).join('; ')
        } else if (typeof errMsg === 'object' && errMsg !== null) {
          errMsg = JSON.stringify(errMsg)
        }
        throw new Error(errMsg || `API error: ${resp.status}`)
      }
      return await resp.json()
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  const apiPatch = async <T>(path: string, body: any): Promise<T> => {
    loading.value = true
    error.value = null
    try {
      const resp = await fetch(getApiUrl(path), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(15000),
      })
      if (!resp.ok) {
        const errData = await resp.json().catch(() => null)
        let errMsg = errData?.error?.message || errData?.detail || ''
        if (Array.isArray(errMsg)) {
          errMsg = errMsg.map((e: any) => e.msg || e.message || JSON.stringify(e)).join('; ')
        } else if (typeof errMsg === 'object' && errMsg !== null) {
          errMsg = JSON.stringify(errMsg)
        }
        throw new Error(errMsg || `API error: ${resp.status}`)
      }
      return await resp.json()
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  const apiDelete = async <T = void>(path: string): Promise<T | void> => {
    loading.value = true
    error.value = null
    try {
      const resp = await fetch(getApiUrl(path), {
        method: 'DELETE',
        signal: AbortSignal.timeout(15000),
      })
      if (!resp.ok) {
        const errData = await resp.json().catch(() => null)
        let errMsg = errData?.error?.message || errData?.detail || ''
        if (Array.isArray(errMsg)) {
          errMsg = errMsg.map((e: any) => e.msg || e.message || JSON.stringify(e)).join('; ')
        } else if (typeof errMsg === 'object' && errMsg !== null) {
          errMsg = JSON.stringify(errMsg)
        }
        throw new Error(errMsg || `API error: ${resp.status}`)
      }
      if (resp.status === 204 || resp.headers.get('content-length') === '0') {
        return
      }
      const text = await resp.text()
      if (!text) return
      return JSON.parse(text)
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  const apiStream = async (
    path: string,
    body: any,
    onChunk: (chunk: ChatStreamChunk) => void,
    onDone: () => void,
    onError: (err: string) => void
  ) => {
    try {
      const resp = await fetch(getApiUrl(path), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(180000),
      })

      if (!resp.ok) {
        const errData = await resp.json().catch(() => null)
        throw new Error(errData?.error?.message || errData?.detail || `API error: ${resp.status}`)
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
            onDone()
            return
          }

          try {
            const chunk: ChatStreamChunk = JSON.parse(dataStr)
            onChunk(chunk)
            if (chunk.done) {
              onDone()
              return
            }
          } catch {
            continue
          }
        }
      }

      onDone()
    } catch (e: any) {
      onError(e.message)
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
    apiGet,
    apiPost,
    apiPatch,
    apiDelete,
    apiStream,
    checkHealth,
  }
}
