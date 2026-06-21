<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  Globe, Eye, RefreshCw, Search, Server, Shield, Zap,
  Play, Square, Plus, Trash2, Radio, Cable, Link, MessageCircle,
  Send, Gamepad2, Home, Smartphone, Settings, X,
  AlertCircle, CheckCircle2, XCircle, Clock,
  FileText, MessageSquare, Trash, ChevronLeft, Image as ImageIcon,
  Cpu, RotateCcw, Bot, User, Timer, Layers
} from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import { useModelStore } from '../../stores/model'
import type { PlatformAdapterType, PlatformInstance, PlatformModelConfig } from '../../types'

const store = usePlatformStore()
const modelStore = useModelStore()

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
const modelConfigLoading = ref(false)
const modelConfigSaving = ref(false)
const modelEditConfig = ref<PlatformModelConfig>({})
const expandedLogIds = ref<Set<string>>(new Set())
const conversationMessagesRef = ref<HTMLElement | null>(null)

const availableProviders = computed(() => modelStore.providers)
const isGameCategory = computed(() => {
  const inst = editingInstance.value
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
    connection_attempting: '尝试连接',
    connection_established: '连接建立',
    connection_lost: '连接断开',
    connection_reconnecting: '重新连接',
    message_received: '消息接收',
    message_sent: '消息发送',
    message_failed: '消息失败',
    llm_call_start: 'LLM 调用开始',
    llm_call_success: 'LLM 调用成功',
    llm_call_failed: 'LLM 调用失败',
    model_config_updated: '模型配置更新',
    config_updated: '配置更新',
    screenshot_received: '截图接收',
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

const openConfigDialog = async (instance: PlatformInstance) => {
  editingInstance.value = instance
  editConfig.value = { ...instance.config }
  delete editConfig.value.model_config
  delete editConfig.value.enable
  modelEditConfig.value = {}
  showConfigDialog.value = true
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
  } catch (e: any) {
    console.error('Failed to load model config:', e)
  } finally {
    modelConfigLoading.value = false
  }
}

const closeConfigDialog = () => {
  showConfigDialog.value = false
  editingInstance.value = null
  editConfig.value = {}
  modelEditConfig.value = {}
}

const handleSaveConfig = async () => {
  if (!editingInstance.value) return
  try {
    await store.updateInstance(editingInstance.value.id, {
      name: editingInstance.value.name,
      config: editConfig.value,
    })
    if (Object.keys(modelEditConfig.value).length > 0) {
      await store.updateInstanceModelConfig(editingInstance.value.id, modelEditConfig.value)
    }
    closeConfigDialog()
  } catch (e: any) {
    console.error('Failed to update platform instance:', e)
  }
}

const handleResetModelConfig = async () => {
  if (!editingInstance.value) return
  modelConfigSaving.value = true
  try {
    await store.updateInstanceModelConfig(editingInstance.value.id, {
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
  } catch (e: any) {
    console.error('Failed to reset model config:', e)
  } finally {
    modelConfigSaving.value = false
  }
}

const handleProviderChange = () => {
  modelEditConfig.value.model = ''
}

const handleSelectConversation = (conversationId: string) => {
  store.selectConversation(conversationId)
}

const handleBackToConversationList = () => {
  store.selectConversation(null)
}

const toggleLogExpand = (logId: string) => {
  if (expandedLogIds.value.has(logId)) {
    expandedLogIds.value.delete(logId)
  } else {
    expandedLogIds.value.add(logId)
  }
}

const isLogExpanded = (logId: string) => expandedLogIds.value.has(logId)

const formatMessageTime = (ts: string) => {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return ts
  }
}

const getRoleIcon = (role: string) => {
  return role === 'assistant' ? Bot : User
}

const getRoleLabel = (role: string) => {
  return role === 'assistant' ? 'LuomiNest' : role === 'system' ? '系统' : '用户'
}

const getLogDetailEntries = (details: Record<string, unknown>) => {
  return Object.entries(details).filter(([_k, v]) => v !== null && v !== undefined && v !== '')
}

const formatLogDetailValue = (val: unknown): string => {
  if (val === null || val === undefined) return ''
  if (typeof val === 'object') return JSON.stringify(val, null, 2)
  return String(val)
}

const isPerformanceLog = (event: string) => {
  return ['llm_call_success', 'llm_call_failed', 'message_sent'].includes(event)
}

const isErrorLog = (event: string, level: string) => {
  return level === 'error' || ['message_failed', 'start_failed', 'stop_failed', 'connection_lost', 'handshake_fail', 'llm_call_failed'].includes(event)
}

const isTraceableLog = (event: string) => {
  return ['message_received', 'llm_call_start', 'llm_call_success', 'llm_call_failed', 'message_sent', 'message_failed'].includes(event)
}

const getPerfLabel = (key: string) => {
  const map: Record<string, string> = {
    elapsed: '总耗时',
    llm_elapsed: 'LLM 耗时',
    total_tokens: '总 Tokens',
    prompt_tokens: 'Prompt Tokens',
    completion_tokens: 'Completion Tokens',
    retry_count: '重试次数',
  }
  return map[key] || key
}

const getPerfUnit = (key: string) => {
  if (key.includes('elapsed')) return ' ms'
  if (key.includes('tokens')) return ''
  if (key === 'retry_count') return ' 次'
  return ''
}

watch(() => store.selectedConversationDetail, () => {
  if (conversationMessagesRef.value) {
    conversationMessagesRef.value.scrollTop = conversationMessagesRef.value.scrollHeight
  }
})

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

        <div v-if="rightTab === 'conversations'" class="detail-body conversations-body">
          <div v-if="!store.selectedConversationId" class="conv-list-pane">
            <div v-if="store.selectedInstance" class="detail-badge">
              <component :is="getIcon(store.selectedInstance.icon)" :size="12" />
              <span>{{ store.selectedInstance.name }}</span>
              <span class="badge-count">{{ store.selectedConversations.length }} 个对话</span>
            </div>
            <div class="conv-list">
              <div
                v-for="c in store.selectedConversations"
                :key="c.id"
                class="conv-item clickable"
                @click="handleSelectConversation(c.id)"
              >
                <div class="conv-item-header">
                  <span class="conv-item-platform">
                    <MessageCircle :size="11" />
                    {{ c.platformName }}
                  </span>
                  <span class="conv-item-time">{{ formatMessageTime(c.time) }}</span>
                </div>
                <span class="conv-item-title">{{ c.title || '未命名对话' }}</span>
                <div class="conv-item-footer">
                  <span class="conv-item-preview">{{ c.preview || '暂无消息' }}</span>
                  <span class="conv-item-count">{{ c.messageCount }} 条</span>
                </div>
              </div>
              <div v-if="store.selectedConversations.length === 0" class="detail-empty">
                <Eye :size="24" />
                <span>{{ store.selectedInstanceId ? '暂无对话记录' : '选择平台查看对话记录' }}</span>
              </div>
            </div>
            <div class="detail-notice">
              <Eye :size="14" />
              <span>只读模式 — 对话来自第三方平台推送</span>
            </div>
          </div>

          <div v-else class="conv-detail-pane">
            <div class="conv-detail-header">
              <button class="back-btn" @click="handleBackToConversationList" title="返回对话列表">
                <ChevronLeft :size="16" />
              </button>
              <div class="conv-detail-title">
                <span class="title-text">{{ store.selectedConversationDetail?.title || '对话详情' }}</span>
                <span v-if="store.selectedConversationDetail" class="title-meta">
                  {{ store.selectedConversationDetail.platformName }}
                  <template v-if="store.selectedConversationDetail.senderName">
                    · {{ store.selectedConversationDetail.senderName }}
                  </template>
                  <template v-if="store.selectedConversationDetail.isGroup"> · 群聊</template>
                </span>
              </div>
              <span class="conv-detail-count">
                {{ store.selectedConversationDetail?.messageCount || 0 }} 条消息
              </span>
            </div>

            <div v-if="store.conversationLoading" class="conv-loading">
              <RefreshCw :size="20" class="spinning" />
              <span>加载消息中...</span>
            </div>

            <div v-else-if="store.selectedConversationDetail" ref="conversationMessagesRef" class="conv-messages">
              <div
                v-for="msg in store.selectedConversationDetail.messages"
                :key="msg.id"
                :class="['msg-row', msg.role]"
              >
                <div class="msg-avatar">
                  <component :is="getRoleIcon(msg.role)" :size="14" />
                </div>
                <div class="msg-content-wrap">
                  <div class="msg-meta">
                    <span class="msg-sender">{{ msg.senderName || getRoleLabel(msg.role) }}</span>
                    <span v-if="msg.model" class="msg-model">
                      <Cpu :size="10" />
                      {{ msg.model }}
                    </span>
                    <span class="msg-time">{{ formatMessageTime(msg.timestamp) }}</span>
                  </div>
                  <div class="msg-bubble">
                    <div v-if="msg.content" class="msg-text">{{ msg.content }}</div>
                    <div v-if="msg.imageUrls && msg.imageUrls.length > 0" class="msg-images">
                      <div v-for="(url, idx) in msg.imageUrls" :key="idx" class="msg-image-item">
                        <img :src="url" :alt="`图片 ${idx + 1}`" loading="lazy" />
                      </div>
                    </div>
                    <div v-if="!msg.content && (!msg.imageUrls || msg.imageUrls.length === 0)" class="msg-empty">
                      <ImageIcon :size="14" />
                      <span>空消息</span>
                    </div>
                  </div>
                </div>
              </div>
              <div v-if="store.selectedConversationDetail.messages.length === 0" class="detail-empty">
                <MessageSquare :size="24" />
                <span>对话暂无消息</span>
              </div>
            </div>

            <div v-else class="detail-empty">
              <MessageSquare :size="24" />
              <span>无法加载对话内容</span>
            </div>
          </div>
        </div>

        <div v-if="rightTab === 'logs'" class="detail-body">
          <div class="log-list">
            <div
              v-for="log in store.logs"
              :key="log.id"
              :class="['log-entry', getLogLevelClass(log.level), {
                'log-traceable': isTraceableLog(log.event),
                'log-error-entry': isErrorLog(log.event, log.level),
                'log-performance': isPerformanceLog(log.event),
                'expanded': isLogExpanded(log.id),
              }]"
              @click="toggleLogExpand(log.id)"
            >
              <div class="log-header">
                <span :class="['log-level', log.level]">{{ log.level.toUpperCase() }}</span>
                <span class="log-event">
                  <Layers v-if="isTraceableLog(log.event)" :size="11" class="log-event-icon" />
                  <Timer v-else-if="isPerformanceLog(log.event)" :size="11" class="log-event-icon" />
                  <AlertCircle v-else-if="isErrorLog(log.event, log.level)" :size="11" class="log-event-icon" />
                  {{ getLogEventLabel(log.event) }}
                </span>
                <span class="log-time">{{ formatLogDate(log.timestamp) }}{{ formatLogTime(log.timestamp) }}</span>
                <span v-if="getLogDetailEntries(log.details).length > 0" class="log-expand-hint">
                  {{ isLogExpanded(log.id) ? '收起' : '详情' }}
                </span>
              </div>
              <div class="log-message">{{ log.message }}</div>

              <div v-if="isPerformanceLog(log.event) && getLogDetailEntries(log.details).length > 0" class="log-perf-stats">
                <template v-for="(val, key) in log.details" :key="key">
                  <span v-if="['elapsed', 'llm_elapsed', 'total_tokens', 'prompt_tokens', 'completion_tokens', 'retry_count'].includes(String(key))" class="perf-stat">
                    <span class="perf-key">{{ getPerfLabel(String(key)) }}</span>
                    <span class="perf-val">{{ formatLogDetailValue(val) }}{{ getPerfUnit(String(key)) }}</span>
                  </span>
                </template>
              </div>

              <div v-if="isLogExpanded(log.id) && getLogDetailEntries(log.details).length > 0" class="log-details-expanded">
                <template v-for="(val, key) in log.details" :key="key">
                  <div v-if="String(key) === 'stack_trace'" class="log-stack-trace">
                    <span class="log-detail-key">stack_trace:</span>
                    <pre class="stack-trace-content">{{ formatLogDetailValue(val) }}</pre>
                  </div>
                  <div v-else class="log-detail-row">
                    <span class="log-detail-key">{{ key }}</span>:
                    <span class="log-detail-val">{{ formatLogDetailValue(val) }}</span>
                  </div>
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
            <span>平台日志 — 连接握手、消息收发、LLM 调用、异常详情（点击展开）</span>
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
        <div class="dialog config-dialog">
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

            <div class="form-group">
              <label class="form-label">
                <Cpu :size="12" />
                模型配置
                <span v-if="effectiveModelConfig?.isOverridden" class="badge overridden">独立配置</span>
                <span v-else-if="effectiveModelConfig" class="badge inherited">继承主 Agent</span>
              </label>

              <div v-if="modelConfigLoading" class="model-config-loading">
                <RefreshCw :size="14" class="spinning" />
                <span>加载模型配置...</span>
              </div>

              <div v-else-if="effectiveModelConfig" class="model-config-section">
                <div v-if="isGameCategory" class="vision-hint">
                  <ImageIcon :size="12" />
                  <span>游戏类平台需要支持图片识别（vision）的模型</span>
                </div>

                <div class="model-current-info">
                  <div class="info-row">
                    <span class="info-label">当前生效:</span>
                    <span class="info-value">{{ effectiveModelConfig.effective.providerName || effectiveModelConfig.effective.provider }}</span>
                    <span class="info-sep">/</span>
                    <span class="info-value">{{ effectiveModelConfig.effective.model }}</span>
                    <span
                      :class="['vision-tag', { supported: effectiveModelConfig.effective.supportsMultimodal }]"
                      :title="effectiveModelConfig.effective.supportsMultimodal ? '支持图片识别' : '不支持图片识别'"
                    >
                      {{ effectiveModelConfig.effective.supportsMultimodal ? 'Vision' : 'No Vision' }}
                    </span>
                  </div>
                  <div class="info-row main-agent-info">
                    <span class="info-label">主 Agent 默认:</span>
                    <span class="info-value">{{ effectiveModelConfig.mainAgent.providerName || effectiveModelConfig.mainAgent.provider }}</span>
                    <span class="info-sep">/</span>
                    <span class="info-value">{{ effectiveModelConfig.mainAgent.model }}</span>
                  </div>
                </div>

                <div class="config-fields">
                  <div class="config-field">
                    <label class="config-field-label">供应商 (空 = 继承主 Agent)</label>
                    <select
                      v-model="modelEditConfig.provider"
                      class="form-input form-select"
                      @change="handleProviderChange"
                    >
                      <option value="">继承主 Agent</option>
                      <option v-for="p in availableProviders" :key="p.id" :value="p.id">
                        {{ p.name }}{{ p.isDefault ? ' (默认)' : '' }}
                      </option>
                    </select>
                  </div>
                  <div class="config-field">
                    <label class="config-field-label">模型 (空 = 继承主 Agent)</label>
                    <select v-model="modelEditConfig.model" class="form-input form-select" :disabled="!modelEditConfig.provider">
                      <option value="">继承主 Agent</option>
                      <option v-for="m in availableModels" :key="m.id" :value="m.id">
                        {{ m.name || m.id }}
                      </option>
                    </select>
                  </div>
                  <div class="config-field">
                    <label class="config-field-label">System Prompt (空 = 继承主 Agent)</label>
                    <textarea
                      v-model="modelEditConfig.systemPrompt"
                      class="form-input form-textarea"
                      rows="3"
                      placeholder="留空继承主 Agent 的 System Prompt"
                    ></textarea>
                  </div>
                  <div class="config-field-row">
                    <div class="config-field">
                      <label class="config-field-label">Temperature (空 = 继承)</label>
                      <input
                        v-model.number="modelEditConfig.temperature"
                        type="number"
                        step="0.1"
                        min="0"
                        max="2"
                        class="form-input"
                        placeholder="继承"
                      />
                    </div>
                    <div class="config-field">
                      <label class="config-field-label">Max Tokens (空 = 继承)</label>
                      <input
                        v-model.number="modelEditConfig.maxTokens"
                        type="number"
                        min="1"
                        class="form-input"
                        placeholder="继承"
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
                  <span>重置为继承主 Agent</span>
                </button>
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

