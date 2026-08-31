<script setup lang="ts">
import { Activity } from 'lucide-vue-next'
import type { LayerTab, MemoryStats } from './types'

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
      :style="{ '--tab-color': tab.color }"
      @click="emit('switchTab', tab.id)"
    >
      <div class="nav-top">
        <div class="nav-icon-wrap" :style="{ background: `color-mix(in srgb, ${tab.color} 10%, transparent)` }">
          <component :is="tab.icon" :size="20" :style="{ color: tab.color }" />
        </div>
        <div class="nav-meta">
          <span class="nav-name">{{ tab.name }}</span>
          <span class="nav-sub">{{ tab.desc }}</span>
        </div>
      </div>
      <div class="nav-stats">
        <span v-if="tab.id === 'profile'" class="nav-stat">{{ hasSummary ? '已总结' : '未总结' }}</span>
        <span v-else-if="tab.id === 'facts'" class="nav-stat">{{ factCount }} 条</span>
        <span v-else-if="tab.id === 'knowledge'" class="nav-stat">{{ knowledgeSectionCount > 0 ? knowledgeSectionCount + ' 节' : '空' }}</span>
        <span v-else-if="tab.id === 'history'" class="nav-stat">{{ dailyCount }} 天</span>
      </div>
    </div>

    <div class="stats-overview">
      <div class="stats-header">
        <Activity :size="16" />
        <span>记忆概览</span>
      </div>
      <div class="stats-grid">
        <div class="stat-item">
          <span class="stat-value">{{ memoryStats.totalFacts }}</span>
          <span class="stat-label">事实</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ memoryStats.dailyCount }}</span>
          <span class="stat-label">天数</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ knowledgeSectionCount }}</span>
          <span class="stat-label">知识</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ memoryStats.hasProfile ? '有' : '无' }}</span>
          <span class="stat-label">档案</span>
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
              :style="{ width: `${(cat.count / Math.max(memoryStats.totalFacts, 1)) * 100}%`, background: cat.color }"
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
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  background: var(--workspace-card, var(--surface));
  border-radius: var(--radius-lg);
  border: 1px solid var(--workspace-border, var(--border));
  box-shadow: var(--shadow-sm);
  align-self: flex-start;
  position: sticky;
  top: 0;
  max-height: 100%;
}

.stats-overview {
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: var(--bg-secondary, var(--bg));
  border: 1px solid var(--border-light, var(--border));
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
  border: 1px solid var(--border-light, var(--border));
  background: var(--bg-secondary, var(--bg));
  cursor: pointer;
  transition: all var(--transition-normal);
}

.nav-card:hover {
  border-color: var(--tab-color);
  box-shadow: 0 2px 12px color-mix(in srgb, var(--tab-color) 8%, transparent);
  transform: translateX(2px);
}

.nav-card.active {
  border-color: var(--tab-color);
  background: color-mix(in srgb, var(--tab-color) 6%, transparent);
  box-shadow: 0 2px 16px color-mix(in srgb, var(--tab-color) 12%, transparent);
}

.nav-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: var(--space-2);
}

.nav-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
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
    overflow-y: visible;
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
