<script setup lang="ts">
import { ref, computed } from 'vue'
import { Sparkles, SlidersHorizontal, X } from 'lucide-vue-next'
import { useMarketplaceStore } from '../stores/marketplace'
import MarketplaceSearch from '../components/marketplace/MarketplaceSearch.vue'
import MarketplaceCategories from '../components/marketplace/MarketplaceCategories.vue'
import MarketplaceFilters from '../components/marketplace/MarketplaceFilters.vue'
import MarketplaceCard from '../components/marketplace/MarketplaceCard.vue'
import MarketplaceBanner from '../components/marketplace/MarketplaceBanner.vue'
import type { MarketplaceFilter } from '../types/marketplace'

const store = useMarketplaceStore()

const categories = computed(() => store.getCategories('skill'))
const showFilters = ref(false)

const filter = computed(() => store.skillFilter)

const activeCategory = computed(() => filter.value.category || 'all')

const filteredItems = computed(() => store.filteredSkillItems)

const featuredItems = computed(() => store.featuredSkills)

const selectCategory = (id: string) => {
  store.setFilter('skill', { category: id === 'all' ? undefined : id })
}

const updateFilter = (updates: Partial<MarketplaceFilter>) => {
  store.setFilter('skill', updates)
}

const toggleFilters = () => {
  showFilters.value = !showFilters.value
}

const resetFilters = () => {
  store.setFilter('skill', { category: undefined })
  store.clearSearch()
}
</script>

<template>
  <div class="skill-market-view">
    <div class="market-header animate-fade-in">
      <div class="header-icon-wrap">
        <Sparkles :size="24" />
      </div>
      <div class="header-text">
        <h1 class="page-title">技能市场</h1>
        <p class="page-subtitle">赋予 AI 更丰富的专业技能</p>
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
          type="skill"
        />

        <div class="items-section">
          <div class="section-header">
            <h3 class="section-title">
              {{ activeCategory === 'all' ? '全部技能' : categories.find(c => c.id === activeCategory)?.name || '技能' }}
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

          <div v-else class="empty-state">
            <Sparkles :size="48" />
            <p>没有找到匹配的技能</p>
            <button class="reset-btn" @click="resetFilters">
              重置筛选
            </button>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.skill-market-view {
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
  background: linear-gradient(135deg, rgba(20, 126, 188, 0.1), rgba(98, 169, 200, 0.1));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
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

.market-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 28px;
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
  padding: 16px 12px 16px 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--workspace-sidebar);
  border-right: 1px solid var(--workspace-border);
}

.sidebar-filter-toggle {
  padding-top: 4px;
  border-top: 1px solid var(--workspace-border);
}

.filter-toggle-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-fast);
}

.filter-toggle-btn:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: rgba(20, 126, 188, 0.06);
}

.filter-toggle-btn.active {
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.sidebar-filters {
  padding-top: 8px;
}

.filters-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.filters-header span {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.close-filters {
  width: 24px;
  height: 24px;
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
  padding: 0 28px 28px 16px;
  min-width: 0;
}

.items-section {
  margin-top: 20px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.section-count {
  font-size: 12px;
  color: var(--text-muted);
}

.items-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--text-muted);
}

.empty-state p {
  font-size: 14px;
}

.reset-btn {
  padding: 8px 20px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  transition: all var(--transition-fast);
}

.reset-btn:hover {
  background: var(--lumi-primary);
  color: white;
}

.filter-slide-enter-active {
  animation: lumi-fade-in 0.25s ease-in-out;
}

.filter-slide-leave-active {
  animation: lumi-fade-in 0.15s ease-in-out reverse;
}
</style>
