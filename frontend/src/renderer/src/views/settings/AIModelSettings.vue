<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  Cpu,
  Zap,
  Atom,
  Volume2,
  Mic,
  Plus,
  ChevronRight,
  Search,
  Trash2,
  Eye,
  EyeOff,
  Check,
  AlertCircle,
  Loader2,
  Server,
  Edit3,
  Info,
  Settings2,
  X,
  RefreshCw,
  Cloud,
  Monitor,
  Network,
} from 'lucide-vue-next'
import { useModelStore } from '../../stores/model'
import { useToast } from '../../composables/useToast'

const router = useRouter()
const modelStore = useModelStore()
const toast = useToast()

const activeTile = ref('main')

const modelTiles = [
  { id: 'main', label: '主模型', icon: Zap, tag: '快速响应' },
  { id: 'reasoner', label: '推理模型', icon: Atom, tag: 'Agent' },
  { id: 'tts', label: '语音合成', icon: Volume2, tag: 'TTS' },
  { id: 'stt', label: '语音识别', icon: Mic, tag: 'STT' },
]

const showInfo = reactive<Record<string, boolean>>({
  main: false,
  reasoner: false,
  tts: false,
  stt: false,
})

const toggleInfo = (section: string) => {
  showInfo[section] = !showInfo[section]
}

const providers = computed(() => modelStore.providers)

const showApiKey = ref<Record<string, boolean>>({ add: false })

const showAddDialog = ref(false)
const showProviderList = ref(true)
const addProviderError = ref('')
const addProviderLoading = ref(false)
const selectedTemplate = ref<string>('')
const addDialogStep = ref<'select' | 'configure'>('select')
const addTemplateCategory = ref('cloud')

const templateCategories = [
  { id: 'cloud', label: '云端 API', icon: Cloud },
  { id: 'local', label: '本地推理', icon: Monitor },
  { id: 'aggregator', label: '聚合网关', icon: Network },
]
const newProvider = ref({
  id: '',
  name: '',
  vendor: 'openai_compatible',
  baseUrl: '',
  apiKey: '',
  defaultModel: '',
  isDefault: false,
})

const showEditDialog = ref(false)
const editProviderError = ref('')
const editProviderLoading = ref(false)
const editingProviderId = ref('')
const editProvider = ref({
  name: '',
  vendor: 'openai_compatible',
  baseUrl: '',
  apiKey: '',
  defaultModel: '',
  isDefault: false,
})

const addModelSelect = ref('')
const editModelSelect = ref('')
const shakingDialog = ref('')

const currentTemplateDefaultModels = computed(() => {
  const tmpl = modelStore.allTemplates.find(t => t.id === selectedTemplate.value)
  return tmpl?.defaultModels || []
})

const editTemplateDefaultModels = computed(() => {
  const tmpl = modelStore.allTemplates.find(t => t.id === editingProviderId.value)
  return tmpl?.defaultModels || []
})

const selectedTmpl = computed(() => modelStore.allTemplates.find(t => t.id === selectedTemplate.value))

const onAddModelSelectChange = () => {
  if (addModelSelect.value && addModelSelect.value !== '__custom__') {
    newProvider.value.defaultModel = addModelSelect.value
  } else if (addModelSelect.value === '__custom__') {
    newProvider.value.defaultModel = ''
  }
}

const onEditModelSelectChange = () => {
  if (editModelSelect.value && editModelSelect.value !== '__custom__') {
    editProvider.value.defaultModel = editModelSelect.value
  } else if (editModelSelect.value === '__custom__') {
    editProvider.value.defaultModel = ''
  }
}

const shakeDialog = (dialog: string) => {
  shakingDialog.value = dialog
  setTimeout(() => { shakingDialog.value = '' }, 500)
}

const isValidUrl = (url: string): boolean => {
  try {
    const u = new URL(url)
    return ['http:', 'https:'].includes(u.protocol)
  } catch {
    return false
  }
}

const getProviderIcon = (providerId: string): string => {
  const tmpl = modelStore.allTemplates.find(t => t.id === providerId)
  return tmpl?.svgIcon || ''
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
    if (tmpl.defaultModel && tmpl.defaultModels?.includes(tmpl.defaultModel)) {
      addModelSelect.value = tmpl.defaultModel
    } else if (tmpl.defaultModel) {
      addModelSelect.value = '__custom__'
    } else {
      addModelSelect.value = ''
    }
  }
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

const mainModelConfig = ref({
  selectedProvider: '',
  model: '',
  temperature: 0.7,
  topP: 0.9,
  maxTokens: 4096,
})

const reasonerModelConfig = ref({
  selectedProvider: '',
  model: '',
  temperature: 0.3,
  maxTokens: 8192,
  reasoningEffort: 'medium',
})

const ttsConfigForm = ref({
  provider: '',
  model: 'tts-1',
  voice: 'alloy',
  speed: 1.0,
})

const sttConfigForm = ref({
  provider: '',
  model: 'whisper-1',
  language: 'zh-CN',
  autoSend: false,
  autoSendDelay: 2000,
})

const mainAvailableModels = computed(() =>
  modelStore.getProviderModels(mainModelConfig.value.selectedProvider)
)

const reasonerAvailableModels = computed(() =>
  modelStore.getProviderModels(reasonerModelConfig.value.selectedProvider)
)

const newProviderValidation = computed(() => {
  const errors: string[] = []
  if (!newProvider.value.id.trim()) errors.push('标识 ID 不能为空')
  if (!newProvider.value.baseUrl.trim()) errors.push('API 地址不能为空')
  if (newProvider.value.baseUrl.trim() && !isValidUrl(newProvider.value.baseUrl)) errors.push('API 地址格式不正确')
  if (newProvider.value.vendor !== 'ollama' && !newProvider.value.apiKey.trim()) errors.push('API Key 不能为空')
  if (!newProvider.value.defaultModel.trim()) errors.push('请选择或输入默认模型')
  return errors
})

