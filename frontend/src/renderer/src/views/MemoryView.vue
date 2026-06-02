<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Brain,
  RefreshCw,
  Loader2,
  X,
  Save,
  Globe,
  BookOpen,
  FileText,
  Plus,
  Edit3,
  Trash2,
  Archive,
  MessageSquare,
  Calendar,
  Sparkles,
  Activity,
  Tag,
  Users,
  MoreVertical,
  Eraser,
} from 'lucide-vue-next'
import { useMemoryStore, CATEGORY_LABELS, CATEGORY_COLORS, FACT_CATEGORIES } from '../stores/memory'
import type { FactItem, FactCategory } from '../stores/memory'
import { useToast } from '../composables/useToast'

const router = useRouter()
const memoryStore = useMemoryStore()
const toast = useToast()

const showMenu = ref(false)
const menuPosition = ref({ x: 0, y: 0 })

// 确认对话框状态
type ConfirmAction = 'clearFacts' | 'clearKnowledge' | 'clearDailies' | 'clearSummary' | 'resetAll'
const showConfirm = ref(false)
const confirmAction = ref<ConfirmAction | null>(null)
const confirmTitle = ref('')
const confirmMessage = ref('')
const confirmDanger = ref(false)
const isProcessing = ref(false)

interface LayerTab {
  id: string
  name: string
  sub: string
  icon: typeof Brain
  color: string
  desc: string
}

const layerTabs = ref<LayerTab[]>([
  { id: 'profile', name: '用户档案', sub: 'memory.json', icon: Globe, color: '#8b5cf6', desc: '用户档案与记忆事实 · 所有对话共享' },
  { id: 'knowledge', name: '知识记忆', sub: 'knowledge.md', icon: BookOpen, color: '#22c55e', desc: '知识库 · 结构化知识存储' },
  { id: 'daily', name: '近期对话', sub: 'daily/*.md', icon: Activity, color: '#f59e0b', desc: '近期动态 · 每日对话记录' },
  { id: 'summary', name: 'AI总结', sub: 'memory.json', icon: Sparkles, color: '#0ea5e9', desc: 'AI自动提炼 · 结构化总结' },
])

const activeTab = ref('profile')

const isEditingKnowledge = ref(false)
const editKnowledgeContent = ref('')

const isEditingSummary = ref(false)
const editSummaryContent = ref('')

const selectedDailyDate = ref('')
const newDailyContent = ref('')
const isAddingDaily = ref(false)

const showAddFact = ref(false)
const newFactContent = ref('')
const newFactCategory = ref<FactCategory>('context')
const newFactConfidence = ref(0.8)

const editingFactId = ref<string | null>(null)
const editFactContent = ref('')
const editFactCategory = ref<FactCategory>('context')
const editFactConfidence = ref(0.8)

const profile = computed(() => memoryStore.profile)
const hasProfile = computed(() => !!profile.value.name)

const factsByCategory = computed(() => {
  const groups: Record<string, FactItem[]> = {}
  for (const cat of FACT_CATEGORIES) {
    groups[cat] = []
  }
  for (const fact of memoryStore.facts) {
    if (groups[fact.category]) {
      groups[fact.category].push(fact)
    } else {
      groups['context'].push(fact)
    }
  }
  return groups
})

const factCount = computed(() => memoryStore.facts.length)

const knowledgeSectionCards = computed(() => {
  return memoryStore.knowledgeSections.filter(s => s.title || s.content)
})

const summarySectionNames = ['用户画像', '偏好设置', '兴趣目标', '近期状态', '事件时间线'] as const

const summarySectionColors: Record<string, string> = {
  '用户画像': '#8b5cf6',
  '偏好设置': '#f59e0b',
  '兴趣目标': '#22c55e',
  '近期状态': '#06b6d4',
  '事件时间线': '#0ea5e9',
}

const hasSummary = computed(() => {
  const s = memoryStore.summarySections
  return !!(s['用户画像'] || s['偏好设置'] || s['兴趣目标'] || s['近期状态'] || s['事件时间线'])
})

const dailyLines = computed(() => {
  const content = memoryStore.dailyContent
  if (!content) return []
  return content.split('\n').filter((l: string) => l.trim())
})

