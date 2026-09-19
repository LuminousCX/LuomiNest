import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '../composables/useApi'
import { i18n } from '../i18n'

export interface MemoryProfile {
  name: string
  updated_at?: string
  static_facts?: string[]
  dynamic_context?: string[]
}

export interface FactItem {
  id: string
  content: string
  category: string
  confidence: number
  created_at: string
  source: string
  source_error: string
  expires_at: string | null
  is_latest: boolean
  supersedes_id: string | null
  /** 置顶：注入时绕过置信度/过期闸门并恒排最前（陪伴关键信息） */
  pinned?: boolean
  scope?: string
  group_id?: string
}

export interface KnowledgeSection {
  title: string
  content: string
}

export interface SummarySections {
  用户画像: string
  偏好设置: string
  兴趣偏好: string
  兴趣目标: string
  近期状态: string
  事件时间线: string
}

export interface MemoryAgent {
  id: string
  name: string
  fact_count?: number
  has_profile?: boolean
  profile_name?: string
}

export interface MemoryUser {
  user_key: string
  platform: string
  name: string
  fact_count: number
  has_profile: boolean
  last_updated?: string
}

export interface MemoryGroup {
  group_key: string
  platform: string
  name: string
  fact_count: number
  has_profile: boolean
  last_updated?: string
}

export type MemoryTrackType = 'owner' | 'users' | 'groups'

export const FACT_CATEGORIES = ['preference', 'knowledge', 'context', 'behavior', 'goal', 'correction'] as const
export type FactCategory = typeof FACT_CATEGORIES[number]

export const FACT_SCOPES = ['global', 'private', 'group'] as const
export type FactScope = typeof FACT_SCOPES[number]

/** 事实类别的本地化标签（类别 id 为发给后端的数据，不做翻译） */
export const categoryLabel = (cat: string): string => {
  try {
    return i18n.global.t(`memory.cat.${cat}`)
  } catch {
    return cat
  }
}

export const CATEGORY_COLORS: Record<string, string> = {
  preference: 'var(--lumi-success)',
  knowledge: 'var(--lumi-sky)',
  context: 'var(--task-sky)',
  behavior: 'var(--lumi-amber)',
  goal: 'var(--lumi-danger)',
  correction: 'var(--lumi-amber)',
}

export const SCOPE_COLORS: Record<string, string> = {
  global: 'var(--lumi-success)',
  private: 'var(--lumi-danger)',
  group: 'var(--task-sky)',
}

export const SCOPE_LABELS: Record<string, string> = {
  global: '全局公开',
  private: '私密心事',
  group: '群聊公开',
}

