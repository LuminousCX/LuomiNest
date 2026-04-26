<script setup lang="ts">
import type { MarketplaceCategory } from '../../types/marketplace'
import {
  LayoutGrid, Cpu, Wrench, Puzzle, Palette, Zap,
  MessageCircle, BookOpen, Code, Image, Heart,
  ChevronRight
} from 'lucide-vue-next'

const ICON_MAP: Record<string, any> = {
  LayoutGrid, Cpu, Wrench, Puzzle, Palette, Zap,
  MessageCircle, BookOpen, Code, Image, Heart,
}

defineProps<{
  categories: MarketplaceCategory[]
  activeCategory: string
}>()

const emit = defineEmits<{
  select: [categoryId: string]
}>()
</script>

<template>
  <div class="market-categories">
    <div class="category-list">
      <button
        v-for="cat in categories"
        :key="cat.id"
        :class="['category-btn', { active: activeCategory === cat.id }]"
        @click="emit('select', cat.id)"
      >
        <component
          v-if="cat.icon && ICON_MAP[cat.icon]"
          :is="ICON_MAP[cat.icon]"
          :size="16"
          class="cat-icon"
        />
        <span class="cat-name">{{ cat.name }}</span>
        <ChevronRight v-if="cat.children?.length" :size="14" class="cat-expand" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.market-categories {
  width: 100%;
}

.category-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.category-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
  text-align: left;
}

.category-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.category-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  font-weight: 500;
}

.cat-icon {
  flex-shrink: 0;
}

.cat-name {
  flex: 1;
}

.cat-expand {
  color: var(--text-muted);
  flex-shrink: 0;
  transition: transform var(--transition-fast);
}

.category-btn:hover .cat-expand {
  transform: translateX(2px);
}

.category-btn.active .cat-expand {
  color: var(--lumi-primary);
}
</style>
