<script setup lang="ts">
import { computed } from 'vue'
import { Check, ChevronRight, SkipForward } from 'lucide-vue-next'
import type { ExecutionStatus } from '../types'

const props = defineProps<{
  status: ExecutionStatus
}>()

const emit = defineEmits<{
  skip: []
}>()

// 获取当前步骤索引
const currentStepIndex = computed(() => props.status.currentStepIndex)

// 判断步骤状态
const getStepStatus = (index: number) => {
  if (index < currentStepIndex.value) return 'completed'
  if (index === currentStepIndex.value) return 'in_progress'
  if (props.status.isSkipped) return 'skipped'
  return 'pending'
}

// 获取步骤图标
const getStepIcon = (index: number) => {
  const status = getStepStatus(index)
  if (status === 'completed') return 'check'
  if (status === 'in_progress') return 'arrow'
  return null
}
</script>

<template>
  <div class="execution-status-container">
    <div 
      v-for="(step, index) in status.steps" 
      :key="step.id"
      :class="['execution-step', getStepStatus(index)]"
    >
      <!-- 左侧：状态图标 -->
      <div class="step-icon">
        <Check v-if="getStepIcon(index) === 'check'" :size="14" class="icon-check" />
        <ChevronRight v-else-if="getStepIcon(index) === 'arrow'" :size="14" class="icon-arrow" />
        <span v-else class="step-number">{{ index + 1 }}</span>
      </div>
      
      <!-- 中间：步骤文案 -->
      <span class="step-label">{{ step.label }}</span>
      
      <!-- 右侧：跳过按钮（仅当前步骤显示） -->
      <button 
        v-if="getStepStatus(index) === 'in_progress' && !status.isComplete"
        class="skip-btn"
        title="跳过当前任务"
        @click="emit('skip')"
      >
        <SkipForward :size="12" />
        <span>跳过</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.execution-status-container {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-3);
  animation: fade-in var(--duration-normal) var(--ease-default);
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.execution-step {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.execution-step.completed {
  background: var(--lumi-teal-soft);
}

.execution-step.in_progress {
  background: var(--lumi-teal-soft);
}

.execution-step.skipped {
  opacity: 0.5;
}

.step-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
}

.execution-step.completed .step-icon {
  background: var(--lumi-brand);
  color: var(--text-inverse);
}

.execution-step.in_progress .step-icon {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.execution-step.pending .step-icon {
  background: var(--surface-hover);
  color: var(--text-muted);
}

.icon-check {
  color: var(--text-inverse);
}

.icon-arrow {
  color: var(--lumi-brand);
  animation: bounce-right 0.6s ease-in-out infinite;
}

@keyframes bounce-right {
  0%, 100% { transform: translateX(0); }
  50% { transform: translateX(2px); }
}

.step-label {
  flex: 1;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.execution-step.completed .step-label {
  color: var(--lumi-brand);
}

.execution-step.in_progress .step-label {
  color: var(--text);
  font-weight: var(--font-medium);
}

.skip-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  color: var(--text-muted);
  background: transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.skip-btn:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

@media (prefers-reduced-motion: reduce) {
  .execution-status-container,
  .execution-step,
  .execution-step.in_progress .step-icon,
  .icon-arrow {
    animation: none;
    transition: none;
  }
}
</style>
