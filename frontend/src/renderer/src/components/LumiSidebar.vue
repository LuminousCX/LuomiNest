<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  MessageCircle,
  MessageSquare,
  Users,
  Globe,
  Wifi,
  Settings2,
  Cpu,
  Palette,
  BarChart3,
  Terminal,
  CheckSquare,
  CalendarDays,
  Home,
  GitBranch,
  Search,
  Settings,
  Trash2,
  Check,
  Clock,
  Loader2,
  Plus,
  Undo2,
  ArrowLeft,
  SquareCheck,
  AlertTriangle,
  ChevronRight,
  ChevronLeft,
  Bell,
  Sparkles,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  Brain,
} from 'lucide-vue-next'
import { useAgentStore } from '../stores/agent'
import { useChatStore } from '../stores/chat'
import LumiBrandStar from './common/LumiBrandStar.vue'
import type { ConversationListItem, ConversationSearchResult } from '../types'

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()
const chatStore = useChatStore()

const expandedGroups = ref<Set<string>>(new Set(['chat']))
const isNavCollapsed = ref(true)
const isHistoryCollapsed = ref(false)

interface NavChild {
  id: string
  label: string
  icon: any
  badge?: string
}

interface NavGroup {
  id: string
  label: string
  icon: any
  children: NavChild[]
}

interface NavItem {
  id: string
  label: string
  icon: any
  route: string
  badge?: string
}

const navGroups: NavGroup[] = [
  {
    id: 'chat',
    label: '聊天',
    icon: MessageCircle,
    children: [
      { id: '/workspace', label: '对话', icon: MessageSquare },
      { id: '/social', label: '群组Agent', icon: Users },
      { id: '/chat/platform', label: '平台接入', icon: Globe },
      { id: '/chat/devices', label: '设备与群组', icon: Wifi },
    ],
  },
  {
    id: 'panel',
    label: '控制面板',
    icon: Settings2,
    children: [
      { id: '/settings/ai-model', label: '模型配置', icon: Cpu },
      { id: '/avatar', label: '皮套工坊', icon: Palette },
      { id: '/panel/data-stats', label: '数据统计', icon: BarChart3 },
      { id: '/memory', label: '记忆中枢', icon: Brain },
      { id: '/market', label: '扩展市场', icon: Package },
      { id: '/panel/console', label: '控制台', icon: Terminal },
    ],
  },
  {
    id: 'plan',
    label: '计划任务',
    icon: CheckSquare,
    children: [
      { id: '/tasks', label: '计划视图', icon: CalendarDays },
      { id: '/plan/smart-home', label: '智能家居', icon: Home },
      { id: '/workflow', label: '工作流', icon: GitBranch },
    ],
  },
]

const navItems: NavItem[] = [
  { id: 'browser', label: '浏览器', icon: Globe, route: '/browser' },
  { id: 'settings', label: '设置', icon: Settings, route: '/settings' },
]

const activeGroup = computed(() => {
  for (const group of navGroups) {
    for (const child of group.children) {
      if (route.path === child.id || route.path.startsWith(child.id + '/')) {
        return group.id
      }
    }
  }
  return null
})

const isItemActive = (item: NavItem) => {
  return route.path === item.route || route.path.startsWith(item.route + '/')
}

const isChildActive = (childId: string) => {
  return route.path === childId || route.path.startsWith(childId + '/')
}

const toggleGroup = (groupId: string) => {
  if (isNavCollapsed.value) {
    isNavCollapsed.value = false
    expandedGroups.value = new Set([groupId])
    return
  }
  const next = new Set(expandedGroups.value)
  if (next.has(groupId)) {
    next.delete(groupId)
  } else {
    next.add(groupId)
  }
  expandedGroups.value = next
}

watch(isNavCollapsed, (collapsed) => {
  if (collapsed) {
    expandedGroups.value = new Set()
  }
})

watch(activeGroup, (groupId) => {
  if (groupId && !expandedGroups.value.has(groupId)) {
    expandedGroups.value = new Set([...expandedGroups.value, groupId])
  }
}, { immediate: true })

const handleNavigate = (path: string) => {
  router.push(path)
}

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

const showHistoryPanel = computed(() => {
  return route.path === '/workspace'
})

onMounted(async () => {
  await agentStore.fetchAgents()
  if (agentStore.activeAgent?.id) {
    chatStore.fetchTrash(agentStore.activeAgent.id)
  }
})
</script>

