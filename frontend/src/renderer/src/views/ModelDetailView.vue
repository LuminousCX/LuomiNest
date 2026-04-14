<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  Save,
  RotateCcw,
  Download,
  Trash2,
  History,
  Settings2,
  Play,
  Pause,
  Eye,
  Box,
  Layers,
  MousePointer,
  FileUp,
  CheckCircle,
  AlertCircle,
  Loader2,
  ChevronDown,
  Tag,
  Calendar,
  HardDrive
} from 'lucide-vue-next'
import ModelConfigPanel from '../components/model/ModelConfigPanel.vue'
import type { ModelAsset, ModelVersion, ModelAnimation, ModelInteraction } from '../types'
import { modelApi } from '../services/modelApi'

const route = useRoute()
const router = useRouter()

const modelId = computed(() => route.params.id as string)

const model = ref<ModelAsset | null>(null)
const versions = ref<ModelVersion[]>([])
const isLoading = ref(true)
const isDeleting = ref(false)
const showDeleteConfirm = ref(false)
const activeSection = ref<'preview' | 'config' | 'animations' | 'interactions' | 'versions'>('preview')
const previewUrl = ref<string | null>(null)
const isPreviewLoading = ref(false)

onMounted(async () => {
  await loadModel()
})

watch(modelId, async () => {
  await loadModel()
})

async function loadModel() {
  isLoading.value = true
  try {
    model.value = await modelApi.get(modelId.value)
    await loadVersions()
    await loadPreview()
  } catch (err) {
    console.error('Failed to load model:', err)
  } finally {
    isLoading.value = false
  }
}

async function loadVersions() {
  try {
    versions.value = await modelApi.getVersions(modelId.value)
  } catch (err) {
    console.error('Failed to load versions:', err)
  }
}

async function loadPreview() {
  isPreviewLoading.value = true
  try {
    const result = await modelApi.preview(modelId.value)
    previewUrl.value = result.render_url
  } catch (err) {
    console.error('Failed to load preview:', err)
  } finally {
    isPreviewLoading.value = false
  }
}

async function deleteModel() {
  isDeleting.value = true
  try {
    await modelApi.delete(modelId.value)
    router.push('/avatar')
  } catch (err) {
    console.error('Failed to delete model:', err)
  } finally {
    isDeleting.value = false
  }
}

