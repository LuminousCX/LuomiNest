<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Brain,
  Search,
  Bot,
  MessageSquare,
  BookOpen,
  Sparkles,
  Activity,
  RefreshCw,
  Archive,
  Trash2,
  Edit3,
  Plus,
  Loader2,
  X,
  Save,
  Globe,
  Lock,
  Flame,
  Tag,
} from 'lucide-vue-next'
import { useMemoryStore } from '../stores/memory'
import { useAgentStore } from '../stores/agent'

const router = useRouter()
const memoryStore = useMemoryStore()
const agentStore = useAgentStore()

interface LayerTab {
  id: string
  name: string
  sub: string
  icon: typeof Brain
  color: string
  desc: string
}

interface SearchMemoryResult {
  id: string
  content: string
  category: string
  tier: string
  layer: string
  confidence: number
}

const layerTabs = ref<LayerTab[]>([
  { id: 'user-space', name: '用户空间', sub: 'UserSpace', icon: Globe, color: '#8b5cf6', desc: '全局共享 · 所有Agent可见' },
  { id: 'agent-memory', name: 'Agent记忆', sub: 'AgentMemory', icon: Bot, color: '#0ea5e9', desc: 'Agent私有 · 仅当前Agent可见' },
  { id: 'thread-memory', name: '对话记忆', sub: 'ThreadMemory', icon: MessageSquare, color: '#f59e0b', desc: '当前对话上下文 · 短期' },
])

const activeTab = ref('user-space')

const searchQuery = ref('')
const isSearching = ref(false)
const showSearchResults = ref(false)
const searchMemoryResults = ref<SearchMemoryResult[]>([])

const showAddDialog = ref(false)
const newFactContent = ref('')
const newFactCategory = ref('context')
const newFactLayer = ref('user')
const isAdding = ref(false)

const editingFactId = ref<string | null>(null)
const editingContent = ref('')

const categoryOptions = [
  { value: 'preference', label: '偏好' },
  { value: 'knowledge', label: '知识' },
  { value: 'context', label: '上下文' },
  { value: 'behavior', label: '行为' },
  { value: 'goal', label: '目标' },
  { value: 'correction', label: '纠正' },
]

const tierOptions = [
  { value: 'core_identity', label: '核心身份', color: '#8b5cf6' },
  { value: 'long_term_preference', label: '长期偏好', color: '#22c55e' },
  { value: 'temporary_context', label: '临时上下文', color: '#f59e0b' },
]

function getCategoryLabel(cat: string) {
  return categoryOptions.find(c => c.value === cat)?.label || cat
}

function getTierLabel(tier: string) {
  return tierOptions.find(t => t.value === tier)?.label || tier
}

function getTierColor(tier: string) {
  return tierOptions.find(t => t.value === tier)?.color || '#888'
}

function formatTimeAgo(isoStr: string) {
  if (!isoStr) return '未知'
  try {
    const d = new Date(isoStr)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)
    if (diffMins < 1) return '刚刚'
    if (diffMins < 60) return `${diffMins}分钟前`
    if (diffHours < 24) return `${diffHours}小时前`
    if (diffDays < 30) return `${diffDays}天前`
    return '长期'
  } catch {
    return '未知'
  }
}

const userSpaceFacts = computed(() => {
  const facts = memoryStore.memoryData?.user_space?.facts || []
  return facts
})

const userSpaceFactsByTier = computed(() => {
  const groups: Record<string, typeof userSpaceFacts.value> = {}
  for (const fact of userSpaceFacts.value) {
    if (!groups[fact.tier]) groups[fact.tier] = []
    groups[fact.tier].push(fact)
  }
  return groups
})

const agentFacts = computed(() => {
  return memoryStore.memoryData?.agent_memory?.agent_facts || []
})

const agentEvents = computed(() => {
  return memoryStore.memoryData?.agent_memory?.agent_events || []
})

const episodicEvents = computed(() => {
  return memoryStore.memoryData?.user_space?.episodic_events || []
})

const distilled = computed(() => {
  return memoryStore.memoryData?.user_space?.distilled || null
})

const hasDistilled = computed(() => {
  const d = distilled.value
  return d && (d.core_identity || d.long_term || d.temporary || d.events_timeline)
})