<template>
  <div class="lumi-sidebar">
    <div :class="['sidebar-nav-panel', { collapsed: isNavCollapsed }]">
      <div class="nav-header">
        <div class="brand">
          <div class="brand-avatar">
            <LumiBrandStar :size="22" :animated="false" />
          </div>
          <div v-if="!isNavCollapsed" class="brand-info">
            <span class="brand-name">LuomiNest</span>
            <span class="brand-tag">LuminousCX</span>
          </div>
        </div>
        <div v-if="!isNavCollapsed" class="header-actions">
          <button class="header-action-btn" aria-label="消息公告">
            <Bell :size="16" />
            <span class="header-action-dot"></span>
          </button>
          <button class="header-action-btn" aria-label="新建" @click="showCreateDialog = true">
            <Plus :size="16" />
          </button>
        </div>
        <button class="collapse-toggle-btn" :aria-label="isNavCollapsed ? '展开侧栏' : '收起侧栏'" @click="isNavCollapsed = !isNavCollapsed">
          <PanelLeftOpen v-if="isNavCollapsed" :size="18" />
          <PanelLeftClose v-else :size="18" />
        </button>
      </div>

      <div v-if="!isNavCollapsed" class="nav-search">
        <Search :size="14" class="nav-search-icon" />
        <input
          type="text"
          placeholder="搜索..."
          class="nav-search-input"
          readonly
          @click="router.push('/workspace')"
        />
        <Sparkles :size="14" class="nav-search-sparkle" />
      </div>

      <div class="nav-content">
        <div class="nav-section">
          <div v-if="!isNavCollapsed" class="section-label">导航</div>

          <div v-for="group in navGroups" :key="group.id" class="nav-group">
            <button
              :class="['group-header', { active: activeGroup === group.id, expanded: expandedGroups.has(group.id) }]"
              @click="toggleGroup(group.id)"
            >
              <div class="group-header-left">
                <component :is="group.icon" :size="17" class="group-icon" />
                <span v-if="!isNavCollapsed" class="group-label">{{ group.label }}</span>
              </div>
              <ChevronRight
                v-if="!isNavCollapsed"
                :size="14"
                :class="['group-chevron', { rotated: expandedGroups.has(group.id) }]"
              />
            </button>

            <Transition name="tree-expand">
              <div v-if="!isNavCollapsed && expandedGroups.has(group.id)" class="group-children">
                <div
                  v-for="(child, idx) in group.children"
                  :key="child.id"
                  :class="['tree-child', { active: isChildActive(child.id), last: idx === group.children.length - 1 }]"
                  @click="handleNavigate(child.id)"
                >
                  <div class="tree-line">
                    <div class="tree-branch"></div>
                    <div class="tree-node"></div>
                  </div>
                  <component :is="child.icon" :size="14" class="child-icon" />
                  <span class="child-label">{{ child.label }}</span>
                </div>
              </div>
            </Transition>
          </div>
        </div>

        <div v-if="!isNavCollapsed" class="nav-section">
          <div class="section-label">工具</div>
          <div class="nav-items">
            <button
              v-for="item in navItems"
              :key="item.id"
              :class="['nav-item', { active: isItemActive(item) }]"
              @click="router.push(item.route)"
            >
              <component :is="item.icon" :size="17" class="nav-item-icon" />
              <span class="nav-item-label">{{ item.label }}</span>
              <span v-if="item.badge" class="nav-item-badge">{{ item.badge }}</span>
            </button>
          </div>
        </div>
      </div>

      <div class="nav-footer">
        <button class="footer-btn" @click="router.push('/settings')">
          <Settings :size="15" />
          <span v-if="!isNavCollapsed">设置</span>
        </button>
      </div>
    </div>

    <div class="history-panel-wrapper">
      <Transition name="history-slide">
        <div v-if="showHistoryPanel && !isHistoryCollapsed" class="sidebar-history-panel">
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
      </Transition>

    </div>

    <button
      v-if="showHistoryPanel && !isHistoryCollapsed"
      class="collapse-history-btn"
      title="收起历史记录"
      @click="isHistoryCollapsed = true"
    >
      <ChevronLeft :size="14" />
    </button>

    <button
      v-if="showHistoryPanel && isHistoryCollapsed"
      class="history-expand-toggle"
      title="展开历史记录"
      @click="isHistoryCollapsed = false"
    >
      <ChevronRight :size="14" />
    </button>

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
  position: relative;
  overflow: visible;
  z-index: 1;
}

.sidebar-nav-panel {
  width: 240px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  flex-shrink: 0;
  overflow: hidden;
  position: relative;
  transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar-nav-panel.collapsed {
  width: 52px;
}

.sidebar-nav-panel::after {
  content: '';
  position: absolute;
  top: 12px;
  bottom: 12px;
  right: 0;
  width: 1px;
  background: var(--divider-vertical);
}

.sidebar-nav-panel.collapsed::after {
  display: none;
}

.nav-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px;
  flex-shrink: 0;
}

