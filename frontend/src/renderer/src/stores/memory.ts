import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '../composables/useApi'

export interface MemoryFact {
  id: string
  content: string
  category: string
  tier: string
  confidence: number
  access_count: number
  last_accessed_at: string
  created_at: string
  source: string
}

export interface MemoryProfile {
  name: string
  nickname: string
  occupation: string
  location: string
  interests: string[]
  hobbies: string[]
  preferences: Record<string, string>
}

export interface MemorySummary {
  version: string
  has_core_goal: boolean
  has_profile: boolean
  total_facts: number
  total_events: number
  total_archived: number
  facts_by_tier: Record<string, number>
  last_updated: string
}

export interface MemoryData {
  memory: {
    version: string
    last_updated: string
    facts: MemoryFact[]
    profile: MemoryProfile
    working_memory: {
      core_goal: string
      conversation_summary: string
      recent_conversations: { role: string; content: string; timestamp: string }[]
      current_state: string
    }
    episodic_events: Array<{
      id: string
      timestamp: string
      core_goal: string
      key_information: string
      scene_tags: string[]
      importance: number
    }>
    archived_facts: MemoryFact[]
  }
  summary: MemorySummary
}

export const useMemoryStore = defineStore('memory', () => {
  const { apiGet, apiPost, apiPatch, apiDelete } = useApi()

  const memoryData = ref<MemoryData | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const summary = ref<MemorySummary | null>(null)
  const injectionContent = ref<string>('')

  const fetchMemory = async (agentId?: string) => {
    loading.value = true
    try {
      const query = agentId ? `?agent_id=${agentId}` : ''
      memoryData.value = await apiGet<MemoryData>(`/memory/${query}`)
    } catch {
      memoryData.value = null
    } finally {
      loading.value = false
    }
  }

  const fetchSummary = async (agentId?: string) => {
    try {
      const query = agentId ? `?agent_id=${agentId}` : ''
      summary.value = await apiGet<MemorySummary>(`/memory/summary${query}`)
    } catch {
      summary.value = null
    }
  }

  const fetchInjectionContent = async (agentId?: string) => {
    try {
      const query = agentId ? `?agent_id=${agentId}` : ''
      const result = await apiPost<{ content: string; has_memory: boolean }>(`/memory/inject${query}`, {})
      injectionContent.value = result.content || ''
      return result
    } catch {
      injectionContent.value = ''
      return { content: '', has_memory: false }
    }
  }

  const addFact = async (
    content: string,
    category: string = 'context',
    confidence: number = 0.8,
    agentId?: string,
    source: string = 'manual'
  ) => {
    saving.value = true
    try {
      const result = await apiPost<{ status: string; fact_id: string; total_facts: number }>('/memory/facts', {
        content,
        category,
        confidence,
        agent_id: agentId || null,
        source,
      })
      await fetchMemory(agentId)
      return result
    } finally {
      saving.value = false
    }
  }

  const updateFact = async (
    factId: string,
    content?: string,
    category?: string,
    confidence?: number,
    agentId?: string
  ) => {
    saving.value = true
    try {
      const query = agentId ? `?agent_id=${agentId}` : ''
      await apiPatch(`/memory/facts/${factId}${query}`, {
        content,
        category,
        confidence,
      })
      await fetchMemory(agentId)
    } finally {
      saving.value = false
    }
  }

  const deleteFact = async (factId: string, agentId?: string) => {
    saving.value = true
    try {
      const query = agentId ? `?agent_id=${agentId}` : ''
      await apiDelete(`/memory/facts/${factId}${query}`)
      await fetchMemory(agentId)
    } finally {
      saving.value = false
    }
  }

  const searchMemory = async (query: string, topK: number = 5) => {
    try {
      const result = await apiPost<{ results: Array<{ content: string; score: number; source: string }>; total: number }>('/memory/search', {
        query,
        top_k: topK,
      })
      return result.results || []
    } catch {
      return []
    }
  }

  const clearMemory = async (agentId?: string) => {
    saving.value = true
    try {
      const query = agentId ? `?agent_id=${agentId}` : ''
      await apiDelete(`/memory/${query}`)
      await fetchMemory(agentId)
    } finally {
      saving.value = false
    }
  }

  const factsByTier = (tier: string) => {
    if (!memoryData.value) return []
    return memoryData.value.memory.facts.filter(f => f.tier === tier)
  }

  return {
    memoryData,
    loading,
    saving,
    summary,
    injectionContent,
    fetchMemory,
    fetchSummary,
    fetchInjectionContent,
    addFact,
    updateFact,
    deleteFact,
    searchMemory,
    clearMemory,
    factsByTier,
  }
})