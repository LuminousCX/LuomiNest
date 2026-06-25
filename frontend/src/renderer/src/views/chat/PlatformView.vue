<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  RefreshCw, Plus, Server, Shield, Zap,
  FileText, MessageSquare, Trash,
} from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import type { PlatformInstance } from '../../types'
import LumiCard from '../../components/common/LumiCard.vue'
import LumiButton from '../../components/common/LumiButton.vue'
import PlatformInstanceList from '../../components/platform/PlatformInstanceList.vue'
import PlatformLogPanel from '../../components/platform/PlatformLogPanel.vue'
import PlatformConversationPanel from '../../components/platform/PlatformConversationPanel.vue'
import PlatformAddDialog from '../../components/platform/PlatformAddDialog.vue'
import PlatformConfigDialog from '../../components/platform/PlatformConfigDialog.vue'

const store = usePlatformStore()

const rightTab = ref<'conversations' | 'logs'>('logs')
const showAddDialog = ref(false)
const showConfigDialog = ref(false)
const editingInstance = ref<PlatformInstance | null>(null)

const handleRefresh = async () => {
  await store.refreshAll()
}

const handleSelectInstance = (instance: PlatformInstance) => {
  store.selectInstance(instance.id)
  rightTab.value = 'logs'
}

const handleConfig = (instance: PlatformInstance) => {
  editingInstance.value = instance
  showConfigDialog.value = true
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
        <LumiButton variant="secondary" size="sm" :disabled="store.loading" @click="handleRefresh">
          <template #icon><RefreshCw :size="15" :class="{ spinning: store.loading }" /></template>
          刷新
        </LumiButton>
        <LumiButton variant="primary" size="sm" @click="showAddDialog = true">
          <template #icon><Plus :size="15" /></template>
          添加平台
        </LumiButton>
      </div>
    </div>

    <div class="platform-stats">
      <LumiCard class="stat-card" :style="{ animationDelay: '0.05s' }" padding="md">
        <div class="lumi-icon-wrap lumi-icon-wrap--md lumi-icon-wrap--brand"><Server :size="18" /></div>
        <div class="stat-info">
          <span class="stat-value">{{ store.stats.totalPlatforms }}</span>
          <span class="stat-label">已接入平台</span>
        </div>
      </LumiCard>
      <LumiCard class="stat-card" :style="{ animationDelay: '0.10s' }" padding="md">
        <div class="lumi-icon-wrap lumi-icon-wrap--md stat-active"><Zap :size="18" /></div>
        <div class="stat-info">
          <span class="stat-value">{{ store.stats.activeConnections }}</span>
          <span class="stat-label">活跃连接</span>
        </div>
      </LumiCard>
      <LumiCard class="stat-card" :style="{ animationDelay: '0.15s' }" padding="md">
        <div class="lumi-icon-wrap lumi-icon-wrap--md lumi-icon-wrap--brand"><Shield :size="18" /></div>
        <div class="stat-info">
          <span class="stat-value">{{ store.stats.totalMessages }}</span>
          <span class="stat-label">消息总量</span>
        </div>
      </LumiCard>
    </div>

    <div class="platform-content">
      <PlatformInstanceList
        @select="handleSelectInstance"
        @config="handleConfig"
        @add="showAddDialog = true"
      />

      <LumiCard class="detail-panel" padding="none">
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
                <button :class="['log-filter-btn', { active: !store.logLevelFilter } ]" @click="handleLogLevelFilter(null)">全部</button>
                <button :class="['log-filter-btn', { active: store.logLevelFilter === 'error' }]" @click="handleLogLevelFilter('error')">错误</button>
                <button :class="['log-filter-btn', { active: store.logLevelFilter === 'warning' }]" @click="handleLogLevelFilter('warning')">警告</button>
                <button :class="['log-filter-btn', { active: store.logLevelFilter === 'success' }]" @click="handleLogLevelFilter('success')">成功</button>
              </div>
              <LumiButton
                v-if="store.selectedInstanceId"
                size="sm"
                icon-only
                variant="ghost"
                class="tab-action-btn"
                aria-label="清空日志"
                @click="handleClearLogs"
              >
                <template #icon><Trash :size="13" /></template>
              </LumiButton>
            </template>
          </div>
        </div>

        <PlatformConversationPanel v-if="rightTab === 'conversations'" />
        <PlatformLogPanel v-else />
      </LumiCard>
    </div>

    <PlatformAddDialog v-model:visible="showAddDialog" />
    <PlatformConfigDialog v-model:visible="showConfigDialog" :instance="editingInstance" />
  </div>
</template>

<style scoped>
.platform-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--space-6) var(--space-7);
  gap: var(--space-5);
  overflow-y: auto;
}

.platform-header {
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

.spinning {
  animation: spin 1s linear infinite;
}

.platform-stats {
  display: flex;
  gap: var(--space-4);
}

.stat-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  animation: lumi-content-fade-up var(--duration-enter) var(--ease-default) both;
}

.stat-active {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.stat-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.stat-label {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.platform-content {
  flex: 1;
  display: flex;
  gap: var(--space-4);
  min-height: 0;
}

.detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-tabs {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
}

.detail-tab {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.detail-tab:hover {
  color: var(--text-secondary);
  background: var(--surface-hover);
}

.detail-tab.active {
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

.tab-count {
  font-size: var(--text-2xs);
  padding: 1px var(--space-1);
  border-radius: var(--radius-xs);
  background: var(--border-light);
  color: var(--text-muted);
}

.detail-tab.active .tab-count {
  background: var(--lumi-brand-glow);
  color: var(--lumi-brand);
}

.detail-tab-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.log-filter-group {
  display: flex;
  gap: var(--space-1);
}

.log-filter-btn {
  padding: 3px var(--space-2);
  border-radius: var(--radius-xs);
  font-size: var(--text-2xs);
  font-weight: var(--font-medium);
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.log-filter-btn:hover {
  background: var(--surface-hover);
}

.log-filter-btn.active {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.tab-action-btn {
  color: var(--text-muted);
}

.tab-action-btn:hover:not(:disabled) {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

</style>
