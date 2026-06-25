<script setup lang="ts">
import { computed } from 'vue'
import { Download } from 'lucide-vue-next'
import LumiButton from './common/LumiButton.vue'
import LumiEmptyState from './common/LumiEmptyState.vue'
import LumiModal from './common/LumiModal.vue'

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
  <LumiModal
    :visible="visible"
    :title="fileName"
    size="lg"
    :closable="true"
    :mask-closable="true"
    @close="emit('close')"
  >
    <template #header>
      <LumiButton variant="outline" size="sm" @click="handleDownload">
        <template #icon>
          <Download :size="16" />
        </template>
        下载
      </LumiButton>
    </template>
    <div class="file-preview-body">
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
  </LumiModal>
</template>

<style scoped>
.file-preview-body {
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
