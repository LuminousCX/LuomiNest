/**
 * TTS 文本过滤器 - 在发送给 TTS 引擎之前清理 LLM 输出中的复杂格式
 *
 * 设计原则（参考 Open-LLM-VTuber + super-agent-party）：
 * - 保留有意义的文字内容（粗体/斜体/链接的文字）
 * - 删除结构标记（标题#/列表-/表格|/引用>）
 * - 删除 emoji 和特殊符号
 * - 字幕显示保留原始 markdown，仅 TTS 文本过滤
 *
 * 过滤顺序敏感，必须按以下顺序执行：
 * 表情标签<exp:xxx> → 代码块(状态机) → 行内代码 → 图片 → 链接 → 标题/列表/引用/分割线/表格 → 粗体 → 斜体 → 删除线 → emoji → 空白合并
 */

import { stripEmotionTags } from './emotionTagInterceptor'

// 行内代码 `code` → 保留 code 内容（在图片/链接之前处理，避免反引号干扰）
const INLINE_CODE_RE = /`([^`]+)`/g

// 图片 ![alt](url) → 整个删除（在链接之前处理）
const IMAGE_RE = /!\[([^\]]*)\]\([^)]*\)/g

// 链接 [text](url) → 保留 text
const LINK_RE = /\[([^\]]+)\]\([^)]+\)/g

// 标题 # / ## / ###（行首）
const HEADING_RE = /^#{1,6}\s+/gm

// 无序列表标记 - / * / +（行首）
const UNORDERED_LIST_RE = /^\s*[-*+]\s+/gm

// 有序列表标记 1. / 2.（行首）
const ORDERED_LIST_RE = /^\s*\d+\.\s+/gm

// 引用 >（行首）
const BLOCKQUOTE_RE = /^\s*>\s*/gm

// 水平分割线 --- / *** / ___
const HR_RE = /^\s*([-*_])\1{2,}\s*$/gm

// 表格分隔行 |---|---|
const TABLE_SEP_RE = /^\s*\|[\s:|-]*-{3,}[\s:|-]*\|?\s*$/gm

// 表格管道符 |（剩余的）
const TABLE_PIPE_RE = /\|/g

// 粗体 **text** / __text__ → 保留 text（在斜体之前处理，避免 ** 被 * 误匹配）
const BOLD_ASTERISK_RE = /\*\*([^*]+)\*\*/g
const BOLD_UNDERSCORE_RE = /__([^_]+)__/g

// 斜体 *text* / _text_ → 保留 text
const ITALIC_ASTERISK_RE = /\*([^*]+)\*/g
const ITALIC_UNDERSCORE_RE = /_([^_]+)_/g

// 删除线 ~~text~~ → 保留 text
const STRIKE_RE = /~~([^~]+)~~/g

// emoji 及特殊符号（覆盖 Emoji 1.0-15.0 + 符号 + 箭头 + Variation Selector + ZWJ）
const EMOJI_RE = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2190}-\u{21FF}\u{2B00}-\u{2BFF}\u{FE0F}\u{200D}\u{2300}-\u{23FF}\u{25A0}-\u{25FF}\u{2B00}-\u{2BFF}]/gu

// 动作描述括号（中文/英文）→ 删除
const ACTION_PAREN_RE = /[（(]\s*(微笑|思考|大笑|点头|摇头|叹气|害羞|生气|惊讶|困惑|smile|think|laugh|nod|sigh|shy|angry|surprised|confused)\s*[)）]/g

// 多余空白合并
const MULTI_SPACE_RE = /[ \t]+/g
const MULTI_NEWLINE_RE = /\n{3,}/g

/**
 * 过滤 TTS 文本，移除 markdown 语法、emoji 和特殊符号
 *
 * @param text 原始文本（可能包含 markdown/emoji）
 * @returns 清理后的纯文本，适合 TTS 朗读
 *
 * @example
 * filterTtsText('## 标题\n**你好**世界！😊') → '你好世界！'
 * filterTtsText('[链接](https://example.com)点击') → '链接点击'
 * filterTtsText('| 列1 | 列2 |\n|---|---|\n| a | b |') → '列1 列2 a b'
 */
export const filterTtsText = (text: string): string => {
  if (!text) return ''

  let result = text

  // 0. 表情标签 <exp:xxx> → 删除（必须在最前面，防止标签被朗读）
  result = stripEmotionTags(result)

  // 1. 行内代码 → 保留内容
  result = result.replace(INLINE_CODE_RE, '$1')

  // 2. 图片 → 删除
  result = result.replace(IMAGE_RE, '')

  // 3. 链接 → 保留文字
  result = result.replace(LINK_RE, '$1')

  // 4. 标题标记
  result = result.replace(HEADING_RE, '')

  // 5. 列表标记
  result = result.replace(UNORDERED_LIST_RE, '')
  result = result.replace(ORDERED_LIST_RE, '')

  // 6. 引用
  result = result.replace(BLOCKQUOTE_RE, '')

  // 7. 水平分割线
  result = result.replace(HR_RE, '')

  // 8. 表格（先删分隔行，再删管道符）
  result = result.replace(TABLE_SEP_RE, '')
  result = result.replace(TABLE_PIPE_RE, ' ')

  // 9. 粗体 → 保留文字（在斜体之前）
  result = result.replace(BOLD_ASTERISK_RE, '$1')
  result = result.replace(BOLD_UNDERSCORE_RE, '$1')

  // 10. 斜体 → 保留文字
  result = result.replace(ITALIC_ASTERISK_RE, '$1')
  result = result.replace(ITALIC_UNDERSCORE_RE, '$1')

  // 11. 删除线 → 保留文字
  result = result.replace(STRIKE_RE, '$1')

  // 12. 动作描述括号 → 删除
  result = result.replace(ACTION_PAREN_RE, '')

  // 13. emoji 和特殊符号 → 删除
  result = result.replace(EMOJI_RE, '')

  // 14. 空白合并
  result = result.replace(MULTI_SPACE_RE, ' ')
  result = result.replace(MULTI_NEWLINE_RE, '\n\n')

  return result.trim()
}
