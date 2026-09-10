<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Cpu, Image as ImageIcon, RefreshCw, RotateCcw,
  AlertCircle, CheckCircle2, XCircle, Clock,
} from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import { useModelStore } from '../../stores/model'
import type { PlatformInstance, PlatformModelConfig } from '../../types'
import LumiModal from '../../components/common/LumiModal.vue'
import LumiButton from '../../components/common/LumiButton.vue'
import LumiInput from '../../components/common/LumiInput.vue'
import { createLuomiNestRendererLogger } from '../../utils/logger'

const logger = createLuomiNestRendererLogger('Platform')

const store = usePlatformStore()
const modelStore = useModelStore()
const { t } = useI18n()

const props = defineProps<{
  visible: boolean
  instance: PlatformInstance | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  saved: []
}>()

const editConfig = ref<Record<string, any>>({})
const modelConfigLoading = ref(false)
const modelConfigSaving = ref(false)
const modelEditConfig = ref<PlatformModelConfig>({})

const availableProviders = computed(() => modelStore.providers)

const isGameCategory = computed(() => {
  const inst = props.instance
  if (!inst) return false
  return inst.category === 'game' || inst.adapterType === 'minecraft' || inst.adapterType === 'game_websocket'
})

const availableModels = computed(() => {
  const providerId = modelEditConfig.value.provider
  if (!providerId) return []
  const provider = availableProviders.value.find(p => p.id === providerId)
  return provider?.models || []
})

const effectiveModelConfig = computed(() => store.instanceModelConfig)

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'running': return CheckCircle2
    case 'stopped': return XCircle
    case 'error': return AlertCircle
    default: return Clock
  }
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'running': return 'var(--lumi-success)'
    case 'stopped': return 'var(--text-muted)'
    case 'error': return 'var(--lumi-danger)'
    default: return 'var(--text-muted)'
  }
}

const getStatusLabel = (status: string) => {
  switch (status) {
    case 'running': return t('platform.status.running')
    case 'stopped': return t('platform.status.stopped')
    case 'error': return t('platform.status.error')
    case 'pending': return t('platform.status.pending')
    default: return t('platform.status.unknown')
  }
}

const closeConfigDialog = () => {
  emit('update:visible', false)
}

const handleSaveConfig = async () => {
  if (!props.instance) return
  try {
    await store.updateInstance(props.instance.id, {
      name: props.instance.name,
      config: editConfig.value,
    })
    if (Object.keys(modelEditConfig.value).length > 0) {
      await store.updateInstanceModelConfig(props.instance.id, modelEditConfig.value)
    }
    closeConfigDialog()
    emit('saved')
  } catch (e: unknown) {
    logger.error('Failed to update platform instance:', e)
  }
}

const handleResetModelConfig = async () => {
  if (!props.instance) return
  modelConfigSaving.value = true
  try {
    await store.updateInstanceModelConfig(props.instance.id, {
      provider: '',
      model: '',
      systemPrompt: '',
      temperature: null,
      maxTokens: null,
    })
    modelEditConfig.value = {
      provider: '',
      model: '',
      systemPrompt: '',
      temperature: null,
      maxTokens: null,
    }
  } catch (e: unknown) {
    logger.error('Failed to reset model config:', e)
  } finally {
    modelConfigSaving.value = false
  }
}

const handleProviderChange = () => {
  modelEditConfig.value.model = ''
}

const resetConfigState = () => {
  editConfig.value = {}
  modelEditConfig.value = {}
}

const loadInstanceConfig = async (instance: PlatformInstance) => {
  editConfig.value = { ...instance.config }
  delete editConfig.value.model_config
  delete editConfig.value.enable
  modelEditConfig.value = {}
  modelConfigLoading.value = true
  try {
    await Promise.all([
      store.fetchInstanceModelConfig(instance.id),
      modelStore.fetchProviders(),
    ])
    const cfg = store.instanceModelConfig
    if (cfg) {
      modelEditConfig.value = {
        provider: cfg.instanceConfig.provider || '',
        model: cfg.instanceConfig.model || '',
        systemPrompt: cfg.instanceConfig.systemPrompt || '',
        temperature: cfg.instanceConfig.temperature ?? null,
        maxTokens: cfg.instanceConfig.maxTokens ?? null,
      }
    }
  } catch (e: unknown) {
    logger.error('Failed to load model config:', e)
  } finally {
    modelConfigLoading.value = false
  }
}