function switchTab(tabId: string) {
  activeTab.value = tabId
  if (tabId === 'knowledge' && !memoryStore.knowledgeContent) {
    memoryStore.fetchKnowledge(selectedAgentId.value)
  }
  if (tabId === 'daily' && memoryStore.dailies.length === 0) {
    memoryStore.fetchDailies(selectedAgentId.value)
  }
  if (tabId === 'summary' && !memoryStore.summaryContent) {
    memoryStore.fetchSummary(selectedAgentId.value)
  }
}

function startAddFact() {
  showAddFact.value = true
  newFactContent.value = ''
  newFactCategory.value = 'context'
  newFactConfidence.value = 0.8
}

function cancelAddFact() {
  showAddFact.value = false
}

async function confirmAddFact() {
  if (!newFactContent.value.trim()) return
  await memoryStore.addFact({
    content: newFactContent.value.trim(),
    category: newFactCategory.value,
    confidence: newFactConfidence.value,
  })
  showAddFact.value = false
}

function startEditFact(fact: FactItem) {
  editingFactId.value = fact.id
  editFactContent.value = fact.content
  editFactCategory.value = fact.category as FactCategory
  editFactConfidence.value = fact.confidence
}

function cancelEditFact() {
  editingFactId.value = null
}

async function saveEditFact() {
  if (!editingFactId.value) return
  await memoryStore.updateFact(editingFactId.value, {
    content: editFactContent.value,
    category: editFactCategory.value,
    confidence: editFactConfidence.value,
  })
  editingFactId.value = null
}

async function deleteFact(factId: string) {
  await memoryStore.removeFact(factId)
}

function startEditKnowledge() {
  editKnowledgeContent.value = memoryStore.knowledgeContent
  isEditingKnowledge.value = true
}

function cancelEditKnowledge() {
  isEditingKnowledge.value = false
  editKnowledgeContent.value = ''
}

async function saveEditKnowledge() {
  if (!editKnowledgeContent.value.trim() && editKnowledgeContent.value !== '') return
  isSaving.value = true
  try {
    await memoryStore.saveKnowledge(editKnowledgeContent.value)
    isEditingKnowledge.value = false
    editKnowledgeContent.value = ''
  } finally {
    isSaving.value = false
  }
}

function startEditSummary() {
  editSummaryContent.value = memoryStore.summaryContent
  isEditingSummary.value = true
}

function cancelEditSummary() {
  isEditingSummary.value = false
  editSummaryContent.value = ''
}

async function saveEditSummary() {
  if (!editSummaryContent.value.trim() && editSummaryContent.value !== '') return
  isSaving.value = true
  try {
    await memoryStore.saveSummary(editSummaryContent.value)
    isEditingSummary.value = false
    editSummaryContent.value = ''
  } finally {
    isSaving.value = false
  }
}

async function selectDaily(date: string) {
  selectedDailyDate.value = date
  await memoryStore.fetchDaily(date, selectedAgentId.value)
}

async function handleAddDaily() {
  if (!newDailyContent.value.trim()) return
  isAddingDaily.value = true
  try {
    await memoryStore.appendDaily(newDailyContent.value.trim(), selectedDailyDate.value || undefined, selectedAgentId.value)
    newDailyContent.value = ''
  } finally {
    isAddingDaily.value = false
  }
}

function chatAboutMemory(text: string) {
  const event = new CustomEvent('luominest:memory-chat-trigger', { detail: { text } })
  window.dispatchEvent(event)
  router.push('/workspace')
}

const isSaving = ref(false)

const selectedAgentId = ref<string | null>(null)

async function onAgentChange() {
  localStorage.setItem('lastMemoryAgentId', selectedAgentId.value || '')
  selectedDailyDate.value = ''
  await memoryStore.switchAgent(selectedAgentId.value)
}

