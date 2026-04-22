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
  role: 'user' | 'assistant' | 'system'
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
}

export interface ChatRequest {
  messages: { role: string; content: string }[]
  model?: string
  provider?: string
  temperature?: number
  maxTokens?: number
  topP?: number
  stream?: boolean
  agentId?: string
  tools?: Record<string, any>[]
}

export interface ChatResponse {
  id: string
  content: string
  model: string
  provider: string
  usage?: Record<string, number>
}

export interface ChatStreamChunk {
  id: string
  content: string
  model: string
  provider: string
  done: boolean
  usage?: {
    promptTokens?: number
    completionTokens?: number
    totalTokens?: number
  }
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
  senderType: 'user' | 'agent'
  content: string
  timestamp: string
  role?: string
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

export {}
