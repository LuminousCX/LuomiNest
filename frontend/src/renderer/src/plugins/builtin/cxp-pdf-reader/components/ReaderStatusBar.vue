<script setup lang="ts">
/**
 * ReaderStatusBar — PDF 阅读器底部状态栏。
 *
 * 显示：当前页码 / 总页数、文件名、文件类型、缩放比例。
 */
import { computed } from 'vue'
import { FileText, FileType2, ZoomIn } from 'lucide-vue-next'
import type { CxPdfFileType } from '../services/pdfApi'

const props = defineProps<{
  currentPage: number
  totalPages: number
  fileName: string
  scale: number
  fileType: CxPdfFileType
}>()

const scalePercent = computed(() => `${Math.round(props.scale * 100)}%`)

const fileTypeLabel = computed<string>(() => {
  switch (props.fileType) {
    case 'pdf': return 'PDF'
    case 'docx': return 'Word'
    case 'txt': return 'TXT'
    default: return '—'
  }
})

const fileIcon = computed<typeof FileText>(() => {
  return props.fileType === 'unknown' ? FileType2 : FileText
})

// 文件名简短显示
const shortFileName = computed<string>(() => {
  if (props.fileName.length <= 40) return props.fileName
  const dotIdx = props.fileName.lastIndexOf('.')
  const ext = dotIdx > 0 ? props.fileName.slice(dotIdx) : ''
  const base = dotIdx > 0 ? props.fileName.slice(0, dotIdx) : props.fileName
  return `${base.slice(0, 30)}...${ext}`
})
</script>

<template>
  <footer class="reader-status-bar">
    <div class="status-section">
      <component :is="fileIcon" :size="12" class="status-icon" />
      <span class="status-text">{{ fileTypeLabel }}</span>
    </div>

    <div class="status-section">
      <span class="status-label">文件：</span>
      <span class="status-value" :title="fileName">{{ shortFileName || '—' }}</span>
    </div>

    <div class="status-spacer" />

    <div class="status-section">
      <span class="status-label">页码：</span>
      <span class="status-value">{{ currentPage }} / {{ totalPages }}</span>
    </div>

    <div class="status-section">
      <ZoomIn :size="12" class="status-icon" />
      <span class="status-value">{{ scalePercent }}</span>
    </div>
  </footer>
</template>

<style scoped>
.reader-status-bar {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: 0 var(--space-4);
  height: 28px;
  background: var(--surface);
  border-top: 1px solid var(--border);
  font-size: var(--text-xs);
  color: var(--text-muted);
  flex-shrink: 0;
  user-select: none;
}

.status-section {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  white-space: nowrap;
  flex-shrink: 0;
}

.status-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.status-label {
  color: var(--text-muted);
}

.status-value {
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-spacer {
  flex: 1;
}
</style>
