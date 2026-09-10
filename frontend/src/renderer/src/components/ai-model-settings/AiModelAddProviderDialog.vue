<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Plus,
  ArrowLeft,
  ChevronRight,
  Cloud,
  Monitor,
  Network,
  Eye,
  EyeOff,
  Loader2,
  Zap,
  Check,
  AlertCircle,
} from 'lucide-vue-next'
import LumiModal from '../common/LumiModal.vue'
import { useModelStore } from '../../stores/model'
import { useToast } from '../../composables/useToast'
import type { NewProviderForm, TestResult } from './types'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const modelStore = useModelStore()
const toast = useToast()
const { t } = useI18n()

const showApiKey = ref(false)
const addProviderError = ref('')
const addProviderLoading = ref(false)
const selectedTemplate = ref<string>('')
const addDialogStep = ref<'select' | 'configure'>('select')
const addTemplateCategory = ref('cloud')
const testingProvider = ref(false)
const testResult = ref<TestResult | null>(null)
const shakingDialog = ref(false)

const templateCategories = computed(() => [
  { id: 'cloud', label: t('aiModel.addDialog.categoryCloud'), icon: Cloud },
  { id: 'local', label: t('aiModel.addDialog.categoryLocal'), icon: Monitor },
  { id: 'aggregator', label: t('aiModel.addDialog.categoryAggregator'), icon: Network },
])

const newProvider = ref<NewProviderForm>({
  id: '',
  name: '',
  vendor: 'openai_compatible',
  baseUrl: '',
  apiKey: '',
  defaultModel: '',
  isDefault: false,
})

const selectedTmpl = computed(() => modelStore.allTemplates.find(t => t.id === selectedTemplate.value))

const isValidUrl = (url: string): boolean => {
  try {
    const u = new URL(url)
    return ['http:', 'https:'].includes(u.protocol)
  } catch {
    return false
  }
}

const newProviderValidation = computed(() => {
  const errors: string[] = []
  if (!newProvider.value.id.trim()) errors.push(t('aiModel.addDialog.errIdEmpty'))
  if (!newProvider.value.baseUrl.trim()) errors.push(t('aiModel.addDialog.errBaseUrlEmpty'))
  if (newProvider.value.baseUrl.trim() && !isValidUrl(newProvider.value.baseUrl)) errors.push(t('aiModel.addDialog.errBaseUrlInvalid'))
  if (newProvider.value.vendor !== 'ollama' && !newProvider.value.apiKey.trim()) errors.push(t('aiModel.addDialog.errApiKeyEmpty'))
  return errors
})

const newProviderFormValid = computed(() => newProviderValidation.value.length === 0)

const shakeDialog = () => {
  shakingDialog.value = true
  setTimeout(() => { shakingDialog.value = false }, 500)
}

const close = () => {
  emit('update:visible', false)
}

const reset = () => {
  selectedTemplate.value = ''
  addDialogStep.value = 'select'
  addTemplateCategory.value = 'cloud'
  newProvider.value = {
    id: '', name: '', vendor: 'openai_compatible',
    baseUrl: '', apiKey: '', defaultModel: '', isDefault: false,
  }
  showApiKey.value = false
  testResult.value = null
  addProviderError.value = ''
}

const handleTemplateSelect = (templateId: string) => {
  selectedTemplate.value = templateId
  const tmpl = modelStore.allTemplates.find(t => t.id === templateId)
  if (tmpl) {
    newProvider.value.id = tmpl.id
    newProvider.value.name = tmpl.name
    newProvider.value.vendor = tmpl.vendor
    newProvider.value.baseUrl = tmpl.baseUrl
    newProvider.value.defaultModel = tmpl.defaultModel
    if (tmpl.vendor === 'ollama') {
      newProvider.value.apiKey = 'ollama'
    } else if (tmpl.id === 'lmstudio') {
      newProvider.value.apiKey = 'lmstudio'
    } else {
      newProvider.value.apiKey = ''
    }
  }
  testResult.value = null
  addDialogStep.value = 'configure'
}

const handleVendorChange = () => {
  if (newProvider.value.vendor === 'ollama') {
    newProvider.value.baseUrl = 'http://localhost:11434/v1'
    newProvider.value.apiKey = 'ollama'
    newProvider.value.defaultModel = 'qwen2.5:7b'
  } else if (newProvider.value.vendor === 'anthropic') {
    newProvider.value.baseUrl = 'https://api.anthropic.com/v1'
    newProvider.value.apiKey = ''
    newProvider.value.defaultModel = 'claude-sonnet-4-20250514'
  } else {
    newProvider.value.baseUrl = 'https://api.openai.com/v1'
    newProvider.value.apiKey = ''
    newProvider.value.defaultModel = 'gpt-4o-mini'
  }
}