const newProviderFormValid = computed(() => newProviderValidation.value.length === 0)

const editProviderValidation = computed(() => {
  const errors: string[] = []
  if (!editProvider.value.name.trim()) errors.push('显示名称不能为空')
  if (!editProvider.value.baseUrl.trim()) errors.push('API 地址不能为空')
  if (editProvider.value.baseUrl.trim() && !isValidUrl(editProvider.value.baseUrl)) errors.push('API 地址格式不正确')
  return errors
})

const editProviderFormValid = computed(() => editProviderValidation.value.length === 0)

const saveValidationErrors = reactive<Record<string, string>>({
  main: '',
  reasoner: '',
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

const reasonerConfigValid = computed(() => {
  if (!reasonerModelConfig.value.selectedProvider) {
    return { valid: false, error: '请选择供应商' }
  }
  if (!reasonerModelConfig.value.model) {
    return { valid: false, error: '请选择模型' }
  }
  return { valid: true, error: '' }
})

const onMainProviderChange = () => {
  saveValidationErrors.main = ''
  mainModelConfig.value.model = ''
}

const onReasonerProviderChange = () => {
  saveValidationErrors.reasoner = ''
  reasonerModelConfig.value.model = ''
}

const openAddDialog = () => {
  selectedTemplate.value = ''
  addDialogStep.value = 'select'
  addTemplateCategory.value = 'cloud'
  newProvider.value = {
    id: '', name: '', vendor: 'openai_compatible',
    baseUrl: '', apiKey: '', defaultModel: '', isDefault: false,
  }
  addModelSelect.value = ''
  addProviderError.value = ''
  showAddDialog.value = true
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
    showAddDialog.value = false
    toast.success(`供应商「${newProvider.value.name.trim() || newProvider.value.id.trim()}」添加成功`)
  } catch (e: any) {
    addProviderError.value = e.message || '添加失败'
    toast.error(`添加供应商失败：${e.message || '未知错误'}`)
  } finally {
    addProviderLoading.value = false
  }
}

const openEditDialog = (providerId: string) => {
  const p = providers.value.find(pr => pr.id === providerId)
  if (!p) return
  editingProviderId.value = providerId
  editProvider.value = {
    name: p.name,
    vendor: p.vendor,
    baseUrl: p.baseUrl,
    apiKey: '',
    defaultModel: p.defaultModel,
    isDefault: p.isDefault,
  }
  const tmpl = modelStore.allTemplates.find(t => t.id === providerId)
  if (p.defaultModel && tmpl?.defaultModels?.includes(p.defaultModel)) {
    editModelSelect.value = p.defaultModel
  } else if (p.defaultModel) {
    editModelSelect.value = '__custom__'
  } else {
    editModelSelect.value = ''
  }
  editProviderError.value = ''
  showEditDialog.value = true
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
    const updates: any = {
      name: editProvider.value.name,
      vendor: editProvider.value.vendor,
      baseUrl: editProvider.value.baseUrl,
      defaultModel: editProvider.value.defaultModel,
      isDefault: editProvider.value.isDefault,
    }
    if (editProvider.value.apiKey) {
      updates.apiKey = editProvider.value.apiKey
    }
    await modelStore.updateProvider(editingProviderId.value, updates)
    showEditDialog.value = false
    toast.success(`供应商「${editProvider.value.name}」已更新`)
  } catch (e: any) {
    editProviderError.value = e.message || '更新失败'
    toast.error(`更新供应商失败：${e.message || '未知错误'}`)
  } finally {
    editProviderLoading.value = false
  }
}

const handleRemoveProvider = async (providerId: string) => {
  try {
    const p = providers.value.find(pr => pr.id === providerId)
    await modelStore.removeProvider(providerId)
    toast.success(`供应商「${p?.name || providerId}」已删除`)
  } catch (e: any) {
    console.error('Failed to remove provider:', e)
    toast.error(`删除供应商失败：${e.message || '未知错误'}`)
  }
}

const handleFetchModels = async (providerId: string) => {
  try {
    await modelStore.fetchProviderModels(providerId)
    toast.info('模型列表已刷新')
  } catch (e: any) {
    console.error('Failed to fetch models:', e)
    toast.error(`获取模型列表失败：${e.message || '未知错误'}`)
  }
}

const saveStatus = reactive<Record<string, 'idle' | 'saving' | 'saved' | 'error'>>({
  main: 'idle',
  reasoner: 'idle',
  tts: 'idle',
  stt: 'idle',
})

const handleSaveMainConfig = async () => {
  saveValidationErrors.main = ''
  if (!mainConfigValid.value.valid) {
    saveValidationErrors.main = mainConfigValid.value.error
    saveStatus.main = 'error'
    toast.warning(mainConfigValid.value.error)
    setTimeout(() => { saveStatus.main = 'idle' }, 3000)
    return
  }
  saveStatus.main = 'saving'
  try {
    await modelStore.updateModelConfig({
      defaultProvider: mainModelConfig.value.selectedProvider,
      defaultModel: mainModelConfig.value.model,
      defaultTemperature: mainModelConfig.value.temperature,
      defaultMaxTokens: mainModelConfig.value.maxTokens,
      defaultTopP: mainModelConfig.value.topP,
    })
    saveStatus.main = 'saved'
    toast.success('主模型配置已保存')
    setTimeout(() => { saveStatus.main = 'idle' }, 2000)
  } catch {
    saveStatus.main = 'error'
    toast.error('主模型配置保存失败')
    setTimeout(() => { saveStatus.main = 'idle' }, 3000)
  }
}

