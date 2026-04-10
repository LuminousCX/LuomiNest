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
