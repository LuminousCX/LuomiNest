<script setup lang="ts">
import type { VNodeRef } from 'vue'
import { computed } from 'vue'
import {
  Sparkles,
  Loader2,
  AlertCircle,
  Monitor,
  MonitorOff,
  Eye
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import { useStageBackgroundStore } from '@/stores/stage-background'
import type { AvatarEmotion, AvatarMode } from './types'

const props = defineProps<{
  setCanvasRef: VNodeRef
  isDesktopMode: boolean
  isLoading: boolean
  loadError: string | null
  isModelReady: boolean
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
</script>

<template>
  <div class="stage-canvas" :class="{ 'desktop-mode-active': props.isDesktopMode }" :style="stageBgStyle">
    <template v-if="!props.isDesktopMode">
      <canvas :ref="props.setCanvasRef" class="live2d-canvas"></canvas>

      <div v-if="props.isLoading" class="stage-loading">
        <Loader2 :size="32" class="loading-spinner" />
        <span class="loading-text">Loading LuomiNest Avatar...</span>
      </div>

      <div v-if="props.loadError" class="stage-error">
        <AlertCircle :size="32" />
        <span class="error-text">{{ props.loadError }}</span>
        <span class="error-hint">Check model resources and try again</span>
      </div>

      <Transition name="subtitle-fade">
        <div
          v-if="props.subtitleEnabled && props.subtitleVisible && props.subtitleText"
          class="subtitle-overlay"
        >
          <span class="subtitle-text">{{ props.subtitleText }}</span>
        </div>
      </Transition>

      <div v-if="!props.isLoading && !props.loadError && !props.isModelReady" class="avatar-placeholder" :class="[props.currentEmotionLocal ? `emotion-${props.currentEmotionLocal.id}` : 'emotion-none']">
        <div class="avatar-ring"></div>
        <div class="avatar-core">
          <Sparkles :size="48" class="avatar-sparkle" />
          <span class="avatar-label">{{ props.currentMode.toUpperCase() }}</span>
        </div>
        <div class="avatar-particles">
          <span v-for="i in 6" :key="i" class="particle" :style="{ '--delay': `${i * 0.15}s` }"></span>
        </div>
      </div>
    </template>

    <div v-if="props.isDesktopMode" class="desktop-mode-hint">
      <div class="hint-icon">
        <Monitor :size="40" />
      </div>
      <div class="hint-content">
        <h3>Desktop Pet Mode</h3>
        <p>The model has been switched to the desktop. You can interact with it directly on your desktop.</p>
        <p class="hint-sub">Right-click the desktop pet for more options. Use the toggle above to switch back.</p>
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
      <div v-else-if="props.currentEmotionLocal" class="overlay-tag emotion-tag" :style="{ borderColor: props.currentEmotionLocal.color }">
        <component :is="props.currentEmotionLocal.icon" :size="12" />
        {{ props.currentEmotionLocal.label }}
      </div>
      <div v-if="props.isModelReady && !props.isDesktopMode" class="overlay-tag status-tag">
        <span class="status-dot"></span> LuomiNest Ready
      </div>
    </div>
  </div>
</template>

<style scoped src="./stage-shared.css"></style>

<style scoped>
/* 本块只保留 AvatarStage 相对 stage-shared.css 的差异（报告 §10.2-B） */

.stage-canvas {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 320px;
  background:
    radial-gradient(circle at 50% 50%, var(--lumi-primary-subtle) 0%, transparent 70%),
    var(--surface);
  overflow: hidden;
}

.stage-canvas.desktop-mode-active {
  background:
    radial-gradient(circle at 50% 50%, var(--lumi-primary-subtle) 0%, transparent 70%),
    var(--surface);
}

.live2d-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
}

/* .subtitle-text 比共享版多 letter-spacing */
.subtitle-text {
  letter-spacing: 0.02em;
}

/* subtitle-fade：带 translateY 位移版（Pixel/Png 为纯 opacity 版） */
.subtitle-fade-enter-active {
  transition: opacity var(--duration-normal) var(--ease-in-out), transform var(--duration-normal) var(--ease-in-out);
}

.subtitle-fade-leave-active {
  transition: opacity var(--duration-slow) var(--ease-in-out), transform var(--duration-slow) var(--ease-in-out);
}

.subtitle-fade-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(6px);
}

.subtitle-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(0);
}

.subtitle-fade-enter-to,
.subtitle-fade-leave-from {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

/* .hint-icon 比共享版多脉冲动画（brand 色系） */
.hint-icon {
  animation: hint-icon-pulse 3s var(--ease-in-out) infinite;
}

@keyframes hint-icon-pulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--lumi-brand-glow); }
  50% { box-shadow: 0 0 0 12px transparent; }
}

/* .stage-error：不带共享版的模糊底，且 gap 更小（space-2） */
.stage-error {
  gap: var(--space-2);
  background: transparent;
  backdrop-filter: none;
}

[data-theme="dark"] .stage-loading {
  background: color-mix(in srgb, var(--surface) 60%, transparent);
}

/* .avatar-placeholder 比共享版多渐变底/内阴影/过渡 */
.avatar-placeholder {
  background: linear-gradient(145deg, color-mix(in srgb, var(--surface) 6%, transparent), color-mix(in srgb, var(--surface) 2%, transparent));
  box-shadow: var(--shadow-inset);
  transition: all var(--duration-slow) var(--ease-in-out);
}

/* primary 色系覆盖（共享版不含颜色） */
.avatar-ring {
  border: 1.5px dashed var(--lumi-primary-border);
}

.avatar-sparkle {
  color: var(--lumi-primary);
}

.avatar-particles {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.particle {
  position: absolute;
  width: var(--space-1);
  height: var(--space-1);
  border-radius: var(--radius-full);
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

/* emotion-tag：动态情绪色（模板注入 --emo-color，保持本地） */
.emotion-tag {
  border-color: var(--emo-color, var(--lumi-primary));
  color: var(--emo-color, var(--lumi-primary));
}

.desktop-tag {
  border-color: var(--lumi-primary-border);
  color: var(--lumi-primary);
}

.status-tag {
  border-color: var(--task-green-border);
  color: var(--lumi-success);
}
</style>
