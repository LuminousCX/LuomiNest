import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '../composables/useApi'

export interface MemoryProfile {
  name: string
  updated_at: string
  static_facts: string[]
  dynamic_context: string[]
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
}

export interface KnowledgeSection {
  title: string
  content: string
}

export interface SummarySections {
  用户画像: string
  偏好设置: string
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

export const FACT_CATEGORIES = ['preference', 'knowledge', 'context', 'behavior', 'goal', 'correction'] as const
export type FactCategory = typeof FACT_CATEGORIES[number]

export const CATEGORY_LABELS: Record<string, string> = {
  preference: '偏好',
  knowledge: '知识',
  context: '背景',
  behavior: '行为',
  goal: '目标',
  correction: '纠正',
}

export const CATEGORY_COLORS: Record<string, string> = {
  preference: '#22c55e',
  knowledge: '#0ea5e9',
  context: '#8b5cf6',
  behavior: '#f59e0b',
  goal: '#ef4444',
  correction: '#f97316',
}

function agentQuery(agentId?: string | null): string {
  return agentId ? `?agent_id=${agentId}` : ''
}

export const useMemoryStore = defineStore('memory', () => {
  const { apiGet, apiPost, apiPut, apiPatch, apiDelete } = useApi()

  const profile = ref<MemoryProfile>({ name: '' })
  const facts = ref<FactItem[]>([])
  const knowledgeContent = ref('')
  const knowledgeSections = ref<KnowledgeSection[]>([])
  const summaryContent = ref('')
  const summarySections = ref<SummarySections>({ 用户画像: '', 偏好设置: '', 兴趣目标: '', 近期状态: '', 事件时间线: '' })
  const dailyContent = ref('')
  const dailyDate = ref('')
  const dailies = ref<string[]>([])
  const injectionContent = ref('')
  const loading = ref(false)
  const saving = ref(false)
  const distilling = ref(false)
  const recentFacts = ref<FactItem[]>([])

  const memoryAgents = ref<MemoryAgent[]>([])
  const currentAgentId = ref<string | null>(null)

  const fetchMemory = async (agentId?: string | null) => {
    loading.value = true
    try {
      const result = await apiGet<{ memory: string; profile: MemoryProfile; facts: FactItem[] }>(`/memory/${agentQuery(agentId)}`)
      profile.value = result.profile || { name: '' }
      facts.value = result.facts || []
    } catch {
      profile.value = { name: '' }
      facts.value = []
    } finally {
      loading.value = false
    }
  }

  const fetchFacts = async (category?: string, agentId?: string | null) => {
    try {
      const params: string[] = []
      if (category) params.push(`category=${category}`)
      if (agentId) params.push(`agent_id=${agentId}`)
      const query = params.length > 0 ? `?${params.join('&')}` : ''
      const result = await apiGet<{ facts: FactItem[] }>(`/memory/facts${query}`)
      facts.value = result.facts || []
    } catch {
      facts.value = []
    }
  }

  const addFact = async (data: { content: string; category: string; confidence: number; source_error?: string }, agentId?: string | null) => {
    saving.value = true
    try {
      await apiPost(`/memory/facts${agentQuery(agentId)}`, { ...data, source_error: data.source_error || '' })
      await fetchMemory(agentId)
    } finally {
      saving.value = false
    }
  }

  const removeFact = async (factId: string, agentId?: string | null) => {
    try {
      await apiDelete(`/memory/facts/${factId}${agentQuery(agentId)}`)
      facts.value = facts.value.filter(f => f.id !== factId)
    } catch { /* ignore */ }
  }

  const updateFact = async (factId: string, data: { content?: string; category?: string; confidence?: number }, agentId?: string | null) => {
    try {
      await apiPatch(`/memory/facts/${factId}${agentQuery(agentId)}`, data)
      await fetchMemory(agentId)
    } catch { /* ignore */ }
  }

  const fetchKnowledge = async (agentId?: string | null) => {
    try {
      const result = await apiGet<{ content: string; sections: KnowledgeSection[] }>(`/memory/knowledge${agentQuery(agentId)}`)
      knowledgeContent.value = result.content || ''
      knowledgeSections.value = result.sections || []
    } catch {
      knowledgeContent.value = ''
      knowledgeSections.value = []
    }
  }

  const saveKnowledge = async (content: string, agentId?: string | null) => {
    saving.value = true
    try {
      await apiPut(`/memory/knowledge${agentQuery(agentId)}`, { content })
      knowledgeContent.value = content
      await fetchKnowledge(agentId)
    } finally {
      saving.value = false
    }
  }

  const fetchSummary = async (agentId?: string | null) => {
    try {
      const result = await apiGet<{ content: string; sections: SummarySections }>(`/memory/summary${agentQuery(agentId)}`)
      summaryContent.value = result.content || ''
      summarySections.value = result.sections || { 用户画像: '', 偏好设置: '', 兴趣目标: '', 近期状态: '', 事件时间线: '' }
    } catch {
      summaryContent.value = ''
      summarySections.value = { 用户画像: '', 偏好设置: '', 兴趣目标: '', 近期状态: '', 事件时间线: '' }
    }
  }

  const saveSummary = async (content: string, agentId?: string | null) => {
    saving.value = true
    try {
      await apiPut(`/memory/summary${agentQuery(agentId)}`, { content })
      summaryContent.value = content
      await fetchSummary(agentId)
    } finally {
      saving.value = false
    }
  }

  const triggerDistill = async (messages: Array<Record<string, any>>, agentId?: string | null) => {
    distilling.value = true
    try {
      await apiPost(`/memory/distill${agentQuery(agentId)}`, { messages })
      await fetchSummary(agentId)
    } finally {
      distilling.value = false
    }
  }

  const fetchDaily = async (date?: string, agentId?: string | null, conversationId?: string | null) => {
    try {
      const params: string[] = []
      if (date) params.push(`date=${date}`)
      if (agentId) params.push(`agent_id=${agentId}`)
      if (conversationId) params.push(`conversation_id=${conversationId}`)
      const query = params.length > 0 ? `?${params.join('&')}` : ''
      const result = await apiGet<{ date: string; content: string }>(`/memory/daily${query}`)
      dailyContent.value = result.content || ''
      dailyDate.value = result.date || ''
    } catch {
      dailyContent.value = ''
    }
  }

  const appendDaily = async (content: string, date?: string, agentId?: string | null, conversationId?: string | null) => {
    saving.value = true
    try {
      await apiPost(`/memory/daily${agentQuery(agentId)}`, { content, date: date || null, conversation_id: conversationId || null })
      await Promise.all([
        fetchDaily(date, agentId, conversationId),
        fetchDailies(agentId, conversationId),
      ])
    } finally {
      saving.value = false
    }
  }

  const fetchDailies = async (agentId?: string | null, conversationId?: string | null) => {
    try {
      const params: string[] = []
      if (agentId) params.push(`agent_id=${agentId}`)
      if (conversationId) params.push(`conversation_id=${conversationId}`)
      const query = params.length > 0 ? `?${params.join('&')}` : ''
      const result = await apiGet<{ dailies: string[] }>(`/memory/dailies${query}`)
      dailies.value = result.dailies || []
    } catch {
      dailies.value = []
    }
  }

  interface ConversationInfo {
  id: string
  title: string
}

const conversationDailies = ref<ConversationInfo[]>([])
const fetchConversationDailies = async (agentId?: string | null) => {
  try {
    const result = await apiGet<{ conversations: ConversationInfo[] }>(`/memory/conversation-dailies${agentQuery(agentId)}`)
    conversationDailies.value = result.conversations || []
  } catch {
    conversationDailies.value = []
  }
}

  const fetchInjectionContent = async (agentId?: string | null) => {
    try {
      const result = await apiGet<{ content: string; has_memory: boolean }>(`/memory/inject${agentQuery(agentId)}`)
      injectionContent.value = result.content || ''
      return result
    } catch {
      injectionContent.value = ''
      return { content: '', has_memory: false }
    }
  }

  const fetchProfile = async (agentId?: string | null) => {
    try {
      profile.value = await apiGet<MemoryProfile>(`/memory/profile${agentQuery(agentId)}`)
    } catch {
      profile.value = { name: '', updated_at: '', static_facts: [], dynamic_context: [] }
    }
  }

  const fetchRecentFacts = async (agentId?: string | null, since: number = 30) => {
    try {
      const query = agentId ? `?agent_id=${agentId}&since=${since}` : `?since=${since}`
      const result = await apiGet<{ facts: FactItem[] }>(`/memory/recent-facts${query}`)
      recentFacts.value = result.facts || []
      return result.facts || []
    } catch {
      recentFacts.value = []
      return []
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

  const switchAgent = async (agentId: string | null) => {
        currentAgentId.value = agentId
        await Promise.all([
            fetchMemory(agentId),
            fetchKnowledge(agentId),
            fetchDailies(agentId),
            fetchSummary(agentId),
            fetchFacts(undefined, agentId),
        ])
    }

    const clearFacts = async (agentId?: string | null) => {
        await apiDelete(`/memory/facts${agentQuery(agentId)}`)
        await fetchMemory(agentId)
    }

    const clearKnowledge = async (agentId?: string | null) => {
        await apiDelete(`/memory/knowledge${agentQuery(agentId)}`)
        await fetchKnowledge(agentId)
    }

    const clearDailies = async (agentId?: string | null) => {
        await apiDelete(`/memory/dailies${agentQuery(agentId)}`)
        await fetchDailies(agentId)
    }

    const clearSummary = async (agentId?: string | null) => {
        await apiDelete(`/memory/summary${agentQuery(agentId)}`)
        await fetchSummary(agentId)
    }

    const resetAll = async (agentId?: string | null) => {
        await apiDelete(`/memory/reset-all${agentQuery(agentId)}`)
        await Promise.all([
            fetchMemory(agentId),
            fetchKnowledge(agentId),
            fetchDailies(agentId),
            fetchSummary(agentId),
        ])
    }

    return {
        profile,
        facts,
        knowledgeContent,
        knowledgeSections,
        summaryContent,
        summarySections,
        dailyContent,
        dailyDate,
        dailies,
        injectionContent,
        loading,
        saving,
        distilling,
        memoryAgents,
        currentAgentId,
        fetchMemory,
        fetchFacts,
        addFact,
        removeFact,
        updateFact,
        fetchKnowledge,
        saveKnowledge,
        fetchSummary,
        saveSummary,
        triggerDistill,
        fetchDaily,
        appendDaily,
        fetchDailies,
        fetchConversationDailies,
        conversationDailies,
        fetchInjectionContent,
        fetchProfile,
        fetchRecentFacts,
        recentFacts,
        fetchMemoryAgents,
        switchAgent,
        clearFacts,
        clearKnowledge,
        clearDailies,
        clearSummary,
        resetAll,
    }
})
