<script setup lang="ts">
import { useFileUpload } from '../composables/useFileUpload'
import FileCard from './FileCard.vue'

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
  </div>
</template>

<style scoped>
.upload-container {
  width: 100%;
}
</style>
