import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '../composables/useApi'

export interface MemoryFact {
  id: string
  content: string
  category: string
  tier: string
  layer: string
  confidence: number
  access_count: number
  last_accessed_at: string
  created_at: string
  source: string
  source_agent_id: string
}

export interface MemoryProfile {
  name: string
  nickname: string
  age: string
  gender: string
  occupation: string
  location: string
  language: string
  interests: string[]
  hobbies: string[]
  preferences: Record<string, string>
  notes: string
  updated_at: string
}

export interface DistilledSection {
  core_identity: string
  long_term: string
  temporary: string
  events_timeline: string
  updated_at: string
}

export interface EpisodicEvent {
  id: string
  timestamp: string
  conversation_id: string
  agent_id: string
  core_goal: string
  key_information: string
  scene_tags: string[]
  importance: number
}

export interface UserSpace {
  version: string
  last_updated: string
  profile: MemoryProfile
  facts: MemoryFact[]
  episodic_events: EpisodicEvent[]
  user: {
    work_context: { summary: string; updated_at: string }
    personal_context: { summary: string; updated_at: string }
    top_of_mind: { summary: string; updated_at: string }
  }
  history: Record<string, any>
  archived_facts: MemoryFact[]
  distilled: DistilledSection
}

export interface AgentMemory {
  version: string
  last_updated: string
  agent_id: string
  agent_facts: MemoryFact[]
  agent_events: EpisodicEvent[]
  working_memory: {
    core_goal: string
    core_goal_extracted_at: string
    conversation_summary: string
    recent_conversations: { role: string; content: string; timestamp: string }[]
    current_state: string
    thread_conversations: Record<string, { role: string; content: string; timestamp: string }[]>
    thread_core_goals: Record<string, string>
  }
  domain_summary: string
  agent_preferences: Record<string, string>
}

export interface MemorySummary {
  version: string
  has_profile: boolean
  total_user_facts: number
  total_user_events: number
  total_archived: number
  facts_by_tier: Record<string, number>
  has_distilled: boolean
  last_updated: string
  agent_facts?: number
  agent_events?: number
  has_domain_summary?: boolean
}

export interface MemoryData {
  version: string
  user_space: UserSpace
  agent_memory: AgentMemory
}

export interface MemoryApiResponse {
  version: string
  user_space?: UserSpace
  agent_memory?: AgentMemory
  memory?: {
    version: string
    last_updated: string
    profile: MemoryProfile
    facts: MemoryFact[]
    episodic_events: EpisodicEvent[]
    user: UserSpace['user']
    history: Record<string, any>
    archived_facts: MemoryFact[]
    working_memory: AgentMemory['working_memory']
  }
}

export const useMemoryStore = defineStore('memory', () => {
  const { apiGet, apiPost, apiPatch, apiDelete, apiPut } = useApi()

  const memoryData = ref<MemoryData | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const summary = ref<MemorySummary | null>(null)
  const injectionContent = ref<string>('')

  const fetchMemory = async (agentId?: string) => {
    loading.value = true
    try {
      const query = agentId ? `?agent_id=${agentId}` : ''
      const raw = await apiGet<MemoryApiResponse>(`/memory/${query}`)

      if (raw.version === '3.0' && raw.user_space) {
        memoryData.value = {
          version: '3.0',
          user_space: raw.user_space,
          agent_memory: raw.agent_memory || {
            version: '3.0',
            last_updated: '',
            agent_id: agentId || '',
            agent_facts: [],
            agent_events: [],
            working_memory: { core_goal: '', core_goal_extracted_at: '', conversation_summary: '', recent_conversations: [], current_state: '', thread_conversations: {}, thread_core_goals: {} },
            domain_summary: '',
            agent_preferences: {},
          },
        }
      } else if (raw.memory) {
        const mem = raw.memory
        memoryData.value = {
          version: '2.0',
          user_space: {
            version: mem.version || '2.0',
            last_updated: mem.last_updated || '',
            profile: mem.profile || { name: '', nickname: '', age: '', gender: '', occupation: '', location: '', language: '', interests: [], hobbies: [], preferences: {}, notes: '', updated_at: '' },
            facts: mem.facts || [],
            episodic_events: mem.episodic_events || [],
            user: mem.user || { work_context: { summary: '', updated_at: '' }, personal_context: { summary: '', updated_at: '' }, top_of_mind: { summary: '', updated_at: '' } },
            history: mem.history || {},
            archived_facts: mem.archived_facts || [],
            distilled: { core_identity: '', long_term: '', temporary: '', events_timeline: '', updated_at: '' },
          },
          agent_memory: {
            version: '3.0',
            last_updated: '',
            agent_id: agentId || '',
            agent_facts: [],
            agent_events: [],
            working_memory: mem.working_memory || { core_goal: '', core_goal_extracted_at: '', conversation_summary: '', recent_conversations: [], current_state: '', thread_conversations: {}, thread_core_goals: {} },
            domain_summary: '',
            agent_preferences: {},
          },
        }
      }
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
    source: string = 'manual',
    layer: string = 'user',
  ) => {
    saving.value = true
    try {
      const result = await apiPost<{ status: string; fact_id: string }>('/memory/facts', {
        content,
        category,
        confidence,
        layer,
        agent_id: layer === 'agent' ? (agentId || null) : null,
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

  const updateProfile = async (profile: Partial<MemoryProfile>) => {
    saving.value = true
    try {
      await apiPut('/memory/user-space/profile', profile)
      await fetchMemory()
    } finally {
      saving.value = false
    }
  }

  const searchMemory = async (query: string, topK: number = 5) => {
    try {
      const result = await apiPost<{ results: Array<{ id: string; content: string; category: string; tier: string; layer: string; confidence: number }>; total: number }>('/memory/search', {
        query,
        top_k: topK,
      })
      return result.results || []
    } catch {
      return []
    }
  }

  const exportMemory = async (agentId?: string) => {
    try {
      const query = agentId ? `?agent_id=${agentId}` : ''
      const result = await apiGet<{ markdown: string }>(`/memory/export${query}`)
      return result.markdown || ''
    } catch {
      return ''
    }
  }

  const importMemory = async (markdown: string, agentId?: string) => {
    saving.value = true
    try {
      await apiPost('/memory/import', {
        markdown,
        agent_id: agentId || null,
      })
      await fetchMemory(agentId)
    } finally {
      saving.value = false
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

  const allFacts = () => {
    if (!memoryData.value) return []
    const userFacts = memoryData.value.user_space?.facts || []
    const agentFacts = memoryData.value.agent_memory?.agent_facts || []
    return [...userFacts, ...agentFacts]
  }

  const factsByTier = (tier: string) => {
    return allFacts().filter(f => f.tier === tier)
  }

  const factsByLayer = (layer: string) => {
    return allFacts().filter(f => f.layer === layer)
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
    updateProfile,
    searchMemory,
    exportMemory,
    importMemory,
    clearMemory,
    allFacts,
    factsByTier,
    factsByLayer,
  }
})
