<script setup lang="ts">
import { ref, computed } from 'vue'
import { Upload, X, FileUp, CheckCircle, AlertCircle, Loader2 } from 'lucide-vue-next'
import type { ModelType } from '../../types'
import { modelApi } from '../../services/modelApi'

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'imported', model: any): void
}>()

const modelTypes: { id: ModelType; label: string; desc: string; exts: string }[] = [
  { id: 'live2d', label: 'Live2D', desc: 'Cubism 模型 (.moc3/.zip)', exts: '.moc3,.zip,.json' },
  { id: 'blender', label: 'Blender/glTF', desc: '3D模型 (.glb/.gltf/.blend)', exts: '.glb,.gltf,.blend' },
  { id: 'vam', label: 'VAM', desc: 'Virt-A-Mate (.var/.vam)', exts: '.var,.vam' },
  { id: 'vrm', label: 'VRM', desc: 'VRM虚拟形象 (.vrm)', exts: '.vrm' }
]

const selectedType = ref<ModelType>('live2d')
const modelName = ref('')
const modelDescription = ref('')
const modelTags = ref('')
const isPublic = ref(false)
const selectedFile = ref<File | null>(null)
const isDragging = ref(false)
const isUploading = ref(false)
const uploadProgress = ref(0)
const uploadError = ref('')
const uploadSuccess = ref(false)

const currentExts = computed(() => {
  return modelTypes.find(t => t.id === selectedType.value)?.exts || ''
})

const canSubmit = computed(() => {
  return modelName.value.trim() && selectedFile.value && !isUploading.value
})

function onDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}

function onDragLeave() {
  isDragging.value = false
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    selectedFile.value = files[0]
  }
}

function onFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    selectedFile.value = input.files[0]
  }
}

