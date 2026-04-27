<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import {
  Palette, Sparkles, Heart, Eye, Smile, Frown, Meh, Zap,
  Volume2, RotateCcw, Maximize2, Download, Settings2,
  Loader2, AlertCircle, FolderOpen, Check, Monitor, MonitorOff,
  ChevronLeft, ChevronRight
} from 'lucide-vue-next'
import { useLuomiNestLive2D } from '@/composables/useLuomiNestLive2D'
import { useAvatarControlStore } from '@/stores/avatar-control'
import { LUOMINEST_BUILTIN_MODELS, type LuomiNestModelInfo } from '@/config/luominest-models'
import type { PetModelInfo } from '../vite-env.d'

const canvasRef = ref<HTMLCanvasElement | null>(null)
const avatarControl = useAvatarControlStore()

const {
  isReady: isModelReady,
  isLoading,
  error: loadError,
  loadModel,
  driveEmotion,
  resetPose,
  destroy: teardown
} = useLuomiNestLive2D(canvasRef)

const importError = ref<string | null>(null)
const importedModels = ref<LuomiNestModelInfo[]>([])
const showImportSuccess = ref(false)
const isDesktopMode = ref(false)
const isDesktopPetRunning = ref(false)
const skinSidebarVisible = ref(true)

const avatarModes = [
  { id: 'live2d', label: 'Live2D', desc: 'Cubism 4/5', active: true },
  { id: 'vrm', label: 'VRM', desc: '3D Model', active: false },
  { id: 'pixel', label: 'PixelPet', desc: 'Q-version Pet', active: false }
]

const currentMode = ref('live2d')

const emotions = [
  { id: 'happy', icon: Smile, label: 'Happy', color: '#f59e0b' },
  { id: 'sad', icon: Frown, label: 'Sad', color: '#6366f1' },
  { id: 'neutral', icon: Meh, label: 'Neutral', color: '#8b5cf6' },
  { id: 'love', icon: Heart, label: 'Love', color: '#ec4899' },
  { id: 'surprise', icon: Zap, label: 'Surprise', color: '#22c55e' }
]

const currentEmotionLocal = ref(emotions[2])

const expressionValue = computed(() => {
  const map: Record<string, number> = {
    happy: 0.8, sad: -0.4, neutral: 0, love: 0.6, surprise: 0.7
  }
  return map[currentEmotionLocal.value.id] ?? 0
})

const idleAnimations = computed(() => [
  { name: 'Breath', status: isModelReady.value ? 'running' : 'paused', progress: isModelReady.value ? 65 : 0 },
  { name: 'Blink', status: isModelReady.value ? 'running' : 'paused', progress: isModelReady.value ? 40 : 0 },
  { name: 'Idle Motion', status: isModelReady.value ? 'running' : 'paused', progress: isModelReady.value ? 80 : 0 },
  { name: 'Head Track', status: isModelReady.value ? 'running' : 'paused', progress: isModelReady.value ? 50 : 0 }
])

const skinList = computed(() => {
  const builtin = LUOMINEST_BUILTIN_MODELS.map(m => ({
    name: `${m.name}`,
    type: m.type === 'live2d' ? 'Live2D' : m.type === 'vrm' ? 'VRM' : 'PixelPet',
    tags: m.tags,
    modelInfo: m as LuomiNestModelInfo | null
  }))
  const imported = importedModels.value.map(m => ({
    name: m.name,
    type: 'Live2D',
    tags: ['Imported', ...m.tags],
    modelInfo: m as LuomiNestModelInfo | null
  }))
  return [...builtin, ...imported]
})

const selectedSkin = ref(0)

const currentModelInfo = computed(() => {
  const skin = skinList.value[selectedSkin.value]
  return skin?.modelInfo ?? null
})

function selectMode(modeId: string) {
  currentMode.value = modeId
}

function selectEmotion(emo: typeof emotions[0]) {
  currentEmotionLocal.value = emo
  driveEmotion(emo.id)
}

async function handleResetPose() {
  await resetPose()
}

async function handleSkinSelect(idx: number) {
  selectedSkin.value = idx
  const skin = skinList.value[idx]
  if (isDesktopMode.value && isDesktopPetRunning.value) {
    if (skin.modelInfo) {
      await window.api.desktopPet.loadModel(skin.modelInfo)
    }
  } else {
    if (skin.modelInfo) {
      await loadModel(skin.modelInfo.url, skin.modelInfo.scale)
    }
  }
}

