<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Globe, Eye, RefreshCw, Search, Server, Shield, Zap,
  Play, Square, Plus, Trash2, Radio, Cable, Link, MessageCircle,
  Send, Gamepad2, Home, Smartphone, Settings, X,
  AlertCircle, CheckCircle2, XCircle, Clock,
  FileText, MessageSquare, Trash
} from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import type { PlatformAdapterType, PlatformInstance } from '../../types'

const store = usePlatformStore()

const searchQuery = ref('')
const activeFilter = ref<'all' | 'active' | 'disconnected'>('all')
const rightTab = ref<'conversations' | 'logs'>('logs')
const showAddDialog = ref(false)
const showConfigDialog = ref(false)
const selectedAdapterType = ref<PlatformAdapterType | null>(null)
const newPlatformName = ref('')
const newPlatformConfig = ref<Record<string, any>>({})
const editingInstance = ref<PlatformInstance | null>(null)
const editConfig = ref<Record<string, any>>({})

const filteredInstances = computed(() => {
  let list = store.instances
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(i => i.name.toLowerCase().includes(q) || i.displayName.toLowerCase().includes(q))
  }
  if (activeFilter.value === 'active') {
    list = list.filter(i => i.status === 'running')
  } else if (activeFilter.value === 'disconnected') {
    list = list.filter(i => i.status !== 'running')
  }
  return list
})

const iconMap: Record<string, any> = {
  Globe, Radio, Cable, Link, MessageCircle, Send, Gamepad2, Home, Smartphone,
}

const getIcon = (iconName: string) => {
  return iconMap[iconName] || Globe
}

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
    const diffDay = Math.floor(diffHour / 24)
    return `${diffDay} 天前`
  } catch {
    return '未同步'
  }
}

const formatLogTime = (ts: string) => {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ts
  }
}

const formatLogDate = (ts: string) => {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    const today = new Date()
    if (d.toDateString() === today.toDateString()) return ''
    return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) + ' '
  } catch {
    return ''
  }
}

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
    case 'error': return 'var(--lumi-error, #ef4444)'
    default: return 'var(--text-muted)'
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

const getLogLevelClass = (level: string) => {
  switch (level) {
    case 'error': return 'log-error'
    case 'warning': return 'log-warning'
    case 'success': return 'log-success'
    default: return 'log-info'
  }
}

const getLogEventLabel = (event: string) => {
  const map: Record<string, string> = {
    instance_created: '实例创建',
    instance_started: '启动成功',
    instance_stopped: '停止实例',
    instance_removed: '实例移除',
    start_failed: '启动失败',
    stop_failed: '停止失败',
    handshake_init: '握手初始化',
    handshake_ok: '握手成功',
    handshake_fail: '握手失败',
    connection_established: '连接建立',
    connection_lost: '连接断开',
    message_received: '消息接收',
    message_sent: '消息发送',
    message_failed: '消息失败',
    config_updated: '配置更新',
    error: '异常',
  }
  return map[event] || event
}

const openAddDialog = (adapterType: PlatformAdapterType) => {
  selectedAdapterType.value = adapterType
  newPlatformName.value = adapterType.displayName
  newPlatformConfig.value = { ...adapterType.configTemplate }
  showAddDialog.value = true
}

const closeAddDialog = () => {
  showAddDialog.value = false
  selectedAdapterType.value = null
  newPlatformName.value = ''
  newPlatformConfig.value = {}
}

const handleCreate = async () => {
  if (!selectedAdapterType.value || !newPlatformName.value.trim()) return
  try {
    await store.createInstance({
      adapterType: selectedAdapterType.value.name,
      name: newPlatformName.value.trim(),
      config: newPlatformConfig.value,
      enable: true,
    })
    closeAddDialog()
  } catch (e: any) {
    console.error('Failed to create platform instance:', e)
  }
}

const openConfigDialog = (instance: PlatformInstance) => {
  editingInstance.value = instance
  editConfig.value = { ...instance.config }
  showConfigDialog.value = true
}

const closeConfigDialog = () => {
  showConfigDialog.value = false
  editingInstance.value = null
  editConfig.value = {}
}

const handleSaveConfig = async () => {
  if (!editingInstance.value) return
  try {
    await store.updateInstance(editingInstance.value.id, {
      name: editingInstance.value.name,
      config: editConfig.value,
    })
    closeConfigDialog()
  } catch (e: any) {
    console.error('Failed to update platform instance:', e)
  }
}

