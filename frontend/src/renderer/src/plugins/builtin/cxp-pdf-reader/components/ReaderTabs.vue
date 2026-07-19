<script setup lang="ts">
/**
 * ReaderTabs — PDF 阅读器多标签栏。
 *
 * 显示当前打开的所有文档标签，支持点击切换、关闭、新建。
 */
import { computed } from 'vue'
import { FileText, X, Plus } from 'lucide-vue-next'
import type { CxPdfFileType } from '../services/pdfApi'

interface CxPdfTab {
  id: string
  fileName: string
  fileId: string
  fileType: CxPdfFileType
  pageCount: number
  loaded: boolean
}

const props = defineProps<{
  tabs: CxPdfTab[]
  activeTabId: string | null
}>()

const emit = defineEmits<{
  'tab-click': [tabId: string]
  'tab-close': [tabId: string]
  'new-tab': []
}>()

// 文件类型图标颜色映射
const fileTypeColor = (fileType: CxPdfFileType): string => {
  switch (fileType) {
    case 'pdf': return 'var(--lumi-danger)'
    case 'docx': return 'var(--lumi-info)'
    case 'txt': return 'var(--text-muted)'
    default: return 'var(--text-muted)'
  }
}

// 文件名简短显示
const shortName = computed(() => (name: string): string => {
  if (name.length <= 24) return name
  const dotIdx = name.lastIndexOf('.')
  const ext = dotIdx > 0 ? name.slice(dotIdx) : ''
  const base = dotIdx > 0 ? name.slice(0, dotIdx) : name
  const trimmed = base.length > 18 ? `${base.slice(0, 15)}...` : base
  return ext ? `${trimmed}${ext}` : trimmed
})

// 处理标签点击关闭：阻止事件冒泡，避免触发 tab-click
const handleClose = (e: MouseEvent, tabId: string) => {
  e.stopPropagation()
  emit('tab-close', tabId)
}
</script>

<template>
  <div class="reader-tabs">
    <div class="tabs-list">
      <button
        v-for="tab in props.tabs"
        :key="tab.id"
        class="tab-item"
        :class="{ active: tab.id === props.activeTabId }"
        :title="tab.fileName"
        @click="emit('tab-click', tab.id)"
      >
        <FileText
          :size="14"
          class="tab-icon"
          :style="{ color: fileTypeColor(tab.fileType) }"
        />
        <span class="tab-label">{{ shortName(tab.fileName) }}</span>
        <span
          class="tab-close"
          role="button"
          tabindex="-1"
          @click="(e) => handleClose(e, tab.id)"
        >
          <X :size="12" />
        </span>
      </button>

      <button
        class="tab-new"
        title="新建标签（打开文件）"
        @click="emit('new-tab')"
      >
        <Plus :size="14" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.reader-tabs {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  overflow: hidden;
}

.tabs-list {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
  padding: 0 var(--space-1);
}

.tabs-list::-webkit-scrollbar {
  height: 4px;
}

.tabs-list::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: var(--radius-full);
}

.tab-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: 30px;
  padding: 0 var(--space-2);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all var(--transition-fast);
}

.tab-item:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.tab-item.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  border-color: var(--lumi-primary-border);
}

.tab-icon {
  flex-shrink: 0;
}

.tab-label {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tab-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: var(--radius-xs);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.tab-close:hover {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.tab-new {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 30px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.tab-new:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}
</style>
