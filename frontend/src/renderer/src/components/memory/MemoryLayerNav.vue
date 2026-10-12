<script setup lang="ts">
import { Activity } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import type { LayerTab, MemoryStats } from './types'

const { t } = useI18n()

interface Props {
  layerTabs: LayerTab[]
  activeTab: string
  hasSummary: boolean
  factCount: number
  knowledgeSectionCount: number
  dailyCount: number
  memoryStats: MemoryStats
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'switchTab', tabId: string): void
}>()
</script>

<template>
  <div class="layer-nav">
    <div
      v-for="tab in layerTabs"
      :key="tab.id"
      :class="['nav-card', { active: activeTab === tab.id }]"
      @click="emit('switchTab', tab.id)"
    >
      <div class="nav-top">
        <component :is="tab.icon" :size="18" class="nav-icon" />
        <div class="nav-meta">
          <span class="nav-name">{{ tab.name }}</span>
          <span class="nav-sub">{{ tab.desc }}</span>
        </div>
      </div>
      <div class="nav-stats">
        <span v-if="tab.id === 'profile'" class="nav-stat">{{ hasSummary ? t('memory.nav.summarized') : t('memory.nav.notSummarized') }}</span>
        <span v-else-if="tab.id === 'facts'" class="nav-stat">{{ t('memory.nav.factUnit', { n: factCount }) }}</span>
        <span v-else-if="tab.id === 'knowledge'" class="nav-stat">{{ knowledgeSectionCount > 0 ? t('memory.nav.sectionUnit', { n: knowledgeSectionCount }) : t('memory.nav.empty') }}</span>
        <span v-else-if="tab.id === 'history'" class="nav-stat">{{ t('memory.nav.dayUnit', { n: dailyCount }) }}</span>
      </div>
    </div>

    <div class="stats-overview">
      <div class="stats-header">
        <Activity :size="16" />
        <span>{{ t('memory.nav.overview') }}</span>
      </div>
      <div class="stats-grid">
        <div class="stat-item">
          <span class="stat-value">{{ memoryStats.totalFacts }}</span>
          <span class="stat-label">{{ t('memory.nav.statFacts') }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ memoryStats.dailyCount }}</span>
          <span class="stat-label">{{ t('memory.nav.statDays') }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ knowledgeSectionCount }}</span>
          <span class="stat-label">{{ t('memory.nav.statKnowledge') }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ memoryStats.hasProfile ? t('memory.nav.has') : t('memory.nav.none') }}</span>
          <span class="stat-label">{{ t('memory.nav.statProfile') }}</span>
        </div>
      </div>
      <div class="category-bars">
        <div
          v-for="cat in memoryStats.categories"
          :key="cat.name"
          class="category-bar-item"
        >
          <span class="cat-name">{{ cat.name }}</span>
          <div class="cat-bar-wrap">
            <div
              class="cat-bar-fill"
              :style="{ width: `${(cat.count / Math.max(memoryStats.totalFacts, 1)) * 100}%` }"
            ></div>
          </div>
          <span class="cat-count">{{ cat.count }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.layer-nav {
  width: 260px;
  flex-shrink: 0;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--workspace-border);
  box-shadow: var(--shadow-sm);
}

.stats-overview {
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
}

.stats-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-bottom: var(--space-3);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}

.stat-item {
  text-align: center;
  padding: var(--space-2);
  background: var(--surface);
  border-radius: var(--radius-xs);
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}

.stat-label {
  display: block;
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: 2px;
}

.category-bars {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.category-bar-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.cat-name {
  font-size: var(--text-xs);
  color: var(--text-muted);
  width: var(--space-7);
}

.cat-bar-wrap {
  flex: 1;
  height: var(--space-1);
  background: var(--border);
  border-radius: var(--radius-xs);
  overflow: hidden;
}

.cat-bar-fill {
  height: 100%;
  border-radius: var(--radius-xs);
  background: var(--text-muted);
  transition: width var(--transition-slow);
}

.cat-count {
  font-size: var(--text-xs);
  color: var(--text-muted);
  width: var(--space-5);
  text-align: right;
}

.nav-card {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  background: var(--bg-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.nav-card:hover {
  border-color: var(--border);
  background: var(--surface-hover);
}

/* 选中态：控制台式弱底色 + 主色文字 */
.nav-card.active {
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

.nav-card.active .nav-name {
  color: var(--lumi-brand);
}

.nav-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: var(--space-2);
}

/* 中性裸图标（无彩色底块） */
.nav-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.nav-card.active .nav-icon {
  color: var(--lumi-brand);
}

.nav-meta { flex: 1; min-width: 0; }

.nav-name {
  display: block;
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text);
}

.nav-sub {
  display: block;
  font-size: var(--text-xs);
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-stats {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-family: monospace;
}

.nav-stat {
  display: inline-block;
  padding: 2px var(--space-2);
  border-radius: var(--radius-xs);
  background: var(--surface);
}

@media (max-width: 768px) {
  .layer-nav {
    width: 100%;
    padding: var(--space-4);
    border-right: none;
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
    flex-direction: row;
  }

  .stats-overview {
    width: 100%;
  }

  .nav-card {
    width: calc(50% - 8px);
    min-width: 140px;
  }
}
</style>
