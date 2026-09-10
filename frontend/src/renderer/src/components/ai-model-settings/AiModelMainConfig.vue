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
const { t } = useI18n()

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
    return { valid: false, error: t('aiModel.common.errSelectProvider') }
  }
  if (!mainModelConfig.value.model) {
    return { valid: false, error: t('aiModel.common.errSelectModel') }
  }
  return { valid: true, error: '' }
})

const onMainProviderChange = () => {
  saveValidationError.value = ''
  mainModelConfig.value.model = ''
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
    toast.error(t('aiModel.common.fetchFailed', { message: (e instanceof Error ? e.message : String(e)) || t('aiModel.common.unknownError') }))
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
    toast.success(t('aiModel.main.savedToast'))
    setTimeout(() => { saveStatus.value = 'idle' }, 2000)
  } catch {
    saveStatus.value = 'error'
    toast.error(t('aiModel.main.saveErrorToast'))
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
          <h3 class="section-title">{{ t('aiModel.main.title') }}</h3>
          <span class="section-tag">{{ t('aiModel.main.tag') }}</span>
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
        <p>{{ t('aiModel.main.info') }}</p>
        <p class="info-tip">{{ t('aiModel.main.infoTip') }}</p>
      </div>
    </Transition>

    <div class="config-form">
      <div class="form-group">
        <label class="form-label">
          {{ t('aiModel.common.provider') }}
          <span class="required-mark">*</span>
        </label>
        <div class="form-select-wrap">
          <select v-model="mainModelConfig.selectedProvider" class="form-select" :class="{ 'select-error': saveValidationError && !mainModelConfig.selectedProvider }" @change="onMainProviderChange">
            <option value="">{{ t('aiModel.common.selectProvider') }}</option>
            <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <ChevronRight :size="14" class="select-icon" />
        </div>
        <span v-if="saveValidationError && !mainModelConfig.selectedProvider" class="form-hint hint-error">
          {{ saveValidationError }}
        </span>
        <span v-else-if="providers.length === 0" class="form-hint hint-warn">
          {{ t('aiModel.main.noProviders') }}
        </span>
      </div>

      <div class="form-group">
        <label class="form-label">
          {{ t('aiModel.common.model') }}
          <span class="required-mark">*</span>
        </label>
        <div class="form-select-wrap">
          <select v-model="mainModelConfig.model" class="form-select">
            <option value="">{{ t('aiModel.common.selectModel') }}</option>
            <option v-for="m in mainAvailableModels" :key="m.id" :value="m.id">{{ m.name }}</option>
          </select>
          <ChevronRight :size="14" class="select-icon" />
        </div>
        <div v-if="mainModelConfig.selectedProvider && mainAvailableModels.length === 0" class="fetch-models-row">
          <span class="form-hint">{{ t('aiModel.common.noModels') }}</span>
          <button class="fetch-btn" @click="handleFetchModels(mainModelConfig.selectedProvider)">
            <RefreshCw :size="12" />
            {{ t('aiModel.common.fetch') }}
          </button>
        </div>
        <span v-if="mainModelConfig.model && mainAvailableModels.length > 0 && !mainAvailableModels.find(m => m.id === mainModelConfig.model)" class="form-hint hint-warn">
          {{ t('aiModel.common.modelMismatch') }}
        </span>
      </div>

      <div class="form-group">
        <div class="form-label-row">
          <label class="form-label">Temperature</label>
          <span class="form-value">{{ mainModelConfig.temperature }}</span>
        </div>
        <input type="range" v-model.number="mainModelConfig.temperature" min="0" max="2" step="0.1" class="form-slider" />
        <div class="slider-labels"><span>{{ t('aiModel.common.precise') }}</span><span>{{ t('aiModel.common.creative') }}</span></div>
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
        {{ saveStatus === 'saving' ? t('aiModel.common.saving') : saveStatus === 'saved' ? t('aiModel.common.saved') : saveStatus === 'error' ? (saveValidationError || t('aiModel.common.saveFailed')) : t('aiModel.common.saveConfig') }}
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

</style>
