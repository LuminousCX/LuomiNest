import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  GroupInfo,
  GroupMessage,
  AgentProfile,
  AgentRoleDefinition,
  CollaborationPhase,
  CollaborationSubTask,
  CollaborationEvent,
  MessageCollaboration,
  SearchResult,
} from '../types'
import type {
  CloudGroupVo,
  CloudGroupMessageVo,
  CloudGroupErrorInfo,
  CloudGroupErrorKind,
} from '@shared/ipc-types'
import { useApi } from '../composables/useApi'
import { generateId } from '../utils/id'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('Social')

export const useSocialStore = defineStore('social', () => {
  const { apiGet, apiPost, apiDelete, apiSseStream } = useApi()

  interface StreamEvent {
    type: string
    data: Record<string, unknown>
  }

  const groups = ref<GroupInfo[]>([])
  const currentGroup = ref<GroupInfo | null>(null)
  const groupMessages = ref<GroupMessage[]>([])
  const availableAgents = ref<AgentProfile[]>([])
  const agentRoles = ref<AgentRoleDefinition[]>([])
  const loading = ref(false)

  const collaborationPhase = ref<CollaborationPhase | null>(null)
  const collaborationPlan = ref<string | null>(null)
  const collaborationTasks = ref<CollaborationSubTask[]>([])
  const collaborationActive = ref(false)
  const collaborationSessionId = ref<string | null>(null)

  const agentsResponding = ref(false)
  const respondingAgentNames = ref<string[]>([])

  const fetchGroups = async () => {
    loading.value = true
    try {
      const response = await apiGet<{ data: GroupInfo[] }>('/social/groups')
      groups.value = response.data || []
    } catch {
      groups.value = []
    } finally {
      loading.value = false
    }
  }

  const createGroup = async (name: string, description?: string, type?: string) => {
    const response = await apiPost<{ data: GroupInfo }>('/social/groups', {
      name,
      description: description || '',
      type: type || 'mixed',
    })
    await fetchGroups()
    return response.data
  }

  const deleteGroup = async (groupId: string) => {
    await apiDelete(`/social/groups/${groupId}`)
    if (currentGroup.value?.id === groupId) {
      currentGroup.value = null
      groupMessages.value = []
    }
    await fetchGroups()
  }

  const addAgentToGroup = async (groupId: string, agentId: string, role?: string) => {
    const response = await apiPost<{ data: GroupInfo }>(`/social/groups/${groupId}/members`, {
      agent_id: agentId,
      role: role || '成员',
    })
    await fetchGroups()
    if (currentGroup.value?.id === groupId) {
      currentGroup.value = response.data
    }
    return response.data
  }

  const removeAgentFromGroup = async (groupId: string, agentId: string) => {
    await apiDelete(`/social/groups/${groupId}/members/${agentId}`)
    await fetchGroups()
  }

  const sendGroupMessage = async (groupId: string, content: string) => {
    agentsResponding.value = true
    respondingAgentNames.value = []

    try {
      await apiSseStream(
        `/social/groups/${groupId}/messages`,
        { content, sender_id: 'user' },
        (event: { type?: string; data?: Record<string, unknown> }) => _handleMessageEvent({ type: event.type || 'unknown', data: event.data || {} }),
        async () => {},
        (err: string) => logger.error('Failed to send message:', err),
      )
    } finally {
      agentsResponding.value = false
      respondingAgentNames.value = []
      await fetchGroups()
    }
  }

  const _handleMessageEvent = (event: StreamEvent) => {
    switch (event.type) {
      case 'user_message': {
        const msg = _validateMessageData(event.data)
        if (msg) groupMessages.value.push(msg)
        break
      }

      case 'agents_start':
        respondingAgentNames.value = (event.data?.agentNames || event.data?.agent_names || []) as string[]
        break

      case 'agent_message_start': {
        // 流式响应开始：推送空内容消息，标记 isStreaming
        const msg = _normalizeMessage(event.data)
        if (msg) {
          msg.isStreaming = true
          groupMessages.value.push(msg)
        }
        break
      }

      case 'agent_message_delta': {
        // 流式增量：追加内容到正在响应的消息
        const id = event.data?.id as string
        const deltaContent = event.data?.content as string
        if (!id || !deltaContent) break
        const idx = groupMessages.value.findIndex(m => m.id === id)
        if (idx >= 0) {
          groupMessages.value[idx].content += deltaContent
        }
        break
      }

      case 'agent_message_end': {
        // 流式响应结束：更新最终内容，清除 isStreaming
        const id = event.data?.id as string
        const finalContent = event.data?.content as string
        if (!id) break
        const idx = groupMessages.value.findIndex(m => m.id === id)
        if (idx >= 0) {
          groupMessages.value[idx].isStreaming = false
          if (finalContent) {
            groupMessages.value[idx].content = finalContent
          }
        } else {
          // 兜底：未找到消息（可能丢失 start 事件），直接推送
          const msg = _normalizeMessage(event.data)
          if (msg) groupMessages.value.push(msg)
        }
        break
      }

      case 'agent_message': {
        // 兼容旧版非流式事件
        const msg = _validateMessageData(event.data)
        if (msg) groupMessages.value.push(msg)
        break
      }

      case 'agent_error': {
        const msg = _validateMessageData(event.data)
        if (msg) groupMessages.value.push(msg)
        break
      }

      case 'agents_done':
        agentsResponding.value = false
        respondingAgentNames.value = []
        break

      case 'info':
        if (event.data?.message && typeof event.data.message === 'string') {
          groupMessages.value.push({
            id: generateId('info'),
            groupId: currentGroup.value?.id || '',
            senderId: 'system',
            senderName: '系统',
            senderType: 'system',
            content: event.data.message,
            timestamp: new Date().toISOString(),
            role: '系统',
          })
        }
        break

      case 'error':
        logger.error('Message stream error:', event.data?.message)
        break
    }
  }

  const fetchGroupMessages = async (groupId: string) => {
    try {
      const response = await apiGet<{ data: { messages: GroupMessage[] } }>(`/social/groups/${groupId}`)
      if (response.data?.messages) {
        groupMessages.value = response.data.messages.map((msg) => _normalizeMessage(msg as unknown as Record<string, unknown>))
      }
    } catch {
      groupMessages.value = []
    }
  }

  const _normalizeMessage = (msg: Record<string, unknown>): GroupMessage => {
    const asString = (v: unknown): string => (typeof v === 'string' ? v : '')
    const asOptionalString = (v: unknown): string | undefined => (typeof v === 'string' ? v : undefined)
    return {
      id: asString(msg.id || msg.message_id) || generateId('msg'),
      groupId: asString(msg.groupId || msg.group_id) || currentGroup.value?.id || '',
      senderId: asString(msg.senderId || msg.sender_id),
      senderName: asOptionalString(msg.senderName || msg.sender_name),
      senderType: asString(msg.senderType || msg.sender_type) || 'user',
      content: asString(msg.content),
      timestamp: asString(msg.timestamp) || new Date().toISOString(),
      role: asOptionalString(msg.role),
      collaboration: msg.collaboration as MessageCollaboration | undefined,
    }
  }

  const _validateMessageData = (data: Record<string, unknown>): GroupMessage | null => {
    if (!data || typeof data !== 'object') return null
    const content = data.content ?? data.Content
    if (typeof content !== 'string' || !content.trim()) return null
    return _normalizeMessage(data)
  }

  const fetchAvailableAgents = async () => {
    try {
      const response = await apiGet<{ data: AgentProfile[] }>('/social/agents')
      availableAgents.value = response.data || []
    } catch {
      availableAgents.value = []
    }
  }

  const fetchAgentRoles = async () => {
    try {
      const response = await apiGet<{ data: AgentRoleDefinition[] }>('/social/agent-roles')
      agentRoles.value = response.data || []
    } catch {
      agentRoles.value = []
    }
  }

  const collaborateStream = async (
    groupId: string,
    content: string,
    onEvent: (event: CollaborationEvent) => void,
    onError: (err: string) => void,
    onDone: () => void,
  ) => {
    collaborationActive.value = true
    collaborationPhase.value = 'analyzing'
    collaborationPlan.value = null
    collaborationTasks.value = []
    collaborationSessionId.value = null

    try {
      await apiSseStream<CollaborationEvent>(
        `/social/groups/${groupId}/collaborate`,
        { content, sender_id: 'user', stream: true },
        (event) => {
          _handleCollaborationEvent(event)
          onEvent(event)

          if (event.type === 'session_end' || event.type === 'error') {
            collaborationActive.value = false
            if (event.type !== 'error') {
              fetchGroups()
            }
          }
        },
        async () => {
          collaborationActive.value = false
          await fetchGroups()
          onDone()
        },
        (err: string) => {
          collaborationActive.value = false
          collaborationPhase.value = 'failed'
          onError(err)
        },
      )
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') {
        collaborationActive.value = false
        onDone()
        return
      }
      collaborationActive.value = false
      collaborationPhase.value = 'failed'
      const message = e instanceof Error ? e.message : String(e)
      onError(message)
    }
  }

  const _handleCollaborationEvent = (event: CollaborationEvent) => {
    switch (event.type) {
      case 'session_start':
        collaborationSessionId.value = event.data.session_id || null
        collaborationPhase.value = 'analyzing'
        break

      case 'phase_change':
        collaborationPhase.value = (event.data.phase as CollaborationPhase) || null
        break

      case 'plan_created':
        collaborationPlan.value = event.data.plan || null
        break

      case 'task_started': {
        const existingIdx = collaborationTasks.value.findIndex(t => t.taskId === event.data.task_id)
        if (existingIdx >= 0) {
          collaborationTasks.value[existingIdx] = {
            ...collaborationTasks.value[existingIdx],
            status: 'running',
            startedAt: new Date().toISOString(),
          }
        } else {
          collaborationTasks.value.push({
            taskId: event.data.task_id,
            roleId: event.data.role_id || '',
            agentId: event.data.agent_id || undefined,
            description: event.data.description || '',
            inputContent: '',
            dependsOn: [],
            status: 'running',
            result: undefined,
            error: undefined,
            startedAt: new Date().toISOString(),
          })
        }
        break
      }

      case 'task_agent_assigned': {
        const taskIdx = collaborationTasks.value.findIndex(t => t.taskId === event.data.task_id)
        if (taskIdx >= 0) {
          collaborationTasks.value[taskIdx] = {
            ...collaborationTasks.value[taskIdx],
            agentId: event.data.agent_id,
          }
        }
        break
      }

      case 'task_completed': {
        const completedIdx = collaborationTasks.value.findIndex(t => t.taskId === event.data.task_id)
        if (completedIdx >= 0) {
          collaborationTasks.value[completedIdx] = {
            ...collaborationTasks.value[completedIdx],
            status: 'completed',
            result: event.data.result,
            completedAt: new Date().toISOString(),
          }
        }

        const role = agentRoles.value.find(r => r.roleId === event.data.role_id)
        const agentName = event.data.agent_name || 'Agent'

        groupMessages.value.push({
          id: `${generateId('collab')}-${event.data.task_id}`,
          groupId: currentGroup.value?.id || '',
          senderId: event.data.agent_id || 'agent',
          senderName: agentName,
          senderType: 'agent',
          content: event.data.result || '',
          timestamp: new Date().toISOString(),
          role: role?.name || event.data.role_id,
          collaboration: {
            sessionId: collaborationSessionId.value || '',
            taskId: event.data.task_id,
            taskDescription: event.data.description,
            type: 'task_result',
          },
        })
        break
      }

      case 'task_failed': {
        const failedIdx = collaborationTasks.value.findIndex(t => t.taskId === event.data.task_id)
        if (failedIdx >= 0) {
          collaborationTasks.value[failedIdx] = {
            ...collaborationTasks.value[failedIdx],
            status: 'failed',
            error: event.data.error,
            completedAt: new Date().toISOString(),
          }
        }
        break
      }

      case 'direct_response': {
        groupMessages.value.push({
          id: generateId('direct'),
          groupId: currentGroup.value?.id || '',
          senderId: event.data.agent_id || 'agent',
          senderName: event.data.agent_name || 'Agent',
          senderType: 'agent',
          content: event.data.content || '',
          timestamp: new Date().toISOString(),
          role: '调度员',
        })
        break
      }

      case 'final_result': {
        groupMessages.value.push({
          id: generateId('synthesis'),
          groupId: currentGroup.value?.id || '',
          senderId: event.data.agent_id || 'coordinator',
          senderName: event.data.agent_name || '调度员',
          senderType: 'agent',
          content: event.data.content || '',
          timestamp: new Date().toISOString(),
          role: '调度员',
          collaboration: {
            sessionId: collaborationSessionId.value || '',
            type: 'synthesis',
          },
        })
        break
      }

      case 'error':
        collaborationPhase.value = 'failed'
        break
    }
  }

  const resetCollaboration = () => {
    collaborationPhase.value = null
    collaborationPlan.value = null
    collaborationTasks.value = []
    collaborationActive.value = false
    collaborationSessionId.value = null
  }

  const indexRAGContent = async (content: string, source: string, metadata?: Record<string, unknown>) => {
    const response = await apiPost<{ data: { indexed_chunks: number } }>('/social/rag/index', {
      content,
      source,
      metadata,
    })
    return response.data
  }

  const searchRAG = async (query: string, topK?: number) => {
    const response = await apiPost<{ data: SearchResult[] }>('/social/rag/search', {
      query,
      top_k: topK || 5,
    })
    return response.data || []
  }

  /* ================================================================
   * 云端群聊（服务端端点未上线时优雅降级）
   *
   * 数据经由主进程 cloud-groups 客户端（window.api.cloud.group*）：
   * - 服务端 404/501（未部署）→ cloudState='unavailable'，界面显示
   *   「云端群聊服务暂未开通」空态，后续请求被短路（不重试轰炸）；
   * - 轮询仅作用于当前打开的群，窗口失焦（document.hasFocus()=false）时暂停；
   * - 连续多次轮询失败自动停止，恢复需重新打开该群。
   * ================================================================ */

  /** 消息分页：契约 limit≤200，首页 50 条，「加载更多」按 50 递增重拉 */
  const CLOUD_PAGE_SIZE = 50
  const CLOUD_PAGE_MAX = 200
  /** 当前打开群的轮询间隔（3~5s 区间取中） */
  const CLOUD_POLL_INTERVAL_MS = 4000
  /** 轮询连续失败上限：达到后自停，避免错误风暴 */
  const CLOUD_POLL_MAX_FAILURES = 5

  const cloudGroups = ref<CloudGroupVo[]>([])
  /** 当前用户云 ID（群列表附带；用于把「自己发的消息」右对齐；未知道时全部左对齐） */
  const cloudMeId = ref('')
  /** idle=未探测/未登录 loading=拉取中 ready=服务可用 unavailable=服务端未开通 */
  const cloudState = ref<'idle' | 'loading' | 'ready' | 'unavailable'>('idle')
  const currentCloudGroupId = ref<string | null>(null)
  const cloudMessages = ref<GroupMessage[]>([])
  const cloudMessagesLoading = ref(false)
  const cloudSending = ref(false)
  const cloudHistoryLimit = ref(CLOUD_PAGE_SIZE)
  /** 还有更早历史可加载（服务端只支持 sinceId 升序增量，故「加载更多」以更大 limit 重拉） */
  const cloudCanLoadMore = ref(false)

  let cloudPollTimer: ReturnType<typeof setInterval> | null = null
  let cloudPollFailures = 0
  /** 每个群已见到的最大服务端消息 id（轮询 sinceId 增量基准） */
  const cloudLastIdByGroup = new Map<string, string>()

  /** 雪花 id 比较：BigInt 优先（64 位超出 Number 安全整数），退化字符串比较 */
  const _compareCloudIds = (a: string, b: string): number => {
    if (a === b) return 0
    try {
      const diff = BigInt(a) - BigInt(b)
      return diff > 0n ? 1 : -1
    } catch {
      return a < b ? -1 : 1
    }
  }

  const _logCloudError = (action: string, error: CloudGroupErrorInfo): void => {
    if (error.kind !== 'unavailable') {
      logger.warn(`Cloud groups ${action} failed: ${error.kind}`, error.message || '')
    }
  }

  /** 服务端消息 → 渲染层 GroupMessage（自己的消息 senderType='user' 以右对齐） */
  const _normalizeCloudMessage = (msg: CloudGroupMessageVo, groupId: string): GroupMessage => ({
    id: `cloud-${msg.id}`,
    groupId,
    senderId: msg.senderId,
    senderName: msg.senderName || msg.senderId,
    senderType: !!msg.senderId && msg.senderId === cloudMeId.value ? 'user' : 'agent',
    content: msg.content,
    timestamp: msg.createdAt || new Date().toISOString(),
  })

  const _updateCloudLastId = (groupId: string, rawIds: string[]): void => {
    const current = cloudLastIdByGroup.get(groupId) || '0'
    const max = rawIds.reduce((acc, id) => (_compareCloudIds(id, acc) > 0 ? id : acc), current)
    cloudLastIdByGroup.set(groupId, max)
  }

  /** 拉取云端群列表（unavailable 后短路：本次会话不再探测，避免重试轰炸） */
  const fetchCloudGroups = async (): Promise<void> => {
    if (cloudState.value === 'unavailable') return
    cloudState.value = 'loading'
    try {
      const result = await window.api.cloud.groupList()
      if (result.ok) {
        cloudGroups.value = result.data.groups
        if (result.data.meId) cloudMeId.value = result.data.meId
        cloudState.value = 'ready'
      } else if (result.error.kind === 'unavailable') {
        logger.debug('Cloud groups service not available; degraded to empty state')
        cloudGroups.value = []
        cloudState.value = 'unavailable'
      } else if (result.error.kind === 'not_logged_in') {
        cloudGroups.value = []
        cloudState.value = 'idle'
      } else {
        _logCloudError('list', result.error)
        cloudState.value = cloudGroups.value.length > 0 ? 'ready' : 'idle'
      }
    } finally {
      if (cloudState.value === 'loading') cloudState.value = 'idle'
    }
  }

  /** 创建云端群；成功返回新群（调用方负责选中），失败返回 null */
  const createCloudGroup = async (name: string): Promise<CloudGroupVo | null> => {
    const result = await window.api.cloud.groupCreate(name)
    if (result.ok) {
      cloudGroups.value = [result.data, ...cloudGroups.value.filter(g => g.id !== result.data.id)]
      return result.data
    }
    _logCloudError('create', result.error)
    return null
  }

  /** 按用户 ID 邀请成员；失败返回错误类别（forbidden → 仅群主/管理员） */
  const inviteCloudMember = async (groupId: string, userId: string): Promise<{ ok: boolean; kind?: CloudGroupErrorKind }> => {
    const result = await window.api.cloud.groupInvite(groupId, userId)
    if (result.ok) return { ok: true }
    _logCloudError('invite', result.error)
    return { ok: false, kind: result.error.kind }
  }

  /** 全量拉取当前页消息（sinceId='0' + cloudHistoryLimit；「加载更多」加大 limit 后重进） */
  const fetchCloudMessages = async (groupId: string, silent = false): Promise<void> => {
    if (cloudState.value === 'unavailable') return
    if (!silent) cloudMessagesLoading.value = true
    try {
      const result = await window.api.cloud.groupMessages({ groupId, sinceId: '0', limit: cloudHistoryLimit.value })
      if (result.ok) {
        const sorted = [...result.data].sort((a, b) => _compareCloudIds(a.id, b.id))
        cloudMessages.value = sorted.map(m => _normalizeCloudMessage(m, groupId))
        _updateCloudLastId(groupId, sorted.map(m => m.id))
        cloudCanLoadMore.value = sorted.length >= cloudHistoryLimit.value && cloudHistoryLimit.value < CLOUD_PAGE_MAX
      } else {
        _handleCloudMessagesError(result.error)
      }
    } finally {
      cloudMessagesLoading.value = false
    }
  }

  /** 消息查询失败分类处理：仅 unavailable 改变全局降级态，其余静默 */
  const _handleCloudMessagesError = (error: CloudGroupErrorInfo): void => {
    if (error.kind === 'unavailable') {
      cloudState.value = 'unavailable'
      stopCloudPolling()
      return
    }
    _logCloudError('fetch messages', error)
  }

  /** 轮询 tick：窗口失焦/最小化时跳过（暂停），增量拉取 sinceId 之后的新消息 */
  const _pollCloudMessages = async (): Promise<void> => {
    const groupId = currentCloudGroupId.value
    if (!groupId || cloudState.value === 'unavailable') return
    if (document.hidden || !document.hasFocus()) return // 失焦暂停轮询
    try {
      const result = await window.api.cloud.groupMessages({
        groupId,
        sinceId: cloudLastIdByGroup.get(groupId) || '0',
        limit: CLOUD_PAGE_SIZE,
      })
      if (result.ok) {
        cloudPollFailures = 0
        if (result.data.length > 0) {
          const known = new Set(cloudMessages.value.map(m => m.id))
          const fresh = result.data
            .sort((a, b) => _compareCloudIds(a.id, b.id))
            .filter(m => !known.has(`cloud-${m.id}`))
          for (const raw of fresh) cloudMessages.value.push(_normalizeCloudMessage(raw, groupId))
          _updateCloudLastId(groupId, fresh.map(m => m.id))
        }
      } else {
        cloudPollFailures += 1
        if (result.error.kind === 'unavailable') {
          cloudState.value = 'unavailable'
          stopCloudPolling()
          return
        }
        if (cloudPollFailures >= CLOUD_POLL_MAX_FAILURES) {
          logger.warn('Cloud group polling stopped after repeated failures')
          stopCloudPolling()
        }
      }
    } catch (err) {
      logger.warn('Cloud group polling error:', err instanceof Error ? err.message : err)
    }
  }

  const startCloudPolling = (): void => {
    stopCloudPolling()
    cloudPollFailures = 0
    cloudPollTimer = setInterval(() => {
      void _pollCloudMessages()
    }, CLOUD_POLL_INTERVAL_MS)
  }

  const stopCloudPolling = (): void => {
    if (cloudPollTimer) {
      clearInterval(cloudPollTimer)
      cloudPollTimer = null
    }
  }

  /** 打开一个云端群：重置分页、拉首页消息并启动轮询 */
  const openCloudGroup = async (groupId: string): Promise<void> => {
    if (currentCloudGroupId.value !== groupId) {
      currentCloudGroupId.value = groupId
      cloudMessages.value = []
      cloudHistoryLimit.value = CLOUD_PAGE_SIZE
      cloudCanLoadMore.value = false
      cloudLastIdByGroup.set(groupId, '0')
      await fetchCloudMessages(groupId)
    } else {
      await fetchCloudMessages(groupId, true)
    }
    if (cloudState.value !== 'unavailable') startCloudPolling()
  }

  /** 离开当前云端群：停轮询、清空线程 */
  const leaveCloudGroup = (): void => {
    stopCloudPolling()
    currentCloudGroupId.value = null
    cloudMessages.value = []
    cloudCanLoadMore.value = false
  }

  /** 解除 unavailable 降级（赋值收进辅助函数，避免调用方 TS 收窄误判） */
  const _resetCloudState = (): void => {
    cloudState.value = 'idle'
  }

  /** 用户手动「重新检测」：解除降级后重探服务可用性，恢复时重开当前群 */
  const recheckCloudGroups = async (groupId: string | null): Promise<void> => {
    _resetCloudState()
    await fetchCloudGroups()
    if (groupId && cloudState.value === 'ready') {
      await openCloudGroup(groupId)
    }
  }

  /** 加载更早历史：加大 limit 重拉（契约只有 sinceId 升序，无反向分页） */
  const loadOlderCloudMessages = async (): Promise<void> => {
    const groupId = currentCloudGroupId.value
    if (!groupId || !cloudCanLoadMore.value || cloudMessagesLoading.value) return
    cloudHistoryLimit.value = Math.min(cloudHistoryLimit.value + CLOUD_PAGE_SIZE, CLOUD_PAGE_MAX)
    await fetchCloudMessages(groupId)
  }

  /** 发送消息：成功后本地追加（幂等去重），失败返回 false 供 UI 提示 */
  const sendCloudMessage = async (groupId: string, content: string): Promise<boolean> => {
    const text = content.trim()
    if (!text || cloudSending.value) return false
    cloudSending.value = true
    try {
      const result = await window.api.cloud.groupSend(groupId, text)
      if (result.ok) {
        const msg = _normalizeCloudMessage(result.data, groupId)
        if (!cloudMessages.value.some(m => m.id === msg.id)) cloudMessages.value.push(msg)
        _updateCloudLastId(groupId, [result.data.id])
        return true
      }
      if (result.error.kind === 'unavailable') cloudState.value = 'unavailable'
      _logCloudError('send', result.error)
      return false
    } finally {
      cloudSending.value = false
    }
  }

  const currentCloudGroup = (): CloudGroupVo | null =>
    cloudGroups.value.find(g => g.id === currentCloudGroupId.value) || null

  return {    groups,
    currentGroup,
    groupMessages,
    availableAgents,
    agentRoles,
    loading,
    collaborationPhase,
    collaborationPlan,
    collaborationTasks,
    collaborationActive,
    collaborationSessionId,
    agentsResponding,
    respondingAgentNames,
    fetchGroups,
    createGroup,
    deleteGroup,
    addAgentToGroup,
    removeAgentFromGroup,
    sendGroupMessage,
    fetchGroupMessages,
    fetchAvailableAgents,
    fetchAgentRoles,
    collaborateStream,
    resetCollaboration,
    indexRAGContent,
    searchRAG,
    // 云端群聊
    cloudGroups,
    cloudMeId,
    cloudState,
    currentCloudGroupId,
    cloudMessages,
    cloudMessagesLoading,
    cloudSending,
    cloudCanLoadMore,
    fetchCloudGroups,
    createCloudGroup,
    inviteCloudMember,
    fetchCloudMessages,
    openCloudGroup,
    leaveCloudGroup,
    loadOlderCloudMessages,
    sendCloudMessage,
    recheckCloudGroups,
    currentCloudGroup,
  }
})
