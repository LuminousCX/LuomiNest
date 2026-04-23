<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import {
  Store,
  Sparkles,
  ArrowRight,
  SlidersHorizontal,
  X,
  Download,
  Heart,
  TrendingUp,
  Clock,
  Star,
  LayoutList
} from 'lucide-vue-next'
import { useMarketplaceStore } from '../../stores/marketplace'
import type { SortOption, MarketItemType } from '../../types/marketplace'
import MarketCard from '../../components/marketplace/MarketCard.vue'
import CategoryFilter from '../../components/marketplace/CategoryFilter.vue'
import SearchBar from '../../components/marketplace/SearchBar.vue'
import MarketIcon from '../../components/marketplace/MarketIcon.vue'

const router = useRouter()
const store = useMarketplaceStore()

const showFilterPanel = ref(false)
const showSortMenu = ref(false)
const sortDropdownRef = ref<HTMLElement | null>(null)

const tabs: { id: MarketItemType; label: string; icon: any }[] = [
  { id: 'plugin', label: '插件市场', icon: Store },
  { id: 'skill', label: 'Skill 市场', icon: Sparkles }
]

const sortOptions: { id: SortOption; label: string; icon: any }[] = [
  { id: 'popular', label: '最热门', icon: TrendingUp },
  { id: 'newest', label: '最新', icon: Clock },
  { id: 'rating', label: '评分最高', icon: Star },
  { id: 'downloads', label: '下载最多', icon: Download }
]

const activeSortLabel = computed(() => {
  const opt = sortOptions.find(o => o.id === store.filter.sort)
  return opt?.label || '最热门'
})

function goDetail(type: MarketItemType, id: string) {
  router.push(`/marketplace/${type}/${id}`)
}

function toggleFilterPanel() {
  showFilterPanel.value = !showFilterPanel.value
}

function handleSearch(val: string) {
  store.setSearch(val)
}

function handleCategorySelect(catId: string) {
  store.setCategory(catId)
}

function handleSortChange(sort: SortOption) {
  store.setSort(sort)
  showSortMenu.value = false
}

function handleTagToggle(tag: string) {
  store.toggleTag(tag)
}

function handleClickOutsideSort(e: MouseEvent) {
  if (sortDropdownRef.value && !sortDropdownRef.value.contains(e.target as Node)) {
    showSortMenu.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutsideSort, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutsideSort, true)
})

function resetAllFilters() {
  store.resetFilters()
  showFilterPanel.value = false
}
</script>

