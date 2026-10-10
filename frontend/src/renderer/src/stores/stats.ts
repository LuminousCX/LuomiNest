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
  /** 按天 token 求和（新增，向后兼容，可能缺省） */
  tokens_by_day?: Record<string, number>
  recent: UsageRecord[]
}

export interface UsageComparison {
  current: {
    total_requests: number
    total_tokens: number
    by_day: Record<string, number>
  }
  previous: {
    total_requests: number
    total_tokens: number
    by_day: Record<string, number>
  }
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

/**
 * 查询窗口：
 * - { days: n }              最近 n 天
 * - { start, end }           任意闭区间（'YYYY-MM-DD'）
 * - {} / undefined           全部
 */
export interface StatsRange {
  days?: number | null
  start?: string | null
  end?: string | null
}

interface DailyUsageResponse {
  by_day: Record<string, number>
  tokens_by_day?: Record<string, number>
}

const normalizeRange = (range?: number | StatsRange): StatsRange | undefined =>
  typeof range === 'number' ? { days: range } : range

const buildRangeQuery = (range?: StatsRange): string => {
  if (!range) return ''
  const parts: string[] = []
  if (range.days) parts.push(`days=${range.days}`)
  if (range.start) parts.push(`start_date=${range.start}`)
  if (range.end) parts.push(`end_date=${range.end}`)
  return parts.length ? `?${parts.join('&')}` : ''
}

export const useStatsStore = defineStore('stats', () => {
  const { apiGet } = useApi()

  const overview = ref<StatsOverview | null>(null)
  const usageSummary = ref<UsageSummary | null>(null)
  /** 当前区间的按天调用量（直方图用） */
  const dailyUsage = ref<Record<string, number>>({})
  /** 当前区间的按天 token（直方图 tooltip 用） */
  const tokensByDay = ref<Record<string, number>>({})
  /** 最近一年的按天调用量（活跃度热力图用，与区间选择无关） */
  const heatmapByDay = ref<Record<string, number>>({})
  const heatmapTokensByDay = ref<Record<string, number>>({})
  const usageComparison = ref<UsageComparison | null>(null)
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

  async function fetchOverview(range?: number | StatsRange) {
    loading.value = true
    error.value = null
    try {
      // overview 只支持 days 窗口；任意区间/全部时不带参数
      const normalized = normalizeRange(range)
      const daysOnly = typeof normalized?.days === 'number' ? normalized.days : undefined
      const params = daysOnly ? `?days=${daysOnly}` : ''
      overview.value = await apiGet<StatsOverview>(`/stats/overview${params}`)
    } catch (e: unknown) {
      error.value = (e instanceof Error ? e.message : '') || 'Failed to fetch stats overview'
    } finally {
      loading.value = false
    }
  }

  async function fetchUsage(range?: number | StatsRange) {
    loading.value = true
    error.value = null
    try {
      const normalized = normalizeRange(range)
      usageSummary.value = await apiGet<UsageSummary>(`/stats/usage${buildRangeQuery(normalized)}`)
    } catch (e: unknown) {
      error.value = (e instanceof Error ? e.message : '') || 'Failed to fetch usage stats'
    } finally {
      loading.value = false
    }
  }

  async function fetchDailyUsage(range?: number | StatsRange) {
    try {
      const normalized = normalizeRange(range)
      const result = await apiGet<DailyUsageResponse>(`/stats/usage/daily${buildRangeQuery(normalized)}`)
      dailyUsage.value = result?.by_day ?? {}
      tokensByDay.value = result?.tokens_by_day ?? {}
    } catch (e: unknown) {
      dailyUsage.value = {}
      tokensByDay.value = {}
    }
  }

  /** 热力图固定拉取最近一年，不随区间选择变化 */
  async function fetchHeatmapUsage() {
    try {
      const result = await apiGet<DailyUsageResponse>('/stats/usage/daily?days=365')
      heatmapByDay.value = result?.by_day ?? {}
      heatmapTokensByDay.value = result?.tokens_by_day ?? {}
    } catch (e: unknown) {
      heatmapByDay.value = {}
      heatmapTokensByDay.value = {}
    }
  }

  async function fetchComparison(range?: number | StatsRange) {
    try {
      const normalized = normalizeRange(range)
      // 「全部」没有可比区间
      if (!normalized || (!normalized.days && !(normalized.start && normalized.end))) {
        usageComparison.value = null
        return
      }
      usageComparison.value = await apiGet<UsageComparison>(`/stats/usage/compare${buildRangeQuery(normalized)}`)
    } catch (e: unknown) {
      usageComparison.value = null
    }
  }

  async function fetchAll(range?: number | StatsRange) {
    loading.value = true
    error.value = null
    try {
      await Promise.all([
        fetchOverview(range),
        fetchUsage(range),
        fetchDailyUsage(range),
        fetchComparison(range),
        fetchHeatmapUsage(),
      ])
    } finally {
      loading.value = false
    }
  }

  return {
    overview,
    usageSummary,
    dailyUsage,
    tokensByDay,
    heatmapByDay,
    heatmapTokensByDay,
    usageComparison,
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
    fetchHeatmapUsage,
    fetchComparison,
    fetchAll,
  }
})
