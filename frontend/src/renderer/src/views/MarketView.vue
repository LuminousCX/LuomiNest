<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Puzzle, Sparkles, SlidersHorizontal, X, Package, Bot, Database } from 'lucide-vue-next'
import { useMarketplaceStore } from '../stores/marketplace'
import { useRepoSourceStore } from '../stores/repo-source'
import MarketplaceSearch from '../components/marketplace/MarketplaceSearch.vue'
import MarketplaceCategories from '../components/marketplace/MarketplaceCategories.vue'
import MarketplaceFilters from '../components/marketplace/MarketplaceFilters.vue'
import MarketplaceCard from '../components/marketplace/MarketplaceCard.vue'
import MarketplaceBanner from '../components/marketplace/MarketplaceBanner.vue'
import RepoSourcePanel from '../components/marketplace/RepoSourcePanel.vue'
import LumiCardIcon from '../components/common/LumiCardIcon.vue'
import type { MarketplaceFilter, MarketplaceItem, MarketplaceType } from '../types/marketplace'

// 安全的同步时间格式化，防止 Invalid Date
const formatSyncTime = (ts: string) => {
  try {
    const d = new Date(ts)
    if (isNaN(d.getTime())) return ts
    return d.toLocaleString('zh-CN')
  } catch {
    return ts
  }
}

const route = useRoute()
const router = useRouter()
const store = useMarketplaceStore()
const repoSourceStore = useRepoSourceStore()

const VALID_TABS: MarketplaceType[] = ['plugin', 'skill', 'agent']
const activeTab = ref<MarketplaceType>('plugin')
const showFilters = ref(false)
const showRepoSource = ref(false)

// 是否使用远程仓库来源的数据
const useRemoteData = computed(() => {
  const active = repoSourceStore.activeSource
  return active && active.enabled && active.status === 'loaded'
})

watch(() => route.query.tab, (tab) => {
  const t = typeof tab === 'string' ? tab : ''
  if (VALID_TABS.includes(t as MarketplaceType)) {
    activeTab.value = t as MarketplaceType
  }
}, { immediate: true })

// 初始化时加载仓库来源数据
onMounted(async () => {
  await repoSourceStore.fetchSources()
  // 加载当前活跃来源的缓存条目
  const activeId = repoSourceStore.activeSourceId
  if (activeId) {
    await repoSourceStore.fetchSourceItems(activeId)
  }
  // 从后端同步安装状态
  await store.syncInstallStatus()
  // 从后端同步统计数据（下载计数、喜欢计数、排行榜）
  await store.syncAllStats()
})

onUnmounted(() => {
  store.cleanup()
})

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

// 远程仓库来源的条目（按当前 tab 过滤）
const remoteItems = computed<MarketplaceItem[]>(() => {
  const items = repoSourceStore.activeSourceItems
  return items.filter(i => i.type === activeTab.value)
})

// 合并后的条目列表：如果使用远程数据则显示远程条目，否则显示本地 mock 数据
const filteredItems = computed(() => {
  if (useRemoteData.value && remoteItems.value.length > 0) {
    return remoteItems.value
  }
  if (activeTab.value === 'plugin') return store.filteredPluginItems
  if (activeTab.value === 'skill') return store.filteredSkillItems
  return store.filteredAgentItems
})

const featuredItems = computed(() => {
  if (useRemoteData.value && remoteItems.value.length > 0) {
    return remoteItems.value.filter(i => i.featured).sort((a, b) => b.rating - a.rating)
  }
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
        <LumiCardIcon :icon="Package" :size="24" theme="Package" />
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
          <button :class="['filter-toggle-btn', { active: showRepoSource }]" @click="showRepoSource = !showRepoSource">
            <Database :size="14" />
            <span>来源</span>
          </button>
        </div>

        <Transition name="filter-slide">
          <div v-if="showRepoSource" class="sidebar-repo-source">
            <RepoSourcePanel />
          </div>
        </Transition>

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
        <!-- 远程数据源指示器 -->
        <div v-if="useRemoteData" class="remote-source-indicator">
          <Database :size="13" />
          <span>数据来源: {{ repoSourceStore.activeSource?.name || '远程仓库' }}</span>
          <span v-if="repoSourceStore.activeSource?.lastSyncedAt" class="indicator-sync-time">
            同步于 {{ formatSyncTime(repoSourceStore.activeSource.lastSyncedAt) }}
          </span>
        </div>
        <div v-else-if="repoSourceStore.activeSource?.status === 'loading'" class="remote-source-indicator loading">
          <Database :size="13" class="spin-animation" />
          <span>正在同步 {{ repoSourceStore.activeSource?.name || '远程仓库' }}...</span>
        </div>

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
  backdrop-filter: blur(8px);
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
  position: relative;
}

.switch-btn:hover {
  color: var(--text-secondary);
}

.switch-btn.active {
  background: var(--workspace-card);
  color: var(--lumi-primary);
  box-shadow: var(--shadow-xs), 0 0 0 1px var(--lumi-primary-glow);
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
  backdrop-filter: blur(12px);
}

.sidebar-filter-toggle {
  padding-top: 4px;
  border-top: 1px solid var(--workspace-border);
  display: flex;
  gap: 6px;
}

.filter-toggle-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  justify-content: center;
  padding: 10px 10px;
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

.sidebar-repo-source {
  padding-top: 8px;
  border-top: 1px solid var(--workspace-border);
  margin-top: 4px;
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

/* 远程数据源指示器 */
.remote-source-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  margin-bottom: 12px;
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  border: 1px solid rgba(var(--lumi-primary-rgb, 20, 126, 188), 0.15);
}

.remote-source-indicator.loading {
  color: var(--text-muted);
  background: var(--workspace-panel);
  border-color: var(--workspace-border);
}

.indicator-sync-time {
  margin-left: auto;
  font-size: 11px;
  opacity: 0.7;
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

.items-grid > * {
  animation: lumi-card-enter 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.items-grid > *:nth-child(1) { animation-delay: 0ms; }
.items-grid > *:nth-child(2) { animation-delay: 60ms; }
.items-grid > *:nth-child(3) { animation-delay: 120ms; }
.items-grid > *:nth-child(4) { animation-delay: 180ms; }
.items-grid > *:nth-child(5) { animation-delay: 240ms; }
.items-grid > *:nth-child(6) { animation-delay: 300ms; }

@keyframes lumi-card-enter {
  from { opacity: 0; transform: translateY(12px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--text-muted);
  animation: lumi-card-enter 0.5s ease-out both;
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
