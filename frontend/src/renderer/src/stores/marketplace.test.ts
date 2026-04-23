import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useMarketplaceStore } from '../stores/marketplace'

describe('MarketplaceStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('初始状态', () => {
    it('默认激活标签为 plugin', () => {
      const store = useMarketplaceStore()
      expect(store.activeTab).toBe('plugin')
    })

    it('默认排序为 popular', () => {
      const store = useMarketplaceStore()
      expect(store.filter.sort).toBe('popular')
    })

    it('有插件和 Skill 数据', () => {
      const store = useMarketplaceStore()
      expect(store.plugins.length).toBeGreaterThan(0)
      expect(store.skills.length).toBeGreaterThan(0)
    })

    it('统计信息正确', () => {
      const store = useMarketplaceStore()
      expect(store.stats.totalPlugins).toBe(store.plugins.length)
      expect(store.stats.totalSkills).toBe(store.skills.length)
    })
  })

  describe('标签页切换', () => {
    it('切换到 skill 标签页', () => {
      const store = useMarketplaceStore()
      store.setActiveTab('skill')
      expect(store.activeTab).toBe('skill')
    })

    it('切换标签页时重置筛选条件', () => {
      const store = useMarketplaceStore()
      store.setSearch('test')
      store.setActiveTab('skill')
      expect(store.filter.search).toBe('')
      expect(store.filter.category).toBe('all-skill')
    })

    it('切换标签页后分类列表更新', () => {
      const store = useMarketplaceStore()
      store.setActiveTab('skill')
      const skillCategories = store.categories
      expect(skillCategories.every(c => c.type === 'skill')).toBe(true)
    })
  })

  describe('搜索功能', () => {
    it('按名称搜索插件', () => {
      const store = useMarketplaceStore()
      store.setSearch('WeChat')
      const results = store.currentItems
      expect(results.length).toBeGreaterThan(0)
      expect(results.every(i => i.name.toLowerCase().includes('wechat') || i.description.toLowerCase().includes('wechat') || i.tags.some(t => t.toLowerCase().includes('wechat')))).toBe(true)
    })

    it('搜索无结果时返回空数组', () => {
      const store = useMarketplaceStore()
      store.setSearch('xyznonexistent123')
      expect(store.currentItems.length).toBe(0)
    })

    it('清空搜索恢复结果', () => {
      const store = useMarketplaceStore()
      store.setSearch('xyznonexistent123')
      expect(store.currentItems.length).toBe(0)
      store.setSearch('')
      expect(store.currentItems.length).toBeGreaterThan(0)
    })
  })

  describe('分类筛选', () => {
    it('按分类筛选插件', () => {
      const store = useMarketplaceStore()
      store.setCategory('communication')
      const results = store.currentItems
      expect(results.length).toBeGreaterThan(0)
      expect(results.every(i => i.category === 'communication')).toBe(true)
    })

    it('选择"全部"分类显示所有项目', () => {
      const store = useMarketplaceStore()
      store.setCategory('all-plugin')
      expect(store.currentItems.length).toBe(store.plugins.length)
    })
  })

  describe('排序功能', () => {
    it('按评分排序', () => {
      const store = useMarketplaceStore()
      store.setSort('rating')
      const results = store.currentItems
      for (let i = 1; i < results.length; i++) {
        expect(results[i - 1].rating).toBeGreaterThanOrEqual(results[i].rating)
      }
    })

    it('按下载量排序', () => {
      const store = useMarketplaceStore()
      store.setSort('downloads')
      const results = store.currentItems
      for (let i = 1; i < results.length; i++) {
        expect(results[i - 1].downloadCount).toBeGreaterThanOrEqual(results[i].downloadCount)
      }
    })

    it('按最新排序', () => {
      const store = useMarketplaceStore()
      store.setSort('newest')
      const results = store.currentItems
      for (let i = 1; i < results.length; i++) {
        expect(new Date(results[i - 1].updatedAt).getTime()).toBeGreaterThanOrEqual(new Date(results[i].updatedAt).getTime())
      }
    })
  })

  describe('收藏管理', () => {
    it('切换收藏状态', () => {
      const store = useMarketplaceStore()
      const item = store.plugins[0]
      const initialFav = item.isFavorite
      store.toggleFavorite(item.id)
      expect(item.isFavorite).toBe(!initialFav)
      store.toggleFavorite(item.id)
      expect(item.isFavorite).toBe(initialFav)
    })

    it('仅显示收藏项', () => {
      const store = useMarketplaceStore()
      store.toggleOnlyFavorites()
      const results = store.currentItems
      expect(results.every(i => i.isFavorite)).toBe(true)
    })

    it('收藏项统计正确', () => {
      const store = useMarketplaceStore()
      const favCount = [...store.plugins, ...store.skills].filter(i => i.isFavorite).length
      expect(store.stats.favoriteCount).toBe(favCount)
    })
  })

  describe('已安装筛选', () => {
    it('仅显示已安装项', () => {
      const store = useMarketplaceStore()
      store.toggleOnlyInstalled()
      const results = store.currentItems
      expect(results.every(i => i.isInstalled)).toBe(true)
    })

    it('已安装和收藏互斥', () => {
      const store = useMarketplaceStore()
      store.toggleOnlyInstalled()
      expect(store.filter.onlyInstalled).toBe(true)
      store.toggleOnlyFavorites()
      expect(store.filter.onlyFavorites).toBe(true)
      expect(store.filter.onlyInstalled).toBe(false)
    })
  })

  describe('标签筛选', () => {
    it('按标签筛选', () => {
      const store = useMarketplaceStore()
      const firstTag = store.allTags[0]
      if (firstTag) {
        store.toggleTag(firstTag)
        const results = store.currentItems
        expect(results.every(i => i.tags.includes(firstTag))).toBe(true)
      }
    })

    it('取消标签筛选', () => {
      const store = useMarketplaceStore()
      const firstTag = store.allTags[0]
      if (firstTag) {
        store.toggleTag(firstTag)
        expect(store.filter.tags).toContain(firstTag)
        store.toggleTag(firstTag)
        expect(store.filter.tags).not.toContain(firstTag)
      }
    })
  })

  describe('安装/卸载流程', () => {
    it('安装未安装的项目', async () => {
      const store = useMarketplaceStore()
      const item = store.plugins.find(p => !p.isInstalled)
      if (item) {
        await store.installItem(item.id)
        expect(item.isInstalled).toBe(true)
        expect(item.installStatus).toBe('installed')
      }
    })

    it('卸载已安装的项目', async () => {
      const store = useMarketplaceStore()
      const item = store.plugins.find(p => p.isInstalled)
      if (item) {
        await store.uninstallItem(item.id)
        expect(item.isInstalled).toBe(false)
        expect(item.installStatus).toBe('idle')
      }
    })

    it('安装过程中有进度更新', async () => {
      const store = useMarketplaceStore()
      const item = store.plugins.find(p => !p.isInstalled)
      if (item) {
        const installPromise = store.installItem(item.id)
        expect(item.installStatus).toBe('downloading')
        await installPromise
        expect(item.downloadProgress).toBe(100)
      }
    })
  })

  describe('评论系统', () => {
    it('获取评论列表', async () => {
      const store = useMarketplaceStore()
      await store.fetchReviews('plugin-1')
      expect(store.reviews.length).toBeGreaterThan(0)
    })

    it('添加评论', async () => {
      const store = useMarketplaceStore()
      await store.fetchReviews('plugin-1')
      const initialCount = store.reviews.length
      await store.addReview('plugin-1', 5, '测试评论内容')
      expect(store.reviews.length).toBe(initialCount + 1)
      expect(store.reviews[0].content).toBe('测试评论内容')
      expect(store.reviews[0].rating).toBe(5)
    })

    it('点赞评论', async () => {
      const store = useMarketplaceStore()
      await store.fetchReviews('plugin-1')
      const review = store.reviews[0]
      const initialLikes = review.likes
      store.likeReview(review.id)
      expect(review.likes).toBe(initialLikes + 1)
    })

    it('添加评论后更新评分', async () => {
      const store = useMarketplaceStore()
      const item = store.plugins[0]
      const initialReviewCount = item.reviewCount
      const initialRating = item.rating
      await store.addReview(item.id, 1, '低分评论')
      expect(item.reviewCount).toBe(initialReviewCount + 1)
    })
  })

  describe('重置筛选', () => {
    it('重置所有筛选条件', () => {
      const store = useMarketplaceStore()
      store.setSearch('test')
      store.setCategory('communication')
      store.setSort('rating')
      store.toggleOnlyInstalled()
      store.toggleTag('test')

      store.resetFilters()

      expect(store.filter.search).toBe('')
      expect(store.filter.category).toBe('all-plugin')
      expect(store.filter.sort).toBe('popular')
      expect(store.filter.onlyInstalled).toBe(false)
      expect(store.filter.onlyFavorites).toBe(false)
      expect(store.filter.tags.length).toBe(0)
    })
  })

  describe('查找项目', () => {
    it('通过 ID 查找插件', () => {
      const store = useMarketplaceStore()
      const item = store.findItem('plugin-1')
      expect(item).toBeDefined()
      expect(item?.type).toBe('plugin')
    })

    it('通过 ID 查找 Skill', () => {
      const store = useMarketplaceStore()
      const item = store.findItem('skill-1')
      expect(item).toBeDefined()
      expect(item?.type).toBe('skill')
    })

    it('查找不存在的项目返回 undefined', () => {
      const store = useMarketplaceStore()
      const item = store.findItem('nonexistent')
      expect(item).toBeUndefined()
    })
  })

  describe('精选推荐', () => {
    it('精选项目评分不低于 4.5', () => {
      const store = useMarketplaceStore()
      const featured = store.featuredItems
      expect(featured.every(i => i.rating >= 4.5)).toBe(true)
    })

    it('精选项目最多 4 个', () => {
      const store = useMarketplaceStore()
      expect(store.featuredItems.length).toBeLessThanOrEqual(4)
    })
  })
})