export const useMemoryStore = defineStore('memory', () => {
  const { apiGet, apiPost, apiPut, apiPatch, apiDelete } = useApi()

  const currentTrack = ref<MemoryTrackType>('owner')
  const currentUserKey = ref<string>('')
  const currentGroupKey = ref<string>('')
  const currentAgentId = ref<string | null>(null)

  const memoryAgents = ref<MemoryAgent[]>([])
  const memoryUsers = ref<MemoryUser[]>([])
  const memoryGroups = ref<MemoryGroup[]>([])

  const profile = ref<MemoryProfile>({ name: '' })
  const briefing = ref<{ date: string; content: string; generated_at: string; enabled?: boolean } | null>(null)
  const briefingFetchedDate = ref('')

  const facts = ref<FactItem[]>([])
  const knowledgeContent = ref('')
  const knowledgeSections = ref<KnowledgeSection[]>([])
  const summaryContent = ref('')
  const summarySections = ref<SummarySections>({ 用户画像: '', 偏好设置: '', 兴趣偏好: '', 兴趣目标: '', 近期状态: '', 事件时间线: '' })
  const dailyContent = ref('')
  const dailyDate = ref('')
  const dailies = ref<string[]>([])
  const conversationDailies = ref<{ id: string; title: string }[]>([])
  const loading = ref(false)
  const saving = ref(false)

  function queryForCurrentTrack(extra?: Record<string, string | number | boolean | null | undefined>): string {
    const params: string[] = []
    if (currentTrack.value === 'owner') {
      if (currentAgentId.value) params.push(`agent_id=${encodeURIComponent(currentAgentId.value)}`)
    } else if (currentTrack.value === 'users') {
      params.push('track=users')
      if (currentUserKey.value) params.push(`user_key=${encodeURIComponent(currentUserKey.value)}`)
    } else if (currentTrack.value === 'groups') {
      params.push('track=groups')
      if (currentGroupKey.value) params.push(`group_key=${encodeURIComponent(currentGroupKey.value)}`)
    }
    if (extra) {
      for (const [k, v] of Object.entries(extra)) {
        if (v !== undefined && v !== null && v !== '') {
          params.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        }
      }
    }
    return params.length > 0 ? `?${params.join('&')}` : ''
  }

  const fetchBriefing = async (force = false): Promise<void> => {
    try {
      const today = new Date().toLocaleDateString('sv-SE')
      if (!force && briefingFetchedDate.value === today && briefing.value) return
      const result = await apiGet<{ date: string; content: string; generated_at: string; enabled?: boolean }>(
        force ? '/memory/briefing/refresh' : '/memory/briefing',
      )
      briefing.value = result?.content ? result : null
      briefingFetchedDate.value = today
    } catch {
      briefing.value = null
    }
  }

  const fetchMemory = async (agentId?: string | null) => {
    if (agentId !== undefined) {
      currentAgentId.value = agentId
    }
    loading.value = true
    try {
      const result = await apiGet<{ memory: string; profile: MemoryProfile; facts: FactItem[] }>(`/memory/${queryForCurrentTrack()}`)
      profile.value = result.profile || { name: '' }
      facts.value = result.facts || []
    } catch {
      profile.value = { name: '' }
      facts.value = []
    } finally {
      loading.value = false
    }
  }

  const fetchFacts = async (category?: string, agentIdOrScope?: string, scope?: string) => {
    let resolvedScope = scope
    if (agentIdOrScope && !scope && (agentIdOrScope === 'global' || agentIdOrScope === 'private' || agentIdOrScope === 'group')) {
      resolvedScope = agentIdOrScope
    } else if (agentIdOrScope && currentTrack.value === 'owner') {
      currentAgentId.value = agentIdOrScope
    }
    try {
      const result = await apiGet<{ facts: FactItem[] }>(`/memory/facts${queryForCurrentTrack({ category, scope: resolvedScope })}`)
      facts.value = result.facts || []
    } catch {
      facts.value = []
    }
  }

  const addFact = async (data: {
    content: string
    category: string
    confidence: number
    source_error?: string
    scope?: string
    group_id?: string
  }) => {
    saving.value = true
    try {
      await apiPost(`/memory/facts${queryForCurrentTrack()}`, {
        ...data,
        source_error: data.source_error || '',
        scope: data.scope || (currentTrack.value === 'users' ? 'private' : currentTrack.value === 'groups' ? 'group' : 'global'),
        group_id: data.group_id || (currentTrack.value === 'groups' ? currentGroupKey.value : ''),
      })
      await fetchMemory()
    } finally {
      saving.value = false
    }
  }

  const removeFact = async (factId: string) => {
    try {
      await apiDelete(`/memory/facts/${factId}${queryForCurrentTrack()}`)
      facts.value = facts.value.filter(f => f.id !== factId)
    } catch { /* ignore */ }
  }

  const toggleFactPin = async (factId: string, pinned: boolean) => {
    try {
      await apiPost(`/memory/facts/${factId}/pin${queryForCurrentTrack()}`, { pinned })
      await fetchMemory()
    } catch { /* ignore */ }
  }

  const updateFact = async (factId: string, data: {
    content?: string
    category?: string
    confidence?: number
    scope?: string
    group_id?: string
  }) => {
    try {
      await apiPatch(`/memory/facts/${factId}${queryForCurrentTrack()}`, data)
      await fetchMemory()
    } catch { /* ignore */ }
  }

  const fetchKnowledge = async (agentId?: string | null) => {
    if (agentId !== undefined && currentTrack.value === 'owner') {
      currentAgentId.value = agentId
    }
    try {
      const result = await apiGet<{ content: string; sections: KnowledgeSection[] }>(`/memory/knowledge${queryForCurrentTrack()}`)
      knowledgeContent.value = result.content || ''
      knowledgeSections.value = result.sections || []
    } catch {
      knowledgeContent.value = ''
      knowledgeSections.value = []
    }
  }

  const saveKnowledge = async (content: string) => {
    saving.value = true
    try {
      await apiPut(`/memory/knowledge${queryForCurrentTrack()}`, { content })
      knowledgeContent.value = content
      await fetchKnowledge()
    } finally {
      saving.value = false
    }
  }

  const fetchSummary = async (agentId?: string | null) => {
    if (agentId !== undefined && currentTrack.value === 'owner') {
      currentAgentId.value = agentId
    }
    try {
      const result = await apiGet<{ content: string; sections: SummarySections }>(`/memory/summary${queryForCurrentTrack()}`)
      summaryContent.value = result.content || ''
      summarySections.value = result.sections || { 用户画像: '', 偏好设置: '', 兴趣偏好: '', 兴趣目标: '', 近期状态: '', 事件时间线: '' }
    } catch {
      summaryContent.value = ''
      summarySections.value = { 用户画像: '', 偏好设置: '', 兴趣偏好: '', 兴趣目标: '', 近期状态: '', 事件时间线: '' }
    }
  }

  const saveSummary = async (content: string) => {
    saving.value = true
    try {
      await apiPut(`/memory/summary${queryForCurrentTrack()}`, { content })
      summaryContent.value = content
      await fetchSummary()
    } finally {
      saving.value = false
    }
  }

  const fetchDaily = async (date?: string, agentIdOrConvId?: string | null, conversationId?: string | null) => {
    let convId = conversationId
    if (agentIdOrConvId !== undefined) {
      if (conversationId === undefined) {
        convId = agentIdOrConvId
      } else if (currentTrack.value === 'owner') {
        currentAgentId.value = agentIdOrConvId
      }
    }
    try {
      const result = await apiGet<{ date: string; content: string }>(`/memory/daily${queryForCurrentTrack({ date, conversation_id: convId })}`)
      dailyContent.value = result.content || ''
      dailyDate.value = result.date || ''
    } catch {
      dailyContent.value = ''
    }
  }

  const appendDaily = async (content: string, date?: string, agentIdOrConvId?: string | null, conversationId?: string | null) => {
    let convId = conversationId
    if (agentIdOrConvId !== undefined) {
      if (conversationId === undefined) {
        convId = agentIdOrConvId
      } else if (currentTrack.value === 'owner') {
        currentAgentId.value = agentIdOrConvId
      }
    }
    saving.value = true
    try {
      await apiPost(`/memory/daily${queryForCurrentTrack()}`, { content, date: date || null, conversation_id: convId || null })
      await Promise.all([
        fetchDaily(date, convId),
        fetchDailies(convId),
      ])
    } finally {
      saving.value = false
    }
  }

  const fetchDailies = async (agentIdOrConvId?: string | null, conversationId?: string | null) => {
    let convId = conversationId
    if (agentIdOrConvId !== undefined) {
      if (conversationId === undefined) {
        convId = agentIdOrConvId
      } else if (currentTrack.value === 'owner') {
        currentAgentId.value = agentIdOrConvId
      }
    }
    try {
      const result = await apiGet<{ dailies: string[] }>(`/memory/dailies${queryForCurrentTrack({ conversation_id: convId })}`)
      dailies.value = result.dailies || []
    } catch {
      dailies.value = []
    }
  }

  const fetchConversationDailies = async () => {
    try {
      const result = await apiGet<{ conversations: { id: string; title: string }[] }>(`/memory/conversation-dailies${queryForCurrentTrack()}`)
      conversationDailies.value = result.conversations || []
    } catch {
      conversationDailies.value = []
    }
  }

  const fetchMemoryAgents = async () => {
    try {
      const result = await apiGet<{ agents: MemoryAgent[] }>('/memory/agents')
      memoryAgents.value = result.agents || []
    } catch {
      memoryAgents.value = []
    }
  }

  const fetchMemoryUsers = async () => {
    try {
      const result = await apiGet<{ users: MemoryUser[] }>('/memory/users')
      memoryUsers.value = result.users || []
    } catch {
      memoryUsers.value = []
    }
  }

  const fetchMemoryGroups = async () => {
    try {
      const result = await apiGet<{ groups: MemoryGroup[] }>('/memory/groups')
      memoryGroups.value = result.groups || []
    } catch {
      memoryGroups.value = []
    }
  }

  const switchAgent = async (agentId: string | null) => {
    currentTrack.value = 'owner'
    currentAgentId.value = agentId
    currentUserKey.value = ''
    currentGroupKey.value = ''
    await Promise.all([
      fetchMemory(),
      fetchKnowledge(),
      fetchDailies(),
      fetchSummary(),
      fetchFacts(),
    ])
  }

  const switchTrack = async (track: MemoryTrackType, targetKey?: string) => {
    currentTrack.value = track
    if (track === 'users') {
      currentUserKey.value = targetKey || ''
      currentGroupKey.value = ''
    } else if (track === 'groups') {
      currentGroupKey.value = targetKey || ''
      currentUserKey.value = ''
    } else {
      currentUserKey.value = ''
      currentGroupKey.value = ''
    }
    await Promise.all([
      fetchMemory(),
      fetchKnowledge(),
      fetchSummary(),
      fetchDailies(),
      fetchFacts(),
    ])
  }

  const clearFacts = async (agentId?: string | null) => {
    if (agentId !== undefined && currentTrack.value === 'owner') currentAgentId.value = agentId
    await apiDelete(`/memory/facts${queryForCurrentTrack()}`)
    await fetchMemory()
  }

  const clearKnowledge = async (agentId?: string | null) => {
    if (agentId !== undefined && currentTrack.value === 'owner') currentAgentId.value = agentId
    await apiDelete(`/memory/knowledge${queryForCurrentTrack()}`)
    await fetchKnowledge()
  }

  const clearDailies = async (agentId?: string | null) => {
    if (agentId !== undefined && currentTrack.value === 'owner') currentAgentId.value = agentId
    await apiDelete(`/memory/dailies${queryForCurrentTrack()}`)
    await fetchDailies()
  }

  const clearSummary = async (agentId?: string | null) => {
    if (agentId !== undefined && currentTrack.value === 'owner') currentAgentId.value = agentId
    await apiDelete(`/memory/summary${queryForCurrentTrack()}`)
    await fetchSummary()
  }

  const resetAll = async (agentId?: string | null) => {
    if (agentId !== undefined && currentTrack.value === 'owner') currentAgentId.value = agentId
    await apiDelete(`/memory/reset-all${queryForCurrentTrack()}`)
    await Promise.all([
      fetchMemory(),
      fetchKnowledge(),
      fetchDailies(),
      fetchSummary(),
    ])
  }

  return {
    currentTrack,
    currentUserKey,
    currentGroupKey,
    currentAgentId,
    profile,
    facts,
    briefing,
    knowledgeContent,
    knowledgeSections,
    summaryContent,
    summarySections,
    dailyContent,
    dailyDate,
    dailies,
    loading,
    saving,
    memoryAgents,
    memoryUsers,
    memoryGroups,
    fetchBriefing,
    fetchMemory,
    fetchFacts,
    addFact,
    removeFact,
    updateFact,
    toggleFactPin,
    fetchKnowledge,
    saveKnowledge,
    fetchSummary,
    saveSummary,
    fetchDaily,
    appendDaily,
    fetchDailies,
    fetchConversationDailies,
    conversationDailies,
    fetchMemoryAgents,
    fetchMemoryUsers,
    fetchMemoryGroups,
    switchAgent,
    switchTrack,
    clearFacts,
    clearKnowledge,
    clearDailies,
    clearSummary,
    resetAll,
  }
})
