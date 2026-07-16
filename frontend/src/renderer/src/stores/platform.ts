import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  PlatformAdapterType, PlatformInstance, PlatformConversation, PlatformStats,
  PlatformLogEntry, PlatformLogSummary, MainAgentInfo,
  PlatformMessage, PlatformConversationDetail, PlatformModelConfig, PlatformModelConfigResponse,
} from '../types'
import { useApi } from '../composables/useApi'
import { useToast } from '../composables/useToast'

interface RawLogEntry {
  id: string
  timestamp: string
  level: string
  event: string
  message: string
  instance_id?: string
  instanceId?: string
  adapter_type?: string
  adapterType?: string
  details?: Record<string, unknown>
}

interface RawAdapterType {
  name: string
  display_name?: string
  displayName?: string
  description: string
  icon: string
  category: string
  config_template?: Record<string, unknown>
  configTemplate?: Record<string, unknown>
  config_metadata?: Record<string, unknown>
  configMetadata?: Record<string, unknown>
  support_streaming?: boolean
  supportStreaming?: boolean
  support_proactive?: boolean
  supportProactive?: boolean
}

interface RawInstance {
  id: string
  adapter_type?: string
  adapterType?: string
  name: string
  config?: Record<string, unknown>
  status?: string
  enable?: boolean
  message_count?: number
  messageCount?: number
  last_sync?: string
  lastSync?: string
  error_message?: string
  errorMessage?: string
  icon?: string
  category?: string
  display_name?: string
  displayName?: string
  created_at?: string
  createdAt?: string
  updated_at?: string
  updatedAt?: string
  model_config?: Record<string, unknown>
  modelConfig?: Record<string, unknown>
}

interface RawStatsData {
  totalPlatforms?: number
  activeConnections?: number
  totalMessages?: number
}

interface RawStatsResponse {
  data?: RawStatsData
  totalPlatforms?: number
  activeConnections?: number
  totalMessages?: number
}

interface RawConversation {
  id: string
  platform_instance_id?: string
  platformInstanceId?: string
  platform_name?: string
  platformName?: string
  title?: string
  preview?: string
  time?: string
  message_count?: number
  messageCount?: number
}

interface RawLogsResponse {
  data?: { entries?: RawLogEntry[]; total?: number }
  entries?: RawLogEntry[]
  total?: number
}

interface RawLogSummaryData {
  totalEntries?: number
  totalInstances?: number
  byLevel?: Record<string, number>
}

interface RawLogSummaryResponse {
  data?: RawLogSummaryData
  totalEntries?: number
  totalInstances?: number
  byLevel?: Record<string, number>
}

interface RawMessage {
  id: string
  role: string
  content: string
  timestamp?: string
  sender_name?: string
  senderName?: string
  is_group?: boolean
  isGroup?: boolean
  image_urls?: string[]
  imageUrls?: string[]
  model?: string
  provider?: string
}

interface RawConversationDetail {
  conversation_id?: string
  conversationId?: string
  title?: string
  instance_id?: string
  instanceId?: string
  platform_name?: string
  platformName?: string
  sender_name?: string
  senderName?: string
  is_group?: boolean
  isGroup?: boolean
  messages?: RawMessage[]
  message_count?: number
  messageCount?: number
}

interface RawModelConfigResponse {
  data?: PlatformModelConfigResponse
  instance_id?: string
  instanceId?: string
  is_overridden?: boolean
  isOverridden?: boolean
  instance_config?: PlatformModelConfig
  instanceConfig?: PlatformModelConfig
  main_agent?: PlatformModelConfigResponse['mainAgent']
  mainAgent?: PlatformModelConfigResponse['mainAgent']
  effective?: PlatformModelConfigResponse['effective']
  category?: string
}

