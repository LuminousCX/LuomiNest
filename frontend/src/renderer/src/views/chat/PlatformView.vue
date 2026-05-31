<script setup lang="ts">
import { ref } from 'vue'
import { Globe, ExternalLink, Eye, RefreshCw, Filter, Search, Server, Shield, Zap } from 'lucide-vue-next'

const searchQuery = ref('')
const activeFilter = ref<'all' | 'active' | 'disconnected'>('all')

const platforms = ref([
  { id: '1', name: 'Dify 工作流', status: 'active', icon: 'dify', lastSync: '2 分钟前', messages: 128 },
  { id: '2', name: 'Coze 机器人', status: 'active', icon: 'coze', lastSync: '5 分钟前', messages: 56 },
  { id: '3', name: 'FastGPT 应用', status: 'disconnected', icon: 'fastgpt', lastSync: '3 小时前', messages: 0 },
  { id: '4', name: '自定义 Webhook', status: 'active', icon: 'webhook', lastSync: '1 分钟前', messages: 342 },
  { id: '5', name: 'OpenAI Assistants', status: 'disconnected', icon: 'openai', lastSync: '1 天前', messages: 89 },
])

const conversations = ref([
  { id: 'c1', platform: 'Dify 工作流', title: '客户咨询自动回复 - 订单查询', time: '10:30', preview: '用户询问订单 #20240315 的物流状态...' },
  { id: 'c2', platform: 'Coze 机器人', title: '技术支持工单 - API 调用异常', time: '09:45', preview: '报错信息: 429 Rate Limit Exceeded...' },
  { id: 'c3', platform: '自定义 Webhook', title: '数据同步通知 - CRM 更新', time: '昨天', preview: '新增 3 条客户记录，已同步至...' },
  { id: 'c4', platform: 'Dify 工作流', title: '内容审核请求 - 用户提交', time: '昨天', preview: '待审核内容: 包含敏感词检测...' },
])
</script>

<template>
  <div class="platform-view">
    <div class="platform-header">
      <div class="header-info">
        <h1 class="header-title">平台接入</h1>
        <p class="header-desc">第三方平台对话浏览 — 仅可视化展示，不作为用户输入交互</p>
      </div>
      <div class="header-actions">
        <button class="action-btn secondary">
          <RefreshCw :size="15" />
          <span>刷新</span>
        </button>
        <button class="action-btn primary">
          <ExternalLink :size="15" />
          <span>添加平台</span>
        </button>
      </div>
    </div>

    <div class="platform-stats">
      <div class="stat-card">
        <div class="stat-icon"><Server :size="18" /></div>
        <div class="stat-info">
          <span class="stat-value">{{ platforms.length }}</span>
          <span class="stat-label">已接入平台</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon active"><Zap :size="18" /></div>
        <div class="stat-info">
          <span class="stat-value">{{ platforms.filter(p => p.status === 'active').length }}</span>
          <span class="stat-label">活跃连接</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon"><Shield :size="18" /></div>
        <div class="stat-info">
          <span class="stat-value">{{ platforms.reduce((s, p) => s + p.messages, 0) }}</span>
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
          <div v-for="p in platforms" :key="p.id" :class="['platform-card', { disconnected: p.status === 'disconnected' }]">
            <div class="card-top">
              <div class="card-icon">
                <Globe :size="16" />
              </div>
              <div class="card-info">
                <span class="card-name">{{ p.name }}</span>
                <span class="card-sync">{{ p.lastSync }}</span>
              </div>
              <span :class="['status-dot', p.status]"></span>
            </div>
            <div class="card-bottom">
              <span class="card-messages">{{ p.messages }} 条消息</span>
              <button class="card-view-btn">
                <Eye :size="13" />
                查看
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="conversation-panel">
        <div class="conv-header">
          <span class="conv-title">对话记录</span>
          <span class="conv-count">{{ conversations.length }} 条</span>
        </div>
        <div class="conv-list">
          <div v-for="c in conversations" :key="c.id" class="conv-item">
            <div class="conv-item-header">
              <span class="conv-item-platform">{{ c.platform }}</span>
              <span class="conv-item-time">{{ c.time }}</span>
            </div>
            <span class="conv-item-title">{{ c.title }}</span>
            <span class="conv-item-preview">{{ c.preview }}</span>
          </div>
        </div>
        <div class="conv-notice">
          <Eye :size="14" />
          <span>只读模式 — 对话来自第三方平台推送</span>
        </div>
      </div>
    </div>
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
  background: rgba(34, 197, 94, 0.1);
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
  width: 320px;
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
}

.platform-card:hover {
  border-color: var(--lumi-primary);
  box-shadow: var(--shadow-glow-sm);
}

.platform-card.disconnected {
  opacity: 0.6;
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
}

.status-dot.disconnected {
  background: var(--text-muted);
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

.card-view-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.card-view-btn:hover {
  background: rgba(20, 126, 188, 0.15);
}

.conversation-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  overflow: hidden;
}

.conv-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-light);
}

.conv-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.conv-count {
  font-size: 12px;
  color: var(--text-muted);
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

.conv-notice {
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
</style>
