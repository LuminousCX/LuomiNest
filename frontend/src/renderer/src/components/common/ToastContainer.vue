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
  max-width: 400px;
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
  backdrop-filter: var(--glass-blur);
  box-shadow: var(--shadow-lg);
  transition:
    transform var(--transition-fast),
    box-shadow var(--transition-fast),
    opacity var(--transition-fast);
}

.toast-item:hover {
  transform: translateX(-4px);
  box-shadow: var(--shadow-xl);
}

.toast-success {
  background: var(--lumi-success-light);
  border: 1px solid var(--task-green-border);
  color: var(--lumi-success);
}

.toast-error {
  background: var(--lumi-danger-light);
  border: 1px solid var(--task-red-border);
  color: var(--lumi-danger);
}

.toast-warning {
  background: var(--lumi-warning-light);
  border: 1px solid var(--lumi-amber-border);
  color: var(--lumi-warning);
}

.toast-info {
  background: var(--lumi-info-light);
  border: 1px solid var(--task-blue-border);
  color: var(--lumi-info);
}

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
  transform: translateX(60px);
}

.toast-slide-leave-to {
  opacity: 0;
  transform: translateX(60px) scale(0.95);
}

.toast-slide-move {
  transition: transform var(--transition-fast);
}

@media (prefers-reduced-motion: reduce) {
  .toast-slide-enter-active,
  .toast-slide-leave-active,
  .toast-slide-move,
  .toast-item {
    transition: none;
  }
}
</style>