async function handleImportClick() {
  importError.value = null
  try {
    const result = await window.api.avatar.importModel()
    if (!result.success) {
      if (result.error !== 'Cancelled') {
        importError.value = result.error ?? 'Import failed'
      }
      return
    }

    if (result.modelInfo) {
      const modelInfo: LuomiNestModelInfo = {
        id: result.modelInfo.id,
        name: result.modelInfo.name,
        url: result.modelInfo.url,
        scale: result.modelInfo.scale,
        type: result.modelInfo.type as LuomiNestModelInfo['type'],
        tags: result.modelInfo.tags
      }

      const existingIdx = importedModels.value.findIndex(m => m.name === modelInfo.name)
      if (existingIdx >= 0) {
        importedModels.value[existingIdx] = modelInfo
      } else {
        importedModels.value.push(modelInfo)
      }

      showImportSuccess.value = true
      setTimeout(() => { showImportSuccess.value = false }, 2000)

      if (isDesktopMode.value) {
        selectedSkin.value = skinList.value.findIndex(s => s.modelInfo?.name === modelInfo.name)
        if (selectedSkin.value < 0) selectedSkin.value = skinList.value.length - 1
        if (isDesktopPetRunning.value) {
          await window.api.desktopPet.loadModel(modelInfo)
        }
      } else {
        selectedSkin.value = skinList.value.findIndex(s => s.modelInfo?.name === modelInfo.name)
        if (selectedSkin.value < 0) selectedSkin.value = skinList.value.length - 1
        await loadModel(modelInfo.url, modelInfo.scale)
      }
    }
  } catch (err) {
    importError.value = err instanceof Error ? err.message : 'Failed to import model'
  }
}

async function toggleDesktopMode() {
  if (isDesktopMode.value) {
    await switchToInlineMode()
  } else {
    await switchToDesktopMode()
  }
}

async function switchToDesktopMode() {
  isDesktopMode.value = true
  const modelInfo = currentModelInfo.value
  await window.api.desktopPet.open(modelInfo ?? undefined)
  isDesktopPetRunning.value = true
  avatarControl.checkDesktopPetStatus()
}

async function switchToInlineMode() {
  isDesktopMode.value = false
  await window.api.desktopPet.close()
  isDesktopPetRunning.value = false
  avatarControl.checkDesktopPetStatus()
  await nextTick()
  if (currentModelInfo.value) {
    await loadModel(currentModelInfo.value.url, currentModelInfo.value.scale)
  }
}

function toggleSkinSidebar() {
  skinSidebarVisible.value = !skinSidebarVisible.value
}

const loadPersistedModels = async () => {
  try {
    const models = await window.api.avatar.listImportedModels()
    importedModels.value = models.map((m: PetModelInfo) => ({
      id: m.id,
      name: m.name,
      url: m.url,
      scale: m.scale,
      type: m.type as LuomiNestModelInfo['type'],
      tags: m.tags
    }))
  } catch {
  }
}

const checkDesktopPetStatus = async () => {
  try {
    isDesktopPetRunning.value = await window.api.desktopPet.isRunning()
  } catch {
    isDesktopPetRunning.value = false
  }
}

onMounted(async () => {
  await loadPersistedModels()
  await checkDesktopPetStatus()
  await avatarControl.checkDesktopPetStatus()
  await nextTick()
  if (!isDesktopPetRunning.value) {
    const defaultModel = LUOMINEST_BUILTIN_MODELS[0]
    await loadModel(defaultModel.url, defaultModel.scale)
  }
})

onBeforeUnmount(() => {
  teardown()
})
</script>

