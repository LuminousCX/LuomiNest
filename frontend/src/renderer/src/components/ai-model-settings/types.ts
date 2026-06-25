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
  defaultModel: string
  isDefault: boolean
}

export interface TestResult {
  success: boolean
  modelCount: number
  error: string
}
