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
  background: #fafaf9;
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
  background: linear-gradient(90deg, transparent 0%, #e7e5e4 15%, #e7e5e4 85%, transparent 100%);
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
  background: #e7e5e4;
}

.bm-icon {
  color: #78716c;
  flex-shrink: 0;
}

.bm-name {
  font-size: 12px;
  color: #57534e;
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
  color: #a8a29e;
  transition: all 0.2s ease-in-out;
}

.bookmark-more:hover {
  background: #e7e5e4;
  color: #78716c;
}
</style>
