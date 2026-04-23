<script setup lang="ts">
import { TrendingUp, Clock, Star, Download, Filter } from 'lucide-vue-next'
import type { MarketplaceFilter } from '../../types/marketplace'

const props = defineProps<{
  filter: MarketplaceFilter
}>()

const emit = defineEmits<{
  update: [filter: Partial<MarketplaceFilter>]
}>()

const sortOptions: { value: MarketplaceFilter['sortBy']; label: string; icon: any }[] = [
  { value: 'popular', label: '最热', icon: TrendingUp },
  { value: 'newest', label: '最新', icon: Clock },
  { value: 'rating', label: '评分', icon: Star },
  { value: 'downloads', label: '安装量', icon: Download },
]

const installStatusOptions: { value: string; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'installed', label: '已安装' },
  { value: 'none', label: '未安装' },
]
</script>

<template>
  <div class="market-filters">
    <div class="filter-section">
      <div class="filter-label">
        <Filter :size="14" />
        <span>排序</span>
      </div>
      <div class="filter-options">
        <button
          v-for="opt in sortOptions"
          :key="opt.value"
          :class="['filter-chip', { active: filter.sortBy === opt.value }]"
          @click="emit('update', { sortBy: opt.value })"
        >
          <component :is="opt.icon" :size="13" />
          <span>{{ opt.label }}</span>
        </button>
      </div>
    </div>

    <div class="filter-section">
      <div class="filter-label">
        <Download :size="14" />
        <span>状态</span>
      </div>
      <div class="filter-options">
        <button
          v-for="opt in installStatusOptions"
          :key="opt.value"
          :class="['filter-chip', { active: (filter.installStatus || 'all') === opt.value }]"
          @click="emit('update', { installStatus: opt.value as any })"
        >
          {{ opt.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.market-filters {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.filter-options {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.filter-chip {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--workspace-panel);
  transition: all var(--transition-fast);
}

.filter-chip:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.filter-chip.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}
</style>
