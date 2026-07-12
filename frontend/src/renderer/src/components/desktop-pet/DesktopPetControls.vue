<script setup lang="ts">
/**
 * LuomiNest 桌面宠物控制面板子组件
 *
 * 从 DesktopPetView.vue 拆分，仅负责控制面板 UI（reset pose / always-on-top toggle / close）。
 * 显示/隐藏与 pin 状态由父组件控制，操作通过 emit 上报。
 */
import { RotateCcw, X, Pin, PinOff } from 'lucide-vue-next'

defineProps<{
  visible: boolean
  isAlwaysOnTop: boolean
}>()

const emit = defineEmits<{
  'reset-pose': []
  'toggle-always-on-top': []
  close: []
  mouseenter: []
  mouseleave: []
}>()
</script>

<template>
  <div
    class="controls-anchor"
    @mouseenter="emit('mouseenter')"
    @mouseleave="emit('mouseleave')"
  >
    <Transition name="controls-fade">
      <div v-if="visible" class="controls-panel">
        <button class="control-btn" title="Reset Pose" @click="emit('reset-pose')">
          <RotateCcw :size="16" />
        </button>
        <button
          class="control-btn"
          :class="{ active: isAlwaysOnTop }"
          :title="isAlwaysOnTop ? 'Unpin' : 'Pin on Top'"
          @click="emit('toggle-always-on-top')"
        >
          <Pin v-if="isAlwaysOnTop" :size="16" />
          <PinOff v-else :size="16" />
        </button>
        <button class="control-btn danger" title="Close Pet" @click="emit('close')">
          <X :size="16" />
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.controls-anchor {
  position: fixed;
  bottom: 0;
  right: 0;
  width: 80px;
  height: 80px;
  z-index: var(--z-dropdown);
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  padding: var(--space-3);
  /* Allow clicking the controls instead of starting a window drag. */
  -webkit-app-region: no-drag;
}

.controls-panel {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-2);
  border-radius: var(--radius-lg);
  background: var(--overlay-bg);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-lg);
}

.control-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  background: color-mix(in srgb, var(--surface) 8%, transparent);
  color: var(--text-inverse);
  cursor: pointer;
  transition: all var(--duration-leave) var(--ease-in-out);
}

.control-btn:hover {
  background: color-mix(in srgb, var(--surface) 14%, transparent);
  transform: scale(1.05);
}

.control-btn.active {
  background: var(--lumi-brand-border);
  border-color: var(--lumi-brand-border);
  color: var(--lumi-brand);
}

.control-btn.danger:hover {
  background: var(--task-red-border);
  border-color: var(--task-red-border);
  color: var(--lumi-danger);
}

.controls-fade-enter-active {
  transition: opacity var(--duration-leave) var(--ease-in-out), transform var(--duration-leave) var(--ease-in-out);
}

.controls-fade-leave-active {
  transition: opacity var(--duration-fast) var(--ease-in-out), transform var(--duration-fast) var(--ease-in-out);
}

.controls-fade-enter-from,
.controls-fade-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.95);
}
</style>
