import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  GroupInfo,
  GroupMessage,
  AgentProfile,
  AgentRoleDefinition,
  CollaborationPhase,
  CollaborationSubTask,
  CollaborationEvent,
} from '../types'
import { useApi } from '../composables/useApi'

const BACKEND_URL = 'http://127.0.0.1:18000/api/v1'

export const useSocialStore = defineStore('social', () => {
  const { apiGet, apiPost, apiDelete } = useApi()

  const groups = ref<GroupInfo[]>([])
  const currentGroup = ref<GroupInfo | null>(null)
  const groupMessages = ref<GroupMessage[]>([])
  const availableAgents = ref<AgentProfile[]>([])
  const agentRoles = ref<AgentRoleDefinition[]>([])
  const loading = ref(false)

  const collaborationPhase = ref<CollaborationPhase | null>(null)
  const collaborationPlan = ref<string | null>(null)
  const collaborationTasks = ref<CollaborationSubTask[]>([])
  const collaborationActive = ref(false)
  const collaborationSessionId = ref<string | null>(null)

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
    const messages = response.data || []
    if (messages.length > 0) {
      groupMessages.value = [...groupMessages.value, ...messages]
    }
    return messages
  }

  const fetchGroupMessages = async (groupId: string) => {
    try {
      const response = await apiGet<{ data: { messages: GroupMessage[] } }>(`/social/groups/${groupId}`)
      if (response.data?.messages) {
        groupMessages.value = response.data.messages
      }
    } catch {
      groupMessages.value = []
    }
  }

  const fetchAvailableAgents = async () => {
    try {
      const response = await apiGet<{ data: AgentProfile[] }>('/social/agents')
      availableAgents.value = response.data || []
    } catch {
      availableAgents.value = []
    }
  }

  const fetchAgentRoles = async () => {
    try {
      const response = await apiGet<{ data: AgentRoleDefinition[] }>('/social/agent-roles')
      agentRoles.value = response.data || []
    } catch {
      agentRoles.value = []
    }
  }

  const collaborateStream = async (
    groupId: string,
    content: string,
    onEvent: (event: CollaborationEvent) => void,
    onError: (err: string) => void,
    onDone: () => void,
  ) => {
    collaborationActive.value = true
    collaborationPhase.value = 'analyzing'
    collaborationPlan.value = null
    collaborationTasks.value = []
    collaborationSessionId.value = null

    const controller = new AbortController()

    try {
      const resp = await fetch(`${BACKEND_URL}/social/groups/${groupId}/collaborate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content,
          sender_id: 'user',
          stream: true,
        }),
        signal: controller.signal,
      })

      if (!resp.ok) {
        const errData = await resp.json().catch(() => null)
        throw new Error(errData?.error?.message || `API error: ${resp.status}`)
      }

      const reader = resp.body?.getReader()
      if (!reader) throw new Error('No readable stream')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const dataStr = trimmed.slice(6)
          if (!dataStr.trim()) continue

          try {
            const event: CollaborationEvent = JSON.parse(dataStr)
            _handleCollaborationEvent(event)
            onEvent(event)

            if (event.type === 'session_end' || event.type === 'error') {
              collaborationActive.value = false
              if (event.type !== 'error') {
                await fetchGroups()
              }
              onDone()
              return
            }
          } catch {
            continue
          }
        }
      }

      collaborationActive.value = false
      await fetchGroups()
      onDone()
    } catch (e: any) {
      if (e.name === 'AbortError') {
        collaborationActive.value = false
        onDone()
        return
      }
      collaborationActive.value = false
      collaborationPhase.value = 'failed'
      onError(e.message)
    }
  }

  const _handleCollaborationEvent = (event: CollaborationEvent) => {
    switch (event.type) {
      case 'session_start':
        collaborationSessionId.value = event.data.session_id || null
        collaborationPhase.value = 'analyzing'
        break

      case 'phase_change':
        collaborationPhase.value = event.data.phase || null
        break

      case 'plan_created':
        collaborationPlan.value = event.data.plan || null
        break

      case 'task_started': {
        const existingIdx = collaborationTasks.value.findIndex(t => t.taskId === event.data.task_id)
        if (existingIdx >= 0) {
          collaborationTasks.value[existingIdx] = {
            ...collaborationTasks.value[existingIdx],
            status: 'running',
            startedAt: new Date().toISOString(),
          }
        } else {
          collaborationTasks.value.push({
            taskId: event.data.task_id,
            roleId: event.data.role_id || '',
            agentId: event.data.agent_id || null,
            description: event.data.description || '',
            inputContent: '',
            dependsOn: [],
            status: 'running',
            result: null,
            error: null,
            startedAt: new Date().toISOString(),
            completedAt: null,
          })
        }
        break
      }

      case 'task_agent_assigned': {
        const taskIdx = collaborationTasks.value.findIndex(t => t.taskId === event.data.task_id)
        if (taskIdx >= 0) {
          collaborationTasks.value[taskIdx] = {
            ...collaborationTasks.value[taskIdx],
            agentId: event.data.agent_id,
          }
        }
        break
      }

      case 'task_completed': {
        const completedIdx = collaborationTasks.value.findIndex(t => t.taskId === event.data.task_id)
        if (completedIdx >= 0) {
          collaborationTasks.value[completedIdx] = {
            ...collaborationTasks.value[completedIdx],
            status: 'completed',
            result: event.data.result,
            completedAt: new Date().toISOString(),
          }
        }

        const role = agentRoles.value.find(r => r.roleId === event.data.role_id)
        const agentName = event.data.agent_name || 'Agent'

        groupMessages.value.push({
          id: `collab-${event.data.task_id}-${Date.now()}`,
          senderId: event.data.agent_id || 'agent',
          senderName: agentName,
          senderType: 'agent',
          content: event.data.result || '',
          timestamp: new Date().toISOString(),
          role: role?.name || event.data.role_id,
          collaboration: {
            sessionId: collaborationSessionId.value || '',
            taskId: event.data.task_id,
            taskDescription: event.data.description,
            type: 'task_result',
          },
        })
        break
      }

      case 'task_failed': {
        const failedIdx = collaborationTasks.value.findIndex(t => t.taskId === event.data.task_id)
        if (failedIdx >= 0) {
          collaborationTasks.value[failedIdx] = {
            ...collaborationTasks.value[failedIdx],
            status: 'failed',
            error: event.data.error,
            completedAt: new Date().toISOString(),
          }
        }
        break
      }

      case 'direct_response': {
        groupMessages.value.push({
          id: `direct-${Date.now()}`,
          senderId: event.data.agent_id || 'agent',
          senderName: event.data.agent_name || 'Agent',
          senderType: 'agent',
          content: event.data.content || '',
          timestamp: new Date().toISOString(),
          role: '调度员',
        })
        break
      }

      case 'final_result': {
        groupMessages.value.push({
          id: `synthesis-${Date.now()}`,
          senderId: event.data.agent_id || 'coordinator',
          senderName: event.data.agent_name || '调度员',
          senderType: 'agent',
          content: event.data.content || '',
          timestamp: new Date().toISOString(),
          role: '调度员',
          collaboration: {
            sessionId: collaborationSessionId.value || '',
            type: 'synthesis',
          },
        })
        break
      }

      case 'error':
        collaborationPhase.value = 'failed'
        break
    }
  }

  const resetCollaboration = () => {
    collaborationPhase.value = null
    collaborationPlan.value = null
    collaborationTasks.value = []
    collaborationActive.value = false
    collaborationSessionId.value = null
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
    agentRoles,
    loading,
    collaborationPhase,
    collaborationPlan,
    collaborationTasks,
    collaborationActive,
    collaborationSessionId,
    fetchGroups,
    createGroup,
    deleteGroup,
    addAgentToGroup,
    removeAgentFromGroup,
    sendGroupMessage,
    fetchGroupMessages,
    fetchAvailableAgents,
    fetchAgentRoles,
    collaborateStream,
    resetCollaboration,
    indexRAGContent,
    searchRAG,
  }
})
