import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { TrashListItem } from '../types'
import { useApi } from '../composables/useApi'

export const useChatTrashStore = defineStore('chat-trash', () => {
  const { apiGet, apiPost, apiDelete } = useApi()

  const trashItems = ref<TrashListItem[]>([])

  const getAgentId = (agentId?: string): string => agentId || ''

  const fetchTrash = async (agentId?: string) => {
    const targetAgentId = getAgentId(agentId)
    if (!targetAgentId) return

    try {
      const query = `?agent_id=${targetAgentId}`
      trashItems.value = await apiGet<TrashListItem[]>(`/chat/trash${query}`)
    } catch (error) {
      console.warn('[ChatTrashStore] Failed to fetch trash:', error)
      trashItems.value = []
    }
  }

  const batchSoftDelete = async (convIds: string[], agentId?: string, onRefresh?: () => Promise<void>) => {
    const targetAgentId = getAgentId(agentId)
    if (!targetAgentId || convIds.length === 0) return

    try {
      await apiPost(`/chat/conversations/batch-delete`, {
        ids: convIds,
        agent_id: targetAgentId,
      })
      if (onRefresh) await onRefresh()
      await fetchTrash(targetAgentId)
    } catch (error) {
      console.warn('[ChatTrashStore] Batch soft delete failed:', error)
    }
  }

  const restoreConversation = async (convId: string, agentId?: string, onRefresh?: () => Promise<void>) => {
    const targetAgentId = getAgentId(agentId)
    if (!targetAgentId) return

    try {
      await apiPost(`/chat/trash/${convId}/restore`, {})
      if (onRefresh) await onRefresh()
      await fetchTrash(targetAgentId)
    } catch (error) {
      console.warn('[ChatTrashStore] Failed to restore conversation:', error)
    }
  }

  const batchRestore = async (convIds: string[], agentId?: string, onRefresh?: () => Promise<void>) => {
    const targetAgentId = getAgentId(agentId)
    if (!targetAgentId || convIds.length === 0) return

    try {
      await apiPost(`/chat/trash/batch-restore`, {
        ids: convIds,
        agent_id: targetAgentId,
      })
      if (onRefresh) await onRefresh()
      await fetchTrash(targetAgentId)
    } catch (error) {
      console.warn('[ChatTrashStore] Batch restore failed:', error)
    }
  }

  const permanentDeleteConversation = async (convId: string, agentId?: string) => {
    const targetAgentId = getAgentId(agentId)
    if (!targetAgentId) return

    try {
      await apiDelete(`/chat/trash/${convId}`)
      await fetchTrash(targetAgentId)
    } catch (error) {
      console.warn('[ChatTrashStore] Failed to permanently delete conversation:', error)
    }
  }

  const batchPermanentDelete = async (convIds: string[], agentId?: string) => {
    const targetAgentId = getAgentId(agentId)
    if (!targetAgentId || convIds.length === 0) return

    try {
      await apiPost(`/chat/trash/batch-delete`, {
        ids: convIds,
        agent_id: targetAgentId,
      })
      await fetchTrash(targetAgentId)
    } catch (error) {
      console.warn('[ChatTrashStore] Batch permanent delete failed:', error)
    }
  }

  const emptyTrash = async (agentId?: string) => {
    const targetAgentId = getAgentId(agentId)
    if (!targetAgentId) return

    try {
      const query = `?agent_id=${targetAgentId}`
      await apiDelete(`/chat/trash${query}`)
      trashItems.value = []
    } catch (error) {
      console.warn('[ChatTrashStore] Failed to empty trash:', error)
    }
  }

  return {
    trashItems,
    fetchTrash,
    batchSoftDelete,
    restoreConversation,
    batchRestore,
    permanentDeleteConversation,
    batchPermanentDelete,
    emptyTrash,
  }
})