watch(() => props.visible, async (visible) => {
  if (!visible) {
    resetConfigState()
    return
  }
  if (props.instance) {
    await loadInstanceConfig(props.instance)
  }
}, { immediate: true })

watch(() => props.instance, async (instance) => {
  if (!instance || !props.visible) {
    if (!instance) resetConfigState()
    return
  }
  await loadInstanceConfig(instance)
})
</script>

<template>
  <LumiModal :visible="visible" :title="t('platform.configTitle', { name: instance?.name || '' })" size="lg" @close="closeConfigDialog" @update:visible="emit('update:visible', $event)">
    <div class="dialog-body">
      <div class="form-group">
        <label class="form-label">{{ t('platform.statusLabel') }}</label>
        <div class="status-display">
          <component :is="getStatusIcon(instance?.status || '')" :size="16" :style="{ color: getStatusColor(instance?.status || '') }" />
          <span :style="{ color: getStatusColor(instance?.status || '') }">{{ getStatusLabel(instance?.status || '') }}</span>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">
          <Cpu :size="12" />
          {{ t('platform.modelConfig') }}
          <span v-if="effectiveModelConfig?.isOverridden" class="badge overridden">{{ t('platform.badgeOverridden') }}</span>
          <span v-else-if="effectiveModelConfig" class="badge inherited">{{ t('platform.badgeInherited') }}</span>
        </label>

        <div v-if="modelConfigLoading" class="model-config-loading">
          <RefreshCw :size="14" class="spin-animation" />
          <span>{{ t('platform.loadingModelConfig') }}</span>
        </div>

        <div v-else-if="effectiveModelConfig" class="model-config-section">
          <div v-if="isGameCategory" class="vision-hint">
            <ImageIcon :size="12" />
            <span>{{ t('platform.visionHint') }}</span>
          </div>

          <div class="model-current-info">
            <div class="info-row">
              <span class="info-label">{{ t('platform.currentEffective') }}</span>
              <span class="info-value">{{ effectiveModelConfig.effective.providerName || effectiveModelConfig.effective.provider }}</span>
              <span class="info-sep">/</span>
              <span class="info-value">{{ effectiveModelConfig.effective.model }}</span>
              <span
                :class="['vision-tag', { supported: effectiveModelConfig.effective.supportsMultimodal }]"
                :title="effectiveModelConfig.effective.supportsMultimodal ? t('platform.visionSupported') : t('platform.visionUnsupported')"
              >
                {{ effectiveModelConfig.effective.supportsMultimodal ? 'Vision' : 'No Vision' }}
              </span>
            </div>
            <div class="info-row main-agent-info">
              <span class="info-label">{{ t('platform.mainAgentDefault') }}</span>
              <span class="info-value">{{ effectiveModelConfig.mainAgent.providerName || effectiveModelConfig.mainAgent.provider }}</span>
              <span class="info-sep">/</span>
              <span class="info-value">{{ effectiveModelConfig.mainAgent.model }}</span>
            </div>
          </div>

          <div class="config-fields">
            <div class="config-field">
              <label class="config-field-label">{{ t('platform.providerLabel') }}</label>
              <select
                v-model="modelEditConfig.provider"
                class="form-input form-select"
                @change="handleProviderChange"
              >
                <option value="">{{ t('platform.inheritMainAgent') }}</option>
                <option v-for="p in availableProviders" :key="p.id" :value="p.id">
                  {{ p.name }}{{ p.isDefault ? t('platform.defaultSuffix') : '' }}
                </option>
              </select>
            </div>
            <div class="config-field">
              <label class="config-field-label">{{ t('platform.modelLabel') }}</label>
              <select v-model="modelEditConfig.model" class="form-input form-select" :disabled="!modelEditConfig.provider">
                <option value="">{{ t('platform.inheritMainAgent') }}</option>
                <option v-for="m in availableModels" :key="m.id" :value="m.id">
                  {{ m.name || m.id }}
                </option>
              </select>
            </div>
            <div class="config-field">
              <label class="config-field-label">{{ t('platform.systemPromptLabel') }}</label>
              <textarea
                v-model="modelEditConfig.systemPrompt"
                class="form-input form-textarea"
                rows="3"
                :placeholder="t('platform.systemPromptPlaceholder')"
              ></textarea>
            </div>
            <div class="config-field-row">
              <div class="config-field">
                <label class="config-field-label">{{ t('platform.temperatureLabel') }}</label>
                <LumiInput
                  v-model.number="modelEditConfig.temperature"
                  type="number"
                  step="0.1"
                  min="0"
                  max="2"
                  :placeholder="t('platform.inherit')"
                />
              </div>
              <div class="config-field">
                <label class="config-field-label">{{ t('platform.maxTokensLabel') }}</label>
                <LumiInput
                  v-model.number="modelEditConfig.maxTokens"
                  type="number"
                  min="1"
                  :placeholder="t('platform.inherit')"
                />
              </div>
            </div>
          </div>

          <button
            class="reset-btn"
            @click="handleResetModelConfig"
            :disabled="modelConfigSaving || !effectiveModelConfig.isOverridden"
          >
            <RotateCcw :size="12" />
            <span>{{ t('platform.resetToInherit') }}</span>
          </button>
        </div>
      </div>

      <div v-if="Object.keys(editConfig).length > 0" class="form-group">
        <label class="form-label">{{ t('platform.connectionConfig') }}</label>
        <div class="config-fields">
          <div v-for="(_val, key) in editConfig" :key="key" class="config-field">
            <label class="config-field-label">{{ key }}</label>
            <LumiInput v-model="editConfig[key]" type="text" />
          </div>
        </div>
      </div>
      <div v-if="instance?.errorMessage" class="form-group">
        <label class="form-label">{{ t('platform.errorLabel') }}</label>
        <div class="error-display">{{ instance.errorMessage }}</div>
      </div>
    </div>
    <template #footer>
      <LumiButton variant="secondary" size="sm" @click="closeConfigDialog">{{ t('platform.cancel') }}</LumiButton>
      <LumiButton variant="primary" size="sm" @click="handleSaveConfig">{{ t('platform.saveConfig') }}</LumiButton>
    </template>
  </LumiModal>
