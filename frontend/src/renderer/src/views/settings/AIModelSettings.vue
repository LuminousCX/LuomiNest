<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  Cloud,
  Cpu,
  Gauge,
  Atom,
  Camera,
  Pencil,
  Mic,
  Volume2,
  Plus,
  ChevronRight,
  Copy,
  Key,
  Search,
  Trash2,
  Eye,
  EyeOff,
  Bot,
  Check,
  AlertCircle,
  Loader2,
  Server,
  Edit3
} from 'lucide-vue-next'
import { useModelStore } from '../../stores/model'
import type { ProviderTemplate } from '../../types'

const router = useRouter()
const modelStore = useModelStore()

const activeTile = ref('service')

const modelTiles = [
  { id: 'service', label: '模型服务', icon: Cloud },
  { id: 'main', label: '主模型', icon: Cpu },
  { id: 'fast', label: '快速模型', icon: Gauge },
  { id: 'reasoner', label: '推理模型', icon: Atom },
  { id: 'vision', label: '视觉模型', icon: Camera },
  { id: 'text2img', label: '文生图', icon: Pencil },
  { id: 'asr', label: '语音识别', icon: Mic },
  { id: 'tts', label: '语音合成', icon: Volume2 }
]

const providers = computed(() => modelStore.providers)

const showApiKey = ref<Record<string, boolean>>({})
const toggleApiKeyVisibility = (id: string) => { showApiKey.value[id] = !showApiKey.value[id] }

const showAddDialog = ref(false)
const addProviderError = ref('')
const addProviderLoading = ref(false)
const selectedTemplate = ref<string>('')
const newProvider = ref({
  id: '',
  name: '',
  vendor: 'openai_compatible',
  baseUrl: '',
  apiKey: '',
  defaultModel: '',
  isDefault: false
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
  isDefault: false
})

const handleTemplateSelect = (templateId: string) => {
  selectedTemplate.value = templateId
  const tmpl = modelStore.templates.find(t => t.id === templateId)
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
}

const handleVendorChange = () => {
  if (newProvider.value.vendor === 'ollama') {
    newProvider.value.baseUrl = 'http://localhost:11434/v1'
    newProvider.value.apiKey = 'ollama'
    newProvider.value.defaultModel = 'qwen2.5:7b'
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
  maxRounds: 20,
  reasoningEffort: 'medium'
})

const fastModelConfig = ref({
  selectedProvider: '',
  model: '',
  temperature: 0.5,
  topP: 0.9,
  maxTokens: 2048
})

const reasonerModelConfig = ref({
  selectedProvider: '',
  model: '',
  temperature: 0.3,
  maxTokens: 8192,
  stopWords: ''
})

const visionModelConfig = ref({
  selectedProvider: '',
  model: '',
  temperature: 0.5,
  enableDesktopVision: false,
  wakeWord: ''
})

const currentTileLabel = computed(() => {
  const tile = modelTiles.find(t => t.id === activeTile.value)
  return tile?.label ?? ''
})

const getModelsForProvider = (providerId: string) => {
  return modelStore.getProviderModels(providerId)
}

const mainAvailableModels = computed(() => {
  return getModelsForProvider(mainModelConfig.value.selectedProvider)
})

const fastAvailableModels = computed(() => {
  return getModelsForProvider(fastModelConfig.value.selectedProvider)
})

const reasonerAvailableModels = computed(() => {
  return getModelsForProvider(reasonerModelConfig.value.selectedProvider)
})

const visionAvailableModels = computed(() => {
  return getModelsForProvider(visionModelConfig.value.selectedProvider)
})

const newProviderFormValid = computed(() => {
  return newProvider.value.id.trim() !== '' && newProvider.value.baseUrl.trim() !== ''
})

const editProviderFormValid = computed(() => {
  return editProvider.value.name.trim() !== '' && editProvider.value.baseUrl.trim() !== ''
})

