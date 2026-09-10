<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
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
import { useMemoryStore, categoryLabel, CATEGORY_COLORS, FACT_CATEGORIES } from '../stores/memory'
import type { FactItem, FactCategory } from '../stores/memory'
import { useToast } from '../composables/useToast'
import LumiButton from '../components/common/LumiButton.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
import MemoryLayerNav from '../components/memory/MemoryLayerNav.vue'
import MemoryProfileTab from '../components/memory/MemoryProfileTab.vue'
import MemoryFactsTab from '../components/memory/MemoryFactsTab.vue'
import MemoryKnowledgeTab from '../components/memory/MemoryKnowledgeTab.vue'
import MemoryHistoryTab from '../components/memory/MemoryHistoryTab.vue'
import type { ConfirmAction, LayerTab } from '../components/memory/types'
import { createLuomiNestRendererLogger } from '../utils/logger'
import { MAIN_AGENT_ID } from '../constants'

const logger = createLuomiNestRendererLogger('Memory')

const memoryStore = useMemoryStore()
const toast = useToast()
const { t } = useI18n()

const showMenu = ref(false)
const menuPosition = ref({ x: 0, y: 0 })

const showConfirm = ref(false)
const confirmAction = ref<ConfirmAction | null>(null)
const confirmTitle = ref('')
const confirmMessage = ref('')
const confirmDanger = ref(false)
const isProcessing = ref(false)

const layerTabs = computed<LayerTab[]>(() => [
  { id: 'profile', name: t('memory.layer.profile.name'), sub: t('memory.layer.profile.sub'), icon: Brain, color: 'var(--task-sky)', desc: t('memory.layer.profile.desc') },
  { id: 'facts', name: t('memory.layer.facts.name'), sub: t('memory.layer.facts.sub'), icon: BookOpen, color: 'var(--lumi-success)', desc: t('memory.layer.facts.desc') },
  { id: 'knowledge', name: t('memory.layer.knowledge.name'), sub: t('memory.layer.knowledge.sub'), icon: FileText, color: 'var(--lumi-sky)', desc: t('memory.layer.knowledge.desc') },
  { id: 'history', name: t('memory.layer.history.name'), sub: t('memory.layer.history.sub'), icon: Calendar, color: 'var(--lumi-amber)', desc: t('memory.layer.history.desc') },
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
  '用户画像': 'var(--task-sky)',
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
    name: categoryLabel(cat),
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
  toast.success(t('memory.toast.factAdded'))
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
  toast.success(t('memory.toast.factUpdated'))
}

async function deleteFact(factId: string) {
  const confirmed = await confirmDeletion(t('memory.confirm.deleteFactTitle'), t('memory.confirm.deleteFactMessage'))
  if (!confirmed) return
  await memoryStore.removeFact(factId)
  toast.success(t('memory.toast.factDeleted'))
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
    toast.success(t('memory.toast.knowledgeSaved'))
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
    toast.success(t('memory.toast.summarySaved'))
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
    toast.success(t('memory.toast.recordAdded'))
  } finally {
    isAddingDaily.value = false
  }
}

