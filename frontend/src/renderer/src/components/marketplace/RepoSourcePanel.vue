<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  Github, Cloud, Globe, Plus, Link2, Unlink, RefreshCw,
  ChevronDown, ChevronRight, X, Loader2, Check, AlertCircle,
  Trash2, ExternalLink, Database, Clock,
} from 'lucide-vue-next'
import { useRepoSourceStore } from '../../stores/repo-source'
import type { RepoSource, RepoSourceType } from '../../types/marketplace'

const store = useRepoSourceStore()

const expandedSourceIds = ref<Set<string>>(new Set(['github-official']))
const showAddDialog = ref(false)
const addForm = ref({ name: '', url: '', description: '' })

const TYPE_CONFIG: Record<RepoSourceType, { icon: any; label: string; color: string }> = {
  github: { icon: Github, label: 'GitHub', color: '#8b5cf6' },
  cloud: { icon: Cloud, label: '云端', color: '#3b82f6' },
  cdn: { icon: Globe, label: 'CDN', color: '#06b6d4' },
  custom: { icon: Plus, label: '自定义', color: '#f59e0b' },
}

const SUB_MARKET_TYPE_LABEL: Record<string, string> = {
  plugin: '插件',
  skill: '技能',
  agent: '智能体',
}

onMounted(() => {
  store.fetchSources()
})

const toggleExpand = (sourceId: string) => {
  const next = new Set(expandedSourceIds.value)
  if (next.has(sourceId)) {
    next.delete(sourceId)
  } else {
    next.add(sourceId)
  }
  expandedSourceIds.value = next
}

const isExpanded = (sourceId: string) => expandedSourceIds.value.has(sourceId)

const handleToggleSource = async (sourceId: string) => {
  await store.toggleSource(sourceId)
}

const handleUnlink = async (sourceId: string, subMarketId: string) => {
  await store.unlinkSubMarket(sourceId, subMarketId)
}

const handleLink = async (sourceId: string, subMarketId: string) => {
  await store.linkSubMarket(sourceId, subMarketId)
}

const handleSync = async (sourceId: string) => {
  await store.syncSource(sourceId, true)
}

const handleSyncSubMarket = async (sourceId: string, subMarketId: string) => {
  await store.syncSubMarket(sourceId, subMarketId, true)
}

const handleSelectSource = (sourceId: string) => {
  store.setActiveSource(sourceId)
  if (!expandedSourceIds.value.has(sourceId)) {
    toggleExpand(sourceId)
  }
}

const handleAddCustom = async () => {
  if (!addForm.value.name.trim()) return
  if (!addForm.value.url.trim()) return
  // 基本 URL 校验
  try {
    const parsed = new URL(addForm.value.url.trim())
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      throw new Error('仅支持 http/https 协议')
    }
  } catch {
    alert('请输入有效的 URL 地址（以 http:// 或 https:// 开头）')
    return
  }
  const result = await store.addCustomSource({
    name: addForm.value.name.trim(),
    url: addForm.value.url.trim(),
    description: addForm.value.description.trim(),
  })
  if (result) {
    showAddDialog.value = false
    addForm.value = { name: '', url: '', description: '' }
  }
}

const handleDeleteSource = async (sourceId: string) => {
  await store.deleteSource(sourceId)
}

const handleClearCache = async (sourceId: string) => {
  await store.clearSourceCache(sourceId)
}

const getStatusIcon = (source: RepoSource) => {
  if (source.status === 'loading') return Loader2
  if (source.status === 'loaded') return Check
  if (source.status === 'error') return AlertCircle
  return null
}

const getStatusClass = (source: RepoSource) => {
  if (source.status === 'loading') return 'status-loading'
  if (source.status === 'loaded') return 'status-loaded'
  if (source.status === 'error') return 'status-error'
  return ''
}

const getStatusText = (source: RepoSource) => {
  if (source.status === 'loading') return '同步中...'
  if (source.status === 'loaded') return '已同步'
  if (source.status === 'error') return '同步失败'
  return '未同步'
}

const getSourceItemCount = (sourceId: string): number => {
  return store.syncedItems[sourceId]?.length || 0
}

