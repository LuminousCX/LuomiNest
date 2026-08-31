<script setup lang="ts">
/**
 * 智能体创建向导 - 步骤3：高级设置
 *
 * 系统提示词。
 * 2026-08 全局模型统一：Temperature/MaxTokens 已收归全局模型设置，
 * Agent 不再单独配置，故此处仅保留系统提示词。
 */
import LumiCard from '../common/LumiCard.vue'
import type { AgentFormData } from '../../composables/useAgentCreateForm'

defineProps<{
  formData: AgentFormData
}>()
</script>

<template>
  <div class="step-content step-layout-full">
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

.system-prompt-area {
  min-height: 200px;
  font-family: inherit;
}
</style>
