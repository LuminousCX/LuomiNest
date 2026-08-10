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

/* ============================================================================
 * 皮套工坊 / Live2D 常量
 * ========================================================================== */

/** Live2D 模型默认缩放 */
export const LUOMINEST_DEFAULT_MODEL_SCALE = 0.25

/** Live2D 模型缩放安全边界 */
export const LUOMINEST_MIN_MODEL_SCALE = 0.05
export const LUOMINEST_MAX_MODEL_SCALE = 3.0
export const LUOMINEST_MAX_INITIAL_MODEL_SCALE = 2.0

/** 模型加载重试策略 */
export const LUOMINEST_MODEL_MAX_RETRIES = 3
export const LUOMINEST_MODEL_RETRY_BASE_DELAY_MS = 1000

/** Canvas 就绪等待超时 */
export const LUOMINEST_CANVAS_READY_TIMEOUT_MS = 2000

/** 默认 TTS 语音 */
export const LUOMINEST_DEFAULT_TTS_VOICE = 'zh-CN-XiaoxiaoNeural'

/** 字幕字符动画间隔基准（毫秒） */
export const LUOMINEST_SUBTITLE_CHAR_INTERVAL_MS = 60
export const LUOMINEST_SUBTITLE_MIN_CHAR_INTERVAL_MS = 30

/** 模型在容器中的垂直位置（0-1） */
export const LUOMINEST_MODEL_ANCHOR_Y_RATIO = 0.90

/* ============================================================================
 * 动画与过渡常量（与 variables.css 对应，避免脚本中硬编码）
 * ========================================================================== */

/** 页面切换动画时长（毫秒） */
export const LUOMINEST_PAGE_SWITCH_ENTER_MS = 180
export const LUOMINEST_PAGE_SWITCH_LEAVE_MS = 120
export const LUOMINEST_PAGE_FADE_ENTER_MS = 200
export const LUOMINEST_PAGE_FADE_LEAVE_MS = 140

/** Avatar 舞台入场动画时长（毫秒） */
export const LUOMINEST_STAGE_APPEAR_MS = 600

/** 侧边栏导航树形菜单 stagger 步长（毫秒） */
export const LUOMINEST_NAV_TREE_STAGGER_MS = 35

/** Live2D Idle 动画进度显示值（百分比） */
export const LUOMINEST_IDLE_ANIMATION_PROGRESS = {
  breath: 65,
  blink: 40,
  idleMotion: 80,
  headTrack: 50,
} as const

/** 导入成功提示显示时长（毫秒） */
export const LUOMINEST_IMPORT_SUCCESS_TTL_MS = 2000