const handleToggleStatus = async (instance: PlatformInstance) => {
  try {
    if (instance.status === 'running') {
      await store.stopInstance(instance.id)
    } else {
      await store.startInstance(instance.id)
    }
  } catch (e: any) {
    console.error('Failed to toggle platform status:', e)
  }
}

const handleDelete = async (instance: PlatformInstance) => {
  if (instance.status === 'running') {
    await store.stopInstance(instance.id)
  }
  await store.deleteInstance(instance.id)
}

const handleRefresh = async () => {
  await store.refreshAll()
}

const handleSelectInstance = (instance: PlatformInstance) => {
  store.selectInstance(instance.id)
  rightTab.value = 'logs'
}

const handleClearLogs = async () => {
  if (store.selectedInstanceId) {
    await store.clearLogs(store.selectedInstanceId)
  }
}

const handleLogLevelFilter = (level: string | null) => {
  store.setLogLevelFilter(level)
}

onMounted(() => {
  store.refreshAll()
})
</script>

<template>
  <div class="platform-view">
    <div class="platform-header">
      <div class="header-info">
        <h1 class="header-title">平台接入</h1>
        <p class="header-desc">第三方平台对话浏览 — 管理平台连接、查看对话与握手日志</p>
      </div>
      <div class="header-actions">
        <button class="action-btn secondary" @click="handleRefresh" :disabled="store.loading">
          <RefreshCw :size="15" :class="{ spinning: store.loading }" />
          <span>刷新</span>
        </button>
        <button class="action-btn primary" @click="showAddDialog = true">
          <Plus :size="15" />
          <span>添加平台</span>
        </button>
      </div>
    </div>

    <div class="platform-stats">
      <div class="stat-card" style="animation-delay: 0.05s">
        <div class="stat-icon"><Server :size="18" /></div>
        <div class="stat-info">
          <span class="stat-value">{{ store.stats.totalPlatforms }}</span>
          <span class="stat-label">已接入平台</span>
        </div>
      </div>
      <div class="stat-card" style="animation-delay: 0.10s">
        <div class="stat-icon active"><Zap :size="18" /></div>
        <div class="stat-info">
          <span class="stat-value">{{ store.stats.activeConnections }}</span>
          <span class="stat-label">活跃连接</span>
        </div>
      </div>
      <div class="stat-card" style="animation-delay: 0.15s">
        <div class="stat-icon"><Shield :size="18" /></div>
        <div class="stat-info">
          <span class="stat-value">{{ store.stats.totalMessages }}</span>
          <span class="stat-label">消息总量</span>
        </div>
      </div>
    </div>

    <div class="platform-content">
      <div class="platform-list-panel">
        <div class="panel-toolbar">
          <div class="search-box">
            <Search :size="14" class="search-icon" />
            <input v-model="searchQuery" type="text" placeholder="搜索平台..." class="search-input" />
          </div>
          <div class="filter-group">
            <button :class="['filter-btn', { active: activeFilter === 'all' }]" @click="activeFilter = 'all'">全部</button>
            <button :class="['filter-btn', { active: activeFilter === 'active' }]" @click="activeFilter = 'active'">活跃</button>
            <button :class="['filter-btn', { active: activeFilter === 'disconnected' }]" @click="activeFilter = 'disconnected'">断开</button>
          </div>
        </div>

        <div class="platform-cards">
          <div
            v-for="(p, idx) in filteredInstances"
            :key="p.id"
            :class="['platform-card', { disconnected: p.status !== 'running', selected: store.selectedInstanceId === p.id }]"
            :style="{ animationDelay: (0.08 + idx * 0.04) + 's' }"
            @click="handleSelectInstance(p)"
          >
            <div class="card-top">
              <div class="card-icon" :class="p.category">
                <component :is="getIcon(p.icon)" :size="16" />
              </div>
              <div class="card-info">
                <span class="card-name">{{ p.name }}</span>
                <span class="card-sync">{{ formatLastSync(p.lastSync) }}</span>
              </div>
              <span :class="['status-dot', p.status]" :title="getStatusLabel(p.status)"></span>
            </div>
            <div class="card-bottom">
              <span class="card-messages">{{ p.messageCount }} 条消息</span>
              <div class="card-actions">
                <button
                  class="card-action-btn"
                  :class="p.status === 'running' ? 'stop' : 'start'"
                  @click.stop="handleToggleStatus(p)"
                  :title="p.status === 'running' ? '停止' : '启动'"
                >
                  <Square v-if="p.status === 'running'" :size="12" />
                  <Play v-else :size="12" />
                </button>
                <button class="card-action-btn config" @click.stop="openConfigDialog(p)" title="配置">
                  <Settings :size="12" />
                </button>
                <button class="card-action-btn delete" @click.stop="handleDelete(p)" title="删除">
                  <Trash2 :size="12" />
                </button>
              </div>
            </div>
            <div v-if="p.errorMessage" class="card-error">
              <AlertCircle :size="11" />
              <span>{{ p.errorMessage }}</span>
            </div>
          </div>

          <div v-if="filteredInstances.length === 0" class="empty-state">
            <Globe :size="32" class="empty-icon" />
            <span class="empty-text">暂无平台实例</span>
            <button class="empty-btn" @click="showAddDialog = true">
              <Plus :size="14" />
              添加平台
            </button>
          </div>
        </div>
      </div>

      <div class="detail-panel">
        <div class="detail-tabs">
          <button :class="['detail-tab', { active: rightTab === 'conversations' }]" @click="rightTab = 'conversations'">
            <MessageSquare :size="14" />
            <span>对话</span>
            <span class="tab-count">{{ store.selectedConversations.length }}</span>
          </button>
          <button :class="['detail-tab', { active: rightTab === 'logs' }]" @click="rightTab = 'logs'">
            <FileText :size="14" />
            <span>日志</span>
            <span class="tab-count">{{ store.logTotal }}</span>
          </button>
          <div class="detail-tab-actions">
            <template v-if="rightTab === 'logs'">
              <div class="log-filter-group">
                <button :class="['log-filter-btn', { active: !store.logLevelFilter }]" @click="handleLogLevelFilter(null)">全部</button>
                <button :class="['log-filter-btn', { active: store.logLevelFilter === 'error' }]" @click="handleLogLevelFilter('error')">错误</button>
                <button :class="['log-filter-btn', { active: store.logLevelFilter === 'warning' }]" @click="handleLogLevelFilter('warning')">警告</button>
                <button :class="['log-filter-btn', { active: store.logLevelFilter === 'success' }]" @click="handleLogLevelFilter('success')">成功</button>
              </div>
              <button v-if="store.selectedInstanceId" class="tab-action-btn" @click="handleClearLogs" title="清空日志">
                <Trash :size="13" />
              </button>
            </template>
          </div>
        </div>

        <div v-if="rightTab === 'conversations'" class="detail-body">
          <div v-if="store.selectedInstance" class="detail-badge">
            <component :is="getIcon(store.selectedInstance.icon)" :size="12" />
            <span>{{ store.selectedInstance.name }}</span>
          </div>
          <div class="conv-list">
            <div v-for="c in store.selectedConversations" :key="c.id" class="conv-item">
              <div class="conv-item-header">
                <span class="conv-item-platform">{{ c.platformName }}</span>
                <span class="conv-item-time">{{ c.time }}</span>
              </div>
              <span class="conv-item-title">{{ c.title }}</span>
              <span class="conv-item-preview">{{ c.preview }}</span>
            </div>
            <div v-if="store.selectedConversations.length === 0" class="detail-empty">
              <Eye :size="24" />
              <span>选择平台查看对话记录</span>
            </div>
          </div>
          <div class="detail-notice">
            <Eye :size="14" />
            <span>只读模式 — 对话来自第三方平台推送</span>
          </div>
        </div>

        <div v-if="rightTab === 'logs'" class="detail-body">
          <div class="log-list">
            <div v-for="log in store.logs" :key="log.id" :class="['log-entry', getLogLevelClass(log.level)]">
              <div class="log-header">
                <span :class="['log-level', log.level]">{{ log.level.toUpperCase() }}</span>
                <span class="log-event">{{ getLogEventLabel(log.event) }}</span>
                <span class="log-time">{{ formatLogDate(log.timestamp) }}{{ formatLogTime(log.timestamp) }}</span>
              </div>
              <div class="log-message">{{ log.message }}</div>
              <div v-if="Object.keys(log.details).length > 0" class="log-details">
                <template v-for="(val, key) in log.details" :key="key">
                  <span class="log-detail-item">
                    <span class="log-detail-key">{{ key }}</span>:
                    <span class="log-detail-val">{{ typeof val === 'object' ? JSON.stringify(val) : val }}</span>
                  </span>
                </template>
              </div>
            </div>
            <div v-if="store.logs.length === 0" class="detail-empty">
              <FileText :size="24" />
              <span>{{ store.selectedInstanceId ? '暂无日志记录' : '选择平台查看日志' }}</span>
            </div>
          </div>
          <div class="detail-notice">
            <FileText :size="14" />
            <span>平台日志 — 连接握手、消息收发、异常记录</span>
          </div>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="showAddDialog" class="dialog-overlay" @click.self="closeAddDialog">
        <div class="dialog">
          <div class="dialog-header">
            <h2 class="dialog-title">添加平台</h2>
            <button class="dialog-close" @click="closeAddDialog"><X :size="18" /></button>
          </div>

          <div v-if="!selectedAdapterType" class="dialog-body">
            <p class="dialog-desc">选择要接入的平台类型：</p>
            <div class="adapter-type-grid">
              <button
                v-for="at in store.adapterTypes"
                :key="at.name"
                class="adapter-type-card"
                @click="openAddDialog(at)"
              >
                <div class="atc-icon" :class="at.category">
                  <component :is="getIcon(at.icon)" :size="20" />
                </div>
                <div class="atc-info">
                  <span class="atc-name">{{ at.displayName }}</span>
                  <span class="atc-desc">{{ at.description }}</span>
                </div>
                <span class="atc-category" :class="at.category">{{ at.category === 'social' ? '社交' : at.category === 'iot' ? 'IoT' : '通用' }}</span>
              </button>
            </div>
          </div>

          <div v-else class="dialog-body">
            <div class="form-group">
              <label class="form-label">平台名称</label>
              <input v-model="newPlatformName" type="text" class="form-input" placeholder="输入平台实例名称" />
            </div>
            <div class="form-group">
              <label class="form-label">平台类型</label>
              <div class="form-type-badge">
                <component :is="getIcon(selectedAdapterType.icon)" :size="14" />
                <span>{{ selectedAdapterType.displayName }}</span>
              </div>
            </div>
            <div v-if="Object.keys(selectedAdapterType.configMetadata).length > 0" class="form-group">
              <label class="form-label">连接配置</label>
              <div class="config-fields">
                <div v-for="(meta, key) in selectedAdapterType.configMetadata" :key="key" class="config-field">
                  <label class="config-field-label">{{ meta.label || key }}</label>
                  <input
                    v-model="newPlatformConfig[key]"
                    :type="meta.type === 'password' ? 'password' : meta.type === 'number' ? 'number' : 'text'"
                    class="form-input"
                    :placeholder="meta.label || key"
                  />
                </div>
              </div>
            </div>
          </div>

          <div class="dialog-footer">
            <button class="dialog-btn cancel" @click="closeAddDialog">取消</button>
            <button
              v-if="selectedAdapterType"
              class="dialog-btn confirm"
              @click="handleCreate"
              :disabled="!newPlatformName.trim()"
            >确认添加</button>
            <button v-else class="dialog-btn confirm" @click="closeAddDialog">关闭</button>
          </div>
        </div>
      </div>

      <div v-if="showConfigDialog && editingInstance" class="dialog-overlay" @click.self="closeConfigDialog">
        <div class="dialog">
          <div class="dialog-header">
            <h2 class="dialog-title">平台配置 - {{ editingInstance.name }}</h2>
            <button class="dialog-close" @click="closeConfigDialog"><X :size="18" /></button>
          </div>
          <div class="dialog-body">
            <div class="form-group">
              <label class="form-label">状态</label>
              <div class="status-display">
                <component :is="getStatusIcon(editingInstance.status)" :size="16" :style="{ color: getStatusColor(editingInstance.status) }" />
                <span :style="{ color: getStatusColor(editingInstance.status) }">{{ getStatusLabel(editingInstance.status) }}</span>
              </div>
            </div>
            <div v-if="Object.keys(editConfig).length > 0" class="form-group">
              <label class="form-label">连接配置</label>
              <div class="config-fields">
                <div v-for="(_val, key) in editConfig" :key="key" class="config-field">
                  <label class="config-field-label">{{ key }}</label>
                  <input v-model="editConfig[key]" type="text" class="form-input" />
                </div>
              </div>
            </div>
            <div v-if="editingInstance.errorMessage" class="form-group">
              <label class="form-label">错误信息</label>
              <div class="error-display">{{ editingInstance.errorMessage }}</div>
            </div>
          </div>
          <div class="dialog-footer">
            <button class="dialog-btn cancel" @click="closeConfigDialog">取消</button>
            <button class="dialog-btn confirm" @click="handleSaveConfig">保存配置</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.platform-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px 28px;
  gap: 20px;
  overflow-y: auto;
}

