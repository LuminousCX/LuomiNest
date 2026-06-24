<script setup lang="ts">
import { computed } from 'vue'
import { FileText, Image, File, X, Download } from 'lucide-vue-next'

const props = defineProps<{
  name: string
  size: number
  status?: 'uploading' | 'success' | 'failed'
  error?: string
}>()

const emit = defineEmits<{
  remove: []
  download: []
}>()

const fileIcon = computed(() => {
  const ext = props.name.split('.').pop()?.toLowerCase()
  if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].includes(ext || '')) {
    return Image
  }
  if (['txt', 'md', 'json', 'xml', 'csv'].includes(ext || '')) {
    return FileText
  }
  return File
})

const formatSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}
</script>

<template>
  <div class="file-card" :class="{ 'status-failed': status === 'failed' }">
    <div class="file-icon-wrapper">
      <component :is="fileIcon" :size="20" />
    </div>
    <div class="file-info">
      <div class="file-name">{{ name }}</div>
      <div v-if="status === 'uploading'" class="file-status uploading">上传中...</div>
      <div v-else-if="status === 'success'" class="file-status success">已附加</div>
      <div v-else-if="status === 'failed'" class="file-status failed">{{ error || '上传失败' }}</div>
      <div v-else class="file-size">{{ formatSize(size) }}</div>
    </div>
    <div class="file-actions">
      <button class="action-btn" @click="emit('download')" title="下载">
        <Download :size="14" />
      </button>
      <button class="action-btn" @click="emit('remove')" title="移除">
        <X :size="14" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.file-card {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.file-card:hover {
  border-color: var(--border);
}

.file-card.status-failed {
  border-color: var(--lumi-danger-light);
  background: var(--lumi-danger-light);
}

.file-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--surface-hover);
  color: var(--text-muted);
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: var(--text-base);
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-status {
  font-size: var(--text-xs);
  margin-top: 2px;
}

.file-status.uploading {
  color: var(--lumi-brand);
}

.file-status.success {
  color: var(--lumi-success);
}

.file-status.failed {
  color: var(--lumi-danger-hover);
}

.file-size {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: 2px;
}

.file-actions {
  display: flex;
  gap: var(--space-1);
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.action-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}
</style>