.sidebar-nav-panel.collapsed .nav-header {
  flex-direction: column;
  gap: 8px;
  padding: 14px 8px 10px;
  align-items: center;
  justify-content: center;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--lumi-primary), var(--lumi-primary-soft));
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 3px 10px var(--lumi-primary-border);
  color: var(--text-inverse);
}

.brand-info {
  display: flex;
  flex-direction: column;
}

.brand-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.brand-tag {
  font-size: 10px;
  color: var(--text-muted);
  font-weight: 500;
  letter-spacing: 0.3px;
}

.header-actions {
  display: flex;
  gap: 4px;
}

.header-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-md);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
}

.header-action-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.header-action-dot {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--lumi-accent);
  border: 1.5px solid var(--surface);
}

.collapse-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-md);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.collapse-toggle-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.sidebar-nav-panel.collapsed .collapse-toggle-btn {
  width: 36px;
  height: 36px;
}

.nav-search {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 14px 10px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.nav-search:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.nav-search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.nav-search-input {
  flex: 1;
  background: transparent;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
}

.nav-search-input::placeholder {
  color: var(--text-muted);
}

.nav-search-sparkle {
  color: var(--lumi-warning);
  flex-shrink: 0;
  opacity: 0.6;
}

.nav-content {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sidebar-nav-panel.collapsed .nav-content {
  padding: 0 6px 10px;
  align-items: center;
}

.nav-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-label {
  padding: 4px 8px;
  font-size: 10px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.nav-group {
  display: flex;
  flex-direction: column;
}

.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 10px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  width: 100%;
  text-align: left;
  position: relative;
  overflow: hidden;
}

.sidebar-nav-panel.collapsed .group-header {
  justify-content: center;
  padding: 9px;
}

.group-header::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at center, var(--lumi-primary-glow) 0%, transparent 70%);
  opacity: 0;
  transform: scale(0.5);
  transition: all 0.4s ease-out;
  pointer-events: none;
}

.group-header:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.group-header:active::after {
  opacity: 1;
  transform: scale(2);
  transition: all 0.2s ease-out;
}

.group-header.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.group-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.group-icon {
  flex-shrink: 0;
}

.group-label {
  font-size: 13px;
  font-weight: 600;
}

.group-chevron {
  flex-shrink: 0;
  color: var(--text-muted);
  transition: transform var(--transition-fast);
}

.group-header.active .group-chevron {
  color: var(--lumi-primary);
}

.group-chevron.rotated {
  transform: rotate(90deg);
}

.group-children {
  display: flex;
  flex-direction: column;
  padding-left: 8px;
  overflow: hidden;
}

.tree-child {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px 7px 0;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
  margin-left: 14px;
  animation: nav-item-pop 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.tree-child:nth-child(1) { animation-delay: 0.02s; }
.tree-child:nth-child(2) { animation-delay: 0.04s; }
.tree-child:nth-child(3) { animation-delay: 0.06s; }
.tree-child:nth-child(4) { animation-delay: 0.08s; }
.tree-child:nth-child(5) { animation-delay: 0.10s; }
.tree-child:nth-child(6) { animation-delay: 0.12s; }

.tree-child:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
  transform: translateX(3px);
}

.tree-child.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.tree-line {
  position: absolute;
  left: -14px;
  top: 0;
  bottom: 0;
  width: 14px;
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
}

.tree-branch {
  position: absolute;
  left: 6px;
  top: 0;
  width: 1px;
  height: 100%;
  background: var(--border-light);
}

.tree-child.last .tree-branch {
  height: 50%;
}

.tree-node {
  position: absolute;
  left: 6px;
  top: 50%;
  width: 8px;
  height: 1px;
  background: var(--border-light);
  transform: translateY(-50%);
}

.tree-child.last .tree-node {
  border-bottom-left-radius: 2px;
}

.child-icon {
  flex-shrink: 0;
  margin-left: 4px;
}

.child-label {
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-items {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  width: 100%;
  text-align: left;
  position: relative;
  overflow: hidden;
}

.nav-item::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at center, var(--lumi-primary-glow) 0%, transparent 70%);
  opacity: 0;
  transform: scale(0.5);
  transition: all 0.4s ease-out;
  pointer-events: none;
}

.nav-item:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
  transform: translateX(2px);
}

