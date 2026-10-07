/**
 * LuomiNest 工作台会话列表（搜索 / 时间分组 / 批量 / 重命名）
 *
 * 从 WorkspaceView.vue 拆分。搜索/时间分组/重命名三件套已下沉到 useConversationListCore
 * （与工作台共用），本文件保留工作区侧的差异：当前 agent 维度、批量删除模式、
 * localSelectedConvId 同步、静默反馈风格。
 * localSelectedAgent / localSelectedConvId 由视图持有并传入（与消息 composable 共享）。
 * backToContacts 需要重置批量状态，故暴露 resetBatchState。
 */
import { ref, type Ref } from 'vue'
import type { AgentProfile, ConversationListItem, ConversationSearchResult } from '../types'
import { useChatStore } from '../stores/chat'
import { useChatTrashStore } from '../stores/chat-trash'
import { useConversationListCore } from './useConversationListCore'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('WorkspaceConvList')

export interface UseWorkspaceConvListOptions {
  localSelectedAgent: Ref<AgentProfile | null>
  localSelectedConvId: Ref<string | null>
}

export const useWorkspaceConvList = (options: UseWorkspaceConvListOptions) => {
  const chatStore = useChatStore()
  const chatTrashStore = useChatTrashStore()
  const { localSelectedAgent, localSelectedConvId } = options

  const convSearchQuery = ref('')

  const core = useConversationListCore({
    searchQuery: convSearchQuery,
    getConversations: () =>
      localSelectedAgent.value
        ? (chatStore.agentConversations[localSelectedAgent.value.id] || [])
        : [],
    timeGroupKeys: 'nested',
    getAgentId: () => localSelectedAgent.value?.id,
    renameTooLongFeedback: 'silent',
    renameFailedFeedback: 'silent',
    autoFocusRenameInput: true,
  })
  const selectConversation = (convId: string, searchKeyword?: string): void => {
    if (searchKeyword) {
      chatStore.pendingSearchKeyword = searchKeyword
      chatStore.searchScrollTarget = { convId, keyword: searchKeyword }
    }
    if (localSelectedAgent.value) {
      chatStore.loadConversation(convId, localSelectedAgent.value.id)
      localSelectedConvId.value = convId
    }
  }

  const handleDeleteConversation = async (convId: string): Promise<void> => {
    try {
      await chatStore.deleteConversation(convId, localSelectedAgent.value?.id)
      if (localSelectedConvId.value === convId) {
        localSelectedConvId.value = null
      }
    } catch (e: unknown) {
      logger.error('Failed to delete conversation:', e)
    }
  }

  const handleNewConversation = (): void => {
    const prevConvId = localSelectedConvId.value
    if (prevConvId) {
      chatStore.leaveCurrentConversation(prevConvId).catch(() => {})
    }
    if (localSelectedAgent.value) {
      chatStore.clearMessages(localSelectedAgent.value.id)
    }
    localSelectedConvId.value = null
  }

  // —— 批量模式（工作区独有）——
  const batchMode = ref(false)
  const selectedIds = ref<Set<string>>(new Set())

  const resetBatchState = (): void => {
    batchMode.value = false
    selectedIds.value = new Set()
  }

  const toggleBatchMode = (): void => {
    batchMode.value = !batchMode.value
    if (!batchMode.value) {
      selectedIds.value = new Set()
    }
  }

  const toggleSelect = (convId: string): void => {
    const next = new Set(selectedIds.value)
    if (next.has(convId)) {
      next.delete(convId)
    } else {
      next.add(convId)
    }
    selectedIds.value = next
  }

  const selectAll = (): void => {
    const convs = localSelectedAgent.value
      ? (chatStore.agentConversations[localSelectedAgent.value.id] || [])
      : []
    const allIds = convs.map((c: ConversationListItem) => c.id)
    if (selectedIds.value.size === allIds.length) {
      selectedIds.value = new Set()
    } else {
      selectedIds.value = new Set(allIds)
    }
  }

  const handleBatchDelete = async (): Promise<void> => {
    if (selectedIds.value.size === 0) return
    try {
      const agentId = localSelectedAgent.value?.id
      await chatTrashStore.batchSoftDelete(Array.from(selectedIds.value), agentId, () => chatStore.fetchConversations(agentId))
      selectedIds.value = new Set()
      batchMode.value = false
    } catch (e: unknown) {
      logger.error('Failed to batch delete:', e)
    }
  }

  return {
    convSearchQuery,
    searchResults: core.searchResults as Ref<ConversationSearchResult[]>,
    isSearching: core.isSearching,
    isSearchMode: core.isSearchMode,
    timeGroups: core.timeGroups,
    batchMode,
    selectedIds,
    renamingConvId: core.renamingConvId,
    renamingTitle: core.renamingTitle,
    selectConversation,
    handleDeleteConversation,
    handleNewConversation,
    toggleBatchMode,
    toggleSelect,
    selectAll,
    handleBatchDelete,
    resetBatchState,
    startRename: core.startRename,
    confirmRename: core.confirmRename,
    cancelRename: core.cancelRename,
  }
}