const handleSaveReasonerConfig = async () => {
  saveValidationErrors.reasoner = ''
  if (!reasonerConfigValid.value.valid) {
    saveValidationErrors.reasoner = reasonerConfigValid.value.error
    saveStatus.reasoner = 'error'
    toast.warning(reasonerConfigValid.value.error)
    setTimeout(() => { saveStatus.reasoner = 'idle' }, 3000)
    return
  }
  saveStatus.reasoner = 'saving'
  try {
    await modelStore.updateModelConfig({
      reasonerProvider: reasonerModelConfig.value.selectedProvider,
      reasonerModel: reasonerModelConfig.value.model,
      reasonerTemperature: reasonerModelConfig.value.temperature,
      reasonerMaxTokens: reasonerModelConfig.value.maxTokens,
      reasonerEffort: reasonerModelConfig.value.reasoningEffort,
    })
    saveStatus.reasoner = 'saved'
    toast.success('推理模型配置已保存')
    setTimeout(() => { saveStatus.reasoner = 'idle' }, 2000)
  } catch {
    saveStatus.reasoner = 'error'
    toast.error('推理模型配置保存失败')
    setTimeout(() => { saveStatus.reasoner = 'idle' }, 3000)
  }
}

const handleSaveTTSConfig = async () => {
  saveStatus.tts = 'saving'
  try {
    await modelStore.updateTTSConfig({
      provider: ttsConfigForm.value.provider,
      model: ttsConfigForm.value.model,
      voice: ttsConfigForm.value.voice,
      speed: ttsConfigForm.value.speed,
    })
    saveStatus.tts = 'saved'
    setTimeout(() => { saveStatus.tts = 'idle' }, 2000)
  } catch {
    saveStatus.tts = 'error'
    setTimeout(() => { saveStatus.tts = 'idle' }, 3000)
  }
}

const handleSaveSTTConfig = async () => {
  saveStatus.stt = 'saving'
  try {
    await modelStore.updateSTTConfig({
      provider: sttConfigForm.value.provider,
      model: sttConfigForm.value.model,
      language: sttConfigForm.value.language,
      autoSend: sttConfigForm.value.autoSend,
      autoSendDelay: sttConfigForm.value.autoSendDelay,
    })
    saveStatus.stt = 'saved'
    setTimeout(() => { saveStatus.stt = 'idle' }, 2000)
  } catch {
    saveStatus.stt = 'error'
    setTimeout(() => { saveStatus.stt = 'idle' }, 3000)
  }
}

onMounted(async () => {
  await modelStore.fetchProviders()
  await modelStore.fetchTemplates()
  await modelStore.fetchModelConfig()

  const cfg = modelStore.modelConfig
  mainModelConfig.value.selectedProvider = cfg.defaultProvider
  mainModelConfig.value.model = cfg.defaultModel
  mainModelConfig.value.temperature = cfg.defaultTemperature
  mainModelConfig.value.topP = cfg.defaultTopP
  mainModelConfig.value.maxTokens = cfg.defaultMaxTokens

  if (cfg.reasonerProvider) {
    reasonerModelConfig.value.selectedProvider = cfg.reasonerProvider
    reasonerModelConfig.value.model = cfg.reasonerModel || ''
    reasonerModelConfig.value.temperature = cfg.reasonerTemperature || 0.3
    reasonerModelConfig.value.maxTokens = cfg.reasonerMaxTokens || 8192
    reasonerModelConfig.value.reasoningEffort = cfg.reasonerEffort || 'medium'
  }

  const tts = modelStore.ttsConfig
  ttsConfigForm.value.provider = tts.provider
  ttsConfigForm.value.model = tts.model
  ttsConfigForm.value.voice = tts.voice
  ttsConfigForm.value.speed = tts.speed

  const stt = modelStore.sttConfig
  sttConfigForm.value.provider = stt.provider
  sttConfigForm.value.model = stt.model
  sttConfigForm.value.language = stt.language
  sttConfigForm.value.autoSend = stt.autoSend
  sttConfigForm.value.autoSendDelay = stt.autoSendDelay
})
</script>

