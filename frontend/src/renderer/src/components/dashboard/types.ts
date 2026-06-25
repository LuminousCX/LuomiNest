export interface ModelProvider {
  id: string
  name: string
  icon: string
  status: 'active' | 'inactive' | 'error'
  model: string
  endpoint: string
  requests: number
  latency: number
  color: string
}

export interface PersonaConfig {
  id: string
  name: string
  avatar: string
  style: string
  voice: string
  tone: string
  active: boolean
}

export interface UsageMetric {
  label: string
  value: number | string
  unit: string
  change: number
  trend: 'up' | 'down'
  color: string
}

export interface LogEntry {
  id: string | number
  timestamp: string
  level: 'info' | 'warn' | 'error' | 'success'
  source: string
  message: string
}
