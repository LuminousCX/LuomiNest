<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Puzzle, Sparkles, SlidersHorizontal, X, Package, Bot, Database, Globe, Check, Loader2, Github, RefreshCw } from 'lucide-vue-next'
import { useMarketplaceStore } from '../stores/marketplace'
import { useRepoSourceStore } from '../stores/repo-source'
import { useRegistrySourceStore } from '../stores/registry-source'
import MarketplaceSearch from '../components/marketplace/MarketplaceSearch.vue'
import MarketplaceCategories from '../components/marketplace/MarketplaceCategories.vue'
import MarketplaceFilters from '../components/marketplace/MarketplaceFilters.vue'
import MarketplaceCard from '../components/marketplace/MarketplaceCard.vue'
import MarketplaceBanner from '../components/marketplace/MarketplaceBanner.vue'
import RepoSourcePanel from '../components/marketplace/RepoSourcePanel.vue'
import LumiCardIcon from '../components/common/LumiCardIcon.vue'
import LumiEmptyState from '../components/common/LumiEmptyState.vue'
import LumiButton from '../components/common/LumiButton.vue'
import type { MarketplaceFilter, MarketplaceItem, MarketplaceType } from '../types/marketplace'
import { formatDateTime } from '../utils/format'

const route = useRoute()
const router = useRouter()
const store = useMarketplaceStore()
const repoSourceStore = useRepoSourceStore()
const registryStore = useRegistrySourceStore()

const VALID_TABS: MarketplaceType[] = ['plugin', 'skill', 'agent']
const activeTab = ref<MarketplaceType>('plugin')
const showFilters = ref(false)
const showRepoSource = ref(false)
const showSourceDropdown = ref(false)

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
  // 优先从后端获取目录数据（失败时保持 Mock 数据）
  await store.fetchCatalogFromBackend()
  await repoSourceStore.fetchSources()
  // 加载当前活跃来源的缓存条目
  const activeId = repoSourceStore.activeSourceId
  if (activeId) {
    await repoSourceStore.fetchSourceItems(activeId)
  }
  // 加载发布源列表（含延迟测试）
  await registryStore.fetchSources()
  // 从后端同步安装状态
  await store.syncInstallStatus()
  // 从后端同步统计数据（下载计数、喜欢计数、排行榜）
  await store.syncAllStats()

  document.addEventListener('click', closeSourceDropdown)
})

const handleQuickSwitchSource = async (sourceId: string) => {
  showSourceDropdown.value = false
  if (sourceId === registryStore.activeSourceId) return
  try {
    await registryStore.switchSource(sourceId)
    // 切换源后刷新市场目录（远程注册表数据会变化）
    await store.fetchCatalogFromBackend()
  } catch {
    // 错误已在 store 中记录
  }
}

const closeSourceDropdown = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.closest('.source-quick-switch')) {
    showSourceDropdown.value = false
  }
}