const openAddDialog = () => {
  selectedTemplate.value = ''
  newProvider.value = { id: '', name: '', vendor: 'openai_compatible', baseUrl: '', apiKey: '', defaultModel: '', isDefault: false }
  addProviderError.value = ''
  showAddDialog.value = true
}

const handleAddProvider = async () => {
  if (!newProviderFormValid.value) {
    addProviderError.value = '请填写必填项（标识 ID 和 API 地址）'
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
  } catch (e: any) {
    addProviderError.value = e.message || '添加失败'
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
  editProviderError.value = ''
  showEditDialog.value = true
}

const handleEditProvider = async () => {
  if (!editProviderFormValid.value) {
    editProviderError.value = '请填写必填项'
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
  } catch (e: any) {
    editProviderError.value = e.message || '更新失败'
  } finally {
    editProviderLoading.value = false
  }
}

const handleRemoveProvider = async (providerId: string) => {
  try {
    await modelStore.removeProvider(providerId)
  } catch (e: any) {
    console.error('Failed to remove provider:', e)
  }
}

const handleFetchModels = async (providerId: string) => {
  try {
    await modelStore.fetchProviderModels(providerId)
  } catch (e: any) {
    console.error('Failed to fetch models:', e)
  }
}

const handleCopy = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
  } catch {}
}

