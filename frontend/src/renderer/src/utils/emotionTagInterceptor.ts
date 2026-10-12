/**
 * 统一标签消费器 - 在 TTS 管道中拦截 <exp:xxx> 标签，并消费
 * action / navigate / avatar_tool / task_dispatch 四类 chunk 字段（W4）
 *
 * 设计参考：
 * - airi 的 llm-marker-parser：流式分离特殊标记与文本
 * - Live2D-Virtual-Girlfriend 的 text_process：TTS 前正则剥离
 * - LuomiNest 三层防御：严格解析 + 宽松正则 + 前端兜底
 *
 * 拦截器职责：
 * 1. 从文本中提取 <exp:NAME> 标签（支持各种变体）
 * 2. 返回提取到的表情 ID（供 Live2D 驱动）
 * 3. 返回剥离标签后的纯文本（供 TTS 朗读）
 * 4. 消费后端下发的结构化指令字段（action/navigate/avatar_tool/task_dispatch，
 *    全部可选可缺省；普通模型不下发时行为与历史版本完全一致 —— 优雅降级）
 * 5. 剥离上述指令对应的行内标签残留（自闭合与非自闭合形态），
 *    保证标签不出现在消息正文与 TTS
 *
 * 支持的标签格式：
 * - <exp:happy> <exp=happy>          标准格式
 * - < exp:happy > <exp: happy />     含空格变体
 * - <exp:happy/> <exp:happy />       自闭合变体
 */

import type { ChatStreamChunk, TaskDispatchPhase } from '../types'

// 宽松正则：匹配所有 <exp:NAME> / <exp=NAME> 变体（含空格、自闭合）
// 与后端 _EMOTION_TAG_LOOSE_RE 保持一致
const EMOTION_TAG_LOOSE_RE = /<\s*exp[:=]\s*([a-zA-Z]+)\s*\/?\s*>/g

// 用于纯剥离（不需要提取表情名时）
const EMOTION_TAG_STRIP_RE = /<\s*exp[:=]\s*[a-zA-Z]+\s*\/?\s*>/g

/**
 * LuomiNest 支持的语义表情 ID（与后端 SUPPORTED_EMOTION_IDS 一致）
 */
const SUPPORTED_EMOTION_IDS = new Set([
  'happy', 'sad', 'neutral', 'love', 'surprise',
  'angry', 'think', 'awkward', 'curious', 'shy', 'excited', 'confused',
])

export interface InterceptResult {
  /** 剥离标签后的纯文本 */
  cleanText: string
  /** 提取到的最后一个有效表情 ID（用于驱动 Live2D） */
  emotion: string | null
  /** 所有提取到的表情 ID（按出现顺序） */
  emotions: string[]
}

/**
 * 拦截文本中的 <exp:xxx> 标签，提取表情并剥离标签
 *
 * @param text 可能包含 <exp:xxx> 标签的原始文本
 * @returns { cleanText, emotion, emotions }
 *
 * @example
 * interceptEmotionTags('<exp:curious>喵？') → { cleanText: '喵？', emotion: 'curious', emotions: ['curious'] }
 * interceptEmotionTags('你好<exp:happy/>再见') → { cleanText: '你好再见', emotion: 'happy', emotions: ['happy'] }
 * interceptEmotionTags('纯文本') → { cleanText: '纯文本', emotion: null, emotions: [] }
 */
export const interceptEmotionTags = (text: string): InterceptResult => {
  if (!text) return { cleanText: '', emotion: null, emotions: [] }

  const emotions: string[] = []
  let match: RegExpExecArray | null

  // 重置正则状态（全局正则有 lastIndex）
  EMOTION_TAG_LOOSE_RE.lastIndex = 0

  while ((match = EMOTION_TAG_LOOSE_RE.exec(text)) !== null) {
    const emotionId = match[1]
    if (SUPPORTED_EMOTION_IDS.has(emotionId)) {
      emotions.push(emotionId)
    }
  }

  // 剥离所有标签变体
  const cleanText = text.replace(EMOTION_TAG_STRIP_RE, '')

  // 返回最后一个有效表情（最新的表情状态）
  const emotion = emotions.length > 0 ? emotions[emotions.length - 1] : null

  return { cleanText, emotion, emotions }
}

/**
 * 仅剥离 <exp:xxx> 标签，不提取表情（用于纯文本清理场景）
 *
 * @param text 可能包含标签的文本
 * @returns 剥离标签后的文本
 */