const workingMemory = computed(() => {
  return memoryStore.memoryData?.agent_memory?.working_memory || null
})

const profile = computed(() => {
  return memoryStore.memoryData?.user_space?.profile || null
})

const hasProfile = computed(() => {
  const p = profile.value
  if (!p) return false
  return !!(p.name || p.nickname || p.occupation || p.location || (p.interests && p.interests.length > 0) || (p.hobbies && p.hobbies.length > 0))
})

const userContext = computed(() => {
  return memoryStore.memoryData?.user_space?.user || null
})

const domainSummary = computed(() => {
  return memoryStore.memoryData?.agent_memory?.domain_summary || ''
})

const totalUserFacts = computed(() => userSpaceFacts.value.length)
const totalAgentFacts = computed(() => agentFacts.value.length)
const totalEvents = computed(() => episodicEvents.value.length + agentEvents.value.length)

function switchTab(tabId: string) {
  activeTab.value = tabId
}

async function handleSearch() {
  if (!searchQuery.value.trim()) return
  isSearching.value = true
  showSearchResults.value = true
  try {
    searchMemoryResults.value = await memoryStore.searchMemory(searchQuery.value, 10)
  } catch {
    searchMemoryResults.value = []
  } finally {
    isSearching.value = false
  }
}

function clearSearch() {
  searchQuery.value = ''
  showSearchResults.value = false
  searchMemoryResults.value = []
}

function chatAboutMemory(text: string) {
  const event = new CustomEvent('luominest:memory-chat-trigger', { detail: { text } })
  window.dispatchEvent(event)
  router.push('/workspace')
}

async function handleAddFact() {
  if (!newFactContent.value.trim()) return
  isAdding.value = true
  try {
    await memoryStore.addFact(
      newFactContent.value.trim(),
      newFactCategory.value,
      0.8,
      agentStore.activeAgent?.id,
      'manual',
      newFactLayer.value,
    )
    newFactContent.value = ''
    newFactCategory.value = 'context'
    showAddDialog.value = false
  } finally {
    isAdding.value = false
  }
}

function startEdit(factId: string, content: string) {
  editingFactId.value = factId
  editingContent.value = content
}

function cancelEdit() {
  editingFactId.value = null
  editingContent.value = ''
}

async function saveEdit() {
  if (!editingFactId.value || !editingContent.value.trim()) return
  try {
    await memoryStore.updateFact(editingFactId.value, editingContent.value.trim(), undefined, undefined, agentStore.activeAgent?.id)
    editingFactId.value = null
    editingContent.value = ''
  } catch (e) {
    console.error('[MemoryView] 保存失败:', e)
  }
}

async function handleDeleteFact(factId: string) {
  try {
    await memoryStore.deleteFact(factId, agentStore.activeAgent?.id)
  } catch (e) {
    console.error('[MemoryView] 删除失败:', e)
  }
}

async function loadData() {
  const agentId = agentStore.activeAgent?.id
  await Promise.all([
    memoryStore.fetchMemory(agentId),
    memoryStore.fetchSummary(agentId),
  ])
}

onMounted(() => { loadData() })
watch(() => agentStore.activeAgent?.id, () => { loadData() })
</script>