const handleSaveConfig = async (configType: string) => {
  let config: any = {}
  if (configType === 'main') {
    config = {
      defaultProvider: mainModelConfig.value.selectedProvider,
      defaultModel: mainModelConfig.value.model,
      defaultTemperature: mainModelConfig.value.temperature,
      defaultMaxTokens: mainModelConfig.value.maxTokens,
      defaultTopP: mainModelConfig.value.topP,
    }
  } else if (configType === 'fast') {
    config = {
      fastProvider: fastModelConfig.value.selectedProvider,
      fastModel: fastModelConfig.value.model,
      fastTemperature: fastModelConfig.value.temperature,
      fastMaxTokens: fastModelConfig.value.maxTokens,
    }
  } else if (configType === 'reasoner') {
    config = {
      reasonerProvider: reasonerModelConfig.value.selectedProvider,
      reasonerModel: reasonerModelConfig.value.model,
      reasonerTemperature: reasonerModelConfig.value.temperature,
      reasonerMaxTokens: reasonerModelConfig.value.maxTokens,
    }
  } else if (configType === 'vision') {
    config = {
      visionProvider: visionModelConfig.value.selectedProvider,
      visionModel: visionModelConfig.value.model,
      visionTemperature: visionModelConfig.value.temperature,
    }
  }
  await modelStore.updateModelConfig(config)
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
  if (cfg.fastProvider) {
    fastModelConfig.value.selectedProvider = cfg.fastProvider
    fastModelConfig.value.model = cfg.fastModel || ''
    fastModelConfig.value.temperature = cfg.fastTemperature || 0.5
    fastModelConfig.value.maxTokens = cfg.fastMaxTokens || 2048
  }
  if (cfg.reasonerProvider) {
    reasonerModelConfig.value.selectedProvider = cfg.reasonerProvider
    reasonerModelConfig.value.model = cfg.reasonerModel || ''
    reasonerModelConfig.value.temperature = cfg.reasonerTemperature || 0.3
    reasonerModelConfig.value.maxTokens = cfg.reasonerMaxTokens || 8192
  }
  if (cfg.visionProvider) {
    visionModelConfig.value.selectedProvider = cfg.visionProvider
    visionModelConfig.value.model = cfg.visionModel || ''
    visionModelConfig.value.temperature = cfg.visionTemperature || 0.5
  }
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
        <p class="page-subtitle">配置 LuomiNest 大语言模型推理引擎与参数</p>
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
            <span>{{ tile.label }}</span>
          </button>
        </nav>
      </div>

      <div class="detail-content animate-slide-up" :style="{ animationDelay: '100ms' }">
        <!-- 模型服务 -->
        <div v-if="activeTile === 'service'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">MODELS</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Bot :size="24" />
              </div>
              <div class="banner-text">
                <h3>模型服务配置</h3>
                <p>
                  1. 所有配置均保存在本地，不会上传至任何服务器<br>
                  2. 添加供应商后，点击搜索图标获取可用模型列表<br>
                  3. 支持所有兼容 OpenAI API 格式的供应商
                </p>
              </div>
            </div>
          </div>

          <div class="provider-grid">
            <div
              v-for="provider in providers"
              :key="provider.id"
              class="provider-card"
            >
              <div class="card-header">
                <div class="vendor-badge">
                  <Server :size="18" />
                  <span class="vendor-name">{{ provider.name }}</span>
                  <span v-if="provider.isDefault" class="default-badge">默认</span>
                </div>
                <div class="card-actions">
                  <button class="action-btn" title="获取模型列表" @click="handleFetchModels(provider.id)">
                    <Search :size="14" />
                  </button>
                  <button class="action-btn" title="编辑" @click="openEditDialog(provider.id)">
                    <Edit3 :size="14" />
                  </button>
                  <button class="action-btn danger" title="删除" @click="handleRemoveProvider(provider.id)">
                    <Trash2 :size="14" />
                  </button>
                </div>
              </div>

              <div class="card-fields">
                <div class="field-item">
                  <label>API 地址</label>
                  <div class="field-input-wrap">
                    <input type="text" :value="provider.baseUrl" class="field-input" readonly />
                    <button class="field-action" title="复制" @click="handleCopy(provider.baseUrl)">
                      <Copy :size="13" />
                    </button>
                  </div>
                </div>
                <div class="field-item">
                  <label>API Key</label>
                  <div class="field-input-wrap">
                    <input
                      :type="showApiKey[provider.id] ? 'text' : 'password'"
                      :value="provider.apiKeySet ? 'sk-****...****' : '未设置'"
                      class="field-input"
                      readonly
                    />
                    <button
                      class="field-action"
                      title="显示/隐藏"
                      @click="toggleApiKeyVisibility(provider.id)"
                    >
                      <Eye v-if="!showApiKey[provider.id]" :size="13" />
                      <EyeOff v-else :size="13" />
                    </button>
                  </div>
                </div>
                <div class="field-item">
                  <label>默认模型</label>
                  <div class="field-input-wrap">
                    <input type="text" :value="provider.defaultModel" class="field-input" readonly />
                    <ChevronRight :size="14" class="field-select-icon" />
                  </div>
                </div>
                <div v-if="provider.models.length > 0" class="field-item">
                  <label>可用模型 ({{ provider.models.length }})</label>
                  <div class="model-list">
                    <span v-for="m in provider.models.slice(0, 5)" :key="m.id" class="model-tag">{{ m.name }}</span>
                    <span v-if="provider.models.length > 5" class="model-tag more">+{{ provider.models.length - 5 }}</span>
                  </div>
                </div>
              </div>
            </div>

            <button class="provider-card add-card" @click="openAddDialog">
              <Plus :size="32" />
              <span>添加供应商</span>
            </button>
          </div>

          <!-- Add Dialog -->
          <Transition name="selection-fade">
            <div v-if="showAddDialog" class="add-dialog-overlay" @click.self="showAddDialog = false">
              <div class="add-dialog">
                <h3>添加模型供应商</h3>

                <div v-if="addProviderError" class="form-error-banner">
                  <AlertCircle :size="16" />
                  <span>{{ addProviderError }}</span>
                </div>

                <div class="form-group">
                  <label class="form-label">选择模板</label>
                  <div class="template-grid">
                    <button
                      v-for="tmpl in modelStore.templates"
                      :key="tmpl.id"
                      :class="['template-chip', { active: selectedTemplate === tmpl.id }]"
                      @click="handleTemplateSelect(tmpl.id)"
                    >
                      {{ tmpl.name }}
                    </button>
                  </div>
                </div>

                <div class="form-group">
                  <label class="form-label">
                    标识 ID
                    <span class="required-mark">*</span>
                  </label>
                  <input v-model="newProvider.id" type="text" class="form-input" placeholder="如: my-ollama" />
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
                    </select>
                    <ChevronRight :size="14" class="select-icon" />
                  </div>
                </div>
                <div class="form-group">
                  <label class="form-label">
                    API 地址
                    <span class="required-mark">*</span>
                  </label>
                  <input v-model="newProvider.baseUrl" type="text" class="form-input" placeholder="http://localhost:11434/v1" />
                  <span class="form-hint">Ollama: http://localhost:11434/v1 | 其他: 含 /v1 后缀</span>
                </div>
                <div class="form-group">
                  <label class="form-label">API Key</label>
                  <input v-model="newProvider.apiKey" type="password" class="form-input" placeholder="sk-..." />
                  <span class="form-hint">Ollama 自动填充，其他供应商需填写真实密钥</span>
                </div>
                <div class="form-group">
                  <label class="form-label">默认模型</label>
                  <input v-model="newProvider.defaultModel" type="text" class="form-input" placeholder="如: qwen2.5:7b" />
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
                <div class="dialog-actions">
                  <button class="dialog-btn cancel" @click="showAddDialog = false">取消</button>
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
          </Transition>

          <!-- Edit Dialog -->
          <Transition name="selection-fade">
            <div v-if="showEditDialog" class="add-dialog-overlay" @click.self="showEditDialog = false">
              <div class="add-dialog">
                <h3>编辑供应商 - {{ editProvider.name }}</h3>

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
                  <input v-model="editProvider.defaultModel" type="text" class="form-input" placeholder="默认模型" />
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

        <!-- 主模型 -->
        <div v-if="activeTile === 'main'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">MAIN</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Cpu :size="24" />
              </div>
              <div class="banner-text">
                <h3>主模型配置</h3>
                <p>主模型用于日常对话与复杂任务处理，首次使用请先前往模型服务添加供应商</p>
              </div>
            </div>
          </div>

          <div class="config-form">
            <div class="form-group">
              <label class="form-label">
                供应商
                <span class="required-mark">*</span>
              </label>
              <div class="form-select-wrap">
                <select v-model="mainModelConfig.selectedProvider" class="form-select">
                  <option value="">请选择供应商</option>
                  <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
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
              <span v-if="mainModelConfig.selectedProvider && mainAvailableModels.length === 0" class="form-hint">
                暂无模型列表，请前往模型服务点击搜索图标获取
              </span>
            </div>

            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Temperature</label>
                <span class="form-value">{{ mainModelConfig.temperature }}</span>
              </div>
              <input
                type="range"
                v-model.number="mainModelConfig.temperature"
                min="0"
                max="2"
                step="0.1"
                class="form-slider"
              />
              <div class="slider-labels">
                <span>精确</span>
                <span>创意</span>
              </div>
            </div>

            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Top P</label>
                <span class="form-value">{{ mainModelConfig.topP }}</span>
              </div>
              <input
                type="range"
                v-model.number="mainModelConfig.topP"
                min="0"
                max="1"
                step="0.05"
                class="form-slider"
              />
            </div>

            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Max Tokens</label>
                <span class="form-value">{{ mainModelConfig.maxTokens }}</span>
              </div>
              <input
                type="range"
                v-model.number="mainModelConfig.maxTokens"
                min="256"
                max="16384"
                step="256"
                class="form-slider"
              />
            </div>

            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">最大对话轮数</label>
                <span class="form-value">{{ mainModelConfig.maxRounds }}</span>
              </div>
              <input
                type="range"
                v-model.number="mainModelConfig.maxRounds"
                min="5"
                max="50"
                step="5"
                class="form-slider"
              />
            </div>

            <div class="form-group">
              <label class="form-label">推理强度</label>
              <div class="form-select-wrap">
                <select v-model="mainModelConfig.reasoningEffort" class="form-select">
                  <option value="low">低</option>
                  <option value="medium">中</option>
                  <option value="high">高</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>

            <button
              :class="['save-btn', { saving: modelStore.saveStatus === 'saving', saved: modelStore.saveStatus === 'saved', error: modelStore.saveStatus === 'error' }]"
              :disabled="modelStore.saveStatus === 'saving'"
              @click="handleSaveConfig('main')"
            >
              <Loader2 v-if="modelStore.saveStatus === 'saving'" :size="16" class="spin-animation" />
              <Check v-else-if="modelStore.saveStatus === 'saved'" :size="16" />
              <AlertCircle v-else-if="modelStore.saveStatus === 'error'" :size="16" />
              <Check v-else :size="16" />
              {{ modelStore.saveStatus === 'saving' ? '保存中...' : modelStore.saveStatus === 'saved' ? '已保存' : modelStore.saveStatus === 'error' ? '保存失败' : '保存配置' }}
            </button>
          </div>
        </div>

        <!-- 快速模型 -->
        <div v-if="activeTile === 'fast'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">FAST</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Gauge :size="24" />
              </div>
              <div class="banner-text">
                <h3>快速模型配置</h3>
                <p>快速模型用于简单问答、分类判断等低延迟场景，优先选择响应速度快的轻量模型</p>
              </div>
            </div>
          </div>

          <div class="config-form">
            <div class="form-group">
              <label class="form-label">供应商</label>
              <div class="form-select-wrap">
                <select v-model="fastModelConfig.selectedProvider" class="form-select">
                  <option value="">请选择供应商</option>
                  <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">模型</label>
              <div class="form-select-wrap">
                <select v-model="fastModelConfig.model" class="form-select">
                  <option value="">请选择模型</option>
                  <option v-for="m in fastAvailableModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Temperature</label>
                <span class="form-value">{{ fastModelConfig.temperature }}</span>
              </div>
              <input
                type="range"
                v-model.number="fastModelConfig.temperature"
                min="0"
                max="2"
                step="0.1"
                class="form-slider"
              />
            </div>
            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Max Tokens</label>
                <span class="form-value">{{ fastModelConfig.maxTokens }}</span>
              </div>
              <input
                type="range"
                v-model.number="fastModelConfig.maxTokens"
                min="256"
                max="8192"
                step="256"
                class="form-slider"
              />
            </div>

            <button
              :class="['save-btn', { saving: modelStore.saveStatus === 'saving', saved: modelStore.saveStatus === 'saved', error: modelStore.saveStatus === 'error' }]"
              :disabled="modelStore.saveStatus === 'saving'"
              @click="handleSaveConfig('fast')"
            >
              <Check :size="16" />
              保存配置
            </button>
          </div>
        </div>

        <!-- 推理模型 -->
        <div v-if="activeTile === 'reasoner'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">REASONER</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Atom :size="24" />
              </div>
              <div class="banner-text">
                <h3>推理模型配置</h3>
                <p>推理模型用于复杂逻辑推理、数学计算、代码分析等需要深度思考的场景</p>
              </div>
            </div>
          </div>

          <div class="config-form">
            <div class="form-group">
              <label class="form-label">供应商</label>
              <div class="form-select-wrap">
                <select v-model="reasonerModelConfig.selectedProvider" class="form-select">
                  <option value="">请选择供应商</option>
                  <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
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
            </div>
            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Temperature</label>
                <span class="form-value">{{ reasonerModelConfig.temperature }}</span>
              </div>
              <input
                type="range"
                v-model.number="reasonerModelConfig.temperature"
                min="0"
                max="2"
                step="0.1"
                class="form-slider"
              />
            </div>
            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Max Tokens</label>
                <span class="form-value">{{ reasonerModelConfig.maxTokens }}</span>
              </div>
              <input
                type="range"
                v-model.number="reasonerModelConfig.maxTokens"
                min="1024"
                max="32768"
                step="1024"
                class="form-slider"
              />
            </div>
            <div class="form-group">
              <label class="form-label">停止词</label>
              <input
                type="text"
                v-model="reasonerModelConfig.stopWords"
                class="form-input"
                placeholder="用逗号分隔多个停止词"
              />
            </div>

            <button
              :class="['save-btn', { saving: modelStore.saveStatus === 'saving', saved: modelStore.saveStatus === 'saved', error: modelStore.saveStatus === 'error' }]"
              :disabled="modelStore.saveStatus === 'saving'"
              @click="handleSaveConfig('reasoner')"
            >
              <Check :size="16" />
              保存配置
            </button>
          </div>
        </div>

        <!-- 视觉模型 -->
        <div v-if="activeTile === 'vision'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">VISION</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Camera :size="24" />
              </div>
              <div class="banner-text">
                <h3>视觉模型配置</h3>
                <p>视觉模型用于图像理解、屏幕截图分析等需要多模态能力的场景</p>
              </div>
            </div>
          </div>

          <div class="config-form">
            <div class="form-group">
              <label class="form-label">供应商</label>
              <div class="form-select-wrap">
                <select v-model="visionModelConfig.selectedProvider" class="form-select">
                  <option value="">请选择供应商</option>
                  <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">模型</label>
              <div class="form-select-wrap">
                <select v-model="visionModelConfig.model" class="form-select">
                  <option value="">请选择模型</option>
                  <option v-for="m in visionAvailableModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Temperature</label>
                <span class="form-value">{{ visionModelConfig.temperature }}</span>
              </div>
              <input
                type="range"
                v-model.number="visionModelConfig.temperature"
                min="0"
                max="2"
                step="0.1"
                class="form-slider"
              />
            </div>
            <div class="form-group">
              <div class="toggle-row">
                <label class="form-label">桌面视觉</label>
                <button
                  :class="['toggle-switch', { active: visionModelConfig.enableDesktopVision }]"
                  @click="visionModelConfig.enableDesktopVision = !visionModelConfig.enableDesktopVision"
                >
                  <span class="toggle-thumb" />
                </button>
              </div>
              <p class="form-hint">启用后 Agent 可截取屏幕内容进行分析</p>
            </div>
            <div class="form-group">
              <label class="form-label">唤醒词</label>
              <input
                type="text"
                v-model="visionModelConfig.wakeWord"
                class="form-input"
                placeholder="输入唤醒词触发视觉分析"
              />
            </div>

            <button
              :class="['save-btn', { saving: modelStore.saveStatus === 'saving', saved: modelStore.saveStatus === 'saved', error: modelStore.saveStatus === 'error' }]"
              :disabled="modelStore.saveStatus === 'saving'"
              @click="handleSaveConfig('vision')"
            >
              <Check :size="16" />
              保存配置
            </button>
          </div>
        </div>

        <!-- 文生图 -->
        <div v-if="activeTile === 'text2img'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">IMAGE</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Pencil :size="24" />
              </div>
              <div class="banner-text">
                <h3>文生图模型配置</h3>
                <p>配置图像生成模型，支持 DALL-E、Stable Diffusion 等文生图服务（即将支持）</p>
              </div>
            </div>
          </div>

          <div class="coming-soon-placeholder">
            <Pencil :size="32" />
            <p>该功能即将上线，敬请期待</p>
          </div>
        </div>

        <!-- 语音识别 -->
        <div v-if="activeTile === 'asr'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">ASR</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Mic :size="24" />
              </div>
              <div class="banner-text">
                <h3>语音识别模型配置</h3>
                <p>配置语音转文字服务，支持 Whisper 等语音识别模型（即将支持）</p>
              </div>
            </div>
          </div>

          <div class="coming-soon-placeholder">
            <Mic :size="32" />
            <p>该功能即将上线，敬请期待</p>
          </div>
        </div>

        <!-- 语音合成 -->
        <div v-if="activeTile === 'tts'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">TTS</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Volume2 :size="24" />
              </div>
              <div class="banner-text">
                <h3>语音合成模型配置</h3>
                <p>配置文字转语音服务，为 Agent 赋予语音输出能力（即将支持）</p>
              </div>
            </div>
          </div>

          <div class="coming-soon-placeholder">
            <Volume2 :size="32" />
            <p>该功能即将上线，敬请期待</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

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
  transition: all var(--transition-fast);
}

