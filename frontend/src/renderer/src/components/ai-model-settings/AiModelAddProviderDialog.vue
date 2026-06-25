<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  Plus,
  X,
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

const showApiKey = ref(false)
const addProviderError = ref('')
const addProviderLoading = ref(false)
const selectedTemplate = ref<string>('')
const addDialogStep = ref<'select' | 'configure'>('select')
const addTemplateCategory = ref('cloud')
const testingProvider = ref(false)
const testResult = ref<TestResult | null>(null)
const shakingDialog = ref(false)

const templateCategories = [
  { id: 'cloud', label: '云端 API', icon: Cloud },
  { id: 'local', label: '本地推理', icon: Monitor },
  { id: 'aggregator', label: '聚合网关', icon: Network },
]

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
  if (!newProvider.value.id.trim()) errors.push('标识 ID 不能为空')
  if (!newProvider.value.baseUrl.trim()) errors.push('API 地址不能为空')
  if (newProvider.value.baseUrl.trim() && !isValidUrl(newProvider.value.baseUrl)) errors.push('API 地址格式不正确')
  if (newProvider.value.vendor !== 'ollama' && !newProvider.value.apiKey.trim()) errors.push('API Key 不能为空')
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
    toast.warning('请先填写 API 地址')
    return
  }
  if (newProvider.value.vendor !== 'ollama' && !newProvider.value.apiKey.trim()) {
    toast.warning('请先填写 API Key')
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
      toast.success(`检测成功，共获取到 ${result.models.length} 个模型`)
    } else {
      toast.error(`检测失败：${result.error || '未知错误'}`)
    }
  } catch (e: any) {
    testResult.value = {
      success: false,
      modelCount: 0,
      error: e.message || '网络错误',
    }
    toast.error(`检测失败：${e.message || '网络错误'}`)
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
    toast.success(`供应商「${newProvider.value.name.trim() || newProvider.value.id.trim()}」添加成功`)
  } catch (e: any) {
    addProviderError.value = e.message || '添加失败'
    toast.error(`添加供应商失败：${e.message || '未知错误'}`)
  } finally {
    addProviderLoading.value = false
  }
}

watch(() => props.visible, (visible) => {
  if (visible) reset()
})
</script>

<template>
  <Transition name="dialog-fade">
    <div v-if="visible" class="dialog-overlay" @click.self="shakeDialog">
      <div :class="['dialog', 'add-dialog', { 'shake-animation': shakingDialog }]">
        <div class="dialog-header">
          <div class="dialog-header-left">
            <div class="lumi-icon-wrap lumi-icon-wrap--sm dialog-header-icon">
              <Plus :size="18" />
            </div>
            <h3>添加模型供应商</h3>
          </div>
          <button class="dialog-close" @click="close">
            <X :size="18" />
          </button>
        </div>

        <div v-if="addProviderError" class="form-error-banner">
          <AlertCircle :size="16" />
          <span>{{ addProviderError }}</span>
        </div>

        <div v-if="addDialogStep === 'select'" class="add-step">
          <div class="step-hint">选择一个供应商模板快速开始，或选择 Custom 自定义配置</div>

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
            <span>返回选择模板</span>
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
                标识 ID
                <span class="required-mark">*</span>
              </label>
              <input v-model="newProvider.id" type="text" class="form-input" :class="{ 'input-error': !newProvider.id.trim() && addProviderError }" placeholder="如: my-ollama" />
              <span class="form-hint">唯一标识，不可与已有供应商重复</span>
            </div>
            <div class="form-group">
              <label class="form-label">显示名称</label>
              <input v-model="newProvider.name" type="text" class="form-input" placeholder="如: My Ollama" />
            </div>
            <div class="form-group">
              <label class="form-label">类型</label>
              <div class="form-select-wrap">
                <select v-model="newProvider.vendor" class="form-select" @change="handleVendorChange">
                  <option value="openai_compatible">OpenAI 兼容</option>
                  <option value="ollama">Ollama</option>
                  <option value="anthropic">Anthropic</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">
                API 地址
                <span class="required-mark">*</span>
              </label>
              <input v-model="newProvider.baseUrl" type="text" class="form-input" :class="{ 'input-error': !newProvider.baseUrl.trim() && addProviderError }" placeholder="http://localhost:11434/v1" />
              <span class="form-hint">Ollama: http://localhost:11434/v1 | 其他: 含 /v1 后缀</span>
            </div>
            <div class="form-group">
              <label class="form-label">API Key</label>
              <div class="api-key-row">
                <input v-model="newProvider.apiKey" :type="showApiKey ? 'text' : 'password'" class="form-input" :class="{ 'input-error': newProvider.vendor !== 'ollama' && !newProvider.apiKey.trim() && addProviderError }" placeholder="sk-..." />
                <button class="eye-btn" @click="showApiKey = !showApiKey">
                  <Eye v-if="!showApiKey" :size="14" />
                  <EyeOff v-else :size="14" />
                </button>
              </div>
              <span class="form-hint">Ollama 自动填充，其他供应商需填写真实密钥</span>
            </div>
            <div class="form-group">
              <label class="form-label">API 连通性检测</label>
              <div class="test-provider-row">
                <button
                  class="test-btn"
                  :disabled="testingProvider || !newProvider.baseUrl.trim() || (newProvider.vendor !== 'ollama' && !newProvider.apiKey.trim())"
                  @click="handleTestProvider"
                >
                  <Loader2 v-if="testingProvider" :size="14" class="spin-animation" />
                  <Zap v-else :size="14" />
                  {{ testingProvider ? '检测中...' : '检测 API / TOKEN' }}
                </button>
                <div v-if="testResult" :class="['test-result', testResult.success ? 'success' : 'error']">
                  <Check v-if="testResult.success" :size="14" />
                  <AlertCircle v-else :size="14" />
                  <span v-if="testResult.success">可用，共 {{ testResult.modelCount }} 个模型</span>
                  <span v-else>{{ testResult.error || '不可用' }}</span>
                </div>
              </div>
              <span class="form-hint">检测会调用供应商 /models 接口验证 API 地址与密钥是否可用</span>
            </div>
            <div class="form-group">
              <div class="toggle-row">
                <label class="form-label">设为默认</label>
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
            <button class="dialog-btn cancel" @click="addDialogStep = 'select'">上一步</button>
            <button
              :class="['dialog-btn confirm', { disabled: !newProviderFormValid || addProviderLoading }]"
              :disabled="!newProviderFormValid || addProviderLoading"
              @click="handleAddProvider"
            >
              <Loader2 v-if="addProviderLoading" :size="16" class="spin-animation" />
              <Check v-else :size="16" />
              添加
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.add-dialog {
  width: 560px;
  max-height: 85vh;
}

.dialog-header-left {
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

.add-dialog {
  width: 560px;
  max-height: 85vh;
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