export const stripEmotionTags = (text: string): string => {
  if (!text) return ''
  return text.replace(EMOTION_TAG_STRIP_RE, '')
}

// ── W4 统一标签消费：action / navigate / avatar_tool / task_dispatch ──

// 四类指令对应的行内标签残留剥离正则（自闭合与非自闭合形态，对齐 exp 的宽松风格）。
// 后端正常路径会把标签翻译成结构化 chunk 字段，这里兜底剥离
// 降级路径（旧会话回放/翻译失败）可能残留在正文中的标签，保证不进正文与 TTS。
const CONTROL_TAG_STRIP_RES: RegExp[] = [
  // <act:nod> <act=shake/> 等动作标签
  /<\s*act[:=]\s*[a-zA-Z]+\s*\/?\s*>/g,
  // <ui:navigate target="..."/> 开标签 + </ui:navigate> 闭标签
  /<\s*ui\s*:\s*navigate\b[^>]*\/?\s*>/gi,
  /<\s*\/\s*ui\s*:\s*navigate\s*>/gi,
  // <tool:avatar_motion>{...}</tool:avatar_motion> 整体删除（载荷是机器参数，不是朗读文本，
  // 必须先于下方开/闭标签单剥执行）
  /<\s*tool[:=]\s*[a-zA-Z_][\w-]*\b[^>]*>\s*\{[\s\S]*?\}\s*<\s*\/\s*tool[:=]\s*[a-zA-Z_][\w-]*\s*>/g,
  // <tool:avatar_motion>{...}</tool:avatar_motion> 皮套工具标签（开+闭）
  /<\s*tool[:=]\s*[a-zA-Z_][\w-]*\b[^>]*\/?\s*>/g,
  /<\s*\/\s*tool[:=]\s*[a-zA-Z_][\w-]*\s*>/g,
  // <task:start .../> / <dispatch task="..."/> 任务派发标签
  /<\s*(?:task\s*:\s*[a-z]+|dispatch)\b[^>]*\/?\s*>/gi,
]

/**
 * 剥离 exp 标签 + 四类指令标签残留（消息正文与 TTS 的统一入口）
 *
 * @param text 可能包含控制标签的文本
 * @returns 剥离所有控制标签后的文本
 */
export const stripAssistantControlTags = (text: string): string => {
  if (!text) return ''
  let result = stripEmotionTags(text)
  for (const re of CONTROL_TAG_STRIP_RES) {
    result = result.replace(re, '')
  }
  return result
}

/**
 * 动作名白名单（与后端 <act:*> 支持集一致，W4 契约钉死不得改）
 */
const SUPPORTED_ACTION_IDS = new Set(['nod', 'shake', 'think', 'hug'])

/** avatar_tool 目标名合法长度（与后端 TOOL_NAME_MAX_LEN 一致，超长视为无效指令） */
const AVATAR_TOOL_NAME_MAX_LEN = 32

/** 前端只需处理 start/done/error（detected 不会下发，防御性忽略） */
const SUPPORTED_TASK_PHASES = new Set<TaskDispatchPhase>(['start', 'done', 'error'])

/** 统一消费结果：null 字段表示该通道本 chunk 无有效指令 */
export interface UnifiedDirectives {
  /** 动作名（已过白名单，直接映射 Live2D motion group） */
  action: string | null
  /** 导航目标（路由白名单在接线层校验，这里只做非空规整） */
  navigate: string | null
  /** 皮套工具调用（已过白名单；与 emotion 同帧冲突时已按优先级让位） */
  avatarTool: { name: string; args: Record<string, string> } | null
  /** 任务派发事件（已过滤 detected 等前端不处理的阶段） */
  taskDispatch: {
    task: string
    phase: TaskDispatchPhase
    taskId: string | null
    summary: string | null
  } | null
}

/** 未知指令 console.debug 计数（不报错，静默降级） */
let ignoredDirectiveCount = 0
const debugIgnore = (kind: string, value: unknown): void => {
  ignoredDirectiveCount += 1
  console.debug(`[UnifiedTag] 忽略未知${kind}指令:`, value, `（累计 ${ignoredDirectiveCount} 次）`)
}

/** avatar_tool 规整后的驱动载荷（motion 与表情分别映射到对应渲染入口） */
export interface AvatarToolDrive {
  kind: 'motion' | 'expression'
  /** motion group 名或 expression 原生名（透传给模型，模型缺失时由渲染层安全忽略） */
  target: string
  /** motion 组内索引（缺省 0） */
  index: number
}

