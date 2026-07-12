<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Globe,
  Radio,
  Cable,
  Link,
  MessageCircle,
  Send,
  Gamepad2,
  Home,
  Smartphone,
  Brain,
  Edit3,
  Server,
  Zap,
  Plus,
  RefreshCw,
  Play,
  Square,
  Settings,
  Trash2,
  AlertCircle,
  Loader2,
  X,
  Save,
  Image as ImageIcon
} from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import { useModelStore } from '../../stores/model'
import type { PlatformAdapterType, PlatformInstance } from '../../types'
import { createLuomiNestRendererLogger } from '../../utils/logger'

const logger = createLuomiNestRendererLogger('Settings')

const platformStore = usePlatformStore()
const modelStore = useModelStore()

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
    logger.error('Failed to create platform instance:', e)
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
    logger.error('Failed to update platform instance:', e)
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
    logger.error('Failed to toggle platform status:', e)
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
    logger.error('Failed to update main agent config:', e)
  } finally {
    mainAgentSaving.value = false
  }
}

onMounted(() => {
  platformStore.refreshAll()
  if (modelStore.providers.length === 0) {
    modelStore.fetchProviders()
  }
})
</script>

<template>
  <div class="platform-panel animate-slide-up">
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

    <div class="platform-stats-row">
      <div class="platform-stat-card">
        <div class="lumi-icon-wrap lumi-icon-wrap--md lumi-icon-wrap--primary"><Server :size="16" /></div>
        <div class="platform-stat-info">
          <span class="platform-stat-value">{{ platformStore.stats.totalPlatforms }}</span>
          <span class="platform-stat-label">已接入平台</span>
        </div>
      </div>
      <div class="platform-stat-card">
        <div class="lumi-icon-wrap lumi-icon-wrap--md platform-stat-active"><Zap :size="16" /></div>
        <div class="platform-stat-info">
          <span class="platform-stat-value">{{ platformStore.stats.activeConnections }}</span>
          <span class="platform-stat-label">活跃连接</span>
        </div>
      </div>
      <div class="platform-stat-card">
        <div class="lumi-icon-wrap lumi-icon-wrap--md lumi-icon-wrap--primary"><MessageCircle :size="16" /></div>
        <div class="platform-stat-info">
          <span class="platform-stat-value">{{ platformStore.stats.totalMessages }}</span>
          <span class="platform-stat-label">消息总量</span>
        </div>
      </div>
    </div>

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

    <div v-if="showMainAgentDialog" class="platform-dialog-overlay" @click.self="closeMainAgentDialog">
      <div class="platform-dialog">
        <div class="platform-dialog-header">
          <h2 class="platform-dialog-title">主 Agent 配置</h2>
          <button class="platform-dialog-close" @click="closeMainAgentDialog"><X :size="18" /></button>
        </div>
        <div class="platform-dialog-body">
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
</template>

<style scoped>
.platform-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
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
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--workspace-border);
  color: var(--lumi-primary);
}

.platform-card-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.platform-header-actions {
  display: flex;
  gap: var(--space-2);
}

.platform-header-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
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
  color: var(--text-inverse);
}

.platform-header-btn.primary:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
  color: var(--text-inverse);
}

.platform-card-body {
  padding: var(--space-4) var(--space-4);
}

.main-agent-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3) var(--space-6);
}

.main-agent-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.main-agent-item.full-width {
  grid-column: 1 / -1;
}

.main-agent-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: 500;
}

.main-agent-value {
  font-size: var(--text-base);
  color: var(--text-primary);
  font-weight: 500;
}

.main-agent-value.mono {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: var(--text-sm);
}

.main-agent-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
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
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.6;
  padding: var(--space-2) var(--space-2);
  background: var(--workspace-panel);
  border-radius: var(--radius-sm);
  border: 1px solid var(--workspace-border);
  max-height: 100px;
  overflow-y: auto;
}

.main-agent-empty {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) 0;
  color: var(--text-muted);
  font-size: var(--text-base);
}

.main-agent-hint {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--divider-soft);
  font-size: var(--text-xs);
  color: var(--text-muted);
  line-height: 1.6;
}

.platform-stats-row {
  display: flex;
  gap: var(--space-3);
}

.platform-stat-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
}

.platform-stat-active {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.platform-stat-info {
  display: flex;
  flex-direction: column;
}

.platform-stat-value {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--text-primary);
}