</template>

<style scoped>
.form-group {
  margin-bottom: var(--space-4);
}

.form-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  margin-bottom: var(--space-1);
}

.status-display {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
}

.error-display {
  padding: var(--space-2) var(--space-3);
  background: var(--lumi-danger-light);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--lumi-danger);
}

.badge {
  margin-left: auto;
  padding: 2px var(--space-2);
  border-radius: var(--radius-xs);
  font-size: var(--text-2xs);
  font-weight: var(--font-medium);
}

.badge.overridden {
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.badge.inherited {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.model-config-loading {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-3);
  color: var(--text-muted);
  font-size: var(--text-sm);
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
}


.model-config-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.vision-hint {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  background: var(--lumi-amber-soft);
  border: 1px solid var(--lumi-amber-border);
  border-radius: var(--radius-sm);
  color: var(--lumi-amber);
  font-size: var(--text-xs);
}

.model-current-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
}

.info-row {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  flex-wrap: wrap;
}

.info-label {
  color: var(--text-muted);
  font-weight: var(--font-medium);
}

.info-value {
  color: var(--text-primary);
  font-weight: var(--font-medium);
}

.info-sep {
  color: var(--text-muted);
}

.main-agent-info {
  font-size: var(--text-xs);
  opacity: 0.8;
}

.vision-tag {
  padding: 1px var(--space-1);
  border-radius: var(--radius-xs);
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.vision-tag.supported {
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.config-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.config-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.config-field-label {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-muted);
}

.form-select {
  cursor: pointer;
  appearance: auto;
  background-image: none;
  padding-right: var(--space-3);
}

.form-select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-textarea {
  resize: vertical;
  font-family: inherit;
  min-height: 80px;
}

.config-field-row {
  display: flex;
  gap: var(--space-3);
}

.config-field-row .config-field {
  flex: 1;
}

.reset-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  background: transparent;
  color: var(--text-muted);
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
  align-self: flex-start;
}

.reset-btn:hover:not(:disabled) {
  color: var(--lumi-danger);
  border-color: var(--lumi-danger);
  background: var(--lumi-danger-light);
}

.reset-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
