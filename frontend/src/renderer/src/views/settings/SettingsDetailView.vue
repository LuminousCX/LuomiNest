<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  Palette,
  Bell,
  Shield,
  Globe,
  Settings,
  Sun,
  Moon,
  Volume2,
  Cpu,
  Check,
  AlertCircle,
  Loader2,
  Wifi,
  WifiOff,
  Plus,
  RefreshCw,
  Play,
  Square,
  Trash2,
  Edit3,
  Image as ImageIcon,
  MessageCircle,
  Send,
  Gamepad2,
  Radio,
  Cable,
  Link,
  Home,
  Smartphone,
  X,
  Server,
  Zap,
  Brain,
  Save
} from 'lucide-vue-next'
import { useThemeStore } from '../../stores/theme'
import { usePlatformStore } from '../../stores/platform'
import { useModelStore } from '../../stores/model'
import { API_ENDPOINTS } from '../../config/api'
import type { PlatformAdapterType, PlatformInstance } from '../../types'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const platformStore = usePlatformStore()
const modelStore = useModelStore()

const section = computed(() => route.params.section as string)

interface TtsEngineInfo {
  id: string
  name: string
  online: boolean
  available: boolean
  default_voices?: Record<string, string>
  voices?: Array<{ id: string; name: string; lang: string }>
  lang_map?: Record<string, string>
}

interface TtsDeviceInfo {
  type: string
  name: string
  cuda_available: boolean
  cuda_version?: string
}

interface TtsBindingInfo {
  model_id: string
  voice: string
  voice_lang: string
  default_expression: string
}

const ttsLoading = ref(false)
const ttsError = ref<string | null>(null)
const ttsEngines = ref<TtsEngineInfo[]>([])
const ttsDevice = ref<TtsDeviceInfo | null>(null)
const ttsBindings = ref<Record<string, TtsBindingInfo>>({})

const fetchTtsInfo = async () => {
  ttsLoading.value = true
  ttsError.value = null
  try {
    const resp = await fetch(`${API_ENDPOINTS.V1}/chat/tts/engines`)
    if (!resp.ok) {
      throw new Error(`请求失败 (${resp.status})`)
    }
    const json = await resp.json()
    if (json.error) {
      throw new Error(json.error)
    }
    const data = json.data || {}
    ttsEngines.value = data.engines || []
    ttsDevice.value = data.device || null
    ttsBindings.value = data.avatar_bindings || {}
  } catch (e) {
    ttsError.value = e instanceof Error ? e.message : '获取 TTS 信息失败'
  } finally {
    ttsLoading.value = false
  }
}

/* ============== 平台管理 ============== */
const platformIconMap: Record<string, any> = {
  Globe, Radio, Cable, Link, MessageCircle, Send, Gamepad2, Home, Smartphone,
}

const getPlatformIcon = (iconName: string) => platformIconMap[iconName] || Globe

const showAddPlatformDialog = ref(false)
const showEditPlatformDialog = ref(false)
const showMainAgentDialog = ref(false)
const selectedAdapterType = ref<PlatformAdapterType | null>(null)
const newPlatformName = ref('')
const newPlatformConfig = ref<Record<string, any>>({})
const editingInstance = ref<PlatformInstance | null>(null)
const editConfig = ref<Record<string, any>>({})

const mainAgentEdit = ref({
  provider: '',
  model: '',
  systemPrompt: '',
  temperature: 0.7,
  maxTokens: 4096,
})
const mainAgentSaving = ref(false)

const platformSearchQuery = ref('')
const platformFilter = ref<'all' | 'active' | 'stopped'>('all')

const filteredPlatformInstances = computed(() => {
  let list = platformStore.instances
  if (platformSearchQuery.value) {
    const q = platformSearchQuery.value.toLowerCase()
    list = list.filter(i => i.name.toLowerCase().includes(q) || i.displayName.toLowerCase().includes(q))
  }
  if (platformFilter.value === 'active') {
    list = list.filter(i => i.status === 'running')
  } else if (platformFilter.value === 'stopped') {
    list = list.filter(i => i.status !== 'running')
  }
  return list
})

const formatLastSync = (lastSync: string) => {
  if (!lastSync) return '未同步'
  try {
    const date = new Date(lastSync)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return '刚刚'
    if (diffMin < 60) return `${diffMin} 分钟前`
    const diffHour = Math.floor(diffMin / 60)
    if (diffHour < 24) return `${diffHour} 小时前`
    return `${Math.floor(diffHour / 24)} 天前`
  } catch {
    return '未同步'
  }
}

const getStatusLabel = (status: string) => {
  switch (status) {
    case 'running': return '运行中'
    case 'stopped': return '已停止'
    case 'error': return '错误'
    case 'pending': return '等待中'
    default: return '未知'
  }
}

const openAddPlatformDialog = (adapterType?: PlatformAdapterType) => {
  if (adapterType) {
    selectedAdapterType.value = adapterType
    newPlatformName.value = adapterType.displayName
    newPlatformConfig.value = { ...adapterType.configTemplate }
  } else {
    selectedAdapterType.value = null
    newPlatformName.value = ''
    newPlatformConfig.value = {}
  }
  showAddPlatformDialog.value = true
}

const closeAddPlatformDialog = () => {
  showAddPlatformDialog.value = false
  selectedAdapterType.value = null
  newPlatformName.value = ''
  newPlatformConfig.value = {}
}

const handleCreatePlatform = async () => {
  if (!selectedAdapterType.value || !newPlatformName.value.trim()) return
  try {
    await platformStore.createInstance({
      adapterType: selectedAdapterType.value.name,
      name: newPlatformName.value.trim(),
      config: newPlatformConfig.value,
      enable: true,
    })
    closeAddPlatformDialog()
  } catch (e) {
    console.error('Failed to create platform instance:', e)
  }
}

const openEditPlatformDialog = (instance: PlatformInstance) => {
  editingInstance.value = instance
  editConfig.value = { ...instance.config }
  showEditPlatformDialog.value = true
}

const closeEditPlatformDialog = () => {
  showEditPlatformDialog.value = false
  editingInstance.value = null
  editConfig.value = {}
}

const handleSavePlatformConfig = async () => {
  if (!editingInstance.value) return
  try {
    await platformStore.updateInstance(editingInstance.value.id, {
      name: editingInstance.value.name,
      config: editConfig.value,
    })
    closeEditPlatformDialog()
  } catch (e) {
    console.error('Failed to update platform instance:', e)
  }
}

