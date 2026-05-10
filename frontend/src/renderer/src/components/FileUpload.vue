<script setup lang="ts">
import { useFileUpload } from '../composables/useFileUpload'
import FileCard from './FileCard.vue'
import { Plus } from 'lucide-vue-next'

const { uploadingFile, isUploading, uploadAndForward, clearUploadState } = useFileUpload()

const triggerFileSelect = () => {
  if (isUploading.value) return
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.jpg,.jpeg,.png,.gif,.bmp,.webp,.pdf,.docx,.doc,.txt,.md,.csv,.json,.xml,.html,.css,.js,.py,.java,.cpp,.c,.h,.go,.rs,.ts,.sql,.yaml,.yml'
  input.onchange = async (e: Event) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (file) {
      await uploadAndForward(file)
    }
  }
  input.click()
}

defineExpose({ triggerFileSelect, clearUploadState })
</script>

<template>
  <div class="upload-container">
    <FileCard
      v-if="uploadingFile"
      :name="uploadingFile.name"
      :size="0"
      :status="uploadingFile.status"
      :error="uploadingFile.error"
      @remove="clearUploadState"
      @download="() => {}"
    />
    <button
      v-if="!uploadingFile"
      class="upload-btn"
      :disabled="isUploading"
      @click="triggerFileSelect"
    >
      <Plus :size="16" />
      <span>添加附件</span>
    </button>
  </div>
</template>

<style scoped>
.upload-container {
  width: 100%;
}

.upload-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 8px 12px;
  border: 1px dashed var(--divider-medium);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
  transition: all 0.2s;
}

.upload-btn:hover:not(:disabled) {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-bg);
}

.upload-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
