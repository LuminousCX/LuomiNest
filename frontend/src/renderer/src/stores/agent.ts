import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AgentProfile, MainAgentConfig } from '../types'
import { useApi } from '../composables/useApi'

export const useAgentStore = defineStore('agent', () => {
  const { apiGet, apiPost, apiPatch, apiDelete } = useApi()

  const agents = ref<AgentProfile[]>([])
  const activeAgent = ref<AgentProfile | null>(null)
  const loading = ref(false)
  const mainAgentConfig = ref<MainAgentConfig>({
    provider: '',
    model: '',
    systemPrompt: '',
    temperature: 0.7,
    maxTokens: 4096,
  })

  const activeAgents = computed(() => agents.value.filter(a => a.isActive))

  const fetchAgents = async () => {
    loading.value = true
    try {
      const data = await apiGet<any[]>('/agents')
      agents.value = data
        .filter(a => !a.is_main)
        .map(a => ({
          id: a.id,
          name: a.name,
          description: a.description,
          avatar: a.avatar,
          color: a.color,
          systemPrompt: a.system_prompt || a.systemPrompt || '',
          model: a.model || '',
          provider: a.provider,
          capabilities: a.capabilities || [],
          isActive: a.is_active ?? true,
          isMain: a.is_main ?? false,
          skills: a.skills || [],
          mcpServers: a.mcp_servers || a.mcpServers || [],
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
    skills?: string[]
    mcpServers?: string[]
  }) => {
    const result = await apiPost<any>('/agents', {
      name: agent.name,
      description: agent.description || '',
      system_prompt: agent.systemPrompt || '',
      model: agent.model,
      provider: agent.provider,
      color: agent.color || '#0d9488',
      capabilities: agent.capabilities || ['chat'],
      skills: agent.skills || [],
      mcp_servers: agent.mcpServers || [],
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
    if (updates.skills !== undefined) body.skills = updates.skills
    if (updates.mcpServers !== undefined) body.mcp_servers = updates.mcpServers

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

  const fetchMainAgentConfig = async () => {
    try {
      const result = await apiGet<any>('/agents/main-agent/config')
      mainAgentConfig.value = {
        provider: result.provider || '',
        model: result.model || '',
        systemPrompt: result.systemPrompt || result.system_prompt || '',
        temperature: result.temperature ?? 0.7,
        maxTokens: result.maxTokens || result.max_tokens || 4096,
      }
    } catch {
      // use defaults
    }
  }

  const updateMainAgentConfig = async (updates: Partial<MainAgentConfig>) => {
    const body: any = {}
    if (updates.provider !== undefined) body.provider = updates.provider
    if (updates.model !== undefined) body.model = updates.model
    if (updates.systemPrompt !== undefined) body.systemPrompt = updates.systemPrompt
    if (updates.temperature !== undefined) body.temperature = updates.temperature
    if (updates.maxTokens !== undefined) body.maxTokens = updates.maxTokens

    const result = await apiPatch<any>('/agents/main-agent/config', body)
    mainAgentConfig.value = {
      provider: result.provider || '',
      model: result.model || '',
      systemPrompt: result.systemPrompt || result.system_prompt || '',
      temperature: result.temperature ?? 0.7,
      maxTokens: result.maxTokens || result.max_tokens || 4096,
    }
    return result
  }

  return {
    agents,
    activeAgent,
    loading,
    mainAgentConfig,
    activeAgents,
    fetchAgents,
    createAgent,
    updateAgent,
    deleteAgent,
    setActiveAgent,
    fetchMainAgentConfig,
    updateMainAgentConfig,
  }
})
