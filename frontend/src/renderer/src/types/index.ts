export interface AgentProfile {
  id: string
  name: string
  description: string
  avatar?: string
  color: string
  systemPrompt: string
  model: string
  provider?: string
  capabilities: string[]
  isActive: boolean
  isMain?: boolean
  skills: string[]
  mcpServers: string[]
  createdAt?: string
  updatedAt?: string
}

export interface MainAgentConfig {
  provider: string
  model: string
  systemPrompt: string
  temperature: number
  maxTokens: number
}

export interface ProviderLogo {
  id: string
  name: string
  color: string
  initials: string
}

export interface WorkflowNode {
  id: string
  name: string
  type: 'agent' | 'tool' | 'condition' | 'output' | 'input'
  agentId?: string
  config: Record<string, any>
  position: { x: number; y: number }
}

export interface WorkflowConnection {
  id: string
  sourceNodeId: string
  targetNodeId: string
  label?: string
}

export interface WorkflowDefinition {
  id: string
  name: string
  description: string
  nodes: WorkflowNode[]
  connections: WorkflowConnection[]
  createdAt: number
  updatedAt: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  timestamp: number
  agentId?: string
  model?: string
  provider?: string
  done?: boolean
  usage?: {
    promptTokens?: number
    completionTokens?: number
    totalTokens?: number
  }
  toolCalls?: ToolCallInfo[]
  toolCallId?: string
  toolResults?: ToolCallResult[]
}

export interface ToolCallInfo {
  id: string
  type: string
  function: {
    name: string
    arguments: string
  }
}

export interface ToolCallResult {
  tool_call_id: string
  tool_name: string
  result: string
  status: 'success' | 'error'
}

export interface ChatRequest {
  messages: { role: string; content: string; tool_calls?: ToolCallInfo[]; tool_call_id?: string; name?: string }[]
  model?: string
  provider?: string
  temperature?: number
  maxTokens?: number
  topP?: number
  stream?: boolean
  agentId?: string
  tools?: Record<string, any>[]
  timestamp?: number
}

export interface ChatResponse {
  id: string
  content: string | null
  model: string
  provider: string
  tool_calls?: ToolCallInfo[] | null
  tool_results?: ToolCallResult[] | null
  usage?: Record<string, number>
  timestamp?: number
}

export interface ChatStreamChunk {
  id: string
  content: string
  model: string
  provider: string
  done: boolean
  tool_calls?: ToolCallInfo[] | null
  tool_results?: ToolCallResult[] | null
  usage?: {
    promptTokens?: number
    completionTokens?: number
    totalTokens?: number
  }
  timestamp?: number
}

export interface Conversation {
  id: string
  title: string
  agentId?: string
  model?: string
  provider?: string
  messages: ChatMessage[]
  createdAt: string
  updatedAt: string
}

export interface ConversationListItem {
  id: string
  title: string
  agentId?: string
  model?: string
  provider?: string
  lastMessage?: string
  createdAt: string
  updatedAt: string
}

export interface ModelProvider {
  id: string
  name: string
  vendor: string
  baseUrl: string
  apiKeySet: boolean
  defaultModel: string
  isDefault: boolean
  models: ModelInfo[]
}

export interface ModelInfo {
  id: string
  name: string
  owned_by?: string
  provider?: string
  size?: number
  modified_at?: string
}

export interface TTSConfig {
  provider: string
  model: string
  voice: string
  speed: number
  baseUrl: string
  apiKeySet: boolean
}

export interface STTConfig {
  provider: string
  model: string
  language: string
  autoSend: boolean
  autoSendDelay: number
  baseUrl: string
  apiKeySet: boolean
}

export interface ModelConfig {
  defaultProvider: string
  defaultModel: string
  defaultTemperature: number
  defaultMaxTokens: number
  defaultTopP: number
  fastProvider?: string
  fastModel?: string
  fastTemperature?: number
  fastMaxTokens?: number
  reasonerProvider?: string
  reasonerModel?: string
  reasonerTemperature?: number
  reasonerMaxTokens?: number
  visionProvider?: string
  visionModel?: string
  visionTemperature?: number
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
}

export interface ProviderTemplate {
  id: string
  name: string
  vendor: string
  baseUrl: string
  defaultModel: string
  description: string
  category: 'cloud' | 'local' | 'aggregator'
  color: string
  initials: string
}

export interface Tab {
  id: string
  title: string
  url: string
  favicon?: string
  loading?: boolean
  error?: TabError
  active?: boolean
  captchaDetected?: boolean
  sleeping?: boolean
}

export interface TabError {
  code: number
  title: string
  message: string
}

export interface Bookmark {
  name: string
  url: string
}

export interface ApiError {
  code: string
  message: string
}

export interface ApiResponse<T> {
  data?: T
  error?: ApiError
}

export interface SkillDefinition {
  name: string
  description: string
  category: string
  parameters: Record<string, SkillParameter>
  isActive: boolean
  isBuiltin: boolean
  promptTemplate?: string
  tags: string[]
}

export interface SkillParameter {
  type: string
  description: string
  required: boolean
  default?: any
}

export interface MCPServer {
  name: string
  command: string
  args: string[]
  env?: Record<string, string>
  transport: 'stdio' | 'sse' | 'http'
  url?: string
  description: string
  isActive: boolean
}

export interface MCPTool {
  name: string
  description: string
  parameters: Record<string, any>
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

export interface GroupMember {
  agentId: string
  name: string
  type: 'agent' | 'user'
  role: string
  color: string
}

export interface GroupMessage {
  id: string
  senderId: string
  senderName?: string
  senderType: 'user' | 'agent' | 'system'
  content: string
  timestamp: string
  role?: string
  collaboration?: CollaborationInfo
}

export interface CollaborationInfo {
  sessionId: string
  taskId?: string
  taskDescription?: string
  type?: 'task_result' | 'synthesis'
}

export type CollaborationPhase = 'analyzing' | 'dispatching' | 'executing' | 'synthesizing' | 'completed' | 'failed'

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed'

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

export interface CollaborationSubTask {
  taskId: string
  roleId: string
  agentId: string | null
  description: string
  inputContent: string
  dependsOn: string[]
  status: TaskStatus
  result: string | null
  error: string | null
  startedAt: string | null
  completedAt: string | null
}

export interface CollaborationSession {
  sessionId: string
  groupId: string
  userMessage: string
  phase: CollaborationPhase
  plan: string | null
  subTasks: CollaborationSubTask[]
  finalResult: string | null
  coordinatorResponse: string | null
  createdAt: string
  completedAt: string | null
}

export type CollaborationEventType =
  | 'session_start'
  | 'phase_change'
  | 'plan_created'
  | 'tasks_started'
  | 'task_started'
  | 'task_agent_assigned'
  | 'task_completed'
  | 'task_failed'
  | 'direct_response'
  | 'final_result'
  | 'session_end'
  | 'error'

export interface CollaborationEvent {
  type: CollaborationEventType
  data: Record<string, any>
}

export interface RAGSearchResult {
  content: string
  source: string
  score: number
  metadata: Record<string, any>
}

export interface ToolCallResult {
  tool: string
  result: string
  status: 'success' | 'error'
}

export interface UserProfile {
  name: string
  nickname: string
  age: string
  gender: string
  occupation: string
  location: string
  timezone: string
  language: string
  interests: string[]
  hobbies: string[]
  preferences: Record<string, string>
  notes: string
  updated_at: string
}

export {}