async function loadData() {
  await memoryStore.fetchMemoryAgents()
  
  const lastAgentId = localStorage.getItem('lastMemoryAgentId')
  if (lastAgentId && memoryStore.memoryAgents.some(a => a.id === lastAgentId)) {
    selectedAgentId.value = lastAgentId
  } else if (memoryStore.memoryAgents.length > 0) {
    selectedAgentId.value = memoryStore.memoryAgents[0].id
  }
  
  await Promise.all([
    memoryStore.fetchMemory(selectedAgentId.value),
    memoryStore.fetchKnowledge(selectedAgentId.value),
    memoryStore.fetchSummary(selectedAgentId.value),
    memoryStore.fetchDailies(selectedAgentId.value),
  ])
}

onMounted(() => { loadData() })

// 菜单处理
const toggleMenu = (event: MouseEvent) => {
  event.stopPropagation()
  if (showMenu.value) {
    showMenu.value = false
  } else {
    const rect = (event.target as HTMLElement).getBoundingClientRect()
    menuPosition.value = { x: rect.left, y: rect.bottom + 8 }
    showMenu.value = true
  }
}

// 点击外部关闭菜单
const closeMenu = () => {
  showMenu.value = false
}

// 确认对话框处理
const openConfirm = (action: ConfirmAction) => {
  confirmAction.value = action
  confirmDanger.value = false
  
  switch (action) {
    case 'clearFacts':
      confirmTitle.value = '清空事实库'
      confirmMessage.value = `确定要清空该 Agent 的所有 ${factCount.value} 条事实吗？`
      break
    case 'clearKnowledge':
      confirmTitle.value = '清空知识记忆'
      confirmMessage.value = '确定要清空所有知识记忆吗？'
      break
    case 'clearDailies':
      confirmTitle.value = '清空近期对话'
      confirmMessage.value = `确定要清空所有 ${memoryStore.dailies.length} 天的对话记录吗？`
      break
    case 'clearSummary':
      confirmTitle.value = '重置AI总结'
      confirmMessage.value = '确定要重置所有AI总结吗？'
      break
    case 'resetAll':
      confirmTitle.value = '清空全部记忆'
      confirmMessage.value = '警告：这将删除所有记忆数据（包括档案、事实、知识、对话和总结），无法恢复！确定要继续吗？'
      confirmDanger.value = true
      break
  }
  
  showConfirm.value = true
  showMenu.value = false
}

const cancelConfirm = () => {
  showConfirm.value = false
  confirmAction.value = null
}

const executeConfirm = async () => {
  if (!confirmAction.value || isProcessing.value) return
  
  isProcessing.value = true
  try {
    switch (confirmAction.value) {
      case 'clearFacts':
        await memoryStore.clearFacts(selectedAgentId.value)
        toast.success('事实库已清空')
        break
      case 'clearKnowledge':
        await memoryStore.clearKnowledge(selectedAgentId.value)
        toast.success('知识记忆已清空')
        break
      case 'clearDailies':
        await memoryStore.clearDailies(selectedAgentId.value)
        selectedDailyDate.value = ''
        toast.success('近期对话已清空')
        break
      case 'clearSummary':
        await memoryStore.clearSummary(selectedAgentId.value)
        toast.success('AI总结已重置')
        break
      case 'resetAll':
        await memoryStore.resetAll(selectedAgentId.value)
        toast.success('所有记忆已重置')
        break
    }
    showConfirm.value = false
    confirmAction.value = null
  } catch (error) {
    console.error('操作失败:', error)
    toast.error('操作失败，请重试')
  } finally {
    isProcessing.value = false
  }
}

// 点击外部关闭菜单
window.addEventListener('click', closeMenu)
</script>

