<script setup lang="ts">
import { ref } from 'vue'
import { Wifi, Bluetooth, Users, Home, Cpu, Monitor, Smartphone, Plus, Search, Settings2, ChevronRight, Activity, MessageSquare, Clock } from 'lucide-vue-next'

const searchQuery = ref('')
const activeTab = ref<'devices' | 'groups'>('devices')

const devices = ref([
  { id: 'd1', name: 'ESP32 智能灯控', type: 'iot', status: 'online', protocol: 'MQTT', lastActive: '刚刚', messages: 56 },
  { id: 'd2', name: 'Arduino 温湿度传感器', type: 'mcu', status: 'online', protocol: 'Serial', lastActive: '3 分钟前', messages: 23 },
  { id: 'd3', name: '树莓派 网关', type: 'iot', status: 'online', protocol: 'HTTP', lastActive: '1 分钟前', messages: 142 },
  { id: 'd4', name: 'HomeAssistant 中控', type: 'hub', status: 'offline', protocol: 'WS', lastActive: '2 小时前', messages: 89 },
  { id: 'd5', name: 'ESP8266 窗帘电机', type: 'iot', status: 'offline', protocol: 'MQTT', lastActive: '1 天前', messages: 12 },
])

const groups = ref([
  { id: 'g1', name: '家庭安防组', members: ['ESP32 摄像头', '门窗传感器', '树莓派网关'], type: 'iot-group', online: true },
  { id: 'g2', name: '照明控制组', members: ['客厅灯', '卧室灯', 'ESP32 灯控'], type: 'iot-group', online: true },
  { id: 'g3', name: '开发测试群', members: ['小陈', 'ESP32 DevKit', 'Claude Agent'], type: 'hybrid', online: true },
  { id: 'g4', name: '办公室自动化', members: ['空调控制器', '打卡机', '小王'], type: 'hybrid', online: false },
])

const recentChats = ref([
  { id: 'rc1', target: 'ESP32 智能灯控', message: '已将客厅灯亮度调至 60%', time: '2 分钟前' },
  { id: 'rc2', target: '开发测试群', message: '小陈: 新固件已烧录完成', time: '15 分钟前' },
  { id: 'rc3', target: 'Arduino 温湿度传感器', message: '当前温度: 24.5°C 湿度: 65%', time: '30 分钟前' },
])
</script>

<template>
  <div class="devices-view">
    <div class="devices-header">
      <div class="header-info">
        <h1 class="header-title">设备与群组</h1>
        <p class="header-desc">物联网设备管理、人机混合群组、历史聊天记录</p>
      </div>
      <div class="header-actions">
        <button class="action-btn secondary">
          <Settings2 :size="15" />
          <span>配置</span>
        </button>
        <button class="action-btn primary">
          <Plus :size="15" />
          <span>添加设备</span>
        </button>
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
          <div class="search-box">
            <Search :size="14" class="search-icon" />
            <input v-model="searchQuery" type="text" placeholder="搜索设备..." class="search-input" />
          </div>
          <div class="device-list">
            <div v-for="d in devices" :key="d.id" :class="['device-card', { offline: d.status === 'offline' }]">
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
            </div>
          </div>
        </template>
        <template v-else>
          <div class="search-box">
            <Search :size="14" class="search-icon" />
            <input v-model="searchQuery" type="text" placeholder="搜索群组..." class="search-input" />
          </div>
          <div class="group-list">
            <div v-for="g in groups" :key="g.id" :class="['group-card', { offline: !g.online }]">
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
            </div>
          </div>
        </template>
      </div>

      <div class="side-panel">
        <div class="side-section">
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
        </div>

        <div class="side-section">
          <div class="side-header">
            <Clock :size="14" />
            <span>最近对话</span>
          </div>
          <div class="recent-list">
            <div v-for="rc in recentChats" :key="rc.id" class="recent-item">
              <MessageSquare :size="12" class="recent-icon" />
              <div class="recent-info">
                <span class="recent-target">{{ rc.target }}</span>
                <span class="recent-msg">{{ rc.message }}</span>
              </div>
              <span class="recent-time">{{ rc.time }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.devices-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px 28px;
  gap: 16px;
  overflow-y: auto;
}

.devices-header {
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

.tab-bar {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  width: fit-content;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab-btn.active {
  background: var(--surface);
  color: var(--lumi-primary);
  box-shadow: var(--shadow-xs);
}

.devices-content {
  flex: 1;
  display: flex;
  gap: 16px;
  min-height: 0;
}

.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
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

.device-list, .group-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.device-card, .group-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.device-card:hover, .group-card:hover {
  border-color: var(--lumi-primary);
  box-shadow: var(--shadow-glow-sm);
}

.device-card.offline, .group-card.offline {
  opacity: 0.6;
}

.device-icon-wrap, .group-icon-wrap {
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

.device-info, .group-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.device-name, .group-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.device-meta {
  display: flex;
  gap: 8px;
}

.device-protocol, .device-time {
  font-size: 11px;
  color: var(--text-muted);
}

.group-members {
  font-size: 11px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.device-status {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--lumi-success);
}

.device-status.offline {
  background: var(--text-muted);
}

.device-arrow {
  color: var(--text-muted);
}

.group-type-badge {
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
}

.group-type-badge.iot-group {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.group-type-badge.hybrid {
  background: rgba(234, 179, 8, 0.1);
  color: var(--lumi-warning);
}

.side-panel {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.side-section {
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  padding: 16px;
}

.side-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.status-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
}

.status-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.status-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.status-value.online {
  color: var(--lumi-success);
}

.status-value.offline {
  color: var(--text-muted);
}

.status-label {
  font-size: 11px;
  color: var(--text-muted);
}

.recent-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recent-item {
  display: flex;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-light);
}

.recent-item:last-child {
  border-bottom: none;
}

.recent-icon {
  color: var(--lumi-primary);
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
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

.recent-msg {
  font-size: 11px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-time {
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
  white-space: nowrap;
}
</style>
