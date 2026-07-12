<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Info,
  ChevronRight,
  RefreshCw,
  Check,
  AlertCircle,
  Loader2,
} from 'lucide-vue-next'
import { useModelStore } from '../../stores/model'
import { useToast } from '../../composables/useToast'
import AiModelProviderList from './AiModelProviderList.vue'
import type { MainModelConfig } from './types'
import { createLuomiNestRendererLogger } from '../../utils/logger'

const logger = createLuomiNestRendererLogger('AiModel')

const emit = defineEmits<{
  (e: 'add-provider'): void
  (e: 'edit-provider', providerId: string): void
}>()

const modelStore = useModelStore()
const toast = useToast()

const providers = computed(() => modelStore.providers)
const showInfo = ref(false)

const mainModelConfig = ref<MainModelConfig>({
  selectedProvider: '',
  model: '',
  temperature: 0.7,
  topP: 0.9,
  maxTokens: 4096,
})

const saveValidationError = ref('')
const saveStatus = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')

const mainAvailableModels = computed(() => {
  const provider = providers.value.find(p => p.id === mainModelConfig.value.selectedProvider)
  if (!provider) return []
  if (provider.selectedModels.length > 0) {
    return provider.selectedModels.map(id => ({ id, name: id }))
  }
  return provider.models
})

const mainConfigValid = computed(() => {
  if (!mainModelConfig.value.selectedProvider) {
    return { valid: false, error: '请选择供应商' }
  }
  if (!mainModelConfig.value.model) {
    return { valid: false, error: '请选择模型' }
  }
  return { valid: true, error: '' }
})

const onMainProviderChange = () => {
  saveValidationError.value = ''
  mainModelConfig.value.model = ''
}

const handleFetchModels = async (providerId: string) => {
  try {
    await modelStore.fetchProviderModels(providerId)
    toast.info('模型列表已刷新')
  } catch (e: any) {
    logger.error('Failed to fetch models:', e)
    toast.error(`获取模型列表失败：${e.message || '未知错误'}`)
  }
}

const handleSaveMainConfig = async () => {
  saveValidationError.value = ''
  if (!mainConfigValid.value.valid) {
    saveValidationError.value = mainConfigValid.value.error
    saveStatus.value = 'error'
    toast.warning(mainConfigValid.value.error)
    setTimeout(() => { saveStatus.value = 'idle' }, 3000)
    return
  }
  saveStatus.value = 'saving'
  try {
    await modelStore.updateModelConfig({
      defaultProvider: mainModelConfig.value.selectedProvider,
      defaultModel: mainModelConfig.value.model,
      defaultTemperature: mainModelConfig.value.temperature,
      defaultMaxTokens: mainModelConfig.value.maxTokens,
      defaultTopP: mainModelConfig.value.topP,
    })
    saveStatus.value = 'saved'
    toast.success('主模型配置已保存')
    setTimeout(() => { saveStatus.value = 'idle' }, 2000)
  } catch {
    saveStatus.value = 'error'
    toast.error('主模型配置保存失败')
    setTimeout(() => { saveStatus.value = 'idle' }, 3000)
  }
}

onMounted(() => {
  const cfg = modelStore.modelConfig
  mainModelConfig.value.selectedProvider = cfg.defaultProvider
  mainModelConfig.value.model = cfg.defaultModel
  mainModelConfig.value.temperature = cfg.defaultTemperature
  mainModelConfig.value.topP = cfg.defaultTopP
  mainModelConfig.value.maxTokens = cfg.defaultMaxTokens
})
</script>

