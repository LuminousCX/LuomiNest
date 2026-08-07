/**
 * Markdown 代码块过滤器
 *
 * 用于 TTS/字幕等场景：跳过 ``` 包裹的代码块，避免朗读代码或特殊格式。
 * 提供无状态单次过滤与有状态流式过滤两种接口。
 */

const CODE_BLOCK_DELIMITER = '```'

/**
 * 单次过滤：返回去掉所有 ``` 代码块后的文本。
 * 不维护状态，适合非流式内容。
 */
export const filterCodeBlocks = (content: string): string => {
  if (!content) return ''
  const parts = content.split(CODE_BLOCK_DELIMITER)
  let result = ''
  let insideBlock = false

  for (let i = 0; i < parts.length; i++) {
    if (i === 0) {
      if (!insideBlock) result += parts[i]
    } else {
      insideBlock = !insideBlock
      if (!insideBlock) result += parts[i]
    }
  }

  return result
}

export interface CodeBlockFilter {
  reset: () => void
  filter: (content: string) => string
}

/**
 * 创建流式代码块过滤器。
 *
 * 在多个分片之间维护代码块开关状态，适合 LLM 流式输出场景。
 */
export const createCodeBlockFilter = (): CodeBlockFilter => {
  let insideBlock = false

  const reset = (): void => {
    insideBlock = false
  }

  const filter = (content: string): string => {
    if (!content) return ''
    const parts = content.split(CODE_BLOCK_DELIMITER)
    let result = ''

    for (let i = 0; i < parts.length; i++) {
      if (i === 0) {
        if (!insideBlock) result += parts[i]
      } else {
        insideBlock = !insideBlock
        if (!insideBlock) result += parts[i]
      }
    }

    return result
  }

  return { reset, filter }
}
