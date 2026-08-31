export interface MainModelConfig {
  selectedProvider: string
  model: string
  temperature: number
  topP: number
  maxTokens: number
}

export interface ReasonerModelConfig {
  selectedProvider: string
  model: string
  temperature: number
  maxTokens: number
  reasoningEffort: string
}

export interface NewProviderForm {
  id: string
  name: string
  vendor: string
  baseUrl: string
  apiKey: string
  defaultModel: string
  isDefault: boolean
}

export interface EditProviderForm {
  name: string
  vendor: string
  baseUrl: string
  apiKey: string
  apiKeyPrefix?: string
  defaultModel: string
  isDefault: boolean
  /** 接入协议：auto | chat_completions | anthropic_messages */
  protocol: string
}

export interface TestResult {
  success: boolean
  modelCount: number
  error: string
}