<template>
  <div class="memory-view">
    <div class="memory-header">
      <div class="header-left">
        <Brain :size="20" />
        <h2>记忆中枢</h2>
        <span class="header-badge">v3 · 三层记忆架构</span>
      </div>
      <div class="header-actions">
        <div class="search-bar" :class="{ 'search-expanded': showSearchResults }">
          <Search :size="14" class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索记忆..." @keydown.enter="handleSearch" />
          <button v-if="showSearchResults" class="search-clear-btn" @click="clearSearch"><X :size="12" /></button>
          <Loader2 v-if="isSearching" :size="13" class="spinning" />
          <button v-else class="search-trigger-btn" @click="handleSearch" :disabled="!searchQuery.trim()"><Search :size="13" /></button>
        </div>
        <button class="h-btn primary" @click="showAddDialog = true">
          <Plus :size="15" /> 添加记忆
        </button>
        <button class="h-btn" @click="loadData">
          <RefreshCw :size="15" :class="{ spinning: memoryStore.loading }" />
        </button>
      </div>
    </div>

    <div v-if="memoryStore.loading && !memoryStore.memoryData" class="memory-loading">
      <Loader2 :size="24" class="spinning" />
      <span>加载记忆数据...</span>
    </div>

    <div v-else class="memory-body">
      <div class="layer-nav animate-fade-up">
        <div
          v-for="tab in layerTabs"
          :key="tab.id"
          :class="['nav-card', { active: activeTab === tab.id }]"
          :style="{ '--tab-color': tab.color, '--tab-delay': `${layerTabs.indexOf(tab) * 0.1}s` }"
          @click="switchTab(tab.id)"
        >
          <div class="nav-top">
            <div class="nav-icon-wrap" :style="{ background: tab.color + '18' }">
              <component :is="tab.icon" :size="20" :style="{ color: tab.color }" />
            </div>
            <div class="nav-meta">
              <span class="nav-name">{{ tab.name }}</span>
              <span class="nav-sub">{{ tab.sub }}</span>
            </div>
          </div>
          <p class="nav-desc">{{ tab.desc }}</p>
          <div class="nav-stats">
            <span v-if="tab.id === 'user-space'" class="nav-stat">{{ totalUserFacts }} 条事实 · {{ totalEvents }} 条事件</span>
            <span v-else-if="tab.id === 'agent-memory'" class="nav-stat">{{ totalAgentFacts }} 条事实</span>
            <span v-else class="nav-stat">{{ workingMemory?.recent_conversations?.length || 0 }} 条对话</span>
          </div>
        </div>

        <div class="nav-flow">
          <div class="flow-step"><Globe :size="12" /> 全局</div>
          <div class="flow-arrow-line"></div>
          <div class="flow-step"><Lock :size="12" /> 私有</div>
          <div class="flow-arrow-line"></div>
          <div class="flow-step"><MessageSquare :size="12" /> 临时</div>
        </div>
      </div>

      <div class="memory-detail animate-slide-left">
        <div v-if="showSearchResults && searchMemoryResults.length > 0" class="search-results-section">
          <div class="section-title">搜索结果 · {{ searchMemoryResults.length }}条</div>
          <div class="memo-items">
            <div v-for="(result, idx) in searchMemoryResults" :key="`search-${idx}`" class="memo-item" :style="{ '--item-delay': `${idx * 0.05}s` }">
              <div class="memo-dot" :style="{ background: getTierColor(result.tier) }"></div>
              <div class="memo-content">
                <p class="memo-text">{{ result.content }}</p>
                <div class="memo-footer">
                  <span class="memo-tag" :style="{ background: getTierColor(result.tier) + '18', color: getTierColor(result.tier) }">{{ getTierLabel(result.tier) }}</span>
                  <span class="memo-tag layer-tag">{{ result.layer === 'user' ? '全局' : '私有' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <template v-if="activeTab === 'user-space'">
          <div class="detail-header">
            <Globe :size="22" :style="{ color: '#8b5cf6' }" />
            <h3>用户空间</h3>
            <span class="detail-sub">UserSpace · 所有Agent共享</span>
          </div>

          <div v-if="hasProfile" class="profile-card">
            <div class="profile-top">
              <div class="profile-avatar">{{ profile?.name?.[0] || '?' }}</div>
              <div class="profile-info">
                <span class="profile-name">{{ profile?.name || '未知用户' }}</span>
                <span v-if="profile?.occupation" class="profile-occ">{{ profile.occupation }}</span>
              </div>
            </div>
            <div class="profile-tags">
              <span v-if="profile?.location" class="p-tag"><Tag :size="10" /> {{ profile.location }}</span>
              <span v-if="profile?.gender" class="p-tag"><Tag :size="10" /> {{ profile.gender }}</span>
              <span v-if="profile?.age" class="p-tag"><Tag :size="10" /> {{ profile.age }}</span>
            </div>
            <div v-if="profile?.interests?.length || profile?.hobbies?.length" class="profile-interests">
              <BookOpen :size="12" />
              <span v-for="i in [...(profile?.interests || []), ...(profile?.hobbies || [])]" :key="i" class="i-tag">{{ i }}</span>
            </div>
          </div>

          <div v-if="userContext && (userContext.work_context?.summary || userContext.personal_context?.summary || userContext.top_of_mind?.summary)" class="context-card">
            <div class="context-title"><Activity :size="14" /> 当前上下文</div>
            <div v-if="userContext.work_context?.summary" class="context-row">
              <span class="context-label">工作</span>
              <span class="context-value">{{ userContext.work_context.summary }}</span>
            </div>
            <div v-if="userContext.personal_context?.summary" class="context-row">
              <span class="context-label">个人</span>
              <span class="context-value">{{ userContext.personal_context.summary }}</span>
            </div>
            <div v-if="userContext.top_of_mind?.summary" class="context-row">
              <span class="context-label">关注</span>
              <span class="context-value">{{ userContext.top_of_mind.summary }}</span>
            </div>
          </div>

          <div v-if="hasDistilled" class="distilled-card">
            <div class="distilled-title"><Sparkles :size="14" /> 蒸馏摘要</div>
            <div v-if="distilled?.core_identity" class="distilled-section">
              <span class="distilled-label" :style="{ color: '#8b5cf6' }">核心身份</span>
              <p class="distilled-text">{{ distilled.core_identity }}</p>
            </div>
            <div v-if="distilled?.long_term" class="distilled-section">
              <span class="distilled-label" :style="{ color: '#22c55e' }">长期偏好</span>
              <p class="distilled-text">{{ distilled.long_term }}</p>
            </div>
            <div v-if="distilled?.temporary" class="distilled-section">
              <span class="distilled-label" :style="{ color: '#f59e0b' }">临时上下文</span>
              <p class="distilled-text">{{ distilled.temporary }}</p>
            </div>
            <div v-if="distilled?.events_timeline" class="distilled-section">
              <span class="distilled-label" :style="{ color: '#0ea5e9' }">事件时间线</span>
              <p class="distilled-text">{{ distilled.events_timeline }}</p>
            </div>
          </div>

          <div class="facts-section">
            <div class="section-title">事实记忆 · {{ totalUserFacts }}条</div>
            <div v-if="totalUserFacts === 0" class="empty-section">
              <Archive :size="28" />
              <p>暂无事实记忆</p>
              <p class="empty-hint">对话后AI会自动提取并存储</p>
            </div>
            <template v-else>
              <div v-for="tier in tierOptions" :key="tier.value">
                <div v-if="userSpaceFactsByTier[tier.value]?.length" class="tier-group">
                  <div class="tier-header" :style="{ color: tier.color }">
                    <div class="tier-dot" :style="{ background: tier.color }"></div>
                    {{ tier.label }} · {{ userSpaceFactsByTier[tier.value].length }}条
                  </div>
                  <div class="memo-items">
                    <div v-for="(fact, idx) in userSpaceFactsByTier[tier.value]" :key="fact.id" class="memo-item" :style="{ '--item-delay': `${idx * 0.04}s` }">
                      <div class="memo-dot" :style="{ background: tier.color }"></div>
                      <div class="memo-content">
                        <template v-if="editingFactId === fact.id">
                          <textarea v-model="editingContent" class="edit-textarea" rows="2"></textarea>
                          <div class="edit-actions">
                            <button class="edit-btn save" @click="saveEdit" :disabled="!editingContent.trim()"><Save :size="12" /> 保存</button>
                            <button class="edit-btn cancel" @click="cancelEdit"><X :size="12" /> 取消</button>
                          </div>
                        </template>
                        <template v-else>
                          <p class="memo-text">{{ fact.content }}</p>
                          <div class="memo-footer">
                            <span class="memo-tag" :style="{ background: tier.color + '18', color: tier.color }">{{ tier.label }}</span>
                            <span class="memo-tag category-tag">{{ getCategoryLabel(fact.category) }}</span>
                            <span class="memo-time">{{ formatTimeAgo(fact.created_at) }}</span>
                          </div>
                        </template>
                      </div>
                      <div v-if="editingFactId !== fact.id" class="memo-actions">
                        <button class="memo-action-btn" title="就此对话" @click="chatAboutMemory(fact.content)"><MessageSquare :size="13" /></button>
                        <button class="memo-action-btn" title="编辑" @click="startEdit(fact.id, fact.content)"><Edit3 :size="13" /></button>
                        <button class="memo-action-btn danger" title="删除" @click="handleDeleteFact(fact.id)"><Trash2 :size="13" /></button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <div v-if="episodicEvents.length > 0" class="events-section">
            <div class="section-title">情景事件 · {{ episodicEvents.length }}条</div>
            <div class="memo-items">
              <div v-for="(event, idx) in episodicEvents.slice(0, 15)" :key="event.id" class="memo-item event-item" :style="{ '--item-delay': `${idx * 0.04}s` }">
                <div class="memo-dot" :style="{ background: '#0ea5e9' }"></div>
                <div class="memo-content">
                  <p class="memo-text">{{ event.core_goal }}</p>
                  <div class="memo-footer">
                    <span v-if="event.key_information" class="memo-info">{{ event.key_information }}</span>
                    <span class="memo-time">{{ formatTimeAgo(event.timestamp) }}</span>
                    <span v-for="tag in (event.scene_tags || []).slice(0, 2)" :key="tag" class="memo-tag scene-tag">{{ tag }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <template v-if="activeTab === 'agent-memory'">
          <div class="detail-header">
            <Bot :size="22" :style="{ color: '#0ea5e9' }" />
            <h3>Agent记忆</h3>
            <span class="detail-sub">AgentMemory · {{ agentStore.activeAgent?.name || '未选择' }}</span>
          </div>

          <div v-if="domainSummary" class="distilled-card">
            <div class="distilled-title"><Sparkles :size="14" /> 领域经验摘要</div>
            <p class="distilled-text">{{ domainSummary }}</p>
          </div>

          <div class="facts-section">
            <div class="section-title">Agent专属事实 · {{ totalAgentFacts }}条</div>
            <div v-if="totalAgentFacts === 0" class="empty-section">
              <Archive :size="28" />
              <p>暂无Agent专属记忆</p>
              <p class="empty-hint">对话中提取的Agent特有知识会存放在这里</p>
            </div>
            <div v-else class="memo-items">
              <div v-for="(fact, idx) in agentFacts" :key="fact.id" class="memo-item" :style="{ '--item-delay': `${idx * 0.04}s` }">
                <div class="memo-dot" :style="{ background: '#0ea5e9' }"></div>
                <div class="memo-content">
                  <template v-if="editingFactId === fact.id">
                    <textarea v-model="editingContent" class="edit-textarea" rows="2"></textarea>
                    <div class="edit-actions">
                      <button class="edit-btn save" @click="saveEdit" :disabled="!editingContent.trim()"><Save :size="12" /> 保存</button>
                      <button class="edit-btn cancel" @click="cancelEdit"><X :size="12" /> 取消</button>
                    </div>
                  </template>
                  <template v-else>
                    <p class="memo-text">{{ fact.content }}</p>
                    <div class="memo-footer">
                      <span class="memo-tag" :style="{ background: '#0ea5e918', color: '#0ea5e9' }">{{ getTierLabel(fact.tier) }}</span>
                      <span class="memo-tag category-tag">{{ getCategoryLabel(fact.category) }}</span>
                      <span class="memo-time">{{ formatTimeAgo(fact.created_at) }}</span>
                    </div>
                  </template>
                </div>
                <div v-if="editingFactId !== fact.id" class="memo-actions">
                  <button class="memo-action-btn" title="就此对话" @click="chatAboutMemory(fact.content)"><MessageSquare :size="13" /></button>
                  <button class="memo-action-btn" title="编辑" @click="startEdit(fact.id, fact.content)"><Edit3 :size="13" /></button>
                  <button class="memo-action-btn danger" title="删除" @click="handleDeleteFact(fact.id)"><Trash2 :size="13" /></button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="agentEvents.length > 0" class="events-section">
            <div class="section-title">Agent情景事件 · {{ agentEvents.length }}条</div>
            <div class="memo-items">
              <div v-for="(event, idx) in agentEvents.slice(0, 10)" :key="event.id" class="memo-item event-item" :style="{ '--item-delay': `${idx * 0.04}s` }">
                <div class="memo-dot" :style="{ background: '#0ea5e9' }"></div>
                <div class="memo-content">
                  <p class="memo-text">{{ event.core_goal }}</p>
                  <div class="memo-footer">
                    <span v-if="event.key_information" class="memo-info">{{ event.key_information }}</span>
                    <span class="memo-time">{{ formatTimeAgo(event.timestamp) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <template v-if="activeTab === 'thread-memory'">
          <div class="detail-header">
            <MessageSquare :size="22" :style="{ color: '#f59e0b' }" />
            <h3>对话记忆</h3>
            <span class="detail-sub">ThreadMemory · 当前对话上下文</span>
          </div>

          <div v-if="workingMemory?.core_goal" class="context-card">
            <div class="context-title"><Flame :size="14" /> 核心目标</div>
            <p class="context-value">{{ workingMemory.core_goal }}</p>
          </div>

          <div v-if="workingMemory?.conversation_summary" class="context-card">
            <div class="context-title"><BookOpen :size="14" /> 对话摘要</div>
            <p class="context-value">{{ workingMemory.conversation_summary }}</p>
          </div>

          <div v-if="workingMemory?.current_state" class="context-card">
            <div class="context-title"><Activity :size="14" /> 当前状态</div>
            <p class="context-value">{{ workingMemory.current_state }}</p>
          </div>

          <div v-if="workingMemory?.recent_conversations?.length" class="facts-section">
            <div class="section-title">近期对话 · {{ workingMemory.recent_conversations.length }}条</div>
            <div class="memo-items">
              <div v-for="(msg, idx) in workingMemory.recent_conversations.slice(-10)" :key="`conv-${idx}`" class="memo-item" :style="{ '--item-delay': `${idx * 0.04}s` }">
                <div class="memo-dot" :style="{ background: msg.role === 'user' ? '#8b5cf6' : '#0ea5e9' }"></div>
                <div class="memo-content">
                  <p class="memo-text">{{ msg.role === 'user' ? '用户' : '助手' }}: {{ msg.content }}</p>
                  <div class="memo-footer">
                    <span class="memo-time">{{ formatTimeAgo(msg.timestamp) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="!workingMemory?.core_goal && !workingMemory?.recent_conversations?.length" class="empty-section">
            <Archive :size="28" />
            <p>暂无对话记忆</p>
            <p class="empty-hint">开始对话后，工作记忆会自动记录</p>
          </div>
        </template>
      </div>
    </div>

    <Transition name="dialog-fade">
      <div v-if="showAddDialog" class="dialog-overlay" @click.self="showAddDialog = false">
        <div class="dialog-card">
          <div class="dialog-header">
            <Plus :size="16" />
            <span>添加记忆</span>
            <button class="dialog-close-btn" @click="showAddDialog = false"><X :size="16" /></button>
          </div>
          <div class="dialog-body">
            <textarea v-model="newFactContent" placeholder="输入记忆内容..." rows="3" class="dialog-textarea"></textarea>
            <div class="dialog-row">
              <div class="dialog-field">
                <span class="field-label">分类</span>
                <select v-model="newFactCategory" class="field-select">
                  <option v-for="opt in categoryOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </div>
              <div class="dialog-field">
                <span class="field-label">层级</span>
                <select v-model="newFactLayer" class="field-select">
                  <option value="user">用户空间（全局共享）</option>
                  <option value="agent">Agent记忆（私有）</option>
                </select>
              </div>
            </div>
          </div>
          <div class="dialog-footer">
            <button class="dialog-btn cancel" @click="showAddDialog = false">取消</button>
            <button class="dialog-btn confirm" @click="handleAddFact" :disabled="isAdding || !newFactContent.trim()">
              <Loader2 v-if="isAdding" :size="14" class="spinning" />
              <Plus v-else :size="14" />
              添加
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.memory-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
}

.memory-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex: 1;
  color: var(--text-muted);
  font-size: 14px;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.memory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-muted);
}

.header-left h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
}

.header-badge {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 20px;
  background: var(--task-purple-soft);
  color: var(--task-purple);
  font-weight: 500;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  border-radius: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  transition: all 300ms ease-in-out;
}

.search-bar:focus-within,
.search-bar.search-expanded {
  border-color: var(--task-purple);
  box-shadow: 0 0 0 2px var(--task-purple-soft);
}

.search-icon { color: var(--text-muted); flex-shrink: 0; }

.search-bar input {
  width: 140px;
  font-size: 13px;
  background: transparent;
  color: var(--text);
}

.search-bar input::placeholder { color: var(--text-muted); }

.search-clear-btn,
.search-trigger-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms;
}

.search-clear-btn:hover,
.search-trigger-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.search-trigger-btn:disabled { opacity: 0.4; cursor: default; }

.h-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  white-space: nowrap;
}

.h-btn:hover { background: var(--surface-hover); color: var(--text); }

.h-btn.primary {
  color: var(--text);
  background: var(--task-purple-soft);
  border: 1px solid var(--task-purple-border);
}

.h-btn.primary:hover { background: var(--task-purple-soft); }

.memory-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.layer-nav {
  width: 300px;
  padding: 20px;
  border-right: 1px solid var(--border);
  overflow-y: auto;
  flex-shrink: 0;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.nav-card {
  padding: 16px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--bg);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  opacity: 0;
  animation: card-enter 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: var(--tab-delay);
}

@keyframes card-enter {
  from { opacity: 0; transform: translateX(-16px); }
  to { opacity: 1; transform: translateX(0); }
}

.nav-card:hover {
  border-color: var(--tab-color);
  box-shadow: 0 4px 20px color-mix(in srgb, var(--tab-color) 10%, transparent);
}

.nav-card.active {
  border-color: var(--tab-color);
  background: color-mix(in srgb, var(--tab-color) 4%, transparent);
}

.nav-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.nav-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.nav-meta { flex: 1; min-width: 0; }

.nav-name {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.nav-sub {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
}

.nav-desc {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.5;
  margin-bottom: 8px;
}

.nav-stats {
  font-size: 11px;
  color: var(--text-muted);
  font-family: monospace;
}

.nav-stat {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--surface);
}

.nav-flow {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--task-purple-soft);
  margin-top: 4px;
}

