<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import {
  Brain,
  RefreshCw,
  Loader2,
  MoreVertical,
  Eraser,
  Trash2,
  BookOpen,
  FileText,
  Calendar,
  Sparkles,
  Download,
  Upload,
} from 'lucide-vue-next'
import { useMemoryStore, CATEGORY_LABELS, CATEGORY_COLORS, FACT_CATEGORIES } from '../stores/memory'
import type { FactItem, FactCategory } from '../stores/memory'
import { useToast } from '../composables/useToast'
import MemoryConfirmDialog from '../components/memory/MemoryConfirmDialog.vue'
import MemoryLayerNav from '../components/memory/MemoryLayerNav.vue'
import MemoryProfileTab from '../components/memory/MemoryProfileTab.vue'
import MemoryFactsTab from '../components/memory/MemoryFactsTab.vue'
import MemoryKnowledgeTab from '../components/memory/MemoryKnowledgeTab.vue'
import MemoryHistoryTab from '../components/memory/MemoryHistoryTab.vue'
import type { ConfirmAction, LayerTab } from '../components/memory/types'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('Memory')

const memoryStore = useMemoryStore()
const toast = useToast()

const showMenu = ref(false)
const menuPosition = ref({ x: 0, y: 0 })

const showConfirm = ref(false)
const confirmAction = ref<ConfirmAction | null>(null)
const confirmTitle = ref('')
const confirmMessage = ref('')
const confirmDanger = ref(false)
const isProcessing = ref(false)

const layerTabs = ref<LayerTab[]>([
  { id: 'profile', name: '用户画像', sub: 'AI眼中的你', icon: Brain, color: 'var(--task-purple)', desc: '展示AI理解的用户身份、偏好和目标' },
  { id: 'facts', name: '记忆事实', sub: '结构化知识', icon: BookOpen, color: 'var(--lumi-success)', desc: '按类别存储的事实信息，支持搜索和管理' },
  { id: 'knowledge', name: '知识记忆', sub: '学到的知识', icon: FileText, color: 'var(--lumi-sky)', desc: '从对话中提取的可复用知识点' },
  { id: 'history', name: '对话历史', sub: '每日记录', icon: Calendar, color: 'var(--lumi-amber)', desc: '按日期分组的对话摘要' },
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
  '用户画像': 'var(--task-purple)',
  '偏好设置': 'var(--lumi-amber)',
  '兴趣目标': 'var(--lumi-success)',
  '近期状态': 'var(--lumi-sky)',
  '事件时间线': 'var(--lumi-sky)',
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
    logger.error('操作失败:', error)
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

    <MemoryConfirmDialog
      :show="showConfirm"
      :title="confirmTitle"
      :message="confirmMessage"
      :danger="confirmDanger"
      :is-processing="isProcessing"
      @cancel="cancelConfirm"
      @confirm="executeConfirm"
    />

    <div v-if="memoryStore.loading && !profile.name && memoryStore.facts.length === 0" class="memory-loading">
      <Loader2 :size="24" class="spinning" />
      <span>加载记忆数据...</span>
    </div>

    <div v-else class="memory-body">
      <MemoryLayerNav
        :layer-tabs="layerTabs"
        :active-tab="activeTab"
        :has-summary="hasSummary"
        :fact-count="factCount"
        :knowledge-section-count="knowledgeSectionCards.length"
        :daily-count="memoryStore.dailies.length"
        :memory-stats="memoryStats"
        @switch-tab="switchTab"
      />

      <div class="memory-detail">
        <MemoryProfileTab
          v-if="activeTab === 'profile'"
          :profile="profile"
          :has-profile="hasProfile"
          :is-editing-summary="isEditingSummary"
          v-model:edit-summary-content="editSummaryContent"
          :is-saving="isSaving"
          :summary-has-changes="summaryHasChanges"
          :summary-section-names="summarySectionNames"
          :summary-section-colors="summarySectionColors"
          :has-summary="hasSummary"
          :summary-sections="memoryStore.summarySections"
          @start-edit-summary="startEditSummary"
          @cancel-edit-summary="cancelEditSummary"
          @save-edit-summary="saveEditSummary"
        />

        <MemoryFactsTab
          v-if="activeTab === 'facts'"
          :fact-count="factCount"
          :filtered-fact-count="filteredFactCount"
          :facts-by-category="factsByCategory"
          :show-add-fact="showAddFact"
          v-model:new-fact-content="newFactContent"
          v-model:new-fact-category="newFactCategory"
          :editing-fact-id="editingFactId"
          v-model:edit-fact-content="editFactContent"
          v-model:edit-fact-category="editFactCategory"
          v-model:search-query="searchQuery"
          v-model:filter-category="filterCategory"
          :saving="memoryStore.saving"
          @start-add-fact="startAddFact"
          @cancel-add-fact="cancelAddFact"
          @confirm-add-fact="confirmAddFact"
          @start-edit-fact="startEditFact"
          @cancel-edit-fact="cancelEditFact"
          @save-edit-fact="saveEditFact"
          @delete-fact="deleteFact"
        />

        <MemoryKnowledgeTab
          v-if="activeTab === 'knowledge'"
          :is-editing-knowledge="isEditingKnowledge"
          v-model:edit-knowledge-content="editKnowledgeContent"
          :is-saving="isSaving"
          :knowledge-has-changes="knowledgeHasChanges"
          :knowledge-section-cards="knowledgeSectionCards"
          @start-edit-knowledge="startEditKnowledge"
          @cancel-edit-knowledge="cancelEditKnowledge"
          @save-edit-knowledge="saveEditKnowledge"
        />

        <MemoryHistoryTab
          v-if="activeTab === 'history'"
          :conversation-dailies="memoryStore.conversationDailies"
          :dailies="memoryStore.dailies"
          :selected-daily-date="selectedDailyDate"
          v-model:selected-conversation-id="selectedConversationId"
          :daily-lines="dailyLines"
          v-model:new-daily-content="newDailyContent"
          :is-adding-daily="isAddingDaily"
          @select-daily="selectDaily"
          @switch-conversation="switchConversation"
          @handle-add-daily="handleAddDaily"
        />
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

.dropdown-menu {
  position: fixed;
  z-index: 1000;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: var(--space-2) 0;
  box-shadow: var(--shadow-lg);
  min-width: 200px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px var(--space-4);
  cursor: pointer;
  transition: background 0.2s;
  font-size: var(--text-md);
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

.memory-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  flex: 1;
  color: var(--text-muted);
  font-size: var(--text-md);
}

.spinning { animation: spin 1s linear infinite; }

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
  font-size: var(--text-xs);
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
  font-size: var(--text-base);
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

.memory-detail {
  flex: 1;
  min-height: 0;
  padding: var(--space-6);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

@media (max-width: 768px) {
  .memory-header {
    padding: var(--space-3) var(--space-4);
    flex-wrap: wrap;
    gap: var(--space-3);
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

  .memory-body {
    flex-direction: column;
  }

  .memory-detail {
    padding: var(--space-4);
  }
}
</style>