/**
 * 规整 avatar_tool 载荷为可驱动形态
 *
 * args 键名做防御性兼容（motion/group/name、expression/name、index），
 * 目标为空视为无效指令（忽略 + 计数）。表情名原样透传：
 * 工具通道可能携带模型原生表情名，不走语义情绪映射（避免未知 ID 被误映射为默认表情）。
 */
export const resolveAvatarToolDrive = (
  tool: { name: string; args: Record<string, string> },
): AvatarToolDrive | null => {
  const args = tool.args || {}
  const readArg = (...keys: string[]): string => {
    for (const key of keys) {
      const value = args[key]
      if (typeof value === 'string' && value.trim()) return value.trim()
    }
    return ''
  }
  if (tool.name === 'avatar_motion') {
    const target = readArg('motion', 'group', 'name')
    if (!target) {
      debugIgnore('avatar_motion(缺少目标)', tool.args)
      return null
    }
    const parsed = Number.parseInt(args.index ?? '', 10)
    return { kind: 'motion', target, index: Number.isFinite(parsed) && parsed >= 0 ? parsed : 0 }
  }
  // avatar_expression（白名单内仅剩此工具）
  const target = readArg('expression', 'name')
  if (!target) {
    debugIgnore('avatar_expression(缺少目标)', tool.args)
    return null
  }
  return { kind: 'expression', target, index: 0 }
}

/**
 * 消费 chunk 上的四类结构化指令字段（W4 统一入口）
 *
 * 全部字段可选可缺省：四个字段都缺省时返回全 null（零开销）。
 * 未知名称一律忽略 + console.debug 计数，不报错、不抛异常。
 * 优先级纪律：exp 情绪通道高于工具通道 —— 后端 avatar_tool 不下发工具种类，
 * 目标统一按 motion 驱动（表情本体始终由 emotion 通道驱动，二者不冲突可并行）；
 * emotion 既有驱动链不受本函数影响。
 *
 * @param chunk SSE 流式 chunk
 * @returns 规整后的四类指令（无有效指令的字段为 null）
 */
export const consumeChunkDirectives = (chunk: ChatStreamChunk): UnifiedDirectives => {
  const result: UnifiedDirectives = {
    action: null,
    navigate: null,
    avatarTool: null,
    taskDispatch: null,
  }
  if (!chunk) return result

  // 1. action：白名单校验，直接作为 Live2D motion group 名
  if (chunk.action) {
    if (SUPPORTED_ACTION_IDS.has(chunk.action)) {
      result.action = chunk.action
    } else {
      debugIgnore('action', chunk.action)
    }
  }

  // 2. navigate：仅做非空规整，路由白名单由接线层（router 表）校验
  if (chunk.navigate && typeof chunk.navigate === 'string' && chunk.navigate.trim()) {
    result.navigate = chunk.navigate.trim()
  }

  // 3. avatar_tool：对齐后端实际下发形状（W6 形状核查修正，唯一改动点）。
  //    后端解析器（core/tags/parser.py _on_tool）下发的 dict = {"name": <motion/表情
  //    目标名>, "args": {}} —— name 键携带的是目标名而非工具种类，工具种类
  //    （avatar_motion/avatar_expression）不随 chunk 下发，注册表白名单校验已在后端完成。
  //    此处把 wire 形状翻译成内部规范形状 { name: 'avatar_motion', args: { motion: 目标 } }，
  //    下游 resolveAvatarToolDrive / driveAvatarTool 全部无需感知差异；目标按 motion 组
  //    驱动（模型缺该组时由渲染层安全忽略），表情本体仍由 exp 情绪通道驱动（优先级纪律不变）。
  if (chunk.avatar_tool && typeof chunk.avatar_tool.name === 'string') {
    const target = chunk.avatar_tool.name.trim()
    if (target && target.length <= AVATAR_TOOL_NAME_MAX_LEN) {
      result.avatarTool = { name: 'avatar_motion', args: { motion: target } }
    } else {
      debugIgnore('avatar_tool', chunk.avatar_tool)
    }
  }

  // 4. task_dispatch：只处理 start/done/error（detected 防御性忽略）
  if (chunk.task_dispatch && typeof chunk.task_dispatch === 'object') {
    const td = chunk.task_dispatch
    if (td.task && SUPPORTED_TASK_PHASES.has(td.phase)) {
      result.taskDispatch = {
        task: td.task,
        phase: td.phase,
        taskId: td.task_id ?? null,
        summary: td.summary ?? null,
      }
    } else {
      debugIgnore('task_dispatch', td.phase)
    }
  }

  return result
}
