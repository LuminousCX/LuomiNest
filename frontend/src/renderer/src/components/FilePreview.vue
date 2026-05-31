<script setup lang="ts">
import { computed } from 'vue'
import { X, FileText, Image, File, Download } from 'lucide-vue-next'

const props = defineProps<{
  visible: boolean
  fileName: string
  fileType?: string
  fileContent?: string
}>()

const emit = defineEmits<{
  close: []
}>()

const isImage = computed(() => props.fileType === 'image')
const isText = computed(() => props.fileType === 'text' || !props.fileType)

const handleDownload = () => {
  if (!props.fileContent) return
  
  let blob: Blob
  if (isImage.value) {
    const base64Data = props.fileContent.split(',')[1]
    const byteString = atob(base64Data)
    const mimeType = props.fileContent.split(':')[1].split(';')[0]
    const ab = new ArrayBuffer(byteString.length)
    const ia = new Uint8Array(ab)
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i)
    }
    blob = new Blob([ab], { type: mimeType })
  } else {
    blob = new Blob([props.fileContent], { type: 'text/plain' })
  }
  
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = props.fileName
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="visible" class="file-preview-overlay" @click.self="emit('close')">
        <div class="file-preview-modal">
          <div class="modal-header">
            <div class="file-info">
              <component :is="isImage ? Image : isText ? FileText : File" :size="18" />
              <span class="file-name">{{ fileName }}</span>
            </div>
            <div class="modal-actions">
              <button class="action-btn" @click="handleDownload">
                <Download :size="16" />
                <span>下载</span>
              </button>
              <button class="close-btn" @click="emit('close')">
                <X :size="16" />
              </button>
            </div>
          </div>
          <div class="modal-body">
            <div v-if="isImage && fileContent" class="image-preview">
              <img :src="fileContent" :alt="fileName" />
            </div>
            <div v-else-if="isText && fileContent" class="text-preview">
              <pre>{{ fileContent }}</pre>
            </div>
            <div v-else class="no-content">
              <File :size="48" />
              <p>无法预览此文件类型</p>
              <button class="download-btn" @click="handleDownload">
                <Download :size="16" />
                下载文件
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.file-preview-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--overlay-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.file-preview-modal {
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  max-width: 90%;
  max-height: 90%;
  width: 600px;
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--divider-soft);
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
}

.file-name {
  font-size: 14px;
  font-weight: 500;
}

.modal-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid var(--divider-medium);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
}

.action-btn:hover {
  background: var(--workspace-hover);
}

.close-btn {
  display: flex;
  align-items: center;
  padding: 6px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
}

.close-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.modal-body {
  flex: 1;
  overflow: auto;
  padding: 18px;
}

.image-preview {
  display: flex;
  justify-content: center;
}

.image-preview img {
  max-width: 100%;
  max-height: 500px;
  object-fit: contain;
  border-radius: var(--radius-md);
}

.text-preview {
  max-height: 500px;
  overflow: auto;
}

.text-preview pre {
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
}

.no-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: var(--text-muted);
}

.no-content p {
  margin-top: 12px;
  font-size: 14px;
}

.download-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 16px;
  padding: 10px 20px;
  background: var(--lumi-primary);
  color: var(--text-inverse);
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
}

.download-btn:hover {
  opacity: 0.9;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
