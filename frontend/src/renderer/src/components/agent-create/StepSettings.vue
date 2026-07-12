<script setup lang="ts">
/**
 * 智能体创建向导 - 步骤3：高级设置
 *
 * 模型参数（Temperature/MaxTokens）+ 系统提示词
 */
import LumiInput from '../common/LumiInput.vue'
import LumiCard from '../common/LumiCard.vue'
import type { AgentFormData } from '../../composables/useAgentCreateForm'

defineProps<{
  formData: AgentFormData
}>()
</script>

<template>
  <div class="step-content step-layout-full">
    <div class="settings-grid">
      <LumiCard class="settings-card" padding="md">
        <h3 class="card-title">模型参数</h3>
        <div class="form-group">
          <label class="form-label">Temperature ({{ formData.temperature.toFixed(1) }})</label>
          <input
            v-model.number="formData.temperature"
            type="range"
            min="0"
            max="2"
            step="0.1"
            class="range-slider"
          />
          <div class="range-labels">
            <span>精确</span>
            <span>创意</span>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">最大 Token 数</label>
          <LumiInput
            v-model.number="formData.maxTokens"
            type="number"
            min="256"
            max="128000"
          />
        </div>
      </LumiCard>

      <LumiCard class="settings-card" padding="md">
        <h3 class="card-title">系统提示词</h3>
        <div class="form-group">
          <textarea
            v-model="formData.systemPrompt"
            class="lumi-textarea system-prompt-area"
            rows="10"
            placeholder="定义智能体的角色、行为准则和约束条件...&#10;&#10;例如：你是一个专业的编程助手，专注于提供高质量的代码解决方案。"
          ></textarea>
        </div>
      </LumiCard>
    </div>
  </div>
</template>

<style scoped>
.step-content {
  min-height: 100%;
}

.step-layout-full {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-5);
}

.settings-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.settings-card :deep(.lumi-card__body) {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.card-title {
  font-size: var(--text-lg);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  margin-bottom: var(--space-3);
}

.form-group {
  margin-bottom: var(--space-5);
}

.form-label {
  display: block;
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.range-slider {
  width: 100%;
  height: 6px;
  border-radius: var(--radius-xs);
  appearance: none;
  background: var(--border);
  outline: none;
  cursor: pointer;
}

.range-slider::-webkit-slider-thumb {
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition: transform var(--transition-fast);
}

.range-slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.range-labels {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.system-prompt-area {
  min-height: 200px;
  font-family: inherit;
}

@media (max-width: 768px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
