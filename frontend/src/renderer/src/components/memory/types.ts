import type { Component } from 'vue'

export interface LayerTab {
  id: string
  name: string
  sub: string
  icon: Component
  color: string
  desc: string
}

export type ConfirmAction = 'clearFacts' | 'clearKnowledge' | 'clearDailies' | 'clearSummary' | 'resetAll'

export interface MemoryStatsCategory {
  name: string
  count: number
  color: string
}

export interface MemoryStats {
  totalFacts: number
  hasProfile: boolean
  dailyCount: number
  hasKnowledge: boolean
  hasSummary: boolean
  categories: MemoryStatsCategory[]
}