<template>
  <div class="ai-model-settings">
    <div class="settings-detail-header animate-fade-in">
      <button class="back-btn" @click="router.push('/settings')">
        <ArrowLeft :size="18" />
      </button>
      <div class="header-icon">
        <Cpu :size="24" />
      </div>
      <div>
        <h1 class="page-title">AI 模型</h1>
        <p class="page-subtitle">配置 LuomiNest 大语言模型与语音引擎</p>
      </div>
    </div>

    <div class="settings-detail-body">
      <div class="detail-sidebar animate-slide-up">
        <nav class="tile-nav">
          <button
            v-for="tile in modelTiles"
            :key="tile.id"
            :class="['tile-item', { active: activeTile === tile.id }]"
            @click="activeTile = tile.id"
          >
            <component :is="tile.icon" :size="18" />
            <div class="tile-text">
              <span class="tile-label">{{ tile.label }}</span>
              <span class="tile-tag">{{ tile.tag }}</span>
            </div>
          </button>
        </nav>

        <div class="sidebar-footer">
          <button class="add-provider-btn" @click="openAddDialog">
            <Plus :size="16" />
            <span>添加供应商</span>
          </button>
        </div>
      </div>

      <div class="detail-content animate-slide-up" :style="{ animationDelay: '100ms' }">
        <!-- 主模型（快速响应） -->
        <div v-if="activeTile === 'main'" class="content-section">
          <div class="section-header">
            <div class="section-header-left">
              <div class="section-header-text">
                <h3 class="section-title">主模型</h3>
                <span class="section-tag">快速响应</span>
              </div>
            </div>
            <button
              :class="['info-btn', { active: showInfo.main }]"
              @click="toggleInfo('main')"
            >
              <Info :size="16" />
            </button>
          </div>
          <Transition name="info-expand">
            <div v-if="showInfo.main" class="section-info-panel">
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
                <select v-model="mainModelConfig.selectedProvider" class="form-select" :class="{ 'select-error': saveValidationErrors.main && !mainModelConfig.selectedProvider }" @change="onMainProviderChange">
                  <option value="">请选择供应商</option>
                  <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
              <span v-if="saveValidationErrors.main && !mainModelConfig.selectedProvider" class="form-hint hint-error">
                {{ saveValidationErrors.main }}
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
              :class="['save-btn', { saving: saveStatus.main === 'saving', saved: saveStatus.main === 'saved', error: saveStatus.main === 'error' }]"
              :disabled="saveStatus.main === 'saving'"
              @click="handleSaveMainConfig"
            >
              <Loader2 v-if="saveStatus.main === 'saving'" :size="16" class="spin-animation" />
              <Check v-else-if="saveStatus.main === 'saved'" :size="16" />
              <AlertCircle v-else-if="saveStatus.main === 'error'" :size="16" />
              <Check v-else :size="16" />
              {{ saveStatus.main === 'saving' ? '保存中...' : saveStatus.main === 'saved' ? '已保存' : saveStatus.main === 'error' ? (saveValidationErrors.main || '保存失败') : '保存配置' }}
            </button>
          </div>

          <div class="provider-section">
            <div class="provider-section-header" @click="showProviderList = !showProviderList">
              <div class="provider-section-title">
                <Settings2 :size="14" />
                <span>供应商管理</span>
                <span class="provider-count">{{ providers.length }}</span>
              </div>
              <ChevronRight :size="14" :class="['chevron-toggle', { expanded: showProviderList }]" />
            </div>
            <Transition name="expand">
              <div v-if="showProviderList" class="provider-list">
                <div v-for="provider in providers" :key="provider.id" class="provider-item">
                  <div class="provider-item-info">
                    <div class="provider-item-header">
                      <div v-if="getProviderIcon(provider.id)" class="provider-svg-icon" v-html="getProviderIcon(provider.id)"></div>
                      <Server v-else :size="14" class="provider-item-icon" />
                      <span class="provider-item-name">{{ provider.name }}</span>
                      <span v-if="provider.isDefault" class="default-badge">默认</span>
                    </div>
                    <div class="provider-item-detail">
                      <span class="detail-text">{{ provider.baseUrl }}</span>
                      <span class="detail-sep">|</span>
                      <span class="detail-text">{{ provider.defaultModel || '未设置' }}</span>
                    </div>
                  </div>
                  <div class="provider-item-actions">
                    <button class="action-btn" title="获取模型" @click="handleFetchModels(provider.id)">
                      <Search :size="13" />
                    </button>
                    <button class="action-btn" title="编辑" @click="openEditDialog(provider.id)">
                      <Edit3 :size="13" />
                    </button>
                    <button class="action-btn danger" title="删除" @click="handleRemoveProvider(provider.id)">
                      <Trash2 :size="13" />
                    </button>
                  </div>
                </div>
                <div v-if="providers.length === 0" class="empty-provider">
                  <p>暂无供应商</p>
                  <button class="add-inline-btn" @click="openAddDialog">
                    <Plus :size="14" />
                    添加供应商
                  </button>
                </div>
              </div>
            </Transition>
          </div>
        </div>

        <!-- 推理模型（复杂Agent任务） -->
        <div v-if="activeTile === 'reasoner'" class="content-section">
          <div class="section-header">
            <div class="section-header-left">
              <div class="section-header-text">
                <h3 class="section-title">推理模型</h3>
                <span class="section-tag">复杂 Agent 任务</span>
              </div>
            </div>
            <button
              :class="['info-btn', { active: showInfo.reasoner }]"
              @click="toggleInfo('reasoner')"
            >
              <Info :size="16" />
            </button>
          </div>
          <Transition name="info-expand">
            <div v-if="showInfo.reasoner" class="section-info-panel">
              <p>推理模型用于复杂逻辑推理、数学计算、代码分析等需要深度思考的场景。当主模型未配置时，推理模型将作为默认模型使用。</p>
              <p class="info-tip">推荐使用 DeepSeek-R1、Claude Opus、o1 等具备推理能力的模型。</p>
            </div>
          </Transition>

          <div class="config-form">
            <div class="form-group">
              <label class="form-label">
                供应商
                <span class="required-mark">*</span>
              </label>
              <div class="form-select-wrap">
                <select v-model="reasonerModelConfig.selectedProvider" class="form-select" :class="{ 'select-error': saveValidationErrors.reasoner && !reasonerModelConfig.selectedProvider }" @change="onReasonerProviderChange">
                  <option value="">请选择供应商</option>
                  <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
              <span v-if="saveValidationErrors.reasoner && !reasonerModelConfig.selectedProvider" class="form-hint hint-error">
                {{ saveValidationErrors.reasoner }}
              </span>
            </div>
            <div class="form-group">
              <label class="form-label">模型</label>
              <div class="form-select-wrap">
                <select v-model="reasonerModelConfig.model" class="form-select">
                  <option value="">请选择模型</option>
                  <option v-for="m in reasonerAvailableModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
              <div v-if="reasonerModelConfig.selectedProvider && reasonerAvailableModels.length === 0" class="fetch-models-row">
                <span class="form-hint">暂无模型列表</span>
                <button class="fetch-btn" @click="handleFetchModels(reasonerModelConfig.selectedProvider)">
                  <RefreshCw :size="12" />
                  获取
                </button>
              </div>
              <span v-if="reasonerModelConfig.model && reasonerAvailableModels.length > 0 && !reasonerAvailableModels.find(m => m.id === reasonerModelConfig.model)" class="form-hint hint-warn">
                当前供应商可能不支持此模型，请求时可能报错
              </span>
            </div>
            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Temperature</label>
                <span class="form-value">{{ reasonerModelConfig.temperature }}</span>
              </div>
              <input type="range" v-model.number="reasonerModelConfig.temperature" min="0" max="2" step="0.1" class="form-slider" />
              <div class="slider-labels"><span>精确</span><span>创意</span></div>
            </div>
            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Max Tokens</label>
                <span class="form-value">{{ reasonerModelConfig.maxTokens }}</span>
              </div>
              <input type="range" v-model.number="reasonerModelConfig.maxTokens" min="1024" max="32768" step="1024" class="form-slider" />
            </div>
            <div class="form-group">
              <label class="form-label">推理强度</label>
              <div class="effort-group">
                <button
                  v-for="effort in [{ value: 'low', label: '低' }, { value: 'medium', label: '中' }, { value: 'high', label: '高' }]"
                  :key="effort.value"
                  :class="['effort-btn', { active: reasonerModelConfig.reasoningEffort === effort.value }]"
                  @click="reasonerModelConfig.reasoningEffort = effort.value"
                >
                  {{ effort.label }}
                </button>
              </div>
            </div>

            <button
              :class="['save-btn', { saving: saveStatus.reasoner === 'saving', saved: saveStatus.reasoner === 'saved', error: saveStatus.reasoner === 'error' }]"
              :disabled="saveStatus.reasoner === 'saving'"
              @click="handleSaveReasonerConfig"
            >
              <Loader2 v-if="saveStatus.reasoner === 'saving'" :size="16" class="spin-animation" />
              <Check v-else-if="saveStatus.reasoner === 'saved'" :size="16" />
              <AlertCircle v-else-if="saveStatus.reasoner === 'error'" :size="16" />
              <Check v-else :size="16" />
              {{ saveStatus.reasoner === 'saving' ? '保存中...' : saveStatus.reasoner === 'saved' ? '已保存' : saveStatus.reasoner === 'error' ? (saveValidationErrors.reasoner || '保存失败') : '保存配置' }}
            </button>
          </div>
        </div>

        <!-- TTS 语音合成 -->
        <div v-if="activeTile === 'tts'" class="content-section">
          <div class="section-header">
            <div class="section-header-left">
              <div class="section-header-text">
                <h3 class="section-title">语音合成</h3>
                <span class="section-tag">TTS</span>
              </div>
            </div>
            <button
              :class="['info-btn', { active: showInfo.tts }]"
              @click="toggleInfo('tts')"
            >
              <Info :size="16" />
            </button>
          </div>
          <Transition name="info-expand">
            <div v-if="showInfo.tts" class="section-info-panel">
              <p>配置文字转语音服务，为 LuomiNest 赋予语音输出能力。支持 OpenAI 兼容的 TTS API。</p>
              <p class="info-tip">配置后，Agent 的回复将通过语音播报。支持多种语音风格选择。</p>
            </div>
          </Transition>

          <div class="config-form">
            <div class="form-group">
              <label class="form-label">供应商</label>
              <div class="form-select-wrap">
                <select v-model="ttsConfigForm.provider" class="form-select">
                  <option value="">请选择供应商</option>
                  <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">模型</label>
              <input v-model="ttsConfigForm.model" type="text" class="form-input" placeholder="tts-1" />
              <span class="form-hint">OpenAI: tts-1 / tts-1-hd | 其他: 参考供应商文档</span>
            </div>

            <div class="form-group">
              <label class="form-label">语音风格</label>
              <div class="voice-grid">
                <button
                  v-for="voice in modelStore.TTS_VOICES"
                  :key="voice"
                  :class="['voice-btn', { active: ttsConfigForm.voice === voice }]"
                  @click="ttsConfigForm.voice = voice"
                >
                  {{ voice }}
                </button>
              </div>
            </div>

            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">语速</label>
                <span class="form-value">{{ ttsConfigForm.speed.toFixed(1) }}x</span>
              </div>
              <input type="range" v-model.number="ttsConfigForm.speed" min="0.25" max="4.0" step="0.25" class="form-slider" />
              <div class="slider-labels"><span>慢速</span><span>快速</span></div>
            </div>

            <button
              :class="['save-btn', { saving: saveStatus.tts === 'saving', saved: saveStatus.tts === 'saved', error: saveStatus.tts === 'error' }]"
              :disabled="saveStatus.tts === 'saving'"
              @click="handleSaveTTSConfig"
            >
              <Loader2 v-if="saveStatus.tts === 'saving'" :size="16" class="spin-animation" />
              <Check v-else-if="saveStatus.tts === 'saved'" :size="16" />
              <AlertCircle v-else-if="saveStatus.tts === 'error'" :size="16" />
              <Check v-else :size="16" />
              {{ saveStatus.tts === 'saving' ? '保存中...' : saveStatus.tts === 'saved' ? '已保存' : saveStatus.tts === 'error' ? '保存失败' : '保存配置' }}
            </button>
          </div>
        </div>

        <!-- STT 语音识别 -->
        <div v-if="activeTile === 'stt'" class="content-section">
          <div class="section-header">
            <div class="section-header-left">
              <div class="section-header-text">
                <h3 class="section-title">语音识别</h3>
                <span class="section-tag">STT</span>
              </div>
            </div>
            <button
              :class="['info-btn', { active: showInfo.stt }]"
              @click="toggleInfo('stt')"
            >
              <Info :size="16" />
            </button>
          </div>
          <Transition name="info-expand">
            <div v-if="showInfo.stt" class="section-info-panel">
              <p>配置语音转文字服务，支持语音输入。可使用 OpenAI 兼容的 Whisper API 或浏览器原生语音识别。</p>
              <p class="info-tip">浏览器原生语音识别无需配置供应商，但识别精度有限。推荐使用 Whisper API 获得更好效果。</p>
            </div>
          </Transition>

          <div class="config-form">
            <div class="form-group">
              <label class="form-label">供应商</label>
              <div class="form-select-wrap">
                <select v-model="sttConfigForm.provider" class="form-select">
                  <option value="">请选择供应商</option>
                  <option value="__browser__">浏览器原生 (Web Speech API)</option>
                  <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>

            <div class="form-group" v-if="sttConfigForm.provider && sttConfigForm.provider !== '__browser__'">
              <label class="form-label">模型</label>
              <input v-model="sttConfigForm.model" type="text" class="form-input" placeholder="whisper-1" />
              <span class="form-hint">OpenAI: whisper-1 | 其他: 参考供应商文档</span>
            </div>

            <div class="form-group">
              <label class="form-label">识别语言</label>
              <div class="form-select-wrap">
                <select v-model="sttConfigForm.language" class="form-select">
                  <option v-for="lang in modelStore.STT_LANGUAGES" :key="lang.value" :value="lang.value">
                    {{ lang.label }}
                  </option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>

            <div class="form-group">
              <div class="toggle-row">
                <div>
                  <label class="form-label">自动发送</label>
                  <span class="form-hint" style="margin-top: 2px;">语音识别完成后自动发送消息</span>
                </div>
                <button
                  :class="['toggle-switch', { active: sttConfigForm.autoSend }]"
                  @click="sttConfigForm.autoSend = !sttConfigForm.autoSend"
                >
                  <span class="toggle-thumb" />
                </button>
              </div>
            </div>

            <div v-if="sttConfigForm.autoSend" class="form-group">
              <div class="form-label-row">
                <label class="form-label">发送延迟</label>
                <span class="form-value">{{ sttConfigForm.autoSendDelay }}ms</span>
              </div>
              <input type="range" v-model.number="sttConfigForm.autoSendDelay" min="500" max="5000" step="250" class="form-slider" />
              <div class="slider-labels"><span>0.5s</span><span>5s</span></div>
            </div>

            <button
              :class="['save-btn', { saving: saveStatus.stt === 'saving', saved: saveStatus.stt === 'saved', error: saveStatus.stt === 'error' }]"
              :disabled="saveStatus.stt === 'saving'"
              @click="handleSaveSTTConfig"
            >
              <Loader2 v-if="saveStatus.stt === 'saving'" :size="16" class="spin-animation" />
              <Check v-else-if="saveStatus.stt === 'saved'" :size="16" />
              <AlertCircle v-else-if="saveStatus.stt === 'error'" :size="16" />
              <Check v-else :size="16" />
              {{ saveStatus.stt === 'saving' ? '保存中...' : saveStatus.stt === 'saved' ? '已保存' : saveStatus.stt === 'error' ? '保存失败' : '保存配置' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Provider Dialog -->
    <Transition name="dialog-fade">
      <div v-if="showAddDialog" class="dialog-overlay" @click.self="shakeDialog('add')">
        <div :class="['dialog', 'add-dialog', { 'shake-animation': shakingDialog === 'add' }]">
          <div class="dialog-header">
            <div class="dialog-header-left">
              <div class="dialog-header-icon">
                <Plus :size="18" />
              </div>
              <h3>添加模型供应商</h3>
            </div>
            <button class="dialog-close" @click="showAddDialog = false">
              <X :size="18" />
            </button>
          </div>

          <div v-if="addProviderError" class="form-error-banner">
            <AlertCircle :size="16" />
            <span>{{ addProviderError }}</span>
          </div>

          <!-- Step 1: Select Template -->
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
                <div class="template-card-logo" :style="tmpl.svgIcon ? {} : { background: tmpl.color || '#6b7280' }">
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

          <!-- Step 2: Configure -->
          <div v-if="addDialogStep === 'configure'" class="add-step">
            <button class="back-to-select" @click="addDialogStep = 'select'">
              <ArrowLeft :size="14" />
              <span>返回选择模板</span>
            </button>

            <div v-if="selectedTemplate" class="selected-template-badge">
              <div class="template-card-logo small" :style="selectedTmpl?.svgIcon ? {} : { background: selectedTmpl?.color || '#6b7280' }">
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
                  <input v-model="newProvider.apiKey" :type="showApiKey.add ? 'text' : 'password'" class="form-input" :class="{ 'input-error': newProvider.vendor !== 'ollama' && !newProvider.apiKey.trim() && addProviderError }" placeholder="sk-..." />
                  <button class="eye-btn" @click="showApiKey.add = !showApiKey.add">
                    <Eye v-if="!showApiKey.add" :size="14" />
                    <EyeOff v-else :size="14" />
                  </button>
                </div>
                <span class="form-hint">Ollama 自动填充，其他供应商需填写真实密钥</span>
              </div>
              <div class="form-group">
                <label class="form-label">默认模型</label>
                <div class="form-select-wrap">
                  <select v-model="addModelSelect" class="form-select" @change="onAddModelSelectChange">
                    <option value="">请选择模型</option>
                    <option v-for="m in currentTemplateDefaultModels" :key="m" :value="m">{{ m }}</option>
                    <option value="__custom__">自定义模型...</option>
                  </select>
                  <ChevronRight :size="14" class="select-icon" />
                </div>
                <input v-if="addModelSelect === '__custom__'" v-model="newProvider.defaultModel" type="text" class="form-input" placeholder="输入自定义模型名称" style="margin-top: 8px;" />
                <span class="form-hint">添加后可点击搜索图标获取可用模型列表</span>
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

    <!-- Edit Provider Dialog -->
    <Transition name="dialog-fade">
      <div v-if="showEditDialog" class="dialog-overlay" @click.self="shakeDialog('edit')">
        <div :class="['dialog', { 'shake-animation': shakingDialog === 'edit' }]">
          <div class="dialog-header">
            <h3>编辑供应商 - {{ editProvider.name }}</h3>
            <button class="dialog-close" @click="showEditDialog = false">
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
            <label class="form-label">API 地址</label>
            <input v-model="editProvider.baseUrl" type="text" class="form-input" placeholder="API 地址" />
          </div>
          <div class="form-group">
            <label class="form-label">API Key</label>
            <input v-model="editProvider.apiKey" type="password" class="form-input" placeholder="留空则不修改" />
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
            <input v-if="editModelSelect === '__custom__'" v-model="editProvider.defaultModel" type="text" class="form-input" placeholder="输入自定义模型名称" style="margin-top: 8px;" />
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
            <button class="dialog-btn cancel" @click="showEditDialog = false">取消</button>
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
  </div>
</template>

<script lang="ts">
export default { name: 'AIModelSettings' }
</script>

<style scoped>
.ai-model-settings {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.settings-detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 28px;
  border-bottom: 1px solid var(--workspace-border);
  flex-shrink: 0;
}

.back-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all 250ms ease-in-out;
}

.back-btn:hover {
  background: var(--workspace-hover);
  color: var(--lumi-primary);
}

.header-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, rgba(20, 126, 188, 0.1), rgba(98, 169, 200, 0.06));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 1px;
}

