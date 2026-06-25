<script setup lang="ts">
import { X, ChevronDown } from 'lucide-vue-next'
import type { MarketplaceScreenshot } from '../../types/marketplace'

const props = defineProps<{
  screenshots: MarketplaceScreenshot[]
  currentIndex: number | null
}>()

const emit = defineEmits<{
  close: []
  prev: []
  next: []
}>()
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="currentIndex !== null && screenshots[currentIndex]" class="screenshot-modal" @click="emit('close')">
        <div class="modal-content" @click.stop>
          <button class="modal-close" @click="emit('close')">
            <X :size="20" />
          </button>
          <img :src="screenshots[currentIndex].url" :alt="screenshots[currentIndex].caption" />
          <div class="modal-caption">
            {{ screenshots[currentIndex].caption || `截图 ${currentIndex + 1}` }}
            <span class="modal-counter">{{ currentIndex + 1 }} / {{ screenshots.length }}</span>
          </div>
          <div class="modal-nav">
            <button v-if="currentIndex > 0" class="nav-btn prev" @click.stop="emit('prev')">
              <ChevronDown :size="20" style="transform: rotate(90deg)" />
            </button>
            <button v-if="currentIndex < screenshots.length - 1" class="nav-btn next" @click.stop="emit('next')">
              <ChevronDown :size="20" style="transform: rotate(-90deg)" />
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.screenshot-modal {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--overlay-backdrop);
  animation: lumi-fade-in var(--duration-fast) var(--ease-out-expo);
}

.modal-content {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.modal-content img {
  max-width: 100%;
  max-height: 80vh;
  border-radius: var(--radius-lg);
  object-fit: contain;
}

.modal-close {
  position: absolute;
  top: calc(var(--space-8) * -1);
  right: 0;
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-inverse);
  transition: all var(--transition-fast);
}

.modal-close:hover {
  background: color-mix(in srgb, var(--text-inverse) 20%, transparent);
}

.modal-caption {
  margin-top: var(--space-3);
  font-size: var(--text-base);
  color: color-mix(in srgb, var(--text-inverse) 70%, transparent);
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.modal-counter {
  font-size: var(--text-xs);
  opacity: 0.5;
}

.modal-nav {
  position: absolute;
  top: 50%;
  left: -50px;
  right: -50px;
  display: flex;
  justify-content: space-between;
  transform: translateY(-50%);
  pointer-events: none;
}

.nav-btn {
  width: var(--nav-item-height);
  height: var(--nav-item-height);
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-inverse);
  background: color-mix(in srgb, var(--text-inverse) 15%, transparent);
  pointer-events: auto;
  transition: all var(--transition-fast);
}

.nav-btn:hover {
  background: color-mix(in srgb, var(--text-inverse) 30%, transparent);
}

.modal-enter-active {
  animation: lumi-fade-in var(--duration-normal) var(--ease-out-expo);
}

.modal-leave-active {
  animation: lumi-fade-in var(--duration-fast) var(--ease-out-expo) reverse;
}
</style>