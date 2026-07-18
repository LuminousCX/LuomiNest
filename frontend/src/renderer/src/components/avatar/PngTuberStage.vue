<script setup lang="ts">
/**
 * PngTuberStage - PNG Tuber 模型独立展示组件
 *
 * 设计原则：
 * - 完全独立于 AvatarStage（不共享 canvas，避免 PIXI.Application 冲突）
 * - 内部封装 usePngTuber，对外暴露驱动方法（defineExpose）
 * - 复用 PixelPetStage 的视觉风格（loading/error/subtitle/overlay）
 * - 支持桌面宠物模式（通过 isDesktopMode 切换显示）
 * - 参照 OpenAI Codex Pet 的 spritesheet 格式（9 状态 × 8 帧）
 *
 * 集成方式：
 * - 父组件根据 currentMode === 'png' 切换显示 AvatarStage / PixelPetStage / PngTuberStage
 * - 通过 ref 调用暴露的驱动方法（driveEmotion / syncLipParam 等）
 *
 * 模型加载：
 * - 通过 luominest-avatar://png/{model}/manifest.json 加载 manifest
 * - 然后 usePngTuber 内部加载 spritesheet.png 并切割帧
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import {
  Sparkles,
  Loader2,
  AlertCircle,
  Monitor,
  MonitorOff,
  Eye
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import { usePngTuber } from '@/composables/avatar/usePngTuber'
import type { AvatarEmotion, AvatarMode } from './types'

const props = defineProps<{
  isDesktopMode: boolean
  currentEmotionLocal: AvatarEmotion | null
  currentMode: string
  avatarModes: AvatarMode[]
  subtitleEnabled: boolean
  subtitleText: string
  subtitleVisible: boolean
  /** manifest.json 的 URL（luominest-avatar://png/{model}/manifest.json） */
  manifestUrl: string
}>()

const emit = defineEmits<{
  'toggle-desktop-mode': []
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const setCanvasRef = (el: unknown) => {
  canvasRef.value = (el as HTMLCanvasElement | null) ?? null
}

const renderer = usePngTuber(canvasRef, 'builtin-png-codex')

const isReady = ref(false)
const isLoading = ref(false)
const loadError = ref<string | null>(null)

onMounted(async () => {
  isLoading.value = true
  try {
    await renderer.loadModel(props.manifestUrl)
    if (renderer.state.error) {
      loadError.value = renderer.state.error
    } else {
      isReady.value = true
    }
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Failed to load PNG Tuber'
  } finally {
    isLoading.value = false
  }
})

onBeforeUnmount(() => {
  renderer.destroy()
})

// 暴露驱动方法给父组件
defineExpose({
  driveEmotion: renderer.driveEmotion,
  drivePadEmotion: renderer.drivePadEmotion,
  syncLipParam: renderer.syncLipParam,
  syncLipVowel: renderer.syncLipVowel,
  triggerMotion: renderer.triggerMotion,
  triggerExpression: renderer.triggerExpression,
  resetPose: renderer.resetPose,
  isReady: () => isReady.value,
})
</script>

<template>
  <div class="stage-canvas png-stage" :class="{ 'desktop-mode-active': props.isDesktopMode }">
    <template v-if="!props.isDesktopMode">
      <canvas :ref="setCanvasRef" class="png-canvas"></canvas>

      <div v-if="isLoading" class="stage-loading">
        <Loader2 :size="32" class="loading-spinner" />
        <span class="loading-text">Loading PNG Tuber...</span>
      </div>

      <div v-if="loadError" class="stage-error">
        <AlertCircle :size="32" />
        <span class="error-text">{{ loadError }}</span>
        <span class="error-hint">PNG Tuber renderer initialization failed</span>
      </div>

      <Transition name="subtitle-fade">
        <div
          v-if="props.subtitleEnabled && props.subtitleVisible && props.subtitleText"
          class="subtitle-overlay"
        >
          <span class="subtitle-text">{{ props.subtitleText }}</span>
        </div>
      </Transition>

      <div
        v-if="!isLoading && !loadError && !isReady"
        class="avatar-placeholder"
        :class="[props.currentEmotionLocal ? `emotion-${props.currentEmotionLocal.id}` : 'emotion-none']"
      >
        <div class="avatar-ring"></div>
        <div class="avatar-core">
          <Sparkles :size="48" class="avatar-sparkle" />
          <span class="avatar-label">{{ props.currentMode.toUpperCase() }}</span>
        </div>
      </div>
    </template>

    <div v-if="props.isDesktopMode" class="desktop-mode-hint">
      <div class="hint-icon">
        <Monitor :size="40" />
      </div>
      <div class="hint-content">
        <h3>Desktop Pet Mode</h3>
        <p>PNG Tuber has been switched to the desktop.</p>
        <p class="hint-sub">Right-click the desktop pet for more options.</p>
      </div>
      <LumiButton variant="primary" size="sm" @click="emit('toggle-desktop-mode')">
        <template #icon><MonitorOff :size="16" /></template>
        <span>Back to Inline</span>
      </LumiButton>
    </div>

    <div class="stage-overlay">
      <div class="overlay-tag mode-tag">
        <Eye :size="12" /> {{ props.avatarModes.find(m => m.id === props.currentMode)?.label }}
      </div>
      <div v-if="props.isDesktopMode" class="overlay-tag desktop-tag">
        <Monitor :size="12" /> Desktop
      </div>
      <div v-else-if="props.currentEmotionLocal" class="overlay-tag emotion-tag">
        <component :is="props.currentEmotionLocal.icon" :size="12" />
        {{ props.currentEmotionLocal.label }}
      </div>
      <div v-if="isReady && !props.isDesktopMode" class="overlay-tag status-tag">
        <span class="status-dot"></span> PNG Tuber Ready
      </div>
    </div>
  </div>
</template>

<style scoped>
.png-stage {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 320px;
  background:
    radial-gradient(circle at 50% 50%, var(--lumi-brand-subtle) 0%, transparent 70%),
    var(--surface);
  overflow: hidden;
}

.png-canvas {
  position: absolute;
  inset: 0;
  margin: auto;
  width: 256px;
  height: 256px;
  z-index: 1;
  image-rendering: auto;
}

.stage-loading,
.stage-error {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  z-index: 10;
  background: color-mix(in srgb, var(--surface) 60%, transparent);
  backdrop-filter: blur(4px);
}

.loading-spinner {
  color: var(--lumi-brand);
  animation: spin 1s linear infinite;
}

.loading-text {
  font-size: var(--text-base);
  color: var(--text-muted);
  font-weight: var(--font-medium);
}

.stage-error {
  color: var(--lumi-accent);
}

.error-text {
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text);
}

