export type MarketItemType = 'plugin' | 'skill'

export type InstallStatus = 'idle' | 'downloading' | 'installing' | 'installed' | 'error'

export type SortOption = 'popular' | 'newest' | 'rating' | 'downloads'

export interface MarketItem {
  id: string
  type: MarketItemType
  name: string
  description: string
  longDescription: string
  icon: string
  author: string
  version: string
  category: string
  tags: string[]
  rating: number
  reviewCount: number
  downloadCount: number
  size: string
  updatedAt: string
  screenshots: string[]
  isInstalled: boolean
  isFavorite: boolean
  installStatus: InstallStatus
  downloadProgress: number
  changelog: string
  permissions: string[]
  homepage?: string
}

export interface MarketReview {
  id: string
  itemId: string
  userName: string
  userAvatar: string
  rating: number
  content: string
  createdAt: string
  likes: number
}

export interface MarketCategory {
  id: string
  name: string
  icon: string
  type: MarketItemType
  count: number
}

export interface MarketFilter {
  type: MarketItemType
  category: string
  search: string
  sort: SortOption
  tags: string[]
  onlyInstalled: boolean
  onlyFavorites: boolean
}
