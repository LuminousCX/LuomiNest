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
} from '../types/marketplace'
import {
  PLUGIN_CATEGORIES,
  SKILL_CATEGORIES,
  MOCK_PLUGINS,
  MOCK_SKILLS,
  MOCK_REVIEWS,
} from '../config/marketplace-data'

const SEARCH_HISTORY_KEY = 'luominest-marketplace-search-history'
const FAVORITES_KEY = 'luominest-marketplace-favorites'

export const useMarketplaceStore = defineStore('marketplace', () => {
  const pluginItems = ref<MarketplaceItem[]>([...MOCK_PLUGINS])
  const skillItems = ref<MarketplaceItem[]>([...MOCK_SKILLS])
  const loading = ref(false)
  const searchQuery = ref('')
  const searchHistory = ref<string[]>(loadSearchHistory())
  const showSearchSuggestions = ref(false)
  const pluginFilter = ref<MarketplaceFilter>({ sortBy: 'popular' })
  const skillFilter = ref<MarketplaceFilter>({ sortBy: 'popular' })
  const installProgress = ref<Map<string, InstallProgress>>(new Map())
  const reviews = ref<Record<string, MarketplaceReview[]>>(loadMockReviews())

  const favorites = ref<Set<string>>(loadFavorites())

  function loadSearchHistory(): string[] {
    try {
      const stored = localStorage.getItem(SEARCH_HISTORY_KEY)
      return stored ? JSON.parse(stored) : []
    } catch {
      return []
    }
  }

  function saveSearchHistory(history: string[]) {
    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(history.slice(0, 20)))
  }

  function loadFavorites(): Set<string> {
    try {
      const stored = localStorage.getItem(FAVORITES_KEY)
      return stored ? new Set(JSON.parse(stored)) : new Set()
    } catch {
      return new Set()
    }
  }

  function saveFavorites() {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify([...favorites.value]))
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
    return type === 'plugin' ? PLUGIN_CATEGORIES : SKILL_CATEGORIES
  }

  const getItems = (type: MarketplaceType): MarketplaceItem[] => {
    return type === 'plugin' ? pluginItems.value : skillItems.value
  }

  const getFilter = (type: MarketplaceType) => {
    return type === 'plugin' ? pluginFilter : skillFilter
  }

  const featuredItems = computed(() => {
    const all = [...pluginItems.value, ...skillItems.value]
    return all.filter(i => i.featured).sort((a, b) => b.rating - a.rating).slice(0, 6)
  })

  const featuredPlugins = computed(() => {
    return pluginItems.value.filter(i => i.featured).sort((a, b) => b.rating - a.rating)
  })

  const featuredSkills = computed(() => {
    return skillItems.value.filter(i => i.featured).sort((a, b) => b.rating - a.rating)
  })

  const filteredPluginItems = computed(() => {
    return applyFilters(pluginItems.value, pluginFilter.value)
  })

  const filteredSkillItems = computed(() => {
    return applyFilters(skillItems.value, skillFilter.value)
  })

  function applyFilters(items: MarketplaceItem[], filter: MarketplaceFilter): MarketplaceItem[] {
    let result = [...items]

    if (filter.category && filter.category !== 'all') {
      result = result.filter(i => {
        if (i.category === filter.category) return true
        const allCats = [...PLUGIN_CATEGORIES, ...SKILL_CATEGORIES]
        const parent = allCats.find(c => c.id === filter.category)
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
      const allItems = [...pluginItems.value, ...skillItems.value]
      const matched = allItems.filter(i =>
        i.name.toLowerCase().includes(q) || i.summary.toLowerCase().includes(q)
      ).slice(0, 5)
      for (const item of matched) {
        suggestions.push({ text: item.name, type: 'suggestion' })
      }

      const allCats = [...PLUGIN_CATEGORIES, ...SKILL_CATEGORIES]
      for (const cat of allCats) {
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

  function getItemById(id: string): MarketplaceItem | undefined {
    return [...pluginItems.value, ...skillItems.value].find(i => i.id === id)
  }

  function getItemByTypeAndId(type: MarketplaceType, id: string): MarketplaceItem | undefined {
    const items = type === 'plugin' ? pluginItems.value : skillItems.value
    return items.find(i => i.id === id)
  }

  function performSearch(query: string) {
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

  function clearSearch() {
    searchQuery.value = ''
    showSearchSuggestions.value = false
  }

  function removeSearchHistoryEntry(entry: string) {
    searchHistory.value = searchHistory.value.filter(h => h !== entry)
    saveSearchHistory(searchHistory.value)
  }

  function clearSearchHistory() {
    searchHistory.value = []
    saveSearchHistory([])
  }

  function setFilter(type: MarketplaceType, filter: Partial<MarketplaceFilter>) {
    const target = type === 'plugin' ? pluginFilter : skillFilter
    target.value = { ...target.value, ...filter }
  }

  function toggleFavorite(itemId: string) {
    if (favorites.value.has(itemId)) {
      favorites.value.delete(itemId)
    } else {
      favorites.value.add(itemId)
    }
    saveFavorites()

    const updateItem = (items: MarketplaceItem[]) => {
      const item = items.find(i => i.id === itemId)
      if (item) item.isFavorite = favorites.value.has(itemId)
    }
    updateItem(pluginItems.value)
    updateItem(skillItems.value)
  }

  const favoriteItems = computed(() => {
    return [...pluginItems.value, ...skillItems.value].filter(i => i.isFavorite)
  })

  const favoritePlugins = computed(() => {
    return pluginItems.value.filter(i => i.isFavorite)
  })

  const favoriteSkills = computed(() => {
    return skillItems.value.filter(i => i.isFavorite)
  })

  function startInstall(itemId: string) {
    const progress: InstallProgress = {
      itemId,
      status: 'downloading',
      progress: 0,
      message: '正在下载...',
    }
    installProgress.value.set(itemId, progress)
    simulateInstall(itemId)
  }

  function simulateInstall(itemId: string) {
    let progress = 0
    const interval = setInterval(() => {
      progress += Math.random() * 15 + 5
      if (progress >= 100) {
        progress = 100
        clearInterval(interval)
        const current = installProgress.value.get(itemId)
        if (current) {
          if (current.status === 'downloading') {
            installProgress.value.set(itemId, {
              ...current,
              status: 'installing',
              progress: 0,
              message: '正在安装...',
            })
            simulateInstalling(itemId)
          }
        }
      } else {
        const current = installProgress.value.get(itemId)
        if (current) {
          installProgress.value.set(itemId, { ...current, progress: Math.min(progress, 99) })
        }
      }
    }, 200)
  }

  function simulateInstalling(itemId: string) {
    let progress = 0
    const interval = setInterval(() => {
      progress += Math.random() * 20 + 10
      if (progress >= 100) {
        clearInterval(interval)
        installProgress.value.set(itemId, {
          itemId,
          status: 'installed',
          progress: 100,
          message: '安装完成',
        })
        const updateItem = (items: MarketplaceItem[]) => {
          const item = items.find(i => i.id === itemId)
          if (item) {
            item.installStatus = 'installed'
            item.installedCount += 1
          }
        }
        updateItem(pluginItems.value)
        updateItem(skillItems.value)
        setTimeout(() => {
          installProgress.value.delete(itemId)
        }, 2000)
      } else {
        const current = installProgress.value.get(itemId)
        if (current) {
          installProgress.value.set(itemId, { ...current, progress: Math.min(progress, 99) })
        }
      }
    }, 150)
  }

  function uninstallItem(itemId: string) {
    const updateItem = (items: MarketplaceItem[]) => {
      const item = items.find(i => i.id === itemId)
      if (item) {
        item.installStatus = 'none'
        item.installedCount = Math.max(0, item.installedCount - 1)
      }
    }
    updateItem(pluginItems.value)
    updateItem(skillItems.value)
    installProgress.value.delete(itemId)
  }

  function updateItem(itemId: string) {
    const progress: InstallProgress = {
      itemId,
      status: 'updating',
      progress: 0,
      message: '正在更新...',
    }
    installProgress.value.set(itemId, progress)

    let progressVal = 0
    const interval = setInterval(() => {
      progressVal += Math.random() * 18 + 8
      if (progressVal >= 100) {
        clearInterval(interval)
        installProgress.value.set(itemId, {
          itemId,
          status: 'installed',
          progress: 100,
          message: '更新完成',
        })
        const updateItemInList = (items: MarketplaceItem[]) => {
          const item = items.find(i => i.id === itemId)
          if (item && item.latestVersion) {
            item.version = item.latestVersion
          }
        }
        updateItemInList(pluginItems.value)
        updateItemInList(skillItems.value)
        setTimeout(() => {
          installProgress.value.delete(itemId)
        }, 2000)
      } else {
        const current = installProgress.value.get(itemId)
        if (current) {
          installProgress.value.set(itemId, { ...current, progress: Math.min(progressVal, 99) })
        }
      }
    }, 180)
  }

  function getInstallProgress(itemId: string): InstallProgress | undefined {
    return installProgress.value.get(itemId)
  }

  function getItemReviews(itemId: string): MarketplaceReview[] {
    return reviews.value[itemId] || []
  }

  function addReview(itemId: string, review: Omit<MarketplaceReview, 'id' | 'createdAt'>) {
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
  }

  function addReviewReply(itemId: string, reviewId: string, reply: Omit<MarketplaceReviewReply, 'id' | 'createdAt'>) {
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

  return {
    pluginItems,
    skillItems,
    loading,
    searchQuery,
    searchHistory,
    showSearchSuggestions,
    pluginFilter,
    skillFilter,
    favorites,
    reviews,
    featuredItems,
    featuredPlugins,
    featuredSkills,
    filteredPluginItems,
    filteredSkillItems,
    searchSuggestions,
    favoriteItems,
    favoritePlugins,
    favoriteSkills,
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
    toggleFavorite,
    startInstall,
    uninstallItem,
    updateItem,
    getInstallProgress,
    getItemReviews,
    addReview,
    addReviewReply,
  }
})
