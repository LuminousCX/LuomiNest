import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AgentProfile } from '../types'
import { useApi } from '../composables/useApi'

/** Raw agent object returned by GET /agents */
interface RawAgent {
  id: string
  name: string
  description?: string
  avatar?: string
  color?: string
  system_prompt?: string
  systemPrompt?: string
  capabilities?: string[]
  is_active?: boolean
  is_main?: boolean
  created_at?: string
  updated_at?: string
}

/** Raw agent object returned by POST /agents */
interface RawAgentCreateResponse {
  id: string
  name?: string
  description?: string
  color?: string
}

export const useAgentStore = defineStore('agent', () => {
  const { apiGet, apiPost, apiPatch, apiDelete } = useApi()

  const agents = ref<AgentProfile[]>([])
  const activeAgent = ref<AgentProfile | null>(null)
  const loading = ref(false)

  const activeAgents = computed(() => agents.value.filter(a => a.isActive))

  const fetchAgents = async () => {
    loading.value = true
    try {
      const data = await apiGet<RawAgent[]>('/agents')
      agents.value = data
        .filter(a => !a.is_main)
        .map(a => ({
          id: a.id,
          name: a.name,
          description: a.description || '',
          avatar: a.avatar || '',
          color: a.color || '',
          systemPrompt: a.system_prompt || a.systemPrompt || '',
          capabilities: a.capabilities || [],
          isActive: a.is_active ?? true,
          isMain: a.is_main ?? false,
          createdAt: a.created_at,
          updatedAt: a.updated_at,
        }))
      if (!activeAgent.value && agents.value.length > 0) {
        activeAgent.value = agents.value[0]
      }
    } catch {
      agents.value = []
    } finally {
      loading.value = false
    }
  }

  const createAgent = async (agent: {
    name: string
    description?: string
    systemPrompt?: string
    color?: string
    avatar?: string
    capabilities?: string[]
  }) => {
    const result = await apiPost<RawAgentCreateResponse>('/agents', {
      name: agent.name,
      description: agent.description || '',
      system_prompt: agent.systemPrompt || '',
      color: agent.color || '#147EBC',
      avatar: agent.avatar || '',
      capabilities: agent.capabilities || ['chat'],
    })
    await fetchAgents()
    const created = agents.value.find(a => a.id === result.id)
    if (created) {
      activeAgent.value = created
    }
    return result
  }

  const updateAgent = async (agentId: string, updates: Partial<AgentProfile>) => {
    const body: Record<string, unknown> = {}
    if (updates.name !== undefined) body.name = updates.name
    if (updates.description !== undefined) body.description = updates.description
    if (updates.systemPrompt !== undefined) body.system_prompt = updates.systemPrompt
    if (updates.color !== undefined) body.color = updates.color
    if (updates.avatar !== undefined) body.avatar = updates.avatar || ''
    if (updates.capabilities !== undefined) body.capabilities = updates.capabilities
    if (updates.isActive !== undefined) body.is_active = updates.isActive

    await apiPatch(`/agents/${agentId}`, body)
    await fetchAgents()
    if (activeAgent.value?.id === agentId) {
      const updated = agents.value.find(a => a.id === agentId)
      if (updated) activeAgent.value = updated
    }
  }

  const deleteAgent = async (agentId: string) => {
    await apiDelete(`/agents/${agentId}`)
    if (activeAgent.value?.id === agentId) {
      activeAgent.value = null
    }
    await fetchAgents()
    if (!activeAgent.value && agents.value.length > 0) {
      activeAgent.value = agents.value[0]
    }
  }

  const setActiveAgent = (agent: AgentProfile) => {
    activeAgent.value = agent
  }

  return {
    agents,
    activeAgent,
    loading,
    activeAgents,
    fetchAgents,
    createAgent,
    updateAgent,
    deleteAgent,
    setActiveAgent,
  }
})
