<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
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
  Calendar,
  Sparkles,
  Activity,
  Tag,
  MoreVertical,
  Eraser,
  Search,
  Filter,
  Download,
  Upload,
  ChevronDown,
  Check,
  AlertCircle,
} from 'lucide-vue-next'
import { useMemoryStore, CATEGORY_LABELS, CATEGORY_COLORS, FACT_CATEGORIES } from '../stores/memory'
import type { FactItem, FactCategory } from '../stores/memory'
import { useToast } from '../composables/useToast'

const memoryStore = useMemoryStore()
const toast = useToast()

const showMenu = ref(false)
const menuPosition = ref({ x: 0, y: 0 })

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
  { id: 'profile', name: '用户画像', sub: 'AI眼中的你', icon: Globe, color: '#8b5cf6', desc: '展示AI理解的用户身份、偏好和目标' },
  { id: 'facts', name: '记忆事实', sub: '结构化知识', icon: BookOpen, color: '#22c55e', desc: '按类别存储的事实信息，支持搜索和管理' },
  { id: 'knowledge', name: '知识记忆', sub: '学到的知识', icon: FileText, color: '#0ea5e9', desc: '从对话中提取的可复用知识点' },
  { id: 'history', name: '对话历史', sub: '每日记录', icon: Calendar, color: '#f59e0b', desc: '按日期分组的对话摘要' },
])

const activeTab = ref('profile')

const isEditingKnowledge = ref(false)
const editKnowledgeContent = ref('')
const knowledgeSavedContent = ref('')
const knowledgeHasChanges = computed(() => editKnowledgeContent.value !== knowledgeSavedContent.value)

const isEditingSummary = ref(false)
const editSummaryContent = ref('')
const summarySavedContent = ref('')
const summaryHasChanges = computed(() => editSummaryContent.value !== summarySavedContent.value)

const selectedDailyDate = ref('')
const selectedConversationId = ref<string | null>(null)
const newDailyContent = ref('')
const isAddingDaily = ref(false)

const showAddFact = ref(false)
const newFactContent = ref('')
const newFactCategory = ref<FactCategory>('context')

const editingFactId = ref<string | null>(null)
const editFactContent = ref('')
const editFactCategory = ref<FactCategory>('context')

const searchQuery = ref('')
const filterCategory = ref<string>('all')

const profile = computed(() => memoryStore.profile)
const hasProfile = computed(() => !!profile.value.name)

const filteredFacts = computed(() => {
  let result = memoryStore.facts
  if (filterCategory.value !== 'all') {
    result = result.filter(f => f.category === filterCategory.value)
  }
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(f => f.content.toLowerCase().includes(query))
  }
  return result
})

const factsByCategory = computed(() => {
  const groups: Record<string, FactItem[]> = {}
  for (const cat of FACT_CATEGORIES) {
    groups[cat] = filteredFacts.value.filter(f => f.category === cat)
  }
  return groups
})

const factCount = computed(() => memoryStore.facts.length)
const filteredFactCount = computed(() => filteredFacts.value.length)

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
  return content.split('\n').filter((l: string) => {
    const trimmed = l.trim()
    if (!trimmed) return false
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return false
    if (/^#\s*\d{4}-\d{2}-\d{2}$/.test(trimmed)) return false
    return true
  })
})

const memoryStats = computed(() => {
  const facts = memoryStore.facts
  const categories = FACT_CATEGORIES.map(cat => ({
    name: CATEGORY_LABELS[cat],
    count: facts.filter(f => f.category === cat).length,
    color: CATEGORY_COLORS[cat],
  }))
  return {
    totalFacts: facts.length,
    hasProfile: !!profile.value.name,
    dailyCount: memoryStore.dailies.length,
    hasKnowledge: knowledgeSectionCards.value.length > 0,
    hasSummary: hasSummary.value,
    categories,
  }
})

function switchTab(tabId: string) {
  activeTab.value = tabId
  if (tabId === 'knowledge' && !memoryStore.knowledgeContent) {
    memoryStore.fetchKnowledge(selectedAgentId.value)
  }
  if (tabId === 'history' && memoryStore.dailies.length === 0) {
    memoryStore.fetchDailies(selectedAgentId.value)
  }
  if (tabId === 'profile' && !memoryStore.summaryContent) {
    memoryStore.fetchSummary(selectedAgentId.value)
  }
}

function startAddFact() {
  showAddFact.value = true
  newFactContent.value = ''
  newFactCategory.value = 'context'
}

function cancelAddFact() {
  showAddFact.value = false
}

