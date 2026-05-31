<script setup lang="ts">
import { Globe, ChevronRight } from 'lucide-vue-next'

interface Bookmark {
  name: string
  url: string
}

defineProps<{
  bookmarks: Bookmark[]
}>()

const emit = defineEmits<{
  select: [url: string]
}>()
</script>

<template>
  <div class="bookmark-bar">
    <button
      v-for="(bm, idx) in bookmarks"
      :key="idx"
      class="bookmark-item"
      @click="emit('select', bm.url)"
    >
      <Globe :size="13" class="bm-icon" />
      <span class="bm-name">{{ bm.name }}</span>
    </button>
    <button class="bookmark-more">
      <ChevronRight :size="14" />
    </button>
  </div>
</template>

<style scoped>
.bookmark-bar {
  height: 34px;
  background: var(--bg);
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 4px;
  overflow-x: auto;
  scrollbar-width: none;
  position: relative;
}

.bookmark-bar::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 12px;
  right: 12px;
  height: 1px;
  background: var(--divider-soft);
}

.bookmark-bar::-webkit-scrollbar {
  display: none;
}

.bookmark-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background 0.2s ease-in-out;
  white-space: nowrap;
}

.bookmark-item:hover {
  background: var(--surface-hover);
}

.bm-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.bm-name {
  font-size: 12px;
  color: var(--text-secondary);
}

.bookmark-more {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  transition: all 0.2s ease-in-out;
}

.bookmark-more:hover {
  background: var(--surface-hover);
  color: var(--text-muted);
}
</style>
