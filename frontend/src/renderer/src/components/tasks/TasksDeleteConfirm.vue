<script setup lang="ts">
import { X, Trash2, AlertTriangle } from 'lucide-vue-next'

const props = defineProps<{
  visible: boolean
  taskTitle: string
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: []
}>()

const closeModal = () => {
  emit('update:visible', false)
}

const handleConfirm = () => {
  emit('confirm')
  closeModal()
}
</script>

<template>
  <Teleport to="body">
    <Transition name="luomi-modal">
      <div v-if="visible" class="luomi-modal-overlay" @click.self="closeModal">
        <div class="luomi-modal">
          <div class="luomi-modal-header">
            <h2 class="luomi-modal-title">
              <Trash2 :size="18" />
              确认删除
            </h2>
            <button class="luomi-modal-close" @click="closeModal">
              <X :size="18" />
            </button>
          </div>

          <div class="luomi-modal-body">
            <div class="confirm-content">
              <div class="confirm-icon">
                <AlertTriangle :size="28" />
              </div>
              <p class="confirm-text">
                确定要删除任务 <strong>"{{ taskTitle }}"</strong> 吗？
              </p>
              <p class="confirm-hint">此操作无法撤销。</p>
            </div>
          </div>

          <div class="luomi-modal-footer">
            <button class="luomi-btn luomi-btn-ghost" @click="closeModal">取消</button>
            <button class="luomi-btn luomi-btn-danger" @click="handleConfirm">
              <Trash2 :size="14" />
              删除
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.luomi-modal-overlay {
  background: var(--overlay-backdrop);
  backdrop-filter: var(--glass-blur);
}

.luomi-modal {
  width: 400px;
  max-height: 85vh;
  background: var(--surface);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.luomi-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5) var(--space-6) var(--space-4);
  border-bottom: 1px solid var(--workspace-border);
}

.luomi-modal-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--text-primary);
}

.luomi-modal-close {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.luomi-modal-close:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.luomi-modal-body {
  padding: var(--space-5) var(--space-6);
  overflow-y: auto;
}

.luomi-modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--workspace-border);
}

.confirm-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: var(--space-3);
}

.confirm-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--task-red-soft);
  color: var(--task-red);
}

.confirm-text {
  font-size: var(--text-base);
  color: var(--text-primary);
  line-height: 1.5;
}

.confirm-text strong {
  font-weight: 700;
}

.confirm-hint {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.luomi-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: 600;
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-fast);
  font-family: inherit;
}

.luomi-btn-ghost {
  background: var(--workspace-bg);
  color: var(--text-secondary);
}

.luomi-btn-ghost:hover {
  background: var(--workspace-hover);
}

.luomi-btn-danger {
  background: var(--task-red-soft);
  border-color: var(--task-red);
  color: var(--task-red);
}

.luomi-btn-danger:hover {
  background: var(--task-red);
  color: var(--text-inverse);
}

.luomi-modal-enter-active {
  transition: all var(--duration-normal) var(--ease-in-out);
}

.luomi-modal-leave-active {
  transition: all var(--duration-leave) var(--ease-in-out);
}

.luomi-modal-enter-from {
  opacity: 0;
}

.luomi-modal-enter-from .luomi-modal {
  transform: scale(0.95) translateY(10px);
}

.luomi-modal-leave-to {
  opacity: 0;
}

.luomi-modal-leave-to .luomi-modal {
  transform: scale(0.95) translateY(10px);
}
</style>