function goBack() {
  router.push('/avatar')
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const modelTypeLabel: Record<string, string> = {
  live2d: 'Live2D Cubism',
  blender: 'Blender glTF',
  vam: 'Virt-A-Mate',
  vrm: 'VRM 3D'
}

const statusConfig: Record<string, { text: string; color: string; icon: any }> = {
  uploading: { text: '上传中', color: '#eab308', icon: Loader2 },
  processing: { text: '处理中', color: '#3b82f6', icon: Loader2 },
  ready: { text: '就绪', color: '#22c55e', icon: CheckCircle },
  error: { text: '错误', color: '#f43f5e', icon: AlertCircle },
  archived: { text: '归档', color: '#6b7280', icon: History }
}

const sections = [
  { id: 'preview' as const, label: '预览', icon: Eye },
  { id: 'config' as const, label: '配置', icon: Settings2 },
  { id: 'animations' as const, label: '动画', icon: Layers },
  { id: 'interactions' as const, label: '交互', icon: MousePointer },
  { id: 'versions' as const, label: '版本', icon: History }
]
</script>

<template>
  <div class="model-detail-view">
    <div class="detail-header">
      <button class="back-btn" @click="goBack">
        <ArrowLeft :size="18" />
        <span>返回模型库</span>
      </button>

      <template v-if="model">
        <div class="header-model-info">
          <div class="model-badge" :class="`type-${model.model_type}`">
            {{ model.model_type.toUpperCase() }}
          </div>
          <div class="model-title-group">
            <h2>{{ model.name }}</h2>
            <div class="model-meta-row">
              <span class="meta-item">
                <component
                  :is="statusConfig[model.status]?.icon || CheckCircle"
                  :size="12"
                  :style="{ color: statusConfig[model.status]?.color }"
                  :class="{ spin: model.status === 'uploading' || model.status === 'processing' }"
                />
                {{ statusConfig[model.status]?.text || model.status }}
              </span>
              <span class="meta-item"><Calendar :size="12" /> {{ formatDate(model.created_at) }}</span>
              <span class="meta-item"><HardDrive :size="12" /> {{ formatSize(model.file_size) }}</span>
              <span class="meta-item"><Tag :size="12" /> v{{ model.version }}</span>
            </div>
          </div>
        </div>

        <div class="header-actions">
          <button class="action-btn danger" @click="showDeleteConfirm = true">
            <Trash2 :size="14" /> 删除
          </button>
        </div>
      </template>
    </div>

    <div v-if="isLoading" class="loading-state">
      <Loader2 :size="28" class="spin" />
      <span>加载模型信息...</span>
    </div>

    <template v-else-if="model">
      <div class="detail-body">
        <div class="section-tabs">
          <button
            v-for="sec in sections"
            :key="sec.id"
            :class="['section-tab', { active: activeSection === sec.id }]"
            @click="activeSection = sec.id"
          >
            <component :is="sec.icon" :size="14" />
            <span>{{ sec.label }}</span>
          </button>
        </div>

        <div class="section-content">
          <div v-if="activeSection === 'preview'" class="preview-section">
            <div class="preview-canvas">
              <div v-if="isPreviewLoading" class="preview-loading">
                <Loader2 :size="24" class="spin" />
                <span>加载预览...</span>
              </div>
              <div v-else-if="previewUrl" class="preview-render">
                <img :src="previewUrl" alt="Model Preview" class="preview-image" />
              </div>
              <div v-else class="preview-placeholder">
                <Box :size="48" />
                <span>{{ modelTypeLabel[model.model_type] || model.model_type }}</span>
                <span class="placeholder-hint">预览渲染不可用</span>
              </div>
            </div>

            <div class="preview-info">
              <h4>模型信息</h4>
              <div class="info-grid">
                <div class="info-item">
                  <span class="info-label">文件名</span>
                  <span class="info-value">{{ model.original_filename }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">文件大小</span>
                  <span class="info-value">{{ formatSize(model.file_size) }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">模型类型</span>
                  <span class="info-value">{{ modelTypeLabel[model.model_type] }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">版本</span>
                  <span class="info-value">v{{ model.version }}</span>
                </div>
                <div v-if="model.file_hash" class="info-item">
                  <span class="info-label">文件哈希</span>
                  <span class="info-value hash">{{ model.file_hash.substring(0, 16) }}...</span>
                </div>
                <div class="info-item">
                  <span class="info-label">公开</span>
                  <span class="info-value">{{ model.is_public ? '是' : '否' }}</span>
                </div>
              </div>

              <div v-if="model.description" class="info-description">
                <h4>描述</h4>
                <p>{{ model.description }}</p>
              </div>

              <div v-if="model.tags && model.tags.length" class="info-tags">
                <h4>标签</h4>
                <div class="tag-list">
                  <span v-for="tag in model.tags" :key="tag" class="tag-item">{{ tag }}</span>
                </div>
              </div>

              <div v-if="model.metadata_json" class="info-metadata">
                <h4>元数据</h4>
                <pre class="metadata-json">{{ JSON.stringify(model.metadata_json, null, 2) }}</pre>
              </div>
            </div>
          </div>

          <div v-if="activeSection === 'config'" class="config-section">
            <ModelConfigPanel :model="model" />
          </div>

          <div v-if="activeSection === 'animations'" class="animations-section">
            <div class="section-placeholder">
              <Layers :size="36" />
              <h3>动画管理</h3>
              <p>在配置面板中管理模型动画参数</p>
              <button class="goto-btn" @click="activeSection = 'config'">
                <Settings2 :size="14" /> 前往配置
              </button>
            </div>
          </div>

          <div v-if="activeSection === 'interactions'" class="interactions-section">
            <div class="section-placeholder">
              <MousePointer :size="36" />
              <h3>交互管理</h3>
              <p>在配置面板中管理模型交互行为</p>
              <button class="goto-btn" @click="activeSection = 'config'">
                <Settings2 :size="14" /> 前往配置
              </button>
            </div>
          </div>

          <div v-if="activeSection === 'versions'" class="versions-section">
            <div v-if="versions.length === 0" class="empty-versions">
              <History :size="28" />
              <span>暂无版本记录</span>
            </div>
            <div v-else class="version-list">
              <div v-for="ver in versions" :key="ver.id" class="version-item">
                <div class="version-badge">v{{ ver.version }}</div>
                <div class="version-info">
                  <span class="version-hash">{{ ver.file_hash.substring(0, 12) }}</span>
                  <span class="version-size">{{ formatSize(ver.file_size) }}</span>
                  <span class="version-date">{{ formatDate(ver.created_at) }}</span>
                </div>
                <div v-if="ver.change_log" class="version-changelog">{{ ver.change_log }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div v-if="showDeleteConfirm" class="confirm-overlay" @click.self="showDeleteConfirm = false">
      <div class="confirm-dialog">
        <h3>确认删除</h3>
        <p>确定要删除模型「{{ model?.name }}」吗？此操作不可撤销。</p>
        <div class="confirm-actions">
          <button class="btn btn-ghost" @click="showDeleteConfirm = false">取消</button>
          <button :class="['btn btn-danger', { loading: isDeleting }]" @click="deleteModel">
            <Loader2 v-if="isDeleting" :size="14" class="spin" />
            <Trash2 v-else :size="14" />
            <span>{{ isDeleting ? '删除中...' : '确认删除' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.model-detail-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-muted);
  transition: all 200ms ease;
  cursor: pointer;
  flex-shrink: 0;
}

.back-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.header-model-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.model-badge {
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  flex-shrink: 0;
}

.model-badge.type-live2d {
  background: rgba(236, 72, 153, 0.12);
  color: #ec4899;
}

.model-badge.type-blender {
  background: rgba(245, 158, 11, 0.12);
  color: #f59e0b;
}

.model-badge.type-vam {
  background: rgba(99, 102, 241, 0.12);
  color: #6366f1;
}

.model-badge.type-vrm {
  background: rgba(34, 197, 94, 0.12);
  color: #22c55e;
}

.model-title-group {
  min-width: 0;
}

.model-title-group h2 {
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-meta-row {
  display: flex;
  gap: 12px;
  margin-top: 2px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.header-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 12px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
  transition: all 200ms ease;
}

.action-btn.danger {
  color: #f43f5e;
}

.action-btn.danger:hover {
  background: rgba(244, 63, 94, 0.1);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex: 1;
  color: var(--text-muted);
  font-size: 13px;
}

.detail-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.section-tabs {
  display: flex;
  gap: 4px;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.section-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms ease;
}

.section-tab:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.section-tab.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  font-weight: 500;
}

.section-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.preview-section {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}

.preview-canvas {
  width: 400px;
  height: 500px;
  border-radius: 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
  position: relative;
}

.preview-loading,
.preview-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 13px;
}

.preview-placeholder svg {
  opacity: 0.3;
}

.placeholder-hint {
  font-size: 11px;
  opacity: 0.5;
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.preview-info {
  flex: 1;
  min-width: 0;
}

.preview-info h4 {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 10px;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-label {
  font-size: 11px;
  color: var(--text-muted);
}

.info-value {
  font-size: 13px;
  color: var(--text);
  word-break: break-all;
}

.info-value.hash {
  font-family: monospace;
  font-size: 11px;
  opacity: 0.7;
}

.info-description {
  margin-bottom: 16px;
}

.info-description p {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.info-tags {
  margin-bottom: 16px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-item {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 12px;
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.info-metadata {
  margin-bottom: 16px;
}

.metadata-json {
  font-size: 11px;
  padding: 12px;
  border-radius: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  overflow-x: auto;
  max-height: 200px;
  overflow-y: auto;
  font-family: monospace;
  line-height: 1.5;
}

.config-section {
  max-width: 800px;
}

.section-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 60px 20px;
  color: var(--text-muted);
  text-align: center;
}

.section-placeholder svg {
  opacity: 0.3;
}

.section-placeholder h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}

.section-placeholder p {
  font-size: 13px;
}

.goto-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  background: var(--lumi-primary);
  color: #fff;
  cursor: pointer;
  transition: all 200ms ease;
  margin-top: 8px;
}

.goto-btn:hover {
  background: var(--lumi-primary-hover);
  transform: translateY(-1px);
}

.versions-section {
  max-width: 600px;
}

.empty-versions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px;
  color: var(--text-muted);
  font-size: 13px;
}

.version-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.version-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid var(--border);
  transition: all 200ms ease;
}

.version-item:hover {
  background: var(--surface-hover);
}

.version-badge {
  padding: 4px 10px;
  border-radius: 8px;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.version-info {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--text-muted);
}

.version-hash {
  font-family: monospace;
}

.version-changelog {
  font-size: 12px;
  color: var(--text-secondary);
  margin-left: auto;
}

.confirm-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  z-index: 1000;
}

.confirm-dialog {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 24px;
  max-width: 400px;
  width: 90%;
}

.confirm-dialog h3 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
}

.confirm-dialog p {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 20px;
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: all 200ms ease;
}

.btn-ghost {
  color: var(--text-muted);
}

.btn-ghost:hover {
  background: var(--surface-hover);
}

.btn-danger {
  background: #f43f5e;
  color: #fff;
}

.btn-danger:hover {
  background: #e11d48;
}

.btn-danger.loading {
  opacity: 0.7;
  pointer-events: none;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