async function confirmAddFact() {
  if (!newFactContent.value.trim()) return
  await memoryStore.addFact({
    content: newFactContent.value.trim(),
    category: newFactCategory.value,
    confidence: 0.8,
  })
  showAddFact.value = false
  toast.success('事实已添加')
}

function startEditFact(fact: FactItem) {
  editingFactId.value = fact.id
  editFactContent.value = fact.content
  editFactCategory.value = fact.category as FactCategory
}

function cancelEditFact() {
  editingFactId.value = null
}

async function saveEditFact() {
  if (!editingFactId.value) return
  await memoryStore.updateFact(editingFactId.value, {
    content: editFactContent.value,
    category: editFactCategory.value,
  })
  editingFactId.value = null
  toast.success('事实已更新')
}

async function deleteFact(factId: string) {
  const confirmed = await confirmDeletion('删除事实', '确定要删除这条事实吗？')
  if (!confirmed) return
  await memoryStore.removeFact(factId)
  toast.success('事实已删除')
}

function formatExpiresAt(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  } catch {
    return iso
  }
}

function startEditKnowledge() {
  editKnowledgeContent.value = memoryStore.knowledgeContent
  knowledgeSavedContent.value = memoryStore.knowledgeContent
  isEditingKnowledge.value = true
}

function cancelEditKnowledge() {
  isEditingKnowledge.value = false
  editKnowledgeContent.value = ''
  knowledgeSavedContent.value = ''
}

async function saveEditKnowledge() {
  if (!editKnowledgeContent.value.trim() && editKnowledgeContent.value !== '') return
  isSaving.value = true
  try {
    await memoryStore.saveKnowledge(editKnowledgeContent.value)
    knowledgeSavedContent.value = editKnowledgeContent.value
    isEditingKnowledge.value = false
    editKnowledgeContent.value = ''
    toast.success('知识记忆已保存')
  } finally {
    isSaving.value = false
  }
}

function startEditSummary() {
  editSummaryContent.value = memoryStore.summaryContent
  summarySavedContent.value = memoryStore.summaryContent
  isEditingSummary.value = true
}

function cancelEditSummary() {
  isEditingSummary.value = false
  editSummaryContent.value = ''
  summarySavedContent.value = ''
}

async function saveEditSummary() {
  if (!editSummaryContent.value.trim() && editSummaryContent.value !== '') return
  isSaving.value = true
  try {
    await memoryStore.saveSummary(editSummaryContent.value)
    summarySavedContent.value = editSummaryContent.value
    isEditingSummary.value = false
    editSummaryContent.value = ''
    toast.success('AI总结已保存')
  } finally {
    isSaving.value = false
  }
}

async function selectDaily(date: string) {
  selectedDailyDate.value = date
  await memoryStore.fetchDaily(date, selectedAgentId.value, selectedConversationId.value)
}

async function handleAddDaily() {
  if (!newDailyContent.value.trim()) return
  isAddingDaily.value = true
  try {
    await memoryStore.appendDaily(newDailyContent.value.trim(), selectedDailyDate.value || undefined, selectedAgentId.value, selectedConversationId.value)
    newDailyContent.value = ''
    toast.success('记录已添加')
  } finally {
    isAddingDaily.value = false
  }
}

const isSaving = ref(false)
// 记忆系统仅对主 Agent 生效，固定为主 Agent ID
const selectedAgentId = ref<string | null>('luominest_main_agent')

async function switchConversation(convId: string | null) {
  selectedConversationId.value = convId
  selectedDailyDate.value = ''
  await memoryStore.fetchDailies(selectedAgentId.value, convId)
  if (memoryStore.dailies.length > 0) {
    selectedDailyDate.value = memoryStore.dailies[memoryStore.dailies.length - 1]
    await memoryStore.fetchDaily(selectedDailyDate.value, selectedAgentId.value, convId)
  }
}

async function loadData() {
  await Promise.all([
    memoryStore.fetchMemory(selectedAgentId.value),
    memoryStore.fetchKnowledge(selectedAgentId.value),
    memoryStore.fetchSummary(selectedAgentId.value),
    memoryStore.fetchDailies(selectedAgentId.value),
    memoryStore.fetchConversationDailies(selectedAgentId.value),
    memoryStore.fetchFacts(undefined, selectedAgentId.value),
  ])

  if (memoryStore.dailies.length > 0) {
    selectedDailyDate.value = memoryStore.dailies[memoryStore.dailies.length - 1]
    await memoryStore.fetchDaily(selectedDailyDate.value, selectedAgentId.value)
  }
}