const handleTogglePlatform = async (instance: PlatformInstance) => {
  try {
    if (instance.status === 'running') {
      await platformStore.stopInstance(instance.id)
    } else {
      await platformStore.startInstance(instance.id)
    }
  } catch (e) {
    console.error('Failed to toggle platform status:', e)
  }
}

const handleDeletePlatform = async (instance: PlatformInstance) => {
  if (instance.status === 'running') {
    await platformStore.stopInstance(instance.id)
  }
  await platformStore.deleteInstance(instance.id)
}

const handleRefreshPlatforms = async () => {
  await platformStore.refreshAll()
}

const openMainAgentDialog = () => {
  if (platformStore.mainAgent) {
    mainAgentEdit.value = {
      provider: platformStore.mainAgent.provider,
      model: platformStore.mainAgent.model,
      systemPrompt: platformStore.mainAgent.systemPrompt,
      temperature: platformStore.mainAgent.temperature,
      maxTokens: platformStore.mainAgent.maxTokens,
    }
  }
  showMainAgentDialog.value = true
}

const closeMainAgentDialog = () => {
  showMainAgentDialog.value = false
}

const handleSaveMainAgent = async () => {
  mainAgentSaving.value = true
  try {
    await platformStore.updateMainAgent({
      provider: mainAgentEdit.value.provider,
      model: mainAgentEdit.value.model,
      systemPrompt: mainAgentEdit.value.systemPrompt,
      temperature: mainAgentEdit.value.temperature,
      maxTokens: mainAgentEdit.value.maxTokens,
    })
    closeMainAgentDialog()
  } catch (e) {
    console.error('Failed to update main agent config:', e)
  } finally {
    mainAgentSaving.value = false
  }
}

const handleProviderChange = async (providerId: string) => {
  mainAgentEdit.value.provider = providerId
  const models = modelStore.getProviderModels(providerId)
  if (models.length > 0 && !models.find(m => m.id === mainAgentEdit.value.model)) {
    mainAgentEdit.value.model = models[0].id
  } else if (models.length === 0) {
    const provider = modelStore.providers.find(p => p.id === providerId)
    mainAgentEdit.value.model = provider?.defaultModel || ''
  }
}

/* ============== 主智能体设置页 ============== */
const mainAgentLoading = ref(false)
const mainAgentSaveMsg = ref<{ type: 'success' | 'error'; text: string } | null>(null)

const loadMainAgentConfig = async () => {
  mainAgentLoading.value = true
  try {
    await Promise.all([
      platformStore.fetchMainAgent(),
      modelStore.providers.length === 0 ? modelStore.fetchProviders() : Promise.resolve(),
    ])
    if (platformStore.mainAgent) {
      mainAgentEdit.value = {
        provider: platformStore.mainAgent.provider,
        model: platformStore.mainAgent.model,
        systemPrompt: platformStore.mainAgent.systemPrompt,
        temperature: platformStore.mainAgent.temperature,
        maxTokens: platformStore.mainAgent.maxTokens,
      }
    }
  } catch (e) {
    console.error('Failed to load main agent config:', e)
  } finally {
    mainAgentLoading.value = false
  }
}

const handleSaveMainAgentConfig = async () => {
  mainAgentSaving.value = true
  mainAgentSaveMsg.value = null
  try {
    await platformStore.updateMainAgent({
      provider: mainAgentEdit.value.provider,
      model: mainAgentEdit.value.model,
      systemPrompt: mainAgentEdit.value.systemPrompt,
      temperature: mainAgentEdit.value.temperature,
      maxTokens: mainAgentEdit.value.maxTokens,
    })
    mainAgentSaveMsg.value = { type: 'success', text: '主智能体配置已保存' }
    setTimeout(() => { mainAgentSaveMsg.value = null }, 3000)
  } catch (e) {
    mainAgentSaveMsg.value = { type: 'error', text: `保存失败: ${e instanceof Error ? e.message : String(e)}` }
  } finally {
    mainAgentSaving.value = false
  }
}

onMounted(() => {
  if (section.value === 'tts') {
    fetchTtsInfo()
  } else if (section.value === 'platforms') {
    platformStore.refreshAll()
    if (modelStore.providers.length === 0) {
      modelStore.fetchProviders()
    }
  } else if (section.value === 'main-agent') {
    loadMainAgentConfig()
  }
})

watch(section, (val) => {
  if (val === 'tts' && ttsEngines.value.length === 0 && !ttsLoading.value) {
    fetchTtsInfo()
  } else if (val === 'platforms') {
    platformStore.refreshAll()
    if (modelStore.providers.length === 0) {
      modelStore.fetchProviders()
    }
  } else if (val === 'main-agent') {
    loadMainAgentConfig()
  }
})

const sectionMap: Record<string, { label: string; icon: typeof Palette; desc: string; items: { label: string; desc: string; type: string }[] }> = {
  appearance: {
    label: '外观主题',
    icon: Palette,
    desc: '自定义界面颜色与风格',
    items: [
      { label: '主题模式', desc: '浅色 / 深色 / 跟随系统', type: 'select' },
      { label: '主色调', desc: '选择界面主色调', type: 'color' },
      { label: '字体大小', desc: '调整界面文字大小', type: 'slider' },
      { label: '动画效果', desc: '开启或关闭界面动画', type: 'toggle' }
    ]
  },
  notifications: {
    label: '通知设置',
    icon: Bell,
    desc: '配置消息提醒方式',
    items: [
      { label: '桌面通知', desc: '接收桌面推送通知', type: 'toggle' },
      { label: '声音提醒', desc: '收到消息时播放提示音', type: 'toggle' },
      { label: '免打扰模式', desc: '设定免打扰时段', type: 'time' },
      { label: '消息预览', desc: '在通知中显示消息内容', type: 'toggle' }
    ]
  },
  privacy: {
    label: '隐私安全',
    icon: Shield,
    desc: '数据加密与访问控制',
    items: [
      { label: '端到端加密', desc: '所有对话数据加密存储', type: 'toggle' },
      { label: '本地存储', desc: '数据仅保存在本地设备', type: 'toggle' },
      { label: '自动清除', desc: '定期清除过期对话记录', type: 'select' },
      { label: '访问控制', desc: '设置应用启动密码', type: 'password' }
    ]
  },
  platforms: {
    label: '消息平台',
    icon: Globe,
    desc: 'QQ / 微信 / Discord 等',
    items: [
      { label: 'QQ', desc: '连接 QQ 机器人', type: 'connect' },
      { label: '微信', desc: '连接微信公众号/企微', type: 'connect' },
      { label: 'Discord', desc: '连接 Discord Bot', type: 'connect' },
      { label: 'Telegram', desc: '连接 Telegram Bot', type: 'connect' }
    ]
  },
  mcp: {
    label: 'MCP 工具',
    icon: Settings,
    desc: '外部工具接入协议',
    items: [
      { label: '已安装工具', desc: '查看和管理已安装的 MCP 工具', type: 'list' },
      { label: '添加工具', desc: '从市场或自定义安装工具', type: 'button' },
      { label: '工具权限', desc: '管理工具的访问权限', type: 'select' },
      { label: '运行日志', desc: '查看工具运行日志', type: 'button' }
    ]
  },
  'main-agent': {
    label: '主智能体',
    icon: Brain,
    desc: '工作台主 Agent 的人格、模型与行为配置',
    items: []
  },
  tts: {
    label: '语音合成 (TTS)',
    icon: Volume2,
    desc: '本地/在线 TTS 引擎与设备检测',
    items: []
  }
}

