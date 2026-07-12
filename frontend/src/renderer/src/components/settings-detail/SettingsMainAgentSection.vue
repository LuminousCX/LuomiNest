<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Brain, Check, AlertCircle, Save, Loader2 } from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import { useModelStore } from '../../stores/model'
import { createLuomiNestRendererLogger } from '../../utils/logger'

const logger = createLuomiNestRendererLogger('Settings')

const platformStore = usePlatformStore()
const modelStore = useModelStore()

const mainAgentEdit = ref({
  provider: '',
  model: '',
  systemPrompt: '',
  temperature: 0.7,
  maxTokens: 4096,
})
const mainAgentLoading = ref(false)
const mainAgentSaving = ref(false)
const mainAgentSaveMsg = ref<{ type: 'success' | 'error'; text: string } | null>(null)

const loadMainAgentConfig = async () => {
  mainAgentLoading.value = true
  try {
    await Promise.all([
      platformStore.fetchMainAgent(),
      modelStore.providers.length === 0 ? modelStore.fetchProviders() : Promise.resolve(),
    ])
    if (platformStore.mainAgent) {
      mainAgentEdit.value = {
        provider: platformStore.mainAgent.provider,
        model: platformStore.mainAgent.model,
        systemPrompt: platformStore.mainAgent.systemPrompt,
        temperature: platformStore.mainAgent.temperature,
        maxTokens: platformStore.mainAgent.maxTokens,
      }
    }
  } catch (e) {
    logger.error('Failed to load main agent config:', e)
  } finally {
    mainAgentLoading.value = false
  }
}

const handleSaveMainAgentConfig = async () => {
  mainAgentSaving.value = true
  mainAgentSaveMsg.value = null
  try {
    await platformStore.updateMainAgent({
      provider: mainAgentEdit.value.provider,
      model: mainAgentEdit.value.model,
      systemPrompt: mainAgentEdit.value.systemPrompt,
      temperature: mainAgentEdit.value.temperature,
      maxTokens: mainAgentEdit.value.maxTokens,
    })
    mainAgentSaveMsg.value = { type: 'success', text: '主智能体配置已保存' }
    setTimeout(() => { mainAgentSaveMsg.value = null }, 3000)
  } catch (e) {
    mainAgentSaveMsg.value = { type: 'error', text: `保存失败: ${e instanceof Error ? e.message : String(e)}` }
  } finally {
    mainAgentSaving.value = false
  }
}

onMounted(() => {
  loadMainAgentConfig()
})
</script>

<template>
  <div class="main-agent-panel animate-slide-up">
    <div v-if="mainAgentLoading" class="main-agent-loading">
      <Loader2 :size="20" class="tts-spin" />
      <span>正在加载主智能体配置...</span>
    </div>

    <template v-else>
      <div class="main-agent-card">
        <div class="main-agent-card-header">
          <Brain :size="18" />
          <span class="main-agent-card-title">人格与系统提示</span>
        </div>
        <div class="main-agent-card-body">
          <div class="platform-form-group">
            <label class="platform-form-label">系统提示词</label>
            <textarea v-model="mainAgentEdit.systemPrompt" class="platform-form-textarea main-agent-prompt" rows="10" placeholder="主智能体的系统提示词，决定其角色、人格与行为准则。例如：你是 LuomiNest 的主控智能体，负责与用户交互、调度子 Agent、管理记忆与工具..."></textarea>
            <span class="platform-form-hint">提示词会作为系统消息注入到主 Agent 的每次对话开头，影响其角色定位与行为方式</span>
          </div>
        </div>
      </div>

      <div class="main-agent-actions">
        <div v-if="mainAgentSaveMsg" :class="['main-agent-msg', mainAgentSaveMsg.type]">
          <component :is="mainAgentSaveMsg.type === 'success' ? Check : AlertCircle" :size="14" />
          <span>{{ mainAgentSaveMsg.text }}</span>
        </div>
        <button class="main-agent-save-btn" @click="handleSaveMainAgentConfig" :disabled="mainAgentSaving">
          <Save :size="14" />
          <span>{{ mainAgentSaving ? '保存中...' : '保存配置' }}</span>
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.main-agent-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  padding: var(--space-6) var(--space-7);
  overflow-y: auto;
  flex: 1;
}

.main-agent-loading {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-8) 0;
  justify-content: center;
  color: var(--text-muted);
  font-size: var(--text-base);
}

.tts-spin {
  animation: tts-spin 1s linear infinite;
  color: var(--lumi-primary);
}

@keyframes tts-spin {
  to { transform: rotate(360deg); }
}

.main-agent-card {
  background: var(--workspace-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-xs);
}

.main-agent-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--divider-soft);
  color: var(--lumi-primary);
}

.main-agent-card-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
}

.main-agent-card-body {
  padding: var(--space-4);
}

.main-agent-prompt {
  min-height: 160px;
  line-height: 1.6;
  font-size: var(--text-base);
}

.main-agent-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3);
  padding-top: var(--space-1);
}

.main-agent-msg {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
}

.main-agent-msg.success {
  color: var(--lumi-success, var(--lumi-success));
  background: var(--lumi-primary-light);
}

.main-agent-msg.error {
  color: var(--lumi-danger);
  background: var(--task-red-soft);
}

.main-agent-save-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 9px var(--space-5);
  background: var(--lumi-primary);
  color: var(--text-inverse);
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition-fast), opacity var(--transition-fast);
}

.main-agent-save-btn:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.main-agent-save-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.platform-form-group {
  margin-bottom: var(--space-4);
}

.platform-form-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.platform-form-textarea {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--surface, var(--workspace-panel));
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  font-size: var(--text-base);
  color: var(--text-primary);
  font-family: inherit;
  resize: vertical;
  box-sizing: border-box;
}

.platform-form-textarea:focus {
  outline: none;
  border-color: var(--lumi-primary);
}

.platform-form-hint {
  display: block;
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: var(--space-2);
  line-height: 1.4;
}
</style>
