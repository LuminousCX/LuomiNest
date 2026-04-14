<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Palette,
  Sparkles,
  Heart,
  Eye,
  Smile,
  Frown,
  Meh,
  Zap,
  Volume2,
  RotateCcw,
  Maximize2,
  Download,
  Settings2,
  Trash2,
  Search,
  Filter,
  Grid3X3,
  List,
  MoreVertical,
  FileUp,
  CheckCircle,
  AlertCircle,
  Loader2,
  ChevronRight
} from 'lucide-vue-next'
import ModelImportDialog from '../components/model/ModelImportDialog.vue'
import ModelConfigPanel from '../components/model/ModelConfigPanel.vue'
import type { ModelAsset, ModelType } from '../types'
import { modelApi } from '../services/modelApi'

const avatarModes = [
  { id: 'live2d', label: 'Live2D', desc: 'Cubism 5 二次元', active: true },
  { id: 'vrm', label: 'VRM', desc: '3D 全身模型', active: false },
  { id: 'blender', label: 'Blender', desc: 'glTF 3D模型', active: false },
  { id: 'vam', label: 'VAM', desc: 'Virt-A-Mate', active: false }
]

const currentMode = ref<ModelType>('live2d')

const emotions = [
  { id: 'happy', icon: Smile, label: '开心', color: '#f59e0b' },
  { id: 'sad', icon: Frown, label: '难过', color: '#6366f1' },
  { id: 'neutral', icon: Meh, label: '平静', color: '#8b5cf6' },
  { id: 'love', icon: Heart, label: '喜爱', color: '#ec4899' },
  { id: 'surprise', icon: Zap, label: '惊讶', color: '#22c55e' }
]

const currentEmotion = ref(emotions[0])

const expressionValue = computed(() => {
  const map: Record<string, number> = {
    happy: 0.8, sad: -0.4, neutral: 0, love: 0.6, surprise: 0.7
  }
  return map[currentEmotion.value.id] ?? 0
})

const models = ref<ModelAsset[]>([])
const totalModels = ref(0)
const currentPage = ref(1)
const selectedModelId = ref<string | null>(null)
const searchQuery = ref('')
const showImportDialog = ref(false)
const showConfigPanel = ref(false)
const isLoadingModels = ref(false)
const viewMode = ref<'grid' | 'list'>('grid')

const selectedModel = computed(() => {
  return models.value.find(m => m.id === selectedModelId.value) || null
})

const filteredModels = computed(() => {
  if (!searchQuery.value) return models.value
  const q = searchQuery.value.toLowerCase()
  return models.value.filter(m =>
    m.name.toLowerCase().includes(q) ||
    (m.tags && m.tags.some(t => t.toLowerCase().includes(q)))
  )
})

onMounted(async () => {
  await loadModels()
})

async function loadModels() {
  isLoadingModels.value = true
  try {
    const result = await modelApi.list({
      model_type: currentMode.value,
      page: currentPage.value,
      page_size: 50
    })
    models.value = result.items
    totalModels.value = result.total
    if (result.items.length > 0 && !selectedModelId.value) {
      selectedModelId.value = result.items[0].id
    }
  } catch (err) {
    console.error('Failed to load models:', err)
  } finally {
    isLoadingModels.value = false
  }
}

function selectMode(modeId: string) {
  currentMode.value = modeId as ModelType
  currentPage.value = 1
  selectedModelId.value = null
  loadModels()
}

function selectEmotion(emo: typeof emotions[0]) {
  currentEmotion.value = emo
}

function selectModel(modelId: string) {
  selectedModelId.value = modelId
}

async function onModelImported(model: ModelAsset) {
  showImportDialog.value = false
  await loadModels()
  selectedModelId.value = model.id
}

