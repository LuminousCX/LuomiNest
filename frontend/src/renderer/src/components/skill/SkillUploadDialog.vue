<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
import {
  X,
  Upload,
  FolderOpen,
  FileArchive,
  Loader2,
  CheckCircle2,
  AlertCircle
} from 'lucide-vue-next'

const emit = defineEmits<{
  close: []
  complete: [name: string]
}>()

type UploadStep = 'select' | 'uploading' | 'success' | 'error'

interface SelectedFile {
  name: string
  path: string
  size: number
}

const step = ref<UploadStep>('select')
const selectedFiles = ref<SelectedFile[]>([])
const skillName = ref('')
const overwrite = ref(false)
const errorMessage = ref('')
const uploadProgress = ref(0)
let progressTimer: ReturnType<typeof setInterval> | null = null
let successTimer: ReturnType<typeof setTimeout> | null = null

const canUpload = computed(() => selectedFiles.value.length > 0 && skillName.value.trim().length > 0)

const totalSize = computed(() => {
  const bytes = selectedFiles.value.reduce((sum, f) => sum + f.size, 0)
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
})

function clearTimers() {
  if (progressTimer !== null) {
    clearInterval(progressTimer)
    progressTimer = null
  }
  if (successTimer !== null) {
    clearTimeout(successTimer)
    successTimer = null
  }
}

onBeforeUnmount(() => {
  clearTimers()
})

function handleOverlayClick() {
  emit('close')
}

function extractFileName(filePath: string): string {
  return filePath.split(/[\\/]/).pop() || filePath
}

async function handleBrowse() {
  try {
    if (!window.api?.dialog?.showOpenDialog) {
      errorMessage.value = '当前环境不支持文件选择对话框，请使用拖拽方式添加文件'
      step.value = 'error'
      return
    }

    const result = await window.api.dialog.showOpenDialog({
      title: '选择技能文件',
      properties: ['openFile', 'multiSelections'],
      filters: [
        { name: '技能包', extensions: ['zip', 'tar.gz', 'tgz', 'json'] },
        { name: '所有文件', extensions: ['*'] }
      ]
    })

    if (result && !result.canceled && result.filePaths.length > 0) {
      const newFiles: SelectedFile[] = result.filePaths.map(p => ({
        name: extractFileName(p),
        path: p,
        size: 0
      }))
      selectedFiles.value = [...selectedFiles.value, ...newFiles]
      if (!skillName.value && newFiles.length > 0) {
        const baseName = newFiles[0].name.replace(/\.(zip|tar\.gz|tgz|json)$/i, '')
        skillName.value = baseName
      }
    }
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '打开文件对话框失败'
    step.value = 'error'
  }
}

function removeFile(idx: number) {
  selectedFiles.value.splice(idx, 1)
}

async function handleUpload() {
  if (!canUpload.value) return

  step.value = 'uploading'
  uploadProgress.value = 0
  errorMessage.value = ''

  progressTimer = setInterval(() => {
    if (uploadProgress.value < 90) {
      uploadProgress.value += Math.random() * 12
      if (uploadProgress.value > 90) uploadProgress.value = 90
    }
  }, 300)

  try {
    if (window.api?.skill?.upload) {
      for (const file of selectedFiles.value) {
        const result = await window.api.skill.upload({
          filePath: file.path,
          name: skillName.value.trim(),
          overwrite: overwrite.value
        })
        if (!result.success) {
          throw new Error(result.error || '上传失败')
        }
      }
    } else {
      await new Promise<void>((resolve, reject) => {
        setTimeout(() => {
          resolve()
        }, 2000)
      })
    }

    clearTimers()
    uploadProgress.value = 100
    step.value = 'success'

    successTimer = setTimeout(() => {
      emit('complete', skillName.value)
    }, 1200)
  } catch (err) {
    clearTimers()
    errorMessage.value = err instanceof Error ? err.message : '上传失败，请重试'
    step.value = 'error'
  }
}

function handleRetry() {
  clearTimers()
  step.value = 'select'
  uploadProgress.value = 0
  errorMessage.value = ''
}

