import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { RegistrySource } from '../types/marketplace'
import { useApi } from '../composables/useApi'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('RegistrySource')

const getErrorMessage = (e: unknown): string => {
  if (e instanceof Error) return e.message
  return String(e)
}

export interface RegistrySourcesResponse {
  activeSourceId: string
  sources: RegistrySource[]
}

export const useRegistrySourceStore = defineStore('registrySource', () => {
  const sources = ref<RegistrySource[]>([])
  const activeSourceId = ref<string>('')
  const loading = ref(false)
  const switching = ref(false)
  const error = ref<string | null>(null)

  const activeSource = computed<RegistrySource | null>(() => {
    return sources.value.find(s => s.id === activeSourceId.value) || sources.value[0] || null
  })

  const healthySources = computed<RegistrySource[]>(() => {
    return sources.value.filter(s => s.enabled && s.healthy !== false)
  })

  /**
   * 拉取发布源列表，默认同时测试延迟。
   */
  const fetchSources = async (ping: boolean = true) => {
    loading.value = true
    error.value = null
    try {
      const api = useApi()
      const data = await api.apiGet<RegistrySourcesResponse>(
        `/marketplace/registry/sources?ping=${ping}`
      )
      sources.value = data.sources || []
      activeSourceId.value = data.activeSourceId || ''
    } catch (e: unknown) {
      error.value = getErrorMessage(e)
      logger.error('Failed to fetch registry sources:', error.value)
    } finally {
      loading.value = false
    }
  }

  /**
   * 手动重新测试所有发布源延迟。
   */
  const pingSources = async () => {
    return fetchSources(true)
  }

  /**
   * 切换到指定发布源。
   * 后端会再次 ping 该源确认可用后才切换。
   */
  const switchSource = async (sourceId: string) => {
    switching.value = true
    error.value = null
    try {
      const api = useApi()
      const result = await api.apiPost<{ activeSourceId: string; latencyMs: number }>(
        `/marketplace/registry/source/${sourceId}`
      )
      activeSourceId.value = result.activeSourceId
      // 刷新列表以同步 active 状态
      await fetchSources(false)
      return result
    } catch (e: unknown) {
      const msg = getErrorMessage(e)
      error.value = msg
      logger.error('Failed to switch registry source:', msg)
      throw e
    } finally {
      switching.value = false
    }
  }

  /**
   * 获取延迟对应的展示状态。
   */
  function getLatencyStatus(source: RegistrySource): { label: string; className: string } {
    if (!source.enabled || source.healthy === false) {
      return { label: '不可用', className: 'unavailable' }
    }
    if (source.latencyMs === undefined || source.latencyMs < 0) {
      return { label: '未测试', className: 'unknown' }
    }
    if (source.latencyMs <= 500) {
      return { label: `${source.latencyMs}ms`, className: 'fast' }
    }
    if (source.latencyMs <= 2000) {
      return { label: `${source.latencyMs}ms`, className: 'medium' }
    }
    return { label: `${source.latencyMs}ms`, className: 'slow' }
  }

  return {
    sources,
    activeSourceId,
    activeSource,
    healthySources,
    loading,
    switching,
    error,
    fetchSources,
    pingSources,
    switchSource,
    getLatencyStatus,
  }
})