async function deleteModel(modelId: string) {
  try {
    await modelApi.delete(modelId)
    if (selectedModelId.value === modelId) {
      selectedModelId.value = null
    }
    await loadModels()
  } catch (err) {
    console.error('Failed to delete model:', err)
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const statusLabel: Record<string, { text: string; color: string }> = {
  uploading: { text: '上传中', color: '#eab308' },
  processing: { text: '处理中', color: '#3b82f6' },
  ready: { text: '就绪', color: '#22c55e' },
  error: { text: '错误', color: '#f43f5e' },
  archived: { text: '归档', color: '#6b7280' }
}
</script>

<template>
  <div class="avatar-view">
    <div class="avatar-header">
      <div class="header-left">
        <Palette :size="20" />
        <h2>皮套工坊</h2>
        <span class="header-badge">Live2D / VRM / Blender / VAM</span>
      </div>
      <div class="header-actions">
        <button class="h-btn" title="重置姿态"><RotateCcw :size="16" /></button>
        <button class="h-btn" title="全屏模式"><Maximize2 :size="16" /></button>
        <button class="h-btn primary" title="导入模型" @click="showImportDialog = true">
          <Download :size="16" /> 导入
        </button>
        <button
          :class="['h-btn', { active: showConfigPanel }]"
          title="配置面板"
          @click="showConfigPanel = !showConfigPanel"
        >
          <Settings2 :size="16" />
        </button>
      </div>
    </div>

    <div class="avatar-body">
      <div class="avatar-stage animate-stage-appear">
        <div class="stage-canvas">
          <div class="avatar-placeholder" :class="[`emotion-${currentEmotion.id}`]">
            <div class="avatar-ring"></div>
            <div class="avatar-core">
              <Sparkles :size="48" class="avatar-sparkle" />
              <span class="avatar-label">{{ currentMode.toUpperCase() }}</span>
              <span v-if="selectedModel" class="avatar-model-name">{{ selectedModel.name }}</span>
            </div>
            <div class="avatar-particles">
              <span v-for="i in 6" :key="i" class="particle" :style="{ '--delay': `${i * 0.15}s` }"></span>
            </div>
          </div>
          <div class="stage-overlay">
            <div class="overlay-tag mode-tag">
              <Eye :size="12" /> {{ avatarModes.find(m => m.id === currentMode)?.label }}
            </div>
            <div class="overlay-tag emotion-tag" :style="{ borderColor: currentEmotion.color }">
              <component :is="currentEmotion.icon" :size="12" />
              {{ currentEmotion.label }}
            </div>
            <div v-if="selectedModel" class="overlay-tag status-tag">
              <CheckCircle :size="12" :style="{ color: statusLabel[selectedModel.status]?.color }" />
              {{ statusLabel[selectedModel.status]?.text || selectedModel.status }}
            </div>
          </div>
        </div>

        <div class="stage-controls">
          <div class="mode-switcher">
            <button
              v-for="mode in avatarModes"
              :key="mode.id"
              :class="['mode-btn', { active: currentMode === mode.id }]"
              @click="selectMode(mode.id)"
            >
              <span class="mode-name">{{ mode.label }}</span>
              <span class="mode-desc">{{ mode.desc }}</span>
            </button>
          </div>

          <div class="emotion-panel">
            <div class="panel-title">
              <Heart :size="14" />
              <span>情感驱动</span>
              <span class="expression-value">PAD: {{ expressionValue > 0 ? '+' : '' }}{{ expressionValue.toFixed(1) }}</span>
            </div>
            <div class="emotion-grid">
              <button
                v-for="emo in emotions"
                :key="emo.id"
                :class="['emo-btn', { active: currentEmotion.id === emo.id }]"
                :style="{ '--emo-color': emo.color }"
                @click="selectEmotion(emo)"
              >
                <component :is="emo.icon" :size="20" />
                <span>{{ emo.label }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="skin-sidebar animate-slide-right">
        <div class="sidebar-header">
          <span class="sidebar-title">模型库</span>
          <div class="sidebar-actions">
            <button
              :class="['view-btn', { active: viewMode === 'grid' }]"
              @click="viewMode = 'grid'"
            >
              <Grid3X3 :size="14" />
            </button>
            <button
              :class="['view-btn', { active: viewMode === 'list' }]"
              @click="viewMode = 'list'"
            >
              <List :size="14" />
            </button>
          </div>
        </div>

        <div class="search-box">
          <Search :size="14" class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索模型..." class="search-input" />
        </div>

        <div class="skin-list" v-if="!isLoadingModels">
          <div v-if="filteredModels.length === 0" class="empty-list">
            <FileUp :size="28" />
            <span>暂无模型，点击导入</span>
          </div>

          <template v-if="viewMode === 'grid'">
            <div
              v-for="model in filteredModels"
              :key="model.id"
              :class="['skin-card', { selected: selectedModelId === model.id }]"
              @click="selectModel(model.id)"
            >
              <div class="skin-thumb">
                <Palette :size="24" />
                <span class="thumb-type">{{ model.model_type.toUpperCase() }}</span>
              </div>
              <div class="skin-info">
                <span class="skin-name">{{ model.name }}</span>
                <span class="skin-type">v{{ model.version }} · {{ formatSize(model.file_size) }}</span>
              </div>
              <div class="skin-tags">
                <span
                  v-for="tag in (model.tags || []).slice(0, 2)"
                  :key="tag"
                  class="skin-tag"
                >{{ tag }}</span>
                <span
                  class="skin-tag status"
                  :style="{ color: statusLabel[model.status]?.color }"
                >{{ statusLabel[model.status]?.text }}</span>
              </div>
            </div>
          </template>

          <template v-else>
            <div
              v-for="model in filteredModels"
              :key="model.id"
              :class="['skin-row', { selected: selectedModelId === model.id }]"
              @click="selectModel(model.id)"
            >
              <div class="row-type">{{ model.model_type.toUpperCase() }}</div>
              <div class="row-info">
                <span class="row-name">{{ model.name }}</span>
                <span class="row-meta">v{{ model.version }} · {{ formatSize(model.file_size) }}</span>
              </div>
              <ChevronRight :size="14" class="row-arrow" />
            </div>
          </template>
        </div>

        <div v-else class="loading-list">
          <Loader2 :size="20" class="spin" />
          <span>加载中...</span>
        </div>

        <div class="sidebar-footer">
          <span class="footer-count">共 {{ totalModels }} 个模型</span>
        </div>
      </div>

      <ModelConfigPanel
        v-if="showConfigPanel && selectedModel"
        :model="selectedModel"
        class="config-sidebar"
      />
    </div>

    <ModelImportDialog
      v-if="showImportDialog"
      @close="showImportDialog = false"
      @imported="onModelImported"
    />
  </div>
</template>

<style scoped>
.avatar-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
}

.avatar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-muted);
}

