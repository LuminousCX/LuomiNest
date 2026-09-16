import type { ConversationListItem, ConversationSearchResult } from '../../types'

/** 联系人类型：本地 Agent / 本地群聊 / 云端群（服务端未上线时降级空态） */
export type ContactType = 'agent' | 'group' | 'cloud-group'

export interface TimeGroup {
  label: string
  items: ConversationListItem[]
}

export type { ConversationListItem, ConversationSearchResult }
