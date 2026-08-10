<script setup lang="ts">
/**
 * DropZone — PDF 阅读器空状态拖拽区。
 *
 * 全屏拖拽区域，中心显示提示文字 + 选择文件按钮。
 * 下方显示最近打开记录（仅文件名 + 时间），点击触发 reopen-item 事件。
 */
import { computed } from 'vue'
import { FileText, FolderOpen, Trash2, Clock, FileUp } from 'lucide-vue-next'
import type { CxPdfFileType } from '../services/pdfApi'

interface CxHistoryItem {
  fileName: string
  fileType: CxPdfFileType
  openedAt: number
}

const props = defineProps<{
  history: CxHistoryItem[]
}>()

const emit = defineEmits<{
  'file-loaded': [file: File]
  'clear-history': []
  'reopen-item': [item: CxHistoryItem]
  'click-select': []
}>()

// 文件类型图标颜色
const fileTypeColor = (fileType: CxPdfFileType): string => {
  switch (fileType) {
    case 'pdf': return 'var(--lumi-danger)'
    case 'docx': return 'var(--lumi-info)'
    case 'txt': return 'var(--text-muted)'
    default: return 'var(--text-muted)'
  }
}

// 格式化时间
const formatTime = (ts: number): string => {
  const now = Date.now()
  const diff = now - ts
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  if (diff < minute) return '刚刚'
  if (diff < hour) return `${Math.floor(diff / minute)} 分钟前`
  if (diff < day) return `${Math.floor(diff / hour)} 小时前`
  if (diff < 7 * day) return `${Math.floor(diff / day)} 天前`
  const date = new Date(ts)
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

const hasHistory = computed(() => props.history.length > 0)
</script>

<template>
  <div
    class="drop-zone"
    @click="emit('click-select')"
    @dragover.prevent.stop
    @drop.prevent.stop="(e) => {
      const files = e.dataTransfer?.files
      if (files && files.length > 0) emit('file-loaded', files[0])
    }"
  >
    <div class="drop-zone-content">
      <!-- 拖拽图标 -->
      <div class="drop-icon">
        <FileUp :size="64" />
      </div>

      <h2 class="drop-title">拖拽 PDF / Word / TXT 文件到此处</h2>
      <p class="drop-subtitle">或</p>
      <button
        class="select-btn"
        @click.stop="emit('click-select')"
      >
        <FolderOpen :size="16" />
        <span>选择文件</span>
      </button>

      <p class="drop-hint">
        支持的格式：PDF (.pdf)、Word (.docx)、纯文本 (.txt)
      </p>
    </div>

    <!-- 最近打开记录 -->
    <div v-if="hasHistory" class="history-section">
      <div class="history-header">
        <div class="history-title">
          <Clock :size="14" />
          <span>最近打开</span>
        </div>
        <button
          class="clear-btn"
          title="清空记录"
          @click.stop="emit('clear-history')"
        >
          <Trash2 :size="14" />
          <span>清空</span>
        </button>
      </div>

      <ul class="history-list">
        <li
          v-for="(item, idx) in props.history"
          :key="`${item.fileName}-${idx}`"
          class="history-item"
          :title="`重新打开：${item.fileName}`"
          @click.stop="emit('reopen-item', item)"
        >
          <FileText
            :size="16"
            class="history-icon"
            :style="{ color: fileTypeColor(item.fileType) }"
          />
          <span class="history-name">{{ item.fileName }}</span>
          <span class="history-time">{{ formatTime(item.openedAt) }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.drop-zone {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-8);
  padding: var(--space-10) var(--space-6);
  background: var(--bg);
  cursor: pointer;
  overflow: auto;
  transition: background var(--transition-fast);
}

.drop-zone:hover {
  background: var(--surface-hover);
}

.drop-zone-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-8) var(--space-10);
  border: 2px dashed var(--border);
  border-radius: var(--radius-xl);
  background: var(--surface);
  transition: all var(--transition-normal);
  max-width: 520px;
  width: 100%;
}

.drop-zone:hover .drop-zone-content {
  border-color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.drop-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
  opacity: 0.7;
  transition: opacity var(--transition-fast);
}

.drop-zone:hover .drop-icon {
  opacity: 1;
}

.drop-title {
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--text);
  text-align: center;
  margin: 0;
}

.drop-subtitle {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin: 0;
}

.select-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-5);
  border: 1px solid var(--lumi-primary);
  border-radius: var(--radius-md);
  background: var(--lumi-primary);
  color: var(--text-inverse);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.select-btn:hover {
  background: var(--lumi-primary-hover);
  border-color: var(--lumi-primary-hover);
}

.drop-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin: var(--space-2) 0 0;
  text-align: center;
}

.history-section {
  width: 100%;
  max-width: 520px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  transition: opacity var(--transition-fast);
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
  padding: 0 var(--space-1);
}

.history-title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: var(--font-medium);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.clear-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: none;
  border-radius: var(--radius-xs);
  background: transparent;
  color: var(--text-muted);
  font-size: var(--text-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.clear-btn:hover {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.history-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.history-item:hover {
  background: var(--surface-hover);
}

.history-icon {
  flex-shrink: 0;
}

.history-name {
  flex: 1;
  font-size: var(--text-sm);
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-time {
  flex-shrink: 0;
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}
</style>
