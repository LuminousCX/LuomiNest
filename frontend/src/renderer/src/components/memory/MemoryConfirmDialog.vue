<script setup lang="ts">
import { Loader2, AlertCircle } from 'lucide-vue-next'

interface Props {
  show: boolean
  title: string
  message: string
  danger: boolean
  isProcessing: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'cancel'): void
  (e: 'confirm'): void
}>()
</script>

<template>
  <div v-if="show" class="confirm-overlay" @click="emit('cancel')">
    <div class="confirm-dialog" @click.stop>
      <div class="confirm-header">
        <AlertCircle v-if="danger" :size="24" class="danger-icon" />
        <h3>{{ title }}</h3>
      </div>
      <div class="confirm-body">
        <p>{{ message }}</p>
      </div>
      <div class="confirm-footer">
        <button class="h-btn" @click="emit('cancel')" :disabled="isProcessing">取消</button>
        <button
          class="h-btn danger"
          @click="emit('confirm')"
          :disabled="isProcessing"
        >
          <Loader2 v-if="isProcessing" :size="14" class="spinning" />
          <span v-else>确定</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.confirm-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--overlay-backdrop);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1001;
}

.confirm-dialog {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-6);
  max-width: 400px;
  width: 90%;
  box-shadow: var(--shadow-xl);
}

.confirm-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: var(--space-3);
}

.danger-icon {
  color: var(--lumi-danger);
}

.confirm-header h3 {
  margin: 0;
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--text);
}

.confirm-body {
  margin-bottom: var(--space-6);
}

.confirm-body p {
  margin: 0;
  font-size: var(--text-md);
  color: var(--text-muted);
  line-height: 1.5;
}

.confirm-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}

.h-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: var(--radius-xs);
  font-size: var(--text-base);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-slow);
  white-space: nowrap;
}

.h-btn:hover { background: var(--surface-hover); color: var(--text); }

.h-btn.danger {
  background: var(--lumi-danger-light);
  border: 1px solid var(--lumi-danger-border);
  color: var(--lumi-danger);
}

.h-btn.danger:hover {
  background: var(--lumi-danger-light);
}

.h-btn:disabled { opacity: 0.5; cursor: default; }

.spinning { animation: spin 1s linear infinite; }

@media (max-width: 768px) {
  .confirm-dialog {
    padding: var(--space-4);
  }
}
</style>