/* ===== 对话详情视图 ===== */
.conversations-body {
  display: flex;
  flex-direction: row;
  padding: 0;
}

.conv-list-pane,
.conv-detail-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.conv-list-pane {
  border-right: 1px solid var(--border-light);
}

.conv-list-pane .detail-badge {
  border-bottom: 1px solid var(--border-light);
}

.badge-count {
  margin-left: auto;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: var(--lumi-primary-glow);
  color: var(--lumi-primary);
  font-weight: 500;
}

.conv-item.clickable {
  cursor: pointer;
}

.conv-item.clickable:hover {
  background: var(--surface-hover);
  border-left: 2px solid var(--lumi-primary);
  padding-left: 12px;
}

.conv-item-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.conv-item-count {
  font-size: 10px;
  color: var(--text-muted);
  padding: 1px 5px;
  background: var(--bg-secondary);
  border-radius: 3px;
  flex-shrink: 0;
}

.conv-detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-light);
  background: var(--surface);
}

.back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  background: transparent;
}

.back-btn:hover {
  background: var(--surface-hover);
  color: var(--lumi-primary);
}

.conv-detail-title {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.title-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.title-meta {
  font-size: 11px;
  color: var(--text-muted);
}

.conv-detail-count {
  font-size: 11px;
  padding: 3px 8px;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  border-radius: 4px;
  font-weight: 500;
  flex-shrink: 0;
}

.conv-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--text-muted);
  font-size: 13px;
}