const isSaving = ref(false)
const selectedAgentId = ref<string | null>(MAIN_AGENT_ID)

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
      confirmTitle.value = t('memory.confirm.clearFactsTitle')
      confirmMessage.value = t('memory.confirm.clearFactsMessage', { n: factCount.value })
      confirmDanger.value = true
      break
    case 'clearKnowledge':
      confirmTitle.value = t('memory.confirm.clearKnowledgeTitle')
      confirmMessage.value = t('memory.confirm.clearKnowledgeMessage')
      confirmDanger.value = true
      break
    case 'clearDailies':
      confirmTitle.value = t('memory.confirm.clearDailiesTitle')
      confirmMessage.value = t('memory.confirm.clearDailiesMessage', { n: memoryStore.dailies.length })
      confirmDanger.value = true
      break
    case 'clearSummary':
      confirmTitle.value = t('memory.confirm.clearSummaryTitle')
      confirmMessage.value = t('memory.confirm.clearSummaryMessage')
      confirmDanger.value = true
      break
    case 'resetAll':
      confirmTitle.value = t('memory.confirm.resetAllTitle')
      confirmMessage.value = t('memory.confirm.resetAllMessage')
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
        toast.success(t('memory.toast.factsCleared'))
        break
      case 'clearKnowledge':
        await memoryStore.clearKnowledge(selectedAgentId.value)
        toast.success(t('memory.toast.knowledgeCleared'))
        break
      case 'clearDailies':
        await memoryStore.clearDailies(selectedAgentId.value)
        selectedDailyDate.value = ''
        toast.success(t('memory.toast.historyCleared'))
        break
      case 'clearSummary':
        await memoryStore.clearSummary(selectedAgentId.value)
        toast.success(t('memory.toast.summaryReset'))
        break
      case 'resetAll':
        await memoryStore.resetAll(selectedAgentId.value)
        toast.success(t('memory.toast.allReset'))
        break
    }
    showConfirm.value = false
    confirmAction.value = null
  } catch (error) {
    logger.error('操作失败:', error)
    toast.error(t('memory.toast.operationFailed'))
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
  toast.success(t('memory.toast.exported'))
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
      toast.success(t('memory.toast.imported'))
    } catch (error) {
      toast.error(t('memory.toast.importFailed'))
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
    <div class="memory-header animate-fade-in">
      <div class="memory-header__left">
        <h1 class="memory-title">{{ t('memory.title') }}</h1>
        <p class="memory-desc">{{ t('memory.desc') }}</p>
      </div>
      <div class="memory-header__actions">
        <LumiButton variant="ghost" size="sm" icon-only @click="exportMemory" :title="t('memory.exportTitle')">
          <template #icon><Download :size="15" /></template>
        </LumiButton>
        <LumiButton variant="ghost" size="sm" icon-only @click="importMemory" :title="t('memory.importTitle')">
          <template #icon><Upload :size="15" /></template>
        </LumiButton>
        <LumiButton variant="ghost" size="sm" icon-only @click="loadData" :title="t('memory.refresh')">
          <template #icon><RefreshCw :size="15" :class="{ 'spin-animation': memoryStore.loading }" /></template>
        </LumiButton>
        <LumiButton variant="ghost" size="sm" icon-only @click="toggleMenu" :title="t('memory.more')">
          <template #icon><MoreVertical :size="15" /></template>
        </LumiButton>
      </div>
    </div>

    <div v-if="showMenu" class="dropdown-menu" :style="{ left: menuPosition.x + 'px', top: menuPosition.y + 'px' }">
      <div class="menu-item" @click="openConfirm('clearFacts')">
        <Trash2 :size="16" />
        <span>{{ t('memory.menu.clearFacts', { n: factCount }) }}</span>
      </div>
      <div class="menu-item" @click="openConfirm('clearKnowledge')">
        <BookOpen :size="16" />
        <span>{{ t('memory.menu.clearKnowledge') }}</span>
      </div>
      <div class="menu-item" @click="openConfirm('clearDailies')">
        <Calendar :size="16" />
        <span>{{ t('memory.menu.clearDailies') }}</span>
      </div>
      <div class="menu-item" @click="openConfirm('clearSummary')">
        <Sparkles :size="16" />
        <span>{{ t('memory.menu.clearSummary') }}</span>
      </div>
      <div class="menu-divider"></div>
      <div class="menu-item danger" @click="openConfirm('resetAll')">
        <Eraser :size="16" />
        <span>{{ t('memory.menu.resetAll') }}</span>
      </div>
    </div>

    <ConfirmDialog
      :visible="showConfirm"
      :title="confirmTitle"
      :message="confirmMessage"
      :danger="confirmDanger"
      :loading="isProcessing"
      @cancel="cancelConfirm"
      @confirm="executeConfirm"
    />

    <div v-if="memoryStore.loading && !profile.name && memoryStore.facts.length === 0" class="memory-loading">
      <Loader2 :size="24" class="spin-animation" />
      <span>{{ t('memory.loading') }}</span>
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


.memory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-6) var(--space-7) var(--space-4);
  flex-shrink: 0;
  background: linear-gradient(180deg, color-mix(in srgb, var(--lumi-brand) 3%, transparent) 0%, transparent 100%);
}

.memory-header__left {
  display: flex;
  flex-direction: column;
}

.memory-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  letter-spacing: -0.01em;
  line-height: 1.2;
}

.memory-desc {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.memory-header__actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.memory-body {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: var(--space-4);
  padding: var(--space-4);
  overflow: hidden;
}

.memory-detail {
  flex: 1;
  min-height: 0;
  padding: var(--space-4) var(--space-6);
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
