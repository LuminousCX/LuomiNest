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
  usage?: {
    promptTokens?: number
    completionTokens?: number
    totalTokens?: number
  }
  suggestedQuestions?: string[]
  quote?: {
    id: string
    role: 'user' | 'assistant'
    content: string
  }
  versions?: {
    content: string
    reasoningContent?: string
    model?: string
    provider?: string
    timestamp: number
  }[]
  activeVersion?: number
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
}

export interface Conversation {
  id: string
  title: string
  agent_id?: string
  model?: string
  provider?: string
  messages: ApiMessage[]
  created_at: string
  updated_at: string
}

export interface ConversationListItem {
  id: string
  title: string
  agent_id?: string
  model?: string
  provider?: string
  last_message?: string
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
  isDefault: boolean
  defaultModel: string
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
  metadata: Record<string, any>
}

export interface AgentProfile {
  id: string
  name: string
  description: string
  systemPrompt?: string
  model?: string
  provider?: string
  color: string
  avatar?: string
  isBuiltin?: boolean
  isMain?: boolean
}

export interface MainAgentConfig {
  provider: string
  model: string
  systemPrompt: string
  temperature: number
  maxTokens: number
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
}

export interface STTConfig {
  provider?: string
  model?: string
  language?: string
  autoSend?: boolean
  autoSendDelay?: number
}

export interface GroupInfo {
  id: string
  name: string
  description: string
  type: string
  members: any[]
  memberCount: number
  aiCount: number
  lastMessage?: string
  createdAt: string
  updatedAt: string
}

export interface GroupMessage {
  id: string
  groupId: string
  senderId: string
  senderType: string
  content: string
  timestamp: string
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

export interface CollaborationPhase {
  value: string
}

export interface CollaborationSubTask {
  taskId: string
  roleId: string
  agentId?: string
  description: string
  status: string
  result?: string
  error?: string
}

export interface CollaborationEvent {
  type: string
  data: any
}

export interface ProviderLogo {
  id: string
  name: string
  color?: string
  initials?: string
  svgIcon?: string
  logo?: string
}

export {}