.flow-step {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: var(--text-muted);
  white-space: nowrap;
}

.flow-arrow-line {
  flex: 1;
  height: 1px;
  background: var(--border);
}

.memory-detail {
  flex: 1;
  min-height: 0;
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.detail-header h3 {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}

.detail-sub {
  font-size: 12px;
  color: var(--text-muted);
}

.profile-card {
  padding: 18px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--task-purple-soft), var(--lumi-sky-soft));
  border: 1px solid var(--border);
}

.profile-top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.profile-avatar {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: var(--lumi-accent-glow);
  color: var(--task-purple);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  flex-shrink: 0;
}

.profile-info { display: flex; flex-direction: column; }

.profile-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}

.profile-occ {
  font-size: 12px;
  color: var(--text-muted);
}

.profile-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.p-tag {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 8px;
  background: var(--task-purple-soft);
  color: var(--task-purple-light);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;
}

.profile-interests {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.profile-interests > svg { color: var(--text-muted); flex-shrink: 0; }

.i-tag {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 8px;
  background: var(--surface);
  color: var(--text-muted);
}

.context-card {
  padding: 16px;
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
}

.context-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 10px;
}

.context-title svg { color: var(--task-purple); }

.context-row {
  display: flex;
  gap: 10px;
  margin-bottom: 6px;
  font-size: 13px;
}