.platform-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.header-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.action-btn.primary {
  background: var(--lumi-primary);
  color: white;
}

.action-btn.primary:hover {
  background: var(--lumi-primary-hover);
}

.action-btn.secondary {
  background: var(--surface);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.action-btn.secondary:hover {
  background: var(--surface-hover);
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.platform-stats {
  display: flex;
  gap: 16px;
}

.stat-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  animation: content-fade-up 0.5s cubic-bezier(0.4, 0, 0.2, 1) both;
}

.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon.active {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted);
}

.platform-content {
  flex: 1;
  display: flex;
  gap: 16px;
  min-height: 0;
}

.platform-list-panel {
  width: 360px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-toolbar {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  background: transparent;
  font-size: 13px;
  color: var(--text-primary);
}

.search-input::placeholder {
  color: var(--text-muted);
}

.filter-group {
  display: flex;
  gap: 4px;
}

.filter-btn {
  padding: 5px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-muted);
  background: var(--surface);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.filter-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  border-color: var(--lumi-primary);
}

.platform-cards {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.platform-card {
  padding: 14px 16px;
  background: var(--surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
  animation: content-fade-up 0.45s cubic-bezier(0.4, 0, 0.2, 1) both;
}

.platform-card:hover {
  border-color: var(--lumi-primary);
  box-shadow: var(--shadow-glow-sm);
}

.platform-card.selected {
  border-color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.platform-card.disconnected {
  opacity: 0.7;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.card-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-icon.social {
  background: var(--task-purple-soft);
  color: var(--task-purple);
}

.card-icon.iot {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.card-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.card-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.card-sync {
  font-size: 11px;
  color: var(--text-muted);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--lumi-success);
  flex-shrink: 0;
}

.status-dot.running {
  background: var(--lumi-success);
}

.status-dot.stopped,
.status-dot.pending {
  background: var(--text-muted);
}

.status-dot.error {
  background: var(--lumi-danger);
}

.card-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-messages {
  font-size: 11px;
  color: var(--text-muted);
}

.card-actions {
  display: flex;
  gap: 4px;
}

.card-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  cursor: pointer;
  transition: all var(--transition-fast);
  background: transparent;
  color: var(--text-muted);
}

.card-action-btn.start {
  color: var(--lumi-success);
}

.card-action-btn.start:hover {
  background: var(--task-green-soft);
}

.card-action-btn.stop {
  color: var(--lumi-danger);
}

.card-action-btn.stop:hover {
  background: var(--task-red-soft);
}

.card-action-btn.config {
  color: var(--lumi-primary);
}

.card-action-btn.config:hover {
  background: var(--lumi-primary-light);
}

.card-action-btn.delete {
  color: var(--text-muted);
}

.card-action-btn.delete:hover {
  background: var(--task-red-soft);
  color: var(--lumi-danger);
}

.card-error {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  padding: 6px 8px;
  background: var(--task-red-soft);
  border-radius: 4px;
  font-size: 11px;
  color: var(--lumi-danger);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 20px;
  color: var(--text-muted);
}

.empty-icon {
  opacity: 0.4;
}

.empty-text {
  font-size: 13px;
}

.empty-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  background: var(--lumi-primary);
  color: white;
  transition: all var(--transition-fast);
}

.empty-btn:hover {
  background: var(--lumi-primary-hover);
}

.detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  overflow: hidden;
}

.detail-tabs {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-light);
}

