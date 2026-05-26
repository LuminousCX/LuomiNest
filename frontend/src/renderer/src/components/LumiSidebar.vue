<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
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
  Plus
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

// 搜索防抖：输入后 300ms 触发搜索，带竞态检查
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

// 时间分组逻辑
interface TimeGroup {
  label: string
  items: ConversationListItem[]
}

const timeGroups = computed<TimeGroup[]>(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const weekAgo = new Date(today.getTime() - 7 * 86400000)

  const groups: TimeGroup[] = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '上周', items: [] },
    { label: '更早', items: [] }
  ]

  const convs = chatStore.conversations

  for (const conv of convs) {
    const updatedAt = new Date(conv.updated_at)
    if (updatedAt >= today) {
      groups[0].items.push(conv)
    } else if (updatedAt >= yesterday) {
      groups[1].items.push(conv)
    } else if (updatedAt >= weekAgo) {
      groups[2].items.push(conv)
    } else {
      groups[3].items.push(conv)
    }
  }

  return groups.filter(g => g.items.length > 0)
})

const formatTime = (dateStr: string) => {
  const d = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())

  if (target.getTime() === today.getTime()) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  if (target.getTime() === today.getTime() - 86400000) {
    return '昨天'
  }
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

const highlightSnippet = (snippet: string): string => {
  if (!snippet) return ''
  // 先转义 HTML 特殊字符，防止 XSS
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

// 保留创建 Agent 对话框
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

onMounted(async () => {
  await agentStore.fetchAgents()
})
</script>

<template>
  <div class="lumi-sidebar">
    <!-- 60px icon bar -->
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

    <!-- 220px 历史记录面板，只在聊天页面显示 -->
    <div v-if="route.path === '/workspace'" class="sidebar-history-panel">
      <!-- 搜索框 -->
      <div class="panel-header">
        <div class="search-box">
          <Search :size="15" class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索历史记录..." class="search-input" />
        </div>
        <button class="new-conv-btn" @click="handleNewConversation">
          <Plus :size="15" />
          <span>创建新对话</span>
        </button>
      </div>

      <!-- 历史记录列表 -->
      <div class="history-list">
        <!-- 搜索模式：显示搜索结果 -->
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

        <!-- 正常模式：时间分组列表 -->
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
                @click="selectConversation(conv.id)"
              >
                <div class="history-item-indicator" />
                <MessageSquare :size="14" class="history-item-icon" />
                <div class="history-item-content">
                  <span class="history-item-title">{{ conv.title }}</span>
                  <span class="history-item-time">{{ formatTime(conv.updated_at) }}</span>
                </div>
                <button class="history-item-delete" @click.stop="handleDeleteConversation(conv.id)">
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

    </div>

    <!-- 保留创建 Agent 对话框 -->
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

/* ===== 60px icon bar ===== */
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

/* ===== 220px 历史记录面板 ===== */
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
  margin-top: 8px;
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

/* 历史记录列表 */
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

/* 空状态 */
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

/* 创建 Agent 对话框 */
.create-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
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
