<script setup lang="ts">
/**
 * DocxViewer — Word 文档查看器（简化版）。
 *
 * 不还原 Word 原始样式，仅按段落显示后端提取的纯文本。
 * 大纲中的标题会被加粗显示。
 */
import { computed } from 'vue'
import { FileText } from 'lucide-vue-next'
import type { CxPdfOutlineItem } from '../services/pdfApi'

const props = defineProps<{
  text: string
  outline: CxPdfOutlineItem[]
}>()

// 标题集合（用于加粗匹配的段落）
const headingSet = computed<Set<string>>(() => {
  const set = new Set<string>()
  const walk = (items: CxPdfOutlineItem[]) => {
    items.forEach((item) => {
      if (item.title) set.add(item.title.trim())
      if (item.children) walk(item.children)
    })
  }
  walk(props.outline)
  return set
})

interface Paragraph {
  text: string
  isHeading: boolean
  level: number
}

// 将文本按段落切分并标记标题
const paragraphs = computed<Paragraph[]>(() => {
  if (!props.text) return []
  const lines = props.text.split(/\r?\n/)
  return lines.map((line) => {
    const trimmed = line.trim()
    if (!trimmed) return { text: '', isHeading: false, level: 0 }
    // 简化判定：行首以 # 开头视为 markdown 标题
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/)
    if (headingMatch) {
      return {
        text: headingMatch[2],
        isHeading: true,
        level: headingMatch[1].length,
      }
    }
    // 与大纲标题匹配的视为标题
    if (headingSet.value.has(trimmed)) {
      return { text: trimmed, isHeading: true, level: 1 }
    }
    return { text: trimmed, isHeading: false, level: 0 }
  })
})

// 段落字号映射
const headingFontSize = (level: number): string => {
  const sizes: Record<number, string> = {
    1: 'var(--text-3xl)',
    2: 'var(--text-2xl)',
    3: 'var(--text-xl)',
    4: 'var(--text-lg)',
    5: 'var(--text-md)',
    6: 'var(--text-base)',
  }
  return sizes[level] ?? 'var(--text-md)'
}
</script>

<template>
  <div class="docx-viewer">
    <div v-if="!text" class="docx-empty">
      <FileText :size="48" class="empty-icon" />
      <p class="empty-text">文档内容为空</p>
      <p class="empty-hint">后端可能未提取到文本内容</p>
    </div>

    <article v-else class="docx-article">
      <p
        v-for="(para, idx) in paragraphs"
        :key="idx"
        class="paragraph"
        :class="{
          heading: para.isHeading,
          [`heading-level-${para.level}`]: para.isHeading && para.level > 0,
        }"
        :style="para.isHeading ? { fontSize: headingFontSize(para.level) } : {}"
      >
        {{ para.text || '\u00A0' }}
      </p>
    </article>
  </div>
</template>

<style scoped>
.docx-viewer {
  flex: 1;
  overflow: auto;
  background: var(--bg-secondary);
  padding: var(--space-7) var(--space-8);
}

.docx-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-10) var(--space-4);
  color: var(--text-muted);
  text-align: center;
}

.empty-icon {
  opacity: 0.4;
}

.empty-text {
  font-size: var(--text-md);
  color: var(--text-secondary);
}

.empty-hint {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.docx-article {
  max-width: 820px;
  margin: 0 auto;
  background: var(--surface);
  padding: var(--space-8) var(--space-9);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  line-height: var(--leading-relaxed);
}

.paragraph {
  margin: 0 0 var(--space-3);
  font-size: var(--text-md);
  color: var(--text);
  word-break: break-word;
}

.paragraph.heading {
  font-weight: var(--font-bold);
  margin-top: var(--space-6);
  margin-bottom: var(--space-3);
  color: var(--text);
}

.paragraph.heading-level-1 {
  padding-bottom: var(--space-2);
  border-bottom: 2px solid var(--border);
}

.paragraph.heading-level-2,
.paragraph.heading-level-3 {
  color: var(--text);
}

.paragraph.heading-level-4,
.paragraph.heading-level-5,
.paragraph.heading-level-6 {
  color: var(--text-secondary);
}
</style>