<template>
  <div class="avatar-view">
    <div class="avatar-header">
      <div class="header-left">
        <Palette :size="20" />
        <h2>Avatar Studio</h2>
        <span class="header-badge">LuomiNest</span>
      </div>
      <div class="header-actions">
        <div class="desktop-mode-toggle" :class="{ active: isDesktopMode }" @click="toggleDesktopMode" :title="isDesktopMode ? 'Switch to Inline Mode' : 'Switch to Desktop Mode'">
          <component :is="isDesktopMode ? MonitorOff : Monitor" :size="16" />
          <span class="toggle-label">{{ isDesktopMode ? 'Inline' : 'Desktop' }}</span>
        </div>
        <div class="header-divider"></div>
        <button class="h-btn" title="Reset Pose" @click="handleResetPose"><RotateCcw :size="16" /></button>
        <button class="h-btn" title="Fullscreen"><Maximize2 :size="16" /></button>
        <button class="h-btn primary" title="Import Avatar" @click="handleImportClick">
          <Download :size="16" /> Import
        </button>
        <button class="h-btn" title="Settings"><Settings2 :size="16" /></button>
      </div>
    </div>

    <div class="avatar-body">
      <div class="avatar-stage animate-stage-appear">
        <div class="stage-canvas" :class="{ 'desktop-mode-active': isDesktopMode }">
          <template v-if="!isDesktopMode">
            <canvas ref="canvasRef" class="live2d-canvas"></canvas>

            <div v-if="isLoading" class="stage-loading">
              <Loader2 :size="32" class="loading-spinner" />
              <span class="loading-text">Loading LuomiNest Avatar...</span>
            </div>

            <div v-if="loadError" class="stage-error">
              <AlertCircle :size="32" />
              <span class="error-text">{{ loadError }}</span>
              <span class="error-hint">Check model resources and try again</span>
            </div>

            <div v-if="!isLoading && !loadError && !isModelReady" class="avatar-placeholder" :class="[`emotion-${currentEmotionLocal.id}`]">
              <div class="avatar-ring"></div>
              <div class="avatar-core">
                <Sparkles :size="48" class="avatar-sparkle" />
                <span class="avatar-label">{{ currentMode.toUpperCase() }}</span>
              </div>
              <div class="avatar-particles">
                <span v-for="i in 6" :key="i" class="particle" :style="{ '--delay': `${i * 0.15}s` }"></span>
              </div>
            </div>
          </template>

          <div v-if="isDesktopMode" class="desktop-mode-hint">
            <div class="hint-icon">
              <Monitor :size="40" />
            </div>
            <div class="hint-content">
              <h3>Desktop Pet Mode</h3>
              <p>The model has been switched to the desktop. You can interact with it directly on your desktop.</p>
              <p class="hint-sub">Right-click the desktop pet for more options. Use the toggle above to switch back.</p>
            </div>
            <button class="hint-back-btn" @click="toggleDesktopMode">
              <MonitorOff :size="16" />
              <span>Back to Inline</span>
            </button>
          </div>

          <div class="stage-overlay">
            <div class="overlay-tag mode-tag">
              <Eye :size="12" /> {{ avatarModes.find(m => m.id === currentMode)?.label }}
            </div>
            <div v-if="isDesktopMode" class="overlay-tag desktop-tag">
              <Monitor :size="12" /> Desktop
            </div>
            <div v-else class="overlay-tag emotion-tag" :style="{ borderColor: currentEmotionLocal.color }">
              <component :is="currentEmotionLocal.icon" :size="12" />
              {{ currentEmotionLocal.label }}
            </div>
            <div v-if="isModelReady && !isDesktopMode" class="overlay-tag status-tag">
              <span class="status-dot"></span> LuomiNest Ready
            </div>
          </div>
        </div>

        <div v-if="!isDesktopMode" class="stage-controls">
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
              <span>Emotion</span>
              <span class="expression-value">PAD: {{ expressionValue > 0 ? '+' : '' }}{{ expressionValue.toFixed(1) }}</span>
            </div>
            <div class="emotion-grid">
              <button
                v-for="emo in emotions"
                :key="emo.id"
                :class="['emo-btn', { active: currentEmotionLocal.id === emo.id }]"
                :style="{ '--emo-color': emo.color }"
                @click="selectEmotion(emo)"
              >
                <component :is="emo.icon" :size="18" />
                <span>{{ emo.label }}</span>
              </button>
            </div>
          </div>

          <div class="idle-panel">
            <div class="panel-title">
              <Volume2 :size="14" />
              <span>Idle Animation</span>
            </div>
            <div class="idle-list">
              <div
                v-for="(anim, idx) in idleAnimations"
                :key="idx"
                class="idle-item"
              >
                <div class="idle-info">
                  <span class="idle-name">{{ anim.name }}</span>
                  <span :class="['idle-status', anim.status]">{{ anim.status === 'running' ? 'Running' : 'Paused' }}</span>
                </div>
                <div class="idle-bar">
                  <div
                    class="idle-fill"
                    :class="anim.status"
                    :style="{ width: anim.progress + '%' }"
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div :class="['skin-sidebar', { 'sidebar-collapsed': !skinSidebarVisible }, 'animate-slide-right']">
        <button class="sidebar-toggle" @click="toggleSkinSidebar" :title="skinSidebarVisible ? 'Hide Library' : 'Show Library'">
          <component :is="skinSidebarVisible ? ChevronRight : ChevronLeft" :size="14" />
        </button>

        <template v-if="skinSidebarVisible">
          <div class="sidebar-title">Avatar Library</div>

          <div v-if="importError" class="import-error">
            <AlertCircle :size="14" />
            <span>{{ importError }}</span>
          </div>

          <div v-if="showImportSuccess" class="import-success">
            <Check :size="14" />
            <span>Model imported successfully</span>
          </div>

          <div class="skin-list">
            <div
              v-for="(skin, idx) in skinList"
              :key="idx"
              :class="['skin-card', { selected: selectedSkin === idx }]"
              @click="handleSkinSelect(idx)"
            >
              <div class="skin-thumb">
                <Palette :size="18" />
              </div>
              <div class="skin-info">
                <span class="skin-name">{{ skin.name }}</span>
                <span class="skin-type">{{ skin.type }}</span>
              </div>
              <div class="skin-tags">
                <span v-for="tag in skin.tags" :key="tag" class="skin-tag">{{ tag }}</span>
              </div>
            </div>
          </div>

          <button class="import-btn" @click="handleImportClick">
            <FolderOpen :size="14" />
            <span>Import .model3.json</span>
          </button>
        </template>
      </div>
    </div>
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
  flex-shrink: 0;
  position: relative;
}