.context-label {
  color: var(--text-muted);
  flex-shrink: 0;
  min-width: 32px;
}

.context-value {
  color: var(--text);
  line-height: 1.5;
}

.distilled-card {
  padding: 16px;
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
}

.distilled-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 12px;
}

.distilled-title svg { color: var(--lumi-amber); }

.distilled-section {
  margin-bottom: 10px;
}

.distilled-label {
  font-size: 12px;
  font-weight: 600;
  display: block;
  margin-bottom: 4px;
}

.distilled-text {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.6;
  margin: 0;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text);
}

.empty-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--text-muted);
}

.empty-section svg { margin-bottom: 12px; opacity: 0.5; }
.empty-section p { font-size: 14px; margin-bottom: 4px; }
.empty-hint { font-size: 12px !important; opacity: 0.7; }

.tier-group {
  margin-bottom: 16px;
}

.tier-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
}

.tier-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.memo-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.memo-item {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--surface);
  border: 1px solid transparent;
  transition: all 300ms ease-in-out;
  opacity: 0;
  animation: memo-in 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: var(--item-delay);
}

@keyframes memo-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

.memo-item:hover { border-color: var(--border); }
.memo-item:hover .memo-actions { opacity: 1; }

.memo-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  margin-top: 7px;
  flex-shrink: 0;
}

