import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SkillDefinition, MCPServer, MCPTool } from '../types'
import { useApi } from '../composables/useApi'

export const useSkillStore = defineStore('skill', () => {
  const { apiGet, apiPost, apiPatch, apiDelete } = useApi()

  const skills = ref<SkillDefinition[]>([])
  const mcpServers = ref<MCPServer[]>([])
  const loading = ref(false)

  const fetchSkills = async () => {
    loading.value = true
    try {
      skills.value = await apiGet<SkillDefinition[]>('/skills')
    } catch {
      skills.value = []
    } finally {
      loading.value = false
    }
  }

  const createSkill = async (skill: {
    name: string
    description?: string
    category?: string
    parameters?: Record<string, any>
    isActive?: boolean
    promptTemplate?: string
    tags?: string[]
  }) => {
    const result = await apiPost<SkillDefinition>('/skills', {
      name: skill.name,
      description: skill.description || '',
      category: skill.category || 'custom',
      parameters: skill.parameters || {},
      is_active: skill.isActive ?? true,
      prompt_template: skill.promptTemplate,
      tags: skill.tags || [],
    })
    await fetchSkills()
    return result
  }

  const updateSkill = async (name: string, updates: Partial<SkillDefinition>) => {
    const body: any = {}
    if (updates.description !== undefined) body.description = updates.description
    if (updates.category !== undefined) body.category = updates.category
    if (updates.parameters !== undefined) body.parameters = updates.parameters
    if (updates.isActive !== undefined) body.is_active = updates.isActive
    if (updates.promptTemplate !== undefined) body.prompt_template = updates.promptTemplate
    if (updates.tags !== undefined) body.tags = updates.tags

    await apiPatch(`/skills/${name}`, body)
    await fetchSkills()
  }

  const deleteSkill = async (name: string) => {
    await apiDelete(`/skills/${name}`)
    await fetchSkills()
  }

  const executeSkill = async (name: string, arguments_: Record<string, any> = {}) => {
    const result = await apiPost<{ result: string }>(`/skills/${name}/execute`, arguments_)
    return result
  }

  const fetchMcpServers = async () => {
    try {
      const response = await apiGet<{ data: MCPServer[] }>('/mcp/servers')
      mcpServers.value = response.data || []
    } catch {
      mcpServers.value = []
    }
  }

  const addMcpServer = async (server: {
    name: string
    command?: string
    args?: string[]
    env?: Record<string, string>
    transport?: string
    url?: string
    description?: string
  }) => {
    await apiPost('/mcp/servers', {
      name: server.name,
      command: server.command || '',
      args: server.args || [],
      env: server.env,
      transport: server.transport || 'stdio',
      url: server.url,
      description: server.description || '',
    })
    await fetchMcpServers()
  }

  const removeMcpServer = async (name: string) => {
    await apiDelete(`/mcp/servers/${name}`)
    await fetchMcpServers()
  }

  const getMcpTools = async (serverName: string): Promise<MCPTool[]> => {
    try {
      const response = await apiGet<{ data: MCPTool[] }>(`/mcp/servers/${serverName}/tools`)
      return response.data || []
    } catch {
      return []
    }
  }

  return {
    skills,
    mcpServers,
    loading,
    fetchSkills,
    createSkill,
    updateSkill,
    deleteSkill,
    executeSkill,
    fetchMcpServers,
    addMcpServer,
    removeMcpServer,
    getMcpTools,
  }
})
