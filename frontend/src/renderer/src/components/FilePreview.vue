<script setup lang="ts">
import { computed } from 'vue'
import { X, FileText, Image, Download, File } from 'lucide-vue-next'
import LumiButton from './common/LumiButton.vue'
import LumiEmptyState from './common/LumiEmptyState.vue'

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
              <LumiEmptyState icon="file" title="无法预览此文件类型">
                <template #action>
                  <LumiButton variant="primary" @click="handleDownload">
                    <template #icon>
                      <Download :size="16" />
                    </template>
                    下载文件
                  </LumiButton>
                </template>
              </LumiEmptyState>
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
  z-index: var(--z-modal);
  padding: var(--space-5);
}

.file-preview-modal {
  background: var(--surface);
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
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border-light);
}

.file-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text);
}

.file-name {
  font-size: var(--text-md);
  font-weight: var(--font-medium);
}

.modal-actions {
  display: flex;
  gap: var(--space-2);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-base);
}

.action-btn:hover {
  background: var(--surface-hover);
}

.close-btn {
  display: flex;
  align-items: center;
  padding: var(--space-1);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
}

.close-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.modal-body {
  flex: 1;
  overflow: auto;
  padding: var(--space-4);
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
  color: var(--text);
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
  margin: 0;
}

.no-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-6) var(--space-4);
  color: var(--text-muted);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--transition-fast);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
