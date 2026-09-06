/**
 * LuomiNest 工作流类型定义
 *
 * 对话模式（ChatMode）语义分离：
 * - normal: 普通对话模式（非工作流），工具最少，仅任务视图操作 + 表情操控
 * - standard: 专业工作流模式，工作流规划 + 全量工具（历史 ultra 超长模式已移除）
 */

/** 对话模式 */
export type ChatMode = 'normal' | 'standard'

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
    label: '专业',
    title: '专业模式：工作流规划 + 全量工具，适合复杂长任务',
  },
]

// ─── 工作流模板（S-WF §4.8）───

export interface WorkflowTemplate {
  template_id: string
  name: string
  description: string
  plan_json: string        // JSON string
  parameters_schema: string // JSON Schema string
  auto_approve: number     // 0=需审批, 1=免审批
  created_from: 'user' | 'ai'
  source_session_id: string
  created_at: string
  updated_at: string
}

export interface SaveAsTemplateRequest {
  name: string
  description?: string
  plan_json: string
  parameters_schema?: string
  auto_approve?: boolean
  created_from?: string
  source_session_id?: string
}

export interface RunTemplateRequest {
  params?: Record<string, unknown>
  auto_approve?: boolean | null
}

export interface ScheduleTemplateRequest {
  schedule: string
  params?: Record<string, unknown>
  auto_approve?: boolean
}
