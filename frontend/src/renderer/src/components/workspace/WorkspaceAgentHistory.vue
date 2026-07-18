<script setup lang="ts">
import { computed } from 'vue'
import {
  Bot,
  ChevronLeft,
  Search,
  Plus,
  SquareCheck,
  MessageSquare,
  Loader2,
  Clock,
  Check,
  Pencil,
  Trash2,
} from 'lucide-vue-next'
import type { AgentProfile } from '../../types'
import type { TimeGroup, ConversationSearchResult } from './types'

const props = defineProps<{
  agent: AgentProfile | null
  searchQuery: string
  isSearchMode: boolean
  searchResults: ConversationSearchResult[]
  isSearching: boolean
  timeGroups: TimeGroup[]
  batchMode: boolean
  selectedIds: Set<string>
  currentConvId: string
  renamingConvId: string | null
  renamingTitle: string
}>()

const emit = defineEmits<{
  back: []
  'update:searchQuery': [query: string]
  'update:renamingTitle': [value: string]
  'new-conversation': []
  'toggle-batch-mode': []
  'select-all': []
  'batch-delete': []
  'select-conversation': [convId: string, searchKeyword?: string]
  'start-rename': [convId: string, currentTitle: string]
  'confirm-rename': []
  'cancel-rename': []
  'delete-conversation': [convId: string]
  'toggle-select': [convId: string]
}>()

const searchQueryModel = computed<string>({
  get: () => props.searchQuery,
  set: (value) => emit('update:searchQuery', value),
})