const toggleMenu = (event: MouseEvent) => {
  event.stopPropagation()
  if (showMenu.value) {
    showMenu.value = false
  } else {
    const rect = (event.target as HTMLElement).getBoundingClientRect()
    const menuWidth = 240
    let menuX = rect.left
    if (menuX + menuWidth > window.innerWidth) {
      menuX = window.innerWidth - menuWidth - 16
    }
    menuPosition.value = { x: menuX, y: rect.bottom + 8 }
    showMenu.value = true
  }
}

const closeMenu = () => {
  showMenu.value = false
}

const openConfirm = (action: ConfirmAction) => {
  confirmAction.value = action
  confirmDanger.value = false
  
  switch (action) {
    case 'clearFacts':
      confirmTitle.value = '清空事实库'
      confirmMessage.value = `确定要清空该 Agent 的所有 ${factCount.value} 条事实吗？`
      confirmDanger.value = true
      break
    case 'clearKnowledge':
      confirmTitle.value = '清空知识记忆'
      confirmMessage.value = '确定要清空所有知识记忆吗？'
      confirmDanger.value = true
      break
    case 'clearDailies':
      confirmTitle.value = '清空对话历史'
      confirmMessage.value = `确定要清空所有 ${memoryStore.dailies.length} 天的对话记录吗？`
      confirmDanger.value = true
      break
    case 'clearSummary':
      confirmTitle.value = '重置AI总结'
      confirmMessage.value = '确定要重置所有AI总结吗？'
      confirmDanger.value = true
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

let cancelConfirm = () => {
  showConfirm.value = false
  confirmAction.value = null
}

let executeConfirm = async () => {
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
        toast.success('对话历史已清空')
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

async function confirmDeletion(title: string, message: string): Promise<boolean> {
  return new Promise(resolve => {
    confirmTitle.value = title
    confirmMessage.value = message
    confirmDanger.value = true
    showConfirm.value = true
    
    const handleConfirm = () => {
      showConfirm.value = false
      confirmAction.value = null
      resolve(true)
    }
    
    const handleCancel = () => {
      showConfirm.value = false
      confirmAction.value = null
      resolve(false)
    }
    
    const originalExecute = executeConfirm
    const originalCancel = cancelConfirm
    
    executeConfirm = async () => {
      executeConfirm = originalExecute
      cancelConfirm = originalCancel
      handleConfirm()
    }
    
    cancelConfirm = () => {
      executeConfirm = originalExecute
      cancelConfirm = originalCancel
      handleCancel()
    }
  })
}

function exportMemory() {
  const data = {
    profile: memoryStore.profile,
    facts: memoryStore.facts,
    knowledge: memoryStore.knowledgeContent,
    summary: memoryStore.summaryContent,
    dailies: memoryStore.dailies,
    exportedAt: new Date().toISOString(),
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `memory-backup-${new Date().toISOString().split('T')[0]}.json`
  a.click()
  URL.revokeObjectURL(url)
  toast.success('记忆数据已导出')
}

async function importMemory() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async (e) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file) return
    
    try {
      const text = await file.text()
      const data = JSON.parse(text)
      
      if (data.profile) {
        memoryStore.profile = data.profile
      }
      if (data.facts && Array.isArray(data.facts)) {
        for (const fact of data.facts) {
          await memoryStore.addFact({
            content: fact.content,
            category: fact.category || 'context',
            confidence: fact.confidence || 0.8,
          })
        }
      }
      if (data.knowledge) {
        await memoryStore.saveKnowledge(data.knowledge)
      }
      if (data.summary) {
        await memoryStore.saveSummary(data.summary)
      }
      
      await loadData()
      toast.success('记忆数据已导入')
    } catch (error) {
      toast.error('导入失败，请检查文件格式')
    }
  }
  input.click()
}

onMounted(() => {
  loadData()
})

onBeforeUnmount(() => {
  window.removeEventListener('click', closeMenu)
})

watch(activeTab, () => {
  if (activeTab.value === 'knowledge') {
    knowledgeSavedContent.value = memoryStore.knowledgeContent
  }
  if (activeTab.value === 'profile') {
    summarySavedContent.value = memoryStore.summaryContent
  }
})

window.addEventListener('click', closeMenu)
</script>

<template>
  <div class="memory-view">
    <div class="memory-header">
      <div class="header-left">
        <Brain :size="20" />
        <h2>记忆中枢</h2>
        <span class="header-badge">AI驱动的记忆系统</span>
      </div>
      <div class="header-actions">
        <button class="h-btn" @click="exportMemory" title="导出记忆">
          <Download :size="15" />
        </button>
        <button class="h-btn" @click="importMemory" title="导入记忆">
          <Upload :size="15" />
        </button>
        <button class="h-btn" @click="loadData">
          <RefreshCw :size="15" :class="{ spinning: memoryStore.loading }" />
        </button>
        <button class="h-btn" @click="toggleMenu">
          <MoreVertical :size="15" />
        </button>
      </div>
    </div>
    
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
        <Calendar :size="16" />
        <span>清空对话历史</span>
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
    
    <div v-if="showConfirm" class="confirm-overlay" @click="cancelConfirm">
      <div class="confirm-dialog" @click.stop>
        <div class="confirm-header">
          <AlertCircle v-if="confirmDanger" :size="24" class="danger-icon" />
          <h3>{{ confirmTitle }}</h3>
        </div>
        <div class="confirm-body">
          <p>{{ confirmMessage }}</p>
        </div>
        <div class="confirm-footer">
          <button class="h-btn" @click="cancelConfirm" :disabled="isProcessing">取消</button>
          <button 
            class="h-btn danger" 
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
      <div class="layer-nav">
        <div
          v-for="tab in layerTabs"
          :key="tab.id"
          :class="['nav-card', { active: activeTab === tab.id }]"
          :style="{ '--tab-color': tab.color }"
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
            <span v-if="tab.id === 'profile'" class="nav-stat">{{ hasSummary ? '已总结' : '未总结' }}</span>
            <span v-else-if="tab.id === 'facts'" class="nav-stat">{{ factCount }} 条</span>
            <span v-else-if="tab.id === 'knowledge'" class="nav-stat">{{ knowledgeSectionCards.length > 0 ? knowledgeSectionCards.length + ' 节' : '空' }}</span>
            <span v-else-if="tab.id === 'history'" class="nav-stat">{{ memoryStore.dailies.length }} 天</span>
          </div>
        </div>

        <div class="stats-overview">
          <div class="stats-header">
            <Activity :size="16" />
            <span>记忆概览</span>
          </div>
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-value">{{ memoryStats.totalFacts }}</span>
              <span class="stat-label">事实</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ memoryStats.dailyCount }}</span>
              <span class="stat-label">天数</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ knowledgeSectionCards.length }}</span>
              <span class="stat-label">知识</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ hasProfile ? '有' : '无' }}</span>
              <span class="stat-label">档案</span>
            </div>
          </div>
          <div class="category-bars">
            <div 
              v-for="cat in memoryStats.categories" 
              :key="cat.name"
              class="category-bar-item"
            >
              <span class="cat-name">{{ cat.name }}</span>
              <div class="cat-bar-wrap">
                <div 
                  class="cat-bar-fill" 
                  :style="{ width: `${(cat.count / Math.max(memoryStats.totalFacts, 1)) * 100}%`, background: cat.color }"
                ></div>
              </div>
              <span class="cat-count">{{ cat.count }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="memory-detail">
        <template v-if="activeTab === 'profile'">
          <div class="detail-header">
            <Globe :size="22" :style="{ color: '#8b5cf6' }" />
            <h3>用户画像</h3>
            <div class="detail-actions">
              <button v-if="!isEditingSummary" class="h-btn primary" @click="startEditSummary">
                <Edit3 :size="14" /> 编辑
              </button>
              <template v-else>
                <button class="h-btn" @click="cancelEditSummary"><X :size="14" /> 取消</button>
                <button class="h-btn primary" @click="saveEditSummary" :disabled="isSaving || !summaryHasChanges">
                  <Loader2 v-if="isSaving" :size="14" class="spinning" />
                  <Save v-else :size="14" /> 保存
                </button>
              </template>
            </div>
          </div>

          <div v-if="hasProfile" class="profile-card">
            <div class="profile-top">
              <div class="profile-avatar-lg">{{ profile.name?.[0] || '?' }}</div>
              <div class="profile-info">
                <span class="profile-name">{{ profile.name || '未知用户' }}</span>
                <span class="profile-label">AI 记住的你</span>
              </div>
            </div>
            <div v-if="profile.static_facts && profile.static_facts.length > 0" class="profile-section">
              <div class="profile-section-label">稳定偏好</div>
              <div class="profile-tags">
                <span v-for="(fact, idx) in profile.static_facts" :key="idx" class="profile-tag static">{{ fact }}</span>
              </div>
            </div>
            <div v-if="profile.dynamic_context && profile.dynamic_context.length > 0" class="profile-section">
              <div class="profile-section-label">当前状态</div>
              <div class="profile-tags">
                <span v-for="(ctx, idx) in profile.dynamic_context" :key="idx" class="profile-tag dynamic">{{ ctx }}</span>
              </div>
            </div>
          </div>

          <div v-if="isEditingSummary" class="editor-section">
            <textarea v-model="editSummaryContent" class="memory-editor" placeholder="编辑 AI 总结内容..."></textarea>
            <div class="editor-hint">支持 Markdown 格式，使用 ## 作为段落标题</div>
          </div>
          <template v-else>
            <div
              v-for="sectionName in summarySectionNames"
              :key="sectionName"
              class="distilled-section-card"
              :style="{ '--section-color': summarySectionColors[sectionName] }"
            >
              <div class="distilled-section-header">
                <div class="section-dot" :style="{ background: summarySectionColors[sectionName] }"></div>
                <span class="section-title-text">{{ sectionName }}</span>
              </div>
              <div class="distilled-section-body">
                <template v-if="memoryStore.summarySections[sectionName] && memoryStore.summarySections[sectionName].trim()">
                  <p v-for="(line, idx) in memoryStore.summarySections[sectionName].split('\n').filter((l: string) => l.trim())" :key="idx" class="distilled-line">{{ line.replace(/^-\s*/, '') }}</p>
                </template>
                <template v-else>
                  <p class="empty-hint">暂无内容</p>
                </template>
              </div>
            </div>
            <div v-if="!hasSummary" class="empty-section summary-empty">
              <Sparkles :size="28" />
              <p>AI 还不了解你</p>
              <p class="empty-hint">与 Agent 对话后，AI 会自动总结你的信息</p>
            </div>
          </template>
        </template>

        <template v-if="activeTab === 'facts'">
          <div class="detail-header">
            <BookOpen :size="22" :style="{ color: '#22c55e' }" />
            <h3>记忆事实</h3>
            <div class="detail-actions">
              <button class="h-btn primary" @click="startAddFact">
                <Plus :size="14" /> 添加事实
              </button>
            </div>
          </div>

          <div class="facts-search-bar">
            <div class="search-input-wrap">
              <Search :size="14" />
              <input v-model="searchQuery" type="text" placeholder="搜索事实..." class="facts-search-input" />
            </div>
            <div class="filter-dropdown">
              <button class="filter-btn" @click="filterCategory = filterCategory === 'all' ? '' : 'all'">
                <Filter :size="14" />
                <span>{{ filterCategory === 'all' ? '全部分类' : CATEGORY_LABELS[filterCategory] || '筛选' }}</span>
                <ChevronDown :size="14" />
              </button>
              <div v-if="filterCategory !== 'all'" class="filter-options">
                <button 
                  v-for="cat in FACT_CATEGORIES" 
                  :key="cat"
                  class="filter-option"
                  :class="{ active: filterCategory === cat }"
                  @click="filterCategory = filterCategory === cat ? 'all' : cat"
                >
                  <Check v-if="filterCategory === cat" :size="12" />
                  {{ CATEGORY_LABELS[cat] }}
                </button>
              </div>
            </div>
          </div>

          <div v-if="showAddFact" class="add-fact-form">
            <div class="add-fact-row">
              <input v-model="newFactContent" type="text" placeholder="输入事实内容..." class="add-fact-input" />
              <select v-model="newFactCategory" class="add-fact-select">
                <option v-for="cat in FACT_CATEGORIES" :key="cat" :value="cat">{{ CATEGORY_LABELS[cat] }}</option>
              </select>
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

          <div v-else-if="filteredFactCount === 0" class="empty-section">
            <Search :size="28" />
            <p>没有找到匹配的事实</p>
            <p class="empty-hint">尝试调整搜索关键词或筛选条件</p>
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
                        <button class="h-btn primary" @click="saveEditFact" :disabled="memoryStore.saving">
                          <Save :size="13" />
                        </button>
                        <button class="h-btn" @click="cancelEditFact"><X :size="13" /></button>
                      </div>
                    </template>
                    <template v-else>
                      <div class="fact-main">
                        <span class="fact-text" :class="{ 'fact-deprecated': !fact.is_latest }">{{ fact.content }}</span>
                        <span v-if="!fact.is_latest" class="fact-badge deprecated">已替代</span>
                        <span v-if="fact.expires_at" class="fact-badge expires">过期: {{ formatExpiresAt(fact.expires_at) }}</span>
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
            <FileText :size="22" :style="{ color: '#0ea5e9' }" />
            <h3>知识记忆</h3>
            <div class="detail-actions">
              <button v-if="!isEditingKnowledge" class="h-btn primary" @click="startEditKnowledge">
                <Edit3 :size="14" /> 编辑
              </button>
              <template v-else>
                <button class="h-btn" @click="cancelEditKnowledge"><X :size="14" /> 取消</button>
                <button class="h-btn primary" @click="saveEditKnowledge" :disabled="isSaving || !knowledgeHasChanges">
                  <Loader2 v-if="isSaving" :size="14" class="spinning" />
                  <Save v-else :size="14" /> 保存
                </button>
              </template>
            </div>
          </div>

          <div v-if="isEditingKnowledge" class="editor-section">
            <textarea v-model="editKnowledgeContent" class="memory-editor" placeholder="编辑知识记忆..."></textarea>
            <div class="editor-hint">使用 ## 标题创建知识章节，- 开头添加知识点</div>
          </div>
          <div v-else class="markdown-preview">
            <div v-if="knowledgeSectionCards.length === 0" class="empty-section">
              <BookOpen :size="28" />
              <p>暂无知识记忆</p>
              <p class="empty-hint">对话中AI会自动提取并存储知识信息</p>
            </div>
            <template v-else>
              <div v-for="(section, idx) in knowledgeSectionCards" :key="idx" class="memory-section-card" :style="{ '--ms-color': '#0ea5e9' }">
                <div class="ms-header">
                  <div class="ms-dot"></div>
                  <span class="ms-label">{{ section.title }}</span>
                  <span class="ms-count">{{ section.content.split('\n').filter((l: string) => l.trim()).length }} 条</span>
                </div>
                <div class="ms-body">
                  <p v-for="(line, lidx) in section.content.split('\n').filter((l: string) => l.trim())" :key="lidx" class="ms-line">{{ line.replace(/^-\s*/, '') }}</p>
                </div>
              </div>
            </template>
          </div>
        </template>

        <template v-if="activeTab === 'history'">
          <div class="detail-header">
            <Calendar :size="22" :style="{ color: '#f59e0b' }" />
            <h3>对话历史</h3>
          </div>

          <!-- 对话筛选 -->
          <div v-if="memoryStore.conversationDailies.length > 0" class="conversation-filter">
            <label class="filter-label">按对话筛选</label>
            <select
              v-model="selectedConversationId"
              class="conversation-select"
              @change="switchConversation(selectedConversationId)"
            >
              <option :value="null">全部对话</option>
              <option v-for="conv in memoryStore.conversationDailies" :key="conv.id" :value="conv.id">
                {{ conv.title || (conv.id.length > 12 ? conv.id.slice(0, 8) + '...' : conv.id) }}
              </option>
            </select>
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
                  <span class="daily-count">{{ getDailyCount(date) }}</span>
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
                  <span class="daily-weekday">{{ getWeekday(selectedDailyDate) }}</span>
                </div>
                <div v-if="dailyLines.length === 0" class="empty-section small">
                  <Archive :size="20" />
                  <p>当天无记录</p>
                </div>
                <div v-else class="memo-items">
                  <div v-for="(line, idx) in dailyLines" :key="idx" class="memo-item">
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

      </div>
    </div>
  </div>
</template>

<script lang="ts">
function getDailyCount(_date: string): number {
  return 0
}

function getWeekday(dateStr: string): string {
  const date = new Date(dateStr)
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return weekdays[date.getDay()]
}
</script>

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

.dropdown-menu {
  position: fixed;
  z-index: 1000;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 0;
  box-shadow: var(--shadow-lg);
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
  color: var(--lumi-danger);
}

.menu-item.danger:hover {
  background: var(--lumi-danger-light);
}

.menu-divider {
  height: 1px;
  background: var(--border);
  margin: var(--space-1) 0;
}

.confirm-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--overlay-backdrop);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1001;
}

