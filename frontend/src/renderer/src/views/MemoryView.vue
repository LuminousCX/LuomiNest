<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Brain,
  Database,
  Search,
  Layers,
  Clock,
  BookOpen,
  User,
  Cpu,
  ArrowRight,
  Activity,
  TrendingUp,
  RefreshCw,
  Zap,
  Archive,
  Trash2,
  Edit3,
  Plus,
  MessageSquare,
  Loader2,
  X,
  Save,
} from 'lucide-vue-next'
import { useMemoryStore } from '../stores/memory'
import { useAgentStore } from '../stores/agent'

const router = useRouter()
const memoryStore = useMemoryStore()
const agentStore = useAgentStore()

interface LayerItem {
  id: string
  text: string
  time: string
  tag: string
  category: string
  confidence: number
  raw: any
}

interface MemoryLayer {
  id: string
  name: string
  sub: string
  icon: typeof Brain
  color: string
  capacity: number
  unit: string
  desc: string
  items: LayerItem[]
}

const layers = ref<MemoryLayer[]>([
  { id: 'working', name: '工作记忆', sub: 'Working Memory', icon: Cpu, color: '#f59e0b', capacity: 100, unit: '条记录', desc: '当前会话上下文 · 内存/Redis', items: [] },
  { id: 'episodic', name: '情景记忆', sub: 'Episodic Memory', icon: Clock, color: '#22c55e', capacity: 50, unit: '条事件', desc: '近期事件回忆 · JSON + 向量检索', items: [] },
  { id: 'semantic', name: '语义记忆', sub: 'Semantic Memory', icon: Database, color: '#8b5cf6', capacity: 500, unit: '条事实', desc: '永久认知 · PGVector + 知识图谱', items: [] },
])

const activeLayerIdx = ref(0)
const activeLayerData = computed(() => layers.value[activeLayerIdx.value])
const activeUsedCount = computed(() => activeLayerData.value.items.length)

const searchQuery = ref('')
const isSearching = ref(false)
const showSearchResults = ref(false)
const searchMemoryResults = ref<Array<{ content: string; score: number; source: string }>>([])

const showAddDialog = ref(false)
const newFactContent = ref('')
const newFactCategory = ref('context')
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

function getCategoryLabel(cat: string) {
  return categoryOptions.find(c => c.value === cat)?.label || cat
}

function getTierLabel(tier: string) {
  const map: Record<string, string> = {
    core_identity: '核心身份',
    long_term_preference: '长期偏好',
    temporary_context: '临时上下文',
  }
  return map[tier] || tier
}