<template>
  <div class="content-section">
    <div class="section-header">
      <div class="section-header-left">
        <div class="section-header-text">
          <h3 class="section-title">主模型</h3>
          <span class="section-tag">快速响应</span>
        </div>
      </div>
      <button
        :class="['info-btn', { active: showInfo }]"
        @click="showInfo = !showInfo"
      >
        <Info :size="16" />
      </button>
    </div>
    <Transition name="info-expand">
      <div v-if="showInfo" class="section-info-panel">
        <p>主模型用于日常对话与快速响应场景。当推理模型未配置时，主模型也将承担复杂推理任务。</p>
        <p class="info-tip">优先选择响应速度快、延迟低的模型，如 GPT-4o-mini、Claude Haiku 等。</p>
      </div>
    </Transition>

    <div class="config-form">
      <div class="form-group">
        <label class="form-label">
          供应商
          <span class="required-mark">*</span>
        </label>
        <div class="form-select-wrap">
          <select v-model="mainModelConfig.selectedProvider" class="form-select" :class="{ 'select-error': saveValidationError && !mainModelConfig.selectedProvider }" @change="onMainProviderChange">
            <option value="">请选择供应商</option>
            <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <ChevronRight :size="14" class="select-icon" />
        </div>
        <span v-if="saveValidationError && !mainModelConfig.selectedProvider" class="form-hint hint-error">
          {{ saveValidationError }}
        </span>
        <span v-else-if="providers.length === 0" class="form-hint hint-warn">
          暂无供应商，请先点击左侧"添加供应商"
        </span>
      </div>

      <div class="form-group">
        <label class="form-label">
          模型
          <span class="required-mark">*</span>
        </label>
        <div class="form-select-wrap">
          <select v-model="mainModelConfig.model" class="form-select">
            <option value="">请选择模型</option>
            <option v-for="m in mainAvailableModels" :key="m.id" :value="m.id">{{ m.name }}</option>
          </select>
          <ChevronRight :size="14" class="select-icon" />
        </div>
        <div v-if="mainModelConfig.selectedProvider && mainAvailableModels.length === 0" class="fetch-models-row">
          <span class="form-hint">暂无模型列表</span>
          <button class="fetch-btn" @click="handleFetchModels(mainModelConfig.selectedProvider)">
            <RefreshCw :size="12" />
            获取
          </button>
        </div>
        <span v-if="mainModelConfig.model && mainAvailableModels.length > 0 && !mainAvailableModels.find(m => m.id === mainModelConfig.model)" class="form-hint hint-warn">
          当前供应商可能不支持此模型，请求时可能报错
        </span>
      </div>

      <div class="form-group">
        <div class="form-label-row">
          <label class="form-label">Temperature</label>
          <span class="form-value">{{ mainModelConfig.temperature }}</span>
        </div>
        <input type="range" v-model.number="mainModelConfig.temperature" min="0" max="2" step="0.1" class="form-slider" />
        <div class="slider-labels"><span>精确</span><span>创意</span></div>
      </div>

      <div class="form-group">
        <div class="form-label-row">
          <label class="form-label">Top P</label>
          <span class="form-value">{{ mainModelConfig.topP }}</span>
        </div>
        <input type="range" v-model.number="mainModelConfig.topP" min="0" max="1" step="0.05" class="form-slider" />
      </div>

      <div class="form-group">
        <div class="form-label-row">
          <label class="form-label">Max Tokens</label>
          <span class="form-value">{{ mainModelConfig.maxTokens }}</span>
        </div>
        <input type="range" v-model.number="mainModelConfig.maxTokens" min="256" max="16384" step="256" class="form-slider" />
      </div>

      <button
        :class="['save-btn', { saving: saveStatus === 'saving', saved: saveStatus === 'saved', error: saveStatus === 'error' }]"
        :disabled="saveStatus === 'saving'"
        @click="handleSaveMainConfig"
      >
        <Loader2 v-if="saveStatus === 'saving'" :size="16" class="spin-animation" />
        <Check v-else-if="saveStatus === 'saved'" :size="16" />
        <AlertCircle v-else-if="saveStatus === 'error'" :size="16" />
        <Check v-else :size="16" />
        {{ saveStatus === 'saving' ? '保存中...' : saveStatus === 'saved' ? '已保存' : saveStatus === 'error' ? (saveValidationError || '保存失败') : '保存配置' }}
      </button>
    </div>

    <AiModelProviderList @add-provider="emit('add-provider')" @edit-provider="emit('edit-provider', $event)" />
  </div>