<template>
  <div class="memory-view">
    <div class="memory-header">
      <div class="header-left">
        <Brain :size="20" />
        <h2>记忆中枢</h2>
        <span class="header-badge">结构化记忆 · JSON 驱动</span>
      </div>
      <div class="header-actions">
        <div class="agent-selector">
          <Users :size="14" />
          <select v-model="selectedAgentId" class="agent-select" @change="onAgentChange">
            <option v-for="a in memoryStore.memoryAgents" :key="a.id" :value="a.id">
              {{ a.name }}{{ a.fact_count !== undefined ? ` (${a.fact_count}条)` : '' }}
            </option>
          </select>
        </div>
        <button class="h-btn" @click="loadData">
          <RefreshCw :size="15" :class="{ spinning: memoryStore.loading }" />
        </button>
        <button class="h-btn" @click="toggleMenu">
          <MoreVertical :size="15" />
        </button>
      </div>
    </div>
    
    <!-- 下拉菜单 -->
    <div v-if="showMenu" class="dropdown-menu" :style="{ left: menuPosition.x + 'px', top: menuPosition.y + 'px' }">
      <div class="menu-item" @click="openConfirm('clearFacts')">
        <Trash2 :size="16" />
        <span>清空事实库 ({{ factCount }})</span>
      </div>
      <div class="menu-item" @click="openConfirm('clearKnowledge')">
        <BookOpen :size="16" />
        <span>清空知识记忆</span>
      </div>
      <div class="menu-item" @click="openConfirm('clearDailies')">
        <Activity :size="16" />
        <span>清空近期对话</span>
      </div>
      <div class="menu-item" @click="openConfirm('clearSummary')">
        <Sparkles :size="16" />
        <span>重置AI总结</span>
      </div>
      <div class="menu-divider"></div>
      <div class="menu-item danger" @click="openConfirm('resetAll')">
        <Eraser :size="16" />
        <span>清空全部记忆 ⚠️</span>
      </div>
    </div>
    
    <!-- 确认对话框 -->
    <div v-if="showConfirm" class="confirm-overlay" @click="cancelConfirm">
      <div class="confirm-dialog" @click.stop>
        <div class="confirm-header">
          <h3>{{ confirmTitle }}</h3>
        </div>
        <div class="confirm-body">
          <p>{{ confirmMessage }}</p>
        </div>
        <div class="confirm-footer">
          <button class="h-btn" @click="cancelConfirm" :disabled="isProcessing">取消</button>
          <button 
            class="h-btn" 
            :class="{ primary: !confirmDanger, danger: confirmDanger }" 
            @click="executeConfirm" 
            :disabled="isProcessing"
          >
            <Loader2 v-if="isProcessing" :size="14" class="spinning" />
            <span v-else>确定</span>
          </button>
        </div>
      </div>
    </div>

    <div v-if="memoryStore.loading && !profile.name && memoryStore.facts.length === 0" class="memory-loading">
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
              <span class="nav-sub">{{ tab.desc }}</span>
            </div>
          </div>
          <div class="nav-stats">
            <span v-if="tab.id === 'profile'" class="nav-stat">{{ factCount }} 条事实 · {{ hasProfile ? '有档案' : '无档案' }}</span>
            <span v-else-if="tab.id === 'knowledge'" class="nav-stat">{{ knowledgeSectionCards.length > 0 ? knowledgeSectionCards.length + ' 节' : '空' }}</span>
            <span v-else-if="tab.id === 'daily'" class="nav-stat">{{ memoryStore.dailies.length }} 天记录</span>
            <span v-else-if="tab.id === 'summary'" class="nav-stat">{{ hasSummary ? '已总结' : '未总结' }}</span>
          </div>
        </div>
      </div>

      <div class="memory-detail animate-slide-left">
        <template v-if="activeTab === 'profile'">
          <div class="detail-header">
            <Globe :size="22" :style="{ color: '#8b5cf6' }" />
            <h3>用户档案</h3>
            <span class="detail-sub">memory.json · 结构化记忆</span>
            <div class="detail-actions">
              <button class="h-btn primary" @click="startAddFact">
                <Plus :size="14" /> 添加事实
              </button>
            </div>
          </div>

          <div v-if="hasProfile" class="profile-card">
            <div class="profile-top">
              <div class="profile-avatar-lg">{{ profile.name?.[0] || '?' }}</div>
              <div class="profile-info">
                <span class="profile-name">{{ profile.name || '未知用户' }}</span>
              </div>
            </div>
          </div>

          <div v-if="showAddFact" class="add-fact-form">
            <div class="add-fact-row">
              <input v-model="newFactContent" type="text" placeholder="输入事实内容..." class="add-fact-input" />
              <select v-model="newFactCategory" class="add-fact-select">
                <option v-for="cat in FACT_CATEGORIES" :key="cat" :value="cat">{{ CATEGORY_LABELS[cat] }}</option>
              </select>
              <input v-model.number="newFactConfidence" type="number" min="0.5" max="1.0" step="0.1" class="add-fact-confidence" />
              <button class="h-btn primary" @click="confirmAddFact" :disabled="!newFactContent.trim() || memoryStore.saving">
                <Loader2 v-if="memoryStore.saving" :size="14" class="spinning" />
                <Save v-else :size="14" />
              </button>
              <button class="h-btn" @click="cancelAddFact"><X :size="14" /></button>
            </div>
          </div>

          <div v-if="factCount === 0 && !showAddFact" class="empty-section">
            <Archive :size="28" />
            <p>暂无记忆事实</p>
            <p class="empty-hint">对话中AI会自动提取并存储用户信息</p>
          </div>

          <div v-else class="facts-grid">
            <div v-for="(items, cat) in factsByCategory" :key="cat">
              <div v-if="items.length > 0" class="fact-category-group">
                <div class="fact-category-header" :style="{ '--cat-color': CATEGORY_COLORS[cat] || '#8b5cf6' }">
                  <div class="cat-dot"></div>
                  <Tag :size="13" :style="{ color: CATEGORY_COLORS[cat] || '#8b5cf6' }" />
                  <span class="cat-label">{{ CATEGORY_LABELS[cat] || cat }}</span>
                  <span class="cat-count">{{ items.length }}</span>
                </div>
                <div class="fact-items">
                  <div
                    v-for="fact in items"
                    :key="fact.id"
                    class="fact-item"
                    :style="{ '--fact-color': CATEGORY_COLORS[fact.category] || '#8b5cf6' }"
                  >
                    <template v-if="editingFactId === fact.id">
                      <div class="fact-edit-row">
                        <input v-model="editFactContent" type="text" class="add-fact-input" />
                        <select v-model="editFactCategory" class="add-fact-select">
                          <option v-for="c in FACT_CATEGORIES" :key="c" :value="c">{{ CATEGORY_LABELS[c] }}</option>
                        </select>
                        <input v-model.number="editFactConfidence" type="number" min="0.5" max="1.0" step="0.1" class="add-fact-confidence" />
                        <button class="h-btn primary" @click="saveEditFact" :disabled="memoryStore.saving">
                          <Save :size="13" />
                        </button>
                        <button class="h-btn" @click="cancelEditFact"><X :size="13" /></button>
                      </div>
                    </template>
                    <template v-else>
                      <div class="fact-main">
                        <div class="fact-confidence-bar">
                          <div class="fact-confidence-fill" :style="{ width: (fact.confidence * 100) + '%', background: CATEGORY_COLORS[fact.category] || '#8b5cf6' }"></div>
                        </div>
                        <span class="fact-text">{{ fact.content }}</span>
                        <span v-if="fact.source_error" class="fact-error">避免: {{ fact.source_error }}</span>
                      </div>
                      <div class="fact-actions">
                        <button class="fact-btn" @click="startEditFact(fact)"><Edit3 :size="12" /></button>
                        <button class="fact-btn danger" @click="deleteFact(fact.id)"><Trash2 :size="12" /></button>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <template v-if="activeTab === 'knowledge'">
          <div class="detail-header">
            <BookOpen :size="22" :style="{ color: '#22c55e' }" />
            <h3>知识记忆</h3>
            <span class="detail-sub">knowledge.md · 结构化知识</span>
            <div class="detail-actions">
              <button v-if="!isEditingKnowledge" class="h-btn primary" @click="startEditKnowledge">
                <Edit3 :size="14" /> 编辑
              </button>
              <template v-else>
                <button class="h-btn" @click="cancelEditKnowledge"><X :size="14" /> 取消</button>
                <button class="h-btn primary" @click="saveEditKnowledge" :disabled="isSaving">
                  <Loader2 v-if="isSaving" :size="14" class="spinning" />
                  <Save v-else :size="14" /> 保存
                </button>
              </template>
            </div>
          </div>

          <div v-if="isEditingKnowledge" class="editor-section">
            <textarea v-model="editKnowledgeContent" class="memory-editor" placeholder="编辑 knowledge.md 内容..."></textarea>
          </div>
          <div v-else class="markdown-preview">
            <div v-if="knowledgeSectionCards.length === 0" class="empty-section">
              <BookOpen :size="28" />
              <p>暂无知识记忆</p>
              <p class="empty-hint">对话中AI会自动提取并存储知识信息</p>
            </div>
            <template v-else>
              <div v-for="(section, idx) in knowledgeSectionCards" :key="idx" class="memory-section-card" :style="{ '--ms-color': '#22c55e' }">
                <div class="ms-header">
                  <div class="ms-dot"></div>
                  <span class="ms-label">{{ section.title }}</span>
                  <span class="ms-count">{{ section.content.split('\n').filter((l: string) => l.trim()).length }} 行</span>
                </div>
                <div class="ms-body">
                  <p v-for="(line, lidx) in section.content.split('\n').filter((l: string) => l.trim())" :key="lidx" class="ms-line">{{ line.replace(/^-\s*/, '') }}</p>
                </div>
              </div>
            </template>
          </div>
        </template>

        <template v-if="activeTab === 'daily'">
          <div class="detail-header">
            <Activity :size="22" :style="{ color: '#f59e0b' }" />
            <h3>近期对话</h3>
            <span class="detail-sub">daily/*.md · 近期动态</span>
          </div>

          <div class="daily-layout">
            <div class="daily-sidebar">
              <div class="section-title">日期列表</div>
              <div v-if="memoryStore.dailies.length === 0" class="empty-section small">
                <Archive :size="20" />
                <p>暂无记录</p>
              </div>
              <div v-else class="daily-dates">
                <div
                  v-for="date in [...memoryStore.dailies].reverse()"
                  :key="date"
                  :class="['daily-date-item', { active: selectedDailyDate === date }]"
                  @click="selectDaily(date)"
                >
                  <FileText :size="13" />
                  <span>{{ date }}</span>
                </div>
              </div>
            </div>

            <div class="daily-main">
              <div v-if="!selectedDailyDate" class="empty-section">
                <Calendar :size="28" />
                <p>选择日期查看记录</p>
              </div>
              <template v-else>
                <div class="daily-header">
                  <span class="daily-date-label">{{ selectedDailyDate }}</span>
                </div>
                <div v-if="dailyLines.length === 0" class="empty-section small">
                  <Archive :size="20" />
                  <p>当天无记录</p>
                </div>
                <div v-else class="memo-items">
                  <div v-for="(line, idx) in dailyLines" :key="idx" class="memo-item" :style="{ '--item-delay': `${idx * 0.04}s` }">
                    <div class="memo-dot" :style="{ background: line.startsWith('-') ? '#f59e0b' : '#8b5cf6' }"></div>
                    <div class="memo-content">
                      <p class="memo-text">{{ line.replace(/^-\s*/, '').replace(/^#+\s*/, '') }}</p>
                    </div>
                  </div>
                </div>
                <div class="add-daily-section">
                  <div class="add-daily-row">
                    <input v-model="newDailyContent" type="text" placeholder="添加记录..." class="add-daily-input" @keydown.enter="handleAddDaily" />
                    <button class="h-btn primary" @click="handleAddDaily" :disabled="isAddingDaily || !newDailyContent.trim()">
                      <Loader2 v-if="isAddingDaily" :size="14" class="spinning" />
                      <Plus v-else :size="14" />
                    </button>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </template>

        <template v-if="activeTab === 'summary'">
          <div class="detail-header">
            <Sparkles :size="22" :style="{ color: '#0ea5e9' }" />
            <h3>AI总结</h3>
            <span class="detail-sub">memory.json · AI自动提炼</span>
            <div class="detail-actions">
              <button v-if="!isEditingSummary" class="h-btn primary" @click="startEditSummary">
                <Edit3 :size="14" /> 编辑
              </button>
              <template v-else>
                <button class="h-btn" @click="cancelEditSummary"><X :size="14" /> 取消</button>
                <button class="h-btn primary" @click="saveEditSummary" :disabled="isSaving">
                  <Loader2 v-if="isSaving" :size="14" class="spinning" />
                  <Save v-else :size="14" /> 保存
                </button>
              </template>
            </div>
          </div>

          <div v-if="isEditingSummary" class="editor-section">
            <textarea v-model="editSummaryContent" class="memory-editor" placeholder="编辑 AI 总结内容..."></textarea>
          </div>
          <template v-else>
            <div v-if="!hasSummary" class="empty-section">
              <Sparkles :size="28" />
              <p>暂无AI总结</p>
              <p class="empty-hint">对话积累后AI会自动提炼关键信息</p>
            </div>
            <template v-else>
              <div
                v-for="sectionName in summarySectionNames"
                :key="sectionName"
              >
                <div v-if="memoryStore.summarySections[sectionName]" class="distilled-section-card" :style="{ '--section-color': summarySectionColors[sectionName] }">
                  <div class="distilled-section-header">
                    <div class="section-dot" :style="{ background: summarySectionColors[sectionName] }"></div>
                    <span class="section-title-text">{{ sectionName }}</span>
                  </div>
                  <div class="distilled-section-body">
                    <p v-for="(line, idx) in memoryStore.summarySections[sectionName].split('\n').filter((l: string) => l.trim())" :key="idx" class="distilled-line">{{ line.replace(/^-\s*/, '') }}</p>
                  </div>
                </div>
              </div>
            </template>
          </template>
        </template>

        <div v-if="memoryStore.injectionContent" class="injection-section">
          <div class="section-title"><MessageSquare :size="14" /> 注入预览 (LLM可见)</div>
          <pre class="injection-preview">{{ memoryStore.injectionContent }}</pre>
        </div>
      </div>
    </div>
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
  position: relative;
}