const handleTestProvider = async () => {
  if (!newProvider.value.baseUrl.trim()) {
    toast.warning(t('aiModel.addDialog.warnFillBaseUrl'))
    return
  }
  if (newProvider.value.vendor !== 'ollama' && !newProvider.value.apiKey.trim()) {
    toast.warning(t('aiModel.addDialog.warnFillApiKey'))
    return
  }
  testingProvider.value = true
  testResult.value = null
  try {
    const result = await modelStore.testProvider({
      vendor: newProvider.value.vendor,
      baseUrl: newProvider.value.baseUrl.trim(),
      apiKey: newProvider.value.apiKey,
      defaultModel: newProvider.value.defaultModel,
    })
    testResult.value = {
      success: result.success,
      modelCount: result.models.length,
      error: result.error || '',
    }
    if (result.success) {
      toast.success(t('aiModel.addDialog.testSuccessToast', { count: result.models.length }))
    } else {
      toast.error(t('aiModel.addDialog.testFailedToast', { message: result.error || t('aiModel.common.unknownError') }))
    }
  } catch (e: unknown) {
    const errMsg = (e instanceof Error ? e.message : String(e)) || t('aiModel.addDialog.networkError')
    testResult.value = {
      success: false,
      modelCount: 0,
      error: errMsg,
    }
    toast.error(t('aiModel.addDialog.testFailedToast', { message: errMsg }))
  } finally {
    testingProvider.value = false
  }
}

const handleAddProvider = async () => {
  if (!newProviderFormValid.value) {
    addProviderError.value = newProviderValidation.value[0]
    toast.warning(newProviderValidation.value[0])
    return
  }
  addProviderError.value = ''
  addProviderLoading.value = true
  try {
    await modelStore.addProvider({
      id: newProvider.value.id.trim(),
      name: newProvider.value.name.trim() || newProvider.value.id.trim(),
      vendor: newProvider.value.vendor,
      baseUrl: newProvider.value.baseUrl.trim(),
      apiKey: newProvider.value.apiKey,
      defaultModel: newProvider.value.defaultModel.trim(),
      isDefault: newProvider.value.isDefault,
    })
    close()
    toast.success(t('aiModel.addDialog.addSuccessToast', { name: newProvider.value.name.trim() || newProvider.value.id.trim() }))
  } catch (e: unknown) {
    addProviderError.value = (e instanceof Error ? e.message : String(e)) || t('aiModel.addDialog.addFailed')
    toast.error(t('aiModel.addDialog.addFailedToast', { message: (e instanceof Error ? e.message : String(e)) || t('aiModel.common.unknownError') }))
  } finally {
    addProviderLoading.value = false
  }
}

watch(() => props.visible, (visible) => {
  if (visible) reset()
})
</script>

