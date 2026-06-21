<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  MessageSquare,
  Check,
  Clock,
  Loader2,
  Plus,
  SquareCheck,
  Search,
  Trash2,
  Pencil,
} from 'lucide-vue-next'
import { useAgentStore } from '../stores/agent'
import { useChatStore } from '../stores/chat'
import { useChatTrashStore } from '../stores/chat-trash'
import type { ConversationListItem, ConversationSearchResult } from '../types'

defineProps<{
  trashCount: number
}>()

const emit = defineEmits<{
  (e: 'open-trash'): void
}>()

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()
const chatStore = useChatStore()

const searchQuery = ref('')
const searchResults = ref<ConversationSearchResult[]>([])
const isSearching = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null
let searchSeq = 0

watch(searchQuery, (q) => {
  if (searchTimer) clearTimeout(searchTimer)
  if (!q.trim()) {
    searchResults.value = []
    isSearching.value = false
    return
  }
  isSearching.value = true
  searchSeq++
  const currentSeq = searchSeq
  searchTimer = setTimeout(async () => {
    const results = await chatStore.searchConversations(q)
    if (currentSeq === searchSeq) {
      searchResults.value = results
      isSearching.value = false
    }
  }, 300)
})

const isSearchMode = computed(() => searchQuery.value.trim().length > 0)

interface TimeGroup {
  label: string
  items: ConversationListItem[]
}