const currentSection = computed(() => sectionMap[section.value] ?? null)
</script>

<template>
  <div class="settings-detail-view">
    <div v-if="currentSection" class="detail-content animate-fade-in">
      <div class="settings-detail-header">
        <button class="back-btn" @click="router.push('/settings')">
          <ArrowLeft :size="18" />
        </button>
        <div class="header-icon">
          <component :is="currentSection.icon" :size="24" />
        </div>
        <div>
          <h1 class="page-title">{{ currentSection.label }}</h1>
          <p class="page-subtitle">{{ currentSection.desc }}</p>
        </div>
      </div>

      <div class="settings-body">
        <!-- TTS 专属面板 -->
        <template v-if="section === 'tts'">
          <div class="tts-panel animate-slide-up">
            <!-- 加载状态 -->
            <div v-if="ttsLoading" class="tts-loading">
              <Loader2 :size="20" class="tts-spin" />
              <span>正在检测 TTS 引擎与设备...</span>
            </div>

            <!-- 错误提示 -->
            <div v-else-if="ttsError" class="tts-error">
              <AlertCircle :size="18" />
              <span>{{ ttsError }}</span>
              <button class="tts-retry-btn" @click="fetchTtsInfo">重试</button>
            </div>

            <template v-else>
              <!-- 设备检测卡片 -->
              <div class="tts-card">
                <div class="tts-card-header">
                  <Cpu :size="18" />
                  <span class="tts-card-title">设备检测</span>
                </div>
                <div class="tts-device-info">
                  <div class="tts-device-row">
                    <span class="tts-device-label">计算设备</span>
                    <span :class="['tts-device-badge', ttsDevice?.type === 'gpu' ? 'gpu' : 'cpu']">
                      {{ ttsDevice?.type === 'gpu' ? 'GPU (CUDA)' : 'CPU' }}
                    </span>
                  </div>
                  <div class="tts-device-row">
                    <span class="tts-device-label">设备名称</span>
                    <span class="tts-device-value">{{ ttsDevice?.name || '未知' }}</span>
                  </div>
                  <div v-if="ttsDevice?.cuda_available" class="tts-device-row">
                    <span class="tts-device-label">CUDA 版本</span>
                    <span class="tts-device-value">{{ ttsDevice.cuda_version || '未知' }}</span>
                  </div>
                  <div class="tts-device-hint">
                    {{ ttsDevice?.type === 'gpu'
                      ? '检测到 GPU，可支持高性能 TTS 推理。当前本地 TTS 使用 pyttsx3 (CPU)，未来可扩展 GPU 加速引擎。'
                      : '未检测到 GPU，本地 TTS 将使用 CPU 推理 (pyttsx3)。在线 TTS (Edge TTS) 不受设备限制。' }}
                  </div>
                </div>
              </div>

              <!-- TTS 引擎列表 -->
              <div class="tts-card">
                <div class="tts-card-header">
                  <Volume2 :size="18" />
                  <span class="tts-card-title">可用引擎</span>
                </div>
                <div class="tts-engine-list">
                  <div
                    v-for="engine in ttsEngines"
                    :key="engine.id"
                    :class="['tts-engine-item', { unavailable: !engine.available }]"
                  >
                    <div class="tts-engine-info">
                      <div class="tts-engine-name-row">
                        <component
                          :is="engine.online ? Wifi : WifiOff"
                          :size="14"
                          :class="engine.online ? 'tts-online-icon' : 'tts-offline-icon'"
                        />
                        <span class="tts-engine-name">{{ engine.name }}</span>
                      </div>
                      <div class="tts-engine-desc">
                        {{ engine.online ? '在线合成，需网络连接' : '离线合成，无需网络' }}
                      </div>
                    </div>
                    <div :class="['tts-engine-status', engine.available ? 'available' : 'unavailable']">
                      <Check v-if="engine.available" :size="14" />
                      <AlertCircle v-else :size="14" />
                      <span>{{ engine.available ? '可用' : '未安装' }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Avatar 语音绑定 -->
              <div class="tts-card">
                <div class="tts-card-header">
                  <Palette :size="18" />
                  <span class="tts-card-title">角色语音绑定</span>
                </div>
                <div class="tts-binding-list">
                  <div
                    v-for="(binding, modelId) in ttsBindings"
                    :key="modelId"
                    class="tts-binding-item"
                  >
                    <div class="tts-binding-model">{{ modelId }}</div>
                    <div class="tts-binding-details">
                      <div class="tts-binding-row">
                        <span class="tts-binding-label">语音</span>
                        <span class="tts-binding-value">{{ binding.voice }}</span>
                      </div>
                      <div class="tts-binding-row">
                        <span class="tts-binding-label">语言</span>
                        <span class="tts-binding-value">{{ binding.voice_lang }}</span>
                      </div>
                      <div class="tts-binding-row">
                        <span class="tts-binding-label">默认表情</span>
                        <span class="tts-binding-value">{{ binding.default_expression }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </template>

        <!-- 平台管理专属面板 -->
        <template v-else-if="section === 'platforms'">
          <div class="platform-panel animate-slide-up">
            <!-- 主 Agent 信息卡片 -->
            <div class="platform-card">
              <div class="platform-card-header">
                <Brain :size="18" />
                <span class="platform-card-title">主 Agent 配置</span>
                <button class="platform-header-btn" @click="openMainAgentDialog">
                  <Edit3 :size="13" />
                  <span>编辑</span>
                </button>
              </div>
              <div class="platform-card-body">
                <div v-if="platformStore.mainAgent" class="main-agent-grid">
                  <div class="main-agent-item">
                    <span class="main-agent-label">供应商</span>
                    <span class="main-agent-value">{{ platformStore.mainAgent.providerName || platformStore.mainAgent.provider || '未配置' }}</span>
                  </div>
                  <div class="main-agent-item">
                    <span class="main-agent-label">模型</span>
                    <span class="main-agent-value mono">{{ platformStore.mainAgent.model || '未配置' }}</span>
                  </div>
                  <div class="main-agent-item">
                    <span class="main-agent-label">图片识别</span>
                    <span :class="['main-agent-badge', platformStore.mainAgent.supportsMultimodal ? 'supported' : 'unsupported']">
                      <ImageIcon :size="12" />
                      <span>{{ platformStore.mainAgent.supportsMultimodal ? '支持多模态' : '不支持图片' }}</span>
                    </span>
                  </div>
                  <div class="main-agent-item">
                    <span class="main-agent-label">温度</span>
                    <span class="main-agent-value mono">{{ platformStore.mainAgent.temperature }}</span>
                  </div>
                  <div class="main-agent-item">
                    <span class="main-agent-label">最大 Tokens</span>
                    <span class="main-agent-value mono">{{ platformStore.mainAgent.maxTokens }}</span>
                  </div>
                  <div class="main-agent-item full-width">
                    <span class="main-agent-label">系统提示词</span>
                    <span class="main-agent-prompt">{{ platformStore.mainAgent.systemPrompt || '（未设置，使用默认提示词）' }}</span>
                  </div>
                </div>
                <div v-else class="main-agent-empty">
                  <Loader2 :size="16" class="tts-spin" />
                  <span>正在加载主 Agent 配置...</span>
                </div>
                <div class="main-agent-hint">
                  主 Agent 是工作台页面的核心智能体，所有平台消息将共享其记忆与配置。子 Agent 不共享此记忆。
                </div>
              </div>
            </div>

            <!-- 统计卡片 -->
            <div class="platform-stats-row">
              <div class="platform-stat-card">
                <div class="platform-stat-icon"><Server :size="16" /></div>
                <div class="platform-stat-info">
                  <span class="platform-stat-value">{{ platformStore.stats.totalPlatforms }}</span>
                  <span class="platform-stat-label">已接入平台</span>
                </div>
              </div>
              <div class="platform-stat-card">
                <div class="platform-stat-icon active"><Zap :size="16" /></div>
                <div class="platform-stat-info">
                  <span class="platform-stat-value">{{ platformStore.stats.activeConnections }}</span>
                  <span class="platform-stat-label">活跃连接</span>
                </div>
              </div>
              <div class="platform-stat-card">
                <div class="platform-stat-icon"><MessageCircle :size="16" /></div>
                <div class="platform-stat-info">
                  <span class="platform-stat-value">{{ platformStore.stats.totalMessages }}</span>
                  <span class="platform-stat-label">消息总量</span>
                </div>
              </div>
            </div>

            <!-- 平台实例列表 -->
            <div class="platform-card">
              <div class="platform-card-header">
                <Globe :size="18" />
                <span class="platform-card-title">平台实例</span>
                <div class="platform-header-actions">
                  <button class="platform-header-btn" @click="handleRefreshPlatforms" :disabled="platformStore.loading">
                    <RefreshCw :size="13" :class="{ spinning: platformStore.loading }" />
                    <span>刷新</span>
                  </button>
                  <button class="platform-header-btn primary" @click="openAddPlatformDialog()">
                    <Plus :size="13" />
                    <span>添加平台</span>
                  </button>
                </div>
              </div>
              <div class="platform-card-body">
                <div class="platform-toolbar">
                  <input v-model="platformSearchQuery" type="text" class="platform-search" placeholder="搜索平台..." />
                  <div class="platform-filter-group">
                    <button :class="['platform-filter-btn', { active: platformFilter === 'all' }]" @click="platformFilter = 'all'">全部</button>
                    <button :class="['platform-filter-btn', { active: platformFilter === 'active' }]" @click="platformFilter = 'active'">运行中</button>
                    <button :class="['platform-filter-btn', { active: platformFilter === 'stopped' }]" @click="platformFilter = 'stopped'">已停止</button>
                  </div>
                </div>

                <div class="platform-instance-list">
                  <div
                    v-for="inst in filteredPlatformInstances"
                    :key="inst.id"
                    :class="['platform-instance-item', { disconnected: inst.status !== 'running' }]"
                  >
                    <div class="pi-left">
                      <div :class="['pi-icon', inst.category]">
                        <component :is="getPlatformIcon(inst.icon)" :size="16" />
                      </div>
                      <div class="pi-info">
                        <div class="pi-name-row">
                          <span class="pi-name">{{ inst.name }}</span>
                          <span :class="['pi-status', inst.status]">{{ getStatusLabel(inst.status) }}</span>
                        </div>
                        <div class="pi-meta">
                          <span>{{ inst.displayName }}</span>
                          <span class="pi-dot">·</span>
                          <span>{{ inst.messageCount }} 条消息</span>
                          <span class="pi-dot">·</span>
                          <span>{{ formatLastSync(inst.lastSync) }}</span>
                        </div>
                        <div v-if="inst.errorMessage" class="pi-error">
                          <AlertCircle :size="11" />
                          <span>{{ inst.errorMessage }}</span>
                        </div>
                      </div>
                    </div>
                    <div class="pi-actions">
                      <button
                        class="pi-action-btn"
                        :class="inst.status === 'running' ? 'stop' : 'start'"
                        @click="handleTogglePlatform(inst)"
                        :title="inst.status === 'running' ? '停止' : '启动'"
                      >
                        <Square v-if="inst.status === 'running'" :size="12" />
                        <Play v-else :size="12" />
                      </button>
                      <button class="pi-action-btn config" @click="openEditPlatformDialog(inst)" title="配置">
                        <Settings :size="12" />
                      </button>
                      <button class="pi-action-btn delete" @click="handleDeletePlatform(inst)" title="删除">
                        <Trash2 :size="12" />
                      </button>
                    </div>
                  </div>

                  <div v-if="filteredPlatformInstances.length === 0" class="platform-empty">
                    <Globe :size="28" class="platform-empty-icon" />
                    <span class="platform-empty-text">暂无平台实例</span>
                    <button class="platform-empty-btn" @click="openAddPlatformDialog()">
                      <Plus :size="13" />
                      添加平台
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- 主智能体专属面板 -->
        <template v-else-if="section === 'main-agent'">
          <div class="main-agent-panel animate-slide-up">
            <!-- 加载状态 -->
            <div v-if="mainAgentLoading" class="main-agent-loading">
              <Loader2 :size="20" class="tts-spin" />
              <span>正在加载主智能体配置...</span>
            </div>

            <template v-else>
              <!-- 模型配置卡片 -->
              <div class="main-agent-card">
                <div class="main-agent-card-header">
                  <Cpu :size="18" />
                  <span class="main-agent-card-title">模型配置</span>
                </div>
                <div class="main-agent-card-body">
                  <div class="platform-form-group">
                    <label class="platform-form-label">供应商</label>
                    <select class="platform-form-input" :value="mainAgentEdit.provider" @change="handleProviderChange(($event.target as HTMLSelectElement).value)">
                      <option value="">未选择（使用默认）</option>
                      <option v-for="p in modelStore.providers" :key="p.id" :value="p.id">{{ p.name }}</option>
                    </select>
                  </div>
                  <div class="platform-form-group">
                    <label class="platform-form-label">模型</label>
                    <input v-model="mainAgentEdit.model" type="text" class="platform-form-input" placeholder="输入模型 ID 或从供应商选择" list="main-agent-models-list" />
                    <datalist id="main-agent-models-list">
                      <option v-for="m in modelStore.getProviderModels(mainAgentEdit.provider)" :key="m.id" :value="m.id" />
                    </datalist>
                  </div>
                  <div class="platform-form-row">
                    <div class="platform-form-group">
                      <label class="platform-form-label">温度 (0-2)</label>
                      <input v-model.number="mainAgentEdit.temperature" type="number" min="0" max="2" step="0.1" class="platform-form-input" />
                    </div>
                    <div class="platform-form-group">
                      <label class="platform-form-label">最大 Tokens</label>
                      <input v-model.number="mainAgentEdit.maxTokens" type="number" min="1" step="1" class="platform-form-input" />
                    </div>
                  </div>
                </div>
              </div>

              <!-- 人格配置卡片 -->
              <div class="main-agent-card">
                <div class="main-agent-card-header">
                  <Brain :size="18" />
                  <span class="main-agent-card-title">人格与系统提示</span>
                </div>
                <div class="main-agent-card-body">
                  <div class="platform-form-group">
                    <label class="platform-form-label">系统提示词</label>
                    <textarea v-model="mainAgentEdit.systemPrompt" class="platform-form-textarea main-agent-prompt" rows="10" placeholder="主智能体的系统提示词，决定其角色、人格与行为准则。例如：你是 LuomiNest 的主控智能体，负责与用户交互、调度子 Agent、管理记忆与工具..."></textarea>
                    <span class="platform-form-hint">提示词会作为系统消息注入到主 Agent 的每次对话开头，影响其角色定位与行为方式</span>
                  </div>
                </div>
              </div>

              <!-- 保存按钮 -->
              <div class="main-agent-actions">
                <div v-if="mainAgentSaveMsg" :class="['main-agent-msg', mainAgentSaveMsg.type]">
                  <component :is="mainAgentSaveMsg.type === 'success' ? Check : AlertCircle" :size="14" />
                  <span>{{ mainAgentSaveMsg.text }}</span>
                </div>
                <button class="main-agent-save-btn" @click="handleSaveMainAgentConfig" :disabled="mainAgentSaving">
                  <Save :size="14" />
                  <span>{{ mainAgentSaving ? '保存中...' : '保存配置' }}</span>
                </button>
              </div>
            </template>
          </div>
        </template>

        <!-- 通用设置项 -->
        <div v-else class="setting-items-card animate-slide-up">
          <div
            v-for="(item, idx) in currentSection.items"
            :key="item.label"
            :class="['setting-row', { last: idx === currentSection.items.length - 1 }]"
          >
            <div class="row-info">
              <span class="row-label">{{ item.label }}</span>
              <span class="row-desc">{{ item.desc }}</span>
            </div>
            <div class="row-control">
              <div v-if="item.type === 'toggle' && item.label === '动画效果'" class="toggle-switch" :class="{ on: true }">
                <span class="toggle-thumb" />
              </div>
              <div v-else-if="item.type === 'select' && section === 'appearance' && item.label === '主题模式'" class="theme-mode-selector">
                <button
                  :class="['theme-option', { active: !themeStore.isDark }]"
                  @click="themeStore.setTheme(false)"
                >
                  <Sun :size="14" />
                  <span>浅色</span>
                </button>
                <button
                  :class="['theme-option', { active: themeStore.isDark }]"
                  @click="themeStore.setTheme(true)"
                >
                  <Moon :size="14" />
                  <span>深色</span>
                </button>
              </div>
              <div v-else-if="item.type === 'select'" class="control-select">
                <span class="control-placeholder">请选择</span>
              </div>
              <div v-else-if="item.type === 'input'" class="control-input">
                <span class="control-placeholder">点击输入</span>
              </div>
              <div v-else-if="item.type === 'slider'" class="control-slider">
                <div class="slider-track" />
              </div>
              <div v-else-if="item.type === 'connect'" class="control-connect">
                <span class="connect-btn">连接</span>
              </div>
              <div v-else class="control-default">
                <span class="control-placeholder">配置</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="not-found animate-fade-in">
      <h2>设置项未找到</h2>
      <p>请返回设置主页选择有效的设置项</p>
      <button class="back-home-btn" @click="router.push('/settings')">返回设置</button>
    </div>

    <!-- 添加平台对话框 -->
    <Teleport to="body">
      <div v-if="showAddPlatformDialog" class="platform-dialog-overlay" @click.self="closeAddPlatformDialog">
        <div class="platform-dialog">
          <div class="platform-dialog-header">
            <h2 class="platform-dialog-title">添加平台</h2>
            <button class="platform-dialog-close" @click="closeAddPlatformDialog"><X :size="18" /></button>
          </div>

          <div v-if="!selectedAdapterType" class="platform-dialog-body">
            <p class="platform-dialog-desc">选择要接入的平台类型：</p>
            <div class="adapter-type-list">
              <button
                v-for="at in platformStore.adapterTypes"
                :key="at.name"
                class="adapter-type-item"
                @click="openAddPlatformDialog(at)"
              >
                <div :class="['adapter-type-icon', at.category]">
                  <component :is="getPlatformIcon(at.icon)" :size="18" />
                </div>
                <div class="adapter-type-info">
                  <span class="adapter-type-name">{{ at.displayName }}</span>
                  <span class="adapter-type-desc">{{ at.description }}</span>
                </div>
                <span :class="['adapter-type-cat', at.category]">{{ at.category === 'social' ? '社交' : at.category === 'iot' ? 'IoT' : at.category === 'game' ? '游戏' : '通用' }}</span>
              </button>
            </div>
          </div>

          <div v-else class="platform-dialog-body">
            <div class="platform-form-group">
              <label class="platform-form-label">平台名称</label>
              <input v-model="newPlatformName" type="text" class="platform-form-input" placeholder="输入平台实例名称" />
            </div>
            <div class="platform-form-group">
              <label class="platform-form-label">平台类型</label>
              <div class="platform-type-badge">
                <component :is="getPlatformIcon(selectedAdapterType.icon)" :size="14" />
                <span>{{ selectedAdapterType.displayName }}</span>
              </div>
            </div>
            <div v-if="Object.keys(selectedAdapterType.configMetadata).length > 0" class="platform-form-group">
              <label class="platform-form-label">连接配置</label>
              <div class="platform-config-fields">
                <div v-for="(meta, key) in selectedAdapterType.configMetadata" :key="key" class="platform-config-field">
                  <label class="platform-config-label">{{ (meta as any).label || key }}</label>
                  <input
                    v-model="newPlatformConfig[key]"
                    :type="(meta as any).type === 'password' ? 'password' : (meta as any).type === 'number' ? 'number' : 'text'"
                    class="platform-form-input"
                    :placeholder="(meta as any).label || key"
                  />
                </div>
              </div>
            </div>
          </div>

          <div class="platform-dialog-footer">
            <button class="platform-dialog-btn cancel" @click="closeAddPlatformDialog">取消</button>
            <button
              v-if="selectedAdapterType"
              class="platform-dialog-btn confirm"
              @click="handleCreatePlatform"
              :disabled="!newPlatformName.trim()"
            >确认添加</button>
            <button v-else class="platform-dialog-btn confirm" @click="closeAddPlatformDialog">关闭</button>
          </div>
        </div>
      </div>

      <!-- 编辑平台配置对话框 -->
      <div v-if="showEditPlatformDialog && editingInstance" class="platform-dialog-overlay" @click.self="closeEditPlatformDialog">
        <div class="platform-dialog">
          <div class="platform-dialog-header">
            <h2 class="platform-dialog-title">平台配置 - {{ editingInstance.name }}</h2>
            <button class="platform-dialog-close" @click="closeEditPlatformDialog"><X :size="18" /></button>
          </div>
          <div class="platform-dialog-body">
            <div class="platform-form-group">
              <label class="platform-form-label">实例名称</label>
              <input v-model="editingInstance.name" type="text" class="platform-form-input" />
            </div>
            <div class="platform-form-group">
              <label class="platform-form-label">状态</label>
              <div class="platform-status-display">
                <span :class="['pi-status', editingInstance.status]">{{ getStatusLabel(editingInstance.status) }}</span>
              </div>
            </div>
            <div v-if="Object.keys(editConfig).length > 0" class="platform-form-group">
              <label class="platform-form-label">连接配置</label>
              <div class="platform-config-fields">
                <div v-for="(_val, key) in editConfig" :key="key" class="platform-config-field">
                  <label class="platform-config-label">{{ key }}</label>
                  <input v-model="editConfig[key]" type="text" class="platform-form-input" />
                </div>
              </div>
            </div>
            <div v-if="editingInstance.errorMessage" class="platform-form-group">
              <label class="platform-form-label">错误信息</label>
              <div class="platform-error-display">{{ editingInstance.errorMessage }}</div>
            </div>
          </div>
          <div class="platform-dialog-footer">
            <button class="platform-dialog-btn cancel" @click="closeEditPlatformDialog">取消</button>
            <button class="platform-dialog-btn confirm" @click="handleSavePlatformConfig">保存配置</button>
          </div>
        </div>
      </div>

      <!-- 主 Agent 配置对话框 -->
      <div v-if="showMainAgentDialog" class="platform-dialog-overlay" @click.self="closeMainAgentDialog">
        <div class="platform-dialog">
          <div class="platform-dialog-header">
            <h2 class="platform-dialog-title">主 Agent 配置</h2>
            <button class="platform-dialog-close" @click="closeMainAgentDialog"><X :size="18" /></button>
          </div>
          <div class="platform-dialog-body">
            <div class="platform-form-group">
              <label class="platform-form-label">供应商</label>
              <select class="platform-form-input" :value="mainAgentEdit.provider" @change="handleProviderChange(($event.target as HTMLSelectElement).value)">
                <option value="">未选择（使用默认）</option>
                <option v-for="p in modelStore.providers" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </div>
            <div class="platform-form-group">
              <label class="platform-form-label">模型</label>
              <input v-model="mainAgentEdit.model" type="text" class="platform-form-input" placeholder="输入模型 ID 或从供应商选择" list="main-agent-models" />
              <datalist id="main-agent-models">
                <option v-for="m in modelStore.getProviderModels(mainAgentEdit.provider)" :key="m.id" :value="m.id" />
              </datalist>
            </div>
            <div class="platform-form-group">
              <label class="platform-form-label">温度 (0-2)</label>
              <input v-model.number="mainAgentEdit.temperature" type="number" min="0" max="2" step="0.1" class="platform-form-input" />
            </div>
            <div class="platform-form-group">
              <label class="platform-form-label">最大 Tokens</label>
              <input v-model.number="mainAgentEdit.maxTokens" type="number" min="1" step="1" class="platform-form-input" />
            </div>
            <div class="platform-form-group">
              <label class="platform-form-label">系统提示词</label>
              <textarea v-model="mainAgentEdit.systemPrompt" class="platform-form-textarea" rows="6" placeholder="主 Agent 的系统提示词，决定其角色与行为"></textarea>
            </div>
          </div>
          <div class="platform-dialog-footer">
            <button class="platform-dialog-btn cancel" @click="closeMainAgentDialog" :disabled="mainAgentSaving">取消</button>
            <button class="platform-dialog-btn confirm" @click="handleSaveMainAgent" :disabled="mainAgentSaving">
              <Save :size="13" />
              <span>{{ mainAgentSaving ? '保存中...' : '保存配置' }}</span>
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.settings-detail-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.detail-content {
  display: flex;
  flex-direction: column;
  height: 100%;
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
  background: linear-gradient(135deg, rgba(20, 126, 188, 0.1), rgba(98, 169, 200, 0.1));
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

.settings-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
}

.setting-items-card {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  max-width: 640px;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid var(--workspace-border);
  transition: background var(--transition-fast);
}

.setting-row.last {
  border-bottom: none;
}

.setting-row:hover {
  background: var(--workspace-hover);
}

.row-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.row-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.row-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.row-control {
  flex-shrink: 0;
  margin-left: 16px;
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

.toggle-switch.on {
  background: var(--lumi-primary);
}

.toggle-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--surface);
  box-shadow: 0 1px 3px var(--overlay-subtle);
  transition: all var(--transition-fast);
}

.toggle-switch.on .toggle-thumb {
  left: 23px;
}

.theme-mode-selector {
  display: flex;
  gap: 4px;
  padding: 2px;
  border-radius: var(--radius-sm);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
}

.theme-option {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  background: transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
  border: none;
}

.theme-option.active {
  background: var(--workspace-card);
  color: var(--text-primary);
  box-shadow: var(--shadow-xs);
}

.control-select,
.control-input,
.control-default {
  padding: 6px 14px;
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-sm);
}