.confirm-dialog {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: var(--space-6);
  max-width: 400px;
  width: 90%;
  box-shadow: var(--shadow-xl);
}

.confirm-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12x
}

.danger-icon {
  color: var(--lumi-danger);
}

.confirm-header h3 {
  margin: 0;
  font-size: var(--text-2xl);
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
  gap: var(--space-2);
}

.h-btn.danger {
  background: var(--lumi-danger-light);
  border: 1px solid var(--lumi-danger-border);
  color: var(--lumi-danger);
}

.h-btn.danger:hover {
  background: var(--lumi-danger-light);
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
  padding: var(--space-4) var(--space-6);
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
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--text);
}

.header-badge {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  background: var(--task-purple-soft);
  color: var(--task-purple);
  font-weight: 500;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.h-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: var(--radius-xs);
  font-size: 13px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-slow);
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
  padding: var(--space-5);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  flex-shrink: 0;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stats-overview {
  padding: var(--space-3);
  border-radius: 12px;
  background: var(--bg);
  border: 1px solid var(--border);
}

.stats-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-bottom: 12x
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}

.stat-item {
  text-align: center;
  padding: var(--space-2);
  background: var(--surface);
  border-radius: var(--radius-xs);
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}

.stat-label {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.category-bars {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.category-bar-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.cat-name {
  font-size: 11px;
  color: var(--text-muted);
  width: 32px;
}

.cat-bar-wrap {
  flex: 1;
  height: 4px;
  background: var(--border);
  border-radius: var(--radius-xs);
  overflow: hidden;
}

.cat-bar-fill {
  height: 100%;
  border-radius: var(--radius-xs);
  transition: width var(--transition-slow);
}

.cat-count {
  font-size: 11px;
  color: var(--text-muted);
  width: 20px;
  text-align: right;
}

.nav-card {
  padding: var(--space-3);
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--bg);
  cursor: pointer;
  transition: all var(--transition-slow);
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
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-stats {
  font-size: 11px;
  color: var(--text-muted);
  font-family: monospace;
}

.nav-stat {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  background: var(--surface);
}

.memory-detail {
  flex: 1;
  min-height: 0;
  padding: var(--space-6);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.detail-header h3 {
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--text);
}

.detail-actions {
  margin-left: auto;
  display: flex;
  gap: var(--space-2);
}

.profile-card {
  padding: 16px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--task-purple-soft), var(--lumi-sky-soft));
  border: 1px solid var(--border);
}