.conv-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.msg-row {
  display: flex;
  gap: 10px;
  max-width: 85%;
  animation: content-fade-up 0.3s ease-out both;
}

.msg-row.user {
  flex-direction: row-reverse;
  align-self: flex-end;
}

.msg-row.assistant,
.msg-row.system {
  align-self: flex-start;
}

.msg-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.msg-row.user .msg-avatar {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.msg-content-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.msg-row.user .msg-content-wrap {
  align-items: flex-end;
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: var(--text-muted);
}

.msg-sender {
  font-weight: 500;
  color: var(--text-secondary);
}

.msg-model {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 5px;
  background: var(--bg-secondary);
  border-radius: 3px;
  font-size: 9px;
}

.msg-time {
  margin-left: auto;
}

.msg-row.user .msg-time {
  margin-left: 0;
  margin-right: auto;
  order: -1;
}

.msg-bubble {
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
  background: var(--surface-hover);
  color: var(--text-primary);
  border: 1px solid var(--border-light);
}

.msg-row.assistant .msg-bubble {
  border-top-left-radius: 4px;
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary-glow);
}

.msg-row.user .msg-bubble {
  border-top-right-radius: 4px;
  background: var(--task-green-soft);
  border-color: var(--lumi-success);
  color: var(--text-primary);
}

