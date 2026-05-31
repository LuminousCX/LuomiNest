<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  MessageCircle,
  GitBranch,
  Lightbulb,
  CheckSquare,
  Globe,
  Search,
  Settings,
  Users,
  Palette,
  Brain,
  Package,
  Trash2,
  Check,
  MessageSquare,
  Clock,
  Loader2,
  Plus,
  Undo2,
  ArrowLeft,
  SquareCheck,
  X,
  AlertTriangle,
  LayoutDashboard,
} from 'lucide-vue-next'
import { useAgentStore } from '../stores/agent'
import { useChatStore } from '../stores/chat'
import LumiBrandStar from './common/LumiBrandStar.vue'
import type { ConversationListItem, ConversationSearchResult } from '../types'

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

const navItems = [
  { id: '/dashboard', label: '控制台', icon: LayoutDashboard },
  { id: '/workspace', label: '对话', icon: MessageCircle },
  { id: '/social', label: '社交', icon: Users },
  { id: '/workflow', label: '工作流', icon: GitBranch },
  { id: '/inspire', label: '灵感', icon: Lightbulb },
  { id: '/tasks', label: '任务', icon: CheckSquare },
  { id: '/avatar', label: '皮套', icon: Palette },
  { id: '/memory', label: '记忆', icon: Brain },
  { id: '/market', label: '扩展', icon: Package },
  { id: '/browser', label: '浏览器', icon: Globe }
]

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
  } catch (e: any) {
    console.error('Failed to delete conversation:', e)
  }
}

const showCreateDialog = ref(false)
const newAgentForm = ref({
  name: '',
  description: '',
  systemPrompt: '',
  color: '#147EBC'
})
const agentColors = ['#147EBC', '#6366f1', '#f59e0b', '#f43f5e', '#8b5cf6', '#06b6d4', '#84cc16', '#ec4899']

const handleCreateAgent = async () => {
  if (!newAgentForm.value.name.trim()) return
  try {
    await agentStore.createAgent({
      name: newAgentForm.value.name.trim(),
      description: newAgentForm.value.description.trim(),
      systemPrompt: newAgentForm.value.systemPrompt.trim(),
      color: newAgentForm.value.color,
      capabilities: ['chat'],
    })
    showCreateDialog.value = false
    newAgentForm.value = { name: '', description: '', systemPrompt: '', color: '#147EBC' }
    router.push('/workspace')
  } catch (e: any) {
    console.error('Failed to create agent:', e)
  }
}

const handleNewConversation = async () => {
  try {
    await chatStore.createConversation()
    if (route.path !== '/workspace') {
      router.push('/workspace')
    }
  } catch (e: any) {
    console.error('Failed to create conversation:', e)
  }
}

const showTrash = ref(false)
const batchMode = ref(false)
const selectedIds = ref<Set<string>>(new Set())
const trashBatchMode = ref(false)
const trashSelectedIds = ref<Set<string>>(new Set())

const trashCount = computed(() => chatStore.trashItems.length)

const openTrash = async () => {
  showTrash.value = true
  trashBatchMode.value = false
  trashSelectedIds.value = new Set()
  await chatStore.fetchTrash(agentStore.activeAgent?.id)
}