<template>
  <LumiModal
    :visible="visible"
    :shake="shakingDialog"
    :mask-closable="false"
    :width="560"
    @mask-click="shakeDialog"
    @update:visible="emit('update:visible', $event)"
  >
    <template #title>
      <span class="dialog-title">
        <span class="lumi-icon-wrap lumi-icon-wrap--sm dialog-header-icon">
          <Plus :size="18" />
        </span>
        {{ t('aiModel.addDialog.title') }}
      </span>
    </template>

    <div v-if="addProviderError" class="form-error-banner">
          <AlertCircle :size="16" />
          <span>{{ addProviderError }}</span>
        </div>

        <div v-if="addDialogStep === 'select'" class="add-step">
          <div class="step-hint">{{ t('aiModel.addDialog.stepHint') }}</div>

          <div class="category-tabs">
            <button
              v-for="cat in templateCategories"
              :key="cat.id"
              :class="['category-tab', { active: addTemplateCategory === cat.id }]"
              @click="addTemplateCategory = cat.id"
            >
              <component :is="cat.icon" :size="14" />
              <span>{{ cat.label }}</span>
            </button>
          </div>

          <div class="template-cards">
            <button
              v-for="tmpl in (modelStore.templatesByCategory[addTemplateCategory] || [])"
              :key="tmpl.id"
              class="template-card"
              @click="handleTemplateSelect(tmpl.id)"
            >
              <div class="lumi-icon-wrap lumi-icon-wrap--md template-card-logo" :style="tmpl.svgIcon ? {} : { background: tmpl.color || 'var(--text-muted)' }">
                <div v-if="tmpl.svgIcon" class="template-svg-icon" v-html="tmpl.svgIcon"></div>
                <span v-else class="template-initials">{{ tmpl.initials || tmpl.name.slice(0, 2).toUpperCase() }}</span>
              </div>
              <div class="template-card-info">
                <span class="template-card-name">{{ tmpl.name }}</span>
                <span class="template-card-desc">{{ tmpl.description }}</span>
              </div>
              <ChevronRight :size="14" class="template-card-arrow" />
            </button>
          </div>
        </div>

        <div v-if="addDialogStep === 'configure'" class="add-step">
          <button class="back-to-select" @click="addDialogStep = 'select'">
            <ArrowLeft :size="14" />
            <span>{{ t('aiModel.addDialog.backToTemplates') }}</span>
          </button>

          <div v-if="selectedTemplate" class="selected-template-badge">
            <div class="template-card-logo small" :style="selectedTmpl?.svgIcon ? {} : { background: selectedTmpl?.color || 'var(--text-muted)' }">
              <div v-if="selectedTmpl?.svgIcon" class="template-svg-icon small" v-html="selectedTmpl.svgIcon"></div>
              <span v-else class="template-initials">{{ selectedTmpl?.initials || 'CU' }}</span>
            </div>
            <span class="selected-template-name">{{ selectedTmpl?.name || 'Custom' }}</span>
          </div>

          <div class="config-form-compact">
            <div class="form-group">
              <label class="form-label">
                {{ t('aiModel.addDialog.idLabel') }}
                <span class="required-mark">*</span>
              </label>
              <input v-model="newProvider.id" type="text" class="form-input" :class="{ 'input-error': !newProvider.id.trim() && addProviderError }" :placeholder="t('aiModel.addDialog.idPlaceholder')" />
              <span class="form-hint">{{ t('aiModel.addDialog.idHint') }}</span>
            </div>
            <div class="form-group">
              <label class="form-label">{{ t('aiModel.addDialog.nameLabel') }}</label>
              <input v-model="newProvider.name" type="text" class="form-input" :placeholder="t('aiModel.addDialog.namePlaceholder')" />
            </div>
            <div class="form-group">
              <label class="form-label">{{ t('aiModel.addDialog.typeLabel') }}</label>
              <div class="form-select-wrap">
                <select v-model="newProvider.vendor" class="form-select" @change="handleVendorChange">
                  <option value="openai_compatible">{{ t('aiModel.addDialog.vendorOpenaiCompatible') }}</option>
                  <option value="ollama">Ollama</option>
                  <option value="anthropic">Anthropic</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">
                {{ t('aiModel.addDialog.baseUrlLabel') }}
                <span class="required-mark">*</span>
              </label>
              <input v-model="newProvider.baseUrl" type="text" class="form-input" :class="{ 'input-error': !newProvider.baseUrl.trim() && addProviderError }" placeholder="http://localhost:11434/v1" />
              <span class="form-hint">Ollama: http://localhost:11434/v1 | 其他: 含 /v1 后缀</span>
            </div>
            <div class="form-group">
              <label class="form-label">{{ t('aiModel.addDialog.apiKeyLabel') }}</label>
              <div class="api-key-row">
                <input v-model="newProvider.apiKey" :type="showApiKey ? 'text' : 'password'" class="form-input" :class="{ 'input-error': newProvider.vendor !== 'ollama' && !newProvider.apiKey.trim() && addProviderError }" placeholder="sk-..." />
                <button class="eye-btn" @click="showApiKey = !showApiKey">
                  <Eye v-if="!showApiKey" :size="14" />
                  <EyeOff v-else :size="14" />
                </button>
              </div>
              <span class="form-hint">{{ t('aiModel.addDialog.apiKeyHint') }}</span>
            </div>
            <div class="form-group">
              <label class="form-label">{{ t('aiModel.addDialog.testTitle') }}</label>
              <div class="test-provider-row">
                <button
                  class="test-btn"
                  :disabled="testingProvider || !newProvider.baseUrl.trim() || (newProvider.vendor !== 'ollama' && !newProvider.apiKey.trim())"
                  @click="handleTestProvider"
                >
                  <Loader2 v-if="testingProvider" :size="14" class="spin-animation" />
                  <Zap v-else :size="14" />
                  {{ testingProvider ? t('aiModel.addDialog.testing') : t('aiModel.addDialog.testButton') }}
                </button>
                <div v-if="testResult" :class="['test-result', testResult.success ? 'success' : 'error']">
                  <Check v-if="testResult.success" :size="14" />
                  <AlertCircle v-else :size="14" />
                  <span v-if="testResult.success">{{ t('aiModel.addDialog.testOk', { count: testResult.modelCount }) }}</span>
                  <span v-else>{{ testResult.error || t('aiModel.addDialog.testUnavailable') }}</span>
                </div>
              </div>
              <span class="form-hint">{{ t('aiModel.addDialog.testHint') }}</span>
            </div>
            <div class="form-group">
              <div class="toggle-row">
                <label class="form-label">{{ t('aiModel.addDialog.setDefault') }}</label>
                <button
                  :class="['toggle-switch', { active: newProvider.isDefault }]"
                  @click="newProvider.isDefault = !newProvider.isDefault"
                >
                  <span class="toggle-thumb" />
                </button>
              </div>
            </div>
          </div>

          <div class="dialog-actions">
            <button class="dialog-btn cancel" @click="addDialogStep = 'select'">{{ t('aiModel.addDialog.prevStep') }}</button>
            <button
              :class="['dialog-btn confirm', { disabled: !newProviderFormValid || addProviderLoading }]"
              :disabled="!newProviderFormValid || addProviderLoading"
              @click="handleAddProvider"
            >
              <Loader2 v-if="addProviderLoading" :size="16" class="spin-animation" />
              <Check v-else :size="16" />
              {{ t('aiModel.addDialog.add') }}
            </button>
          </div>
        </div>
  </LumiModal>