.error-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.subtitle-overlay {
  position: absolute;
  bottom: var(--space-6);
  left: 50%;
  transform: translateX(-50%);
  z-index: 15;
  max-width: 80%;
  padding: var(--space-2) var(--space-5);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--surface) 85%, transparent);
  backdrop-filter: blur(8px);
  box-shadow: var(--shadow-sm);
  pointer-events: none;
}

.subtitle-text {
  font-size: var(--text-md);
  line-height: var(--leading-relaxed);
  color: var(--text);
  text-align: center;
  font-weight: var(--font-medium);
}

.subtitle-fade-enter-active,
.subtitle-fade-leave-active {
  transition: opacity var(--duration-normal) var(--ease-in-out);
}

.subtitle-fade-enter-from,
.subtitle-fade-leave-to {
  opacity: 0;
}

.avatar-placeholder {
  position: relative;
  width: 260px;
  height: 340px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-light);
  z-index: 2;
}

.avatar-ring {
  position: absolute;
  width: 200px;
  height: 200px;
  border-radius: var(--radius-full);
  border: 1.5px dashed var(--lumi-brand-border);
  animation: ring-spin 12s linear infinite;
}

@keyframes ring-spin {
  to { transform: rotate(360deg); }
}

.avatar-core {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  z-index: 1;
}

.avatar-sparkle {
  color: var(--lumi-brand);
  opacity: 0.6;
  animation: sparkle-pulse 2s ease-in-out infinite;
}

@keyframes sparkle-pulse {
  0%, 100% { opacity: 0.4; transform: scale(1); }
  50% { opacity: 0.9; transform: scale(1.1); }
}

.avatar-label {
  font-size: var(--text-base);
  font-weight: 600;
  letter-spacing: 3px;
  color: var(--text-muted);
}

.desktop-mode-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-5);
  padding: var(--space-8);
  z-index: 5;
  text-align: center;
  animation: hint-fade-in var(--duration-slow) var(--ease-in-out);
}

@keyframes hint-fade-in {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.hint-icon {
  width: 72px;
  height: 72px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.hint-content h3 {
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
  color: var(--text);
  margin-bottom: var(--space-2);
}

.hint-content p {
  font-size: var(--text-base);
  color: var(--text-muted);
  line-height: var(--leading-relaxed);
  max-width: 360px;
}

.hint-sub {
  font-size: var(--text-sm) !important;
  opacity: 0.7;
  margin-top: var(--space-1);
}

.stage-overlay {
  position: absolute;
  top: var(--space-4);
  left: var(--space-4);
  display: flex;
  gap: var(--space-2);
  z-index: 20;
}

.overlay-tag {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-xl);
  font-size: var(--text-xs);
  font-weight: 500;
  backdrop-filter: blur(8px);
  background: var(--overlay-subtle);
  border: 1px solid var(--border-light);
  color: var(--text-inverse);
}

.emotion-tag {
  border-color: var(--lumi-brand-border);
  color: var(--lumi-brand);
}

.desktop-tag {
  border-color: var(--lumi-brand-border);
  color: var(--lumi-brand);
}

.status-tag {
  border-color: var(--lumi-success-border, var(--lumi-success));
  color: var(--lumi-success);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--lumi-success);
  animation: dot-pulse 2s ease-in-out infinite;
}

@keyframes dot-pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