.memo-content { flex: 1; min-width: 0; }

.memo-text {
  font-size: 13px;
  color: var(--text);
  line-height: 1.5;
  margin-bottom: 4px;
}

.memo-footer {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.memo-tag {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 8px;
  background: var(--task-purple-soft);
  color: var(--task-purple);
  font-weight: 500;
}

.memo-tag.category-tag {
  background: var(--lumi-amber-soft);
  color: var(--lumi-amber-dark);
}

.memo-tag.layer-tag {
  background: var(--lumi-sky-soft);
  color: var(--lumi-sky);
}

.memo-tag.scene-tag {
  background: var(--task-green-soft);
  color: var(--lumi-success-dark);
}

.memo-info {
  font-size: 11px;
  color: var(--text-muted);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.memo-time {
  font-size: 11px;
  color: var(--text-muted);
}

.memo-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  opacity: 0;
  transition: opacity 200ms;
  flex-shrink: 0;
}

.memo-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms;
}

.memo-action-btn:hover { background: var(--surface-hover); color: var(--lumi-primary); }
.memo-action-btn.danger:hover { background: var(--lumi-accent-light); color: var(--lumi-accent); }

.edit-textarea {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
  resize: vertical;
  font-family: inherit;
  outline: none;
}

.edit-textarea:focus { border-color: var(--task-purple); }