.control-placeholder {
  font-size: 12px;
  color: var(--text-muted);
}

.control-slider {
  width: 120px;
  height: 6px;
}

.slider-track {
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: var(--workspace-border);
  position: relative;
}

.slider-track::after {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 60%;
  height: 100%;
  border-radius: 3px;
  background: var(--lumi-primary);
}

.control-connect {
  padding: 6px 16px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-light);
}

.connect-btn {
  font-size: 12px;
  font-weight: 600;
  color: var(--lumi-primary);
}

.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: var(--text-muted);
}

.not-found h2 {
  font-size: 18px;
  color: var(--text-primary);
}

.not-found p {
  font-size: 13px;
}

.back-home-btn {
  margin-top: 8px;
  padding: 8px 20px;
  border-radius: var(--radius-md);
  background: var(--lumi-primary);
  color: white;
  font-size: 13px;
  font-weight: 600;
  transition: all var(--transition-fast);
}

.back-home-btn:hover {
  background: var(--lumi-primary-hover);
}

/* TTS 设置面板 */
.tts-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 640px;
}

.tts-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 32px 20px;
  justify-content: center;
  color: var(--text-muted);
  font-size: 13px;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
}

.tts-spin {
  animation: tts-spin 1s linear infinite;
  color: var(--lumi-primary);
}

