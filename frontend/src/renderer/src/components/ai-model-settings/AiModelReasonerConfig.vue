<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
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
import type { ReasonerModelConfig } from './types'
import { createLuomiNestRendererLogger } from '../../utils/logger'
import { toErrorMessage } from '@/utils/error'

const logger = createLuomiNestRendererLogger('AiModel')

const modelStore = useModelStore()
const toast = useToast()
const { t } = useI18n()

const providers = computed(() => modelStore.providers)
const showInfo = ref(false)

const reasonerModelConfig = ref<ReasonerModelConfig>({
  selectedProvider: '',
  model: '',
  temperature: 0.3,
  maxTokens: 8192,
  reasoningEffort: 'medium',
})

const saveValidationError = ref('')

const effortOptions = computed(() => [
  { value: 'low', label: t('aiModel.reasoner.effortLow') },
  { value: 'medium', label: t('aiModel.reasoner.effortMedium') },
  { value: 'high', label: t('aiModel.reasoner.effortHigh') },
])
const saveStatus = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')

const reasonerAvailableModels = computed(() => {
  const provider = providers.value.find(p => p.id === reasonerModelConfig.value.selectedProvider)
  if (!provider) return []
  if (provider.selectedModels.length > 0) {
    return provider.selectedModels.map(id => ({ id, name: id }))
  }
  return provider.models
})

const reasonerConfigValid = computed(() => {
  if (!reasonerModelConfig.value.selectedProvider) {
    return { valid: false, error: t('aiModel.common.errSelectProvider') }
  }
  if (!reasonerModelConfig.value.model) {
    return { valid: false, error: t('aiModel.common.errSelectModel') }
  }
  return { valid: true, error: '' }
})

const onReasonerProviderChange = () => {
  saveValidationError.value = ''
  reasonerModelConfig.value.model = ''
}

const handleFetchModels = async (providerId: string) => {
  try {
    const models = await modelStore.fetchProviderModels(providerId)
    if (models.length > 0) {
      toast.success(t('aiModel.common.fetchSuccess', { count: models.length }))
    } else {
      toast.warning(t('aiModel.common.fetchEmpty'))
    }
  } catch (e: unknown) {
    logger.error('Failed to fetch models:', e)
    toast.error(t('aiModel.common.fetchFailed', { message: toErrorMessage(e) || t('aiModel.common.unknownError') }))
  }
}

const handleSaveReasonerConfig = async () => {
  saveValidationError.value = ''
  if (!reasonerConfigValid.value.valid) {
    saveValidationError.value = reasonerConfigValid.value.error
    saveStatus.value = 'error'
    toast.warning(reasonerConfigValid.value.error)
    setTimeout(() => { saveStatus.value = 'idle' }, 3000)
    return
  }
  saveStatus.value = 'saving'
  try {
    await modelStore.updateModelConfig({
      reasonerProvider: reasonerModelConfig.value.selectedProvider,
      reasonerModel: reasonerModelConfig.value.model,
      reasonerTemperature: reasonerModelConfig.value.temperature,
      reasonerMaxTokens: reasonerModelConfig.value.maxTokens,
      reasonerEffort: reasonerModelConfig.value.reasoningEffort,
    })
    saveStatus.value = 'saved'
    toast.success(t('aiModel.reasoner.savedToast'))
    setTimeout(() => { saveStatus.value = 'idle' }, 2000)
  } catch {
    saveStatus.value = 'error'
    toast.error(t('aiModel.reasoner.saveErrorToast'))
    setTimeout(() => { saveStatus.value = 'idle' }, 3000)
  }
}

onMounted(() => {
  const cfg = modelStore.modelConfig
  if (cfg.reasonerProvider) {
    reasonerModelConfig.value.selectedProvider = cfg.reasonerProvider
    reasonerModelConfig.value.model = cfg.reasonerModel || ''
    reasonerModelConfig.value.temperature = cfg.reasonerTemperature || 0.3
    reasonerModelConfig.value.maxTokens = cfg.reasonerMaxTokens || 8192
    reasonerModelConfig.value.reasoningEffort = cfg.reasonerEffort || 'medium'
  }
})
</script>

