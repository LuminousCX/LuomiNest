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
  createdAt?: string
  updatedAt?: string
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
}

export interface ProviderTemplate {
  id: string
  name: string
  vendor: string
  baseUrl: string
  defaultModel: string
  description: string
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

export {}