@keyframes tts-spin {
  to { transform: rotate(360deg); }
}

.tts-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 18px;
  color: var(--lumi-danger);
  font-size: 13px;
  background: var(--task-red-soft);
  border: 1px solid var(--task-red-border);
  border-radius: var(--radius-lg);
}

.tts-retry-btn {
  margin-left: auto;
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary);
  color: white;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.tts-retry-btn:hover {
  background: var(--lumi-primary-hover);
}

.tts-card {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.tts-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--workspace-border);
  color: var(--lumi-primary);
}

.tts-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.tts-device-info {
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tts-device-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tts-device-label {
  font-size: 13px;
  color: var(--text-muted);
}

.tts-device-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
  font-family: monospace;
}

.tts-device-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 12px;
}

.tts-device-badge.gpu {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.tts-device-badge.cpu {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.tts-device-hint {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.6;
  padding-top: 6px;
  border-top: 1px solid var(--divider-soft);
  margin-top: 4px;
}

.tts-engine-list {
  padding: 8px 0;
}

.tts-engine-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  transition: background var(--transition-fast);
}

.tts-engine-item:not(:last-child) {
  border-bottom: 1px solid var(--divider-soft);
}

.tts-engine-item:hover {
  background: var(--workspace-hover);
}

.tts-engine-item.unavailable {
  opacity: 0.55;
}

.tts-engine-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.tts-engine-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tts-online-icon {
  color: var(--lumi-success);
}

.tts-offline-icon {
  color: var(--text-muted);
}

.tts-engine-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.tts-engine-desc {
  font-size: 11px;
  color: var(--text-muted);
  padding-left: 20px;
}

.tts-engine-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 8px;
}

