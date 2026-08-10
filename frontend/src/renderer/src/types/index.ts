export interface Agent {
  id: string
  name: string
  description: string
  systemPrompt?: string
  model?: string
  provider?: string
  color: string
  avatar?: string
  isBuiltin?: boolean
}

export interface ChatFile {
  id?: string
  name: string
  size?: number
  type?: string
  content?: string
}

export interface MessageVersion {
  content: string
  reasoningContent?: string
  model?: string
  provider?: string
  suggestedQuestions?: string[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  reasoningContent?: string
  timestamp: number
  agentId?: string
  model?: string
  provider?: string
  done?: boolean
  interrupted?: boolean
  files?: ChatFile[]
  quote?: {
    id: string
    role: 'user' | 'assistant'
    content: string
  }
  versions?: MessageVersion[]
  currentVersion?: number
  usage?: {
    promptTokens?: number
    completionTokens?: number
    totalTokens?: number
  }
  suggestedQuestions?: string[]
  /** 关联的工作流会话 ID（当此消息触发工作流时设置，用于渲染"已创建工作流"卡片） */
  workflowSessionId?: string
  /** 工作流子任务数量（配合 workflowSessionId 使用） */
  workflowTaskCount?: number
}

/** Raw message shape returned by the backend API (snake_case) */
export interface ApiMessage {
  id?: string
  role: 'user' | 'assistant' | 'system'
  content?: string
  reasoning_content?: string
  timestamp?: number
  agent_id?: string
  model?: string
  provider?: string
  file_name?: string
  file_type?: string
  files?: ChatFile[]
  interrupted?: boolean
  suggested_questions?: string[]
  versions?: MessageVersion[]
  current_version?: number
}

export interface ChatRequest {
  messages: { role: ChatMessage['role']; content: string }[]
  model?: string
  provider?: string
  temperature?: number
  maxTokens?: number
  topP?: number
  stream?: boolean
  agentId?: string
  timestamp?: number
  fileContent?: string
}

export interface ChatResponse {
  id: string
  content: string | null
  model: string
  provider: string
}

export interface ToolCall {
  id: string
  type: string
  function: {
    name: string
    arguments: string
  }
}

export interface ToolEvent {
  tool_name: string
  status: 'started' | 'completed' | 'failed'
  output?: string | null
}

/** 子 Agent 执行事件（主 Agent 通过 delegate_to_subagent 工具委派时推送） */
export interface SubagentEvent {
  subagent_id: string
  status: 'started' | 'running' | 'completed' | 'failed'
  task: string
  depth: number
  iteration?: number
  tool_name?: string
  tool_args?: string
  tool_output?: string
  progress?: string
  result?: string
  error?: string
  /** 浏览器工具专用字段（create_browser_tab 工具复用 subagent_event 通道） */
  browser_action?: string
  browser_url?: string
  browser_title?: string
  browser_purpose?: string
  browser_tab_id?: string
}

/** 定时任务事件（后端调度器触发时推送） */
export interface TaskStreamEvent {
  task_id: string
  task_name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'removed'
  task_type: 'date' | 'cron' | 'interval'
  message: string
  result?: string | null
  error?: string | null
  timestamp: string
  payload?: Record<string, unknown>
}

export interface ChatStreamChunk {
  id: string
  content: string
  reasoning_content: string
  model: string
  provider: string
  done: boolean
  usage?: {
    promptTokens?: number
    completionTokens?: number
    totalTokens?: number
  }
  suggested_questions?: string[]
  emotion?: string
  tool_calls?: ToolCall[]
  tool_event?: ToolEvent
  subagent_event?: SubagentEvent
  task_event?: TaskStreamEvent
  iteration?: number
  /** 当前上下文已使用的 token 数（仅 done=True 的 chunk 携带） */
  context_tokens?: number
  /** 上下文窗口容量（仅 done=True 的 chunk 携带，前端用于计算使用百分比） */
  context_max_tokens?: number
}

export interface Conversation {
  id: string
  title: string
  agent_id?: string
  model?: string
  provider?: string
  chat_mode?: string
  messages: ApiMessage[]
  created_at: string
  updated_at: string
  has_more?: boolean
  total_messages?: number
}

export interface ConversationListItem {
  id: string
  title: string
  agent_id?: string
  model?: string
  provider?: string
  chat_mode?: string
  last_message?: string
  is_hidden?: boolean
  created_at: string
  updated_at: string
}

export interface ConversationSearchResult {
  id: string
  title: string
  snippet: string
  updated_at: string
}

export interface TrashListItem {
  id: string
  title: string
  deleted_at: string
  agent_id?: string
}

export interface ModelProvider {
  id: string
  name: string
  type: string
  vendor: string
  baseUrl: string
  apiKeySet: boolean
  apiKeyPrefix: string
  isDefault: boolean
  defaultModel: string
  selectedModels: string[]
  models: { id: string; name: string }[]
}

export interface ModelConfig {
  defaultProvider: string
  defaultModel: string
  defaultTemperature: number
  defaultMaxTokens: number
  defaultTopP: number
  reasonerProvider?: string
  reasonerModel?: string
  reasonerTemperature?: number
  reasonerMaxTokens?: number
  reasonerEffort?: string
  ttsProvider?: string
  ttsModel?: string
  ttsVoice?: string
  ttsSpeed?: number
  sttProvider?: string
  sttModel?: string
  sttLanguage?: string
  sttAutoSend?: boolean
  sttAutoSendDelay?: number
  sttEngine?: string
  /** LLM 上下文窗口大小（0 = 自动从 provider 获取） */
  contextWindowSize?: number
  /** 压缩阈值（0.5 - 0.95） */
  compressionThreshold?: number
  /** 是否启用 LLM 摘要压缩 */
  llmCompressEnabled?: boolean
  /** 摘要模型 */
  summaryModel?: string
  /** 摘要供应商 */
  summaryProvider?: string
}

export interface Skill {
  name: string
  description: string
  category: string
  isActive: boolean
  isBuiltin: boolean
}

export interface McpServer {
  name: string
  transport: string
  status?: string
}

export interface SearchResult {
  content: string
  source: string
  score: number
  metadata: Record<string, unknown>
}

export interface ExecutionStep {
  id: string
  label: string
}

export interface ExecutionStatus {
  steps: ExecutionStep[]
  currentStepIndex: number
  isSkipped: boolean
  isComplete: boolean
}

export interface AgentProfile extends Agent {
  isMain?: boolean
  capabilities?: string[]
  isActive?: boolean
}

export interface MainAgentConfig {
  provider: string
  model: string
  systemPrompt: string
  temperature: number
  maxTokens: number
  color: string
  avatar?: string | null
}

export interface ModelInfo {
  id: string
  name: string
  owned_by?: string
  provider?: string
}

export interface ProviderTemplate {
  id: string
  name: string
  vendor: string
  baseUrl: string
  defaultModel: string
  description: string
  category?: 'cloud' | 'local' | 'aggregator'
  color?: string
  initials?: string
  svgIcon?: string
  defaultModels?: string[]
}

export interface TTSConfig {
  provider?: string
  model?: string
  voice?: string
  speed?: number
  baseUrl?: string
  apiKeySet?: boolean
  /** 引擎 ID，与 provider 同义（edge-tts / sherpa-onnx / local / auto 等） */
  engine?: string
  /** 云端引擎 API Key（仅前端暂存标记，明文不回传） */
  apiKey?: string
}

export interface STTConfig {
  provider?: string
  model?: string
  language?: string
  autoSend?: boolean
  autoSendDelay?: number
  baseUrl?: string
  apiKeySet?: boolean
  engine?: string
}

export interface STTEngine {
  id: string
  name: string
  online: boolean
  available: boolean
  model_ready?: boolean
  languages?: string[]
  description?: string
  model_types?: string[]
  models?: string[]
}

/** 计算设备信息（TTS/STT 共用，来自后端硬件检测） */
export interface ComputeDeviceInfo {
  type: string
  name: string
  vendor?: string
  gpu_count?: number
  cuda_available: boolean
  cuda_version?: string
  torch_available?: boolean
  note?: string
}

/** 系统信息（来自 /system/info） */
export interface LuomiNestSystemInfo {
  os_name: string
  os_family: string
  kernel_version: string
  machine: string
  python_version: string
  package_manager: string
  is_frozen: boolean
  distro?: {
    id: string
    name: string
    version: string
    family: string
    pretty_name: string
    version_id: string
  }
}

export interface GroupMember {
  agent_id: string
  name: string
  type: string
  role: string
  color: string
}

export interface GroupInfo {
  id: string
  name: string
  description: string
  type: string
  members: GroupMember[]
  memberCount: number
  aiCount: number
  lastMessage?: string
  createdAt: string
  updatedAt: string
}

export interface MessageCollaboration {
  sessionId?: string
  taskId?: string
  taskDescription?: string
  type?: string
}

export interface GroupMessage {
  id: string
  groupId: string
  senderId: string
  senderName?: string
  senderType: string
  content: string
  timestamp: string
  role?: string
  collaboration?: MessageCollaboration
  isStreaming?: boolean
}

export interface AgentRoleDefinition {
  roleId: string
  name: string
  description: string
  capabilities: string[]
  executionMode: string
  maxConcurrentTasks: number
  timeoutSeconds: number
  color: string
}

export type CollaborationPhase = 'analyzing' | 'dispatching' | 'executing' | 'synthesizing' | 'completed' | 'failed'

export interface CollaborationSubTask {
  taskId: string
  roleId: string
  agentId?: string | null
  description: string
  inputContent?: string
  dependsOn?: string[]
  status: string
  result?: string
  error?: string
  startedAt?: string
  completedAt?: string
}

export interface CollaborationEvent {
  type: string
  data: Record<string, any>
}

export interface ProviderLogo {
  id: string
  name: string
  color?: string
  initials?: string
  svgIcon?: string
  logo?: string
}

export interface CommandRecord {
  id: string
  command: string
  description: string
  status: 'success' | 'failed' | 'running'
  exit_code: number | null
  executed_by: string
  started_at: string
  finished_at: string | null
  duration_ms: number | null
  output: string | null
  error: string | null
  rollback_command: string | null
}

export interface SystemLogEntry {
  id: string
  timestamp: string
  level: 'info' | 'warn' | 'error' | 'success'
  source: 'frontend' | 'backend'
  message: string
  module: string | null
  extra: Record<string, unknown> | null
}

export interface LogUploadRequest {
  logs: SystemLogEntry[]
  uploaded_by: string
  session_id: string | null
}

export interface LogUploadResponse {
  upload_id: string
  received_count: number
  status: string
}

export interface ExecuteCommandRequest {
  command: string
  description?: string
  executed_by?: string
  working_dir?: string
  timeout?: number
}

export interface ExecuteCommandResponse {
  command_id: string
  status: 'success' | 'failed' | 'running'
  exit_code: number | null
  output: string | null
  error: string | null
  duration_ms: number
}

/** 平台适配器配置字段元数据（描述一个配置项的渲染方式） */
export interface ConfigFieldMeta {
  label?: string
  type?: 'text' | 'password' | 'number'
  [key: string]: unknown
}

export interface PlatformAdapterType {
  name: string
  displayName: string
  description: string
  icon: string
  category: string
  configTemplate: Record<string, unknown>
  configMetadata: Record<string, ConfigFieldMeta>
  supportStreaming: boolean
  supportProactive: boolean
}

export interface PlatformInstance {
  id: string
  adapterType: string
  name: string
  config: Record<string, unknown>
  status: 'pending' | 'running' | 'stopped' | 'error'
  enable: boolean
  messageCount: number
  lastSync: string
  errorMessage: string
  icon: string
  category: string
  displayName: string
  createdAt: string
  updatedAt: string
  modelConfig?: PlatformModelConfig
}

export interface PlatformModelConfig {
  provider?: string
  model?: string
  systemPrompt?: string
  temperature?: number | null
  maxTokens?: number | null
}

export interface PlatformModelConfigResponse {
  instanceId: string
  isOverridden: boolean
  instanceConfig: PlatformModelConfig
  mainAgent: {
    provider: string
    providerName: string
    model: string
    supportsMultimodal: boolean
    systemPrompt: string
    temperature: number
    maxTokens: number
  }
  effective: {
    provider: string
    providerName: string
    model: string
    supportsMultimodal: boolean
  }
  category: string
}

export interface PlatformConversation {
  id: string
  platformInstanceId: string
  platformName: string
  title: string
  preview: string
  time: string
  messageCount: number
}

export interface PlatformMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  senderName: string
  isGroup: boolean
  imageUrls: string[]
  model: string
  provider: string
}

export interface PlatformConversationDetail {
  conversationId: string
  title: string
  instanceId: string
  platformName: string
  senderName: string
  isGroup: boolean
  messages: PlatformMessage[]
  messageCount: number
}

export interface PlatformStats {
  totalPlatforms: number
  activeConnections: number
  totalMessages: number
}

export interface PlatformLogEntry {
  id: string
  timestamp: string
  level: 'info' | 'success' | 'warning' | 'error'
  event: string
  message: string
  instanceId: string
  adapterType: string
  details: Record<string, unknown>
}

export interface PlatformLogResult {
  entries: PlatformLogEntry[]
  total: number
}

export interface PlatformLogSummary {
  totalEntries: number
  totalInstances: number
  byLevel: Record<string, number>
}

export interface MainAgentInfo {
  provider: string
  providerName: string
  model: string
  supportsMultimodal: boolean
  systemPrompt: string
  temperature: number
  maxTokens: number
  color?: string
  avatar?: string | null
}

export {}