const closeTrash = () => {
  showTrash.value = false
  trashBatchMode.value = false
  trashSelectedIds.value = new Set()
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

const handleBatchDelete = async () => {
  if (selectedIds.value.size === 0) return
  try {
    await chatStore.batchSoftDelete(Array.from(selectedIds.value), agentStore.activeAgent?.id)
    selectedIds.value = new Set()
    batchMode.value = false
  } catch (e: any) {
    console.error('Failed to batch delete:', e)
  }
}

const toggleTrashBatchMode = () => {
  trashBatchMode.value = !trashBatchMode.value
  if (!trashBatchMode.value) {
    trashSelectedIds.value = new Set()
  }
}

const toggleTrashSelect = (convId: string) => {
  const next = new Set(trashSelectedIds.value)
  if (next.has(convId)) {
    next.delete(convId)
  } else {
    next.add(convId)
  }
  trashSelectedIds.value = next
}

const selectAllTrash = () => {
  const allIds = chatStore.trashItems.map(t => t.id)
  if (trashSelectedIds.value.size === allIds.length) {
    trashSelectedIds.value = new Set()
  } else {
    trashSelectedIds.value = new Set(allIds)
  }
}

const handleBatchRestore = async () => {
  if (trashSelectedIds.value.size === 0) return
  try {
    await chatStore.batchRestore(Array.from(trashSelectedIds.value), agentStore.activeAgent?.id)
    trashSelectedIds.value = new Set()
    trashBatchMode.value = false
  } catch (e: any) {
    console.error('Failed to batch restore:', e)
  }
}

const handleBatchPermanentDelete = async () => {
  if (trashSelectedIds.value.size === 0) return
  showTrashConfirm.value = true
  trashConfirmAction.value = 'batch-permanent-delete'
}

const handleRestoreItem = async (convId: string) => {
  try {
    await chatStore.restoreConversation(convId, agentStore.activeAgent?.id)
  } catch (e: any) {
    console.error('Failed to restore:', e)
  }
}

const handlePermanentDeleteItem = async (convId: string) => {
  showTrashConfirm.value = true
  trashConfirmAction.value = 'permanent-delete'
  trashConfirmTargetId.value = convId
}

const handleEmptyTrash = () => {
  showTrashConfirm.value = true
  trashConfirmAction.value = 'empty-trash'
}

const showTrashConfirm = ref(false)
const trashConfirmAction = ref('')
const trashConfirmTargetId = ref('')

const trashConfirmMessage = computed(() => {
  if (trashConfirmAction.value === 'empty-trash') return '确定要清空回收站吗？所有对话将被永久删除，无法恢复。'
  if (trashConfirmAction.value === 'batch-permanent-delete') return `确定要永久删除选中的 ${trashSelectedIds.value.size} 个对话吗？此操作无法撤销。`
  if (trashConfirmAction.value === 'permanent-delete') return '确定要永久删除这个对话吗？此操作无法撤销。'
  return ''
})

const handleTrashConfirm = async () => {
  try {
    if (trashConfirmAction.value === 'empty-trash') {
      await chatStore.emptyTrash(agentStore.activeAgent?.id)
    } else if (trashConfirmAction.value === 'batch-permanent-delete') {
      await chatStore.batchPermanentDelete(Array.from(trashSelectedIds.value), agentStore.activeAgent?.id)
      trashSelectedIds.value = new Set()
      trashBatchMode.value = false
    } else if (trashConfirmAction.value === 'permanent-delete') {
      await chatStore.permanentDeleteConversation(trashConfirmTargetId.value, agentStore.activeAgent?.id)
    }
  } catch (e: any) {
    console.error('Failed to execute trash action:', e)
  }
  showTrashConfirm.value = false
  trashConfirmAction.value = ''
  trashConfirmTargetId.value = ''
}

const formatDeleteTime = (dateStr: string) => {
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

onMounted(async () => {
  await agentStore.fetchAgents()
  if (agentStore.activeAgent?.id) {
    chatStore.fetchTrash(agentStore.activeAgent.id)
  }
})
</script>

<template>
  <div class="lumi-sidebar">
    <div class="sidebar-icon-rail">
      <div class="rail-top">
        <button class="avatar-btn" aria-label="LuminousChenXi 账户">
          <div class="avatar-ring">
            <LumiBrandStar :size="20" :animated="false" />
          </div>
        </button>
        <nav class="icon-nav">
          <button
            v-for="item in navItems"
            :key="item.id"
            :class="['icon-btn', { active: route.path === item.id || route.path.startsWith(item.id + '/') }]"
            :aria-label="item.label"
            @click="router.push(item.id)"
          >
            <component :is="item.icon" :size="20" />
          </button>
        </nav>
      </div>
      <div class="rail-bottom">
        <button class="icon-btn" aria-label="设置" @click="router.push('/settings')">
          <Settings :size="20" />
        </button>
      </div>
    </div>

    <div v-if="route.path === '/workspace'" class="sidebar-history-panel">
      <template v-if="!showTrash">
        <div class="panel-header">
          <div class="search-box">
            <Search :size="15" class="search-icon" />
            <input v-model="searchQuery" type="text" placeholder="搜索历史记录..." class="search-input" />
          </div>
          <div class="panel-header-actions">
            <button class="new-conv-btn" @click="handleNewConversation">
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
                    <span class="history-item-title">{{ conv.title }}</span>
                    <span class="history-item-time">{{ formatTime(conv.updated_at) }}</span>
                  </div>
                  <button v-if="!batchMode" class="history-item-delete" @click.stop="handleDeleteConversation(conv.id)">
                    <Trash2 :size="13" />
                  </button>
                </div>
              </div>
            </template>

            <div v-if="timeGroups.length === 0" class="history-empty">
              <MessageSquare :size="24" />
              <span>暂无历史记录</span>
            </div>
          </template>
        </div>

        <button class="trash-entry-btn" @click="openTrash">
          <Trash2 :size="14" />
          <span>回收站</span>
          <span v-if="trashCount > 0" class="trash-badge">{{ trashCount }}</span>
        </button>
      </template>

      <template v-else>
        <div class="trash-header">
          <button class="trash-back-btn" @click="closeTrash">
            <ArrowLeft :size="16" />
          </button>
          <span class="trash-title">回收站</span>
          <button
            :class="['batch-toggle-btn', { active: trashBatchMode }]"
            title="批量操作"
            @click="toggleTrashBatchMode"
          >
            <SquareCheck :size="15" />
          </button>
        </div>

        <div v-if="trashBatchMode" class="batch-toolbar">
          <button class="batch-action-btn" @click="selectAllTrash">全选</button>
          <span class="batch-count">已选 {{ trashSelectedIds.size }} 项</span>
          <button
            :class="['batch-restore-btn', { disabled: trashSelectedIds.size === 0 }]"
            :disabled="trashSelectedIds.size === 0"
            @click="handleBatchRestore"
          >
            <Undo2 :size="13" />
            恢复
          </button>
          <button
            :class="['batch-delete-btn', { disabled: trashSelectedIds.size === 0 }]"
            :disabled="trashSelectedIds.size === 0"
            @click="handleBatchPermanentDelete"
          >
            <Trash2 :size="13" />
            删除
          </button>
        </div>

        <div class="trash-toolbar" v-if="!trashBatchMode && chatStore.trashItems.length > 0">
          <button class="empty-trash-btn" @click="handleEmptyTrash">
            <Trash2 :size="12" />
            清空回收站
          </button>
        </div>

        <div class="trash-list">
          <div v-if="chatStore.trashItems.length === 0" class="history-empty">
            <Trash2 :size="24" />
            <span>回收站为空</span>
          </div>
          <div
            v-for="item in chatStore.trashItems"
            :key="item.id"
            :class="['trash-item']"
            @click="trashBatchMode ? toggleTrashSelect(item.id) : undefined"
          >
            <div v-if="trashBatchMode" class="history-item-checkbox" @click.stop="toggleTrashSelect(item.id)">
              <div :class="['checkbox-box', { checked: trashSelectedIds.has(item.id) }]">
                <Check v-if="trashSelectedIds.has(item.id)" :size="10" />
              </div>
            </div>
            <MessageSquare :size="14" class="history-item-icon" />
            <div class="trash-item-content">
              <span class="history-item-title">{{ item.title }}</span>
              <span class="trash-item-deleted-time">{{ formatDeleteTime(item.deleted_at) }}</span>
            </div>
            <div v-if="!trashBatchMode" class="trash-item-actions">
              <button class="trash-action-btn restore" title="恢复" @click.stop="handleRestoreItem(item.id)">
                <Undo2 :size="13" />
              </button>
              <button class="trash-action-btn delete" title="永久删除" @click.stop="handlePermanentDeleteItem(item.id)">
                <Trash2 :size="13" />
              </button>
            </div>
          </div>
        </div>
      </template>
    </div>

    <Transition name="selection-fade">
      <div v-if="showCreateDialog" class="create-dialog-overlay" @click.self="showCreateDialog = false">
        <div class="create-dialog">
          <h3>创建自定义 Agent</h3>
          <div class="form-group">
            <label class="form-label">
              名称
              <span class="required-mark">*</span>
            </label>
            <input v-model="newAgentForm.name" type="text" class="form-input" placeholder="如: 小助手" />
          </div>
          <div class="form-group">
            <label class="form-label">描述</label>
            <input v-model="newAgentForm.description" type="text" class="form-input" placeholder="如: 通用对话助手" />
          </div>
          <div class="form-group">
            <label class="form-label">系统提示词</label>
            <textarea
              v-model="newAgentForm.systemPrompt"
              class="form-input form-textarea"
              placeholder="定义 Agent 的角色和行为..."
              rows="4"
            ></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">颜色</label>
            <div class="color-picker">
              <button
                v-for="color in agentColors"
                :key="color"
                :class="['color-dot', { active: newAgentForm.color === color }]"
                :style="{ background: color }"
                @click="newAgentForm.color = color"
              ></button>
            </div>
          </div>
          <div class="dialog-actions">
            <button class="dialog-btn cancel" @click="showCreateDialog = false">取消</button>
            <button
              :class="['dialog-btn confirm', { disabled: !newAgentForm.name.trim() }]"
              :disabled="!newAgentForm.name.trim()"
              @click="handleCreateAgent"
            >
              <Check :size="16" />
              创建
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <Transition name="selection-fade">
      <div v-if="showTrashConfirm" class="create-dialog-overlay" @click.self="showTrashConfirm = false">
        <div class="confirm-dialog">
          <div class="confirm-dialog-icon">
            <AlertTriangle :size="24" />
          </div>
          <p class="confirm-dialog-message">{{ trashConfirmMessage }}</p>
          <div class="confirm-dialog-actions">
            <button class="dialog-btn danger" @click="handleTrashConfirm">删除</button>
            <button class="dialog-btn cancel" @click="showTrashConfirm = false">取消</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.lumi-sidebar {
  display: flex;
  height: 100%;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-normal);
}

.sidebar-icon-rail {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  width: 60px;
  height: 100%;
  padding: 12px 0;
  flex-shrink: 0;
  position: relative;
  background: var(--surface);
}

.sidebar-icon-rail::after {
  content: '';
  position: absolute;
  top: 12px;
  bottom: 12px;
  right: 0;
  width: 1px;
  background: var(--divider-vertical);
}

.rail-top {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.rail-bottom {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.avatar-btn {
  width: 40px;
  height: 40px;
  padding: 0;
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: transform var(--transition-fast);
}

.avatar-btn:hover {
  transform: scale(1.05);
}

.avatar-ring {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--lumi-primary), var(--lumi-primary-soft));
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(20, 126, 188, 0.3);
}

.icon-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 8px;
  width: 100%;
  padding: 0 8px;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
}