.settings-detail-body {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.detail-sidebar {
  width: 200px;
  flex-shrink: 0;
  border-right: 1px solid var(--workspace-border);
  padding: 16px 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.tile-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tile-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  text-align: left;
  transition: all 250ms ease-in-out;
}

.tile-item:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.tile-item.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.tile-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.tile-label {
  font-weight: 600;
  font-size: 13px;
}

.tile-tag {
  font-size: 10px;
  font-weight: 500;
  opacity: 0.6;
  letter-spacing: 0.5px;
}

.sidebar-footer {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid var(--workspace-border);
}

.add-provider-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--lumi-primary);
  transition: all 250ms ease-in-out;
}

.add-provider-btn:hover {
  background: var(--lumi-primary-light);
}

.detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
  min-width: 0;
}

.content-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--workspace-border);
  transition: all 250ms ease-in-out;
}

.section-header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.section-header-text {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.section-tag {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted);
  letter-spacing: 0.5px;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--workspace-panel);
}

.info-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all 250ms ease-in-out;
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
  padding: 14px 20px;
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
  border: 1px solid var(--workspace-border);
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.section-info-panel p {
  margin-bottom: 6px;
}

.section-info-panel p:last-child {
  margin-bottom: 0;
}

.info-tip {
  color: var(--lumi-primary) !important;
  font-weight: 500;
  font-size: 12px !important;
}

