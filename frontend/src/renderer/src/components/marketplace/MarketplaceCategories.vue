<script setup lang="ts">
import type { MarketplaceCategory } from '../../types/marketplace'
import type { LucideIcon } from 'lucide-vue-next'
import {
  LayoutGrid, Cpu, Wrench, Puzzle, Palette, Zap,
  MessageCircle, BookOpen, Code, Image, Heart,
  Bot, Lightbulb, BarChart3, Terminal, GraduationCap,
  ChevronRight
} from 'lucide-vue-next'

const ICON_MAP: Record<string, LucideIcon> = {
  LayoutGrid, Cpu, Wrench, Puzzle, Palette, Zap,
  MessageCircle, BookOpen, Code, Image, Heart,
  Bot, Lightbulb, BarChart3, Terminal, GraduationCap,
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
  gap: calc(var(--space-1) / 2);
}

.category-btn {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  color: var(--text-secondary);
  transition: all var(--transition-normal);
  text-align: left;
  position: relative;
}

.category-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.category-btn.active {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  font-weight: var(--font-medium);
}

.category-btn.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: calc(var(--space-1) + var(--space-1) / 2);
  bottom: calc(var(--space-1) + var(--space-1) / 2);
  width: calc(var(--space-1) / 2 + 1px);
  border-radius: 0 calc(var(--space-1) / 2 + 1px) calc(var(--space-1) / 2 + 1px) 0;
  background: var(--lumi-brand);
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
  color: var(--lumi-brand);
}

@media (prefers-reduced-motion: reduce) {
  .category-btn,
  .cat-expand {
    transition: none;
  }
}
</style>