function getTierColor(tier: string) {
  const map: Record<string, string> = {
    core_identity: '#8b5cf6',
    long_term_preference: '#22c55e',
    temporary_context: '#f59e0b',
  }
  return map[tier] || '#888'
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

function factToLayerItem(fact: any): LayerItem {
  return {
    id: fact.id,
    text: fact.content,
    time: formatTimeAgo(fact.created_at),
    tag: getTierLabel(fact.tier),
    category: fact.category,
    confidence: fact.confidence,
    raw: fact,
  }
}

function eventToLayerItem(event: any): LayerItem {
  return {
    id: event.id,
    text: event.key_information || event.core_goal,
    time: formatTimeAgo(event.timestamp),
    tag: event.scene_tags?.[0] || '事件',
    category: 'context',
    confidence: event.importance || 0.5,
    raw: event,
  }
}

function buildLayers() {
  const data = memoryStore.memoryData
  if (!data) return

  const memory = data.memory

  layers.value[0].items = [
    ...memory.facts.filter(f => f.tier === 'temporary_context').map(factToLayerItem),
    ...memory.working_memory.recent_conversations.slice(-5).map((c: any) => ({
      id: `conv-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      text: `${c.role === 'user' ? '用户' : '助手'}: ${(c.content || '').slice(0, 60)}`,
      time: formatTimeAgo(c.timestamp),
      tag: '对话',
      category: 'context',
      confidence: 0.6,
      raw: c,
    })),
  ]

  if (memory.working_memory.core_goal) {
    layers.value[0].items.unshift({
      id: 'core-goal',
      text: memory.working_memory.core_goal,
      time: formatTimeAgo(memory.working_memory.core_goal_extracted_at),
      tag: '核心目标',
      category: 'goal',
      confidence: 1.0,
      raw: { content: memory.working_memory.core_goal },
    })
  }

  layers.value[1].items = memory.episodic_events.map(eventToLayerItem)

  const semanticItems: LayerItem[] = []
  for (const fact of memory.facts.filter(f => f.tier === 'core_identity' || f.tier === 'long_term_preference')) {
    semanticItems.push(factToLayerItem(fact))
  }
  layers.value[2].items = semanticItems

  for (const arch of memory.archived_facts) {
    layers.value[2].items.push({
      ...factToLayerItem(arch),
      tag: '已归档',
    })
  }
}

watch(() => memoryStore.memoryData, () => {
  if (memoryStore.memoryData) {
    buildLayers()
  }
}, { immediate: true })

const userPortrait = computed(() => {
  const profile = memoryStore.memoryData?.memory.profile
  if (!profile) return null

  const tags: string[] = []
  if (profile.occupation) tags.push(profile.occupation)
  if (profile.language) tags.push(profile.language)
  if (profile.gender) tags.push(profile.gender)
  if (profile.name) tags.push(profile.name)

  const interests = profile.interests || []
  const hobbies = profile.hobbies || []

  const totalFacts = memoryStore.memoryData?.summary.total_facts || 0
  const totalEvents = memoryStore.memoryData?.memory.episodic_events?.length || 0

  return {
    tags: tags.length > 0 ? tags : ['暂无标签'],
    interests: [...interests, ...hobbies],
    interactionCount: totalFacts,
    memoryHealth: Math.min(100, Math.round((totalFacts / Math.max(totalFacts + (memoryStore.memoryData?.summary.total_archived || 0), 1)) * 100)),
  }
})

const hasProfile = computed(() => {
  const p = memoryStore.memoryData?.memory.profile
  if (!p) return false
  return !!(p.name || p.nickname || p.occupation || p.location || (p.interests && p.interests.length > 0) || (p.hobbies && p.hobbies.length > 0))
})

function switchLayer(idx: number) {
  activeLayerIdx.value = idx
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

function chatAboutMemory(item: LayerItem) {
  const event = new CustomEvent('luominest:memory-chat-trigger', {
    detail: { text: item.text }
  })
  window.dispatchEvent(event)
  router.push('/workspace')
}

async function handleAddFact() {
  if (!newFactContent.value.trim()) return
  isAdding.value = true
  try {
    await memoryStore.addFact(newFactContent.value.trim(), newFactCategory.value, 0.8, agentStore.activeAgent?.id)
    newFactContent.value = ''
    newFactCategory.value = 'context'
    showAddDialog.value = false
  } finally {
    isAdding.value = false
  }
}

function startEdit(fact: LayerItem) {
  editingFactId.value = fact.id
  editingContent.value = fact.text
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
  } catch {
  }
}

async function handleDeleteFact(fact: LayerItem) {
  try {
    await memoryStore.deleteFact(fact.id, agentStore.activeAgent?.id)
  } catch {
  }
}

function getTierCapacity(tier: string) {
  switch (tier) {
    case 'working': return 100
    case 'episodic': return 50
    case 'semantic': return 500
    default: return 100
  }
}

async function loadData() {
  const agentId = agentStore.activeAgent?.id
  await Promise.all([
    memoryStore.fetchMemory(agentId),
    memoryStore.fetchSummary(agentId),
  ])
}

onMounted(() => {
  loadData()
})

watch(() => agentStore.activeAgent?.id, () => {
  loadData()
})
</script>

<template>
  <div class="memory-view">
    <div class="memory-header">
      <div class="header-left">
        <Brain :size="20" />
        <h2>记忆中枢</h2>
        <span class="header-badge">MaaS · 三层记忆架构</span>
      </div>
      <div class="header-actions">
        <div class="search-bar" :class="{ 'search-expanded': showSearchResults }">
          <Search :size="14" class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索记忆..."
            @keydown.enter="handleSearch" />
          <button v-if="showSearchResults" class="search-clear-btn" @click="clearSearch">
            <X :size="12" />
          </button>
          <Loader2 v-if="isSearching" :size="13" class="search-refresh spinning" />
          <button v-else class="search-trigger-btn" @click="handleSearch" :disabled="!searchQuery.trim()">
            <Search :size="13" />
          </button>
        </div>
        <button class="h-btn primary" @click="showAddDialog = true">
          <Plus :size="15" /> 添加事实
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
      <div class="layer-stack animate-fade-up">
        <div class="stack-visual">
          <div
            v-for="(layer, idx) in layers"
            :key="layer.id"
            :class="['layer-card', { active: activeLayerIdx === idx }]"
            :style="{ '--layer-color': layer.color, '--layer-delay': `${idx * 0.12}s` }"
            @click="switchLayer(idx)"
          >
            <div class="layer-top">
              <div class="layer-icon-wrap" :style="{ background: layer.color + '18' }">
                <component :is="layer.icon" :size="20" :style="{ color: layer.color }" />
              </div>
              <div class="layer-meta">
                <span class="layer-name">{{ layer.name }}</span>
                <span class="layer-sub">{{ layer.sub }}</span>
              </div>
              <Layers :size="14" class="layer-indicator" />
            </div>

            <div class="layer-bar-wrap">
              <div class="layer-bar-track">
                <div
                  class="layer-bar-fill"
                  :style="{
                    width: Math.min(100, (layer.items.length / Math.max(layer.capacity, 1)) * 100) + '%',
                    background: layer.color
                  }"
                ></div>
              </div>
              <span class="layer-bar-label">{{ layer.items.length }} / {{ layer.capacity }} {{ layer.unit }}</span>
            </div>

            <p class="layer-desc">{{ layer.desc }}</p>
          </div>

          <div class="flow-arrow">
            <ArrowRight :size="16" />
            <span>MemCell 提取 → 分类 → 压缩 → 检索</span>
          </div>
        </div>
      </div>

      <div class="memory-detail animate-slide-left">
        <div class="detail-header">
          <component :is="activeLayerData.icon" :size="22" :style="{ color: activeLayerData.color }" />
          <h3>{{ activeLayerData.name }}</h3>
          <span class="detail-sub">{{ activeLayerData.sub }}</span>
        </div>

        <div class="detail-capacity">
          <div class="cap-ring">
            <svg viewBox="0 0 100 100" class="cap-svg">
              <circle cx="50" cy="50" r="42" fill="none" stroke="var(--border)" stroke-width="8" />
              <circle cx="50" cy="50" r="42" fill="none"
                :stroke="activeLayerData.color" stroke-width="8" stroke-linecap="round"
                :stroke-dasharray="264"
                :stroke-dashoffset="264 - (264 * Math.min(1, activeUsedCount / Math.max(activeLayerData.capacity, 1)))"
                class="cap-progress" />
            </svg>
            <div class="cap-text">
              <span class="cap-value">{{ Math.round(Math.min(100, (activeUsedCount / Math.max(activeLayerData.capacity, 1)) * 100)) }}%</span>
              <span class="cap-unit">已用</span>
            </div>
          </div>
          <div class="cap-stats">
            <div class="stat-item">
              <Activity :size="14" />
              <span>{{ activeUsedCount }} 条记录</span>
            </div>
            <div class="stat-item">
              <TrendingUp :size="14" />
              <span>实时统计</span>
            </div>
            <div class="stat-item">
              <Zap :size="14" />
              <span>RAG 就绪</span>
            </div>
          </div>
        </div>

        <div v-if="showSearchResults && searchMemoryResults.length > 0" class="detail-list">
          <div class="list-title">搜索结果 · {{ searchMemoryResults.length }}条</div>
          <TransitionGroup name="memo-list" tag="div" class="memo-items">
            <div v-for="(result, idx) in searchMemoryResults" :key="`search-${idx}`" class="memo-item"
              :style="{ '--item-delay': `${idx * 0.06}s` }">
              <div class="memo-dot" :style="{ background: '#8b5cf6' }"></div>
              <div class="memo-content">
                <p class="memo-text">{{ result.content }}</p>
                <div class="memo-footer">
                  <span class="memo-tag">{{ result.source || '知识库' }}</span>
                  <span class="memo-time">相关度: {{ (result.score * 100).toFixed(1) }}%</span>
                </div>
              </div>
            </div>
          </TransitionGroup>
        </div>

        <div class="detail-list">
          <div class="list-title">{{ showSearchResults ? '搜索结果' : '记忆片段' }}</div>

          <div v-if="activeLayerData.items.length === 0 && !memoryStore.loading" class="empty-layer">
            <Archive :size="32" />
            <p>暂无记忆数据</p>
            <p class="empty-hint">进行对话后，AI 会自动提取并存储记忆</p>
          </div>

          <TransitionGroup v-else name="memo-list" tag="div" class="memo-items">
            <div v-for="(item, idx) in activeLayerData.items" :key="item.id" class="memo-item"
              :style="{ '--item-delay': `${idx * 0.06}s` }">
              <div class="memo-dot" :style="{ background: activeLayerData.color }"></div>
              <div class="memo-content">
                <template v-if="editingFactId === item.id">
                  <textarea v-model="editingContent" class="edit-textarea" rows="2"></textarea>
                  <div class="edit-actions">
                    <button class="edit-btn save" @click="saveEdit" :disabled="!editingContent.trim()">
                      <Save :size="12" /> 保存
                    </button>
                    <button class="edit-btn cancel" @click="cancelEdit">
                      <X :size="12" /> 取消
                    </button>
                  </div>
                </template>
                <template v-else>
                  <p class="memo-text">{{ item.text }}</p>
                  <div class="memo-footer">
                    <span class="memo-tag">{{ item.tag }}</span>
                    <span class="memo-tag category-tag">{{ getCategoryLabel(item.category) }}</span>
                    <span class="memo-time">{{ item.time }}</span>
                  </div>
                </template>
              </div>
              <div v-if="editingFactId !== item.id" class="memo-actions">
                <button class="memo-action-btn" title="就此对话" @click="chatAboutMemory(item)">
                  <MessageSquare :size="13" />
                </button>
                <button class="memo-action-btn" title="编辑" @click="startEdit(item)">
                  <Edit3 :size="13" />
                </button>
                <button class="memo-action-btn danger" title="删除" @click="handleDeleteFact(item)">
                  <Trash2 :size="13" />
                </button>
              </div>
            </div>
          </TransitionGroup>
        </div>

        <div v-if="hasProfile" class="portrait-card">
          <div class="portrait-header">
            <User :size="15" />
            <span>用户画像</span>
          </div>
          <div class="portrait-tags">
            <span v-for="tag in userPortrait?.tags" :key="tag" class="p-tag">{{ tag }}</span>
          </div>
          <div v-if="userPortrait?.interests?.length" class="portrait-interests">
            <BookOpen :size="13" />
            <span v-for="int in userPortrait.interests" :key="int" class="i-tag">{{ int }}</span>
          </div>
          <div class="portrait-stats-row">
            <div class="ps-item">
              <Archive :size="13" />
              <span>{{ (userPortrait?.interactionCount || 0).toLocaleString() }} 条记忆</span>
            </div>
            <div class="ps-item">
              <Activity :size="13" />
              <span>记忆健康 {{ userPortrait?.memoryHealth || 0 }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <Transition name="dialog-fade">
      <div v-if="showAddDialog" class="dialog-overlay" @click.self="showAddDialog = false">
        <div class="dialog-card">
          <div class="dialog-header">
            <Plus :size="16" />
            <span>添加记忆事实</span>
            <button class="dialog-close-btn" @click="showAddDialog = false">
              <X :size="16" />
            </button>
          </div>
          <div class="dialog-body">
            <textarea v-model="newFactContent" placeholder="输入记忆内容，例如：用户喜欢 Vue 3 框架，偏好组合式 API..."
              rows="4" class="dialog-textarea"></textarea>
            <div class="dialog-category">
              <span class="category-label">分类：</span>
              <select v-model="newFactCategory" class="category-select">
                <option v-for="opt in categoryOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
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
  to {
    transform: rotate(360deg);
  }
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
  background: rgba(139, 92, 246, 0.1);
  color: #8b5cf6;
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
  border-color: #8b5cf6;
  box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.15);
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-bar input {
  width: 140px;
  font-size: 13px;
  background: transparent;
  color: var(--text);
}

.search-bar input::placeholder {
  color: var(--text-muted);
}

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

.search-trigger-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.search-refresh {
  color: var(--text-muted);
}

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

.h-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.h-btn.primary {
  color: var(--text);
  background: rgba(139, 92, 246, 0.1);
  border: 1px solid rgba(139, 92, 246, 0.2);
}

.h-btn.primary:hover {
  background: rgba(139, 92, 246, 0.18);
}

.memory-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.layer-stack {
  width: 340px;
  padding: 20px;
  border-right: 1px solid var(--border);
  overflow-y: auto;
  flex-shrink: 0;
  background: var(--surface);
}

.stack-visual {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.layer-card {
  padding: 16px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--bg);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  opacity: 0;
  animation: card-enter 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: var(--layer-delay);
}

@keyframes card-enter {
  from {
    opacity: 0;
    transform: translateX(-16px);
  }

  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.layer-card:hover {
  border-color: var(--layer-color);
  box-shadow: 0 4px 20px color-mix(in srgb, var(--layer-color) 10%, transparent);
}

.layer-card.active {
  border-color: var(--layer-color);
  background: color-mix(in srgb, var(--layer-color) 4%, transparent);
}

.layer-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.layer-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.layer-meta {
  flex: 1;
  min-width: 0;
}

.layer-name {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.layer-sub {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
}

.layer-indicator {
  color: var(--text-muted);
  opacity: 0.4;
}

.layer-bar-wrap {
  margin-bottom: 8px;
}

.layer-bar-track {
  height: 5px;
  background: var(--border);
  border-radius: 3px;
  overflow: hidden;
}

.layer-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 800ms cubic-bezier(0.22, 1, 0.36, 1);
}

.layer-bar-label {
  display: block;
  text-align: right;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
  font-family: monospace;
}

.layer-desc {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.5;
}

.flow-arrow {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(139, 92, 246, 0.06);
  font-size: 11px;
  color: var(--text-muted);
}

.flow-arrow svg {
  color: #8b5cf6;
  flex-shrink: 0;
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

.detail-capacity {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 20px;
  border-radius: 14px;
  background: var(--surface);
  border: 1px solid var(--border);
}

.cap-ring {
  position: relative;
  width: 90px;
  height: 90px;
  flex-shrink: 0;
}

.cap-svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.cap-progress {
  transition: stroke-dashoffset 1s cubic-bezier(0.22, 1, 0.36, 1);
}

.cap-text {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.cap-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
}

.cap-unit {
  font-size: 10px;
  color: var(--text-muted);
}

.cap-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-muted);
}

.stat-item svg {
  color: #8b5cf6;
}

.detail-list {
  flex: 1;
}

.list-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text);
}

.empty-layer {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--text-muted);
}

.empty-layer svg {
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-layer p {
  font-size: 14px;
  margin-bottom: 4px;
}

.empty-hint {
  font-size: 12px !important;
  opacity: 0.7;
}

.memo-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.memo-item {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid transparent;
  transition: all 300ms ease-in-out;
  opacity: 0;
  animation: memo-in 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: var(--item-delay);
  position: relative;
}

@keyframes memo-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.memo-item:hover {
  border-color: var(--border);
}

.memo-item:hover .memo-actions {
  opacity: 1;
}

.memo-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  margin-top: 7px;
  flex-shrink: 0;
}

.memo-content {
  flex: 1;
  min-width: 0;
}

.memo-text {
  font-size: 13px;
  color: var(--text);
  line-height: 1.5;
  margin-bottom: 6px;
}

.memo-footer {
  display: flex;
  align-items: center;
  gap: 6px;
}

.memo-tag {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 8px;
  background: rgba(139, 92, 246, 0.1);
  color: #8b5cf6;
  font-weight: 500;
}

.memo-tag.category-tag {
  background: rgba(245, 158, 11, 0.1);
  color: #b45309;
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

.memo-action-btn:hover {
  background: var(--surface-hover);
  color: var(--lumi-primary);
}

.memo-action-btn.danger:hover {
  background: rgba(244, 63, 94, 0.1);
  color: #f43f5e;
}

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

.edit-textarea:focus {
  border-color: #8b5cf6;
}

.edit-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

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

.edit-btn.save {
  background: rgba(139, 92, 246, 0.1);
  color: #8b5cf6;
}

.edit-btn.save:hover {
  background: rgba(139, 92, 246, 0.2);
}

.edit-btn.save:disabled {
  opacity: 0.5;
  cursor: default;
}

.edit-btn.cancel {
  background: var(--surface-hover);
  color: var(--text-muted);
}

.edit-btn.cancel:hover {
  color: var(--text);
}

.portrait-card {
  padding: 18px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.06), rgba(20, 126, 188, 0.04));
  border: 1px solid var(--border);
}

.portrait-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 14px;
  color: var(--text);
}

.portrait-header svg {
  color: #8b5cf6;
}

.portrait-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.p-tag {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 20px;
  background: rgba(139, 92, 246, 0.1);
  color: #a78bfa;
  font-weight: 500;
}

.portrait-interests {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.portrait-interests>svg {
  color: var(--text-muted);
  flex-shrink: 0;
}

.i-tag {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 8px;
  background: var(--surface);
  color: var(--text-muted);
}

.portrait-stats-row {
  display: flex;
  gap: 20px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.ps-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.ps-item svg {
  color: var(--lumi-primary);
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.dialog-card {
  width: 460px;
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

.dialog-close-btn:hover {
  background: var(--surface-hover);
}

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

.dialog-textarea:focus {
  border-color: #8b5cf6;
}

.dialog-textarea::placeholder {
  color: var(--text-muted);
}

.dialog-category {
  display: flex;
  align-items: center;
  gap: 10px;
}

.category-label {
  font-size: 13px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.category-select {
  flex: 1;
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

.dialog-btn.cancel {
  background: var(--surface);
  color: var(--text-muted);
}

.dialog-btn.cancel:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.dialog-btn.confirm {
  background: rgba(139, 92, 246, 0.1);
  color: #8b5cf6;
  border: 1px solid rgba(139, 92, 246, 0.2);
}

.dialog-btn.confirm:hover {
  background: rgba(139, 92, 246, 0.2);
}

.dialog-btn.confirm:disabled {
  opacity: 0.5;
  cursor: default;
}

.dialog-fade-enter-active {
  animation: fade-in 0.25s ease-out;
}

.dialog-fade-enter-active .dialog-card {
  animation: scale-in 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.dialog-fade-leave-active {
  animation: fade-in 0.2s ease-out reverse;
}

@keyframes fade-in {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

@keyframes scale-in {
  from {
    opacity: 0;
    transform: scale(0.92);
  }

  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes fade-up {
  0% {
    opacity: 0;
    transform: translateY(16px);
  }

  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-up {
  animation: fade-up 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes slide-left {
  0% {
    opacity: 0;
    transform: translateX(24px);
  }

  100% {
    opacity: 1;
    transform: translateX(0);
  }
}

.animate-slide-left {
  animation: slide-left 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.memo-list-enter-active,
.memo-list-leave-active {
  transition: all 300ms ease-in-out;
}

.memo-list-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.memo-list-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}
</style>