/**
 * LuomiNest 工作台对话历史
 *
 * 从 WorkbenchView.vue 拆分：收纳对话搜索、时间分组、选择/新建/删除/重命名逻辑。
 * 搜索/时间分组/重命名三件套已下沉到 useConversationListCore（与工作区共用），
 * 本文件保留工作台侧的差异：固定主 Agent、toast 反馈、会话选择/新建/删除编排。
 */
import { ref, type Ref } from 'vue'
import { i18n } from '../i18n'
import { useChatStore } from '../stores/chat'
import { useConversationListCore } from './useConversationListCore'
import { useToast } from './useToast'
import type { ConversationSearchResult } from '../types'
import type { TimeGroup } from '../components/workbench/types'
import { toErrorMessage } from '@/utils/error'

export interface UseWorkbenchHistoryOptions {
  agentId: string
}

export const useWorkbenchHistory = (options: UseWorkbenchHistoryOptions) => {
  const { agentId } = options
  const chatStore = useChatStore()
  const toast = useToast()

  const searchQuery = ref('')

  const {
    searchResults,
    isSearching,
    isSearchMode,
    timeGroups,
    renamingConvId,
    renamingTitle,
    startRename,
    confirmRename,
    cancelRename,
  } = useConversationListCore({
    searchQuery,
    getConversations: () => chatStore.conversations,
    timeGroupKeys: 'flat',
    getAgentId: () => agentId,
    renameTooLongFeedback: 'toast',
    renameFailedFeedback: 'toast',
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
      const errMsg = toErrorMessage(e)
      toast.error(i18n.global.t('chat.deleteConvFailed', { msg: errMsg }))
    }
  }

  return {
    searchQuery,
    searchResults: searchResults as Ref<ConversationSearchResult[]>,
    isSearching,
    isSearchMode,
    timeGroups: timeGroups as Ref<TimeGroup[]>,
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
