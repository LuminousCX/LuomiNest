import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { GroupInfo, GroupMessage, AgentProfile } from '../types'
import { useApi } from '../composables/useApi'

export const useSocialStore = defineStore('social', () => {
  const { apiGet, apiPost, apiDelete } = useApi()

  const groups = ref<GroupInfo[]>([])
  const currentGroup = ref<GroupInfo | null>(null)
  const groupMessages = ref<GroupMessage[]>([])
  const availableAgents = ref<AgentProfile[]>([])
  const loading = ref(false)

  const fetchGroups = async () => {
    loading.value = true
    try {
      const response = await apiGet<{ data: GroupInfo[] }>('/social/groups')
      groups.value = response.data || []
    } catch {
      groups.value = []
    } finally {
      loading.value = false
    }
  }

  const createGroup = async (name: string, description?: string, type?: string) => {
    const response = await apiPost<{ data: GroupInfo }>('/social/groups', {
      name,
      description: description || '',
      type: type || 'mixed',
    })
    await fetchGroups()
    return response.data
  }

  const deleteGroup = async (groupId: string) => {
    await apiDelete(`/social/groups/${groupId}`)
    if (currentGroup.value?.id === groupId) {
      currentGroup.value = null
      groupMessages.value = []
    }
    await fetchGroups()
  }

  const addAgentToGroup = async (groupId: string, agentId: string, role?: string) => {
    const response = await apiPost<{ data: GroupInfo }>(`/social/groups/${groupId}/members`, {
      agent_id: agentId,
      role: role || '成员',
    })
    await fetchGroups()
    if (currentGroup.value?.id === groupId) {
      currentGroup.value = response.data
    }
    return response.data
  }

  const removeAgentFromGroup = async (groupId: string, agentId: string) => {
    await apiDelete(`/social/groups/${groupId}/members/${agentId}`)
    await fetchGroups()
  }

  const sendGroupMessage = async (groupId: string, content: string) => {
    const response = await apiPost<{ data: GroupMessage[] }>(`/social/groups/${groupId}/messages`, {
      content,
      sender_id: 'user',
    })
    return response.data || []
  }

  const fetchAvailableAgents = async () => {
    try {
      const response = await apiGet<{ data: AgentProfile[] }>('/social/agents')
      availableAgents.value = response.data || []
    } catch {
      availableAgents.value = []
    }
  }

  const indexRAGContent = async (content: string, source: string, metadata?: Record<string, any>) => {
    const response = await apiPost<{ data: { indexed_chunks: number } }>('/social/rag/index', {
      content,
      source,
      metadata,
    })
    return response.data
  }

  const searchRAG = async (query: string, topK?: number) => {
    const response = await apiPost<{ data: any[] }>('/social/rag/search', {
      query,
      top_k: topK || 5,
    })
    return response.data || []
  }

  return {
    groups,
    currentGroup,
    groupMessages,
    availableAgents,
    loading,
    fetchGroups,
    createGroup,
    deleteGroup,
    addAgentToGroup,
    removeAgentFromGroup,
    sendGroupMessage,
    fetchAvailableAgents,
    indexRAGContent,
    searchRAG,
  }
})
