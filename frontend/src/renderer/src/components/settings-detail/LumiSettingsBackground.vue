<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const DAMPING_FACTOR = 0.35

const leftRef = ref<HTMLDivElement>()
const rightRef = ref<HTMLDivElement>()
let bodyEl: HTMLElement | null = null

const handleScroll = () => {
  if (!bodyEl || !leftRef.value || !rightRef.value) return
  const offset = bodyEl.scrollTop * DAMPING_FACTOR
  leftRef.value.style.transform = `translateY(${offset}px)`
  rightRef.value.style.transform = `translateY(${offset}px) scaleX(-1)`
}

onMounted(() => {
  bodyEl = leftRef.value?.closest('.lumi-settings-page')?.querySelector('.lumi-settings-page__body') as HTMLElement | null
  if (bodyEl) {
    bodyEl.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()
  }
})

onUnmounted(() => {
  if (bodyEl) {
    bodyEl.removeEventListener('scroll', handleScroll)
  }
})
</script>

<template>
  <div class="lumi-settings-bg" aria-hidden="true">
    <div ref="leftRef" class="lumi-settings-bg__side lumi-settings-bg__side--left" />
    <div ref="rightRef" class="lumi-settings-bg__side lumi-settings-bg__side--right" />
  </div>
</template>

<style scoped>
.lumi-settings-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}

.lumi-settings-bg__side {
  position: absolute;
  top: 0;
  width: var(--lumi-settings-bg-width);
  height: 100%;
  background-image: var(--lumi-settings-bg-image);
  background-repeat: no-repeat;
  background-size: contain;
  background-position: center top;
  opacity: var(--lumi-settings-bg-opacity);
  will-change: transform;
}

.lumi-settings-bg__side--left {
  left: 0;
}

.lumi-settings-bg__side--right {
  right: 0;
  transform: scaleX(-1);
}

@media (max-width: 1200px) {
  .lumi-settings-bg__side {
    display: none;
  }
}
</style>