const renamingTitleModel = computed<string>({
  get: () => props.renamingTitle,
  set: (value) => emit('update:renamingTitle', value),
})

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const formatConvTime = (dateStr: string) => {
  const d = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diffDays = Math.floor((today.getTime() - target.getTime()) / 86400000)
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

  if (diffDays <= 0) return time
  if (diffDays === 1) return `昨天 ${time}`
  if (diffDays <= 7) return `${WEEKDAYS[d.getDay()]} ${time}`
  if (d.getFullYear() === now.getFullYear()) return `${d.getMonth() + 1}月${d.getDate()}日`
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

const highlightSnippet = (snippet: string): string => {
  if (!snippet) return ''
  const escaped = snippet
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
  const q = props.searchQuery.trim()
  if (!q) return escaped
  const escapedQ = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${escapedQ})`, 'gi')
  return escaped.replace(regex, '<mark>$1</mark>')
}
</script>

<template>
  <div class="agent-history-panel">
    <div class="left-panel-header">
      <button class="back-btn" title="返回联系人" @click="emit('back')">
        <ChevronLeft :size="16" />
      </button>
      <div class="left-panel-title">
        <div class="left-panel-avatar" :style="{ color: agent?.color }">
          <img v-if="agent?.avatar" :src="agent.avatar" class="left-panel-avatar-img" :alt="agent?.name || ''" />
          <Bot v-else :size="14" />
        </div>
        <span class="left-panel-name">{{ agent?.name }}</span>
      </div>
    </div>

    <div class="sidebar-header">
      <div class="conv-search">
        <Search :size="14" class="search-icon" />
        <input v-model="searchQueryModel" type="text" placeholder="搜索对话..." />
      </div>
      <div class="sidebar-actions">
        <button class="new-conv-btn" title="创建新对话" @click="emit('new-conversation')">
          <Plus :size="14" />
          <span>新对话</span>
        </button>
        <button
          :class="['batch-toggle-btn', { active: batchMode }]"
          title="批量操作"
          @click="emit('toggle-batch-mode')"
        >
          <SquareCheck :size="14" />
        </button>
      </div>
    </div>

    <div v-if="batchMode" class="batch-toolbar">
      <button class="batch-action-btn" @click="emit('select-all')">全选</button>
      <span class="batch-count">已选 {{ selectedIds.size }} 项</span>
      <button
        :class="['batch-delete-btn', { disabled: selectedIds.size === 0 }]"
        :disabled="selectedIds.size === 0"
        title="批量删除"
        @click="emit('batch-delete')"
      >
        <Trash2 :size="13" />
        删除
      </button>
    </div>

    <div class="conv-list">
      <template v-if="isSearchMode">
        <div v-if="isSearching" class="conv-empty">
          <Loader2 :size="20" class="spin-animation" />
          <span>搜索中...</span>
        </div>
        <template v-else>
          <div
            v-for="result in searchResults"
            :key="result.id"
            :class="['conv-item', { active: currentConvId === result.id }]"
            @click="emit('select-conversation', result.id, searchQuery.trim())"
          >
            <MessageSquare :size="14" class="conv-item-icon" />
            <div class="conv-item-content">
              <span class="conv-item-title">{{ result.title }}</span>
              <span class="conv-item-snippet" v-html="highlightSnippet(result.snippet)"></span>
            </div>
          </div>
          <div v-if="searchResults.length === 0" class="conv-empty">
            <MessageSquare :size="24" />
            <span>未找到匹配的会话</span>
          </div>
        </template>
      </template>

      <template v-else>
        <template v-for="group in timeGroups" :key="group.label">
          <div class="time-group">
            <div class="time-group-label">
              <Clock :size="12" />
              <span>{{ group.label }}</span>
            </div>
            <div
              v-for="conv in group.items"
              :key="conv.id"
              :class="['conv-item', { active: currentConvId === conv.id }]"
              @click="batchMode ? emit('toggle-select', conv.id) : emit('select-conversation', conv.id)"
            >
              <div v-if="batchMode" class="conv-item-checkbox" @click.stop="emit('toggle-select', conv.id)">
                <div :class="['checkbox-box', { checked: selectedIds.has(conv.id) }]">
                  <Check v-if="selectedIds.has(conv.id)" :size="10" />
                </div>
              </div>
              <MessageSquare :size="14" class="conv-item-icon" />
              <div class="conv-item-content">
                <template v-if="renamingConvId === conv.id">
                  <input
                    v-model="renamingTitleModel"
                    class="conv-item-rename-input"
                    maxlength="200"
                    @keydown.enter="emit('confirm-rename')"
                    @keydown.escape="emit('cancel-rename')"
                    @blur="emit('confirm-rename')"
                    @click.stop
                  />
                </template>
                <template v-else>
                  <span class="conv-item-title">{{ conv.title }}</span>
                  <span class="conv-item-time">{{ formatConvTime(conv.updated_at) }}</span>
                </template>
              </div>
              <template v-if="!batchMode">
                <button v-if="renamingConvId !== conv.id" class="conv-item-rename" title="重命名" @click.stop="emit('start-rename', conv.id, conv.title)">
                  <Pencil :size="13" />
                </button>
                <button class="conv-item-delete" title="删除对话" @click.stop="emit('delete-conversation', conv.id)">
                  <Trash2 :size="13" />
                </button>
              </template>
            </div>
          </div>
        </template>

        <div v-if="timeGroups.length === 0" class="conv-empty">
          <MessageSquare :size="24" />
          <span>暂无历史记录</span>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.agent-history-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.left-panel-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 10px var(--space-3);
  flex-shrink: 0;
  border-bottom: 1px solid var(--workspace-border);
}

.back-btn {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.back-btn:hover {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.left-panel-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  flex: 1;
}

.left-panel-avatar {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-xs);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}

.left-panel-avatar-img {
  width: 100%;
  height: 100%;
  border-radius: inherit;
  object-fit: cover;
}

.left-panel-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-header {
  padding: var(--space-3) var(--space-3) var(--space-2);
  flex-shrink: 0;
}

.conv-search {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 10px;
  background: var(--surface);
  border-radius: var(--radius-sm);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-fast);
  margin-bottom: var(--space-2);
}

.conv-search:focus-within {
  border-color: var(--lumi-brand-border);
}

.conv-search .search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.conv-search input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--text-base);
  color: var(--text-primary);
  min-width: 0;
}

.conv-search input::placeholder {
  color: var(--text-muted);
}

.sidebar-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.new-conv-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.new-conv-btn:hover {
  background: var(--lumi-brand-glow);
}

.batch-toggle-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  background: transparent;
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.batch-toggle-btn:hover {
  color: var(--text-secondary);
  background: var(--workspace-hover);
}

.batch-toggle-btn.active {
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  border-color: var(--lumi-brand-border);
}

.batch-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px var(--space-3);
  background: var(--lumi-brand-subtle);
  border-bottom: 1px solid var(--workspace-border);
  flex-shrink: 0;
}

.batch-action-btn {
  font-size: var(--text-sm);
  color: var(--lumi-brand);
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.batch-action-btn:hover {
  background: var(--lumi-brand-light);
}

.batch-count {
  flex: 1;
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-align: center;
}

.batch-delete-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--lumi-danger);
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.batch-delete-btn:hover:not(.disabled) {
  background: var(--lumi-danger-light);
}

.batch-delete-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-1) var(--space-2) var(--space-3);
}

.time-group {
  margin-bottom: var(--space-1);
}

.time-group-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-2) var(--space-1);
  font-size: var(--text-2xs);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.conv-item:hover {
  background: var(--workspace-hover);
}

.conv-item.active {
  background: var(--lumi-brand-light);
}

.conv-item-checkbox {
  flex-shrink: 0;
  cursor: pointer;
}

.checkbox-box {
  width: var(--space-4);
  height: var(--space-4);
  border-radius: 4px;
  border: 1px solid var(--workspace-border);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
}

.checkbox-box.checked {
  background: var(--lumi-brand);
  border-color: var(--lumi-brand);
  color: var(--text-inverse);
}

.conv-item-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.conv-item-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conv-item-title {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-item-time {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.conv-item-snippet {
  font-size: var(--text-xs);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
}

.conv-item-snippet :deep(mark) {
  background: var(--lumi-amber-soft);
  color: var(--lumi-amber-dark);
  padding: 0 2px;
  border-radius: 2px;
}

.conv-item-rename-input {
  width: 100%;
  border: 1px solid var(--lumi-brand-border);
  border-radius: 4px;
  padding: 2px var(--space-1);
  font-size: var(--text-base);
  color: var(--text-primary);
  background: var(--surface);
  outline: none;
}

.conv-item-rename,
.conv-item-delete {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  opacity: 0;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.conv-item:hover .conv-item-rename,
.conv-item:hover .conv-item-delete {
  opacity: 1;
}

.conv-item-rename:hover {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.conv-item-delete:hover {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.conv-empty {
  padding: var(--space-7) var(--space-4);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-muted);
}

.conv-empty span {
  font-size: var(--text-sm);
}

.spin-animation {
  animation: luominest-spin 1s linear infinite;
}

@keyframes luominest-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
