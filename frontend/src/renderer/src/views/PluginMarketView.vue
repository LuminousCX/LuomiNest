<script setup lang="ts">
import { ref, computed } from 'vue'
import { Puzzle, SlidersHorizontal, X } from 'lucide-vue-next'
import { useMarketplaceStore } from '../stores/marketplace'
import MarketplaceSearch from '../components/marketplace/MarketplaceSearch.vue'
import MarketplaceCategories from '../components/marketplace/MarketplaceCategories.vue'
import MarketplaceFilters from '../components/marketplace/MarketplaceFilters.vue'
import MarketplaceCard from '../components/marketplace/MarketplaceCard.vue'
import MarketplaceBanner from '../components/marketplace/MarketplaceBanner.vue'
import LumiEmptyState from '../components/common/LumiEmptyState.vue'
import LumiButton from '../components/common/LumiButton.vue'
import type { MarketplaceFilter } from '../types/marketplace'

const store = useMarketplaceStore()

const categories = computed(() => store.getCategories('plugin'))
const showFilters = ref(false)

const filter = computed(() => store.pluginFilter)

const activeCategory = computed(() => filter.value.category || 'all')

const filteredItems = computed(() => store.filteredPluginItems)

const featuredItems = computed(() => store.featuredPlugins)

const selectCategory = (id: string) => {
  store.setFilter('plugin', { category: id === 'all' ? undefined : id })
}

const updateFilter = (updates: Partial<MarketplaceFilter>) => {
  store.setFilter('plugin', updates)
}

const toggleFilters = () => {
  showFilters.value = !showFilters.value
}

const resetFilters = () => {
  store.resetFilters('plugin')
}
</script>

<template>
  <div class="plugin-market-view">
    <div class="market-header animate-fade-in">
      <div class="header-icon-wrap">
        <Puzzle :size="24" />
      </div>
      <div class="header-text">
        <h1 class="page-title">插件市场</h1>
        <p class="page-subtitle">扩展 LuomiNest 的能力边界</p>
      </div>
    </div>

    <div class="market-toolbar animate-slide-up">
      <MarketplaceSearch />
    </div>

    <div class="market-content">
      <aside class="market-sidebar">
        <MarketplaceCategories
          :categories="categories"
          :active-category="activeCategory"
          @select="selectCategory"
        />

        <div class="sidebar-filter-toggle">
          <button :class="['filter-toggle-btn', { active: showFilters }]" @click="toggleFilters">
            <SlidersHorizontal :size="14" />
            <span>筛选</span>
          </button>
        </div>

        <Transition name="filter-slide">
          <div v-if="showFilters" class="sidebar-filters">
            <div class="filters-header">
              <span>筛选条件</span>
              <button class="close-filters" @click="showFilters = false">
                <X :size="14" />
              </button>
            </div>
            <MarketplaceFilters :filter="filter" @update="updateFilter" />
          </div>
        </Transition>
      </aside>

      <main class="market-main">
        <MarketplaceBanner
          v-if="featuredItems.length > 0 && activeCategory === 'all' && !store.searchQuery"
          :items="featuredItems"
          title="热门推荐"
          type="plugin"
        />

        <div class="items-section">
          <div class="section-header">
            <h3 class="section-title">
              {{ activeCategory === 'all' ? '全部插件' : categories.find(c => c.id === activeCategory)?.name || '插件' }}
            </h3>
            <span class="section-count">{{ filteredItems.length }} 个</span>
          </div>

          <div v-if="filteredItems.length > 0" class="items-grid">
            <MarketplaceCard
              v-for="item in filteredItems"
              :key="item.id"
              :item="item"
            />
          </div>

          <LumiEmptyState
            v-else
            icon="search"
            title="没有找到匹配的插件"
            description="尝试调整筛选条件或搜索关键词"
          >
            <template #action>
              <LumiButton variant="outline" size="sm" @click="resetFilters">
                重置筛选
              </LumiButton>
            </template>
          </LumiEmptyState>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.plugin-market-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.market-header {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-6) var(--space-7) 0;
}

.header-icon-wrap {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-lg);
  background: var(--lumi-brand-gradient-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-brand);
}

.page-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.page-subtitle {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: calc(var(--space-1) / 2);
}

.market-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-7);
}

.market-toolbar > :deep(.market-search) {
  flex: 1;
}

.market-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.market-sidebar {
  width: 210px;
  flex-shrink: 0;
  padding: var(--space-4) var(--space-3) var(--space-4) var(--space-5);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  background: var(--workspace-sidebar);
  border-right: 1px solid var(--workspace-border);
}

.sidebar-filter-toggle {
  padding-top: var(--space-1);
  border-top: 1px solid var(--workspace-border);
}

.filter-toggle-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-fast);
}

.filter-toggle-btn:hover {
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
  background: var(--lumi-brand-subtle);
}

.filter-toggle-btn.active {
  background: var(--lumi-brand-light);
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
}

.sidebar-filters {
  padding-top: var(--space-2);
}

.filters-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.filters-header span {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.close-filters {
  width: var(--space-6);
  height: var(--space-6);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.close-filters:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.market-main {
  flex: 1;
  overflow-y: auto;
  padding: 0 var(--space-7) var(--space-7) var(--space-4);
  min-width: 0;
}

.items-section {
  margin-top: var(--space-5);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.section-title {
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.section-count {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.items-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-4);
}

.filter-slide-enter-active {
  animation: lumi-fade-in var(--duration-normal) var(--ease-out-expo);
}

.filter-slide-leave-active {
  animation: lumi-fade-in var(--duration-fast) var(--ease-out-expo) reverse;
}

@media (prefers-reduced-motion: reduce) {
  .market-header,
  .market-toolbar,
  .filter-toggle-btn,
  .close-filters {
    animation: none;
    transition: none;
  }
}
</style>
