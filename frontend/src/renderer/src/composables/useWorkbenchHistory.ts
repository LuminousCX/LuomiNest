/**
 * LuomiNest 工作台对话历史
 *
 * 从 WorkbenchView.vue 拆分：收纳对话搜索、时间分组、选择/新建/删除/重命名等逻辑。
 * agentId 通过 options 传入（主 Agent 固定标识）。
 */
import { ref, computed } from 'vue'
import { useChatStore } from '../stores/chat'
import { useDebouncedSearch } from './useDebouncedSearch'
import { useToast } from './useToast'
import type { ConversationSearchResult } from '../types'
import type { TimeGroup } from '../components/workbench/types'

export interface UseWorkbenchHistoryOptions {
  agentId: string
}

export const useWorkbenchHistory = (options: UseWorkbenchHistoryOptions) => {
  const { agentId } = options
  const chatStore = useChatStore()
  const toast = useToast()

  const searchQuery = ref('')
  const { results: searchResults, isSearching } = useDebouncedSearch<ConversationSearchResult[]>(
    searchQuery,
    (q) => chatStore.searchConversations(q),
    300,
  )

  const isSearchMode = computed(() => searchQuery.value.trim().length > 0)

  const timeGroups = computed<TimeGroup[]>(() => {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const groups: TimeGroup[] = [
      { label: '今天', items: [] },
      { label: '昨天', items: [] },
      { label: '近7天', items: [] },
      { label: '更早', items: [] },
    ]

    for (const conv of chatStore.conversations) {
      const d = new Date(conv.updated_at)
      const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
      const diffDays = Math.floor((today.getTime() - target.getTime()) / 86400000)
      if (diffDays <= 0) groups[0].items.push(conv)
      else if (diffDays === 1) groups[1].items.push(conv)
      else if (diffDays <= 7) groups[2].items.push(conv)
      else groups[3].items.push(conv)
    }

    return groups.filter((g) => g.items.length > 0)
  })

  const selectConversation = (convId: string, searchKeyword?: string): void => {
    if (searchKeyword) {
      chatStore.pendingSearchKeyword = searchKeyword
      chatStore.searchScrollTarget = { convId, keyword: searchKeyword }
    }
    chatStore.loadConversation(convId)
  }

  const handleNewConversation = (): void => {
    const prevConvId = chatStore.currentConvId
    if (prevConvId) {
      chatStore.leaveCurrentConversation(prevConvId).catch(() => {})
    }
    chatStore.clearMessages()
  }

  const handleDeleteConversation = async (convId: string): Promise<void> => {
    try {
      await chatStore.deleteConversation(convId, agentId)
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e)
      toast.error(`删除对话失败：${errMsg}`)
    }
  }

  // 重命名
  const renamingConvId = ref<string | null>(null)
  const renamingTitle = ref('')

  const startRename = (convId: string, currentTitle: string): void => {
    renamingConvId.value = convId
    renamingTitle.value = currentTitle
  }

  const confirmRename = async (): Promise<void> => {
    if (!renamingConvId.value) return
    const newTitle = renamingTitle.value.trim()
    if (!newTitle) {
      renamingConvId.value = null
      return
    }
    if (newTitle.length > 200) {
      toast.warning('标题过长，请限制在 200 字符以内')
      return
    }
    const success = await chatStore.renameConversation(renamingConvId.value, newTitle, agentId)
    if (success) {
      renamingConvId.value = null
      renamingTitle.value = ''
    } else {
      toast.error('重命名对话失败，请重试')
    }
  }

  const cancelRename = (): void => {
    renamingConvId.value = null
    renamingTitle.value = ''
  }

  return {
    searchQuery,
    searchResults,
    isSearching,
    isSearchMode,
    timeGroups,
    selectConversation,
    handleNewConversation,
    handleDeleteConversation,
    renamingConvId,
    renamingTitle,
    startRename,
    confirmRename,
    cancelRename,
  }
}
