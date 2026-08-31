<template>
  <Teleport to="body">
    <TransitionGroup name="toast-slide" tag="div" class="toast-container">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="toast-item"
        :class="`toast-${toast.type}`"
        role="alert"
        @click="remove(toast.id)"
      >
        <span class="toast-icon" aria-hidden="true">
          <CheckCircle v-if="toast.type === 'success'" :size="18" />
          <XCircle v-else-if="toast.type === 'error'" :size="18" />
          <AlertTriangle v-else-if="toast.type === 'warning'" :size="18" />
          <Info v-else :size="18" />
        </span>
        <span class="toast-message">{{ toast.message }}</span>
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<script setup lang="ts">
import { CheckCircle, XCircle, AlertTriangle, Info } from 'lucide-vue-next'
import { useToast } from '../../composables/useToast'

const { toasts, remove } = useToast()
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: var(--space-5);
  right: var(--space-5);
  z-index: var(--z-toast);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  pointer-events: none;
  max-width: calc(var(--space-9) * 8 + var(--space-4));
}

.toast-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  font-size: var(--text-md);
  font-weight: var(--font-medium);
  cursor: pointer;
  pointer-events: auto;
  /* 反相高对比：明色主题黑底白字 / 暗色主题白底黑字 */
  background: var(--toast-bg);
  color: var(--toast-fg);
  border: 1px solid var(--toast-border);
  box-shadow: var(--toast-shadow);
  transition:
    transform var(--transition-fast),
    box-shadow var(--transition-fast),
    opacity var(--transition-fast);
}

.toast-item:hover {
  transform: translateX(calc(var(--space-1) * -1));
  box-shadow: var(--shadow-xl);
}

/* 类型色仅作为图标点缀，保留类型识别；文字与背景统一反相 */
.toast-success .toast-icon { color: var(--lumi-success); }
.toast-error .toast-icon { color: var(--lumi-danger); }
.toast-warning .toast-icon { color: var(--lumi-warning); }
.toast-info .toast-icon { color: var(--lumi-info); }

.toast-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.toast-message {
  line-height: var(--leading-snug);
}

.toast-slide-enter-active {
  transition: all var(--duration-slow) var(--ease-out-expo);
}

.toast-slide-leave-active {
  transition: all var(--duration-fast) var(--ease-default);
}

.toast-slide-enter-from {
  opacity: 0;
  transform: translateX(calc(var(--space-8) + var(--space-5)));
}

.toast-slide-leave-to {
  opacity: 0;
  transform: translateX(calc(var(--space-8) + var(--space-5))) scale(0.95);
}

.toast-slide-move {
  transition: transform var(--transition-fast);
}

</style>
