<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ChevronRight,
  Check,
  AlertCircle,
  Eye,
  EyeOff,
} from 'lucide-vue-next'
import LumiModal from '../common/LumiModal.vue'
import LumiButton from '../common/LumiButton.vue'
import { useModelStore } from '../../stores/model'
import { useToast } from '../../composables/useToast'
import type { EditProviderForm } from './types'

const props = defineProps<{
  visible: boolean
  providerId: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const modelStore = useModelStore()
const toast = useToast()
const { t } = useI18n()

const editProviderError = ref('')
const editProviderLoading = ref(false)
const editingProviderId = ref('')
const editModelSelect = ref('')
const shakingDialog = ref(false)
const showApiKey = ref(false)

const editProvider = ref<EditProviderForm>({
  name: '',
  vendor: 'openai_compatible',
  baseUrl: '',
  apiKey: '',
  defaultModel: '',
  isDefault: false,
  protocol: 'auto',
})

const providers = computed(() => modelStore.providers)

const editTemplateDefaultModels = computed(() => {
  const tmpl = modelStore.allTemplates.find(t => t.id === editingProviderId.value)
  return tmpl?.defaultModels || []
})

const isValidUrl = (url: string): boolean => {
  try {
    const u = new URL(url)
    return ['http:', 'https:'].includes(u.protocol)
  } catch {
    return false
  }
}

const editProviderValidation = computed(() => {
  const errors: string[] = []
  if (!editProvider.value.name.trim()) errors.push(t('aiModel.editDialog.errNameEmpty'))
  if (!editProvider.value.baseUrl.trim()) errors.push(t('aiModel.editDialog.errBaseUrlEmpty'))
  if (editProvider.value.baseUrl.trim() && !isValidUrl(editProvider.value.baseUrl)) errors.push(t('aiModel.editDialog.errBaseUrlInvalid'))
  return errors
})

const editProviderFormValid = computed(() => editProviderValidation.value.length === 0)

const shakeDialog = () => {
  shakingDialog.value = true
  setTimeout(() => { shakingDialog.value = false }, 500)
}

const close = () => {
  emit('update:visible', false)
}

const onEditModelSelectChange = () => {
  if (editModelSelect.value && editModelSelect.value !== '__custom__') {
    editProvider.value.defaultModel = editModelSelect.value
  } else if (editModelSelect.value === '__custom__') {
    editProvider.value.defaultModel = ''
  }
}

const openForProvider = (providerId: string) => {
  const p = providers.value.find(pr => pr.id === providerId)
  if (!p) return
  editingProviderId.value = providerId
  editProvider.value = {
    name: p.name,
    vendor: p.vendor,
    baseUrl: p.baseUrl,
    apiKey: '',
    apiKeyPrefix: p.apiKeyPrefix || '',
    defaultModel: p.defaultModel,
    isDefault: p.isDefault,
    protocol: p.protocol || 'auto',
  }
  showApiKey.value = false
  const tmpl = modelStore.allTemplates.find(t => t.id === providerId)
  if (p.defaultModel && tmpl?.defaultModels?.includes(p.defaultModel)) {
    editModelSelect.value = p.defaultModel
  } else if (p.defaultModel) {
    editModelSelect.value = '__custom__'
  } else {
    editModelSelect.value = ''
  }
  editProviderError.value = ''
}

const handleEditProvider = async () => {
  if (!editProviderFormValid.value) {
    editProviderError.value = editProviderValidation.value[0]
    toast.warning(editProviderValidation.value[0])
    return
  }
  editProviderError.value = ''
  editProviderLoading.value = true
  try {
    const updates: {
      name?: string
      vendor?: string
      baseUrl?: string
      apiKey?: string
      defaultModel?: string
      isDefault?: boolean
      protocol?: string
    } = {
      name: editProvider.value.name,
      vendor: editProvider.value.vendor,
      baseUrl: editProvider.value.baseUrl,
      defaultModel: editProvider.value.defaultModel,
      isDefault: editProvider.value.isDefault,
      protocol: editProvider.value.protocol,
    }
    if (editProvider.value.apiKey) {
      updates.apiKey = editProvider.value.apiKey
    }
    await modelStore.updateProvider(editingProviderId.value, updates)
    close()
    toast.success(t('aiModel.editDialog.updateSuccessToast', { name: editProvider.value.name }))
  } catch (e: unknown) {
    const errMsg = (e instanceof Error ? e.message : (e == null ? '' : String(e))) || t('aiModel.editDialog.updateFailed')
    editProviderError.value = errMsg
    toast.error(t('aiModel.editDialog.updateFailedToast', { message: errMsg }))
  } finally {
    editProviderLoading.value = false
  }
}

watch(() => props.visible, (visible) => {
  if (visible && props.providerId) {
    openForProvider(props.providerId)
  }
})

watch(() => props.providerId, (providerId) => {
  if (props.visible && providerId) {
    openForProvider(providerId)
  }
})
</script>

<template>
  <LumiModal
    :visible="visible"
    :shake="shakingDialog"
    :mask-closable="false"
    :width="480"
    :title="t('aiModel.editDialog.title', { name: editProvider.name })"
    @mask-click="shakeDialog"
    @update:visible="emit('update:visible', $event)"
  >
    <div v-if="editProviderError" class="form-error-banner">
          <AlertCircle :size="16" />
          <span>{{ editProviderError }}</span>
        </div>

        <div class="form-group">
          <label class="form-label">{{ t('aiModel.editDialog.nameLabel') }}</label>
          <input v-model="editProvider.name" type="text" class="form-input" :placeholder="t('aiModel.editDialog.namePlaceholder')" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('aiModel.editDialog.typeLabel') }}</label>
          <div class="form-select-wrap">
            <select v-model="editProvider.vendor" class="form-select">
              <option value="openai_compatible">{{ t('aiModel.editDialog.vendorOpenaiCompatible') }}</option>
              <option value="ollama">Ollama</option>
              <option value="anthropic">Anthropic</option>
            </select>
            <ChevronRight :size="14" class="select-icon" />
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('aiModel.editDialog.protocolLabel') }}</label>
          <div class="form-select-wrap">
            <select v-model="editProvider.protocol" class="form-select">
              <option value="auto">{{ t('aiModel.editDialog.protocolAuto') }}</option>
              <option value="chat_completions">{{ t('aiModel.editDialog.protocolChatCompletions') }}</option>
              <option value="anthropic_messages">{{ t('aiModel.editDialog.protocolAnthropicMessages') }}</option>
            </select>
            <ChevronRight :size="14" class="select-icon" />
          </div>
          <span class="form-hint">{{ t('aiModel.editDialog.protocolHint') }}</span>
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('aiModel.editDialog.baseUrlLabel') }}</label>
          <input v-model="editProvider.baseUrl" type="text" class="form-input" :placeholder="t('aiModel.editDialog.baseUrlPlaceholder')" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('aiModel.editDialog.apiKeyLabel') }}</label>
          <div v-if="editProvider.apiKeyPrefix" class="current-key-hint">
            {{ t('aiModel.editDialog.currentKey') }} <code>{{ editProvider.apiKeyPrefix }}</code>
          </div>
          <div class="input-with-eye">
            <input
              v-model="editProvider.apiKey"
              :type="showApiKey ? 'text' : 'password'"
              class="form-input"
              :placeholder="t('aiModel.editDialog.keyPlaceholder')"
            />
            <button
              type="button"
              class="eye-toggle"
              :title="showApiKey ? t('aiModel.editDialog.hide') : t('aiModel.editDialog.show')""
              @click="showApiKey = !showApiKey"
            >
              <Eye v-if="!showApiKey" :size="16" />
              <EyeOff v-else :size="16" />
            </button>
          </div>
          <span class="form-hint">{{ t('aiModel.editDialog.keyHint') }}</span>
        </div>
        <div class="form-group">
          <label class="form-label">{{ t('aiModel.editDialog.defaultModelLabel') }}</label>
          <div class="form-select-wrap">
            <select v-model="editModelSelect" class="form-select" @change="onEditModelSelectChange">
              <option value="">{{ t('aiModel.editDialog.selectModel') }}</option>
              <option v-for="m in editTemplateDefaultModels" :key="m" :value="m">{{ m }}</option>
              <option value="__custom__">{{ t('aiModel.editDialog.customModel') }}</option>
            </select>
            <ChevronRight :size="14" class="select-icon" />
          </div>
          <input v-if="editModelSelect === '__custom__'" v-model="editProvider.defaultModel" type="text" class="form-input" :placeholder="t('aiModel.editDialog.customModelPlaceholder')" style="margin-top: var(--space-2);" />
        </div>
        <div class="form-group">
          <div class="toggle-row">
            <label class="form-label">{{ t('aiModel.editDialog.setDefault') }}</label>
            <button
              :class="['toggle-switch', { active: editProvider.isDefault }]"
              @click="editProvider.isDefault = !editProvider.isDefault"
            >
              <span class="toggle-thumb" />
            </button>
          </div>
        </div>
    <template #footer>
      <LumiButton variant="secondary" size="sm" @click="close">{{ t('aiModel.editDialog.cancel') }}</LumiButton>
      <LumiButton
        variant="primary"
        size="sm"
        :loading="editProviderLoading"
        :disabled="!editProviderFormValid"
        @click="handleEditProvider"
      >
        <template #icon>
          <Check :size="14" />
        </template>
        {{ t('aiModel.editDialog.save') }}
      </LumiButton>
    </template>
  </LumiModal>
</template>

<style scoped>
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

.current-key-hint {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-bottom: var(--space-1);
}

.current-key-hint code {
  font-family: var(--font-mono, 'Courier New', monospace);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  background: var(--workspace-panel);
  padding: 1px var(--space-1);
  border-radius: var(--radius-sm);
}

.input-with-eye {
  position: relative;
  display: flex;
  align-items: center;
}

.input-with-eye .form-input {
  padding-right: var(--space-8);
}

.eye-toggle {
  position: absolute;
  right: var(--space-2);
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-5);
  height: var(--space-5);
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  background: transparent;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.eye-toggle:hover {
  color: var(--text-secondary);
  background: var(--workspace-hover);
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
</style>