.icon-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.icon-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.icon-btn.active::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  border-radius: 2px;
  background: var(--lumi-primary);
}

.sidebar-history-panel {
  width: 220px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f9fafb;
  overflow: hidden;
  flex-shrink: 0;
}

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
  background: #ffffff;
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
  flex: 1;
  background: transparent;
  font-size: 13px;
  color: var(--text-secondary);
}

.search-input::placeholder {
  color: var(--text-muted);
}

.new-conv-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 7px 0;
  background: var(--lumi-primary);
  color: white;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.new-conv-btn:hover {
  background: var(--lumi-primary-hover);
}

.batch-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  color: var(--text-muted);
  background: #ffffff;
  border: 1px solid var(--workspace-border, #e5e7eb);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.batch-toggle-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.batch-toggle-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  border-color: var(--lumi-primary);
}

.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: #f0f4f8;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
  flex-wrap: nowrap;
  overflow: hidden;
}

.batch-action-btn {
  padding: 3px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: var(--text-secondary);
  background: #ffffff;
  border: 1px solid #e2e8f0;
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
  flex-shrink: 0;
}

.batch-action-btn:hover {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  border-color: var(--lumi-primary);
}

.batch-count {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: auto;
  white-space: nowrap;
  flex-shrink: 0;
}

.batch-delete-btn {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 3px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: #ef4444;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
  flex-shrink: 0;
}

