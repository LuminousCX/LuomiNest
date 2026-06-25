<script setup lang="ts">
import { Image } from 'lucide-vue-next'
import type { MarketplaceScreenshot } from '../../types/marketplace'

const props = defineProps<{
  screenshots: MarketplaceScreenshot[]
}>()

const emit = defineEmits<{
  open: [index: number]
}>()
</script>

<template>
  <div class="detail-screenshots animate-slide-up">
    <h3 class="section-title">截图预览</h3>
    <div class="screenshots-grid">
      <div
        v-for="(shot, idx) in screenshots"
        :key="idx"
        class="screenshot-thumb"
        @click="emit('open', idx)"
      >
        <img :src="shot.url" :alt="shot.caption || `截图 ${idx + 1}`" loading="lazy" />
        <div class="screenshot-overlay">
          <Image :size="20" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.detail-screenshots {
  margin-bottom: var(--space-6);
}

.section-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-3);
}

.screenshots-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-3);
}

.screenshot-thumb {
  position: relative;
  aspect-ratio: 16/10;
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-fast);
}

.screenshot-thumb:hover {
  border-color: var(--lumi-primary);
  box-shadow: var(--shadow-sm);
}

.screenshot-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.screenshot-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--overlay-bg);
  color: var(--text-inverse);
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.screenshot-thumb:hover .screenshot-overlay {
  opacity: 1;
}
</style>