.profile-top {
  display: flex;
  align-items: center;
  gap: 12px;
}

.profile-avatar-lg {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--lumi-accent-glow);
  color: var(--task-purple);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-2xl);
  font-weight: 700;
  flex-shrink: 0;
}

.profile-info { display: flex; flex-direction: column; }

.profile-name {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text);
}

.profile-label {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.profile-section {
  margin-top: var(--space-3);
}

.profile-section-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 6px;
  font-weight: 500;
}

.profile-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.profile-tag {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: var(--text-sm);
  font-weight: 500;
}

.profile-tag.static {
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.profile-tag.dynamic {
  background: var(--lumi-info-light);
  color: var(--lumi-info);
}

.editor-section { flex: 1; min-height: 300px; }

.memory-editor {
  width: 100%;
  min-height: 300px;
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

.editor-hint {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: var(--space-2);
  text-align: right;
}

.markdown-preview { flex: 1; }

.memory-section-card {
  padding: var(--space-3) var(--space-4);
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  margin-bottom: 10px;
  transition: all var(--transition-slow);
}

.memory-section-card:hover {
  border-color: var(--ms-color);
  box-shadow: 0 2px 12px color-mix(in srgb, var(--ms-color) 8%, transparent);
}

.ms-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
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
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: 1.6;
  margin-bottom: 3px;
}

.distilled-section-card {
  padding: var(--space-3);
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  transition: all var(--transition-slow);
}

.distilled-section-card:hover {
  border-color: var(--section-color);
  box-shadow: 0 2px 12px color-mix(in srgb, var(--section-color) 8%, transparent);
}

.distilled-section-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 10px;
}

