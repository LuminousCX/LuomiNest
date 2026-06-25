import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { stripEmotionTags } from './emotionTagInterceptor'

marked.setOptions({
  breaks: true,
  gfm: true,
})

export const renderMarkdown = (text: string): string => {
  if (!text) return ''
  const cleaned = stripEmotionTags(text)
  const raw = marked.parse(cleaned) as string
  return DOMPurify.sanitize(raw)
}