.edit-actions { display: flex; gap: 8px; margin-top: 8px; }

.edit-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 200ms;
}

.edit-btn.save { background: var(--task-purple-soft); color: var(--task-purple); }
.edit-btn.save:hover { background: var(--task-purple-border); }
.edit-btn.save:disabled { opacity: 0.5; cursor: default; }
.edit-btn.cancel { background: var(--surface-hover); color: var(--text-muted); }
.edit-btn.cancel:hover { color: var(--text); }

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: var(--overlay-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.dialog-card {
  width: 480px;
  max-width: 90vw;
  background: var(--bg);
  border-radius: 16px;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.dialog-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.dialog-close-btn {
  margin-left: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
}

.dialog-close-btn:hover { background: var(--surface-hover); }

.dialog-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dialog-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  resize: none;
  font-family: inherit;
  outline: none;
}

.dialog-textarea:focus { border-color: var(--task-purple); }
.dialog-textarea::placeholder { color: var(--text-muted); }

.dialog-row {
  display: flex;
  gap: 12px;
}

.dialog-field {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 12px;
  color: var(--text-muted);
}

.field-select {
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  outline: none;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 14px 20px;
  border-top: 1px solid var(--border);
}

.dialog-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 200ms;
}

.dialog-btn.cancel { background: var(--surface); color: var(--text-muted); }
.dialog-btn.cancel:hover { background: var(--surface-hover); color: var(--text); }

.dialog-btn.confirm {
  background: var(--task-purple-soft);
  color: var(--task-purple);
  border: 1px solid var(--task-purple-border);
}

.dialog-btn.confirm:hover { background: var(--task-purple-border); }
.dialog-btn.confirm:disabled { opacity: 0.5; cursor: default; }

.dialog-fade-enter-active { animation: fade-in 0.25s ease-out; }
.dialog-fade-enter-active .dialog-card { animation: scale-in 0.3s cubic-bezier(0.22, 1, 0.36, 1); }
.dialog-fade-leave-active { animation: fade-in 0.2s ease-out reverse; }

@keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
@keyframes scale-in { from { opacity: 0; transform: scale(0.92); } to { opacity: 1; transform: scale(1); } }

.animate-fade-up { animation: fade-up 0.5s cubic-bezier(0.22, 1, 0.36, 1) both; }
@keyframes fade-up { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }

.animate-slide-left { animation: slide-left 0.5s cubic-bezier(0.22, 1, 0.36, 1) both; }
@keyframes slide-left { from { opacity: 0; transform: translateX(24px); } to { opacity: 1; transform: translateX(0); } }
</style>
