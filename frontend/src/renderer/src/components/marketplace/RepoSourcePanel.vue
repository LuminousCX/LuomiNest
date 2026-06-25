<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  Github, Cloud, Globe, Plus, Link2, Unlink, RefreshCw,
  ChevronDown, ChevronRight, Loader2, Check, AlertCircle,
  Trash2, ExternalLink, Database, Clock,
} from 'lucide-vue-next'
import type { LucideIcon } from 'lucide-vue-next'
import { useRepoSourceStore } from '../../stores/repo-source'
import type { RepoSource, RepoSourceType } from '../../types/marketplace'
import LumiButton from '../../components/common/LumiButton.vue'
import LumiInput from '../../components/common/LumiInput.vue'
import LumiModal from '../../components/common/LumiModal.vue'
import { formatDateRelative } from '../../utils/format'

const store = useRepoSourceStore()

const expandedSourceIds = ref<Set<string>>(new Set(['github-official']))
const showAddDialog = ref(false)
const addForm = ref({ name: '', url: '', description: '' })

const TYPE_CONFIG: Record<RepoSourceType, { icon: LucideIcon; label: string; color: string }> = {
  github: { icon: Github, label: 'GitHub', color: 'var(--task-purple)' },
  cloud: { icon: Cloud, label: '云端', color: 'var(--lumi-info)' },
  cdn: { icon: Globe, label: 'CDN', color: 'var(--lumi-sky)' },
  custom: { icon: Plus, label: '自定义', color: 'var(--lumi-amber)' },
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

</script>

<template>
  <div class="repo-source-panel">
    <div class="panel-header">
      <span class="panel-title">仓库来源</span>
      <LumiButton
        variant="ghost"
        size="sm"
        icon-only
        aria-label="添加自定义来源"
        title="添加自定义来源"
        @click="showAddDialog = true"
      >
        <Plus :size="14" />
      </LumiButton>
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
            <div class="source-type-icon" :style="{ color: TYPE_CONFIG[source.type]?.color || 'var(--text-muted)' }">
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
              :class="['status-icon', getStatusClass(source), { 'spin-animation': source.status === 'loading' }]"
            />
            <button
              class="lumi-toggle"
              :class="{ 'is-active': source.enabled }"
              :title="source.enabled ? '禁用' : '启用'"
              @click.stop="handleToggleSource(source.id)"
            ></button>
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
                {{ formatDateRelative(source.lastSyncedAt) }}
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
    <LumiModal v-model:visible="showAddDialog" title="添加自定义仓库来源">
      <div class="dialog-body">
        <div class="form-field">
          <label>名称</label>
          <LumiInput v-model="addForm.name" placeholder="输入仓库名称" />
        </div>
        <div class="form-field">
          <label>URL</label>
          <LumiInput v-model="addForm.url" placeholder="输入仓库地址（如 GitHub 仓库 URL）" />
        </div>
        <div class="form-field">
          <label>描述</label>
          <textarea v-model="addForm.description" class="lumi-textarea" placeholder="输入仓库描述（可选）" rows="3" />
        </div>
      </div>
      <template #footer>
        <LumiButton variant="ghost" size="md" @click="showAddDialog = false">
          取消
        </LumiButton>
        <LumiButton
          variant="primary"
          size="md"
          :disabled="!addForm.name.trim()"
          @click="handleAddCustom"
        >
          添加
        </LumiButton>
      </template>
    </LumiModal>
  </div>
</template>

<style scoped>
.repo-source-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-1);
}

.panel-title {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.panel-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-5) 0;
  color: var(--text-muted);
  font-size: var(--text-base);
}

.source-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.source-item {
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  transition: all var(--transition-fast);
}

.source-item.active {
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

.source-item.disabled {
  opacity: 0.6;
}

.source-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.source-header:hover {
  background: var(--surface-hover);
}

.source-item.active .source-header:hover {
  background: var(--lumi-brand-subtle);
}

.source-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1;
  min-width: 0;
}

