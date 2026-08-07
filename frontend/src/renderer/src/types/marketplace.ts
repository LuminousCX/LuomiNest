export type MarketplaceType = 'plugin' | 'skill' | 'agent'

export type InstallStatus = 'none' | 'downloading' | 'installing' | 'installed' | 'updating' | 'error'

export type RepoSourceType = 'github' | 'cloud' | 'cdn' | 'custom'

export interface RepoSubMarket {
  id: string
  name: string
  type: MarketplaceType
  url: string
  description?: string
  linked: boolean
}

export interface RepoSource {
  id: string
  type: RepoSourceType
  name: string
  icon?: string
  url?: string
  description?: string
  enabled: boolean
  subMarkets?: RepoSubMarket[]
  lastSyncedAt?: string
  status: 'idle' | 'loading' | 'loaded' | 'syncing' | 'error'
  errorMessage?: string
}

export interface RegistrySource {
  id: string
  name: string
  type: 'github' | 'cdn' | 'custom'
  baseUrl: string
  urlPattern: 'raw' | 'gh'
  enabled: boolean
  /** 延迟测试后填充 */
  latencyMs?: number
  healthy?: boolean
  statusCode?: number | null
  error?: string | null
  active?: boolean
}

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
  likeCount: number
  installStatus: InstallStatus
  isFavorite: boolean
  isLiked?: boolean
  featured?: boolean
  homepage?: string
  repository?: string
  license?: string
  minAppVersion?: string
  createdAt: string
  updatedAt: string
  size: number
  /** 来源: "local" 表示本地内置插件,卸载时仅禁用不删文件 */
  source?: string
  /** 平台: fullstack / frontend / backend */
  platform?: string
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

export interface MarketplaceSearchResult {
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
  speed?: number       // 下载速度 (bytes/s)
  eta?: number         // 预计剩余时间 (秒)
  downloadedBytes?: number
  totalBytes?: number
  /** 本地内置插件标记:安装即启用,无需下载 */
  frontendBuiltin?: boolean
}

export interface ItemStats {
  itemId: string
  downloadCount: number
  likeCount: number
  isLiked: boolean
}

export interface LeaderboardItem {
  itemId: string
  downloadCount: number
  likeCount: number
  type: MarketplaceType
  score: number
}