<template>
  <div class="content-section lumi-stack-5">
    <div class="section-header">
      <div class="section-header-left lumi-row-3">
        <div class="section-header-text">
          <h3 class="lumi-section-title">{{ t('aiModel.reasoner.title') }}</h3>
          <span class="section-tag">{{ t('aiModel.reasoner.tag') }}</span>
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
        <p>{{ t('aiModel.reasoner.info') }}</p>
        <p class="info-tip">{{ t('aiModel.reasoner.infoTip') }}</p>
      </div>
    </Transition>

    <div class="config-form">
      <div class="form-group">
        <label class="form-label">
          {{ t('aiModel.common.provider') }}
          <span class="required-mark">*</span>
        </label>
        <div class="form-select-wrap">
          <select v-model="reasonerModelConfig.selectedProvider" class="form-select" :class="{ 'select-error': saveValidationError && !reasonerModelConfig.selectedProvider }" @change="onReasonerProviderChange">
            <option value="">{{ t('aiModel.common.selectProvider') }}</option>
            <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <ChevronRight :size="14" class="select-icon" />
        </div>
        <span v-if="saveValidationError && !reasonerModelConfig.selectedProvider" class="form-hint hint-error">
          {{ saveValidationError }}
        </span>
      </div>
      <div class="form-group">
        <label class="form-label">{{ t('aiModel.common.model') }}</label>
        <div class="form-select-wrap">
          <select v-model="reasonerModelConfig.model" class="form-select">
            <option value="">{{ t('aiModel.common.selectModel') }}</option>
            <option v-for="m in reasonerAvailableModels" :key="m.id" :value="m.id">{{ m.name }}</option>
          </select>
          <ChevronRight :size="14" class="select-icon" />
        </div>
        <div v-if="reasonerModelConfig.selectedProvider && reasonerAvailableModels.length === 0" class="fetch-models-row">
          <span class="form-hint">{{ t('aiModel.common.noModels') }}</span>
          <button class="fetch-btn" @click="handleFetchModels(reasonerModelConfig.selectedProvider)">
            <RefreshCw :size="12" />
            {{ t('aiModel.common.fetch') }}
          </button>
        </div>
        <span v-if="reasonerModelConfig.model && reasonerAvailableModels.length > 0 && !reasonerAvailableModels.find(m => m.id === reasonerModelConfig.model)" class="form-hint hint-warn">
          {{ t('aiModel.common.modelMismatch') }}
        </span>
      </div>
      <div class="form-group">
        <div class="form-label-row lumi-row-between">
          <label class="form-label">Temperature</label>
          <span class="form-value">{{ reasonerModelConfig.temperature }}</span>
        </div>
        <input type="range" v-model.number="reasonerModelConfig.temperature" min="0" max="2" step="0.1" class="form-slider" />
        <div class="slider-labels"><span>{{ t('aiModel.common.precise') }}</span><span>{{ t('aiModel.common.creative') }}</span></div>
      </div>
      <div class="form-group">
        <div class="form-label-row lumi-row-between">
          <label class="form-label">Max Tokens</label>
          <span class="form-value">{{ reasonerModelConfig.maxTokens }}</span>
        </div>
        <input type="range" v-model.number="reasonerModelConfig.maxTokens" min="1024" max="32768" step="1024" class="form-slider" />
      </div>
      <div class="form-group">
        <label class="form-label">{{ t('aiModel.reasoner.reasoningEffort') }}</label>
        <div class="effort-group">
          <button
            v-for="effort in effortOptions"
            :key="effort.value"
            :class="['effort-btn', { active: reasonerModelConfig.reasoningEffort === effort.value }]"
            @click="reasonerModelConfig.reasoningEffort = effort.value"
          >
            {{ effort.label }}
          </button>
        </div>
      </div>

      <button
        :class="['save-btn', { saving: saveStatus === 'saving', saved: saveStatus === 'saved', error: saveStatus === 'error' }]"
        :disabled="saveStatus === 'saving'"
        @click="handleSaveReasonerConfig"
      >
        <Loader2 v-if="saveStatus === 'saving'" :size="16" class="spin-animation" />
        <Check v-else-if="saveStatus === 'saved'" :size="16" />
        <AlertCircle v-else-if="saveStatus === 'error'" :size="16" />
        <Check v-else :size="16" />
        {{ saveStatus === 'saving' ? t('aiModel.common.saving') : saveStatus === 'saved' ? t('aiModel.common.saved') : saveStatus === 'error' ? (saveValidationError || t('aiModel.common.saveFailed')) : t('aiModel.common.saveConfig') }}
      </button>
    </div>
  </div>
</template>

<style scoped src="./ai-model-shared.css"></style>
<style scoped>
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

.form-value {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--lumi-primary);
  font-variant-numeric: tabular-nums;
}

.select-icon {
  position: absolute;
  right: var(--space-3);
  color: var(--text-muted);
  pointer-events: none;
  transform: rotate(90deg);
}

.effort-group {
  display: flex;
  gap: var(--space-2);
}

.effort-btn {
  flex: 1;
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-normal);
  text-align: center;
}

.effort-btn:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.effort-btn.active {
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  font-weight: 600;
}

</style>
