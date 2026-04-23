<script setup lang="ts">
import { computed } from 'vue'
import type { MarketCategory } from '../../types/marketplace'
import MarketIcon from './MarketIcon.vue'

const props = defineProps<{
  categories: MarketCategory[]
  activeCategory: string
}>()

const emit = defineEmits<{
  select: [categoryId: string]
}>()

const groupedCategories = computed(() => {
  return props.categories
})
</script>

<template>
  <div class="category-filter">
    <h4 class="filter-title">分类</h4>
    <div class="category-list">
      <button
        v-for="cat in groupedCategories"
        :key="cat.id"
        :class="['category-item', { active: activeCategory === cat.id }]"
        @click="emit('select', cat.id)"
      >
        <MarketIcon :name="cat.icon" :size="16" />
        <span class="cat-name">{{ cat.name }}</span>
        <span class="cat-count">{{ cat.count }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.category-filter {
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

.category-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.category-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
}

.category-item:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.category-item.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  font-weight: 500;
}

.cat-name {
  flex: 1;
}

.cat-count {
  font-size: 11px;
  color: var(--text-muted);
  min-width: 20px;
  text-align: right;
}

.category-item.active .cat-count {
  color: var(--lumi-primary);
  opacity: 0.7;
}

@media (max-width: 768px) {
  .category-filter {
    flex-direction: row;
    overflow-x: auto;
    gap: 6px;
  }

  .filter-title {
    display: none;
  }

  .category-list {
    flex-direction: row;
    gap: 6px;
  }

  .category-item {
    white-space: nowrap;
    padding: 6px 12px;
    font-size: 12px;
  }

  .cat-count {
    display: none;
  }
}
</style>
