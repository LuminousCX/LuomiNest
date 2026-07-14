<script setup lang="ts">
import type { VNodeRef } from 'vue'
import {
  Sparkles,
  Loader2,
  AlertCircle,
  Monitor,
  MonitorOff,
  Eye
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
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
</script>

<template>
  <div class="stage-canvas" :class="{ 'desktop-mode-active': props.isDesktopMode }">
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

<style scoped>
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
  animation: hint-icon-pulse 3s var(--ease-in-out) infinite;
}

@keyframes hint-icon-pulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--lumi-brand-glow); }
  50% { box-shadow: 0 0 0 12px transparent; }
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

.stage-loading {
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

[data-theme="dark"] .stage-loading {
  background: color-mix(in srgb, var(--surface) 60%, transparent);
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
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  z-index: 10;
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
  letter-spacing: 0.02em;
}

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

.avatar-placeholder {
  position: relative;
  width: 260px;
  height: 340px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-xl);
  background: linear-gradient(145deg, color-mix(in srgb, var(--surface) 6%, transparent), color-mix(in srgb, var(--surface) 2%, transparent));
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-inset);
  transition: all var(--duration-slow) var(--ease-in-out);
  z-index: 2;
}

.avatar-ring {
  position: absolute;
  width: 200px;
  height: 200px;
  border-radius: var(--radius-full);
  border: 1.5px dashed var(--lumi-primary-border);
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
  color: var(--lumi-primary);
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
</style>