.batch-delete-btn:hover {
  background: rgba(239, 68, 68, 0.15);
}

.batch-delete-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.batch-restore-btn {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 3px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  border: 1px solid rgba(20, 126, 188, 0.2);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
  flex-shrink: 0;
}

.batch-restore-btn:hover {
  background: rgba(20, 126, 188, 0.15);
}

.batch-restore-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px;
}

.time-group {
  margin-bottom: 8px;
}

.time-group-label {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 8px 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
}

.history-item:hover {
  background: #f3f4f6;
}

.history-item.active {
  background: #eff6ff;
}

.history-item-indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 2px;
  height: 0;
  border-radius: 1px;
  background: var(--lumi-primary);
  transition: height var(--transition-fast);
}

.history-item.active .history-item-indicator {
  height: 20px;
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
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-item.active .history-item-title {
  color: var(--lumi-primary);
  font-weight: 600;
}

.history-item-time {
  font-size: 10px;
  color: var(--text-muted);
}

.history-item-snippet {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.history-item-snippet :deep(mark) {
  background: rgba(20, 126, 188, 0.2);
  color: var(--lumi-primary);
  border-radius: 2px;
  padding: 0 1px;
}

.history-item-delete {
  display: none;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border-radius: 4px;
  color: var(--text-muted);
  flex-shrink: 0;
  transition: all var(--transition-fast);
}

.history-item:hover .history-item-delete {
  display: flex;
}

.history-item-delete:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.history-item-checkbox {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.checkbox-box {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1.5px solid #d1d5db;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
  background: #ffffff;
}

.checkbox-box.checked {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
  color: white;
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 0;
  color: var(--text-muted);
  font-size: 13px;
}

.trash-entry-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  margin: 0 10px 10px;
  border-radius: var(--radius-md);
  background: #ffffff;
  border: 1px solid #e5e7eb;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.trash-entry-btn:hover {
  background: #f3f4f6;
  color: var(--text-secondary);
  border-color: #d1d5db;
}

.trash-badge {
  margin-left: auto;
  min-width: 18px;
  height: 18px;
  border-radius: 9px;
  background: var(--lumi-accent, #ef4444);
  color: white;
  font-size: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 5px;
}

.trash-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.trash-back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.trash-back-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.trash-title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.trash-toolbar {
  display: flex;
  justify-content: flex-end;
  padding: 6px 14px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.empty-trash-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  color: #ef4444;
  background: rgba(239, 68, 68, 0.06);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.empty-trash-btn:hover {
  background: rgba(239, 68, 68, 0.12);
}

.trash-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px 10px;
}

.trash-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  cursor: default;
  transition: all var(--transition-fast);
}

.trash-item:hover {
  background: #f3f4f6;
}

.trash-item-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.trash-item-deleted-time {
  font-size: 10px;
  color: var(--text-muted);
}

.trash-item-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.trash-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 4px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.trash-action-btn.restore {
  color: var(--lumi-primary);
}

.trash-action-btn.restore:hover {
  background: var(--lumi-primary-light);
}

.trash-action-btn.delete {
  color: var(--text-muted);
}

.trash-action-btn.delete:hover {
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.create-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.create-dialog {
  background: var(--workspace-card);
  border-radius: var(--radius-xl);
  padding: 28px;
  width: 400px;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.create-dialog h3 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 20px;
}

.confirm-dialog {
  background: var(--workspace-card);
  border-radius: var(--radius-xl);
  padding: 32px 28px 24px;
  width: 340px;
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.confirm-dialog-icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  margin-bottom: 16px;
}

.confirm-dialog-message {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  margin: 0 0 24px;
}

.confirm-dialog-actions {
  display: flex;
  gap: 12px;
  width: 100%;
}

.confirm-dialog-actions .dialog-btn {
  flex: 1;
  justify-content: center;
  padding: 10px 20px;
  border-radius: var(--radius-lg);
  font-size: 14px;
  font-weight: 500;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 2px;
}

.required-mark {
  color: var(--lumi-accent);
  font-weight: 700;
  margin-left: 2px;
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-primary);
  transition: all var(--transition-fast);
}

.form-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.form-input::placeholder {
  color: var(--text-muted);
}

.form-textarea {
  resize: vertical;
  min-height: 80px;
}

.color-picker {
  display: flex;
  gap: 8px;
}

.color-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  transition: all var(--transition-fast);
  border: 2px solid transparent;
}

.color-dot:hover {
  transform: scale(1.15);
}

.color-dot.active {
  border-color: var(--text-primary);
  box-shadow: 0 0 0 2px white, 0 0 0 4px currentColor;
}

.dialog-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 20px;
}

.dialog-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.dialog-btn.cancel {
  color: var(--text-muted);
  background: var(--workspace-panel);
}

.dialog-btn.cancel:hover {
  background: var(--workspace-hover);
}

.dialog-btn.confirm {
  color: white;
  background: var(--lumi-primary);
}

.dialog-btn.confirm:hover {
  background: var(--lumi-primary-hover);
}

.dialog-btn.confirm.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.dialog-btn.danger {
  color: white;
  background: #ef4444;
}

.dialog-btn.danger:hover {
  background: #dc2626;
}

.selection-fade-enter-active {
  animation: lumi-fade-in 0.3s ease-out;
}

.selection-fade-leave-active {
  animation: lumi-fade-in 0.2s ease-out reverse;
}

.spin-animation {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
