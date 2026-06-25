<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Wifi, Users, Home, Cpu, Plus, Search, Settings2, ChevronRight, Activity, MessageSquare, Clock } from 'lucide-vue-next'
import { useApi } from '../../composables/useApi'
import { formatDateRelative } from '../../utils/format'
import LumiCard from '../../components/common/LumiCard.vue'
import LumiButton from '../../components/common/LumiButton.vue'
import LumiInput from '../../components/common/LumiInput.vue'
import LumiEmptyState from '../../components/common/LumiEmptyState.vue'

interface Device {
  id: string
  name: string
  type: 'iot' | 'mcu' | 'hub'
  status: 'online' | 'offline'
  protocol: string
  lastActive: string
  messages: number
}

interface Group {
  id: string
  name: string
  members: string[]
  type: 'iot-group' | 'hybrid'
  online: boolean
}

interface RecentChat {
  id: string
  target: string
  message: string
  time: string
}

interface RawInstance {
  id: string
  adapter_type?: string
  adapterType?: string
  name: string
  status?: string
  message_count?: number
  messageCount?: number
  last_sync?: string
  lastSync?: string
  display_name?: string
  displayName?: string
  category?: string
}

const SUPPORTED_ADAPTER_TYPES = ['mqtt_terminal', 'home_assistant', 'xiaomi_iot']

const PROTOCOL_MAP: Record<string, string> = {
  mqtt_terminal: 'MQTT',
  home_assistant: 'HTTP',
  xiaomi_iot: 'MQTT',
}

const searchQuery = ref('')
const activeTab = ref<'devices' | 'groups'>('devices')

const devices = ref<Device[]>([])
const groups = ref<Group[]>([])
const recentChats = ref<RecentChat[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const { apiGet } = useApi()

const mapInstanceToDevice = (inst: RawInstance): Device => {
  const adapterType = inst.adapter_type || inst.adapterType || ''
  const status = inst.status || 'stopped'
  const lastSync = inst.last_sync || inst.lastSync || ''
  return {
    id: inst.id,
    name: inst.name,
    type: adapterType === 'home_assistant' ? 'hub' : 'iot',
    status: status === 'running' ? 'online' : 'offline',
    protocol: PROTOCOL_MAP[adapterType] || adapterType || '—',
    lastActive: lastSync ? formatDateRelative(lastSync) : '未知',
    messages: inst.message_count ?? inst.messageCount ?? 0,
  }
}

const fetchDevices = async () => {
  loading.value = true
  error.value = null
  try {
    const data = await apiGet<RawInstance[]>(
      '/platforms/instances?adapter_type=mqtt_terminal,home_assistant,xiaomi_iot'
    )
    const filtered = (data || []).filter(i => {
      const at = i.adapter_type || i.adapterType || ''
      return SUPPORTED_ADAPTER_TYPES.includes(at)
    })
    devices.value = filtered.map(mapInstanceToDevice)
  } catch (e: any) {
    error.value = e?.message || '加载设备列表失败'
    devices.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDevices()
})
</script>

<template>
  <div class="devices-view">
    <div class="devices-header">
      <div class="header-info">
        <h1 class="header-title">设备与群组</h1>
        <p class="header-desc">物联网设备管理、人机混合群组、历史聊天记录</p>
      </div>
      <div class="header-actions">
        <LumiButton variant="secondary" size="sm">
          <template #icon><Settings2 :size="15" /></template>
          配置
        </LumiButton>
        <LumiButton variant="primary" size="sm">
          <template #icon><Plus :size="15" /></template>
          添加设备
        </LumiButton>
      </div>
    </div>

    <div class="tab-bar">
      <button :class="['tab-btn', { active: activeTab === 'devices' }]" @click="activeTab = 'devices'">
        <Wifi :size="14" />
        设备
      </button>
      <button :class="['tab-btn', { active: activeTab === 'groups' }]" @click="activeTab = 'groups'">
        <Users :size="14" />
        群组
      </button>
    </div>

    <div class="devices-content">
      <div class="main-panel">
        <template v-if="activeTab === 'devices'">
          <LumiInput v-model="searchQuery" type="search" placeholder="搜索设备..." class="search-input">
            <template #icon><Search :size="14" /></template>
          </LumiInput>
          <div class="device-list">
            <div v-if="loading" class="state-tip">加载中...</div>
            <LumiEmptyState
              v-else-if="error"
              icon="error"
              title="加载失败"
              :description="error"
              size="md"
            />
            <LumiEmptyState
              v-else-if="devices.length === 0"
              icon="folder"
              title="暂无设备"
              size="md"
            />
            <LumiCard
              v-for="d in devices"
              v-else
              :key="d.id"
              class="device-card"
              :class="{ offline: d.status === 'offline' }"
              padding="md"
              hoverable
            >
              <div class="device-icon-wrap">
                <Cpu :size="18" />
              </div>
              <div class="device-info">
                <span class="device-name">{{ d.name }}</span>
                <div class="device-meta">
                  <span class="device-protocol">{{ d.protocol }}</span>
                  <span class="device-time">{{ d.lastActive }}</span>
                </div>
              </div>
              <div class="device-right">
                <span :class="['device-status', d.status]"></span>
                <ChevronRight :size="16" class="device-arrow" />
              </div>
            </LumiCard>
          </div>
        </template>
        <template v-else>
          <LumiInput v-model="searchQuery" type="search" placeholder="搜索群组..." class="search-input">
            <template #icon><Search :size="14" /></template>
          </LumiInput>
          <div class="group-list">
            <LumiEmptyState
              v-if="groups.length === 0"
              icon="folder"
              title="暂无群组"
              size="md"
            />
            <LumiCard
              v-for="g in groups"
              v-else
              :key="g.id"
              class="group-card"
              :class="{ offline: !g.online }"
              padding="md"
              hoverable
            >
              <div class="group-icon-wrap">
                <Users v-if="g.type === 'hybrid'" :size="18" />
                <Home v-else :size="18" />
              </div>
              <div class="group-info">
                <span class="group-name">{{ g.name }}</span>
                <span class="group-members">{{ g.members.join(', ') }}</span>
              </div>
              <div class="group-right">
                <span :class="['group-type-badge', g.type]">{{ g.type === 'hybrid' ? '人机混合' : 'IoT群组' }}</span>
              </div>
            </LumiCard>
          </div>
        </template>
      </div>

      <div class="side-panel">
        <LumiCard class="side-section" padding="md">
          <div class="side-header">
            <Activity :size="14" />
            <span>设备状态</span>
          </div>
          <div class="status-grid">
            <div class="status-item">
              <span class="status-value online">{{ devices.filter(d => d.status === 'online').length }}</span>
              <span class="status-label">在线</span>
            </div>
            <div class="status-item">
              <span class="status-value offline">{{ devices.filter(d => d.status === 'offline').length }}</span>
              <span class="status-label">离线</span>
            </div>
            <div class="status-item">
              <span class="status-value">{{ devices.reduce((s, d) => s + d.messages, 0) }}</span>
              <span class="status-label">消息数</span>
            </div>
          </div>
        </LumiCard>

        <LumiCard class="side-section" padding="md">
          <div class="side-header">
            <Clock :size="14" />
            <span>最近对话</span>
          </div>
          <div class="recent-list">
            <LumiEmptyState
              v-if="recentChats.length === 0"
              icon="file"
              title="暂无最近对话"
              size="sm"
            />
            <div v-for="rc in recentChats" :key="rc.id" class="recent-item">
              <MessageSquare :size="12" class="recent-icon" />
              <div class="recent-info">
                <span class="recent-target">{{ rc.target }}</span>
                <span class="recent-msg">{{ rc.message }}</span>
              </div>
              <span class="recent-time">{{ rc.time }}</span>
            </div>
          </div>
        </LumiCard>
      </div>
    </div>
  </div>
</template>

<style scoped>
.devices-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--space-6) var(--space-7);
  gap: var(--space-4);
  overflow-y: auto;
}

