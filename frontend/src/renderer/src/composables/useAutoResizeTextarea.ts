import type { Ref } from 'vue'

/**
 * textarea 自适应内容高度。
 * autoResize 在输入时调用；resetTextareaHeight 用于发送后复位，
 * 高度上限默认 120px，超出后内部滚动。
 */
export function useAutoResizeTextarea(
  textareaRef: Ref<HTMLTextAreaElement | null>,
  maxHeight = 120
) {
  const autoResize = () => {
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto'
      textareaRef.value.style.height = `${Math.min(textareaRef.value.scrollHeight, maxHeight)}px`
    }
  }

  const resetTextareaHeight = () => {
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto'
    }
  }

  return { autoResize, resetTextareaHeight }
}