</template>

<style scoped>
.dialog-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.dialog-header-icon {
  background: var(--lumi-primary-gradient-soft);
  color: var(--lumi-primary);
}

.add-step {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.step-hint {
  font-size: var(--text-base);
  color: var(--text-muted);
  line-height: 1.5;
}

.category-tabs {
  display: flex;
  gap: var(--space-2);
}

.category-tab {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-normal);
  cursor: pointer;
}

.category-tab:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.category-tab.active {
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  font-weight: 600;
}

.template-cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-height: 380px;
  overflow-y: auto;
  padding-right: var(--space-1);
}

.template-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-normal);
  cursor: pointer;
  text-align: left;
  width: 100%;
}

.template-card:hover {
  border-color: var(--lumi-primary);
  box-shadow: 0 1px var(--space-1) var(--lumi-primary-glow);
  transform: translateX(var(--space-1));
}

.template-card-logo {
  flex-shrink: 0;
}

.template-card-logo.small {
  width: var(--space-6);
  height: var(--space-6);
  border-radius: var(--radius-sm);
}

.template-initials {
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--text-inverse);
  letter-spacing: 0.5px;
}

.template-card-logo.small .template-initials {
  font-size: var(--text-2xs);
}

.template-card-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  flex: 1;
  min-width: 0;
}

.template-card-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
}

.template-card-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-card-arrow {
  color: var(--text-muted);
  flex-shrink: 0;
  transition: transform var(--transition-normal);
}

.template-card:hover .template-card-arrow {
  color: var(--lumi-primary);
  transform: translateX(var(--space-1));
}

.back-to-select {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-muted);
  transition: all var(--transition-normal);
  align-self: flex-start;
}

.back-to-select:hover {
  background: var(--workspace-hover);
  color: var(--lumi-primary);
}

.selected-template-badge {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--lumi-primary-light);
  border: 1px solid var(--lumi-primary);
}

.selected-template-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--lumi-primary);
}

.config-form-compact {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.api-key-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.api-key-row .form-input {
  flex: 1;
}

.eye-btn {
  width: var(--space-8);
  height: var(--space-8);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  flex-shrink: 0;
  transition: all var(--transition-normal);
}

.eye-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.form-hint {
  margin-top: calc(var(--space-1) * -1);
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

.input-error {
  border-color: var(--lumi-accent) !important;
  box-shadow: 0 0 0 var(--space-1) var(--task-red-soft) !important;
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toggle-switch {
  width: var(--space-9);
  height: var(--space-6);
  border-radius: var(--radius-md);
  background: var(--workspace-border);
  position: relative;
  cursor: pointer;
  transition: background var(--transition-normal);
  flex-shrink: 0;
}

.toggle-switch.active {
  background: var(--lumi-primary);
}

.toggle-thumb {
  position: absolute;
  top: var(--space-1);
  left: var(--space-1);
  width: var(--space-4);
  height: var(--space-4);
  border-radius: var(--radius-full);
  background: var(--text-inverse);
  transition: transform var(--transition-normal);
  box-shadow: var(--shadow-xs);
}

.toggle-switch.active .toggle-thumb {
  transform: translateX(var(--space-5));
}

.test-provider-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.test-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--lumi-primary);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.test-btn:hover:not(:disabled) {
  background: var(--lumi-primary);
  color: var(--text-inverse);
}

.test-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.test-result {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  font-weight: 500;
}

.test-result.success {
  color: var(--lumi-success, var(--lumi-success));
}

.test-result.error {
  color: var(--lumi-accent);
}

.template-svg-icon {
  width: var(--space-6);
  height: var(--space-6);
  display: flex;
  align-items: center;
  justify-content: center;
}
.template-svg-icon :deep(svg) {
  width: var(--space-6);
  height: var(--space-6);
}
.template-svg-icon.small {
  width: var(--space-4);
  height: var(--space-4);
}
.template-svg-icon.small :deep(svg) {
  width: var(--space-4);
  height: var(--space-4);
}
</style>