.section-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.section-title-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.distilled-section-body {
  padding-left: 16px;
}

.distilled-line {
  font-size: var(--text-sm);
  color: var(--text);
  line-height: 1.6;
  margin-bottom: 2px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 12x
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

.empty-section.summary-empty {
  margin-top: 16px;
}

.facts-search-bar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  background: var(--surface);
}

.facts-search-input {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text);
  font-size: 13px;
  outline: none;
}

.filter-dropdown {
  position: relative;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  cursor: pointer;
}

.filter-options {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  padding: var(--space-1);
  min-width: 120px;
}

.filter-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
  border-radius: var(--radius-xs);
}

.filter-option:hover {
  background: var(--surface-hover);
}

.filter-option.active {
  background: var(--task-purple-soft);
}

.add-fact-form {
  padding: var(--space-3);
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--task-purple-border);
}

.add-fact-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.add-fact-input {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
  outline: none;
}

.add-fact-input:focus { border-color: var(--task-purple); }

.add-fact-select {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  background: var(--bg);
  color: var(--text);
  font-size: var(--text-sm);
  outline: none;
  min-width: 80px;
}

.facts-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
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
  gap: var(--space-2);
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
  border-radius: var(--radius-xs);
  background: var(--bg);
}

.fact-items {
  padding: 6px;
}