function clearFile() {
  selectedFile.value = null
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function submitImport() {
  if (!selectedFile.value || !modelName.value.trim()) return

  isUploading.value = true
  uploadError.value = ''
  uploadProgress.value = 0

  try {
    const result = await modelApi.upload(selectedFile.value, {
      name: modelName.value.trim(),
      model_type: selectedType.value,
      description: modelDescription.value.trim() || undefined,
      tags: modelTags.value.trim() || undefined,
      is_public: isPublic.value
    })

    uploadSuccess.value = true
    uploadProgress.value = 100
    setTimeout(() => {
      emit('imported', result)
      emit('close')
    }, 1200)
  } catch (err: any) {
    uploadError.value = err.message || '导入失败'
  } finally {
    isUploading.value = false
  }
}
</script>

<template>
  <div class="import-overlay" @click.self="emit('close')">
    <div class="import-dialog animate-scale-in">
      <div class="dialog-header">
        <h3>导入模型</h3>
        <button class="close-btn" @click="emit('close')"><X :size="18" /></button>
      </div>

      <div class="dialog-body">
        <div class="form-section">
          <label class="form-label">模型类型</label>
          <div class="type-grid">
            <button
              v-for="mt in modelTypes"
              :key="mt.id"
              :class="['type-card', { active: selectedType === mt.id }]"
              @click="selectedType = mt.id"
            >
              <span class="type-name">{{ mt.label }}</span>
              <span class="type-desc">{{ mt.desc }}</span>
            </button>
          </div>
        </div>

        <div class="form-row">
          <div class="form-field flex-1">
            <label class="form-label">模型名称 *</label>
            <input v-model="modelName" type="text" class="form-input" placeholder="输入模型名称" />
          </div>
          <div class="form-field" style="width: 120px">
            <label class="form-label">公开</label>
            <button
              :class="['toggle-btn', { on: isPublic }]"
              @click="isPublic = !isPublic"
            >
              {{ isPublic ? '公开' : '私有' }}
            </button>
          </div>
        </div>

        <div class="form-field">
          <label class="form-label">描述</label>
          <textarea v-model="modelDescription" class="form-textarea" rows="2" placeholder="模型描述（可选）"></textarea>
        </div>

        <div class="form-field">
          <label class="form-label">标签</label>
          <input v-model="modelTags" type="text" class="form-input" placeholder="用逗号分隔标签" />
        </div>

        <div class="form-field">
          <label class="form-label">模型文件 *</label>
          <div
            :class="['drop-zone', { dragging: isDragging, has_file: selectedFile }]"
            @dragover="onDragOver"
            @dragleave="onDragLeave"
            @drop="onDrop"
            @click="($refs.fileInput as HTMLInputElement)?.click()"
          >
            <input
              ref="fileInput"
              type="file"
              :accept="currentExts"
              class="file-input"
              @change="onFileSelect"
            />
            <template v-if="!selectedFile">
              <FileUp :size="32" class="drop-icon" />
              <span class="drop-text">拖拽文件到此处或点击选择</span>
              <span class="drop-hint">支持格式: {{ currentExts }}</span>
            </template>
            <template v-else>
              <div class="file-info">
                <CheckCircle :size="20" class="file-check" />
                <div class="file-details">
                  <span class="file-name">{{ selectedFile.name }}</span>
                  <span class="file-size">{{ formatSize(selectedFile.size) }}</span>
                </div>
                <button class="file-clear" @click.stop="clearFile"><X :size="14" /></button>
              </div>
            </template>
          </div>
        </div>

        <div v-if="uploadError" class="upload-error">
          <AlertCircle :size="16" />
          <span>{{ uploadError }}</span>
        </div>

        <div v-if="uploadSuccess" class="upload-success">
          <CheckCircle :size="16" />
          <span>导入成功！</span>
        </div>
      </div>

      <div class="dialog-footer">
        <button class="btn btn-ghost" @click="emit('close')">取消</button>
        <button
          :class="['btn btn-primary', { loading: isUploading }]"
          :disabled="!canSubmit"
          @click="submitImport"
        >
          <Loader2 v-if="isUploading" :size="16" class="spin" />
          <Upload v-else :size="16" />
          <span>{{ isUploading ? '导入中...' : '开始导入' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.import-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.import-dialog {
  width: 560px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  overflow: hidden;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--border);
}

.dialog-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.close-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.type-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.type-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
}

.type-card:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.type-card.active {
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.type-name {
  font-size: 13px;
  font-weight: 600;
}

.type-desc {
  font-size: 10px;
  opacity: 0.7;
}

.form-row {
  display: flex;
  gap: 12px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.flex-1 {
  flex: 1;
}

.form-input,
.form-textarea {
  padding: 10px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-secondary);
  color: var(--text);
  font-size: 13px;
  transition: all var(--transition-fast);
}

.form-input:focus,
.form-textarea:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.form-textarea {
  resize: vertical;
  min-height: 60px;
}

.toggle-btn {
  padding: 10px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-secondary);
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  width: 100%;
}

.toggle-btn.on {
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 28px 20px;
  border-radius: var(--radius-lg);
  border: 2px dashed var(--border);
  background: var(--bg-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.drop-zone:hover,
.drop-zone.dragging {
  border-color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.drop-zone.has_file {
  border-style: solid;
  border-color: var(--lumi-success);
  background: rgba(34, 197, 94, 0.04);
}

.file-input {
  display: none;
}

.drop-icon {
  color: var(--text-muted);
  opacity: 0.5;
}

.drop-text {
  font-size: 13px;
  color: var(--text-secondary);
}

.drop-hint {
  font-size: 11px;
  color: var(--text-muted);
}

.file-info {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.file-check {
  color: var(--lumi-success);
  flex-shrink: 0;
}

.file-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-size {
  font-size: 11px;
  color: var(--text-muted);
}

.file-clear {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.file-clear:hover {
  background: rgba(244, 63, 94, 0.1);
  color: var(--lumi-accent);
}

.upload-error,
.upload-success {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
}

.upload-error {
  background: rgba(244, 63, 94, 0.08);
  color: var(--lumi-accent);
}

.upload-success {
  background: rgba(34, 197, 94, 0.08);
  color: var(--lumi-success);
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px;
  border-top: 1px solid var(--border);
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-ghost {
  color: var(--text-muted);
}

.btn-ghost:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.btn-primary {
  background: var(--lumi-primary);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(13, 148, 136, 0.3);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn.loading {
  pointer-events: none;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>