.tts-engine-status.available {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.tts-engine-status.unavailable {
  background: var(--task-red-soft);
  color: var(--lumi-danger);
}

.tts-binding-list {
  padding: 8px 0;
}

.tts-binding-item {
  padding: 12px 18px;
}

.tts-binding-item:not(:last-child) {
  border-bottom: 1px solid var(--divider-soft);
}

.tts-binding-model {
  font-size: 13px;
  font-weight: 600;
  color: var(--lumi-primary);
  text-transform: capitalize;
  margin-bottom: 8px;
}

.tts-binding-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tts-binding-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.tts-binding-label {
  font-size: 12px;
  color: var(--text-muted);
  min-width: 60px;
}

.tts-binding-value {
  font-size: 12px;
  color: var(--text-primary);
  font-family: monospace;
}

/* ============== 平台管理面板 ============== */
.platform-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 880px;
}

.platform-card {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.platform-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--workspace-border);
  color: var(--lumi-primary);
}

.platform-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.platform-header-actions {
  display: flex;
  gap: 6px;
}

.platform-header-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  background: transparent;
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.platform-header-btn:hover:not(:disabled) {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.platform-header-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.platform-header-btn.primary {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
  color: white;
}

.platform-header-btn.primary:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
  color: white;
}

.platform-card-body {
  padding: 16px 18px;
}