/* 下拉菜单样式 */
.dropdown-menu {
  position: fixed;
  z-index: 1000;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 8px 0;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  min-width: 200px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.2s;
  font-size: 14px;
  color: var(--text);
}

.menu-item:hover {
  background: var(--surface-hover);
}

.menu-item.danger {
  color: #ef4444;
}

.menu-item.danger:hover {
  background: rgba(239, 68, 68, 0.1);
}

.menu-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 0;
}

/* 确认对话框样式 */
.confirm-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1001;
}

.confirm-dialog {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  max-width: 400px;
  width: 90%;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.confirm-header h3 {
  margin: 0 0 12px 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
}

.confirm-body {
  margin-bottom: 24px;
}

.confirm-body p {
  margin: 0;
  font-size: 14px;
  color: var(--text-muted);
  line-height: 1.5;
}

.confirm-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.h-btn.danger {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #ef4444;
}

.h-btn.danger:hover {
  background: rgba(239, 68, 68, 0.2);
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

.spinning { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

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

.agent-selector {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-muted);
}

.agent-select {
  background: transparent;
  border: none;
  color: var(--text);
  font-size: 12px;
  outline: none;
  cursor: pointer;
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

.h-btn:hover { background: var(--surface-hover); color: var(--text); }

.h-btn.primary {
  color: var(--text);
  background: var(--task-purple-soft);
  border: 1px solid var(--task-purple-border);
}

.h-btn.primary:hover { background: var(--task-purple-soft); }
.h-btn:disabled { opacity: 0.5; cursor: default; }

.memory-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.layer-nav {
  width: 280px;
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
  margin-bottom: 8px;
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

.detail-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
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
}

.profile-avatar-lg {
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

.add-fact-form {
  padding: 14px;
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--task-purple-border);
}

.add-fact-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.add-fact-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
  outline: none;
}

.add-fact-input:focus { border-color: var(--task-purple); }

.add-fact-select {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font-size: 12px;
  outline: none;
  min-width: 80px;
}

.add-fact-confidence {
  width: 60px;
  padding: 8px 6px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font-size: 12px;
  outline: none;
  text-align: center;
}

.facts-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.fact-category-group {
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  overflow: hidden;
}

.fact-category-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: color-mix(in srgb, var(--cat-color) 6%, transparent);
  border-bottom: 1px solid var(--border);
}

.cat-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--cat-color);
  flex-shrink: 0;
}