.header-left h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
}

.header-badge {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 20px;
  background: rgba(13, 148, 136, 0.1);
  color: var(--lumi-primary);
  font-weight: 500;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.h-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-muted);
  transition: all 300ms ease-in-out;
  cursor: pointer;
  white-space: nowrap;
}

.h-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.h-btn.primary {
  background: var(--lumi-primary);
  color: #fff;
}

.h-btn.primary:hover {
  background: var(--lumi-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(13, 148, 136, 0.3);
}

.h-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.avatar-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.avatar-stage {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.stage-canvas {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 320px;
  background:
    radial-gradient(circle at 50% 50%, rgba(13, 148, 136, 0.04) 0%, transparent 70%),
    var(--surface);
  overflow: hidden;
}

.avatar-placeholder {
  position: relative;
  width: 260px;
  height: 340px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 24px;
  background: linear-gradient(145deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
  border: 1px solid var(--border);
  transition: all 500ms ease-in-out;
}

.avatar-ring {
  position: absolute;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  border: 1.5px dashed rgba(13, 148, 136, 0.25);
  animation: ring-spin 12s linear infinite;
}

@keyframes ring-spin {
  to { transform: rotate(360deg); }
}

.avatar-core {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  z-index: 1;
}

.avatar-sparkle {
  color: var(--lumi-primary);
  opacity: 0.6;
  animation: sparkle-pulse 2s ease-in-out infinite;
}

@keyframes sparkle-pulse {
  0%, 100% { opacity: 0.4; transform: scale(1); }
  50% { opacity: 0.9; transform: scale(1.1); }
}

.avatar-label {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 3px;
  color: var(--text-muted);
}

.avatar-model-name {
  font-size: 11px;
  color: var(--lumi-primary);
  max-width: 200px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.avatar-particles {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.particle {
  position: absolute;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--lumi-primary);
  opacity: 0;
  animation: particle-float 3s ease-in-out infinite;
  animation-delay: var(--delay);
}

@keyframes particle-float {
  0% { opacity: 0; transform: translateY(0) scale(0); }
  30% { opacity: 0.6; }
  100% { opacity: 0; transform: translateY(-120px) scale(1); }
}

.stage-overlay {
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.overlay-tag {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 500;
  backdrop-filter: blur(8px);
  background: rgba(0,0,0,0.35);
  border: 1px solid rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.85);
}

.emotion-tag {
  border-color: var(--emo-color, var(--lumi-primary));
  color: var(--emo-color, var(--lumi-primary));
}

.status-tag {
  border-color: transparent;
}

.stage-controls {
  display: flex;
  gap: 16px;
  padding: 16px 20px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
  overflow-x: auto;
}

.mode-switcher {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.mode-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 10px 18px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  white-space: nowrap;
}

.mode-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.mode-btn.active {
  background: rgba(13, 148, 136, 0.1);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.mode-name {
  font-size: 13px;
  font-weight: 600;
}

.mode-desc {
  font-size: 10px;
  opacity: 0.6;
}

.emotion-panel {
  flex-shrink: 0;
  min-width: 200px;
  max-width: 280px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.expression-value {
  margin-left: auto;
  font-family: monospace;
  font-size: 11px;
  color: var(--lumi-primary);
  opacity: 0.7;
}

.emotion-grid {
  display: flex;
  gap: 6px;
}

.emo-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  font-size: 11px;
}

.emo-btn:hover {
  background: color-mix(in srgb, var(--emo-color, #888) 8%, transparent);
  color: var(--text);
  transform: translateY(-2px);
}

.emo-btn.active {
  background: color-mix(in srgb, var(--emo-color, #888) 14%, transparent);
  border-color: var(--emo-color, var(--lumi-primary));
  color: var(--emo-color, var(--lumi-primary));
  box-shadow: 0 2px 12px color-mix(in srgb, var(--emo-color, #888) 18%, transparent);
}

.skin-sidebar {
  width: 280px;
  border-left: 1px solid var(--border);
  padding: 16px;
  overflow-y: auto;
  flex-shrink: 0;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sidebar-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.sidebar-actions {
  display: flex;
  gap: 4px;
}

.view-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.view-btn:hover {
  background: var(--surface-hover);
}

.view-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  transition: all var(--transition-fast);
}

.search-box:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  background: transparent;
  font-size: 13px;
  color: var(--text-secondary);
}

.search-input::placeholder {
  color: var(--text-muted);
}

.skin-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  overflow-y: auto;
}

.empty-list,
.loading-list {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px 16px;
  color: var(--text-muted);
  font-size: 13px;
}

.skin-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all 300ms ease-in-out;
}

.skin-card:hover {
  background: var(--surface-hover);
  border-color: rgba(13, 148, 136, 0.3);
}

.skin-card.selected {
  background: rgba(13, 148, 136, 0.08);
  border-color: var(--lumi-primary);
}

.skin-thumb {
  width: 100%;
  height: 80px;
  border-radius: 8px;
  background: var(--surface-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  position: relative;
}

.thumb-type {
  position: absolute;
  top: 6px;
  right: 6px;
  font-size: 9px;
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(0,0,0,0.3);
  color: rgba(255,255,255,0.8);
  font-weight: 500;
}

.skin-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.skin-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.skin-type {
  font-size: 11px;
  color: var(--text-muted);
}

.skin-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.skin-tag {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 8px;
  background: var(--surface-hover);
  color: var(--text-muted);
}

.skin-tag.status {
  background: transparent;
  font-weight: 500;
}

.skin-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.skin-row:hover {
  background: var(--surface-hover);
}

.skin-row.selected {
  background: var(--lumi-primary-light);
}

.row-type {
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 6px;
  background: var(--surface-hover);
  color: var(--text-muted);
  font-weight: 600;
  flex-shrink: 0;
}

.row-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.row-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row-meta {
  font-size: 11px;
  color: var(--text-muted);
}

.row-arrow {
  color: var(--text-muted);
  flex-shrink: 0;
}

.sidebar-footer {
  padding-top: 8px;
  border-top: 1px solid var(--border-light);
}

.footer-count {
  font-size: 11px;
  color: var(--text-muted);
}

.config-sidebar {
  width: 320px;
  flex-shrink: 0;
}

@keyframes stage-appear {
  0% { opacity: 0; transform: scale(0.96); }
  100% { opacity: 1; transform: scale(1); }
}

.animate-stage-appear {
  animation: stage-appear 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes slide-right {
  0% { opacity: 0; transform: translateX(30px); }
  100% { opacity: 1; transform: translateX(0); }
}

.animate-slide-right {
  animation: slide-right 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