<template>
  <div class="marketplace-view">
    <div class="market-header animate-fade-in">
      <div class="header-icon-wrap">
        <Store :size="24" />
      </div>
      <div class="header-text">
        <h1 class="page-title">市场</h1>
        <p class="page-subtitle">发现插件与 Skill，扩展你的 LuomiNest 能力</p>
      </div>
    </div>

    <div class="market-tabs animate-fade-in">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-btn', { active: store.activeTab === tab.id }]"
        @click="store.setActiveTab(tab.id)"
      >
        <component :is="tab.icon" :size="16" />
        <span>{{ tab.label }}</span>
        <span class="tab-count">{{ tab.id === 'plugin' ? store.stats.totalPlugins : store.stats.totalSkills }}</span>
      </button>
    </div>

    <div class="market-toolbar animate-fade-in">
      <SearchBar
        :model-value="store.filter.search"
        @update:model-value="handleSearch"
        :placeholder="store.activeTab === 'plugin' ? '搜索插件...' : '搜索 Skill...'"
      />

      <div class="toolbar-actions">
        <button
          :class="['toolbar-btn', { active: store.filter.onlyInstalled }]"
          @click="store.toggleOnlyInstalled()"
          aria-label="已安装"
        >
          <Download :size="15" />
          <span class="btn-label">已安装</span>
          <span v-if="store.stats.installedCount" class="btn-badge">{{ store.stats.installedCount }}</span>
        </button>
        <button
          :class="['toolbar-btn', { active: store.filter.onlyFavorites }]"
          @click="store.toggleOnlyFavorites()"
          aria-label="收藏"
        >
          <Heart :size="15" />
          <span class="btn-label">收藏</span>
          <span v-if="store.stats.favoriteCount" class="btn-badge accent">{{ store.stats.favoriteCount }}</span>
        </button>
        <div ref="sortDropdownRef" class="sort-dropdown">
          <button :class="['toolbar-btn sort-btn', { active: showSortMenu }]" aria-label="排序" @click="showSortMenu = !showSortMenu">
            <SlidersHorizontal :size="15" />
            <span class="btn-label">{{ activeSortLabel }}</span>
          </button>
          <Transition name="sort-menu">
            <div v-if="showSortMenu" class="sort-menu" @click.self="showSortMenu = false">
              <button
                v-for="opt in sortOptions"
                :key="opt.id"
                :class="['sort-option', { active: store.filter.sort === opt.id }]"
                @click="handleSortChange(opt.id)"
              >
                <component :is="opt.icon" :size="14" />
                <span>{{ opt.label }}</span>
              </button>
            </div>
          </Transition>
        </div>
        <button
          :class="['toolbar-btn', { active: showFilterPanel }]"
          @click="toggleFilterPanel"
          aria-label="筛选"
        >
          <LayoutList :size="15" />
          <span class="btn-label">筛选</span>
        </button>
      </div>
    </div>

    <div class="market-content">
      <Transition name="filter-slide">
        <div v-if="showFilterPanel" class="filter-sidebar">
          <div class="filter-sidebar-header">
            <h4>筛选</h4>
            <button class="close-filter-btn" @click="showFilterPanel = false" aria-label="关闭筛选">
              <X :size="16" />
            </button>
          </div>

          <CategoryFilter
            :categories="store.categories"
            :active-category="store.filter.category"
            @select="handleCategorySelect"
          />

          <div class="filter-section">
            <h4 class="filter-title">标签</h4>
            <div class="tag-cloud">
              <button
                v-for="tag in store.allTags"
                :key="tag"
                :class="['tag-btn', { active: store.filter.tags.includes(tag) }]"
                @click="handleTagToggle(tag)"
              >
                {{ tag }}
              </button>
            </div>
          </div>

          <button class="reset-filters-btn" @click="resetAllFilters">
            重置筛选
          </button>
        </div>
      </Transition>

      <div class="market-main">
        <div v-if="store.featuredItems.length > 0 && !store.filter.search && !store.filter.onlyInstalled && !store.filter.onlyFavorites" class="featured-section animate-slide-up">
          <div class="section-header">
            <h3 class="section-title">
              <Sparkles :size="16" class="title-icon" />
              精选推荐
            </h3>
          </div>
          <div class="featured-grid">
            <div
              v-for="item in store.featuredItems"
              :key="item.id"
              class="featured-card"
              @click="goDetail(item.type, item.id)"
            >
              <div class="featured-icon" :style="{ background: (item.type === 'plugin' ? '#6366f1' : '#0d9488') + '14', color: item.type === 'plugin' ? '#6366f1' : '#0d9488' }">
                <MarketIcon :name="item.icon" :size="28" />
              </div>
              <div class="featured-info">
                <h4>{{ item.name }}</h4>
                <p>{{ item.description }}</p>
              </div>
              <div class="featured-meta">
                <span class="featured-rating">
                  <Star :size="12" />
                  {{ item.rating.toFixed(1) }}
                </span>
                <ArrowRight :size="16" class="featured-arrow" />
              </div>
            </div>
          </div>
        </div>

        <div class="items-section">
          <div class="section-header">
            <h3 class="section-title">
              <template v-if="store.filter.onlyInstalled">已安装</template>
              <template v-else-if="store.filter.onlyFavorites">我的收藏</template>
              <template v-else-if="store.filter.search">搜索结果</template>
              <template v-else>全部{{ store.activeTab === 'plugin' ? '插件' : 'Skill' }}</template>
              <span class="item-count">{{ store.currentItems.length }}</span>
            </h3>
          </div>

          <div v-if="store.currentItems.length > 0" class="items-grid">
            <MarketCard
              v-for="item in store.currentItems"
              :key="item.id"
              :item="item"
            />
          </div>

          <div v-else class="empty-state animate-scale-in">
            <div class="empty-icon">
              <Store :size="48" />
            </div>
            <p class="empty-text">
              <template v-if="store.filter.search">没有找到匹配「{{ store.filter.search }}」的内容</template>
              <template v-else-if="store.filter.onlyInstalled">还没有安装任何{{ store.activeTab === 'plugin' ? '插件' : 'Skill' }}</template>
              <template v-else-if="store.filter.onlyFavorites">还没有收藏任何内容</template>
              <template v-else>暂无内容</template>
            </p>
            <button v-if="store.filter.search || store.filter.onlyInstalled || store.filter.onlyFavorites" class="empty-action" @click="resetAllFilters">
              清除筛选
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.marketplace-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.market-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px 28px 0;
}