.back-btn:hover {
  background: var(--workspace-hover);
  color: var(--lumi-primary);
}

.header-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, rgba(13, 148, 136, 0.1), rgba(20, 184, 166, 0.1));
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
  width: 180px;
  flex-shrink: 0;
  border-right: 1px solid var(--workspace-border);
  padding: 16px 12px;
  overflow-y: auto;
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
  transition: all var(--transition-fast);
}

.tile-item:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.tile-item.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
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
  gap: 24px;
}

.section-banner {
  display: flex;
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: linear-gradient(135deg, var(--lumi-primary), #14b8a6);
  color: white;
  min-height: 100px;
}

.banner-accent {
  width: 48px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  background: rgba(0, 0, 0, 0.15);
  padding: 12px 0;
}

.banner-body {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  flex: 1;
}

.banner-icon-box {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.banner-text h3 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}

.banner-text p {
  font-size: 12px;
  opacity: 0.9;
  line-height: 1.6;
}

.provider-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.provider-card {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  transition: all var(--transition-fast);
}

.provider-card:hover {
  border-color: var(--lumi-primary);
  box-shadow: 0 2px 12px var(--lumi-primary-glow);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.vendor-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  font-size: 13px;
  font-weight: 600;
}

.card-actions {
  display: flex;
  gap: 4px;
}

.action-btn {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.action-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.action-btn.danger:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.card-fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-item label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.field-input-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-sm);
  padding: 0 10px;
  transition: all var(--transition-fast);
}

