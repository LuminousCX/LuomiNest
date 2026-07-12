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

/** 对话模式（普通/标准/超长）
 * - normal: 普通模式，非工作流，工具最少（任务视图操作 + 表情操控）
 * - standard: 标准模式，工作流，排除细粒度浏览器自动化工具
 * - ultra: 超长模式，工作流，全部工具可用
 */
export type ChatModeLevel = 'normal' | 'standard' | 'ultra'

export interface WorkflowModeOption {
  value: ChatModeLevel
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
