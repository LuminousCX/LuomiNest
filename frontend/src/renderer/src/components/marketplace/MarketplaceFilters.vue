<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { TrendingUp, Clock, Star, Download, Filter } from 'lucide-vue-next'
import type { LucideIcon } from 'lucide-vue-next'
import type { MarketplaceFilter, InstallStatus } from '../../types/marketplace'

const { t } = useI18n()

const props = defineProps<{
  filter: MarketplaceFilter
}>()

const emit = defineEmits<{
  update: [filter: Partial<MarketplaceFilter>]
}>()

const sortOptions: { value: MarketplaceFilter['sortBy']; label: string; icon: LucideIcon }[] = [
  { value: 'popular', label: t('market.filters.popular'), icon: TrendingUp },
  { value: 'newest', label: t('market.filters.newest'), icon: Clock },
  { value: 'rating', label: t('market.filters.rating'), icon: Star },
  { value: 'downloads', label: t('market.filters.downloads'), icon: Download },
]

const installStatusOptions: { value: InstallStatus | 'all'; label: string }[] = [
  { value: 'all', label: t('market.filters.all') },
  { value: 'installed', label: t('market.filters.installed') },
  { value: 'none', label: t('market.filters.none') },
]
</script>

<template>
  <div class="market-filters">
    <div class="filter-section">
      <div class="filter-label">
        <Filter :size="14" />
        <span>{{ t('market.filters.sortLabel') }}</span>
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
        <span>{{ t('market.filters.statusLabel') }}</span>
      </div>
      <div class="filter-options">
        <button
          v-for="opt in installStatusOptions"
          :key="opt.value"
          :class="['filter-chip', { active: (filter.installStatus || 'all') === opt.value }]"
          @click="emit('update', { installStatus: opt.value as InstallStatus | 'all' })"
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
  gap: var(--space-4);
}

.filter-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.filter-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.filter-options {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.filter-chip {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  background: var(--workspace-panel);
  transition: all var(--transition-fast);
}

.filter-chip:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.filter-chip.active {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

</style>
