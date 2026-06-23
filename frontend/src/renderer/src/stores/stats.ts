import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '../composables/useApi'

export interface ProviderUsage {
  name: string
  requests: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface UsageRecord {
  timestamp: string
  provider: string
  model: string
  total_tokens: number
  conv_id?: string
}

export interface UsageSummary {
  total_requests: number
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  by_provider: ProviderUsage[]
  by_day: Record<string, number>
  recent: UsageRecord[]
}

export interface MemoryStats {
  user_facts: number
  agent_facts: number
  episodic_events: number
  total_memory_records: number
}

export interface StatsOverview {
  usage: UsageSummary
  conversations: number
  messages: number
  agents_count: number
  memory: MemoryStats
}

export const useStatsStore = defineStore('stats', () => {
  const { apiGet } = useApi()

  const overview = ref<StatsOverview | null>(null)
  const usageSummary = ref<UsageSummary | null>(null)
  const dailyUsage = ref<Record<string, number>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)

  // === Token 侦听器 ===
  // 实时统计 LLM 返回的字符数（前端拦截）
  const liveSessionTokens = ref<{
    prompt_chars: number
    completion_chars: number
    total_chars: number
    started_at: number
  }>({
    prompt_chars: 0,
    completion_chars: 0,
    total_chars: 0,
    started_at: Date.now(),
  })

  // 历史会话记录（最近 100 次）
  const sessionHistory = ref<Array<{
    timestamp: number
    provider: string
    model: string
    completion_chars: number
    conv_id?: string
  }>>([])

  /**
   * Token 侦听器：在 apiStream 的 onChunk 中调用
   * 拦截 LLM 返回的所有字符，实时统计
   */
  const interceptChunk = (chunk: {
    content?: string
    reasoning_content?: string
    model?: string
    provider?: string
    done?: boolean
  }, convId?: string) => {
    if (chunk.content) {
      liveSessionTokens.value.completion_chars += chunk.content.length
      liveSessionTokens.value.total_chars += chunk.content.length
    }
    if (chunk.reasoning_content) {
      liveSessionTokens.value.completion_chars += chunk.reasoning_content.length
      liveSessionTokens.value.total_chars += chunk.reasoning_content.length
    }

    // 流结束时记录到历史
    if (chunk.done) {
      sessionHistory.value.unshift({
        timestamp: Date.now(),
        provider: chunk.provider || 'unknown',
        model: chunk.model || 'unknown',
        completion_chars: liveSessionTokens.value.completion_chars,
        conv_id: convId,
      })
      if (sessionHistory.value.length > 100) {
        sessionHistory.value = sessionHistory.value.slice(0, 100)
      }
      // 重置当前会话计数
      liveSessionTokens.value = {
        prompt_chars: 0,
        completion_chars: 0,
        total_chars: 0,
        started_at: Date.now(),
      }
    }
  }

  /**
   * 记录 prompt 字符数（在发送消息时调用）
   */
  const recordPrompt = (prompt: string) => {
    liveSessionTokens.value.prompt_chars += prompt.length
    liveSessionTokens.value.total_chars += prompt.length
  }

  const totalRequests = computed(() => usageSummary.value?.total_requests ?? 0)
  const totalTokens = computed(() => usageSummary.value?.total_tokens ?? 0)
  const totalPromptTokens = computed(() => usageSummary.value?.total_prompt_tokens ?? 0)
  const totalCompletionTokens = computed(() => usageSummary.value?.total_completion_tokens ?? 0)
  const byProvider = computed(() => usageSummary.value?.by_provider ?? [])
  const byDay = computed(() => usageSummary.value?.by_day ?? {})
  const recentRecords = computed(() => usageSummary.value?.recent ?? [])

  const totalConversations = computed(() => overview.value?.conversations ?? 0)
  const totalMessages = computed(() => overview.value?.messages ?? 0)
  const agentsCount = computed(() => overview.value?.agents_count ?? 0)
  const memoryStats = computed(() => overview.value?.memory ?? { user_facts: 0, agent_facts: 0, episodic_events: 0, total_memory_records: 0 })

  async function fetchOverview(days?: number) {
    loading.value = true
    error.value = null
    try {
      const params = days ? `?days=${days}` : ''
      overview.value = await apiGet<StatsOverview>(`/stats/overview${params}`)
    } catch (e: unknown) {
      error.value = (e instanceof Error ? e.message : '') || 'Failed to fetch stats overview'
    } finally {
      loading.value = false
    }
  }

  async function fetchUsage(days?: number) {
    loading.value = true
    error.value = null
    try {
      const params = days ? `?days=${days}` : ''
      usageSummary.value = await apiGet<UsageSummary>(`/stats/usage${params}`)
    } catch (e: unknown) {
      error.value = (e instanceof Error ? e.message : '') || 'Failed to fetch usage stats'
    } finally {
      loading.value = false
    }
  }

  async function fetchDailyUsage(days: number = 7) {
    try {
      const result = await apiGet<{ by_day: Record<string, number> }>(`/stats/usage/daily?days=${days}`)
      dailyUsage.value = result?.by_day ?? {}
    } catch (e: unknown) {
      dailyUsage.value = {}
    }
  }

  async function fetchAll(days?: number) {
    loading.value = true
    error.value = null
    try {
      await Promise.all([
        fetchOverview(days),
        fetchUsage(days),
        fetchDailyUsage(days || 7),
      ])
    } finally {
      loading.value = false
    }
  }

  return {
    overview,
    usageSummary,
    dailyUsage,
    loading,
    error,
    totalRequests,
    totalTokens,
    totalPromptTokens,
    totalCompletionTokens,
    byProvider,
    byDay,
    recentRecords,
    totalConversations,
    totalMessages,
    agentsCount,
    memoryStats,
    // Token 侦听器
    liveSessionTokens,
    sessionHistory,
    interceptChunk,
    recordPrompt,
    fetchOverview,
    fetchUsage,
    fetchDailyUsage,
    fetchAll,
  }
})
