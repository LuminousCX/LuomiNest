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
  ChevronDown,
  Check,
  Bot,
  User,
  Users,
} from 'lucide-vue-next'
import { useMemoryStore, categoryLabel, CATEGORY_COLORS, FACT_CATEGORIES } from '../stores/memory'
import type { FactItem, FactCategory, MemoryAgent, MemoryTrackType } from '../stores/memory'
import { useToast } from '../composables/useToast'
import LumiButton from '../components/common/LumiButton.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
import SearchInput from '../components/common/SearchInput.vue'
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
    memoryStore.fetchKnowledge()
  }
  if (tabId === 'history' && memoryStore.dailies.length === 0) {
    memoryStore.fetchDailies()
  }
  if (tabId === 'profile' && !memoryStore.summaryContent) {
    memoryStore.fetchSummary()
  }
}

const newFactScope = ref<string>('global')
const editFactScope = ref<string>('global')

function startAddFact() {
  showAddFact.value = true
  newFactContent.value = ''
  newFactCategory.value = 'context'
  newFactScope.value = memoryStore.currentTrack === 'users' ? 'private' : memoryStore.currentTrack === 'groups' ? 'group' : 'global'
}

function cancelAddFact() {
  showAddFact.value = false
}

async function confirmAddFact() {
  if (!newFactContent.value.trim()) return
  await memoryStore.addFact({
    content: newFactContent.value.trim(),
    category: newFactCategory.value,
    scope: newFactScope.value || (memoryStore.currentTrack === 'users' ? 'private' : memoryStore.currentTrack === 'groups' ? 'group' : 'global'),
    confidence: 0.8,
  })
  showAddFact.value = false
  toast.success(t('memory.toast.factAdded'))
}

function startEditFact(fact: FactItem) {
  editingFactId.value = fact.id
  editFactContent.value = fact.content
  editFactCategory.value = fact.category as FactCategory
  editFactScope.value = fact.scope || (memoryStore.currentTrack === 'users' ? 'private' : memoryStore.currentTrack === 'groups' ? 'group' : 'global')
}

function cancelEditFact() {
  editingFactId.value = null
}