.cat-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.cat-count {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: auto;
  padding: 1px 8px;
  border-radius: 6px;
  background: var(--bg);
}

.fact-items {
  padding: 6px;
}

.fact-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  transition: all 200ms;
}

.fact-item:hover {
  background: color-mix(in srgb, var(--fact-color) 4%, transparent);
}

.fact-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.fact-confidence-bar {
  width: 32px;
  height: 4px;
  border-radius: 2px;
  background: var(--border);
  flex-shrink: 0;
  overflow: hidden;
}

.fact-confidence-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 300ms;
}

.fact-text {
  font-size: 13px;
  color: var(--text);
  line-height: 1.5;
}

.fact-error {
  font-size: 11px;
  color: #f97316;
  opacity: 0.8;
}

.fact-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 200ms;
}

.fact-item:hover .fact-actions {
  opacity: 1;
}

.fact-btn {
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

.fact-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.fact-btn.danger:hover {
  background: #ef444418;
  color: #ef4444;
}

.fact-edit-row {
  display: flex;
  gap: 6px;
  align-items: center;
  flex: 1;
}

.editor-section { flex: 1; min-height: 300px; }

.memory-editor {
  width: 100%;
  min-height: 400px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  line-height: 1.6;
  resize: vertical;
  outline: none;
}

.memory-editor:focus { border-color: var(--task-purple); }

.markdown-preview { flex: 1; }

.memory-section-card {
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  margin-bottom: 10px;
  transition: all 300ms ease-in-out;
}

.memory-section-card:hover {
  border-color: var(--ms-color);
  box-shadow: 0 2px 12px color-mix(in srgb, var(--ms-color) 8%, transparent);
}

.ms-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.ms-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ms-color);
  flex-shrink: 0;
}

