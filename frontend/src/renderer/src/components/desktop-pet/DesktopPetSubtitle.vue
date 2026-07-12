<script setup lang="ts">
/**
 * LuomiNest 桌面宠物字幕 overlay 子组件
 *
 * 从 DesktopPetView.vue 拆分，仅负责字幕 UI 与 fade transition。
 */
defineProps<{
  visible: boolean
  text: string
}>()
</script>

<template>
  <Transition name="pet-subtitle-fade">
    <div
      v-if="visible && text"
      class="pet-subtitle-overlay"
    >
      <span class="pet-subtitle-text">{{ text }}</span>
    </div>
  </Transition>
</template>

<style scoped>
.pet-subtitle-overlay {
  position: fixed;
  bottom: var(--space-4);
  left: 50%;
  transform: translateX(-50%);
  z-index: 50;
  max-width: 90%;
  padding: 6px 14px;
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--surface) 85%, transparent);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow: var(--shadow-md);
  pointer-events: none;
}

.pet-subtitle-text {
  font-size: var(--text-sm);
  line-height: 1.5;
  color: var(--text);
  text-align: center;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.pet-subtitle-fade-enter-active {
  transition: opacity var(--duration-normal) var(--ease-in-out), transform var(--duration-normal) var(--ease-in-out);
}

.pet-subtitle-fade-leave-active {
  transition: opacity var(--duration-slow) var(--ease-in-out), transform var(--duration-slow) var(--ease-in-out);
}

.pet-subtitle-fade-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(6px);
}

.pet-subtitle-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(0);
}
</style>
