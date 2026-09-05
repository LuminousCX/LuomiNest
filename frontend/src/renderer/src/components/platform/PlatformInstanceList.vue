<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Globe, Radio, Cable, Link, MessageCircle, Send, Gamepad2, Home, Smartphone,
  Play, Square, Plus, Trash2, Settings,
  AlertCircle,
} from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import type { PlatformInstance } from '../../types'
import LumiCard from '../../components/common/LumiCard.vue'
import LumiButton from '../../components/common/LumiButton.vue'
import SearchInput from '../common/SearchInput.vue'
import LumiEmptyState from '../../components/common/LumiEmptyState.vue'
import { createLuomiNestRendererLogger } from '../../utils/logger'

const logger = createLuomiNestRendererLogger('Platform')

const store = usePlatformStore()

const emit = defineEmits<{
  select: [instance: PlatformInstance]
  config: [instance: PlatformInstance]
  add: []
}>()

const searchQuery = ref('')
const activeFilter = ref<'all' | 'active' | 'disconnected'>('all')

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

const getStatusLabel = (status: string) => {
  switch (status) {
    case 'running': return '运行中'
    case 'stopped': return '已停止'
    case 'error': return '错误'
    case 'pending': return '等待中'
    default: return '未知'
  }
}

const handleSelectInstance = (instance: PlatformInstance) => {
  emit('select', instance)
}

const handleToggleStatus = async (instance: PlatformInstance) => {
  try {
    if (instance.status === 'running') {
      await store.stopInstance(instance.id)
    } else {
      await store.startInstance(instance.id)
    }
  } catch (e: unknown) {
    logger.error('Failed to toggle platform status:', e)
  }
}

const handleDelete = async (instance: PlatformInstance) => {
  if (instance.status === 'running') {
    await store.stopInstance(instance.id)
  }
  await store.deleteInstance(instance.id)
}

const handleConfig = (instance: PlatformInstance) => {
  emit('config', instance)
}
</script>

<template>
  <div class="platform-list-panel">
    <div class="panel-toolbar">
      <SearchInput v-model="searchQuery" placeholder="搜索平台..." class="search-input" />
      <div class="filter-group">
        <button :class="['filter-btn', { active: activeFilter === 'all' }]" @click="activeFilter = 'all'">全部</button>
        <button :class="['filter-btn', { active: activeFilter === 'active' }]" @click="activeFilter = 'active'">活跃</button>
        <button :class="['filter-btn', { active: activeFilter === 'disconnected' }]" @click="activeFilter = 'disconnected'">断开</button>
      </div>
    </div>

    <div class="platform-cards">
      <LumiCard
        v-for="(p, idx) in filteredInstances"
        :key="p.id"
        class="platform-card"
        :class="{ disconnected: p.status !== 'running', selected: store.selectedInstanceId === p.id }"
        :style="{ animationDelay: (0.08 + idx * 0.04) + 's' }"
        padding="md"
        hoverable
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
            <LumiButton
              size="sm"
              icon-only
              :variant="p.status === 'running' ? 'danger-ghost' : 'ghost'"
              :class="['card-action-btn', p.status === 'running' ? 'stop' : 'start']"
              :aria-label="p.status === 'running' ? '停止' : '启动'"
              @click.stop="handleToggleStatus(p)"
            >
              <template #icon>
                <Square v-if="p.status === 'running'" :size="12" />
                <Play v-else :size="12" />
              </template>
            </LumiButton>
            <LumiButton
              size="sm"
              icon-only
              variant="ghost"
              class="card-action-btn config"
              aria-label="配置"
              @click.stop="handleConfig(p)"
            >
              <template #icon><Settings :size="12" /></template>
            </LumiButton>
            <LumiButton
              size="sm"
              icon-only
              variant="danger-ghost"
              class="card-action-btn delete"
              aria-label="删除"
              @click.stop="handleDelete(p)"
            >
              <template #icon><Trash2 :size="12" /></template>
            </LumiButton>
          </div>
        </div>
        <div v-if="p.errorMessage" class="card-error">
          <AlertCircle :size="11" />
          <span>{{ p.errorMessage }}</span>
        </div>
      </LumiCard>

      <LumiEmptyState
        v-if="filteredInstances.length === 0"
        icon="folder"
        title="暂无平台实例"
        size="md"
      >
        <template #action>
          <LumiButton variant="primary" size="sm" @click="emit('add')">
            <template #icon><Plus :size="14" /></template>
            添加平台
          </LumiButton>
        </template>
      </LumiEmptyState>
    </div>
  </div>
</template>

<style scoped>
.platform-list-panel {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.panel-toolbar {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.search-input {
  width: 100%;
}

.filter-group {
  display: flex;
  gap: var(--space-1);
}

.filter-btn {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--text-muted);
  background: var(--surface);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.filter-btn.active {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  border-color: var(--lumi-brand);
}

.platform-cards {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.platform-card {
  cursor: pointer;
  animation: lumi-content-fade-up var(--duration-slow) var(--ease-default) both;
}

.platform-card:hover {
  border-color: var(--lumi-brand);
  box-shadow: var(--shadow-glow-sm);
}

.platform-card.selected {
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

.platform-card.disconnected {
  opacity: 0.7;
}

.card-top {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.card-icon {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-sm);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-icon.social {
  background: var(--task-sky-soft);
  color: var(--task-sky);
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
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.card-sync {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.status-dot {
  width: var(--space-2);
  height: var(--space-2);
  border-radius: var(--radius-full);
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
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.card-actions {
  display: flex;
  gap: var(--space-1);
}

.card-action-btn.start {
  color: var(--lumi-success);
}

.card-action-btn.start:hover:not(:disabled) {
  background: var(--lumi-success-light);
}

.card-action-btn.config {
  color: var(--lumi-brand);
}

.card-action-btn.config:hover:not(:disabled) {
  background: var(--lumi-brand-light);
}

.card-error {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-2);
  padding: var(--space-1) var(--space-2);
  background: var(--lumi-danger-light);
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  color: var(--lumi-danger);
}

</style>
