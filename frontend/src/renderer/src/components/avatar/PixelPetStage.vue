<script setup lang="ts">
/**
 * PixelPetStage - 像素模型独立展示组件
 *
 * 设计原则：
 * - 完全独立于 AvatarStage（不共享 canvas，避免 PIXI.Application 冲突）
 * - 内部封装 usePixelPet，对外暴露驱动方法（defineExpose）
 * - 复用 AvatarStage 的视觉风格（loading/error/subtitle/overlay）
 * - 支持桌面宠物模式（通过 isDesktopMode 切换显示）
 *
 * 集成方式：
 * - 父组件根据 currentMode === 'pixel' 切换显示 AvatarStage 或 PixelPetStage
 * - 通过 ref 调用暴露的驱动方法（driveEmotion / syncLipParam 等）
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import {
  Sparkles,
  Loader2,
  AlertCircle,
  Monitor,
  MonitorOff,
  Eye
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import { usePixelPet } from '@/composables/avatar/usePixelPet'
import { useStageBackgroundStore } from '@/stores/stage-background'
import type { AvatarEmotion, AvatarMode } from './types'

const props = defineProps<{
  isDesktopMode: boolean
  currentEmotionLocal: AvatarEmotion | null
  currentMode: string
  avatarModes: AvatarMode[]
  subtitleEnabled: boolean
  subtitleText: string
  subtitleVisible: boolean
}>()

const emit = defineEmits<{
  'toggle-desktop-mode': []
}>()

// 舞台自定义背景（默认渐变底时 backgroundStyle 为空，不覆盖组件原样式）
const stageBg = useStageBackgroundStore()
const stageBgStyle = computed(() =>
  stageBg.backgroundStyle ? { background: stageBg.backgroundStyle } : undefined
)

const canvasRef = ref<HTMLCanvasElement | null>(null)
const setCanvasRef = (el: unknown) => {
  canvasRef.value = (el as HTMLCanvasElement | null) ?? null
}

const renderer = usePixelPet(canvasRef, 'builtin-pixel-default')

const isReady = ref(false)
const isLoading = ref(false)
const loadError = ref<string | null>(null)

onMounted(async () => {
  isLoading.value = true
  try {
    await renderer.loadModel('builtin-pixel-default')
    isReady.value = true
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Failed to load PixelPet'
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
  <div class="stage-canvas pixel-stage" :class="{ 'desktop-mode-active': props.isDesktopMode }" :style="stageBgStyle">
    <template v-if="!props.isDesktopMode">
      <canvas :ref="setCanvasRef" class="pixel-canvas"></canvas>

      <div v-if="isLoading" class="stage-loading">
        <Loader2 :size="32" class="loading-spinner" />
        <span class="loading-text">Loading PixelPet...</span>
      </div>

      <div v-if="loadError" class="stage-error">
        <AlertCircle :size="32" />
        <span class="error-text">{{ loadError }}</span>
        <span class="error-hint">Pixel renderer initialization failed</span>
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
        <p>PixelPet has been switched to the desktop.</p>
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
        <span class="status-dot"></span> PixelPet Ready
      </div>
    </div>
  </div>
</template>

<style scoped src="./stage-shared.css"></style>

<style scoped>
/* 本块只保留 PixelPetStage 相对 stage-shared.css 的差异（报告 §10.2-B） */

.pixel-stage {
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

.pixel-canvas {
  position: absolute;
  inset: 0;
  margin: auto;
  width: 256px;
  height: 256px;
  z-index: 1;
  image-rendering: pixelated;
  image-rendering: -moz-crisp-edges;
  image-rendering: crisp-edges;
}

/* subtitle-fade：纯 opacity 版（AvatarStage 为 translateY 位移版） */
.subtitle-fade-enter-active,
.subtitle-fade-leave-active {
  transition: opacity var(--duration-normal) var(--ease-in-out);
}

.subtitle-fade-enter-from,
.subtitle-fade-leave-to {
  opacity: 0;
}

/* brand 色系覆盖（共享版不含颜色） */
.avatar-ring {
  border: 1.5px dashed var(--lumi-brand-border);
}

.avatar-sparkle {
  color: var(--lumi-brand);
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
</style>
