/**
 * LuomiNest 工作流类型定义
 *
 * 对话模式（ChatMode）语义分离：
 * - normal: 普通对话模式（非工作流），工具最少，仅任务视图操作 + 表情操控
 * - standard: 标准工作流模式，均衡裁剪，排除细粒度浏览器自动化工具
 * - ultra: 超长工作流模式，全部工具传给 LLM
 */

/** 对话模式 */
export type ChatMode = 'normal' | 'standard' | 'ultra'

/** 工作流节点类型（供前端流程图渲染分类） */
export type WorkflowNodeType = 'input' | 'agent' | 'tool' | 'condition' | 'output'

/** 工作流任务状态 */
export type WorkflowTaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'skipped'

/** 工作流执行阶段 */
export type WorkflowPhase =
  | 'analyzing'
  | 'planning'
  | 'waiting_confirmation'
  | 'executing'
  | 'synthesizing'
  | 'completed'
  | 'failed'

/** 对话模式选项 */
export interface ChatModeOption {
  value: ChatMode
  label: string
  title: string
}

/** 工作流计划任务（AI 返回的 JSON 语法中的任务定义） */
export interface WorkflowPlanTask {
  title: string
  description: string
  tool_name: string
  arguments: Record<string, unknown>
  depends_on: string[]
  priority: 'normal' | 'high' | 'urgent' | 'low'
  node_type: WorkflowNodeType
}

/** 工作流计划 JSON（AI 返回的完整 JSON 语法） */
export interface WorkflowPlanJSON {
  analysis: string
  plan: string
  tasks: WorkflowPlanTask[]
}

/** 工作流任务（运行时状态） */
export interface WorkflowTask {
  task_id: string
  title: string
  description: string
  task_type: string
  tool_name: string
  arguments: Record<string, unknown>
  depends_on: string[]
  priority: 'normal' | 'high' | 'urgent' | 'low'
  node_type: WorkflowNodeType
  status: WorkflowTaskStatus
  result: string | null
  error: string | null
  metadata: Record<string, unknown>
  started_at: string | null
  completed_at: string | null
}

/** 工作流会话 */
export interface WorkflowSession {
  session_id: string
  user_message: string
  phase: WorkflowPhase
  plan: string | null
  tasks: WorkflowTask[]
  final_result: string | null
  error: string | null
  created_at: string
  completed_at: string | null
  conversation_id: string | null
  stats: {
    total: number
    completed: number
    failed: number
  }
}

/** 定时任务（数据库持久化） */
export interface ScheduledTask {
  task_id: string
  name: string
  schedule_cron: string
  schedule_type: 'cron' | 'interval' | 'once'
  action: string
  description: string | null
  context: string | null
  created_from: 'manual' | 'workflow' | 'normal_chat'
  is_active: boolean
  created_at: string
  last_run_at: string | null
}

/** 工具调用记录 */
export interface ToolCallRecord {
  record_id: string
  session_id: string | null
  conversation_id: string | null
  tool_name: string
  arguments: Record<string, unknown>
  result: string
  success: boolean
  duration_ms: number
  created_at: string
}

/** 对话模式选项配置 */
export const CHAT_MODE_OPTIONS: ChatModeOption[] = [
  {
    value: 'normal',
    label: '普通',
    title: '普通模式：快速对话，仅支持任务视图操作和表情操控',
  },
  {
    value: 'standard',
    label: '标准',
    title: '标准模式：工作流规划，平衡速度与深度，排除细粒度浏览器工具',
  },
  {
    value: 'ultra',
    label: '超长',
    title: '超长模式：工作流规划，全部工具可用，适合复杂长任务',
  },
]