function handleDrop(e: DragEvent) {
  e.preventDefault()
  if (!e.dataTransfer?.files) return

  const newFiles: SelectedFile[] = []
  for (let i = 0; i < e.dataTransfer.files.length; i++) {
    const f = e.dataTransfer.files[i]
    const filePath = (f as File & { path?: string }).path
    newFiles.push({
      name: f.name,
      path: filePath || '',
      size: f.size
    })
  }

  if (newFiles.length === 0) return

  const hasEmptyPaths = newFiles.some(f => !f.path)
  if (hasEmptyPaths) {
    errorMessage.value = '部分文件无法获取路径，请使用"选择文件"按钮浏览文件'
  }

  selectedFiles.value = [...selectedFiles.value, ...newFiles]
  if (!skillName.value && newFiles.length > 0) {
    skillName.value = newFiles[0].name.replace(/\.(zip|tar\.gz|tgz|json)$/i, '')
  }
}

function handleDragOver(e: DragEvent) {
  e.preventDefault()
}
</script>

<template>
  <Teleport to="body">
    <div class="modal-overlay" @click="handleOverlayClick">
      <div class="upload-dialog animate-scale-in" @click.stop>
        <div class="dialog-header">
          <div class="dialog-title-area">
            <Upload :size="20" class="dialog-icon" />
            <h2>上传本地技能</h2>
          </div>
          <button class="close-btn" @click="emit('close')">
            <X :size="18" />
          </button>
        </div>

        <div class="dialog-body">
          <div v-if="step === 'select'" class="select-step">
            <div
              class="drop-zone"
              :class="{ 'has-files': selectedFiles.length > 0 }"
              @drop="handleDrop"
              @dragover="handleDragOver"
            >
              <Upload :size="32" class="drop-icon" />
              <p class="drop-text">拖拽文件到此处</p>
              <p class="drop-hint">或点击下方按钮选择文件</p>
              <button class="browse-btn" @click="handleBrowse">
                <FolderOpen :size="16" />
                选择文件
              </button>
              <span class="drop-formats">支持 .zip .tar.gz .json 格式</span>
            </div>

            <div v-if="selectedFiles.length > 0" class="file-list">
              <div v-for="(file, idx) in selectedFiles" :key="file.path" class="file-item">
                <FileArchive :size="16" class="file-icon" />
                <div class="file-info">
                  <span class="file-name">{{ file.name }}</span>
                  <span class="file-size">{{ (file.size / 1024).toFixed(1) }} KB</span>
                </div>
                <button class="file-remove" @click="removeFile(idx)">
                  <X :size="14" />
                </button>
              </div>
              <div class="file-total">
                共 {{ selectedFiles.length }} 个文件，{{ totalSize }}
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">技能名称</label>
              <input
                v-model="skillName"
                type="text"
                placeholder="输入技能名称..."
                class="form-input"
              />
            </div>

            <div class="form-group">
              <label class="form-check">
                <input v-model="overwrite" type="checkbox" class="form-checkbox" />
                <span class="check-label">覆盖已存在的同名技能</span>
              </label>
            </div>
          </div>

          <div v-if="step === 'uploading'" class="uploading-step">
            <div class="uploading-animation">
              <Loader2 :size="40" class="upload-spinner" />
            </div>
            <h3>正在上传技能...</h3>
            <p class="upload-status">正在处理 {{ skillName }}</p>
            <div class="progress-bar-wrap">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
              </div>
              <span class="progress-text">{{ Math.round(uploadProgress) }}%</span>
            </div>
          </div>

          <div v-if="step === 'success'" class="success-step">
            <div class="success-animation">
              <CheckCircle2 :size="48" class="success-icon" />
            </div>
            <h3>上传成功！</h3>
            <p>{{ skillName }} 已成功上传并安装</p>
          </div>

          <div v-if="step === 'error'" class="error-step">
            <div class="error-animation">
              <AlertCircle :size="48" class="error-icon" />
            </div>
            <h3>上传失败</h3>
            <p class="error-message">{{ errorMessage }}</p>
            <button class="retry-btn" @click="handleRetry">
              重试
            </button>
          </div>
        </div>

        <div v-if="step === 'select'" class="dialog-footer">
          <button class="footer-btn cancel" @click="emit('close')">取消</button>
          <button class="footer-btn upload" :disabled="!canUpload" @click="handleUpload">
            <Upload :size="14" />
            上传并安装
          </button>
        </div>

        <div v-if="step === 'error'" class="dialog-footer">
          <button class="footer-btn cancel" @click="emit('close')">关闭</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2001;
  padding: 20px;
}

