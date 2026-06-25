import type { ConversationListItem } from '../../types'

export interface ToolActivity {
  id: string
  name: string
  arguments: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  output?: string
  iteration: number
}

export interface SubagentToolCall {
  name: string
  args?: string
  output?: string
  status: 'running' | 'completed'
}

export interface SubagentActivity {
  id: string
  task: string
  depth: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress?: string
  result?: string
  error?: string
  iteration: number
  toolCalls: SubagentToolCall[]
}

export interface McpServerStatus {
  name: string
  status: string
  tool_count: number
  description?: string
  tools?: string[]
}

export interface McpStatus {
  servers: McpServerStatus[]
  totalTools: number
}

export type WorkflowModeLevel = 'flash' | 'standard' | 'pro' | 'ultra'

export interface WorkflowModeOption {
  value: WorkflowModeLevel
  label: string
  title: string
}

export interface TimeGroup {
  label: string
  items: ConversationListItem[]
}

export interface WorkflowPendingPlan {
  plan: string
  tasks: Array<{
    task_id?: string
    title: string
    description?: string
    tool_name?: string
    priority?: string
  }>
}