.detail-tab {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.detail-tab:hover {
  color: var(--text-secondary);
  background: var(--surface-hover);
}

.detail-tab.active {
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.tab-count {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--border-light);
  color: var(--text-muted);
}

.detail-tab.active .tab-count {
  background: var(--lumi-primary-glow);
  color: var(--lumi-primary);
}

.detail-tab-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
}

.log-filter-group {
  display: flex;
  gap: 2px;
}

.log-filter-btn {
  padding: 3px 8px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 500;
  color: var(--text-muted);
  background: transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.log-filter-btn:hover {
  background: var(--surface-hover);
}

.log-filter-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.tab-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 4px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab-action-btn:hover {
  background: var(--task-red-soft);
  color: var(--lumi-danger);
}

.detail-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.detail-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  font-size: 11px;
  font-weight: 500;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  border-bottom: 1px solid var(--border-light);
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conv-item {
  padding: 12px 14px;
  border-radius: var(--radius-md);
  cursor: default;
  transition: background var(--transition-fast);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.conv-item:hover {
  background: var(--surface-hover);
}

.conv-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.conv-item-platform {
  font-size: 11px;
  color: var(--lumi-primary);
  font-weight: 500;
}

.conv-item-time {
  font-size: 11px;
  color: var(--text-muted);
}

.conv-item-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.conv-item-preview {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 60px 20px;
  color: var(--text-muted);
  font-size: 13px;
}

.detail-notice {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px;
  background: var(--bg-secondary);
  color: var(--text-muted);
  font-size: 11px;
  border-top: 1px solid var(--border-light);
}

.log-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
}

.log-entry {
  padding: 8px 12px;
  border-radius: 4px;
  margin-bottom: 2px;
  transition: background var(--transition-fast);
  border-left: 3px solid transparent;
}

.log-entry:hover {
  background: var(--surface-hover);
}

.log-entry.log-info {
  border-left-color: var(--lumi-primary);
}

.log-entry.log-success {
  border-left-color: var(--lumi-success);
}

.log-entry.log-warning {
  border-left-color: var(--lumi-amber);
}

.log-entry.log-error {
  border-left-color: var(--lumi-danger);
  background: var(--task-red-soft);
}

.log-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 3px;
}