.avatar-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 24px;
  right: 24px;
  height: 1px;
  background: var(--divider-soft);
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

.header-divider {
  width: 1px;
  height: 20px;
  background: var(--divider-soft);
  margin: 0 4px;
}

.desktop-mode-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  background: var(--surface-hover);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  user-select: none;
}

.desktop-mode-toggle:hover {
  color: var(--text);
  background: var(--surface);
  border-color: var(--lumi-primary);
}

.desktop-mode-toggle.active {
  background: rgba(13, 148, 136, 0.15);
  color: var(--lumi-primary);
  border: 1px solid rgba(13, 148, 136, 0.3);
}

.toggle-label {
  font-weight: 600;
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

.stage-canvas.desktop-mode-active {
  background:
    radial-gradient(circle at 50% 50%, rgba(13, 148, 136, 0.06) 0%, transparent 70%),
    var(--surface);
}

.live2d-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
}

.desktop-mode-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  padding: 40px;
  z-index: 5;
  text-align: center;
  animation: hint-fade-in 500ms ease-in-out;
}

@keyframes hint-fade-in {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.hint-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(13, 148, 136, 0.1);
  color: var(--lumi-primary);
  animation: hint-icon-pulse 3s ease-in-out infinite;
}

@keyframes hint-icon-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(13, 148, 136, 0.15); }
  50% { box-shadow: 0 0 0 12px rgba(13, 148, 136, 0); }
}

.hint-content h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 8px;
}

.hint-content p {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.6;
  max-width: 360px;
}

.hint-sub {
  font-size: 12px !important;
  opacity: 0.7;
  margin-top: 4px;
}

.hint-back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  border-radius: var(--radius-lg);
  background: var(--lumi-primary);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 300ms ease-in-out;
  margin-top: 8px;
}

.hint-back-btn:hover {
  background: var(--lumi-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(13, 148, 136, 0.3);
}

.stage-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  z-index: 10;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(4px);
}

[data-theme="dark"] .stage-loading {
  background: rgba(12, 10, 9, 0.6);
}

.loading-spinner {
  color: var(--lumi-primary);
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
}

.stage-error {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  z-index: 10;
  color: var(--lumi-accent);
}

.error-text {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}

.error-hint {
  font-size: 11px;
  color: var(--text-muted);
}