onUnmounted(() => {
  store.cleanup()
  document.removeEventListener('click', closeSourceDropdown)
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

const installedBannerItems = computed(() => {
  if (activeTab.value === 'plugin') return store.installedPlugins
  if (activeTab.value === 'skill') return store.installedSkills
  return store.installedAgents
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

      <!-- 发布源快速切换 -->
      <div class="source-quick-switch">
        <button
          class="source-quick-btn"
          :disabled="registryStore.loading || registryStore.switching"
          @click.stop="showSourceDropdown = !showSourceDropdown"
        >
          <Globe :size="14" />
          <span class="source-quick-label">
            {{ registryStore.activeSource?.name || '发布源' }}
          </span>
          <Loader2
            v-if="registryStore.loading || registryStore.switching"
            :size="12"
            class="spin-animation"
          />
        </button>

        <Transition name="dropdown">
          <div
            v-if="showSourceDropdown"
            class="source-quick-dropdown"
            @click.stop
          >
            <div class="source-quick-dropdown-header">
              <span>选择发布源</span>
              <button
                class="source-quick-refresh"
                title="重新测试延迟"
                :disabled="registryStore.loading"
                @click="registryStore.pingSources()"
              >
                <RefreshCw :size="12" />
              </button>
            </div>
            <div
              v-for="source in registryStore.sources"
              :key="source.id"
              :class="[
                'source-quick-option',
                {
                  active: registryStore.activeSourceId === source.id,
                  disabled: !source.enabled || source.healthy === false,
                },
              ]"
              @click="handleQuickSwitchSource(source.id)"
            >
              <div class="source-quick-option-left">
                <component
                  :is="source.type === 'github' ? Github : source.type === 'cdn' ? Globe : Database"
                  :size="14"
                />
                <span>{{ source.name }}</span>
              </div>
              <div class="source-quick-option-right">
                <span
                  :class="[
                    'source-quick-latency',
                    registryStore.getLatencyStatus(source).className,
                  ]"
                >
                  {{ registryStore.getLatencyStatus(source).label }}
                </span>
                <Check
                  v-if="registryStore.activeSourceId === source.id"
                  :size="14"
                  class="source-quick-check"
                />
              </div>
            </div>
          </div>
        </Transition>
      </div>
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
            同步于 {{ formatDateTime(repoSourceStore.activeSource.lastSyncedAt) }}
          </span>
        </div>
        <div v-else-if="repoSourceStore.activeSource?.status === 'loading'" class="remote-source-indicator loading">
          <Database :size="13" class="spin-animation" />
          <span>正在同步 {{ repoSourceStore.activeSource?.name || '远程仓库' }}...</span>
        </div>

        <MarketplaceBanner
          v-if="installedBannerItems.length > 0 && activeCategory === 'all' && !store.searchQuery"
          :items="installedBannerItems"
          :title="activeTab === 'plugin' ? '已安装插件' : activeTab === 'skill' ? '已安装技能' : '已安装智能体'"
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

          <LumiEmptyState
            v-else
            :icon="headerConfig.emptyIcon"
            :title="headerConfig.emptyText"
            description="尝试调整筛选条件或搜索关键词"
          >
            <template #action>
              <LumiButton variant="outline" size="sm" @click="activeCategory = 'all'; store.clearSearch()">
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
  gap: var(--space-4);
  padding: var(--space-6) var(--space-7) 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}


.market-switch {
  display: flex;
  gap: calc(var(--space-1) / 2);
  padding: var(--space-1);
  background: var(--workspace-panel);
  border-radius: var(--radius-lg);
  border: 1px solid var(--workspace-border);
  backdrop-filter: blur(8px);
}

.switch-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-muted);
  transition: all var(--transition-normal);
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
  gap: var(--space-3);
  padding: 0 var(--space-7);
}

.market-toolbar > :deep(.market-search) {
  flex: 1;
}

.source-quick-switch {
  position: relative;
  flex-shrink: 0;
}

.source-quick-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-fast);
  cursor: pointer;
  max-width: 160px;
}

.source-quick-btn:hover:not(:disabled) {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.source-quick-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.source-quick-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-quick-dropdown {
  position: absolute;
  top: calc(100% + var(--space-2));
  right: 0;
  width: 260px;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 100;
  display: flex;
  flex-direction: column;
  padding: var(--space-2);
  gap: var(--space-1);
}

.source-quick-dropdown-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--text-muted);
}

.source-quick-refresh {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-6);
  height: var(--space-6);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
  cursor: pointer;
}

.source-quick-refresh:hover:not(:disabled) {
  background: var(--surface-hover);
  color: var(--lumi-primary);
}

.source-quick-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.source-quick-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.source-quick-option:hover:not(.disabled) {
  background: var(--surface-hover);
}

.source-quick-option.active {
  background: var(--lumi-primary-light);
}

.source-quick-option.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.source-quick-option-left,
.source-quick-option-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.source-quick-latency {
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
  padding: calc(var(--space-1) / 4) var(--space-1);
  border-radius: var(--radius-sm);
  min-width: var(--space-8);
  text-align: center;
}

.source-quick-latency.fast {
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.source-quick-latency.medium {
  background: var(--lumi-warning-light);
  color: var(--lumi-warning);
}

.source-quick-latency.slow {
  background: var(--lumi-amber-light);
  color: var(--lumi-amber);
}

.source-quick-latency.unavailable,
.source-quick-latency.unknown {
  background: var(--surface-disabled);
  color: var(--text-muted);
}

.source-quick-check {
  color: var(--lumi-success);
}

.dropdown-enter-active,
.dropdown-leave-active {
  transition: all var(--transition-fast);
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
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
  backdrop-filter: blur(12px);
}

.sidebar-filter-toggle {
  padding-top: var(--space-1);
  border-top: 1px solid var(--workspace-border);
  display: flex;
  gap: var(--space-2);
}

.filter-toggle-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1;
  justify-content: center;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
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

.sidebar-repo-source {
  padding-top: var(--space-2);
  border-top: 1px solid var(--workspace-border);
  margin-top: var(--space-1);
}

.filters-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.filters-header span {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* 远程数据源指示器 */
.remote-source-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  border: 1px solid var(--lumi-primary-border);
}

.remote-source-indicator.loading {
  color: var(--text-muted);
  background: var(--workspace-panel);
  border-color: var(--workspace-border);
}

.indicator-sync-time {
  margin-left: auto;
  font-size: var(--text-xs);
  opacity: 0.7;
}

.section-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.items-grid > * {
  animation: lumi-card-enter var(--duration-enter) var(--ease-out-expo) both;
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

</style>