.log-level {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
  letter-spacing: 0.5px;
}

.log-level.info {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.log-level.success {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.log-level.warning {
  background: var(--lumi-amber-soft);
  color: var(--lumi-amber);
}

.log-level.error {
  background: var(--task-red-soft);
  color: var(--lumi-danger);
}

.log-event {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
}

.log-time {
  font-size: 10px;
  color: var(--text-muted);
  margin-left: auto;
}

.log-message {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.5;
  padding-left: 2px;
}

.log-details {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
  padding-left: 2px;
}

.log-detail-item {
  font-size: 10px;
  color: var(--text-muted);
}

.log-detail-key {
  color: var(--lumi-primary);
  font-weight: 500;
}

.log-detail-val {
  color: var(--text-secondary);
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: var(--overlay-bg);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fade-in 0.2s ease-in-out;
}

.dialog {
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  width: 560px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  animation: content-fade-up 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 24px 48px -12px var(--overlay-subtle), 0 0 0 1px var(--overlay-subtle);
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-light);
}

.dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.dialog-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.dialog-close:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.dialog-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.adapter-type-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.adapter-type-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
}

.adapter-type-card:hover {
  border-color: var(--lumi-primary);
  box-shadow: var(--shadow-glow-sm);
}

.atc-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.atc-icon.social {
  background: var(--task-purple-soft);
  color: var(--task-purple);
}

.atc-icon.iot {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.atc-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.atc-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.atc-desc {
  font-size: 11px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.atc-category {
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
  flex-shrink: 0;
}

.atc-category.social {
  background: var(--task-purple-soft);
  color: var(--task-purple);
}

.atc-category.iot {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.atc-category.general {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.form-group {
  margin-bottom: 16px;
}

.form-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.form-input {
  width: 100%;
  padding: 8px 12px;
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-primary);
  transition: border-color var(--transition-fast);
}

.form-input:focus {
  outline: none;
  border-color: var(--lumi-primary);
}

.form-type-badge {
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

.config-fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.config-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.config-field-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted);
}

.status-display {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
}

.error-display {
  padding: 8px 12px;
  background: var(--task-red-soft);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--lumi-danger);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-light);
}

.dialog-btn {
  padding: 8px 20px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.dialog-btn.cancel {
  background: var(--surface);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.dialog-btn.cancel:hover {
  background: var(--surface-hover);
}

.dialog-btn.confirm {
  background: var(--lumi-primary);
  color: white;
}

.dialog-btn.confirm:hover {
  background: var(--lumi-primary-hover);
}

.dialog-btn.confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@keyframes content-fade-up {
  from {
    opacity: 0;
    transform: translateY(14px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