.devices-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.header-desc {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.header-actions {
  display: flex;
  gap: var(--space-2);
}

.tab-bar {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-1);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  width: fit-content;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-5);
  border-radius: var(--radius-sm);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab-btn.active {
  background: var(--surface);
  color: var(--lumi-brand);
  box-shadow: var(--shadow-xs);
}

.tab-btn:hover:not(.active) {
  color: var(--text-secondary);
}

.devices-content {
  flex: 1;
  display: flex;
  gap: var(--space-4);
  min-height: 0;
}

.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
}

.search-input {
  width: 100%;
}

.device-list,
.group-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.device-card,
.group-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  cursor: pointer;
}

.device-card.offline,
.group-card.offline {
  opacity: 0.6;
}

.device-icon-wrap,
.group-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.device-info,
.group-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.device-name,
.group-name {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.device-meta {
  display: flex;
  gap: var(--space-2);
}

.device-protocol,
.device-time {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.group-members {
  font-size: var(--text-xs);
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.device-status {
  width: var(--space-2);
  height: var(--space-2);
  border-radius: var(--radius-full);
  background: var(--lumi-success);
}

.device-status.offline {
  background: var(--text-muted);
}

.device-arrow {
  color: var(--text-muted);
}

.group-type-badge {
  padding: 3px var(--space-2);
  border-radius: var(--radius-xs);
  font-size: var(--text-2xs);
  font-weight: var(--font-medium);
}

.group-type-badge.iot-group {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.group-type-badge.hybrid {
  background: var(--task-yellow-soft);
  color: var(--lumi-warning);
}

.side-panel {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.side-section {
  display: flex;
  flex-direction: column;
}

.side-header {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-3);
}

.status-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: var(--space-2);
}

.status-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
}

.status-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.status-value.online {
  color: var(--lumi-success);
}

.status-value.offline {
  color: var(--text-muted);
}

.status-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.recent-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.recent-item {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-light);
}

.recent-item:last-child {
  border-bottom: none;
}

.recent-icon {
  color: var(--lumi-brand);
  flex-shrink: 0;
  margin-top: 2px;
}

.recent-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.recent-target {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.recent-msg {
  font-size: var(--text-xs);
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-time {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  flex-shrink: 0;
  white-space: nowrap;
}

.state-tip {
  padding: var(--space-6) var(--space-4);
  text-align: center;
  font-size: var(--text-base);
  color: var(--text-muted);
}

</style>
