<script setup lang="ts">
import { computed } from 'vue'
import { X, Download } from 'lucide-vue-next'
import LumiButton from './common/LumiButton.vue'
import { getFileIcon } from '../utils/file'
import { formatFileSize } from '../utils/format'

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

const fileIcon = computed(() => getFileIcon(props.name))
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
      <div v-else class="file-size">{{ formatFileSize(size) }}</div>
    </div>
    <div class="file-actions">
      <LumiButton variant="ghost" size="sm" icon-only aria-label="下载" @click="emit('download')">
        <template #icon>
          <Download :size="14" />
        </template>
      </LumiButton>
      <LumiButton variant="ghost" size="sm" icon-only aria-label="移除" @click="emit('remove')">
        <template #icon>
          <X :size="14" />
        </template>
      </LumiButton>
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
  width: var(--nav-item-height);
  height: var(--nav-item-height);
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
  margin-top: calc(var(--space-1) / 2);
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
  margin-top: calc(var(--space-1) / 2);
}

.file-actions {
  display: flex;
  gap: var(--space-1);
}

</style>