.expand-btn {
  width: var(--space-5);
  height: var(--space-5);
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
  gap: calc(var(--space-1) / 4);
  min-width: 0;
}

.source-name {
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-url {
  font-size: var(--text-xs);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.source-item-count {
  font-size: var(--text-xs);
  color: var(--text-muted);
  background: var(--workspace-panel);
  padding: calc(var(--space-1) / 2) var(--space-1);
  border-radius: var(--radius-sm);
}

.status-icon {
  color: var(--text-muted);
}

.status-icon.status-loading {
  color: var(--lumi-brand);
}

.status-icon.status-loaded {
  color: var(--lumi-success);
}

.status-icon.status-error {
  color: var(--lumi-danger);
}

.lumi-toggle {
  border: none;
  padding: 0;
  background: transparent;
  cursor: pointer;
}

.source-detail {
  padding: 0 var(--space-3) var(--space-3) calc(var(--space-8) - var(--space-1) / 2);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.source-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
  line-height: var(--leading-normal);
  margin: 0;
}

/* 同步状态栏 */
.sync-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
}

.sync-status-bar.loading {
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

.sync-status-bar.loaded {
  color: var(--lumi-success);
  border-color: var(--task-green-border);
  background: var(--lumi-success-light);
}

.sync-status-bar.error {
  color: var(--lumi-danger);
  border-color: var(--task-red-border);
  background: var(--lumi-danger-light);
}

.sync-status-bar.idle {
  color: var(--text-muted);
}

.sync-status-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.sync-time {
  font-size: var(--text-xs);
  opacity: 0.7;
}

.source-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
  font-size: var(--text-xs);
}

.sub-markets {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sub-markets-label {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.sub-market-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-fast);
}

.sub-market-item.unlinked {
  opacity: 0.5;
  border-style: dashed;
}

.sub-market-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.sub-market-type-badge {
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
  padding: calc(var(--space-1) / 2) var(--space-1);
  border-radius: var(--radius-sm);
  text-transform: uppercase;
  flex-shrink: 0;
}

.sub-market-type-badge[data-type="plugin"] {
  background: var(--task-purple-soft);
  color: var(--task-purple);
}

.sub-market-type-badge[data-type="skill"] {
  background: var(--task-green-soft);
  color: var(--task-green);
}

.sub-market-type-badge[data-type="agent"] {
  background: var(--task-blue-soft);
  color: var(--task-blue);
}

.sub-market-name {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sub-market-count {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  background: var(--workspace-border);
  padding: calc(var(--space-1) / 4) calc(var(--space-1) + var(--space-1) / 4);
  border-radius: var(--radius-sm);
  min-width: var(--space-5);
  text-align: center;
}

.sub-market-actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-shrink: 0;
}

.sub-market-link {
  width: var(--space-6);
  height: var(--space-6);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.sub-market-link:hover {
  background: var(--surface-hover);
  color: var(--lumi-brand);
}

.sub-action-btn {
  width: var(--space-6);
  height: var(--space-6);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.sub-action-btn:hover {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.sub-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.unlink-btn,
.link-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  transition: all var(--transition-fast);
}

.unlink-btn {
  color: var(--text-muted);
}

.unlink-btn:hover {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.link-btn {
  color: var(--lumi-brand);
}

.link-btn:hover {
  background: var(--lumi-brand-light);
}

.source-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.action-btn:hover {
  background: var(--surface-hover);
}

.sync-btn:hover {
  color: var(--lumi-brand);
}

.cache-btn:hover {
  color: var(--lumi-amber);
}

.delete-btn:hover {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-field label {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}

/* Transitions */
.expand-enter-active {
  animation: expand-in var(--duration-normal) var(--ease-out-expo);
}

.expand-leave-active {
  animation: expand-in var(--duration-fast) var(--ease-out-expo) reverse;
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

</style>