.fact-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: var(--radius-xs);
  transition: all 200ms;
}

.fact-item:hover {
  background: color-mix(in srgb, var(--fact-color) 4%, transparent);
}

.fact-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.fact-text {
  font-size: 13px;
  color: var(--text);
  line-height: 1.5;
}

.fact-error {
  font-size: var(--text-xs);
  color: var(--lumi-warning);
  opacity: 0.8;
}

.fact-deprecated {
  text-decoration: line-through;
  opacity: 0.5;
}

.fact-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: var(--radius-xs);
  font-size: var(--text-2xs);
  font-weight: 500;
}

.fact-badge.deprecated {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.fact-badge.expires {
  background: var(--lumi-warning-light);
  color: var(--lumi-warning);
}

.fact-actions {
  display: flex;
  gap: 4px;
}

.fact-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-xs);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms;
}

.fact-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.fact-btn.danger:hover {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.fact-edit-row {
  display: flex;
  gap: 6px;
  align-items: center;
  flex: 1;
}

.daily-layout {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.conversation-filter {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 12x
  padding: 0 var(--space-1);
}

.filter-label {
  font-size: var(--text-sm);
  color: var(--text-muted);
  white-space: nowrap;
}

.conversation-select {
  flex: 1;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-xs);
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: var(--input-border);
  font-size: var(--text-sm);
  outline: none;
  cursor: pointer;
}

.conversation-select:focus {
  border-color: var(--lumi-primary);
}

.daily-sidebar {
  width: 180px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
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
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-xs);
  font-size: var(--text-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms;
}

.daily-date-item:hover { background: var(--surface-hover); color: var(--text); }
.daily-date-item.active { background: var(--lumi-sky-soft); color: var(--lumi-sky); font-weight: 600; }

.daily-count {
  font-size: var(--text-2xs);
  padding: 1px 5px;
  border-radius: var(--radius-xs);
  background: var(--border);
  margin-left: auto;
}

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
  gap: var(--space-2);
}

