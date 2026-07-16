<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  RefreshCw, Plus, Server, Shield, Zap,
  FileText, MessageSquare, Trash, Eye, MessageCircle,
} from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import type { PlatformInstance } from '../../types'
import LumiCard from '../../components/common/LumiCard.vue'
import LumiButton from '../../components/common/LumiButton.vue'
import LumiEmptyState from '../../components/common/LumiEmptyState.vue'
import PlatformInstanceList from '../../components/platform/PlatformInstanceList.vue'
import PlatformLogPanel from '../../components/platform/PlatformLogPanel.vue'
import PlatformConversationPanel from '../../components/platform/PlatformConversationPanel.vue'
import PlatformAddDialog from '../../components/platform/PlatformAddDialog.vue'
import PlatformConfigDialog from '../../components/platform/PlatformConfigDialog.vue'

const store = usePlatformStore()

const rightTab = ref<'conversations' | 'logs'>('conversations')
const showAddDialog = ref(false)
const showConfigDialog = ref(false)
const editingInstance = ref<PlatformInstance | null>(null)

const handleRefresh = async () => {
  await store.refreshAll()
}

const handleSelectInstance = (instance: PlatformInstance) => {
  store.selectInstance(instance.id)
  rightTab.value = 'conversations'
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

const handleSelectConversation = (conversationId: string) => {
  store.selectConversation(conversationId)
}

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
          <template #icon><RefreshCw :size="15" :class="{ 'spin-animation': store.loading }" /></template>
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
      <!-- Left panel: platform list only -->
      <div class="left-panel">
        <PlatformInstanceList
          @select="handleSelectInstance"
          @config="handleConfig"
          @add="showAddDialog = true"
        />
      </div>
    
      <!-- Right panel: 2/3 -->
      <LumiCard class="detail-panel" padding="none">
        <!-- No platform selected -->
        <template v-if="!store.selectedInstance">
          <div class="detail-empty">
            <LumiEmptyState
              :icon="Eye"
              title="选择平台查看详情"
              description="从左侧列表选择一个平台实例，查看其对话记录与日志"
              size="md"
            />
          </div>
        </template>
    
        <!-- Platform selected -->
        <template v-else>
          <div class="detail-tabs">
            <button :class="['detail-tab', { active: rightTab === 'conversations' }]" @click="rightTab = 'conversations'">
              <MessageSquare :size="14" />
              <span>对话</span>
              <span v-if="store.selectedConversations.length" class="tab-count">
                {{ store.selectedConversations.length }}
              </span>
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
              <template v-if="rightTab === 'conversations' && store.selectedConversationDetail">
                <div class="conv-detail-header-info">
                  <span class="conv-detail-title-text">{{ store.selectedConversationDetail.title || '对话详情' }}</span>
                  <span class="conv-detail-meta">
                    {{ store.selectedConversationDetail.platformName }}
                    <template v-if="store.selectedConversationDetail.senderName">
                      · {{ store.selectedConversationDetail.senderName }}
                    </template>
                    <template v-if="store.selectedConversationDetail.isGroup"> · 群聊</template>
                  </span>
                </div>
              </template>
            </div>
          </div>
    
          <!-- Conversations tab: vertical split (list top + detail bottom) -->
          <div v-if="rightTab === 'conversations'" class="conv-split">
            <!-- Conv list (top, compact) -->
            <div class="conv-sub-panel">
              <div class="conv-section-header">
                <MessageCircle :size="12" />
                <span>{{ store.selectedInstance.name }}</span>
                <span class="conv-section-count">{{ store.selectedConversations.length }} 个对话</span>
              </div>
              <div class="conv-list">
                <div v-if="store.selectedConversations.length === 0" class="conv-list-empty-wrap">
                  <LumiEmptyState
                    :icon="MessageSquare"
                    title="暂无对话记录"
                    description="该平台暂未推送任何对话"
                    size="sm"
                  />
                </div>
                <div
                v-for="c in store.selectedConversations"
                v-else
                :key="c.id"
                :class="['conv-item', { active: store.selectedConversationId === c.id }]"
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
              </div>
            </div>
            <!-- Conv detail (bottom) -->
            <div class="conv-detail-sub-panel">
              <div class="detail-notice">
                <Eye :size="14" />
                <span>只读模式 — 对话来自第三方平台推送</span>
              </div>
              <PlatformConversationPanel v-if="store.selectedConversationDetail" />
              <div v-else class="conv-detail-empty-wrap">
                <LumiEmptyState
                  :icon="Eye"
                  title="选择对话查看详情"
                  description="从上方对话列表中选择一个对话，查看消息内容"
                  size="sm"
                />
              </div>
            </div>
          </div>
    
          <PlatformLogPanel v-else />
        </template>
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
  overflow: hidden;
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

/* 1:2 split layout */
.platform-content {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: var(--space-4);
  min-height: 0;
  overflow: hidden;
}

/* Left panel: platform list only */
.left-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
}

/* Right panel empty state */
.detail-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}

.conv-section-header {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.conv-section-count {
  margin-left: auto;
  font-size: var(--text-2xs);
  padding: 1px var(--space-1);
  border-radius: var(--radius-full);
  background: var(--lumi-brand-glow);
  color: var(--lumi-brand);
  font-weight: var(--font-medium);
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.conv-list-empty-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 80px;
}

.conv-item {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.conv-item:hover {
  background: var(--surface-hover);
  border-left: 2px solid var(--lumi-brand);
  padding-left: calc(var(--space-3) - 2px);
}

.conv-item.active {
  background: var(--lumi-brand-light);
  border-left: 2px solid var(--lumi-brand);
  padding-left: calc(var(--space-3) - 2px);
}

.conv-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.conv-item-platform {
  font-size: var(--text-2xs);
  color: var(--lumi-brand);
  font-weight: var(--font-medium);
  display: flex;
  align-items: center;
  gap: 3px;
}

.conv-item-time {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.conv-item-title {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-item-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
}

.conv-item-preview {
  font-size: var(--text-xs);
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-item-count {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  padding: 1px var(--space-1);
  background: var(--bg-secondary);
  border-radius: var(--radius-xs);
  flex-shrink: 0;
}

/* Conversations tab: vertical split layout (list top + detail bottom) */
.conv-split {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.conv-sub-panel {
  display: flex;
  flex-direction: column;
  flex: 0 0 35%;
  min-height: 100px;
  max-height: 45%;
  border-bottom: 2px solid var(--border-light);
  overflow: hidden;
  background: var(--bg-secondary);
}

.conv-detail-sub-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.conv-detail-empty-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
}

.detail-notice {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: var(--space-2);
  background: var(--bg-secondary);
  color: var(--text-muted);
  font-size: var(--text-xs);
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

/* Right panel */
.detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  min-height: 0;
  height: 100%;
}

.detail-panel :deep(.lumi-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
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
  gap: var(--space-2);
  min-width: 0;
}

.conv-detail-header-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.conv-detail-title-text {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-detail-meta {
  font-size: var(--text-2xs);
  color: var(--text-muted);
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
