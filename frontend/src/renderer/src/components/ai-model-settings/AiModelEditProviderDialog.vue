<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  X,
  ChevronRight,
  Loader2,
  Check,
  AlertCircle,
  Eye,
  EyeOff,
} from 'lucide-vue-next'
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
  if (!editProvider.value.name.trim()) errors.push('显示名称不能为空')
  if (!editProvider.value.baseUrl.trim()) errors.push('API 地址不能为空')
  if (editProvider.value.baseUrl.trim() && !isValidUrl(editProvider.value.baseUrl)) errors.push('API 地址格式不正确')
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
    toast.success(`供应商「${editProvider.value.name}」已更新`)
  } catch (e: unknown) {
    const errMsg = (e instanceof Error ? e.message : (e == null ? '' : String(e))) || '更新失败'
    editProviderError.value = errMsg
    toast.error(`更新供应商失败：${errMsg}`)
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
  <Transition name="dialog-fade">
    <div v-if="visible" class="dialog-overlay" @click.self="shakeDialog">
      <div :class="['dialog', { 'shake-animation': shakingDialog }]">
        <div class="dialog-header">
          <h3>编辑供应商 - {{ editProvider.name }}</h3>
          <button class="dialog-close" @click="close">
            <X :size="18" />
          </button>
        </div>

        <div v-if="editProviderError" class="form-error-banner">
          <AlertCircle :size="16" />
          <span>{{ editProviderError }}</span>
        </div>

        <div class="form-group">
          <label class="form-label">显示名称</label>
          <input v-model="editProvider.name" type="text" class="form-input" placeholder="显示名称" />
        </div>
        <div class="form-group">
          <label class="form-label">类型</label>
          <div class="form-select-wrap">
            <select v-model="editProvider.vendor" class="form-select">
              <option value="openai_compatible">OpenAI 兼容</option>
              <option value="ollama">Ollama</option>
              <option value="anthropic">Anthropic</option>
            </select>
            <ChevronRight :size="14" class="select-icon" />
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">接入协议</label>
          <div class="form-select-wrap">
            <select v-model="editProvider.protocol" class="form-select">
              <option value="auto">自动（按供应商推断）</option>
              <option value="chat_completions">Chat Completions（OpenAI 兼容）</option>
              <option value="anthropic_messages">Anthropic Messages（原生）</option>
            </select>
            <ChevronRight :size="14" class="select-icon" />
          </div>
          <span class="form-hint">自动：Anthropic 供应商走原生 Messages 协议，其余走 Chat Completions</span>
        </div>
        <div class="form-group">
          <label class="form-label">API 地址</label>
          <input v-model="editProvider.baseUrl" type="text" class="form-input" placeholder="API 地址" />
        </div>
        <div class="form-group">
          <label class="form-label">API Key</label>
          <div v-if="editProvider.apiKeyPrefix" class="current-key-hint">
            当前密钥: <code>{{ editProvider.apiKeyPrefix }}</code>
          </div>
          <div class="input-with-eye">
            <input
              v-model="editProvider.apiKey"
              :type="showApiKey ? 'text' : 'password'"
              class="form-input"
              placeholder="留空则不修改"
            />
            <button
              type="button"
              class="eye-toggle"
              :title="showApiKey ? '隐藏' : '显示'"
              @click="showApiKey = !showApiKey"
            >
              <Eye v-if="!showApiKey" :size="16" />
              <EyeOff v-else :size="16" />
            </button>
          </div>
          <span class="form-hint">留空表示不修改现有密钥</span>
        </div>
        <div class="form-group">
          <label class="form-label">默认模型</label>
          <div class="form-select-wrap">
            <select v-model="editModelSelect" class="form-select" @change="onEditModelSelectChange">
              <option value="">请选择模型</option>
              <option v-for="m in editTemplateDefaultModels" :key="m" :value="m">{{ m }}</option>
              <option value="__custom__">自定义模型...</option>
            </select>
            <ChevronRight :size="14" class="select-icon" />
          </div>
          <input v-if="editModelSelect === '__custom__'" v-model="editProvider.defaultModel" type="text" class="form-input" placeholder="输入自定义模型名称" style="margin-top: var(--space-2);" />
        </div>
        <div class="form-group">
          <div class="toggle-row">
            <label class="form-label">设为默认</label>
            <button
              :class="['toggle-switch', { active: editProvider.isDefault }]"
              @click="editProvider.isDefault = !editProvider.isDefault"
            >
              <span class="toggle-thumb" />
            </button>
          </div>
        </div>
        <div class="dialog-actions">
          <button class="dialog-btn cancel" @click="close">取消</button>
          <button
            :class="['dialog-btn confirm', { disabled: !editProviderFormValid || editProviderLoading }]"
            :disabled="!editProviderFormValid || editProviderLoading"
            @click="handleEditProvider"
          >
            <Loader2 v-if="editProviderLoading" :size="16" class="spin-animation" />
            <Check v-else :size="16" />
            保存
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.dialog-overlay {
  background: var(--overlay-bg);
  z-index: 100;
  backdrop-filter: blur(var(--space-1));
}

.dialog {
  background: var(--workspace-card);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  width: 480px;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: var(--shadow-xl);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-5);
}

.dialog-header h3 {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--text-primary);
}

.dialog-close {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-normal);
}

.dialog-close:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.dialog-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-5);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.dialog-btn.cancel {
  color: var(--text-muted);
  background: var(--workspace-panel);
}

.dialog-btn.cancel:hover {
  background: var(--workspace-hover);
}

.dialog-btn.confirm {
  color: var(--text-inverse);
  background: var(--lumi-primary);
}

.dialog-btn.confirm:hover {
  background: var(--lumi-primary-hover);
}

.form-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: calc(var(--space-1) * -1);
}

.form-error-banner {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
  font-size: var(--text-base);
  font-weight: 500;
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

.form-input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  color: var(--text-primary);
  transition: all var(--transition-normal);
}

.form-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 var(--space-1) var(--lumi-primary-glow);
}

.form-input::placeholder {
  color: var(--text-muted);
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

.spin-animation {
  animation: spin 1s linear infinite;
}

.dialog-fade-enter-active {
  animation: dialog-in var(--duration-slow) var(--ease-in-out);
}

.dialog-fade-leave-active {
  animation: dialog-in var(--duration-fast) var(--ease-in-out) reverse;
}

@keyframes dialog-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.shake-animation {
  animation: dialog-shake var(--duration-slow) var(--ease-in-out);
}

@keyframes dialog-shake {
  0%, 100% { transform: scale(1); }
  20% { transform: scale(1.02); }
  40% { transform: scale(0.98); }
  60% { transform: scale(1.01); }
  80% { transform: scale(0.99); }
}
</style>