const getSubMarketItemCount = (sourceId: string, subMarketType: string): number => {
  const items = store.syncedItems[sourceId] || []
  return items.filter(i => i.type === subMarketType).length
}

const formatSyncTime = (timeStr?: string) => {
  if (!timeStr) return ''
  try {
    const d = new Date(timeStr)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return '刚刚'
    if (diffMin < 60) return `${diffMin} 分钟前`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr} 小时前`
    return d.toLocaleDateString('zh-CN')
  } catch {
    return ''
  }
}
</script>

<template>
  <div class="repo-source-panel">
    <div class="panel-header">
      <span class="panel-title">仓库来源</span>
      <button class="add-source-btn" @click="showAddDialog = true" title="添加自定义来源">
        <Plus :size="14" />
      </button>
    </div>

    <div v-if="store.loading" class="panel-loading">
      <Loader2 :size="20" class="spin-animation" />
      <span>加载中...</span>
    </div>

    <div v-else class="source-list">
      <div
        v-for="source in store.sources"
        :key="source.id"
        :class="['source-item', { active: store.activeSourceId === source.id, disabled: !source.enabled }]"
      >
        <div class="source-header" @click="handleSelectSource(source.id)">
          <div class="source-left">
            <button
              class="expand-btn"
              @click.stop="toggleExpand(source.id)"
            >
              <component
                :is="isExpanded(source.id) ? ChevronDown : ChevronRight"
                :size="14"
              />
            </button>
            <div class="source-type-icon" :style="{ color: TYPE_CONFIG[source.type]?.color || '#888' }">
              <component :is="TYPE_CONFIG[source.type]?.icon || Globe" :size="16" />
            </div>
            <div class="source-info">
              <span class="source-name">{{ source.name }}</span>
              <span v-if="source.url" class="source-url">{{ source.url }}</span>
            </div>
          </div>

          <div class="source-right">
            <span v-if="getSourceItemCount(source.id) > 0" class="source-item-count">
              {{ getSourceItemCount(source.id) }} 项
            </span>
            <component
              v-if="getStatusIcon(source)"
              :is="getStatusIcon(source)"
              :size="14"
              :class="['status-icon', getStatusClass(source)]"
            />
            <button
              class="toggle-btn"
              :class="{ on: source.enabled }"
              @click.stop="handleToggleSource(source.id)"
              :title="source.enabled ? '禁用' : '启用'"
            >
              <div class="toggle-track">
                <div class="toggle-thumb" />
              </div>
            </button>
          </div>
        </div>

        <Transition name="expand">
          <div v-if="isExpanded(source.id)" class="source-detail">
            <p v-if="source.description" class="source-desc">{{ source.description }}</p>

            <!-- 同步状态栏 -->
            <div :class="['sync-status-bar', source.status]">
              <div class="sync-status-left">
                <component
                  :is="source.status === 'loading' ? Loader2 : source.status === 'loaded' ? Check : source.status === 'error' ? AlertCircle : Clock"
                  :size="13"
                  :class="{ 'spin-animation': source.status === 'loading' }"
                />
                <span>{{ getStatusText(source) }}</span>
              </div>
              <span v-if="source.lastSyncedAt" class="sync-time">
                {{ formatSyncTime(source.lastSyncedAt) }}
              </span>
            </div>

            <div v-if="source.errorMessage" class="source-error">
              <AlertCircle :size="14" />
              <span>{{ source.errorMessage }}</span>
            </div>

            <div v-if="source.subMarkets && source.subMarkets.length > 0" class="sub-markets">
              <div class="sub-markets-label">子市场</div>
              <div
                v-for="sm in source.subMarkets"
                :key="sm.id"
                :class="['sub-market-item', { unlinked: !sm.linked }]"
              >
                <div class="sub-market-info">
                  <span class="sub-market-type-badge" :data-type="sm.type">
                    {{ SUB_MARKET_TYPE_LABEL[sm.type] || sm.type }}
                  </span>
                  <span class="sub-market-name">{{ sm.name }}</span>
                  <span v-if="sm.linked && getSubMarketItemCount(source.id, sm.type) > 0" class="sub-market-count">
                    {{ getSubMarketItemCount(source.id, sm.type) }}
                  </span>
                </div>
                <div class="sub-market-actions">
                  <a
                    v-if="sm.url"
                    :href="sm.url"
                    target="_blank"
                    class="sub-market-link"
                    title="在浏览器中打开"
                    @click.stop
                  >
                    <ExternalLink :size="13" />
                  </a>
                  <button
                    v-if="sm.linked"
                    class="sub-action-btn sync-sub-btn"
                    :disabled="source.status === 'loading' || source.status === 'syncing'"
                    title="同步此子市场"
                    @click="handleSyncSubMarket(source.id, sm.id)"
                  >
                    <RefreshCw :size="12" :class="{ 'spin-animation': source.status === 'loading' }" />
                  </button>
                  <button
                    v-if="sm.linked"
                    class="unlink-btn"
                    title="取消链接"
                    @click="handleUnlink(source.id, sm.id)"
                  >
                    <Unlink :size="13" />
                    <span>取消链接</span>
                  </button>
                  <button
                    v-else
                    class="link-btn"
                    title="重新链接"
                    @click="handleLink(source.id, sm.id)"
                  >
                    <Link2 :size="13" />
                    <span>重新链接</span>
                  </button>
                </div>
              </div>
            </div>

            <div class="source-actions">
              <button
                class="action-btn sync-btn"
                :disabled="source.status === 'loading'"
                @click="handleSync(source.id)"
              >
                <RefreshCw :size="13" :class="{ 'spin-animation': source.status === 'loading' }" />
                <span>{{ source.status === 'loading' ? '同步中...' : '同步' }}</span>
              </button>
              <button
                v-if="getSourceItemCount(source.id) > 0"
                class="action-btn cache-btn"
                @click="handleClearCache(source.id)"
                title="清除缓存"
              >
                <Database :size="13" />
                <span>清除缓存</span>
              </button>
              <button
                v-if="source.type === 'custom'"
                class="action-btn delete-btn"
                @click="handleDeleteSource(source.id)"
              >
                <Trash2 :size="13" />
                <span>删除</span>
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Add Custom Source Dialog -->
    <Teleport to="body">
      <Transition name="dialog-fade">
        <div v-if="showAddDialog" class="dialog-overlay" @click.self="showAddDialog = false">
          <div class="dialog-content">
            <div class="dialog-header">
              <h3>添加自定义仓库来源</h3>
              <button class="dialog-close" @click="showAddDialog = false">
                <X :size="18" />
              </button>
            </div>
            <div class="dialog-body">
              <div class="form-field">
                <label>名称</label>
                <input v-model="addForm.name" type="text" placeholder="输入仓库名称" />
              </div>
              <div class="form-field">
                <label>URL</label>
                <input v-model="addForm.url" type="text" placeholder="输入仓库地址（如 GitHub 仓库 URL）" />
              </div>
              <div class="form-field">
                <label>描述</label>
                <textarea v-model="addForm.description" placeholder="输入仓库描述（可选）" rows="3" />
              </div>
            </div>
            <div class="dialog-footer">
              <button class="btn-cancel" @click="showAddDialog = false">取消</button>
              <button
                class="btn-confirm"
                :disabled="!addForm.name.trim()"
                @click="handleAddCustom"
              >
                添加
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.repo-source-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px;
}

.panel-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.add-source-btn {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.add-source-btn:hover {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.panel-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px 0;
  color: var(--text-muted);
  font-size: 13px;
}

.source-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.source-item {
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.source-item.active {
  border-color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.source-item.disabled {
  opacity: 0.6;
}

.source-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: background 0.15s;
}

.source-header:hover {
  background: var(--surface-hover);
}

.source-item.active .source-header:hover {
  background: rgba(var(--lumi-primary-rgb, 20, 126, 188), 0.08);
}

.source-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.expand-btn {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  flex-shrink: 0;
  transition: all var(--transition-fast);
}

.expand-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.source-type-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.source-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.source-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-url {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.source-item-count {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--workspace-panel);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.status-icon {
  color: var(--text-muted);
}

.status-icon.status-loading {
  color: var(--lumi-primary);
  animation: spin 1s linear infinite;
}

.status-icon.status-loaded {
  color: #22c55e;
}

.status-icon.status-error {
  color: #ef4444;
}

.toggle-btn {
  padding: 0;
  background: none;
  cursor: pointer;
}

.toggle-track {
  width: 32px;
  height: 18px;
  border-radius: 9px;
  background: var(--workspace-border);
  position: relative;
  transition: background 0.25s;
}

.toggle-btn.on .toggle-track {
  background: var(--lumi-primary);
}

.toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--surface);
  transition: transform 0.25s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
}

.toggle-btn.on .toggle-thumb {
  transform: translateX(14px);
}

.source-detail {
  padding: 0 10px 10px 38px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.source-desc {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
  margin: 0;
}

/* 同步状态栏 */
.sync-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
}

.sync-status-bar.loading {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.sync-status-bar.loaded {
  color: #22c55e;
  border-color: rgba(34, 197, 94, 0.2);
  background: rgba(34, 197, 94, 0.05);
}

.sync-status-bar.error {
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.2);
  background: rgba(239, 68, 68, 0.05);
}

.sync-status-bar.idle {
  color: var(--text-muted);
}

.sync-status-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.sync-time {
  font-size: 11px;
  opacity: 0.7;
}

.source-error {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  font-size: 12px;
}

.sub-markets {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sub-markets-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.sub-market-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all 0.2s;
}

.sub-market-item.unlinked {
  opacity: 0.5;
  border-style: dashed;
}

.sub-market-info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.sub-market-type-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  text-transform: uppercase;
  flex-shrink: 0;
}

.sub-market-type-badge[data-type="plugin"] {
  background: rgba(139, 92, 246, 0.15);
  color: #8b5cf6;
}

.sub-market-type-badge[data-type="skill"] {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.sub-market-type-badge[data-type="agent"] {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.sub-market-name {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sub-market-count {
  font-size: 10px;
  color: var(--text-muted);
  background: var(--workspace-border);
  padding: 1px 5px;
  border-radius: 8px;
  min-width: 18px;
  text-align: center;
}

.sub-market-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.sub-market-link {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.sub-market-link:hover {
  background: var(--surface-hover);
  color: var(--lumi-primary);
}

.sub-action-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.sub-action-btn:hover {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.sub-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.unlink-btn,
.link-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  transition: all var(--transition-fast);
}

.unlink-btn {
  color: var(--text-muted);
}

.unlink-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.link-btn {
  color: var(--lumi-primary);
}

.link-btn:hover {
  background: var(--lumi-primary-light);
}

.sync-info {
  font-size: 11px;
  color: var(--text-muted);
}

.source-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.action-btn:hover {
  background: var(--surface-hover);
}

.sync-btn:hover {
  color: var(--lumi-primary);
}

.cache-btn:hover {
  color: #f59e0b;
}

.delete-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Dialog */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.dialog-content {
  width: 400px;
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--workspace-border);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--workspace-border);
}

.dialog-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.dialog-close {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.dialog-close:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.dialog-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.form-field input,
.form-field textarea {
  padding: 8px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--workspace-border);
  background: var(--workspace-panel);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: border-color var(--transition-fast);
  font-family: inherit;
}

.form-field input:focus,
.form-field textarea:focus {
  border-color: var(--lumi-primary);
}

.form-field textarea {
  resize: vertical;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--workspace-border);
}

.btn-cancel,
.btn-confirm {
  padding: 8px 18px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.btn-cancel {
  color: var(--text-secondary);
}

.btn-cancel:hover {
  background: var(--surface-hover);
}

.btn-confirm {
  background: var(--lumi-primary);
  color: white;
}

.btn-confirm:hover {
  opacity: 0.9;
}

.btn-confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Transitions */
.expand-enter-active {
  animation: expand-in 0.25s ease-out;
}

.expand-leave-active {
  animation: expand-in 0.15s ease-in reverse;
}

@keyframes expand-in {
  from {
    opacity: 0;
    max-height: 0;
    overflow: hidden;
  }
  to {
    opacity: 1;
    max-height: 500px;
  }
}

.dialog-fade-enter-active {
  animation: dialog-in 0.2s ease-out;
}

.dialog-fade-leave-active {
  animation: dialog-in 0.15s ease-in reverse;
}

@keyframes dialog-in {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.spin-animation {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