.avatar-placeholder {
  position: relative;
  width: 260px;
  height: 340px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-xl);
  background: linear-gradient(145deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-inset);
  transition: all 500ms ease-in-out;
  z-index: 2;
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
  gap: 12px;
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
  z-index: 20;
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

.desktop-tag {
  border-color: rgba(13, 148, 136, 0.5);
  color: var(--lumi-primary);
}

.status-tag {
  border-color: rgba(34, 197, 94, 0.4);
  color: #22c55e;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22c55e;
  animation: dot-pulse 2s ease-in-out infinite;
}

@keyframes dot-pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.stage-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 14px 20px;
  flex-shrink: 0;
  position: relative;
  align-items: flex-start;
}

.stage-controls::before {
  content: '';
  position: absolute;
  top: 0;
  left: 20px;
  right: 20px;
  height: 1px;
  background: var(--divider-soft);
}

.mode-switcher {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.mode-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  padding: 8px 14px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
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
  font-size: 9px;
  opacity: 0.55;
}

.emotion-panel,
.idle-panel {
  flex-shrink: 0;
  min-width: 180px;
  max-width: 220px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.expression-value {
  margin-left: auto;
  font-family: monospace;
  font-size: 10px;
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
  gap: 3px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
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

.idle-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.idle-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.idle-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.idle-name {
  font-size: 11px;
  color: var(--text);
}

.idle-status {
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 8px;
}

.idle-status.running {
  background: rgba(34, 197, 94, 0.12);
  color: #22c55e;
}

.idle-status.paused {
  background: rgba(107, 114, 128, 0.12);
  color: #6b7280;
}

.idle-bar {
  height: 3px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
}

.idle-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 1000ms ease-in-out;
}

.idle-fill.running {
  background: linear-gradient(90deg, var(--lumi-primary), #22c55e);
  animation: bar-pulse 2s ease-in-out infinite;
}

@keyframes bar-pulse {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}

.skin-sidebar {
  width: 230px;
  padding: 16px 12px;
  overflow-y: auto;
  overflow-x: hidden;
  flex-shrink: 0;
  background: var(--surface);
  position: relative;
  display: flex;
  flex-direction: column;
  transition: width 300ms ease-in-out, padding 300ms ease-in-out;
}

.skin-sidebar.sidebar-collapsed {
  width: 36px;
  padding: 20px 6px;
  overflow: hidden;
}

.skin-sidebar::before {
  content: '';
  position: absolute;
  top: 16px;
  bottom: 16px;
  left: 0;
  width: 1px;
  background: var(--divider-vertical);
}

.sidebar-toggle {
  position: absolute;
  top: 50%;
  left: -12px;
  transform: translateY(-50%);
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface);
  border: 1px solid var(--border-light);
  color: var(--text-muted);
  cursor: pointer;
  z-index: 10;
  transition: all 300ms ease-in-out;
}

.sidebar-toggle:hover {
  background: var(--surface-hover);
  color: var(--lumi-primary);
  border-color: var(--lumi-primary);
}

.sidebar-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text);
  letter-spacing: 0.3px;
}

.import-error {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  font-size: 11px;
  margin-bottom: 10px;
}

.import-success {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
  font-size: 11px;
  margin-bottom: 10px;
  animation: fade-in 300ms ease-in-out;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

.skin-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  overflow-y: auto;
  margin-right: 2px;
  padding-right: 2px;
}

.skin-list::-webkit-scrollbar {
  width: 3px;
}

.skin-list::-webkit-scrollbar-track {
  background: transparent;
}

.skin-list::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 3px;
}

.skin-list::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

.skin-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all 250ms ease-in-out;
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
  width: 38px;
  height: 38px;
  border-radius: 8px;
  background: var(--surface-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  flex-shrink: 0;
}

.skin-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.skin-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text);
}

.skin-type {
  font-size: 10px;
  color: var(--text-muted);
  opacity: 0.75;
}

.skin-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: 4px;
}

.skin-tag {
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 6px;
  background: var(--surface-hover);
  color: var(--text-muted);
  line-height: 1.4;
}

.import-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: var(--radius-md);
  border: 1px dashed var(--border-light);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  font-size: 12px;
  margin-top: 12px;
  flex-shrink: 0;
}

.import-btn:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: rgba(13, 148, 136, 0.05);
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
</style>