.platform-stat-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.platform-toolbar {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.platform-search {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-sm);
  font-size: var(--text-base);
  color: var(--text-primary);
}

.platform-search:focus {
  outline: none;
  border-color: var(--lumi-primary);
}

.platform-filter-group {
  display: flex;
  gap: var(--space-1);
}

.platform-filter-btn {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
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
  gap: var(--space-2);
}

.platform-instance-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-3);
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
  gap: var(--space-2);
  min-width: 0;
  flex: 1;
}

.pi-icon {
  width: var(--space-7);
  height: var(--space-7);
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
  background: var(--task-amber-soft);
  color: var(--lumi-amber);
}

.pi-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.pi-name-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.pi-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
}

.pi-status {
  font-size: var(--text-2xs);
  font-weight: 600;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-xs);
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
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.pi-dot {
  opacity: 0.5;
}

.pi-error {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  color: var(--lumi-danger);
}

.pi-actions {
  display: flex;
  gap: var(--space-1);
  flex-shrink: 0;
}

.pi-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-xs);
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
  gap: var(--space-2);
  padding: var(--space-7) var(--space-5);
  color: var(--text-muted);
}

.platform-empty-icon {
  opacity: 0.4;
}

.platform-empty-text {
  font-size: var(--text-base);
}

.platform-empty-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  background: var(--lumi-primary);
  color: var(--text-inverse);
  transition: all var(--transition-fast);
}

.platform-empty-btn:hover {
  background: var(--lumi-primary-hover);
}

.tts-spin {
  animation: tts-spin 1s linear infinite;
  color: var(--lumi-primary);
}

@keyframes tts-spin {
  to { transform: rotate(360deg); }
}

.platform-dialog-overlay {
  position: fixed;
  inset: 0;
  background: var(--overlay-bg);
  backdrop-filter: blur(var(--space-1));
  -webkit-backdrop-filter: blur(var(--space-1));
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: platform-fade-in var(--duration-fast) var(--ease-in-out);
}

.platform-dialog {
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  width: 560px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  animation: platform-slide-up var(--duration-slow) var(--ease-default);
  box-shadow: 0 var(--space-6) var(--space-9) calc(var(--space-3) * -1) var(--overlay-subtle);
}

.platform-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-light);
}

.platform-dialog-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.platform-dialog-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  background: transparent;
  border: none;
}

.platform-dialog-close:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.platform-dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5);
}

.platform-dialog-desc {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-bottom: var(--space-4);
}

.adapter-type-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.adapter-type-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-3);
  background: var(--surface, var(--workspace-panel));
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
}

.adapter-type-item:hover {
  border-color: var(--lumi-primary);
}

.adapter-type-icon {
  width: var(--space-8);
  height: var(--space-8);
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
  background: var(--task-amber-soft);
  color: var(--lumi-amber);
}

.adapter-type-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.adapter-type-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
}

.adapter-type-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.adapter-type-cat {
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-xs);
  font-size: var(--text-2xs);
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
  background: var(--task-amber-soft);
  color: var(--lumi-amber);
}

.platform-form-group {
  margin-bottom: var(--space-4);
}

.platform-form-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.platform-form-input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--surface, var(--workspace-panel));
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  font-size: var(--text-base);
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
  padding: var(--space-2) var(--space-3);
  background: var(--surface, var(--workspace-panel));
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  font-size: var(--text-base);
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
  gap: var(--space-4);
}

.platform-form-hint {
  display: block;
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: var(--space-2);
  line-height: 1.4;
}

.platform-config-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.platform-config-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.platform-config-label {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--text-muted);
}

.platform-status-display {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-base);
}

.platform-error-display {
  padding: var(--space-2) var(--space-3);
  background: var(--task-red-soft);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--lumi-danger);
}

.platform-type-badge {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--lumi-primary-light);
  border-radius: var(--radius-sm);
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--lumi-primary);
}

.platform-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--border-light);
}

.platform-dialog-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  border: none;
}

.platform-dialog-btn.cancel {
  background: var(--surface, var(--workspace-panel));
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.platform-dialog-btn.cancel:hover:not(:disabled) {
  background: var(--surface-hover);
}

.platform-dialog-btn.confirm {
  background: var(--lumi-primary);
  color: var(--text-inverse);
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
    transform: translateY(var(--space-3)) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