async function saveEditFact() {
  if (!editingFactId.value) return
  await memoryStore.updateFact(editingFactId.value, {
    content: editFactContent.value,
    category: editFactCategory.value,
    scope: editFactScope.value,
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
  await memoryStore.fetchDaily(date, selectedConversationId.value)
}

async function handleAddDaily() {
  if (!newDailyContent.value.trim()) return
  isAddingDaily.value = true
  try {
    await memoryStore.appendDaily(newDailyContent.value.trim(), selectedDailyDate.value || undefined, selectedConversationId.value)
    newDailyContent.value = ''
    toast.success(t('memory.toast.recordAdded'))
  } finally {
    isAddingDaily.value = false
  }
}

const isSaving = ref(false)
const selectedAgentId = ref<string | null>(MAIN_AGENT_ID)

// —— 记忆轨与主体切换 ——
const showAgentPicker = ref(false)
const agentPickerPosition = ref({ x: 0, y: 0 })

const showFanPicker = ref(false)
const fanPickerPosition = ref({ x: 0, y: 0 })
const fanSearchQuery = ref('')

const showGroupPicker = ref(false)
const groupPickerPosition = ref({ x: 0, y: 0 })
const groupSearchQuery = ref('')

const agents = computed<MemoryAgent[]>(() => memoryStore.memoryAgents)

const currentAgentName = computed(() => {
  if (!selectedAgentId.value) return t('memory.agentPicker.mainWorkspace')
  if (selectedAgentId.value === MAIN_AGENT_ID) return t('memory.agentPicker.mainWorkspace')
  const hit = agents.value.find(a => a.id === selectedAgentId.value)
  return hit?.name || selectedAgentId.value
})

const currentFanDisplayName = computed(() => {
  if (!memoryStore.currentUserKey) return t('memory.tracks.currentFan')
  const hit = memoryStore.memoryUsers.find(u => u.user_key === memoryStore.currentUserKey)
  if (hit) {
    return `${hit.name || hit.user_key} (${hit.platform.toUpperCase()})`
  }
  return memoryStore.currentUserKey
})

const currentGroupDisplayName = computed(() => {
  if (!memoryStore.currentGroupKey) return t('memory.tracks.currentGroup')
  const hit = memoryStore.memoryGroups.find(g => g.group_key === memoryStore.currentGroupKey)
  if (hit) {
    return `${hit.name || hit.group_key} (${hit.platform.toUpperCase()})`
  }
  return memoryStore.currentGroupKey
})

const filteredMemoryUsers = computed(() => {
  if (!fanSearchQuery.value.trim()) return memoryStore.memoryUsers
  const q = fanSearchQuery.value.toLowerCase()
  return memoryStore.memoryUsers.filter(u =>
    (u.name && u.name.toLowerCase().includes(q)) ||
    (u.user_key && u.user_key.toLowerCase().includes(q)) ||
    (u.platform && u.platform.toLowerCase().includes(q))
  )
})

const filteredMemoryGroups = computed(() => {
  if (!groupSearchQuery.value.trim()) return memoryStore.memoryGroups
  const q = groupSearchQuery.value.toLowerCase()
  return memoryStore.memoryGroups.filter(g =>
    (g.name && g.name.toLowerCase().includes(q)) ||
    (g.group_key && g.group_key.toLowerCase().includes(q)) ||
    (g.platform && g.platform.toLowerCase().includes(q))
  )
})

function toggleAgentPicker(event: MouseEvent) {
  event.stopPropagation()
  if (showAgentPicker.value) {
    showAgentPicker.value = false
    return
  }
  closeMenu()
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const menuWidth = 260
  let menuX = rect.left
  if (menuX + menuWidth > window.innerWidth) {
    menuX = window.innerWidth - menuWidth - 16
  }
  agentPickerPosition.value = { x: menuX, y: rect.bottom + 8 }
  showAgentPicker.value = true
}

function toggleFanPicker(event: MouseEvent) {
  event.stopPropagation()
  if (showFanPicker.value) {
    showFanPicker.value = false
    return
  }
  closeMenu()
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const menuWidth = 280
  let menuX = rect.left
  if (menuX + menuWidth > window.innerWidth) {
    menuX = window.innerWidth - menuWidth - 16
  }
  fanPickerPosition.value = { x: menuX, y: rect.bottom + 8 }
  showFanPicker.value = true
}

function toggleGroupPicker(event: MouseEvent) {
  event.stopPropagation()
  if (showGroupPicker.value) {
    showGroupPicker.value = false
    return
  }
  closeMenu()
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const menuWidth = 280
  let menuX = rect.left
  if (menuX + menuWidth > window.innerWidth) {
    menuX = window.innerWidth - menuWidth - 16
  }
  groupPickerPosition.value = { x: menuX, y: rect.bottom + 8 }
  showGroupPicker.value = true
}

async function handleSelectTrack(track: MemoryTrackType) {
  if (track === memoryStore.currentTrack) return
  closeMenu()
  if (track === 'owner') {
    await memoryStore.switchTrack('owner')
  } else if (track === 'users') {
    let target = memoryStore.currentUserKey
    if (!target && memoryStore.memoryUsers.length > 0) {
      target = memoryStore.memoryUsers[0].user_key
    }
    await memoryStore.switchTrack('users', target)
  } else if (track === 'groups') {
    let target = memoryStore.currentGroupKey
    if (!target && memoryStore.memoryGroups.length > 0) {
      target = memoryStore.memoryGroups[0].group_key
    }
    await memoryStore.switchTrack('groups', target)
  }
}

async function selectFan(userKey: string) {
  showFanPicker.value = false
  await memoryStore.switchTrack('users', userKey)
}

async function selectGroup(groupKey: string) {
  showGroupPicker.value = false
  await memoryStore.switchTrack('groups', groupKey)
}

async function selectAgent(agentId: string | null) {
  showAgentPicker.value = false
  selectedAgentId.value = agentId
  selectedConversationId.value = null
  selectedDailyDate.value = ''
  await memoryStore.switchAgent(agentId)
}

async function switchConversation(convId: string | null) {
  selectedConversationId.value = convId
  selectedDailyDate.value = ''
  await memoryStore.fetchDailies(convId)
  if (memoryStore.dailies.length > 0) {
    selectedDailyDate.value = memoryStore.dailies[memoryStore.dailies.length - 1]
    await memoryStore.fetchDaily(selectedDailyDate.value, convId)
  }
}

async function loadData() {
  await Promise.all([
    memoryStore.fetchMemory(selectedAgentId.value),
    memoryStore.fetchMemoryAgents(),
    memoryStore.fetchMemoryUsers(),
    memoryStore.fetchMemoryGroups(),
    memoryStore.fetchKnowledge(),
    memoryStore.fetchSummary(),
    memoryStore.fetchDailies(),
    memoryStore.fetchConversationDailies(),
    memoryStore.fetchFacts(),
  ])

  if (memoryStore.dailies.length > 0) {
    selectedDailyDate.value = memoryStore.dailies[memoryStore.dailies.length - 1]
    await memoryStore.fetchDaily(selectedDailyDate.value)
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
  showAgentPicker.value = false
  showFanPicker.value = false
  showGroupPicker.value = false
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
        await memoryStore.clearFacts()
        toast.success(t('memory.toast.factsCleared'))
        break
      case 'clearKnowledge':
        await memoryStore.clearKnowledge()
        toast.success(t('memory.toast.knowledgeCleared'))
        break
      case 'clearDailies':
        await memoryStore.clearDailies()
        selectedDailyDate.value = ''
        toast.success(t('memory.toast.historyCleared'))
        break
      case 'clearSummary':
        await memoryStore.clearSummary()
        toast.success(t('memory.toast.summaryReset'))
        break
      case 'resetAll':
        await memoryStore.resetAll()
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

        <!-- 3-Track switcher tabs: Owner / Users (Fans) / Groups -->
        <div class="memory-track-nav">
          <button
            class="track-tab-btn"
            :class="{ active: memoryStore.currentTrack === 'owner' }"
            @click="handleSelectTrack('owner')"
          >
            <Sparkles :size="14" />
            <span>{{ t('memory.tracks.owner') }}</span>
          </button>
          <button
            class="track-tab-btn"
            :class="{ active: memoryStore.currentTrack === 'users' }"
            @click="handleSelectTrack('users')"
          >
            <User :size="14" />
            <span>{{ t('memory.tracks.users') }}</span>
            <span v-if="memoryStore.memoryUsers.length > 0" class="track-badge">{{ memoryStore.memoryUsers.length }}</span>
          </button>
          <button
            class="track-tab-btn"
            :class="{ active: memoryStore.currentTrack === 'groups' }"
            @click="handleSelectTrack('groups')"
          >
            <Users :size="14" />
            <span>{{ t('memory.tracks.groups') }}</span>
            <span v-if="memoryStore.memoryGroups.length > 0" class="track-badge">{{ memoryStore.memoryGroups.length }}</span>
          </button>
        </div>

        <!-- Track entity selector triggers -->
        <div v-if="memoryStore.currentTrack === 'owner'" class="memory-agent-picker">
          <button class="agent-picker-trigger" @click="toggleAgentPicker">
            <Bot :size="15" />
            <span class="agent-picker-label">{{ t('memory.agentPicker.viewing') }}</span>
            <span class="agent-picker-current">{{ currentAgentName }}</span>
            <ChevronDown :size="15" class="agent-picker-caret" />
          </button>
        </div>

        <div v-else-if="memoryStore.currentTrack === 'users'" class="memory-agent-picker">
          <button class="agent-picker-trigger" @click="toggleFanPicker">
            <User :size="15" />
            <span class="agent-picker-label">{{ t('memory.tracks.currentFan') }}：</span>
            <span class="agent-picker-current">{{ currentFanDisplayName }}</span>
            <ChevronDown :size="15" class="agent-picker-caret" />
          </button>
        </div>

        <div v-else-if="memoryStore.currentTrack === 'groups'" class="memory-agent-picker">
          <button class="agent-picker-trigger" @click="toggleGroupPicker">
            <Users :size="15" />
            <span class="agent-picker-label">{{ t('memory.tracks.currentGroup') }}：</span>
            <span class="agent-picker-current">{{ currentGroupDisplayName }}</span>
            <ChevronDown :size="15" class="agent-picker-caret" />
          </button>
        </div>
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

    <!-- Quick pills bar for fans and groups -->
    <div v-if="memoryStore.currentTrack === 'users' && memoryStore.memoryUsers.length > 0" class="quick-pill-bar">
      <span class="pill-bar-label">快捷切换：</span>
      <button
        v-for="u in memoryStore.memoryUsers.slice(0, 8)"
        :key="u.user_key"
        class="quick-pill"
        :class="{ active: memoryStore.currentUserKey === u.user_key }"
        @click="selectFan(u.user_key)"
      >
        <span class="pill-platform">{{ u.platform }}</span>
        <span class="pill-name">{{ u.name || u.user_key }}</span>
        <span class="pill-count">({{ u.fact_count }})</span>
      </button>
    </div>

    <div v-if="memoryStore.currentTrack === 'groups' && memoryStore.memoryGroups.length > 0" class="quick-pill-bar">
      <span class="pill-bar-label">快捷切换：</span>
      <button
        v-for="g in memoryStore.memoryGroups.slice(0, 8)"
        :key="g.group_key"
        class="quick-pill"
        :class="{ active: memoryStore.currentGroupKey === g.group_key }"
        @click="selectGroup(g.group_key)"
      >
        <span class="pill-platform">{{ g.platform }}</span>
        <span class="pill-name">{{ g.name || g.group_key }}</span>
        <span class="pill-count">({{ g.fact_count }})</span>
      </button>
    </div>

    <!-- Agent dropdown -->
    <div v-if="showAgentPicker" class="dropdown-menu agent-picker-menu" :style="{ left: agentPickerPosition.x + 'px', top: agentPickerPosition.y + 'px' }" @click.stop>
      <div class="menu-item" :class="{ active: selectedAgentId === MAIN_AGENT_ID }" @click="selectAgent(MAIN_AGENT_ID)">
        <Bot :size="16" />
        <div class="agent-option">
          <span class="agent-option-name">{{ t('memory.agentPicker.mainWorkspace') }}</span>
          <span class="agent-option-sub">{{ t('memory.agentPicker.mainWorkspaceSub') }}</span>
        </div>
        <Check v-if="selectedAgentId === MAIN_AGENT_ID" :size="16" class="agent-check" />
      </div>
      <div class="menu-divider"></div>
      <template v-if="agents.length > 0">
        <div
          v-for="agent in agents"
          :key="agent.id"
          class="menu-item"
          :class="{ active: selectedAgentId === agent.id }"
          @click="selectAgent(agent.id)"
        >
          <Bot :size="16" />
          <div class="agent-option">
            <span class="agent-option-name">{{ agent.name }}</span>
            <span class="agent-option-sub">{{ t('memory.agentPicker.factCount', { n: agent.fact_count ?? 0 }) }}</span>
          </div>
          <Check v-if="selectedAgentId === agent.id" :size="16" class="agent-check" />
        </div>
      </template>
      <div v-else class="agent-picker-empty">{{ t('memory.agentPicker.noSubAgents') }}</div>
    </div>

    <!-- Fan dropdown -->
    <div v-if="showFanPicker" class="dropdown-menu agent-picker-menu" :style="{ left: fanPickerPosition.x + 'px', top: fanPickerPosition.y + 'px' }" @click.stop>
      <div class="picker-search-wrap">
        <SearchInput
          :model-value="fanSearchQuery"
          :placeholder="t('memory.tracks.searchFans')"
          @update:model-value="(v) => fanSearchQuery = String(v ?? '')"
        />
      </div>
      <div v-if="filteredMemoryUsers.length > 0" class="picker-list">
        <div
          v-for="u in filteredMemoryUsers"
          :key="u.user_key"
          class="menu-item"
          :class="{ active: memoryStore.currentUserKey === u.user_key }"
          @click="selectFan(u.user_key)"
        >
          <User :size="16" />
          <div class="agent-option">
            <span class="agent-option-name">{{ u.name || u.user_key }}</span>
            <span class="agent-option-sub">[{{ u.platform.toUpperCase() }}] · {{ t('memory.agentPicker.factCount', { n: u.fact_count }) }}</span>
          </div>
          <Check v-if="memoryStore.currentUserKey === u.user_key" :size="16" class="agent-check" />
        </div>
      </div>
      <div v-else class="agent-picker-empty">{{ t('memory.tracks.noUsers') }}</div>
    </div>

    <!-- Group dropdown -->
    <div v-if="showGroupPicker" class="dropdown-menu agent-picker-menu" :style="{ left: groupPickerPosition.x + 'px', top: groupPickerPosition.y + 'px' }" @click.stop>
      <div class="picker-search-wrap">
        <SearchInput
          :model-value="groupSearchQuery"
          :placeholder="t('memory.tracks.searchGroups')"
          @update:model-value="(v) => groupSearchQuery = String(v ?? '')"
        />
      </div>
      <div v-if="filteredMemoryGroups.length > 0" class="picker-list">
        <div
          v-for="g in filteredMemoryGroups"
          :key="g.group_key"
          class="menu-item"
          :class="{ active: memoryStore.currentGroupKey === g.group_key }"
          @click="selectGroup(g.group_key)"
        >
          <Users :size="16" />
          <div class="agent-option">
            <span class="agent-option-name">{{ g.name || g.group_key }}</span>
            <span class="agent-option-sub">[{{ g.platform.toUpperCase() }}] · {{ t('memory.agentPicker.factCount', { n: g.fact_count }) }}</span>
          </div>
          <Check v-if="memoryStore.currentGroupKey === g.group_key" :size="16" class="agent-check" />
        </div>
      </div>
      <div v-else class="agent-picker-empty">{{ t('memory.tracks.noGroups') }}</div>
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
          v-model:new-fact-scope="newFactScope"
          :editing-fact-id="editingFactId"
          v-model:edit-fact-content="editFactContent"
          v-model:edit-fact-category="editFactCategory"
          v-model:edit-fact-scope="editFactScope"
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
          @toggle-pin="(fact: FactItem) => memoryStore.toggleFactPin(fact.id, !fact.pinned)"
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

.memory-track-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 3px;
  margin-top: var(--space-3);
  width: fit-content;
}

.track-tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all 0.2s ease;
}

.track-tab-btn:hover {
  color: var(--text);
  background: var(--surface-hover);
}

.track-tab-btn.active {
  background: var(--lumi-brand);
  color: #fff;
  font-weight: var(--font-semibold);
  box-shadow: 0 2px 6px color-mix(in srgb, var(--lumi-brand) 30%, transparent);
}

.track-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 1px 6px;
  font-size: 11px;
  border-radius: 999px;
  background: color-mix(in srgb, currentColor 20%, transparent);
}

.quick-pill-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px var(--space-7) 10px;
  overflow-x: auto;
  border-bottom: 1px solid var(--border);
  background: color-mix(in srgb, var(--surface) 50%, transparent);
}