.main-agent-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px 24px;
}

.main-agent-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.main-agent-item.full-width {
  grid-column: 1 / -1;
}

.main-agent-label {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
}

.main-agent-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

.main-agent-value.mono {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
}

.main-agent-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 500;
  width: fit-content;
}

.main-agent-badge.supported {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.main-agent-badge.unsupported {
  background: var(--task-red-soft);
  color: var(--lumi-danger);
}

.main-agent-prompt {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  padding: 8px 10px;
  background: var(--workspace-panel);
  border-radius: var(--radius-sm);
  border: 1px solid var(--workspace-border);
  max-height: 100px;
  overflow-y: auto;
}

.main-agent-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 0;
  color: var(--text-muted);
  font-size: 13px;
}

.main-agent-hint {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--divider-soft);
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.6;
}

.platform-stats-row {
  display: flex;
  gap: 12px;
}

.platform-stat-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
}

.platform-stat-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.platform-stat-icon.active {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.platform-stat-info {
  display: flex;
  flex-direction: column;
}

.platform-stat-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.platform-stat-label {
  font-size: 11px;
  color: var(--text-muted);
}

.platform-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.platform-search {
  flex: 1;
  padding: 7px 12px;
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-primary);
}

.platform-search:focus {
  outline: none;
  border-color: var(--lumi-primary);
}

.platform-filter-group {
  display: flex;
  gap: 4px;
}

.platform-filter-btn {
  padding: 5px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-muted);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.platform-filter-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  border-color: var(--lumi-primary);
}

.platform-instance-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.platform-instance-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.platform-instance-item:hover {
  border-color: var(--lumi-primary);
}

.platform-instance-item.disconnected {
  opacity: 0.75;
}