export const usePlatformStore = defineStore('platform', () => {
  const { apiGet, apiPost, apiPatch, apiDelete } = useApi()

  const adapterTypes = ref<PlatformAdapterType[]>([])
  const instances = ref<PlatformInstance[]>([])
  const conversations = ref<PlatformConversation[]>([])
  const logs = ref<PlatformLogEntry[]>([])
  const logTotal = ref(0)
  const logSummary = ref<PlatformLogSummary>({ totalEntries: 0, totalInstances: 0, byLevel: {} })
  const stats = ref<PlatformStats>({ totalPlatforms: 0, activeConnections: 0, totalMessages: 0 })
  const mainAgent = ref<MainAgentInfo | null>(null)
  const mainAgentError = ref<string | null>(null)
  const loading = ref(false)
  const selectedInstanceId = ref<string | null>(null)
  const logLevelFilter = ref<string | null>(null)
  const selectedConversationId = ref<string | null>(null)
  const selectedConversationDetail = ref<PlatformConversationDetail | null>(null)
  const conversationLoading = ref(false)
  const instanceModelConfig = ref<PlatformModelConfigResponse | null>(null)

  const activeInstances = computed(() => instances.value.filter(i => i.status === 'running'))
  const disconnectedInstances = computed(() => instances.value.filter(i => i.status !== 'running'))

  const selectedInstance = computed(() =>
    instances.value.find(i => i.id === selectedInstanceId.value) || null
  )

  const selectedConversations = computed(() =>
    conversations.value.filter(c => c.platformInstanceId === selectedInstanceId.value)
  )

  const selectedInstanceLogs = computed(() => {
    if (!selectedInstanceId.value) return logs.value
    return logs.value.filter(l => l.instanceId === selectedInstanceId.value)
  })

  const fetchAdapterTypes = async () => {
    try {
      const data = await apiGet<RawAdapterType[]>('/platforms/types')
      adapterTypes.value = data.map(t => ({
        name: t.name,
        displayName: t.display_name || t.displayName || '',
        description: t.description,
        icon: t.icon,
        category: t.category,
        configTemplate: t.config_template || t.configTemplate || {},
        configMetadata: (t.config_metadata || t.configMetadata || {}) as PlatformAdapterType['configMetadata'],
        supportStreaming: t.support_streaming ?? t.supportStreaming ?? false,
        supportProactive: t.support_proactive ?? t.supportProactive ?? true,
      }))
    } catch {
      adapterTypes.value = []
    }
  }

  const fetchInstances = async () => {
    loading.value = true
    try {
      const data = await apiGet<RawInstance[]>('/platforms/instances')
      instances.value = data.map(i => ({
        id: i.id,
        adapterType: i.adapter_type || i.adapterType || '',
        name: i.name,
        config: i.config || {},
        status: (i.status || 'stopped') as PlatformInstance['status'],
        enable: i.enable ?? true,
        messageCount: i.message_count ?? i.messageCount ?? 0,
        lastSync: i.last_sync || i.lastSync || '',
        errorMessage: i.error_message || i.errorMessage || '',
        icon: i.icon || 'Globe',
        category: i.category || 'general',
        displayName: i.display_name || i.displayName || i.adapter_type || i.adapterType || '',
        createdAt: i.created_at || i.createdAt || '',
        updatedAt: i.updated_at || i.updatedAt || '',
        modelConfig: (i.model_config || i.modelConfig || {}) as PlatformModelConfig,
      }))
    } catch {
      instances.value = []
    } finally {
      loading.value = false
    }
  }

  const fetchStats = async () => {
    try {
      const result = await apiGet<RawStatsResponse>('/platforms/stats')
      stats.value = {
        totalPlatforms: result.data?.totalPlatforms ?? result.totalPlatforms ?? 0,
        activeConnections: result.data?.activeConnections ?? result.activeConnections ?? 0,
        totalMessages: result.data?.totalMessages ?? result.totalMessages ?? 0,
      }
    } catch {
      const total = instances.value.length
      const active = instances.value.filter(i => i.status === 'running').length
      const messages = instances.value.reduce((s, i) => s + i.messageCount, 0)
      stats.value = { totalPlatforms: total, activeConnections: active, totalMessages: messages }
    }
  }

  const fetchConversations = async (instanceId: string) => {
    try {
      const data = await apiGet<RawConversation[]>(`/platforms/instances/${instanceId}/conversations`)
      const mapped = data.map(c => ({
        id: c.id,
        platformInstanceId: c.platform_instance_id || c.platformInstanceId || instanceId,
        platformName: c.platform_name || c.platformName || '',
        title: c.title || '',
        preview: c.preview || '',
        time: c.time || '',
        messageCount: c.message_count ?? c.messageCount ?? 0,
      }))
      conversations.value = conversations.value.filter(c => c.platformInstanceId !== instanceId).concat(mapped)
    } catch {
      // conversations will remain as-is
    }
  }

  const fetchConversationMessages = async (instanceId: string, conversationId: string) => {
    conversationLoading.value = true
    try {
      const result = await apiGet<RawConversationDetail | { data: RawConversationDetail }>(
        `/platforms/instances/${instanceId}/conversations/${conversationId}/messages`
      )
      const data = (result as { data?: RawConversationDetail })?.data || (result as RawConversationDetail)
      selectedConversationDetail.value = {
        conversationId: data.conversation_id || data.conversationId || conversationId,
        title: data.title || '',
        instanceId: data.instance_id || data.instanceId || instanceId,
        platformName: data.platform_name || data.platformName || '',
        senderName: data.sender_name || data.senderName || '',
        isGroup: data.is_group ?? data.isGroup ?? false,
        messages: (data.messages || []).map(m => ({
          id: m.id,
          role: m.role as PlatformMessage['role'],
          content: m.content,
          timestamp: m.timestamp || '',
          senderName: m.sender_name || m.senderName || '',
          isGroup: m.is_group ?? m.isGroup ?? false,
          imageUrls: m.image_urls || m.imageUrls || [],
          model: m.model || '',
          provider: m.provider || '',
        })),
        messageCount: data.message_count ?? data.messageCount ?? 0,
      }
      selectedConversationId.value = conversationId
    } catch {
      selectedConversationDetail.value = null
    } finally {
      conversationLoading.value = false
    }
  }

  const fetchInstanceModelConfig = async (instanceId: string) => {
    try {
      const result = await apiGet<RawModelConfigResponse>(`/platforms/instances/${instanceId}/model_config`)
      const data = (result as { data?: PlatformModelConfigResponse })?.data || (result as PlatformModelConfigResponse)
      instanceModelConfig.value = {
        instanceId: data.instanceId || instanceId,
        isOverridden: data.isOverridden ?? false,
        instanceConfig: data.instanceConfig || {},
        mainAgent: data.mainAgent,
        effective: data.effective,
        category: data.category || '',
      }
    } catch {
      instanceModelConfig.value = null
    }
  }

  const updateInstanceModelConfig = async (instanceId: string, updates: PlatformModelConfig) => {
    const body: Record<string, unknown> = {}
    if (updates.provider !== undefined) body.provider = updates.provider || null
    if (updates.model !== undefined) body.model = updates.model || null
    if (updates.systemPrompt !== undefined) body.system_prompt = updates.systemPrompt || null
    if (updates.temperature !== undefined) body.temperature = updates.temperature
    if (updates.maxTokens !== undefined) body.max_tokens = updates.maxTokens
    await apiPatch(`/platforms/instances/${instanceId}/model_config`, body)
    await fetchInstanceModelConfig(instanceId)
    await fetchInstances()
  }

  const fetchLogs = async (instanceId?: string, level?: string | null) => {
    try {
      const id = instanceId || selectedInstanceId.value
      const lvl = level ?? logLevelFilter.value
      if (id) {
        const result = await apiGet<RawLogsResponse>(`/platforms/instances/${id}/logs?limit=200${lvl ? `&level=${lvl}` : ''}`)
        const data = result.data || result
        logs.value = (data.entries || []).map((l: RawLogEntry) => ({
          id: l.id,
          timestamp: l.timestamp,
          level: l.level as PlatformLogEntry['level'],
          event: l.event,
          message: l.message,
          instanceId: l.instance_id || l.instanceId || id,
          adapterType: l.adapter_type || l.adapterType || '',
          details: l.details || {},
        }))
        logTotal.value = data.total || 0
      } else {
        const result = await apiGet<RawLogsResponse>(`/platforms/logs?limit=200${lvl ? `&level=${lvl}` : ''}`)
        const data = result.data || result
        logs.value = (data.entries || []).map((l: RawLogEntry) => ({
          id: l.id,
          timestamp: l.timestamp,
          level: l.level as PlatformLogEntry['level'],
          event: l.event,
          message: l.message,
          instanceId: l.instance_id || l.instanceId || '',
          adapterType: l.adapter_type || l.adapterType || '',
          details: l.details || {},
        }))
        logTotal.value = data.total || 0
      }
    } catch {
      logs.value = []
      logTotal.value = 0
    }
  }

  const fetchLogSummary = async () => {
    try {
      const result = await apiGet<RawLogSummaryResponse>('/platforms/logs/summary')
      const data = result.data || result
      logSummary.value = {
        totalEntries: data.totalEntries ?? 0,
        totalInstances: data.totalInstances ?? 0,
        byLevel: data.byLevel ?? {},
      }
    } catch {
      logSummary.value = { totalEntries: 0, totalInstances: 0, byLevel: {} }
    }
  }

  interface RawMainAgentInfo {
    provider?: string
    provider_name?: string
    providerName?: string
    model?: string
    supports_multimodal?: boolean
    supportsMultimodal?: boolean
    system_prompt?: string
    systemPrompt?: string
    temperature?: number
    max_tokens?: number
    maxTokens?: number
  }

  // 模块级标记：记录上次已弹 toast 的错误信息，避免页面切换时重复弹窗
  let _lastMainAgentToastMsg: string | null = null

  const fetchMainAgent = async () => {
    const toast = useToast()
    try {
      const result = await apiGet<{ data?: RawMainAgentInfo } | RawMainAgentInfo>('/platforms/main_agent')
      const data = (result as { data?: RawMainAgentInfo })?.data || (result as RawMainAgentInfo)
      mainAgent.value = {
        provider: data.provider || '',
        providerName: data.provider_name || data.providerName || data.provider || '',
        model: data.model || '',
        supportsMultimodal: data.supports_multimodal ?? data.supportsMultimodal ?? false,
        systemPrompt: data.system_prompt || data.systemPrompt || '',
        temperature: data.temperature ?? 0.7,
        maxTokens: data.max_tokens ?? data.maxTokens ?? 4096,
      }
      mainAgentError.value = null
      _lastMainAgentToastMsg = null
    } catch (e: unknown) {
      mainAgent.value = null
      const msg = (e instanceof Error ? e.message : String(e)) || '未知错误'
      mainAgentError.value = msg
      // 仅当错误信息变化时弹 toast，避免页面切换时重复打扰
      if (_lastMainAgentToastMsg !== msg) {
        _lastMainAgentToastMsg = msg
        toast.warning(`主 Agent 配置加载失败：${msg}。请在设置中检查 AI 模型配置。`, 5000)
      }
    }
  }

  const updateMainAgent = async (updates: Partial<MainAgentInfo>) => {
    const toast = useToast()
    const body: Record<string, unknown> = {}
    if (updates.provider !== undefined) body.provider = updates.provider
    if (updates.model !== undefined) body.model = updates.model
    if (updates.systemPrompt !== undefined) body.system_prompt = updates.systemPrompt
    if (updates.temperature !== undefined) body.temperature = updates.temperature
    if (updates.maxTokens !== undefined) body.max_tokens = updates.maxTokens
    try {
      await apiPatch('/platforms/main_agent', body)
      await fetchMainAgent()
      toast.success('主 Agent 配置已更新')
    } catch (e: unknown) {
      toast.error(`更新失败：${(e instanceof Error ? e.message : String(e)) || '未知错误'}`)
      throw e
    }
  }

  const createNewConversation = async (instanceId: string) => {
    try {
      await apiPost(`/platforms/instances/${instanceId}/conversations/new`, {})
      await fetchConversations(instanceId)
    } catch (e: unknown) {
      const toast = useToast()
      const msg = (e instanceof Error ? e.message : String(e)) || '未知错误'
      toast.error(`创建对话失败：${msg}`)
      throw e
    }
  }

  const clearLogs = async (instanceId: string) => {
    await apiDelete(`/platforms/instances/${instanceId}/logs`)
    await fetchLogs(instanceId)
  }

  const createInstance = async (params: { adapterType: string; name: string; config?: Record<string, unknown>; enable?: boolean }) => {
    const result = await apiPost<Record<string, unknown>>('/platforms/instances', {
      adapter_type: params.adapterType,
      name: params.name,
      config: params.config || {},
      enable: params.enable ?? true,
    })
    await fetchInstances()
    await fetchStats()
    await fetchLogs()
    return result
  }

  const updateInstance = async (instanceId: string, updates: Partial<PlatformInstance>) => {
    const body: Record<string, unknown> = {}
    if (updates.name !== undefined) body.name = updates.name
    if (updates.config !== undefined) body.config = updates.config
    if (updates.enable !== undefined) body.enable = updates.enable

    await apiPatch(`/platforms/instances/${instanceId}`, body)
    await fetchInstances()
    await fetchStats()
  }

  const deleteInstance = async (instanceId: string) => {
    await apiDelete(`/platforms/instances/${instanceId}`)
    if (selectedInstanceId.value === instanceId) {
      selectedInstanceId.value = null
    }
    await fetchInstances()
    await fetchStats()
    await fetchLogs()
  }

  const startInstance = async (instanceId: string) => {
    await apiPost(`/platforms/instances/${instanceId}/start`, {})
    await fetchInstances()
    await fetchStats()
    await fetchLogs(instanceId)
  }

  const stopInstance = async (instanceId: string) => {
    await apiPost(`/platforms/instances/${instanceId}/stop`, {})
    await fetchInstances()
    await fetchStats()
    await fetchLogs(instanceId)
  }

  const selectInstance = (instanceId: string | null) => {
    selectedInstanceId.value = instanceId
    selectedConversationId.value = null
    selectedConversationDetail.value = null
    if (instanceId) {
      fetchConversations(instanceId)
      fetchLogs(instanceId)
    } else {
      fetchLogs()
    }
  }

  const selectConversation = (conversationId: string | null) => {
    if (!conversationId) {
      selectedConversationId.value = null
      selectedConversationDetail.value = null
      return
    }
    if (selectedInstanceId.value) {
      fetchConversationMessages(selectedInstanceId.value, conversationId)
    }
  }

  const setLogLevelFilter = (level: string | null) => {
    logLevelFilter.value = level
    fetchLogs()
  }

  const refreshAll = async () => {
    await Promise.all([fetchAdapterTypes(), fetchInstances(), fetchStats(), fetchLogSummary(), fetchMainAgent()])
    if (selectedInstanceId.value) {
      await Promise.all([fetchConversations(selectedInstanceId.value), fetchLogs(selectedInstanceId.value)])
    } else {
      await fetchLogs()
    }
  }

  return {
    adapterTypes,
    instances,
    conversations,
    logs,
    logTotal,
    logSummary,
    stats,
    mainAgent,
    mainAgentError,
    loading,
    selectedInstanceId,
    logLevelFilter,
    selectedConversationId,
    selectedConversationDetail,
    conversationLoading,
    instanceModelConfig,
    activeInstances,
    disconnectedInstances,
    selectedInstance,
    selectedConversations,
    selectedInstanceLogs,
    fetchAdapterTypes,
    fetchInstances,
    fetchStats,
    fetchConversations,
    fetchConversationMessages,
    fetchInstanceModelConfig,
    updateInstanceModelConfig,
    fetchLogs,
    fetchLogSummary,
    fetchMainAgent,
    updateMainAgent,
    createNewConversation,
    clearLogs,
    createInstance,
    updateInstance,
    deleteInstance,
    startInstance,
    stopInstance,
    selectInstance,
    selectConversation,
    setLogLevelFilter,
    refreshAll,
  }
})