.info-expand-enter-active {
  animation: info-expand-in 0.3s ease-in-out;
}

.info-expand-leave-active {
  animation: info-expand-in 0.2s ease-in-out reverse;
}

@keyframes info-expand-in {
  from {
    opacity: 0;
    max-height: 0;
    margin-top: -8px;
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
  gap: 18px;
  max-width: 560px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 2px;
}

.required-mark {
  color: var(--lumi-accent);
  font-weight: 700;
  margin-left: 2px;
}

.form-hint {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: -4px;
}

.hint-warn {
  color: #f59e0b;
}

.hint-error {
  color: var(--lumi-accent);
  font-weight: 500;
}

.select-error {
  border-color: var(--lumi-accent) !important;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1) !important;
}

.fetch-models-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fetch-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 500;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  transition: all 250ms ease-in-out;
}

.fetch-btn:hover {
  background: var(--lumi-primary);
  color: white;
}

.form-error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
  font-size: 13px;
  font-weight: 500;
}

.form-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.form-value {
  font-size: 13px;
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
  padding: 10px 36px 10px 14px;
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
  appearance: none;
  transition: all 250ms ease-in-out;
}

.form-select:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.select-icon {
  position: absolute;
  right: 12px;
  color: var(--text-muted);
  pointer-events: none;
  transform: rotate(90deg);
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-primary);
  transition: all 250ms ease-in-out;
}

