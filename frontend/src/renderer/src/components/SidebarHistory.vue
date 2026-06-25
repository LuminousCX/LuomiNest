<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
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
import LumiButton from './common/LumiButton.vue'
import LumiEmptyState from './common/LumiEmptyState.vue'
import { useAgentStore } from '../stores/agent'
import { useChatStore } from '../stores/chat'
import { useChatTrashStore } from '../stores/chat-trash'
import { useDebouncedSearch } from '../composables/useDebouncedSearch'
import type { ConversationListItem, ConversationSearchResult } from '../types'
import { formatDateCalendar } from '../utils/format'

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
const { results: searchResults, isSearching } = useDebouncedSearch<ConversationSearchResult[]>(
  searchQuery,
  (q) => chatStore.searchConversations(q),
  300,
)

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
        <LumiButton variant="primary" size="sm" block @click="handleNewConversation">
          <template #icon>
            <Plus :size="15" />
          </template>
          创建新对话
        </LumiButton>
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
      <LumiButton
        variant="danger"
        size="sm"
        :disabled="selectedIds.size === 0"
        @click="handleBatchDelete"
      >
        <template #icon>
          <Trash2 :size="13" />
        </template>
        删除
      </LumiButton>
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
          <LumiEmptyState v-if="searchResults.length === 0" :icon="MessageSquare" title="未找到匹配的会话" size="sm" />
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
                  <span class="history-item-time">{{ formatDateCalendar(conv.updated_at) }}</span>
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

        <LumiEmptyState v-if="timeGroups.length === 0" :icon="MessageSquare" title="暂无历史记录" size="sm" />
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
  padding: var(--space-3) var(--space-4) var(--space-2);
}

.panel-header-actions {
  display: flex;
  gap: var(--space-1);
  margin-top: var(--space-2);
}

.panel-header-actions .lumi-btn {
  flex: 1;
}

.search-box {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  height: calc(var(--space-8) + var(--space-2));
  background: var(--surface);
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  transition: all var(--transition-fast);
  box-sizing: border-box;
}

.search-box:focus-within {
  border-color: var(--lumi-brand);
  box-shadow: var(--input-focus-ring);
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
  font-size: var(--text-base);
  color: var(--text);
}

.search-input::placeholder {
  color: var(--text-muted);
}

.batch-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--btn-height-md);
  height: var(--btn-height-md);
  border: none;
  background: var(--surface-hover);
  color: var(--text-muted);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.batch-toggle-btn:hover {
  background: var(--surface-active);
  color: var(--text);
}

.batch-toggle-btn.active {
  background: var(--lumi-brand);
  color: var(--text-inverse);
}

.batch-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--border-light);
}

.batch-action-btn {
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--border-light);
  background: var(--surface);
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--text-sm);
  transition: all var(--transition-fast);
}

.batch-action-btn:hover {
  background: var(--surface-hover);
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
}

.batch-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
  flex: 1;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: var(--space-1) var(--space-2);
}

.time-group {
  margin-bottom: var(--space-2);
}

.time-group-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  user-select: none;
}

.history-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
  position: relative;
}

.history-item:hover {
  background: var(--surface-hover);
}

.history-item.active {
  background: var(--lumi-brand-light);
}

.history-item-indicator {
  width: calc(var(--space-1) / 1.5);
  height: var(--space-4);
  border-radius: calc(var(--space-1) / 2);
  background: transparent;
  flex-shrink: 0;
  transition: background var(--transition-fast);
}

.history-item.active .history-item-indicator {
  background: var(--lumi-brand);
}

.history-item-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.history-item.active .history-item-icon {
  color: var(--lumi-brand);
}

.history-item-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: calc(var(--space-1) / 2);
}

.history-item-title {
  font-size: var(--text-base);
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-item.active .history-item-title {
  color: var(--lumi-brand);
  font-weight: var(--font-medium);
}

.history-item-time {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.history-item-snippet {
  font-size: var(--text-sm);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-item-snippet :deep(mark) {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  padding: 0 calc(var(--space-1) / 4);
  border-radius: calc(var(--space-1) / 2);
}

.history-item-delete {
  display: none;
  align-items: center;
  justify-content: center;
  width: calc(var(--space-5) + var(--space-1));
  height: calc(var(--space-5) + var(--space-1));
  border: none;
  background: transparent;
  color: var(--text-muted);
  border-radius: var(--radius-md);
  cursor: pointer;
  flex-shrink: 0;
  transition: all var(--transition-fast);
}

.history-item:hover .history-item-delete {
  display: flex;
}

.history-item-delete:hover {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.history-item-rename {
  display: none;
  align-items: center;
  justify-content: center;
  width: calc(var(--space-5) + var(--space-1));
  height: calc(var(--space-5) + var(--space-1));
  border: none;
  background: transparent;
  color: var(--text-muted);
  border-radius: var(--radius-md);
  cursor: pointer;
  flex-shrink: 0;
  transition: all var(--transition-fast);
}

.history-item:hover .history-item-rename,
.history-item:focus-within .history-item-rename,
.history-item-rename:focus {
  display: flex;
}

.history-item-rename:hover {
  background: var(--surface-active);
  color: var(--text);
}

.history-item-rename-input {
  width: 100%;
  height: calc(var(--space-5) + var(--space-1));
  border: 1px solid var(--lumi-brand);
  border-radius: var(--radius-md);
  padding: 0 var(--space-1);
  font-size: var(--text-base);
  color: var(--text);
  background: var(--surface);
  outline: none;
  box-shadow: var(--input-focus-ring);
}

.history-item-checkbox {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-5);
  height: var(--space-5);
  flex-shrink: 0;
  cursor: pointer;
}

.checkbox-box {
  width: var(--space-4);
  height: var(--space-4);
  border: 1.5px solid var(--border);
  border-radius: var(--space-1);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
  color: var(--text-inverse);
}

.checkbox-box.checked {
  background: var(--lumi-brand);
  border-color: var(--lumi-brand);
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-8) var(--space-5);
  color: var(--text-muted);
  font-size: var(--text-base);
}

.trash-entry-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: var(--space-2);
  margin: var(--space-2);
  border: 1px dashed var(--border-light);
  background: transparent;
  color: var(--text-muted);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--text-sm);
  transition: all var(--transition-fast);
}

.trash-entry-btn:hover {
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

.trash-badge {
  padding: 0 var(--space-1);
  height: var(--badge-height);
  line-height: var(--badge-height);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  background: var(--lumi-danger);
  color: var(--text-inverse);
  border-radius: var(--radius-full);
}

.spin-animation {
  animation: spin var(--duration-slow) linear infinite;
}
</style>
