import type { ConversationListItem, ConversationSearchResult } from '../../types'

export type ContactType = 'agent' | 'group'

export interface TimeGroup {
  label: string
  items: ConversationListItem[]
}

export type { ConversationListItem, ConversationSearchResult }