.header-icon-wrap {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(13, 148, 136, 0.1));
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6366f1;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 2px;
}

.market-tabs {
  display: flex;
  gap: 4px;
  padding: 16px 28px 0;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 18px;
  border-radius: var(--radius-full);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.tab-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.tab-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.tab-count {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background: var(--bg-secondary);
  color: var(--text-muted);
}

.tab-btn.active .tab-count {
  background: rgba(13, 148, 136, 0.15);
  color: var(--lumi-primary);
}

.market-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 28px;
  position: relative;
  z-index: 100;
}

.market-toolbar .search-bar {
  flex: 1;
  max-width: 400px;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--text-muted);
  transition: all var(--transition-fast);
  position: relative;
}

.toolbar-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.toolbar-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.btn-label {
  display: inline;
}

.btn-badge {
  font-size: 10px;
  padding: 0 5px;
  border-radius: var(--radius-full);
  background: var(--bg-secondary);
  color: var(--text-muted);
  font-weight: 600;
}

.btn-badge.accent {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.sort-dropdown {
  position: relative;
}

.sort-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  padding: 4px;
  z-index: 9999;
  min-width: 150px;
}

.sort-menu-enter-active {
  animation: sort-menu-in 0.15s ease-out both;
}

.sort-menu-leave-active {
  animation: sort-menu-in 0.1s ease-in reverse both;
}

@keyframes sort-menu-in {
  from {
    opacity: 0;
    transform: translateY(-4px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.sort-option {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
  text-align: left;
}

.sort-option:hover {
  background: var(--surface-hover);
}

.sort-option.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.market-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.filter-sidebar {
  width: 220px;
  flex-shrink: 0;
  padding: 0 28px 16px 28px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.filter-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.filter-sidebar-header h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.close-filter-btn {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.close-filter-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.filter-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--text-muted);
  padding: 0 4px;
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-btn {
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  transition: all var(--transition-fast);
}

.tag-btn:hover {
  background: var(--surface-hover);
}

.tag-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.reset-filters-btn {
  padding: 8px 14px;
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  transition: all var(--transition-fast);
  margin-top: auto;
}

.reset-filters-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.market-main {
  flex: 1;
  overflow-y: auto;
  padding: 0 28px 28px;
  min-width: 0;
}

.featured-section {
  margin-bottom: 28px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.title-icon {
  color: #f59e0b;
}

.item-count {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--bg-secondary);
}

.featured-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.featured-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.featured-card:hover {
  border-color: var(--lumi-primary);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.featured-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.featured-info {
  flex: 1;
  min-width: 0;
}

.featured-info h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.featured-info p {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.featured-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.featured-rating {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  color: #f59e0b;
}

.featured-arrow {
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.featured-card:hover .featured-arrow {
  color: var(--lumi-primary);
  transform: translateX(3px);
}

.items-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-icon {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  background: var(--workspace-panel);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  margin: 0 auto 16px;
}

.empty-text {
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.empty-action {
  padding: 8px 20px;
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  transition: all var(--transition-fast);
}

.empty-action:hover {
  background: rgba(13, 148, 136, 0.15);
}

.filter-slide-enter-active,
.filter-slide-leave-active {
  transition: all var(--transition-normal);
}

.filter-slide-enter-from,
.filter-slide-leave-to {
  opacity: 0;
  width: 0;
  padding-left: 0;
  padding-right: 0;
}

@media (max-width: 768px) {
  .market-header {
    padding: 16px 16px 0;
  }

  .market-tabs {
    padding: 12px 16px 0;
  }

  .market-toolbar {
    padding: 10px 16px;
    flex-wrap: wrap;
  }

  .market-toolbar .search-bar {
    max-width: 100%;
    width: 100%;
    order: -1;
  }

  .toolbar-actions {
    width: 100%;
    justify-content: space-between;
  }

  .btn-label {
    display: none;
  }

  .market-main {
    padding: 0 16px 16px;
  }

  .filter-sidebar {
    display: none;
  }

  .featured-grid {
    grid-template-columns: 1fr;
  }

  .items-grid {
    grid-template-columns: 1fr;
  }

  .header-icon-wrap {
    width: 42px;
    height: 42px;
  }

  .page-title {
    font-size: 20px;
  }
}

@media (max-width: 1024px) and (min-width: 769px) {
  .items-grid {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  }
}
</style>
