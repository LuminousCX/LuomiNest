import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AgentProfile } from '../types'
import { useApi } from '../composables/useApi'

export const useAgentStore = defineStore('agent', () => {
  const { apiGet, apiPost, apiPatch, apiDelete } = useApi()

  const agents = ref<AgentProfile[]>([])
  const activeAgent = ref<AgentProfile | null>(null)
  const loading = ref(false)

  const activeAgents = computed(() => agents.value.filter(a => a.isActive))

  const fetchAgents = async () => {
    loading.value = true
    try {
      const data = await apiGet<any[]>('/agents')
      agents.value = data.map(a => ({
        id: a.id,
        name: a.name,
        description: a.description,
        avatar: a.avatar,
        color: a.color,
        systemPrompt: a.system_prompt,
        model: a.model || '',
        provider: a.provider,
        capabilities: a.capabilities || [],
        isActive: a.is_active ?? true,
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
    model?: string
    provider?: string
    color?: string
    capabilities?: string[]
  }) => {
    const result = await apiPost<any>('/agents', {
      name: agent.name,
      description: agent.description || '',
      system_prompt: agent.systemPrompt || '',
      model: agent.model,
      provider: agent.provider,
      color: agent.color || '#0d9488',
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
    const body: any = {}
    if (updates.name !== undefined) body.name = updates.name
    if (updates.description !== undefined) body.description = updates.description
    if (updates.systemPrompt !== undefined) body.system_prompt = updates.systemPrompt
    if (updates.model !== undefined) body.model = updates.model
    if (updates.provider !== undefined) body.provider = updates.provider
    if (updates.color !== undefined) body.color = updates.color
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