.ms-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.ms-count {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: auto;
}

.ms-body {
  padding-left: 16px;
}

.ms-line {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.6;
  margin-bottom: 3px;
}

.distilled-section-card {
  padding: 16px;
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  transition: all 300ms ease-in-out;
}

.distilled-section-card:hover {
  border-color: var(--section-color);
  box-shadow: 0 2px 12px color-mix(in srgb, var(--section-color) 8%, transparent);
}

.distilled-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.section-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.section-title-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.distilled-section-body {
  padding-left: 16px;
}

.distilled-line {
  font-size: 13px;
  color: var(--text);
  line-height: 1.6;
  margin-bottom: 2px;
}

.injection-section {
  padding: 16px;
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
}

.injection-preview {
  font-size: 12px;
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-muted);
  margin: 8px 0 0;
  max-height: 200px;
  overflow-y: auto;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 6px;
}

.empty-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--text-muted);
}

.empty-section.small { padding: 20px; }
.empty-section svg { margin-bottom: 12px; opacity: 0.5; }
.empty-section p { font-size: 14px; margin-bottom: 4px; }
.empty-hint { font-size: 12px !important; opacity: 0.7; }

.daily-layout {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.daily-sidebar {
  width: 180px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.daily-dates {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 400px;
  overflow-y: auto;
}

.daily-date-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms;
}

.daily-date-item:hover { background: var(--surface-hover); color: var(--text); }
.daily-date-item.active { background: var(--lumi-sky-soft); color: var(--lumi-sky); font-weight: 600; }

.daily-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.daily-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.daily-date-label {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}

.memo-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.memo-item {
  display: flex;
  gap: 12px;
  padding: 10px 14px;
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
}

.add-daily-section { margin-top: 8px; }

.add-daily-row { display: flex; gap: 8px; }

.add-daily-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  outline: none;
}

.add-daily-input:focus { border-color: var(--task-purple); }
.add-daily-input::placeholder { color: var(--text-muted); }

.animate-fade-up { animation: fade-up 0.5s cubic-bezier(0.22, 1, 0.36, 1) both; }
@keyframes fade-up { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }

.animate-slide-left { animation: slide-left 0.5s cubic-bezier(0.22, 1, 0.36, 1) both; }
@keyframes slide-left { from { opacity: 0; transform: translateX(24px); } to { opacity: 1; transform: translateX(0); } }
</style>