.msg-text {
  white-space: pre-wrap;
}

.msg-images {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.msg-image-item {
  width: 160px;
  height: 160px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: transform var(--transition-fast);
}

.msg-image-item:hover {
  transform: scale(1.02);
}

.msg-image-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.msg-empty {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-muted);
  font-size: 11px;
  font-style: italic;
}

/* ===== 模型配置区域 ===== */
.config-dialog {
  width: 640px;
}

.form-label {
  display: flex;
  align-items: center;
  gap: 5px;
}

.badge {
  margin-left: auto;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
}

.badge.overridden {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.badge.inherited {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.model-config-loading {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px;
  color: var(--text-muted);
  font-size: 12px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
}

.model-config-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.vision-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--task-amber-soft, rgba(245, 158, 11, 0.1));
  border: 1px solid var(--lumi-amber);
  border-radius: var(--radius-sm);
  color: var(--lumi-amber);
  font-size: 11px;
}

.model-current-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
}

.info-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  flex-wrap: wrap;
}

.info-label {
  color: var(--text-muted);
  font-weight: 500;
}

.info-value {
  color: var(--text-primary);
  font-weight: 500;
}

.info-sep {
  color: var(--text-muted);
}

.main-agent-info {
  font-size: 11px;
  opacity: 0.8;
}

