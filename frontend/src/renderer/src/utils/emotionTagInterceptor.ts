/**
 * 表情标签拦截器 - 在 TTS 管道中拦截 <exp:xxx> 标签
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
 *
 * 支持的标签格式：
 * - <exp:happy> <exp=happy>          标准格式
 * - < exp:happy > <exp: happy />     含空格变体
 * - <exp:happy/> <exp:happy />       自闭合变体
 */

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
