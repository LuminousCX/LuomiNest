/**
 * LuomiNest 工作台会话列表（搜索 / 时间分组 / 批量 / 重命名）
 *
 * 从 WorkspaceView.vue 拆分：收纳会话搜索、时间分组、批量删除、重命名等逻辑。
 * localSelectedAgent / localSelectedConvId 由视图持有并传入（与消息 composable 共享）。
 * backToContacts 需要重置批量状态，故暴露 resetBatchState。
 */
import { ref, computed, nextTick } from 'vue'
import type { Ref } from 'vue'
import type { AgentProfile, ConversationListItem, ConversationSearchResult } from '../types'
import { useChatStore } from '../stores/chat'
import { useChatTrashStore } from '../stores/chat-trash'
import { useDebouncedSearch } from './useDebouncedSearch'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('WorkspaceConvList')

interface TimeGroup {
  label: string
  items: ConversationListItem[]
}

const TIME_GROUPS: readonly string[] = ['今天', '昨天', '近7天', '更早']

export interface UseWorkspaceConvListOptions {
  localSelectedAgent: Ref<AgentProfile | null>
  localSelectedConvId: Ref<string | null>
}

export const useWorkspaceConvList = (options: UseWorkspaceConvListOptions) => {
  const chatStore = useChatStore()
  const chatTrashStore = useChatTrashStore()
  const { localSelectedAgent, localSelectedConvId } = options

  const convSearchQuery = ref('')
  const { results: searchResults, isSearching } = useDebouncedSearch<ConversationSearchResult[]>(
    convSearchQuery,
    (q) => chatStore.searchConversations(q),
    300,
  )

  const isSearchMode = computed(() => convSearchQuery.value.trim().length > 0)

  const timeGroups = computed<TimeGroup[]>(() => {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())

    const groups: TimeGroup[] = TIME_GROUPS.map(label => ({ label, items: [] }))

    const convs = localSelectedAgent.value
      ? (chatStore.agentConversations[localSelectedAgent.value.id] || [])
      : []
    for (const conv of convs) {
      const d = new Date(conv.updated_at)
      const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
      const diffDays = Math.floor((today.getTime() - target.getTime()) / 86400000)

      if (diffDays <= 0) groups[0].items.push(conv)
      else if (diffDays === 1) groups[1].items.push(conv)
      else if (diffDays <= 7) groups[2].items.push(conv)
      else groups[3].items.push(conv)
    }

    return groups.filter(g => g.items.length > 0)
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

  // —— 批量模式 ——
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

  // —— 重命名 ——
  const renamingConvId = ref<string | null>(null)
  const renamingTitle = ref('')

  const startRename = (convId: string, currentTitle: string): void => {
    renamingConvId.value = convId
    renamingTitle.value = currentTitle
    nextTick(() => {
      const input = document.querySelector('.conv-item-rename-input') as HTMLInputElement | null
      if (input) {
        input.focus()
        input.select()
      }
    })
  }

  const confirmRename = async (): Promise<void> => {
    if (!renamingConvId.value) return
    const newTitle = renamingTitle.value.trim()
    if (!newTitle) {
      renamingConvId.value = null
      return
    }
    if (newTitle.length > 200) {
      return
    }
    const success = await chatStore.renameConversation(renamingConvId.value, newTitle, localSelectedAgent.value?.id)
    if (success) {
      renamingConvId.value = null
      renamingTitle.value = ''
    }
  }

  const cancelRename = (): void => {
    renamingConvId.value = null
    renamingTitle.value = ''
  }

  return {
    convSearchQuery,
    searchResults,
    isSearching,
    isSearchMode,
    timeGroups,
    batchMode,
    selectedIds,
    renamingConvId,
    renamingTitle,
    selectConversation,
    handleDeleteConversation,
    handleNewConversation,
    toggleBatchMode,
    toggleSelect,
    selectAll,
    handleBatchDelete,
    resetBatchState,
    startRename,
    confirmRename,
    cancelRename,
  }
}
