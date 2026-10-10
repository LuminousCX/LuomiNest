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
import { useProviderModelFetch } from './useProviderModelFetch'
import AiModelProviderList from './AiModelProviderList.vue'
import type { MainModelConfig } from './types'

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

const {
  availableModels: mainAvailableModels,
  modelsUnknown: mainModelsUnknown,
  isFetching: isMainFetching,
  fetchModels,
} = useProviderModelFetch(computed(() => mainModelConfig.value.selectedProvider))

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
  <div class="content-section lumi-stack-5">
    <div class="section-header">
      <div class="section-header-left lumi-row-3">
        <div class="section-header-text">
          <h3 class="lumi-section-title">{{ t('aiModel.main.title') }}</h3>
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
        <div class="model-field-row">
          <div class="form-select-wrap model-select-wrap">
            <select v-model="mainModelConfig.model" class="form-select" :disabled="mainModelsUnknown">
              <option value="">{{ t('aiModel.common.selectModel') }}</option>
              <option v-for="m in mainAvailableModels" :key="m.id" :value="m.id">{{ m.name }}</option>
            </select>
            <ChevronRight :size="14" class="select-icon" />
          </div>
          <button
            class="refresh-models-btn"
            :disabled="!mainModelConfig.selectedProvider || isMainFetching(mainModelConfig.selectedProvider)"
            :title="t('aiModel.common.fetch')"
            :aria-label="t('aiModel.common.fetch')"
            @click="fetchModels(mainModelConfig.selectedProvider)"
          >
            <RefreshCw :size="14" :class="{ 'spin-animation': isMainFetching(mainModelConfig.selectedProvider) }" />
          </button>
        </div>
        <span v-if="mainModelsUnknown" class="form-hint">
          {{ t('aiModel.common.modelsUnknownHint') }}
        </span>
        <span v-if="mainModelConfig.model && mainAvailableModels.length > 0 && !mainAvailableModels.find(m => m.id === mainModelConfig.model)" class="form-hint hint-warn">
          {{ t('aiModel.common.modelMismatch') }}
        </span>
      </div>

      <div class="form-group">
        <div class="form-label-row lumi-row-between">
          <label class="form-label">Temperature</label>
          <span class="form-value">{{ mainModelConfig.temperature }}</span>
        </div>
        <input type="range" v-model.number="mainModelConfig.temperature" min="0" max="2" step="0.1" class="form-slider" />
        <div class="slider-labels"><span>{{ t('aiModel.common.precise') }}</span><span>{{ t('aiModel.common.creative') }}</span></div>
      </div>

      <div class="form-group">
        <div class="form-label-row lumi-row-between">
          <label class="form-label">Top P</label>
          <span class="form-value">{{ mainModelConfig.topP }}</span>
        </div>
        <input type="range" v-model.number="mainModelConfig.topP" min="0" max="1" step="0.05" class="form-slider" />
      </div>

      <div class="form-group">
        <div class="form-label-row lumi-row-between">
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

</style>