.vision-tag {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  background: var(--task-red-soft);
  color: var(--lumi-danger);
}

.vision-tag.supported {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.form-select {
  cursor: pointer;
  appearance: auto;
  background-image: none;
  padding-right: 12px;
}

.form-select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-textarea {
  resize: vertical;
  font-family: inherit;
  min-height: 60px;
}

.config-field-row {
  display: flex;
  gap: 10px;
}

.config-field-row .config-field {
  flex: 1;
}

.reset-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: transparent;
  color: var(--text-muted);
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  font-size: 11px;
  cursor: pointer;
  transition: all var(--transition-fast);
  align-self: flex-start;
}

.reset-btn:hover:not(:disabled) {
  color: var(--lumi-danger);
  border-color: var(--lumi-danger);
  background: var(--task-red-soft);
}

.reset-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ===== 增强日志展示 ===== */
.log-entry {
  cursor: pointer;
}

.log-entry.log-traceable {
  border-left-color: var(--lumi-primary);
}

.log-entry.log-performance {
  border-left-color: var(--lumi-amber);
}

.log-entry.log-error-entry {
  border-left-color: var(--lumi-danger);
  background: var(--task-red-soft);
}

.log-entry.expanded {
  background: var(--surface-hover);
}

.log-event-icon {
  vertical-align: middle;
  margin-right: 2px;
}

