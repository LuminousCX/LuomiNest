import type { ConversationListItem } from '../../types'

export interface ToolActivity {
  id: string
  name: string
  arguments: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'blocked'
  output?: string
  iteration: number
  /** 拦截原因（status === 'blocked' 时展示） */
  blockedReason?: string
  /** 被拦截的命令 */
  blockedCommand?: string
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

/** 对话模式（普通/专业）
 * - normal: 普通模式，工具最少（任务视图操作 + 表情操控）
 * - standard: 专业模式，工作流规划，全量工具（历史 ultra 超长模式已移除）
 * 上下文隔离：切换模式需新建对话，不同模式的对话各自独立
 */
export type ChatModeLevel = 'normal' | 'standard'

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
