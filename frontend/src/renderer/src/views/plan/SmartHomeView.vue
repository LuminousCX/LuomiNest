<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { Component } from 'vue'
import { Lightbulb, Thermometer, Droplets, Lock, Wifi, Power, Settings2, Wind, Eye, Plus, Activity } from 'lucide-vue-next'
import LumiButton from '../../components/common/LumiButton.vue'
import LumiCard from '../../components/common/LumiCard.vue'
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
  icon: Component
  active: boolean
  desc: string
}

interface Room {
  id: string
  name: string
  devices: number
  active: number
  icon: Component
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
        <LumiButton variant="secondary" size="sm">
          <template #icon><Settings2 :size="14" /></template>
          <span>设置</span>
        </LumiButton>
        <LumiButton variant="primary" size="sm">
          <template #icon><Plus :size="14" /></template>
          <span>添加设备</span>
        </LumiButton>
      </div>
    </div>

    <div class="sh-content">
      <div class="left-col">
        <LumiCard class="section-card" padding="md">
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
        </LumiCard>

        <LumiCard class="section-card" padding="md">
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
        </LumiCard>
      </div>

      <div class="center-col">
        <LumiCard class="section-card full" padding="md">
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
        </LumiCard>
      </div>

      <div class="right-col">
        <LumiCard class="section-card" padding="md">
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
        </LumiCard>
      </div>
    </div>
  </div>
</template>

<style scoped>
.smart-home-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--space-6) var(--space-7);
  gap: var(--space-5);
  overflow-y: auto;
}

.sh-header {
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

.sh-content {
  flex: 1;
  display: flex;
  gap: var(--space-4);
  min-height: 0;
}

.left-col {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
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
  background: transparent;
  border: none;
  box-shadow: none;
}

.section-card.full {
  flex: 1;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}

.section-title {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.section-icon {
  color: var(--text-muted);
}

.room-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}

.room-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-3) var(--space-2);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background-color var(--transition-fast);
}

.room-card:hover {
  background: var(--lumi-brand-light);
}

.room-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
}

.room-name {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.room-count {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.scene-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.scene-card {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.scene-card.active {
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

.scene-icon-wrap {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.scene-card.active .scene-icon-wrap {
  background: var(--lumi-brand-glow);
  color: var(--lumi-brand);
}

.scene-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.scene-name {
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.scene-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.scene-toggle {
  width: 36px;
  height: var(--space-5);
  border-radius: var(--radius-full);
  background: var(--border);
  position: relative;
  cursor: pointer;
  transition: background-color var(--transition-fast);
  flex-shrink: 0;
}

.scene-toggle.on {
  background: var(--lumi-brand);
}

.toggle-dot {
  width: var(--space-4);
  height: var(--space-4);
  border-radius: var(--radius-full);
  background: var(--surface);
  position: absolute;
  top: 2px;
  left: 2px;
  transition: transform var(--transition-fast);
}

.scene-toggle.on .toggle-dot {
  transform: translateX(var(--space-4));
}

.device-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-2);
}

.device-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-4) var(--space-3);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background-color var(--transition-fast);
}

.device-tile:hover {
  background: var(--lumi-brand-light);
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
  color: var(--lumi-brand);
}

.tile-room {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.tile-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
}

.device-tile.off .tile-icon-wrap {
  background: var(--bg-secondary);
  color: var(--text-muted);
}

.tile-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  text-align: center;
}

.tile-value {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.automation-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.automation-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
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
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.auto-detail {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.auto-toggle {
  width: var(--space-7);
  height: 18px;
  border-radius: var(--radius-full);
  background: var(--border);
  position: relative;
  cursor: pointer;
  transition: background-color var(--transition-fast);
  flex-shrink: 0;
}

.auto-toggle.on {
  background: var(--lumi-brand);
}

.auto-toggle .toggle-dot {
  width: 14px;
  height: 14px;
  border-radius: var(--radius-full);
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