.log-expand-hint {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--bg-secondary);
  color: var(--text-muted);
  margin-left: 4px;
}

.log-entry.expanded .log-expand-hint {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.log-perf-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
  padding: 6px 8px;
  background: var(--task-amber-soft, rgba(245, 158, 11, 0.08));
  border-radius: 3px;
  border: 1px solid var(--lumi-amber-soft, rgba(245, 158, 11, 0.2));
}

.perf-stat {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
}

.perf-key {
  color: var(--lumi-amber);
  font-weight: 500;
}

.perf-val {
  color: var(--text-primary);
  font-weight: 600;
}

.log-details-expanded {
  margin-top: 6px;
  padding: 8px 10px;
  background: var(--bg-secondary);
  border-radius: 3px;
  border: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.log-detail-row {
  display: flex;
  gap: 6px;
  font-size: 10px;
  line-height: 1.5;
}

.log-detail-row .log-detail-key {
  color: var(--lumi-primary);
  font-weight: 500;
  flex-shrink: 0;
  min-width: 80px;
}

.log-detail-row .log-detail-val {
  color: var(--text-secondary);
  word-break: break-all;
  white-space: pre-wrap;
}

.log-stack-trace {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.log-stack-trace .log-detail-key {
  color: var(--lumi-danger);
  font-size: 10px;
  font-weight: 600;
}

.stack-trace-content {
  margin: 0;
  padding: 8px;
  background: var(--task-red-soft);
  border-radius: 3px;
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
  font-size: 10px;
  color: var(--lumi-danger);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}
</style>
