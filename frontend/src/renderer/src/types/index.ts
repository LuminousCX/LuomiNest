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
}

export interface Conversation {
  id: string
  title: string
  agent_id?: string
  model?: string
  provider?: string
  messages: ChatMessage[]
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

export interface ModelProvider {
  id: string
  name: string
  type: string
  defaultModel: string
  models: { id: string; name: string }[]
}

export interface ModelConfig {
  defaultTemperature: number
  defaultMaxTokens: number
  defaultTopP: number
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

export {}
