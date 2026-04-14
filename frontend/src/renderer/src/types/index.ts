export interface AgentProfile {
  id: string
  name: string
  description: string
  avatar?: string
  color: string
  systemPrompt: string
  model: string
  capabilities: string[]
  isActive: boolean
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

export type ModelType = 'live2d' | 'blender' | 'vam' | 'vrm'
export type ModelStatus = 'uploading' | 'processing' | 'ready' | 'error' | 'archived'
export type TriggerType = 'manual' | 'auto' | 'event' | 'idle' | 'emotion'
export type BlendMode = 'override' | 'add' | 'mix'
export type InteractionType = 'tap' | 'drag' | 'pinch' | 'hover' | 'voice' | 'motion'

export interface ModelAsset {
  id: string
  name: string
  description: string | null
  model_type: ModelType
  status: ModelStatus
  file_size: number
  file_hash: string | null
  original_filename: string
  thumbnail_path: string | null
  version: number
  metadata_json: Record<string, any> | null
  tags: string[] | null
  user_id: string | null
  is_public: boolean
  created_at: string
  updated_at: string
}

export interface ModelListResult {
  items: ModelAsset[]
  total: number
  page: number
  page_size: number
}

export interface ModelConfiguration {
  id: string
  model_id: string
  config_name: string
  config_type: string
  display_name: string | null
  description: string | null
  properties: Record<string, any> | null
  animation_params: Record<string, any> | null
  render_settings: Record<string, any> | null
  physics_settings: Record<string, any> | null
  is_active: boolean
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface ModelAnimation {
  id: string
  model_id: string
  name: string
  group: string | null
  duration: number
  fps: number
  loop: boolean
  trigger_type: string
  trigger_condition: Record<string, any> | null
  blend_mode: string
  blend_weight: number
  metadata_json: Record<string, any> | null
  sort_order: number
  is_enabled: boolean
  created_at: string
}

export interface ModelInteraction {
  id: string
  model_id: string
  name: string
  interaction_type: string
  trigger_event: string
  target_parameter: string
  response_curve: Record<string, any> | null
  min_value: number
  max_value: number
  default_value: number
  cooldown_ms: number
  priority: number
  is_enabled: boolean
  created_at: string
}

export interface ModelVersion {
  id: string
  model_id: string
  version: number
  file_path: string
  file_size: number
  file_hash: string
  change_log: string | null
  configuration_snapshot: Record<string, any> | null
  created_at: string
  created_by: string | null
}

export interface PreviewResponse {
  model_id: string
  render_url: string
  thumbnail_url: string | null
  metadata: Record<string, any> | null
}

export {}