.form-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.form-input::placeholder {
  color: var(--text-muted);
}

.form-slider {
  width: 100%;
  height: 6px;
  appearance: none;
  background: var(--workspace-border);
  border-radius: 3px;
  outline: none;
  cursor: pointer;
}

.form-slider::-webkit-slider-thumb {
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--lumi-primary);
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(20, 126, 188, 0.3);
  transition: transform 250ms ease-in-out;
}

.form-slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toggle-switch {
  width: 44px;
  height: 24px;
  border-radius: 12px;
  background: var(--workspace-border);
  position: relative;
  cursor: pointer;
  transition: background 250ms ease-in-out;
  flex-shrink: 0;
}

.toggle-switch.active {
  background: var(--lumi-primary);
}

.toggle-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: white;
  transition: transform 250ms ease-in-out;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.toggle-switch.active .toggle-thumb {
  transform: translateX(20px);
}

.effort-group {
  display: flex;
  gap: 8px;
}

.effort-btn {
  flex: 1;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all 250ms ease-in-out;
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

.voice-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.voice-btn {
  padding: 8px 12px;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all 250ms ease-in-out;
  text-align: center;
  text-transform: capitalize;
}

.voice-btn:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.voice-btn.active {
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  font-weight: 600;
}

.provider-section {
  margin-top: 8px;
  border-top: 1px solid var(--workspace-border);
  padding-top: 16px;
}

.provider-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 250ms ease-in-out;
}

