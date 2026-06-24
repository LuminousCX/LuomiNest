<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Lightbulb, Thermometer, Droplets, Lock, Wifi, Power, Settings2, Wind, Eye, Plus, Activity } from 'lucide-vue-next'
import { useApi } from '../../composables/useApi'

const { apiGet } = useApi()

interface Device {
  id: string
  name: string
  room: string
  type: string
  status: boolean
  value: string
}

interface Scene {
  id: string
  name: string
  icon: any
  active: boolean
  desc: string
}

interface Room {
  id: string
  name: string
  devices: number
  active: number
  icon: any
}

interface Automation {
  id: string
  name: string
  trigger: string
  action: string
  enabled: boolean
}

const rooms = ref<Room[]>([])
const scenes = ref<Scene[]>([])
const deviceList = ref<Device[]>([])
const automations = ref<Automation[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const fetchData = async () => {
  loading.value = true
  error.value = null
  try {
    const [devicesRes, scenesRes, roomsRes, automationsRes] = await Promise.all([
      apiGet<{ devices: Device[] }>('/smart-home/devices'),
      apiGet<{ scenes: Scene[] }>('/smart-home/scenes'),
      apiGet<{ rooms: Room[] }>('/smart-home/rooms'),
      apiGet<{ automations: Automation[] }>('/smart-home/automations'),
    ])
    deviceList.value = devicesRes?.devices || []
    scenes.value = scenesRes?.scenes || []
    rooms.value = roomsRes?.rooms || []
    automations.value = automationsRes?.automations || []
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)

const toggleScene = (sceneId: string) => {
  scenes.value = scenes.value.map(s => ({
    ...s,
    active: s.id === sceneId ? !s.active : false,
  }))
}
</script>

<template>
  <div class="smart-home-view">
    <div class="sh-header">
      <div class="header-info">
        <h1 class="header-title">智能家居</h1>
        <p class="header-desc">物联网智能居家计划与设备控制</p>
      </div>
      <div class="header-actions">
        <button class="action-btn secondary">
          <Settings2 :size="15" />
          <span>设置</span>
        </button>
        <button class="action-btn primary">
          <Plus :size="15" />
          <span>添加设备</span>
        </button>
      </div>
    </div>

    <div class="sh-content">
      <div class="left-col">
        <div class="section-card">
          <div class="section-header">
            <span class="section-title">房间</span>
          </div>
          <div class="room-grid">
            <div v-for="r in rooms" :key="r.id" class="room-card">
              <div class="room-icon-wrap">
                <component :is="r.icon" :size="18" />
              </div>
              <span class="room-name">{{ r.name }}</span>
              <span class="room-count">{{ r.active }}/{{ r.devices }} 在线</span>
            </div>
          </div>
        </div>

        <div class="section-card">
          <div class="section-header">
            <span class="section-title">场景</span>
          </div>
          <div class="scene-list">
            <div
              v-for="s in scenes"
              :key="s.id"
              :class="['scene-card', { active: s.active }]"
              @click="toggleScene(s.id)"
            >
              <div class="scene-icon-wrap">
                <component :is="s.icon" :size="16" />
              </div>
              <div class="scene-info">
                <span class="scene-name">{{ s.name }}</span>
                <span class="scene-desc">{{ s.desc }}</span>
              </div>
              <div :class="['scene-toggle', { on: s.active }]">
                <div class="toggle-dot"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="center-col">
        <div class="section-card full">
          <div class="section-header">
            <span class="section-title">设备控制</span>
            <Wifi :size="14" class="section-icon" />
          </div>
          <div class="device-grid">
            <div v-for="d in deviceList" :key="d.id" :class="['device-tile', { off: !d.status }]">
              <div class="tile-top">
                <Power :size="14" :class="['power-icon', { on: d.status }]" />
                <span class="tile-room">{{ d.room }}</span>
              </div>
              <div class="tile-icon-wrap">
                <Lightbulb v-if="d.type === 'light'" :size="22" />
                <Wind v-else-if="d.type === 'ac'" :size="22" />
                <Droplets v-else-if="d.type === 'humidifier'" :size="22" />
                <Lock v-else-if="d.type === 'lock'" :size="22" />
                <Eye v-else-if="d.type === 'curtain'" :size="22" />
                <Thermometer v-else :size="22" />
              </div>
              <span class="tile-name">{{ d.name }}</span>
              <span class="tile-value">{{ d.value }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="right-col">
        <div class="section-card">
          <div class="section-header">
            <span class="section-title">自动化</span>
            <Activity :size="14" class="section-icon" />
          </div>
          <div class="automation-list">
            <div v-for="a in automations" :key="a.id" :class="['automation-item', { disabled: !a.enabled }]">
              <div class="auto-info">
                <span class="auto-name">{{ a.name }}</span>
                <span class="auto-detail">{{ a.trigger }} → {{ a.action }}</span>
              </div>
              <div :class="['auto-toggle', { on: a.enabled }]">
                <div class="toggle-dot"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.smart-home-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px 28px;
  gap: 20px;
  overflow-y: auto;
}

.sh-header {
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

.sh-content {
  flex: 1;
  display: flex;
  gap: 16px;
  min-height: 0;
}

.left-col {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.center-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.right-col {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.section-card {
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  padding: 18px;
}

.section-card.full {
  flex: 1;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.section-icon {
  color: var(--text-muted);
}

.room-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.room-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 14px 10px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.room-card:hover {
  background: var(--lumi-primary-light);
}

.room-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.room-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.room-count {
  font-size: 11px;
  color: var(--text-muted);
}

.scene-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.scene-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.scene-card.active {
  border-color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.scene-icon-wrap {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.scene-card.active .scene-icon-wrap {
  background: var(--lumi-primary-glow);
  color: var(--lumi-primary);
}

.scene-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.scene-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.scene-desc {
  font-size: 11px;
  color: var(--text-muted);
}

.scene-toggle {
  width: 36px;
  height: 20px;
  border-radius: 10px;
  background: var(--border);
  position: relative;
  cursor: pointer;
  transition: background var(--transition-fast);
  flex-shrink: 0;
}

.scene-toggle.on {
  background: var(--lumi-primary);
}

.toggle-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--surface);
  position: absolute;
  top: 2px;
  left: 2px;
  transition: transform var(--transition-fast);
}

.scene-toggle.on .toggle-dot {
  transform: translateX(16px);
}

.device-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.device-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 16px 12px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.device-tile:hover {
  background: var(--lumi-primary-light);
}

.device-tile.off {
  opacity: 0.5;
}

.tile-top {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.power-icon {
  color: var(--text-muted);
}

.power-icon.on {
  color: var(--lumi-primary);
}

.tile-room {
  font-size: 10px;
  color: var(--text-muted);
}

.tile-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.device-tile.off .tile-icon-wrap {
  background: var(--bg-secondary);
  color: var(--text-muted);
}

.tile-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  text-align: center;
}

.tile-value {
  font-size: 11px;
  color: var(--text-muted);
}

.automation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.automation-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
}

.automation-item.disabled {
  opacity: 0.5;
}

.auto-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.auto-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

.auto-detail {
  font-size: 10px;
  color: var(--text-muted);
}

.auto-toggle {
  width: 32px;
  height: 18px;
  border-radius: 9px;
  background: var(--border);
  position: relative;
  cursor: pointer;
  transition: background var(--transition-fast);
  flex-shrink: 0;
}

.auto-toggle.on {
  background: var(--lumi-primary);
}

.auto-toggle .toggle-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--surface);
  position: absolute;
  top: 2px;
  left: 2px;
  transition: transform var(--transition-fast);
}

.auto-toggle.on .toggle-dot {
  transform: translateX(14px);
}
</style>