.daily-date-label {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text);
}

.daily-weekday {
  font-size: var(--text-sm);
  color: var(--text-muted);
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
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid transparent;
  transition: all var(--transition-slow);
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

.add-daily-section {
  margin-top: var(--space-3);
}

.add-daily-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.add-daily-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  outline: none;
}

.add-daily-input:focus { border-color: var(--lumi-amber); }

@media (max-width: 768px) {
  .memory-header {
    padding: 12px 16px;
    flex-wrap: wrap;
    gap: 12px;
  }
  
  .header-left {
    order: 1;
    width: 100%;
  }
  
  .header-actions {
    order: 2;
    width: 100%;
    justify-content: flex-end;
  }
  
  .layer-nav {
    width: 100%;
    padding: 16px;
    border-right: none;
    border-bottom: 1px solid var(--border);
    overflow-y: visible;
    flex-wrap: wrap;
    flex-direction: row;
  }
  
  .stats-overview {
    width: 100%;
  }
  
  .nav-card {
    width: calc(50% - 8px);
    min-width: 140px;
  }
  
  .memory-body {
    flex-direction: column;
  }
  
  .memory-detail {
    padding: 16px;
  }
  
  .daily-layout {
    flex-direction: column;
  }
  
  .daily-sidebar {
    width: 100%;
  }
  
  .daily-dates {
    flex-direction: row;
    flex-wrap: wrap;
    max-height: none;
    gap: 6px;
  }
  
  .daily-date-item {
    width: calc(33.33% - 4px);
    min-width: 100px;
    justify-content: center;
  }
  
  .facts-search-bar {
    flex-direction: column;
  }
  
  .search-input-wrap {
    width: 100%;
  }
  
  .filter-dropdown {
    align-self: flex-start;
  }
  
  .add-fact-row {
    flex-wrap: wrap;
  }
  
  .add-fact-input {
    width: 100%;
  }
  
  .add-fact-select {
    flex: 1;
  }
  
  .fact-item {
    flex-wrap: wrap;
  }
  
  .fact-actions {
    margin-top: var(--space-2);
  }
  
  .confirm-dialog {
    padding: 16px;
  }
}
</style>