const timeGroups = computed<TimeGroup[]>(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())

  const groups: TimeGroup[] = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '近7天', items: [] },
    { label: '更早', items: [] }
  ]

  for (const conv of chatStore.conversations) {
    const d = new Date(conv.updated_at)
    const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
    const diffDays = Math.floor((today.getTime() - target.getTime()) / 86400000)

    if (diffDays <= 0) groups[0].items.push(conv)
    else if (diffDays === 1) groups[1].items.push(conv)
    else if (diffDays <= 7) groups[2].items.push(conv)
    else groups[3].items.push(conv)
  }

  return groups.filter(g => g.items.length > 0)
})

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const formatTime = (dateStr: string) => {
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
  const q = searchQuery.value.trim()
  if (!q) return escaped
  const escapedQ = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${escapedQ})`, 'gi')
  return escaped.replace(regex, '<mark>$1</mark>')
}

const selectConversation = (convId: string, searchKeyword?: string) => {
  if (searchKeyword) {
    chatStore.pendingSearchKeyword = searchKeyword
    chatStore.searchScrollTarget = { convId, keyword: searchKeyword }
  }
  chatStore.loadConversation(convId)
  if (route.path !== '/workspace') {
    router.push('/workspace')
  }
}

const handleDeleteConversation = async (convId: string) => {
  try {
    await chatStore.deleteConversation(convId, agentStore.activeAgent?.id)
  } catch (e: unknown) {
    console.error('Failed to delete conversation:', e)
  }
}

const handleNewConversation = () => {
  const prevConvId = chatStore.currentConvId
  if (prevConvId) {
    chatStore.leaveCurrentConversation(prevConvId).catch(() => {})
  }
  chatStore.clearMessages()
  if (route.path !== '/workspace') {
    router.push('/workspace')
  }
}

const batchMode = ref(false)
const selectedIds = ref<Set<string>>(new Set())

const renamingConvId = ref<string | null>(null)
const renamingTitle = ref('')

const startRename = (convId: string, currentTitle: string) => {
  renamingConvId.value = convId
  renamingTitle.value = currentTitle
  nextTick(() => {
    const input = document.querySelector('.history-item-rename-input') as HTMLInputElement
    if (input) {
      input.focus()
      input.select()
    }
  })
}

const confirmRename = async () => {
  if (!renamingConvId.value) return
  const newTitle = renamingTitle.value.trim()
  if (!newTitle) {
    renamingConvId.value = null
    return
  }
  if (newTitle.length > 200) {
    return
  }
  const success = await chatStore.renameConversation(renamingConvId.value, newTitle, agentStore.activeAgent?.id)
  if (success) {
    renamingConvId.value = null
    renamingTitle.value = ''
  }
}

const cancelRename = () => {
  renamingConvId.value = null
  renamingTitle.value = ''
}

const toggleBatchMode = () => {
  batchMode.value = !batchMode.value
  if (!batchMode.value) {
    selectedIds.value = new Set()
  }
}

const toggleSelect = (convId: string) => {
  const next = new Set(selectedIds.value)
  if (next.has(convId)) {
    next.delete(convId)
  } else {
    next.add(convId)
  }
  selectedIds.value = next
}

const selectAll = () => {
  const allIds = chatStore.conversations.map(c => c.id)
  if (selectedIds.value.size === allIds.length) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(allIds)
  }
}

const chatTrashStore = useChatTrashStore()

const handleBatchDelete = async () => {
  if (selectedIds.value.size === 0) return
  try {
    await chatTrashStore.batchSoftDelete(Array.from(selectedIds.value), agentStore.activeAgent?.id, () => chatStore.fetchConversations(agentStore.activeAgent?.id))
    selectedIds.value = new Set()
    batchMode.value = false
  } catch (e: unknown) {
    console.error('Failed to batch delete:', e)
  }
}

const showHistoryPanel = computed(() => {
  return route.path === '/workspace'
})

const handleOpenTrash = () => {
  emit('open-trash')
}
</script>

<template>
  <template v-if="showHistoryPanel">
    <div class="panel-header">
      <div class="search-box">
        <Search :size="15" class="search-icon" />
        <input v-model="searchQuery" type="text" placeholder="搜索历史记录..." class="search-input" />
      </div>
      <div class="panel-header-actions">
        <button class="new-conv-btn" title="创建新对话" @click="handleNewConversation">
          <Plus :size="15" />
          <span>创建新对话</span>
        </button>
        <button
          :class="['batch-toggle-btn', { active: batchMode }]"
          title="批量操作"
          @click="toggleBatchMode"
        >
          <SquareCheck :size="15" />
        </button>
      </div>
    </div>

    <div v-if="batchMode" class="batch-toolbar">
      <button class="batch-action-btn" @click="selectAll">全选</button>
      <span class="batch-count">已选 {{ selectedIds.size }} 项</span>
      <button
        :class="['batch-delete-btn', { disabled: selectedIds.size === 0 }]"
        :disabled="selectedIds.size === 0"
        title="批量删除"
        @click="handleBatchDelete"
      >
        <Trash2 :size="13" />
        删除
      </button>
    </div>

    <div class="history-list">
      <template v-if="isSearchMode">
        <div v-if="isSearching" class="history-empty">
          <Loader2 :size="20" class="spin-animation" />
          <span>搜索中...</span>
        </div>
        <template v-else>
          <div
            v-for="result in searchResults"
            :key="result.id"
            :class="['history-item', { active: chatStore.currentConvId === result.id }]"
            @click="selectConversation(result.id, searchQuery.trim())"
          >
            <div class="history-item-indicator" />
            <MessageSquare :size="14" class="history-item-icon" />
            <div class="history-item-content">
              <span class="history-item-title">{{ result.title }}</span>
              <span class="history-item-snippet" v-html="highlightSnippet(result.snippet)"></span>
            </div>
          </div>
          <div v-if="searchResults.length === 0" class="history-empty">
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
              :class="['history-item', { active: chatStore.currentConvId === conv.id }]"
              @click="batchMode ? toggleSelect(conv.id) : selectConversation(conv.id)"
            >
              <div v-if="batchMode" class="history-item-checkbox" @click.stop="toggleSelect(conv.id)">
                <div :class="['checkbox-box', { checked: selectedIds.has(conv.id) }]">
                  <Check v-if="selectedIds.has(conv.id)" :size="10" />
                </div>
              </div>
              <div class="history-item-indicator" />
              <MessageSquare :size="14" class="history-item-icon" />
              <div class="history-item-content">
                <template v-if="renamingConvId === conv.id">
                  <input
                    v-model="renamingTitle"
                    class="history-item-rename-input"
                    maxlength="200"
                    @keydown.enter="confirmRename"
                    @keydown.escape="cancelRename"
                    @blur="confirmRename"
                    @click.stop
                  />
                </template>
                <template v-else>
                  <span class="history-item-title">{{ conv.title }}</span>
                  <span class="history-item-time">{{ formatTime(conv.updated_at) }}</span>
                </template>
              </div>
              <template v-if="!batchMode">
                <button v-if="renamingConvId !== conv.id" class="history-item-rename" title="重命名" @click.stop="startRename(conv.id, conv.title)">
                  <Pencil :size="13" />
                </button>
                <button class="history-item-delete" title="删除对话" @click.stop="handleDeleteConversation(conv.id)">
                  <Trash2 :size="13" />
                </button>
              </template>
            </div>
          </div>
        </template>

        <div v-if="timeGroups.length === 0" class="history-empty">
          <MessageSquare :size="24" />
          <span>暂无历史记录</span>
        </div>
      </template>
    </div>

    <button class="trash-entry-btn" title="回收站" @click="handleOpenTrash">
      <Trash2 :size="14" />
      <span>回收站</span>
      <span v-if="trashCount > 0" class="trash-badge">{{ trashCount }}</span>
    </button>
  </template>
</template>

<style scoped>
.panel-header {
  padding: 12px 14px 8px;
}

.panel-header-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.panel-header-actions .new-conv-btn {
  flex: 1;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  height: 48px;
  background: var(--surface);
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  transition: all var(--transition-fast);
  box-sizing: border-box;
}

.search-box:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  width: 100%;
  height: 100%;
  background: transparent;
  border: none;
  outline: none;
  font-size: 13px;
  color: var(--text-primary);
}

.search-input::placeholder {
  color: var(--text-muted);
}

.new-conv-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 12px;
  border: none;
  background: var(--lumi-primary);
  color: var(--text-inverse);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: background 0.15s ease-in-out;
}

.new-conv-btn:hover {
  background: var(--lumi-primary-hover);
}

.batch-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  background: var(--surface-hover);
  color: var(--text-muted);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s ease-in-out;
}

.batch-toggle-btn:hover {
  background: var(--surface-active);
  color: var(--text-primary);
}

.batch-toggle-btn.active {
  background: var(--lumi-primary);
  color: var(--text-inverse);
}

.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--divider-horizontal);
}

.batch-action-btn {
  padding: 4px 10px;
  border: 1px solid var(--divider-horizontal);
  background: var(--surface);
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s ease-in-out;
}

.batch-action-btn:hover {
  background: var(--surface-hover);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.batch-count {
  font-size: 12px;
  color: var(--text-muted);
  flex: 1;
}

.batch-delete-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: none;
  background: var(--color-danger);
  color: var(--text-inverse);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 12px;
  transition: opacity 0.15s ease-in-out;
}

.batch-delete-btn:hover {
  opacity: 0.85;
}

.batch-delete-btn.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 4px 8px;
}

.time-group {
  margin-bottom: 8px;
}

.time-group-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  user-select: none;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.15s ease-in-out;
  position: relative;
}

.history-item:hover {
  background: var(--surface-hover);
}

.history-item.active {
  background: var(--lumi-primary-soft);
}

.history-item-indicator {
  width: 3px;
  height: 16px;
  border-radius: 2px;
  background: transparent;
  flex-shrink: 0;
  transition: background 0.15s ease-in-out;
}

.history-item.active .history-item-indicator {
  background: var(--lumi-primary);
}

.history-item-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.history-item.active .history-item-icon {
  color: var(--lumi-primary);
}

.history-item-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.history-item-title {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-item.active .history-item-title {
  color: var(--lumi-primary);
  font-weight: 500;
}

.history-item-time {
  font-size: 11px;
  color: var(--text-muted);
}

.history-item-snippet {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-item-snippet :deep(mark) {
  background: var(--lumi-primary-soft);
  color: var(--lumi-primary);
  padding: 0 1px;
  border-radius: 2px;
}

.history-item-delete {
  display: none;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  border-radius: var(--radius-md);
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s ease-in-out;
}

.history-item:hover .history-item-delete {
  display: flex;
}

.history-item-delete:hover {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

.history-item-rename {
  display: none;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  border-radius: var(--radius-md);
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s ease-in-out;
}

.history-item:hover .history-item-rename,
.history-item:focus-within .history-item-rename,
.history-item-rename:focus {
  display: flex;
}

.history-item-rename:hover {
  background: var(--surface-active);
  color: var(--text-primary);
}

.history-item-rename-input {
  width: 100%;
  height: 24px;
  border: 1px solid var(--lumi-primary);
  border-radius: var(--radius-md);
  padding: 0 6px;
  font-size: 13px;
  color: var(--text-primary);
  background: var(--surface);
  outline: none;
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.history-item-checkbox {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  cursor: pointer;
}

.checkbox-box {
  width: 16px;
  height: 16px;
  border: 1.5px solid var(--divider-vertical);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease-in-out;
  color: var(--text-inverse);
}

.checkbox-box.checked {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 20px;
  color: var(--text-muted);
  font-size: 13px;
}

.trash-entry-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  margin: 8px 8px;
  border: 1px dashed var(--divider-horizontal);
  background: transparent;
  color: var(--text-muted);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s ease-in-out;
}

.trash-entry-btn:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-soft);
}

.trash-badge {
  padding: 0 6px;
  height: 18px;
  line-height: 18px;
  font-size: 11px;
  font-weight: 600;
  background: var(--color-danger);
  color: var(--text-inverse);
  border-radius: var(--radius-full);
}

.spin-animation {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