.pill-bar-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  white-space: nowrap;
}

.quick-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: var(--text-xs);
  color: var(--text);
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
}

.quick-pill:hover {
  background: var(--surface-hover);
  border-color: var(--lumi-brand);
}

.quick-pill.active {
  background: color-mix(in srgb, var(--lumi-brand) 12%, var(--surface));
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
  font-weight: var(--font-semibold);
}

.pill-platform {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 4px;
  background: var(--border);
  text-transform: uppercase;
  color: var(--text-muted);
}

.pill-count {
  font-size: 10px;
  opacity: 0.7;
}

.picker-search-wrap {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}

.picker-list {
  max-height: 280px;
  overflow-y: auto;
}

.memory-agent-picker {
  margin-top: var(--space-3);
}

.agent-picker-trigger {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  font-size: var(--text-md);
}

.agent-picker-trigger:hover {
  background: var(--surface-hover);
  border-color: var(--lumi-brand);
}

.agent-picker-label {
  color: var(--text-muted);
}

.agent-picker-current {
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.agent-picker-caret {
  color: var(--text-muted);
}

.agent-picker-menu {
  min-width: 260px;
  max-height: 360px;
  overflow-y: auto;
}

.agent-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.agent-option-name {
  font-size: var(--text-md);
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-option-sub {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.menu-item.active {
  background: color-mix(in srgb, var(--lumi-brand) 10%, transparent);
}

.agent-check {
  color: var(--lumi-brand);
  flex-shrink: 0;
}

.agent-picker-empty {
  padding: 12px var(--space-4);
  color: var(--text-muted);
  font-size: var(--text-md);
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
