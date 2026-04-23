export type MarketplaceType = 'plugin' | 'skill'

export type InstallStatus = 'none' | 'downloading' | 'installing' | 'installed' | 'updating' | 'error'

export interface MarketplaceCategory {
  id: string
  name: string
  icon?: string
  children?: MarketplaceCategory[]
}

export interface MarketplaceTag {
  id: string
  name: string
  color: string
}

export interface MarketplaceAuthor {
  id: string
  name: string
  avatar?: string
  verified?: boolean
}

export interface MarketplaceVersion {
  version: string
  changelog: string
  releasedAt: string
  size: number
  downloadUrl?: string
}

export interface MarketplaceScreenshot {
  url: string
  caption?: string
}

export interface MarketplaceItem {
  id: string
  type: MarketplaceType
  name: string
  description: string
  summary: string
  icon: string
  author: MarketplaceAuthor
  category: string
  tags: MarketplaceTag[]
  version: string
  latestVersion?: string
  versions: MarketplaceVersion[]
  screenshots: MarketplaceScreenshot[]
  rating: number
  ratingCount: number
  downloadCount: number
  installedCount: number
  installStatus: InstallStatus
  isFavorite: boolean
  featured?: boolean
  homepage?: string
  repository?: string
  license?: string
  minAppVersion?: string
  createdAt: string
  updatedAt: string
  size: number
}

export interface MarketplaceReview {
  id: string
  itemId: string
  userId: string
  userName: string
  userAvatar?: string
  rating: number
  content: string
  createdAt: string
  replies?: MarketplaceReviewReply[]
}

export interface MarketplaceReviewReply {
  id: string
  userId: string
  userName: string
  userAvatar?: string
  content: string
  createdAt: string
}

export interface MarketplaceFilter {
  category?: string
  tags?: string[]
  sortBy: 'popular' | 'newest' | 'rating' | 'downloads'
  installStatus?: InstallStatus | 'all'
}

export interface SearchResult {
  items: MarketplaceItem[]
  total: number
  query: string
}

export interface SearchSuggestion {
  text: string
  type: 'history' | 'suggestion' | 'category'
}

export interface InstallProgress {
  itemId: string
  status: InstallStatus
  progress: number
  message?: string
  error?: string
}
