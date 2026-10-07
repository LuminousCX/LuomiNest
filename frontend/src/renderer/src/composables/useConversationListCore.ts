/**
 * 会话列表核心逻辑（搜索防抖 / 时间分组 / 重命名三件套）。
 *
 * useWorkbenchHistory（工作台）与 useWorkspaceConvList（工作区）原本是同一套逻辑的两份拷贝
 * （调查报告：文档/2026年10月8日前端清理调查/重复造轮子清查报告.md §N1/P2），
 * 差异仅在：i18n 键风格、反馈方式（toast/静默）、agentId 来源、批量模式（工作区独有，留外层）。
 */
import { ref, computed, nextTick, type Ref } from 'vue'
import type { ConversationListItem, ConversationSearchResult } from '../types'
import { useChatStore } from '../stores/chat'
import { useDebouncedSearch } from './useDebouncedSearch'
import { useToast } from './useToast'
import { i18n } from '../i18n'

/** 时间分组（今天/昨天/近7天/更早，空组被过滤） */
export interface ConversationTimeGroup {
  label: string
  items: ConversationListItem[]
}

export interface UseConversationListCoreOptions {
  /** 防抖搜索输入框绑定（调用方持有，绑定输入框） */
  searchQuery: Ref<string>
  /** 会话清单来源（工作台=chatStore.conversations；工作区=当前 agent 的会话） */
  getConversations: () => ConversationListItem[]
  /**
   * 时间分组 i18n 键风格。两套键并存（zh-CN 文案一致）：
   * flat = chat.today / chat.yesterday / chat.last7Days / chat.earlier
   * nested = chat.timeGroups.today / chat.timeGroups.yesterday / chat.timeGroups.week / chat.timeGroups.earlier
   */
  timeGroupKeys: 'flat' | 'nested'
  /** 当前 agentId（重命名请求参数；工作台固定主 Agent，工作区取当前选中） */
  getAgentId: () => string | undefined
  /** 重命名超长（>200 字）反馈：toast 提示（工作台）或静默复位（工作区） */
  renameTooLongFeedback: 'toast' | 'silent'
  /** 重命名失败反馈：toast（工作台）或静默（工作区） */
  renameFailedFeedback: 'toast' | 'silent'
  /** startRename 后自动聚焦重命名输入框（工作区的 querySelector 行为） */
  autoFocusRenameInput?: boolean
}

export const useConversationListCore = (options: UseConversationListCoreOptions) => {
  const chatStore = useChatStore()
  const toast = useToast()

  const { results: searchResults, isSearching } = useDebouncedSearch<ConversationSearchResult[]>(
    options.searchQuery,
    (q, signal) => chatStore.searchConversations(q, undefined, signal),
    300,
  )

  const isSearchMode = computed(() => options.searchQuery.value.trim().length > 0)

  const timeGroups = computed<ConversationTimeGroup[]>(() => {
    const k = (flatSuffix: string, nestedSuffix: string): string =>
      options.timeGroupKeys === 'flat' ? `chat.${flatSuffix}` : `chat.timeGroups.${nestedSuffix}`
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())

    const groups: ConversationTimeGroup[] = [
      { label: i18n.global.t(k('today', 'today')), items: [] },
      { label: i18n.global.t(k('yesterday', 'yesterday')), items: [] },
      { label: i18n.global.t(k('last7Days', 'week')), items: [] },
      { label: i18n.global.t(k('earlier', 'earlier')), items: [] },
    ]

    for (const conv of options.getConversations()) {
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

  // —— 重命名三件套 ——
  const renamingConvId = ref<string | null>(null)
  const renamingTitle = ref('')

  const startRename = (convId: string, currentTitle: string): void => {
    renamingConvId.value = convId
    renamingTitle.value = currentTitle
    if (options.autoFocusRenameInput) {
      nextTick(() => {
        const input = document.querySelector('.conv-item-rename-input') as HTMLInputElement | null
        if (input) {
          input.focus()
          input.select()
        }
      })
    }
  }

  const confirmRename = async (): Promise<void> => {
    if (!renamingConvId.value) return
    const newTitle = renamingTitle.value.trim()
    if (!newTitle) {
      renamingConvId.value = null
      return
    }
    if (newTitle.length > 200) {
      if (options.renameTooLongFeedback === 'toast') {
        toast.warning(i18n.global.t('chat.titleTooLong'))
      }
      return
    }
    const success = await chatStore.renameConversation(renamingConvId.value, newTitle, options.getAgentId())
    if (success) {
      renamingConvId.value = null
      renamingTitle.value = ''
    } else if (options.renameFailedFeedback === 'toast') {
      toast.error(i18n.global.t('chat.renameFailed'))
    }
  }

  const cancelRename = (): void => {
    renamingConvId.value = null
    renamingTitle.value = ''
  }

  return {
    searchResults,
    isSearching,
    isSearchMode,
    timeGroups,
    renamingConvId,
    renamingTitle,
    startRename,
    confirmRename,
    cancelRename,
  }
}
