﻿<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Puzzle, Sparkles, SlidersHorizontal, X, Package, Bot } from 'lucide-vue-next'
import { useMarketplaceStore } from '../stores/marketplace'
import MarketplaceSearch from '../components/marketplace/MarketplaceSearch.vue'
import MarketplaceCategories from '../components/marketplace/MarketplaceCategories.vue'
import MarketplaceFilters from '../components/marketplace/MarketplaceFilters.vue'
import MarketplaceCard from '../components/marketplace/MarketplaceCard.vue'
import MarketplaceBanner from '../components/marketplace/MarketplaceBanner.vue'
import type { MarketplaceFilter, MarketplaceType } from '../types/marketplace'

const route = useRoute()
const router = useRouter()
const store = useMarketplaceStore()

const VALID_TABS: MarketplaceType[] = ['plugin', 'skill', 'agent']
const activeTab = ref<MarketplaceType>('plugin')
const showFilters = ref(false)

watch(() => route.query.tab, (tab) => {
  const t = typeof tab === 'string' ? tab : ''
  if (VALID_TABS.includes(t as MarketplaceType)) {
    activeTab.value = t as MarketplaceType
  }
}, { immediate: true })

const categories = computed(() => store.getCategories(activeTab.value))
const filter = computed(() => {
  if (activeTab.value === 'plugin') return store.pluginFilter
  if (activeTab.value === 'skill') return store.skillFilter
  return store.agentFilter
})
const activeCategory = computed({
  get: () => filter.value.category || 'all',
  set: (val: string) => store.setFilter(activeTab.value, { category: val === 'all' ? undefined : val })
})

const filteredItems = computed(() => {
  if (activeTab.value === 'plugin') return store.filteredPluginItems
  if (activeTab.value === 'skill') return store.filteredSkillItems
  return store.filteredAgentItems
})

const featuredItems = computed(() => {
  if (activeTab.value === 'plugin') return store.featuredPlugins
  if (activeTab.value === 'skill') return store.featuredSkills
  return store.featuredAgents
})

const headerConfig = computed(() => {
  if (activeTab.value === 'plugin') {
    return {
      icon: Puzzle,
      title: '插件市场',
      subtitle: '扩展 LuomiNest 的能力边界',
      allLabel: '全部插件',
      emptyIcon: Puzzle,
      emptyText: '没有找到匹配的插件',
    }
  }
  if (activeTab.value === 'skill') {
    return {
      icon: Sparkles,
      title: '技能市场',
      subtitle: '赋予 AI 更丰富的专业技能',
      allLabel: '全部技能',
      emptyIcon: Sparkles,
      emptyText: '没有找到匹配的技能',
    }
  }
  return {
    icon: Bot,
    title: '智能体市场',
    subtitle: '打造专属 AI 智能助手',
    allLabel: '全部智能体',
    emptyIcon: Bot,
    emptyText: '没有找到匹配的智能体',
  }
})

function switchTab(tab: MarketplaceType) {
  activeTab.value = tab
  store.setFilter(tab, { category: undefined })
  showFilters.value = false
  router.replace({ path: route.path, query: { ...route.query, tab } })
}

function selectCategory(id: string) {
  activeCategory.value = id
}

function updateFilter(updates: Partial<MarketplaceFilter>) {
  store.setFilter(activeTab.value, updates)
}

function toggleFilters() {
  showFilters.value = !showFilters.value
}
</script>

<template>
  <div class="market-view">
    <div class="market-header animate-fade-in">
      <div class="header-left">
        <div class="header-icon-wrap">
          <Package :size="24" />
        </div>
        <div class="header-text">
          <h1 class="page-title">扩展</h1>
          <p class="page-subtitle">插件、技能与智能体，一站式管理</p>
        </div>
      </div>
      <div class="market-switch">
        <button
          :class="['switch-btn', { active: activeTab === 'plugin' }]"
          @click="switchTab('plugin')"
        >
          <Puzzle :size="14" />
          <span>插件市场</span>
        </button>
        <button
          :class="['switch-btn', { active: activeTab === 'skill' }]"
          @click="switchTab('skill')"
        >
          <Sparkles :size="14" />
          <span>技能市场</span>
        </button>
        <button
          :class="['switch-btn', { active: activeTab === 'agent' }]"
          @click="switchTab('agent')"
        >
          <Bot :size="14" />
          <span>智能体市场</span>
        </button>
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
          :title="activeTab === 'plugin' ? '热门插件' : activeTab === 'skill' ? '热门技能' : '热门智能体'"
          :type="activeTab"
        />

        <div class="items-section">
          <div class="section-header">
            <h3 class="section-title">
              {{ activeCategory === 'all' ? headerConfig.allLabel : categories.find(c => c.id === activeCategory)?.name || (activeTab === 'plugin' ? '插件' : activeTab === 'skill' ? '技能' : '智能体') }}
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
            <component :is="headerConfig.emptyIcon" :size="48" />
            <p>{{ headerConfig.emptyText }}</p>
            <button class="reset-btn" @click="activeCategory = 'all'; store.clearSearch()">
              重置筛选
            </button>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.market-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.market-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 24px 28px 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-icon-wrap {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-lg);
  background: var(--gradient-hero-soft);
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

.market-switch {
  display: flex;
  gap: 2px;
  padding: 3px;
  background: var(--workspace-panel);
  border-radius: var(--radius-lg);
  border: 1px solid var(--workspace-border);
}

.switch-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  transition: all 0.25s ease-in-out;
}

.switch-btn:hover {
  color: var(--text-secondary);
}

.switch-btn.active {
  background: var(--workspace-card);
  color: var(--lumi-primary);
  box-shadow: var(--shadow-xs);
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
  background: var(--lumi-primary-light);
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
  color: var(--text-inverse);
}

.filter-slide-enter-active {
  animation: lumi-fade-in 0.25s ease-out;
}

.filter-slide-leave-active {
  animation: lumi-fade-in 0.15s ease-out reverse;
}
</style>