.upload-dialog {
  width: 480px;
  max-width: 100%;
  background: var(--surface);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--border-light);
}

.dialog-title-area {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dialog-icon {
  color: var(--lumi-primary);
}

.dialog-title-area h2 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.close-btn {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
  cursor: pointer;
  flex-shrink: 0;
}

.close-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.dialog-body {
  padding: 20px 24px;
  overflow-y: auto;
  max-height: 60vh;
}

.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 20px;
  border: 2px dashed var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-secondary);
  transition: all var(--transition-normal);
  cursor: pointer;
  margin-bottom: 16px;
}

.drop-zone:hover {
  border-color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.drop-zone.has-files {
  padding: 20px;
  border-style: solid;
  border-color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.drop-icon {
  color: var(--text-muted);
  transition: color var(--transition-fast);
}

.drop-zone:hover .drop-icon {
  color: var(--lumi-primary);
}

.drop-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
}

.drop-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.browse-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  color: var(--lumi-primary);
  background: var(--surface);
  border: 1px solid var(--lumi-primary);
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-top: 4px;
}

.browse-btn:hover {
  background: var(--lumi-primary);
  color: #fff;
}

.drop-formats {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
}

.file-icon {
  color: var(--lumi-primary);
  flex-shrink: 0;
}

.file-info {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-size {
  font-size: 11px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.file-remove {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  color: var(--text-muted);
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.file-remove:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.file-total {
  font-size: 11px;
  color: var(--text-muted);
  padding: 4px 0 0 4px;
}

.form-group {
  margin-bottom: 16px;
}

.form-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.form-input {
  width: 100%;
  padding: 9px 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  font-size: 13px;
  color: var(--text-primary);
  transition: all var(--transition-fast);
}

.form-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.form-input::placeholder {
  color: var(--text-muted);
}

.form-check {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.form-checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--lumi-primary);
  cursor: pointer;
}

.check-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.uploading-step,
.success-step,
.error-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px 0;
  text-align: center;
}

.uploading-animation {
  margin-bottom: 16px;
}

.upload-spinner {
  color: var(--lumi-primary);
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.uploading-step h3,
.success-step h3,
.error-step h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.upload-status,
.success-step p,
.error-step p {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.progress-bar-wrap {
  width: 100%;
  max-width: 320px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.progress-bar {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: var(--bg-secondary);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--lumi-primary), #14b8a6);
  transition: width 300ms ease-out;
}

.progress-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--lumi-primary);
  min-width: 36px;
  text-align: right;
}

.success-animation {
  margin-bottom: 16px;
}

.success-icon {
  color: #16a34a;
  animation: success-pop 0.4s ease-out;
}

@keyframes success-pop {
  0% { transform: scale(0.5); opacity: 0; }
  60% { transform: scale(1.1); }
  100% { transform: scale(1); opacity: 1; }
}

.error-animation {
  margin-bottom: 16px;
}

.error-icon {
  color: var(--lumi-accent);
}

.error-message {
  font-size: 13px;
  color: var(--lumi-accent);
  background: var(--lumi-accent-light);
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  max-width: 360px;
  word-break: break-word;
}

.retry-btn {
  padding: 8px 20px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 600;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.retry-btn:hover {
  background: rgba(13, 148, 136, 0.15);
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px;
  border-top: 1px solid var(--border-light);
}

.footer-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.footer-btn.cancel {
  color: var(--text-secondary);
  background: var(--surface-hover);
}

.footer-btn.cancel:hover {
  background: var(--bg-secondary);
}

.footer-btn.upload {
  background: var(--lumi-primary);
  color: #fff;
}

.footer-btn.upload:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(13, 148, 136, 0.3);
}

.footer-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 540px) {
  .upload-dialog {
    border-radius: var(--radius-lg);
  }

  .drop-zone {
    padding: 20px 16px;
  }

  .file-info {
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
  }
}
</style>
