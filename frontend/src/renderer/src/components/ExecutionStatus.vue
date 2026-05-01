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
  if (props.status.isSkipped) return 'skipped'
  if (index < currentStepIndex.value) return 'completed'
  if (index === currentStepIndex.value) return 'in_progress'
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
  gap: 4px;
  padding: 8px 12px;
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
  margin-bottom: 12px;
  animation: fade-in 0.3s ease-out;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.execution-step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  transition: all 0.2s ease;
}

.execution-step.completed {
  background: rgba(13, 148, 136, 0.08);
}

.execution-step.in_progress {
  background: rgba(13, 148, 136, 0.12);
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
  font-size: 10px;
  font-weight: 600;
}

.execution-step.completed .step-icon {
  background: var(--lumi-primary);
  color: white;
}

.execution-step.in_progress .step-icon {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.execution-step.pending .step-icon {
  background: var(--workspace-hover);
  color: var(--text-muted);
}

.icon-check {
  color: white;
}

.icon-arrow {
  color: var(--lumi-primary);
  animation: bounce-right 0.6s ease-in-out infinite;
}

@keyframes bounce-right {
  0%, 100% { transform: translateX(0); }
  50% { transform: translateX(2px); }
}

.step-label {
  flex: 1;
  font-size: 12px;
  color: var(--text-secondary);
}

.execution-step.completed .step-label {
  color: var(--lumi-primary);
}

.execution-step.in_progress .step-label {
  color: var(--text-primary);
  font-weight: 500;
}

.skip-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  color: var(--text-muted);
  background: transparent;
  transition: all 0.2s ease;
}

.skip-btn:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}
</style>
