/**
 * 全局常量定义 — 消除跨视图重复硬编码
 */
import type { AgentProfile } from './types'

/** 主 Agent 固定标识（与后端 _MAIN_AGENT_ID 保持一致） */
export const MAIN_AGENT_ID = 'luominest_main_agent'

/** 主 Agent 固定 Profile（工作台 / 皮套工坊共用） */
export const MAIN_AGENT_PROFILE: AgentProfile = {
  id: MAIN_AGENT_ID,
  name: '主智能体',
  description: 'LuomiNest 工作台主 Agent，驱动 Live2D、记忆、工具、MCP 和子 Agent',
  color: 'var(--lumi-brand)',
  isMain: true,
  isActive: true,
}