.field-input-wrap:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.field-input {
  flex: 1;
  padding: 8px 0;
  font-size: 13px;
  color: var(--text-primary);
  background: transparent;
}

.field-action {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.field-action:hover {
  background: var(--workspace-hover);
  color: var(--lumi-primary);
}

.field-select-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.add-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 200px;
  border: 2px dashed var(--workspace-border);
  border-radius: var(--radius-lg);
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.add-card:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.template-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.template-chip {
  padding: 6px 12px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-fast);
  cursor: pointer;
}

.template-chip:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.template-chip.active {
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  font-weight: 600;
}

.config-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
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
  transition: all var(--transition-fast);
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
  transition: all var(--transition-fast);
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
  box-shadow: 0 2px 6px rgba(13, 148, 136, 0.3);
  transition: transform var(--transition-fast);
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
  transition: background var(--transition-fast);
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
  transition: transform var(--transition-fast);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.toggle-switch.active .toggle-thumb {
  transform: translateX(20px);
}

.default-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background: var(--lumi-primary);
  color: white;
  font-weight: 500;
}

.model-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.model-tag {
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 11px;
  background: var(--workspace-panel);
  color: var(--text-secondary);
  border: 1px solid var(--workspace-border);
}

.model-tag.more {
  color: var(--lumi-primary);
  border-color: var(--lumi-primary);
}

.add-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.add-dialog {
  background: var(--workspace-card);
  border-radius: var(--radius-xl);
  padding: 28px;
  width: 480px;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.add-dialog h3 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 20px;
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
  transition: all var(--transition-fast);
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
  transition: all var(--transition-fast);
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

.coming-soon-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--text-muted);
  gap: 12px;
}

.coming-soon-placeholder p {
  font-size: 14px;
  font-weight: 500;
}

.spin-animation {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.selection-fade-enter-active {
  animation: lumi-fade-in 0.3s ease-out;
}

.selection-fade-leave-active {
  animation: lumi-fade-in 0.2s ease-out reverse;
}
</style>