.provider-section-header:hover {
  background: var(--workspace-hover);
}

.provider-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.provider-count {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: var(--radius-full);
  background: var(--workspace-panel);
  color: var(--text-muted);
  font-weight: 500;
}

.chevron-toggle {
  color: var(--text-muted);
  transition: transform 250ms ease-in-out;
}

.chevron-toggle.expanded {
  transform: rotate(90deg);
}

.provider-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 8px;
}

.provider-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all 250ms ease-in-out;
}

.provider-item:hover {
  border-color: var(--lumi-primary);
  box-shadow: 0 1px 4px var(--lumi-primary-glow);
}

.provider-item-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  flex: 1;
}

.provider-item-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.provider-item-icon {
  color: var(--lumi-primary);
  flex-shrink: 0;
}

.provider-item-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.default-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background: var(--lumi-primary);
  color: white;
  font-weight: 500;
}

.provider-item-detail {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-muted);
  padding-left: 20px;
}

.detail-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-sep {
  opacity: 0.3;
}

.provider-item-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.action-btn {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all 250ms ease-in-out;
}

.action-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.action-btn.danger:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.empty-provider {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px;
  color: var(--text-muted);
  font-size: 13px;
}

.add-inline-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 500;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  transition: all 250ms ease-in-out;
}

.add-inline-btn:hover {
  background: var(--lumi-primary);
  color: white;
}

.template-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.add-dialog {
  width: 560px;
  max-height: 85vh;
}

.dialog-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dialog-header-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(20, 126, 188, 0.12), rgba(20, 126, 188, 0.04));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
}

.add-step {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step-hint {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}

.category-tabs {
  display: flex;
  gap: 6px;
}

.category-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all 250ms ease-in-out;
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
  gap: 6px;
  max-height: 380px;
  overflow-y: auto;
  padding-right: 4px;
}

.template-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all 250ms ease-in-out;
  cursor: pointer;
  text-align: left;
  width: 100%;
}

.template-card:hover {
  border-color: var(--lumi-primary);
  box-shadow: 0 1px 4px var(--lumi-primary-glow);
  transform: translateX(2px);
}

.template-card-logo {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.template-card-logo.small {
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
}

.template-initials {
  font-size: 11px;
  font-weight: 700;
  color: white;
  letter-spacing: 0.5px;
}

.template-card-logo.small .template-initials {
  font-size: 9px;
}

.template-card-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.template-card-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.template-card-desc {
  font-size: 11px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-card-arrow {
  color: var(--text-muted);
  flex-shrink: 0;
  transition: transform 250ms ease-in-out;
}

.template-card:hover .template-card-arrow {
  color: var(--lumi-primary);
  transform: translateX(2px);
}

.back-to-select {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  transition: all 250ms ease-in-out;
  align-self: flex-start;
}

.back-to-select:hover {
  background: var(--workspace-hover);
  color: var(--lumi-primary);
}

.selected-template-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: var(--radius-md);
  background: var(--lumi-primary-light);
  border: 1px solid var(--lumi-primary);
}

.selected-template-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--lumi-primary);
}

.config-form-compact {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.api-key-row {
  display: flex;
  gap: 6px;
  align-items: center;
}

.api-key-row .form-input {
  flex: 1;
}

.eye-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  flex-shrink: 0;
  transition: all 250ms ease-in-out;
}

.eye-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  backdrop-filter: blur(4px);
}

.dialog {
  background: var(--workspace-card);
  border-radius: var(--radius-xl);
  padding: 24px;
  width: 480px;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.dialog-header h3 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.dialog-close {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all 250ms ease-in-out;
}

.dialog-close:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.dialog-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 20px;
}

.dialog-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 250ms ease-in-out;
}

.dialog-btn.cancel {
  color: var(--text-muted);
  background: var(--workspace-panel);
}

.dialog-btn.cancel:hover {
  background: var(--workspace-hover);
}

.dialog-btn.confirm {
  color: white;
  background: var(--lumi-primary);
}

.dialog-btn.confirm:hover {
  background: var(--lumi-primary-hover);
}

.dialog-btn.confirm.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.save-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 24px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 600;
  color: white;
  background: var(--lumi-primary);
  cursor: pointer;
  transition: all 250ms ease-in-out;
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
  background: #10b981;
}

.save-btn.error {
  background: var(--lumi-accent);
}

.spin-animation {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.dialog-fade-enter-active {
  animation: dialog-in 0.3s ease-in-out;
}

.dialog-fade-leave-active {
  animation: dialog-in 0.2s ease-in-out reverse;
}

@keyframes dialog-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.expand-enter-active {
  animation: expand-in 0.3s ease-in-out;
}

.expand-leave-active {
  animation: expand-in 0.2s ease-in-out reverse;
}

@keyframes expand-in {
  from {
    opacity: 0;
    max-height: 0;
  }
  to {
    opacity: 1;
    max-height: 600px;
  }
}

.template-svg-icon {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.template-svg-icon :deep(svg) {
  width: 22px;
  height: 22px;
}
.template-svg-icon.small {
  width: 18px;
  height: 18px;
}
.template-svg-icon.small :deep(svg) {
  width: 16px;
  height: 16px;
}

.provider-svg-icon {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.provider-svg-icon :deep(svg) {
  width: 16px;
  height: 16px;
}

.input-error {
  border-color: var(--lumi-accent) !important;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1) !important;
}

@keyframes dialog-shake {
  0%, 100% { transform: scale(1); }
  20% { transform: scale(1.02); }
  40% { transform: scale(0.98); }
  60% { transform: scale(1.01); }
  80% { transform: scale(0.99); }
}

.shake-animation {
  animation: dialog-shake 0.4s ease-in-out;
}
</style>
