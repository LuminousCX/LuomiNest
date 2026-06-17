import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { RepoSource, RepoSourceType, RepoSubMarket, MarketplaceItem } from '../types/marketplace'
import { useApi } from '../composables/useApi'

const REPO_SOURCES_KEY = 'luominest-repo-sources-active'

export interface SyncedItemsResult {
  items: MarketplaceItem[]
  total: number
  sourceId: string
  subMarketId?: string
  syncedAt?: string
  fromCache?: boolean
}

export const useRepoSourceStore = defineStore('repoSource', () => {
  const sources = ref<RepoSource[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const activeSourceId = ref<string>(loadActiveSourceId())

  // 同步后的远程条目缓存（按 sourceId 索引）
  const syncedItems = ref<Record<string, MarketplaceItem[]>>({})
  const syncedItemsLoading = ref<Record<string, boolean>>({})

  function loadActiveSourceId(): string {
    try {
      const stored = localStorage.getItem(REPO_SOURCES_KEY)
      if (stored && sources.value.some(s => s.id === stored)) {
        return stored
      }
      return sources.value[0]?.id || ''
    } catch {
      return sources.value[0]?.id || ''
    }
  }

  const saveActiveSourceId = (id: string) => {
    localStorage.setItem(REPO_SOURCES_KEY, id)
  }

  const activeSource = computed(() => {
    return sources.value.find(s => s.id === activeSourceId.value) || sources.value[0] || null
  })

  const enabledSources = computed(() => {
    return sources.value.filter(s => s.enabled)
  })

  const githubSources = computed(() => {
    return sources.value.filter(s => s.type === 'github')
  })

  const cloudSources = computed(() => {
    return sources.value.filter(s => s.type === 'cloud')
  })

  const cdnSources = computed(() => {
    return sources.value.filter(s => s.type === 'cdn')
  })

  const customSources = computed(() => {
    return sources.value.filter(s => s.type === 'custom')
  })

  const groupedSources = computed(() => {
    const groups: { type: RepoSourceType; label: string; icon: string; items: RepoSource[] }[] = [
      { type: 'github', label: 'GitHub', icon: 'Github', items: githubSources.value },
      { type: 'cloud', label: '云端', icon: 'Cloud', items: cloudSources.value },
      { type: 'cdn', label: 'CDN', icon: 'Globe', items: cdnSources.value },
      { type: 'custom', label: '自定义', icon: 'Plus', items: customSources.value },
    ]
    return groups.filter(g => g.items.length > 0)
  })

  // 当前活跃来源的已同步条目
  const activeSourceItems = computed<MarketplaceItem[]>(() => {
    return syncedItems.value[activeSourceId.value] || []
  })

  const fetchSources = async () => {
    loading.value = true
    error.value = null
    try {
      const api = useApi()
      const data = await api.apiGet<RepoSource[]>('/repo-sources')
      sources.value = data
    } catch (e: any) {
      error.value = e.message
      sources.value = getDefaultSources()
    } finally {
      loading.value = false
    }
  }

  const setActiveSource = (sourceId: string) => {
    activeSourceId.value = sourceId
    saveActiveSourceId(sourceId)
    // 切换来源时自动加载缓存条目
    fetchSourceItems(sourceId)
  }

  const toggleSource = async (sourceId: string) => {
    try {
      const api = useApi()
      const updated = await api.apiPost<RepoSource>(`/repo-sources/${sourceId}/toggle`)
      const idx = sources.value.findIndex(s => s.id === sourceId)
      if (idx >= 0) {
        sources.value[idx] = updated
      }
    } catch (e: any) {
      error.value = e?.message || '操作失败'
    }
  }

  const unlinkSubMarket = async (sourceId: string, subMarketId: string) => {
    try {
      const api = useApi()
      const updated = await api.apiPatch<RepoSource>(`/repo-sources/${sourceId}/sub-markets/${subMarketId}/unlink`)
      const idx = sources.value.findIndex(s => s.id === sourceId)
      if (idx >= 0) {
        sources.value[idx] = updated
      }
    } catch (e: any) {
      error.value = e?.message || '操作失败'
    }
  }

  const linkSubMarket = async (sourceId: string, subMarketId: string) => {
    try {
      const api = useApi()
      const updated = await api.apiPatch<RepoSource>(`/repo-sources/${sourceId}/sub-markets/${subMarketId}/link`)
      const idx = sources.value.findIndex(s => s.id === sourceId)
      if (idx >= 0) {
        sources.value[idx] = updated
      }
    } catch (e: any) {
      error.value = e?.message || '操作失败'
    }
  }

  const syncSource = async (sourceId: string, force: boolean = false) => {
    try {
      const api = useApi()
      const idx = sources.value.findIndex(s => s.id === sourceId)
      if (idx >= 0) {
        sources.value[idx] = { ...sources.value[idx], status: 'loading' }
      }
      syncedItemsLoading.value = { ...syncedItemsLoading.value, [sourceId]: true }

      const updated = await api.apiPost<RepoSource>(`/repo-sources/${sourceId}/sync${force ? '?force=true' : ''}`)
      if (idx >= 0) {
        sources.value[idx] = updated
      }

      // 同步完成后获取条目
      await fetchSourceItems(sourceId)
    } catch (e: any) {
      error.value = e.message
      const idx = sources.value.findIndex(s => s.id === sourceId)
      if (idx >= 0) {
        sources.value[idx] = { ...sources.value[idx], status: 'error', errorMessage: e.message }
      }
    } finally {
      syncedItemsLoading.value = { ...syncedItemsLoading.value, [sourceId]: false }
    }
  }

  const syncSubMarket = async (sourceId: string, subMarketId: string, force: boolean = false) => {
    try {
      const api = useApi()
      const result = await api.apiPost<SyncedItemsResult>(
        `/repo-sources/${sourceId}/sub-markets/${subMarketId}/sync${force ? '?force=true' : ''}`
      )
      // 更新该来源的条目缓存
      await fetchSourceItems(sourceId)
      return result
    } catch (e: any) {
      error.value = e.message
      return null
    }
  }

  /**
   * 获取仓库来源下的已缓存市场条目（不触发网络请求，仅读取后端缓存）
   */
  const fetchSourceItems = async (sourceId: string) => {
    try {
      const api = useApi()
      const result = await api.apiGet<SyncedItemsResult>(`/repo-sources/${sourceId}/items`)
      syncedItems.value = { ...syncedItems.value, [sourceId]: result.items || [] }
    } catch (e: any) {
      // 静默失败，不影响用户体验
      console.warn('[RepoSource] Failed to fetch source items:', e.message)
    }
  }

  /**
   * 获取仓库来源下指定类型的市场条目
   */
  const fetchSourceItemsByType = async (sourceId: string, type: string) => {
    try {
      const api = useApi()
      const result = await api.apiGet<SyncedItemsResult>(`/repo-sources/${sourceId}/items?type=${type}`)
      return result.items || []
    } catch (e: any) {
      console.warn('[RepoSource] Failed to fetch source items by type:', e.message)
      return []
    }
  }

  /**
   * 清除仓库来源的缓存
   */
  const clearSourceCache = async (sourceId: string) => {
    try {
      const api = useApi()
      await api.apiDelete(`/repo-sources/${sourceId}/cache`)
      // 清除本地缓存
      const newSynced = { ...syncedItems.value }
      delete newSynced[sourceId]
      syncedItems.value = newSynced
    } catch (e: any) {
      error.value = e.message
    }
  }

  const addCustomSource = async (data: { name: string; url: string; description?: string }) => {
    try {
      const api = useApi()
      const created = await api.apiPost<RepoSource>('/repo-sources', {
        type: 'custom',
        name: data.name,
        url: data.url,
        description: data.description || '',
        enabled: true,
        sub_markets: [],
      })
      sources.value.push(created)
      return created
    } catch (e: any) {
      error.value = e.message
      return null
    }
  }

  const deleteSource = async (sourceId: string) => {
    try {
      const api = useApi()
      await api.apiDelete(`/repo-sources/${sourceId}`)
      sources.value = sources.value.filter(s => s.id !== sourceId)
      // 清除本地条目缓存
      const newSynced = { ...syncedItems.value }
      delete newSynced[sourceId]
      syncedItems.value = newSynced
      if (activeSourceId.value === sourceId) {
        activeSourceId.value = sources.value[0]?.id || ''
        saveActiveSourceId(activeSourceId.value)
      }
    } catch (e: any) {
      error.value = e.message
    }
  }

  function getDefaultSources(): RepoSource[] {
    return [
      {
        id: 'github-official',
        type: 'github',
        name: 'GitHub 官方仓库',
        url: 'https://github.com/LuminousCX',
        description: 'LuminousCX 官方 GitHub 仓库，包含技能、智能体和插件',
        enabled: true,
        subMarkets: [
          { id: 'gh-skills', name: 'Skills 市场', type: 'skill', url: 'https://github.com/LuminousCX/skills', description: 'LuminousCX 官方技能仓库', linked: true },
          { id: 'gh-agents', name: 'Agents 市场', type: 'agent', url: 'https://github.com/LuminousCX/agents', description: 'LuminousCX 官方智能体仓库', linked: true },
          { id: 'gh-plugins', name: 'Plugins 市场', type: 'plugin', url: 'https://github.com/LuminousCX/plugins', description: 'LuminousCX 官方插件仓库', linked: true },
        ],
        status: 'idle',
      },
      {
        id: 'cloud-official',
        type: 'cloud',
        name: '云端仓库',
        description: 'LuminousCX 云端托管仓库',
        enabled: false,
        subMarkets: [],
        status: 'idle',
      },
      {
        id: 'cdn-official',
        type: 'cdn',
        name: 'CDN 仓库',
        description: 'CDN 加速分发仓库',
        enabled: false,
        subMarkets: [],
        status: 'idle',
      },
    ]
  }

  return {
    sources,
    loading,
    error,
    activeSourceId,
    activeSource,
    enabledSources,
    githubSources,
    cloudSources,
    cdnSources,
    customSources,
    groupedSources,
    syncedItems,
    syncedItemsLoading,
    activeSourceItems,
    fetchSources,
    setActiveSource,
    toggleSource,
    unlinkSubMarket,
    linkSubMarket,
    syncSource,
    syncSubMarket,
    fetchSourceItems,
    fetchSourceItemsByType,
    clearSourceCache,
    addCustomSource,
    deleteSource,
  }
})