.nav-item:active::after {
  opacity: 1;
  transform: scale(2);
  transition: all 0.2s ease-out;
}

.nav-item.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.nav-item-icon {
  flex-shrink: 0;
}

.nav-item-label {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
}

.nav-item-badge {
  padding: 1px 6px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 600;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.nav-footer {
  padding: 10px 14px;
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

.sidebar-nav-panel.collapsed .nav-footer {
  padding: 10px 6px;
}

.footer-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  width: 100%;
}

.sidebar-nav-panel.collapsed .footer-btn {
  justify-content: center;
  padding: 8px;
}

.footer-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.sidebar-history-panel {
  width: 220px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  overflow: hidden;
  flex-shrink: 0;
  position: relative;
}

.history-panel-wrapper {
  display: flex;
  height: 100%;
  align-items: stretch;
  position: relative;
}

.collapse-history-btn {
  width: 16px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0 6px 6px 0;
  color: var(--text-muted);
  cursor: pointer;
  background: var(--surface);
  border: none;
  border-left: 1px solid var(--divider-soft);
  transition: all var(--transition-fast);
  position: absolute;
  right: -16px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 20;
  padding: 0;
}

.collapse-history-btn:hover {
  color: var(--lumi-primary);
  background: var(--surface-hover);
}

.history-expand-toggle {
  width: 16px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0 6px 6px 0;
  color: var(--text-muted);
  cursor: pointer;
  background: var(--surface);
  border: none;
  border-left: 1px solid var(--divider-soft);
  transition: all var(--transition-fast);
  position: absolute;
  right: -16px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 20;
  padding: 0;
}

.history-expand-toggle:hover {
  color: var(--lumi-primary);
  background: var(--surface-hover);
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
  color: var(--text-inverse);
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
  background: var(--surface);
  border: 1px solid var(--workspace-border, var(--border));
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
  background: var(--surface);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
  flex-wrap: nowrap;
  overflow: hidden;
}

.batch-action-btn {
  padding: 3px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: var(--text-secondary);
  background: var(--surface);
  border: 1px solid var(--border-light);
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
  color: var(--lumi-accent);
  background: var(--lumi-accent-light);
  border: 1px solid var(--lumi-accent-border);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
  flex-shrink: 0;
}

.batch-delete-btn:hover {
  background: var(--lumi-accent-glow);
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
  border: 1px solid var(--lumi-primary-border);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
  flex-shrink: 0;
}

.batch-restore-btn:hover {
  background: var(--lumi-primary-glow);
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
  background: var(--surface-hover);
}

.history-item.active {
  background: var(--lumi-primary-light);
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
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.history-item-snippet :deep(mark) {
  background: var(--lumi-primary-border);
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
  border: 1.5px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
  background: var(--surface);
}

.checkbox-box.checked {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
  color: var(--text-inverse);
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
  background: var(--surface);
  border: 1px solid var(--border-light);
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.trash-entry-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
  border-color: var(--border);
}

.trash-badge {
  margin-left: auto;
  min-width: 18px;
  height: 18px;
  border-radius: 9px;
  background: var(--lumi-accent);
  color: var(--text-inverse);
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
  border-bottom: 1px solid var(--border-light);
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
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.empty-trash-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  color: var(--lumi-accent);
  background: var(--lumi-accent-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.empty-trash-btn:hover {
  background: var(--lumi-accent-glow);
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
  background: var(--surface-hover);
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
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.tree-expand-enter-active {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.tree-expand-leave-active {
  transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
}

.tree-expand-enter-from,
.tree-expand-leave-to {
  opacity: 0;
  max-height: 0;
  transform: translateY(-4px);
}

.tree-expand-enter-to,
.tree-expand-leave-from {
  opacity: 1;
  max-height: 300px;
  transform: translateY(0);
}

.history-slide-enter-active {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.history-slide-leave-active {
  transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
}

.history-slide-enter-from,
.history-slide-leave-to {
  opacity: 0;
  width: 0;
  min-width: 0;
  overflow: hidden;
}

.history-slide-enter-to,
.history-slide-leave-from {
  opacity: 1;
  width: 220px;
}

.selection-fade-enter-active {
  animation: lumi-fade-in 0.3s ease-out;
}

.selection-fade-leave-active {
  animation: lumi-fade-in 0.2s ease-out reverse;
}

@keyframes lumi-fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes nav-item-pop {
  from {
    opacity: 0;
    transform: translateX(-8px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
}

@keyframes nav-ripple {
  from {
    opacity: 0.6;
    transform: scale(0);
  }
  to {
    opacity: 0;
    transform: scale(2.5);
  }
}
</style>