</template>

<style scoped>
.content-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-5);
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-normal);
}

.section-header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.section-header-text {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}

.section-title {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
}

.section-tag {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--text-muted);
  letter-spacing: 0.5px;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-full);
  background: var(--workspace-panel);
}

.info-btn {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-normal);
  flex-shrink: 0;
}

.info-btn:hover {
  background: var(--workspace-hover);
  color: var(--lumi-primary);
}

.info-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.section-info-panel {
  padding: var(--space-3) var(--space-5);
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
  border: 1px solid var(--workspace-border);
  font-size: var(--text-base);
  color: var(--text-secondary);
  line-height: 1.7;
}

.section-info-panel p {
  margin-bottom: var(--space-2);
}

.section-info-panel p:last-child {
  margin-bottom: 0;
}

.info-tip {
  color: var(--lumi-primary) !important;
  font-weight: 500;
  font-size: var(--text-sm) !important;
}

.info-expand-enter-active {
  animation: info-expand-in var(--duration-slow) var(--ease-in-out);
}

.info-expand-leave-active {
  animation: info-expand-in var(--duration-fast) var(--ease-in-out) reverse;
}

@keyframes info-expand-in {
  from {
    opacity: 0;
    max-height: 0;
    margin-top: calc(var(--space-2) * -1);
  }
  to {
    opacity: 1;
    max-height: 200px;
    margin-top: 0;
  }
}

.config-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 560px;
}

.form-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: calc(var(--space-1) * -1);
}

.hint-warn {
  color: var(--lumi-amber);
}

.hint-error {
  color: var(--lumi-accent);
  font-weight: 500;
}

.select-error {
  border-color: var(--lumi-accent) !important;
  box-shadow: 0 0 0 var(--space-1) var(--task-red-soft) !important;
}

.fetch-models-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.fetch-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  transition: all var(--transition-normal);
}

.fetch-btn:hover {
  background: var(--lumi-primary);
  color: var(--text-inverse);
}

.form-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.form-value {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--lumi-primary);
  font-variant-numeric: tabular-nums;
}

.form-select-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.form-select {
  width: 100%;
  padding: var(--space-2) var(--space-8) var(--space-2) var(--space-3);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  color: var(--text-primary);
  cursor: pointer;
  appearance: none;
  transition: all var(--transition-normal);
}

.form-select:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 var(--space-1) var(--lumi-primary-glow);
}

.select-icon {
  position: absolute;
  right: var(--space-3);
  color: var(--text-muted);
  pointer-events: none;
  transform: rotate(90deg);
}

.form-slider {
  width: 100%;
  height: var(--space-2);
  appearance: none;
  background: var(--workspace-border);
  border-radius: var(--space-1);
  outline: none;
  cursor: pointer;
}

.form-slider::-webkit-slider-thumb {
  appearance: none;
  width: var(--space-4);
  height: var(--space-4);
  border-radius: var(--radius-full);
  background: var(--lumi-primary);
  cursor: pointer;
  box-shadow: 0 var(--space-1) var(--space-2) var(--lumi-primary-border);
  transition: transform var(--transition-normal);
}

.form-slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.save-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-6);
  border-radius: var(--radius-md);
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-inverse);
  background: var(--lumi-primary);
  cursor: pointer;
  transition: all var(--transition-normal);
  align-self: flex-start;
}

.save-btn:hover {
  background: var(--lumi-primary-hover);
}

.save-btn.saving {
  opacity: 0.8;
  cursor: wait;
}

.save-btn.saved {
  background: var(--lumi-emerald);
}

.save-btn.error {
  background: var(--lumi-accent);
}

.spin-animation {
  animation: spin 1s linear infinite;
}
</style>