.pi-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.pi-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.pi-icon.social {
  background: var(--task-purple-soft);
  color: var(--task-purple);
}

.pi-icon.iot {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.pi-icon.game {
  background: var(--task-amber-soft, rgba(245, 158, 11, 0.1));
  color: var(--lumi-amber);
}

.pi-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.pi-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pi-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.pi-status {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
}

.pi-status.running {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.pi-status.stopped,
.pi-status.pending {
  background: var(--workspace-border);
  color: var(--text-muted);
}

.pi-status.error {
  background: var(--task-red-soft);
  color: var(--lumi-danger);
}

.pi-meta {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--text-muted);
}

.pi-dot {
  opacity: 0.5;
}

.pi-error {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 3px;
  font-size: 11px;
  color: var(--lumi-danger);
}

.pi-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.pi-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.pi-action-btn.start {
  color: var(--lumi-success);
}

.pi-action-btn.start:hover {
  background: var(--task-green-soft);
}

.pi-action-btn.stop {
  color: var(--lumi-danger);
}

.pi-action-btn.stop:hover {
  background: var(--task-red-soft);
}

.pi-action-btn.config {
  color: var(--lumi-primary);
}

.pi-action-btn.config:hover {
  background: var(--lumi-primary-light);
}

.pi-action-btn.delete:hover {
  background: var(--task-red-soft);
  color: var(--lumi-danger);
}

.platform-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 32px 20px;
  color: var(--text-muted);
}

.platform-empty-icon {
  opacity: 0.4;
}

.platform-empty-text {
  font-size: 13px;
}

.platform-empty-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  background: var(--lumi-primary);
  color: white;
  transition: all var(--transition-fast);
}

.platform-empty-btn:hover {
  background: var(--lumi-primary-hover);
}

/* ============== 平台对话框 ============== */
.platform-dialog-overlay {
  position: fixed;
  inset: 0;
  background: var(--overlay-bg, rgba(0, 0, 0, 0.5));
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: platform-fade-in 0.2s ease-in-out;
}

.platform-dialog {
  background: var(--surface, var(--workspace-card));
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light, var(--workspace-border));
  width: 560px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  animation: platform-slide-up 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 24px 48px -12px var(--overlay-subtle, rgba(0, 0, 0, 0.2));
}

.platform-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-light, var(--workspace-border));
}

.platform-dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.platform-dialog-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  background: transparent;
  border: none;
}

.platform-dialog-close:hover {
  background: var(--surface-hover, var(--workspace-hover));
  color: var(--text-primary);
}

.platform-dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.platform-dialog-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.adapter-type-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.adapter-type-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--surface, var(--workspace-panel));
  border: 1px solid var(--border-light, var(--workspace-border));
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
}

.adapter-type-item:hover {
  border-color: var(--lumi-primary);
}

.adapter-type-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.adapter-type-icon.social {
  background: var(--task-purple-soft);
  color: var(--task-purple);
}

.adapter-type-icon.iot {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.adapter-type-icon.game {
  background: var(--task-amber-soft, rgba(245, 158, 11, 0.1));
  color: var(--lumi-amber);
}

.adapter-type-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.adapter-type-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.adapter-type-desc {
  font-size: 11px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.adapter-type-cat {
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
  flex-shrink: 0;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.adapter-type-cat.social {
  background: var(--task-purple-soft);
  color: var(--task-purple);
}

.adapter-type-cat.iot {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.adapter-type-cat.game {
  background: var(--task-amber-soft, rgba(245, 158, 11, 0.1));
  color: var(--lumi-amber);
}

.platform-form-group {
  margin-bottom: 16px;
}

.platform-form-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.platform-form-input {
  width: 100%;
  padding: 8px 12px;
  background: var(--surface, var(--workspace-panel));
  border: 1px solid var(--border-light, var(--workspace-border));
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-primary);
  transition: border-color var(--transition-fast);
  box-sizing: border-box;
}

.platform-form-input:focus {
  outline: none;
  border-color: var(--lumi-primary);
}

.platform-form-textarea {
  width: 100%;
  padding: 10px 12px;
  background: var(--surface, var(--workspace-panel));
  border: 1px solid var(--border-light, var(--workspace-border));
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-primary);
  font-family: inherit;
  resize: vertical;
  box-sizing: border-box;
}

.platform-form-textarea:focus {
  outline: none;
  border-color: var(--lumi-primary);
}

.platform-form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.platform-form-hint {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 6px;
  line-height: 1.4;
}

/* ============== 主智能体设置面板 ============== */
.main-agent-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px 28px;
  overflow-y: auto;
  flex: 1;
}

.main-agent-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 40px 0;
  justify-content: center;
  color: var(--text-muted);
  font-size: 13px;
}

.main-agent-card {
  background: var(--workspace-card);
  border: 1px solid var(--border-light, var(--workspace-border));
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-xs);
}

.main-agent-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--divider-soft, var(--workspace-border));
  color: var(--lumi-primary);
}

.main-agent-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.main-agent-card-body {
  padding: 18px;
}

.main-agent-prompt {
  min-height: 160px;
  line-height: 1.6;
  font-size: 13px;
}

.main-agent-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
  padding-top: 4px;
}

.main-agent-msg {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
}

.main-agent-msg.success {
  color: var(--lumi-success, #10b981);
  background: var(--lumi-primary-light);
}

.main-agent-msg.error {
  color: var(--lumi-danger, #ef4444);
  background: var(--task-red-soft, rgba(239, 68, 68, 0.1));
}

.main-agent-save-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 20px;
  background: var(--lumi-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition-fast), opacity var(--transition-fast);
}

.main-agent-save-btn:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.main-agent-save-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.platform-type-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--lumi-primary-light);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  color: var(--lumi-primary);
}

.platform-config-fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.platform-config-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.platform-config-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted);
}

.platform-status-display {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.platform-error-display {
  padding: 8px 12px;
  background: var(--task-red-soft);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--lumi-danger);
}

.platform-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-light, var(--workspace-border));
}

.platform-dialog-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 18px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  border: none;
}

.platform-dialog-btn.cancel {
  background: var(--surface, var(--workspace-panel));
  color: var(--text-secondary);
  border: 1px solid var(--border, var(--workspace-border));
}

.platform-dialog-btn.cancel:hover:not(:disabled) {
  background: var(--surface-hover, var(--workspace-hover));
}

.platform-dialog-btn.confirm {
  background: var(--lumi-primary);
  color: white;
}

.platform-dialog-btn.confirm:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.platform-dialog-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@keyframes platform-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes platform-slide-up {
  from {
    opacity: 0;
    transform: translateY(14px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
