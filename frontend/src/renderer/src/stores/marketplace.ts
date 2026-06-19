import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  MarketplaceType,
  MarketplaceItem,
  MarketplaceCategory,
  MarketplaceFilter,
  MarketplaceReview,
  MarketplaceReviewReply,
  SearchSuggestion,
  InstallProgress,
  ItemStats,
  LeaderboardItem,
} from '../types/marketplace'
import {
  PLUGIN_CATEGORIES,
  SKILL_CATEGORIES,
  AGENT_CATEGORIES,
  MOCK_PLUGINS,
  MOCK_SKILLS,
  MOCK_AGENTS,
  MOCK_REVIEWS,
} from '../config/marketplace-data'

const SEARCH_HISTORY_KEY = 'luominest-marketplace-search-history'
const FAVORITES_KEY = 'luominest-marketplace-favorites'

const ALL_CATEGORIES = [...PLUGIN_CATEGORIES, ...SKILL_CATEGORIES, ...AGENT_CATEGORIES]

export const useMarketplaceStore = defineStore('marketplace', () => {
  const pluginItems = ref<MarketplaceItem[]>([...MOCK_PLUGINS])
  const skillItems = ref<MarketplaceItem[]>([...MOCK_SKILLS])
  const agentItems = ref<MarketplaceItem[]>([...MOCK_AGENTS])
  const loading = ref(false)
  const searchQuery = ref('')
  const searchHistory = ref<string[]>(loadSearchHistory())
  const showSearchSuggestions = ref(false)
  const pluginFilter = ref<MarketplaceFilter>({ sortBy: 'popular' })
  const skillFilter = ref<MarketplaceFilter>({ sortBy: 'popular' })
  const agentFilter = ref<MarketplaceFilter>({ sortBy: 'popular' })
  const installProgress = ref<Record<string, InstallProgress>>({})
  const reviews = ref<Record<string, MarketplaceReview[]>>(loadMockReviews())
  const favorites = ref<string[]>(loadFavorites())

  const syncFavoriteFlags = () => {
    const syncItems = (items: MarketplaceItem[]) => {
      for (const item of items) {
        item.isFavorite = favorites.value.includes(item.id)
      }
    }
    syncItems(pluginItems.value)
    syncItems(skillItems.value)
    syncItems(agentItems.value)
  }

  syncFavoriteFlags()

  const activeIntervals = new Set<ReturnType<typeof setInterval>>()
  const cancelledInstalls = new Set<string>()

  function loadSearchHistory(): string[] {
    try {
      const stored = localStorage.getItem(SEARCH_HISTORY_KEY)
      return stored ? JSON.parse(stored) : []
    } catch {
      return []
    }
  }

  const saveSearchHistory = (history: string[]) => {
    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(history.slice(0, 20)))
  }

  function loadFavorites(): string[] {
    try {
      const stored = localStorage.getItem(FAVORITES_KEY)
      return stored ? JSON.parse(stored) : []
    } catch {
      return []
    }
  }

  const saveFavorites = () => {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites.value))
  }

  const isFavorite = (itemId: string): boolean => {
    return favorites.value.includes(itemId)
  }

  function loadMockReviews(): Record<string, MarketplaceReview[]> {
    const result: Record<string, MarketplaceReview[]> = {}
    for (const [itemId, itemReviews] of Object.entries(MOCK_REVIEWS)) {
      result[itemId] = itemReviews.map(r => ({
        ...r,
        replies: r.replies?.map(rp => ({
          ...rp,
        })),
      }))
    }
    return result
  }

  const getCategories = (type: MarketplaceType): MarketplaceCategory[] => {
    if (type === 'plugin') return PLUGIN_CATEGORIES
    if (type === 'skill') return SKILL_CATEGORIES
    return AGENT_CATEGORIES
  }

  const getItems = (type: MarketplaceType): MarketplaceItem[] => {
    if (type === 'plugin') return pluginItems.value
    if (type === 'skill') return skillItems.value
    return agentItems.value
  }

  const getFilter = (type: MarketplaceType) => {
    if (type === 'plugin') return pluginFilter
    if (type === 'skill') return skillFilter
    return agentFilter
  }

  const allItems = computed(() => [...pluginItems.value, ...skillItems.value, ...agentItems.value])

  const featuredItems = computed(() => {
    return allItems.value.filter(i => i.featured).sort((a, b) => b.rating - a.rating).slice(0, 6)
  })

  const featuredPlugins = computed(() => {
    return pluginItems.value.filter(i => i.featured).sort((a, b) => b.rating - a.rating)
  })

  const featuredSkills = computed(() => {
    return skillItems.value.filter(i => i.featured).sort((a, b) => b.rating - a.rating)
  })

  const featuredAgents = computed(() => {
    return agentItems.value.filter(i => i.featured).sort((a, b) => b.rating - a.rating)
  })

  const filteredPluginItems = computed(() => {
    return applyFilters(pluginItems.value, pluginFilter.value)
  })

  const filteredSkillItems = computed(() => {
    return applyFilters(skillItems.value, skillFilter.value)
  })

  const filteredAgentItems = computed(() => {
    return applyFilters(agentItems.value, agentFilter.value)
  })

  const applyFilters = (items: MarketplaceItem[], filter: MarketplaceFilter): MarketplaceItem[] => {
    let result = [...items]

    if (filter.category && filter.category !== 'all') {
      result = result.filter(i => {
        if (i.category === filter.category) return true
        const parent = ALL_CATEGORIES.find(c => c.id === filter.category)
        if (parent?.children?.some(c => c.id === i.category)) return true
        return false
      })
    }

    if (filter.tags && filter.tags.length > 0) {
      result = result.filter(i =>
        filter.tags!.some(tagId => i.tags.some(t => t.id === tagId))
      )
    }

    if (filter.installStatus && filter.installStatus !== 'all') {
      result = result.filter(i => i.installStatus === filter.installStatus)
    }

    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase().trim()
      result = result.filter(i =>
        i.name.toLowerCase().includes(q) ||
        i.description.toLowerCase().includes(q) ||
        i.summary.toLowerCase().includes(q) ||
        i.tags.some(t => t.name.toLowerCase().includes(q)) ||
        i.author.name.toLowerCase().includes(q)
      )
    }

    switch (filter.sortBy) {
      case 'popular':
        result.sort((a, b) => b.downloadCount - a.downloadCount)
        break
      case 'newest':
        result.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
        break
      case 'rating':
        result.sort((a, b) => b.rating - a.rating)
        break
      case 'downloads':
        result.sort((a, b) => b.installedCount - a.installedCount)
        break
    }

    return result
  }

  const searchSuggestions = computed((): SearchSuggestion[] => {
    const suggestions: SearchSuggestion[] = []

    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase().trim()
      const matched = allItems.value.filter(i =>
        i.name.toLowerCase().includes(q) || i.summary.toLowerCase().includes(q)
      ).slice(0, 5)
      for (const item of matched) {
        suggestions.push({ text: item.name, type: 'suggestion' })
      }

      for (const cat of ALL_CATEGORIES) {
        if (cat.name.toLowerCase().includes(q) && cat.id !== 'all') {
          suggestions.push({ text: cat.name, type: 'category' })
        }
        for (const child of cat.children || []) {
          if (child.name.toLowerCase().includes(q)) {
            suggestions.push({ text: child.name, type: 'category' })
          }
        }
      }
    } else {
      for (const h of searchHistory.value.slice(0, 5)) {
        suggestions.push({ text: h, type: 'history' })
      }
    }

    return suggestions.slice(0, 8)
  })

  const getItemById = (id: string): MarketplaceItem | undefined => {
    return allItems.value.find(i => i.id === id)
  }

  const getItemByTypeAndId = (type: MarketplaceType, id: string): MarketplaceItem | undefined => {
    return getItems(type).find(i => i.id === id)
  }

  const performSearch = (query: string) => {
    searchQuery.value = query
    if (query.trim()) {
      searchHistory.value = [
        query.trim(),
        ...searchHistory.value.filter(h => h !== query.trim()),
      ].slice(0, 20)
      saveSearchHistory(searchHistory.value)
    }
    showSearchSuggestions.value = false
  }

  const clearSearch = () => {
    searchQuery.value = ''
    showSearchSuggestions.value = false
  }

  const removeSearchHistoryEntry = (entry: string) => {
    searchHistory.value = searchHistory.value.filter(h => h !== entry)
    saveSearchHistory(searchHistory.value)
  }

  const clearSearchHistory = () => {
    searchHistory.value = []
    saveSearchHistory([])
  }

  const setFilter = (type: MarketplaceType, filter: Partial<MarketplaceFilter>) => {
    const target = type === 'plugin' ? pluginFilter : type === 'skill' ? skillFilter : agentFilter
    target.value = { ...target.value, ...filter }
  }

  const resetFilters = (type: MarketplaceType) => {
    const target = type === 'plugin' ? pluginFilter : type === 'skill' ? skillFilter : agentFilter
    target.value = { sortBy: 'popular' }
    clearSearch()
  }

  const toggleFavorite = (itemId: string) => {
    const idx = favorites.value.indexOf(itemId)
    if (idx >= 0) {
      favorites.value.splice(idx, 1)
    } else {
      favorites.value.push(itemId)
    }
    saveFavorites()
    syncFavoriteFlags()
  }

  const favoriteItems = computed(() => {
    return allItems.value.filter(i => i.isFavorite)
  })

  const favoritePlugins = computed(() => {
    return pluginItems.value.filter(i => i.isFavorite)
  })

  const favoriteSkills = computed(() => {
    return skillItems.value.filter(i => i.isFavorite)
  })

  const favoriteAgents = computed(() => {
    return agentItems.value.filter(i => i.isFavorite)
  })

  const setProgress = (itemId: string, progress: InstallProgress) => {
    installProgress.value = { ...installProgress.value, [itemId]: progress }
  }

  const setInstallProgress = (itemId: string, progress: InstallProgress) => {
    setProgress(itemId, progress)
  }

  // 轮询后端下载进度
  const _progressTimers: Record<string, ReturnType<typeof setInterval>> = {}

  const startProgressPolling = (itemId: string) => {
    stopProgressPolling(itemId)
    // 延迟导入避免循环依赖
    import('../composables/useApi').then(({ useApi }) => {
      const api = useApi()
      _progressTimers[itemId] = setInterval(async () => {
        try {
          const result = await api.apiGet<InstallProgress>(`/marketplace/download-progress/${itemId}`)
          setProgress(itemId, result)
          if (result.status === 'installed' || result.status === 'error') {
            stopProgressPolling(itemId)
            if (result.status === 'installed') {
              const updateInstalledItem = (items: MarketplaceItem[]) => {
                const item = items.find(i => i.id === itemId)
                if (item) {
                  item.installStatus = 'installed'
                  item.installedCount += 1
                  item.downloadCount += 1
                }
              }
              updateInstalledItem(pluginItems.value)
              updateInstalledItem(skillItems.value)
              updateInstalledItem(agentItems.value)
              // 同步 repoSourceStore 中对应条目的状态
              import('../stores/repo-source').then(({ useRepoSourceStore }) => {
                const repoStore = useRepoSourceStore()
                for (const items of Object.values(repoStore.syncedItems)) {
                  const ri = (items as MarketplaceItem[]).find(i => i.id === itemId)
                  if (ri) {
                    ri.installStatus = 'installed'
                    ri.downloadCount += 1
                  }
                }
              })
              // 同步后端统计数据 + 排行榜
              syncAllStats()
              setTimeout(() => {
                removeProgress(itemId)
              }, 2000)
            }
          }
        } catch {
          stopProgressPolling(itemId)
        }
      }, 500)
    })
  }

  const stopProgressPolling = (itemId: string) => {
    if (_progressTimers[itemId]) {
      clearInterval(_progressTimers[itemId])
      delete _progressTimers[itemId]
    }
  }

  const removeProgress = (itemId: string) => {
    const { [itemId]: _, ...rest } = installProgress.value
    installProgress.value = rest
  }

  const cleanupInterval = (intervalId: ReturnType<typeof setInterval>) => {
    activeIntervals.delete(intervalId)
    clearInterval(intervalId)
  }

  const startInstall = (itemId: string) => {
    const progress: InstallProgress = {
      itemId,
      status: 'downloading',
      progress: 0,
      message: '正在下载...',
    }
    setProgress(itemId, progress)
    simulateInstall(itemId)
  }

  const simulateInstall = (itemId: string) => {
    let progress = 0
    const intervalId = setInterval(() => {
      progress += Math.random() * 15 + 5
      if (progress >= 100) {
        progress = 100
        cleanupInterval(intervalId)
        const current = installProgress.value[itemId]
        if (current && current.status === 'downloading') {
          setProgress(itemId, {
            ...current,
            status: 'installing',
            progress: 0,
            message: '正在安装...',
          })
          simulateInstalling(itemId)
        }
      } else {
        const current = installProgress.value[itemId]
        if (current) {
          setProgress(itemId, { ...current, progress: Math.min(progress, 99) })
        }
      }
    }, 200)
    activeIntervals.add(intervalId)
  }

  const simulateInstalling = (itemId: string) => {
    let progress = 0
    const intervalId = setInterval(() => {
      if (cancelledInstalls.has(itemId)) {
        cleanupInterval(intervalId)
        cancelledInstalls.delete(itemId)
        return
      }
      progress += Math.random() * 20 + 10
      if (progress >= 100) {
        cleanupInterval(intervalId)
        if (cancelledInstalls.has(itemId)) {
          cancelledInstalls.delete(itemId)
          return
        }
        setProgress(itemId, {
          itemId,
          status: 'installed',
          progress: 100,
          message: '安装完成',
        })
        const updateInstalledItem = (items: MarketplaceItem[]) => {
          const item = items.find(i => i.id === itemId)
          if (item) {
            item.installStatus = 'installed'
            item.installedCount += 1
            item.downloadCount += 1
          }
        }
        updateInstalledItem(pluginItems.value)
        updateInstalledItem(skillItems.value)
        updateInstalledItem(agentItems.value)
        // 同步后端统计数据 + 排行榜
        syncAllStats()
        setTimeout(() => {
          removeProgress(itemId)
        }, 2000)
      } else {
        const current = installProgress.value[itemId]
        if (current) {
          setProgress(itemId, { ...current, progress: Math.min(progress, 99) })
        }
      }
    }, 150)
    activeIntervals.add(intervalId)
  }

  const uninstallItem = (itemId: string) => {
    cancelledInstalls.add(itemId)
    removeProgress(itemId)

    const updateUninstalledItem = (items: MarketplaceItem[]) => {
      const item = items.find(i => i.id === itemId)
      if (item) {
        item.installStatus = 'none'
        item.installedCount = Math.max(0, item.installedCount - 1)
      }
    }
    updateUninstalledItem(pluginItems.value)
    updateUninstalledItem(skillItems.value)
    updateUninstalledItem(agentItems.value)
    // 同步 repoSourceStore 中对应条目的状态
    import('../stores/repo-source').then(({ useRepoSourceStore }) => {
      const repoStore = useRepoSourceStore()
      for (const items of Object.values(repoStore.syncedItems)) {
        const ri = (items as MarketplaceItem[]).find(i => i.id === itemId)
        if (ri) {
          ri.installStatus = 'none'
        }
      }
    })
  }

  const updateItem = (itemId: string) => {
    cancelledInstalls.delete(itemId)
    const progress: InstallProgress = {
      itemId,
      status: 'updating',
      progress: 0,
      message: '正在更新...',
    }
    setProgress(itemId, progress)

    let progressVal = 0
    const intervalId = setInterval(() => {
      if (cancelledInstalls.has(itemId)) {
        cleanupInterval(intervalId)
        cancelledInstalls.delete(itemId)
        return
      }
      progressVal += Math.random() * 18 + 8
      if (progressVal >= 100) {
        cleanupInterval(intervalId)
        if (cancelledInstalls.has(itemId)) {
          cancelledInstalls.delete(itemId)
          return
        }
        setProgress(itemId, {
          itemId,
          status: 'installed',
          progress: 100,
          message: '更新完成',
        })
        const updateItemVersion = (items: MarketplaceItem[]) => {
          const item = items.find(i => i.id === itemId)
          if (item && item.latestVersion) {
            item.version = item.latestVersion
          }
        }
        updateItemVersion(pluginItems.value)
        updateItemVersion(skillItems.value)
        updateItemVersion(agentItems.value)
        setTimeout(() => {
          removeProgress(itemId)
        }, 2000)
      } else {
        const current = installProgress.value[itemId]
        if (current) {
          setProgress(itemId, { ...current, progress: Math.min(progressVal, 99) })
        }
      }
    }, 180)
    activeIntervals.add(intervalId)
  }

  const getInstallProgress = (itemId: string): InstallProgress | undefined => {
    return installProgress.value[itemId]
  }

  const getItemReviews = (itemId: string): MarketplaceReview[] => {
    return reviews.value[itemId] || []
  }

  const addReview = (itemId: string, review: Omit<MarketplaceReview, 'id' | 'createdAt'>) => {
    const newReview: MarketplaceReview = {
      ...review,
      id: `r-${Date.now()}`,
      createdAt: new Date().toISOString().split('T')[0],
    }
    if (!reviews.value[itemId]) {
      reviews.value[itemId] = []
    }
    reviews.value[itemId] = [newReview, ...reviews.value[itemId]]

    const updateRating = (items: MarketplaceItem[]) => {
      const item = items.find(i => i.id === itemId)
      if (item) {
        const itemReviews = reviews.value[itemId] || []
        const totalRating = itemReviews.reduce((sum, r) => sum + r.rating, 0)
        item.rating = Math.round((totalRating / itemReviews.length) * 10) / 10
        item.ratingCount = itemReviews.length
      }
    }
    updateRating(pluginItems.value)
    updateRating(skillItems.value)
    updateRating(agentItems.value)
  }

  const addReviewReply = (itemId: string, reviewId: string, reply: Omit<MarketplaceReviewReply, 'id' | 'createdAt'>) => {
    const itemReviews = reviews.value[itemId]
    if (!itemReviews) return
    const review = itemReviews.find(r => r.id === reviewId)
    if (!review) return
    if (!review.replies) review.replies = []
    review.replies.push({
      ...reply,
      id: `rp-${Date.now()}`,
      createdAt: new Date().toISOString().split('T')[0],
    })
  }

  const syncInstallStatus = async () => {
    try {
      const { useApi } = await import('../composables/useApi')
      const api = useApi()
      const result = await api.apiGet<{ items: Array<{ id: string; type: string; status: string }> }>('/marketplace/installed')
      const installedItems = result.items || []

      const updateStatus = (items: MarketplaceItem[]) => {
        for (const item of items) {
          const installed = installedItems.find((i) => i.id === item.id && i.type === item.type)
          item.installStatus = installed ? 'installed' : 'none'
        }
      }

      updateStatus(pluginItems.value)
      updateStatus(skillItems.value)
      updateStatus(agentItems.value)

      // 同步 repoSourceStore 中的安装状态
      import('../stores/repo-source').then(({ useRepoSourceStore }) => {
        const repoStore = useRepoSourceStore()
        for (const items of Object.values(repoStore.syncedItems)) {
          updateStatus(items as MarketplaceItem[])
        }
      })
    } catch {
      // 忽略同步失败
    }
  }

  const cleanup = () => {
    for (const intervalId of activeIntervals) {
      clearInterval(intervalId)
    }
    activeIntervals.clear()
    for (const timerId of Object.values(_progressTimers)) {
      clearInterval(timerId)
    }
    Object.keys(_progressTimers).forEach(key => delete _progressTimers[key])
  }

  // ─── 统计功能 ───────────────────────────────────────────

  const leaderboard = ref<LeaderboardItem[]>([])
  const itemStatsMap = ref<Record<string, ItemStats>>({})
  const currentLeaderboardType = ref<MarketplaceType | undefined>(undefined)
  const currentLeaderboardSortBy = ref('composite')

  // 统一同步：刷新所有统计数据 + 排行榜
  const syncAllStats = async (type?: MarketplaceType) => {
    await Promise.all([
      fetchAllStats(type),
      fetchLeaderboard(currentLeaderboardType.value, currentLeaderboardSortBy.value),
    ])
  }

  // 从后端同步单个条目的统计数据
  const fetchItemStats = async (itemId: string) => {
    try {
      const { useApi } = await import('../composables/useApi')
      const api = useApi()
      const result = await api.apiGet<ItemStats>(`/marketplace/stats/${itemId}`)
      itemStatsMap.value = { ...itemStatsMap.value, [itemId]: result }

      // 同步到本地 item
      const updateItemStats = (items: MarketplaceItem[]) => {
        const item = items.find(i => i.id === itemId)
        if (item) {
          item.downloadCount = result.downloadCount
          item.likeCount = result.likeCount
          item.isLiked = result.isLiked
        }
      }
      updateItemStats(pluginItems.value)
      updateItemStats(skillItems.value)
      updateItemStats(agentItems.value)
    } catch {
      // 忽略
    }
  }

  // 批量同步所有统计数据
  const fetchAllStats = async (type?: MarketplaceType) => {
    try {
      const { useApi } = await import('../composables/useApi')
      const api = useApi()
      const query = type ? `?type=${type}` : ''
      const result = await api.apiGet<{ stats: ItemStats[] }>(`/marketplace/stats${query}`)
      const statsList = result.stats || []
      const newMap: Record<string, ItemStats> = {}
      for (const s of statsList) {
        newMap[s.itemId] = s
      }
      itemStatsMap.value = newMap

      // 同步到本地 items
      const syncStats = (items: MarketplaceItem[]) => {
        for (const item of items) {
          const stats = newMap[item.id]
          if (stats) {
            item.downloadCount = stats.downloadCount
            item.likeCount = stats.likeCount
            item.isLiked = stats.isLiked
          }
        }
      }
      syncStats(pluginItems.value)
      syncStats(skillItems.value)
      syncStats(agentItems.value)

      // 同步 repoSourceStore 中的统计数据
      import('../stores/repo-source').then(({ useRepoSourceStore }) => {
        const repoStore = useRepoSourceStore()
        for (const items of Object.values(repoStore.syncedItems)) {
          syncStats(items as MarketplaceItem[])
        }
      })
    } catch {
      // 忽略
    }
  }

  // 切换喜欢状态
  const toggleLike = async (itemId: string, itemType: MarketplaceType = 'plugin') => {
    try {
      const { useApi } = await import('../composables/useApi')
      const api = useApi()
      const result = await api.apiPost<{ itemId: string; isLiked: boolean; likeCount: number }>(
        '/marketplace/stats/like',
        { itemId, itemType }
      )

      // 更新本地状态
      const updateLike = (items: MarketplaceItem[]) => {
        const item = items.find(i => i.id === itemId)
        if (item) {
          item.isLiked = result.isLiked
          item.likeCount = result.likeCount
        }
      }
      updateLike(pluginItems.value)
      updateLike(skillItems.value)
      updateLike(agentItems.value)

      // 同步 repoSourceStore 中对应条目的状态
      import('../stores/repo-source').then(({ useRepoSourceStore }) => {
        const repoStore = useRepoSourceStore()
        for (const items of Object.values(repoStore.syncedItems)) {
          updateLike(items as MarketplaceItem[])
        }
      })

      // 更新 statsMap
      if (itemStatsMap.value[itemId]) {
        itemStatsMap.value[itemId].isLiked = result.isLiked
        itemStatsMap.value[itemId].likeCount = result.likeCount
      }

      // 同步排行榜数据
      fetchLeaderboard(currentLeaderboardType.value, currentLeaderboardSortBy.value)

      return result
    } catch {
      return null
    }
  }

  // 获取排行榜
  const fetchLeaderboard = async (type?: MarketplaceType, sortBy: string = 'composite', limit: number = 20) => {
    try {
      currentLeaderboardType.value = type
      currentLeaderboardSortBy.value = sortBy
      const { useApi } = await import('../composables/useApi')
      const api = useApi()
      const params = new URLSearchParams()
      if (type) params.set('type', type)
      params.set('sort_by', sortBy)
      params.set('limit', String(limit))
      const result = await api.apiGet<{ leaderboard: LeaderboardItem[]; total: number }>(
        `/marketplace/leaderboard?${params.toString()}`
      )
      leaderboard.value = result.leaderboard || []
      return leaderboard.value
    } catch {
      leaderboard.value = []
      return []
    }
  }

  // 排行榜 computed：将排行榜数据与本地 item 信息合并
  const leaderboardItems = computed(() => {
    return leaderboard.value.map(entry => {
      const item = allItems.value.find(i => i.id === entry.itemId)
      return {
        ...entry,
        name: item?.name || entry.itemId,
        icon: item?.icon || 'Package',
        summary: item?.summary || '',
        rating: item?.rating || 0,
        author: item?.author,
      }
    })
  })

  return {
    pluginItems,
    skillItems,
    agentItems,
    loading,
    searchQuery,
    searchHistory,
    showSearchSuggestions,
    pluginFilter,
    skillFilter,
    agentFilter,
    favorites,
    reviews,
    featuredItems,
    featuredPlugins,
    featuredSkills,
    featuredAgents,
    filteredPluginItems,
    filteredSkillItems,
    filteredAgentItems,
    searchSuggestions,
    favoriteItems,
    favoritePlugins,
    favoriteSkills,
    favoriteAgents,
    isFavorite,
    getCategories,
    getItems,
    getFilter,
    getItemById,
    getItemByTypeAndId,
    performSearch,
    clearSearch,
    removeSearchHistoryEntry,
    clearSearchHistory,
    setFilter,
    resetFilters,
    toggleFavorite,
    startInstall,
    uninstallItem,
    updateItem,
    getInstallProgress,
    setInstallProgress,
    startProgressPolling,
    stopProgressPolling,
    getItemReviews,
    addReview,
    addReviewReply,
    syncInstallStatus,
    fetchItemStats,
    fetchAllStats,
    syncAllStats,
    toggleLike,
    fetchLeaderboard,
    leaderboard,
    leaderboardItems,
    itemStatsMap,
    cleanup,
  }
})
