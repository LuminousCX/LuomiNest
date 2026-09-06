<script setup lang="ts">
import { computed } from 'vue'
import type { VNodeRef } from 'vue'
import {
  Loader2,
  AlertTriangle,
  Volume2,
  VolumeX,
  Subtitles,
  StopCircle,
  Monitor,
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import type { LuomiNestModelInfo } from '../../config/luominest-models'

const props = defineProps<{
  isDesktopMode: boolean
  currentModelInfo: LuomiNestModelInfo
  isModelLoading: boolean
  isModelReady: boolean
  loadError: string | null
  isSpeaking: boolean
  isSynthesizing: boolean
  subtitleVisible: boolean
  subtitleText: string
  ttsEnabled: boolean
  subtitleEnabled: boolean
  builtinModels: LuomiNestModelInfo[]
  setCanvasRef: VNodeRef
}>()

const emit = defineEmits<{
  'switch-model': [model: LuomiNestModelInfo]
  'toggle-tts': []
  'toggle-subtitle': []
  'stop-tts': []
  'dismiss-subtitle': []
}>()
// 此页面方便用户切换角色形象
const statusText = computed(() => {
  if (props.isSpeaking) return '正在说话'
  if (props.isSynthesizing) return '合成语音中'
  return `${props.currentModelInfo.name} 已就绪`
})
</script>

<template>
  <div class="avatar-main">
    <div class="avatar-header">
      <div class="avatar-title">
        <span>陪伴形象</span>
      </div>
      <div class="avatar-model-selector">
        <LumiButton
          v-for="model in builtinModels"
          :key="model.id"
          :variant="currentModelInfo.id === model.id ? 'primary' : 'outline'"
          size="sm"
          :class="['model-chip', { active: currentModelInfo.id === model.id }]"
          :title="model.name"
          @click="emit('switch-model', model)"
        >
          {{ model.name }}
        </LumiButton>
      </div>
    </div>

    <div class="avatar-stage" :class="{ 'desktop-mode-active': isDesktopMode }">
      <template v-if="!isDesktopMode">
        <canvas :ref="setCanvasRef" class="live2d-canvas"></canvas>
        <Transition name="fade">
          <div v-if="isModelLoading && !isModelReady" class="avatar-loading">
            <Loader2 :size="28" class="spin-animation" />
            <span>加载模型中...</span>
          </div>
        </Transition>
        <Transition name="fade">
          <div v-if="loadError" class="avatar-error">
            <AlertTriangle :size="24" />
            <span>{{ loadError }}</span>
          </div>
        </Transition>
        <div v-if="isModelReady" class="avatar-status">
          <span class="status-dot" :class="{ speaking: isSpeaking }"></span>
          <span>{{ statusText }}</span>
        </div>
        <Transition name="subtitle-fade">
          <div
            v-if="subtitleVisible && subtitleText"
            class="avatar-subtitle"
            @click="emit('dismiss-subtitle')"
          >
            {{ subtitleText }}
          </div>
        </Transition>
      </template>

      <div v-else class="desktop-mode-hint">
        <div class="hint-icon">
          <Monitor :size="40" />
        </div>
        <div class="hint-content">
          <h3>桌宠模式已开启</h3>
          <p>模型已切换到桌面宠物窗口，请直接在桌面上与角色互动。</p>
          <p class="hint-sub">工作台的对话、表情和动作会同步到桌宠。前往"皮套工坊"可切换回内联模式。</p>
        </div>
      </div>
    </div>

    <div class="avatar-footer">
      <div class="avatar-controls">
        <LumiButton
          variant="outline"
          size="sm"
          icon-only
          :aria-label="ttsEnabled ? '关闭语音播报' : '开启语音播报'"
          :class="['ctrl-btn', { active: ttsEnabled }]"
          @click="emit('toggle-tts')"
        >
          <template #icon>
            <Volume2 v-if="ttsEnabled" :size="15" />
            <VolumeX v-else :size="15" />
          </template>
        </LumiButton>
        <LumiButton
          variant="outline"
          size="sm"
          icon-only
          :aria-label="subtitleEnabled ? '关闭字幕' : '开启字幕'"
          :class="['ctrl-btn', { active: subtitleEnabled }]"
          @click="emit('toggle-subtitle')"
        >
          <template #icon>
            <Subtitles :size="15" />
          </template>
        </LumiButton>
        <LumiButton
          v-if="isSpeaking || isSynthesizing"
          variant="danger"
          size="sm"
          icon-only
          aria-label="停止播放"
          class="ctrl-btn stop-btn"
          @click="emit('stop-tts')"
        >
          <template #icon>
            <StopCircle :size="15" />
          </template>
        </LumiButton>
      </div>
      <p class="avatar-tip">主 Agent 工作台 · 支持工具调用与子 Agent 协作</p>
    </div>
  </div>
</template>

<style scoped>
button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}

.avatar-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.avatar-header {
  padding: var(--space-3) var(--space-4) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.avatar-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-3);
}

.avatar-model-selector {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.model-chip {
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
}

.model-chip.active {
  background: var(--lumi-primary);
  color: var(--text-inverse);
  border-color: var(--lumi-primary);
}

.avatar-stage {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface);
  overflow: hidden;
}

.avatar-stage.desktop-mode-active {
  background:
    radial-gradient(circle at 50% 50%, var(--lumi-primary-subtle) 0%, transparent 70%),
    var(--surface);
}

.desktop-mode-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-5);
  padding: var(--space-10) var(--space-6);
  text-align: center;
  animation: hint-fade-in 500ms var(--ease-in-out);
}

@keyframes hint-fade-in {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.desktop-mode-hint .hint-icon {
  width: 72px;
  height: 72px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  animation: hint-icon-pulse 3s var(--ease-in-out) infinite;
}

@keyframes hint-icon-pulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--lumi-primary-glow); }
  50% { box-shadow: 0 0 0 12px transparent; }
}

.desktop-mode-hint .hint-content h3 {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.desktop-mode-hint .hint-content p {
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: var(--leading-relaxed);
  max-width: 280px;
}

.desktop-mode-hint .hint-sub {
  font-size: var(--text-xs) !important;
  opacity: 0.7;
  margin-top: var(--space-1);
}

.live2d-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.avatar-loading,
.avatar-error {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  color: var(--text-muted);
  font-size: var(--text-base);
  background: var(--surface);
}

.avatar-error {
  color: var(--lumi-danger);
}

.avatar-status {
  position: absolute;
  bottom: var(--space-3);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: var(--surface);
  backdrop-filter: blur(8px);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  border: 1px solid var(--border-light);
  z-index: 2;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--lumi-success);
  animation: pulse 2s var(--ease-in-out) infinite;
}

.status-dot.speaking {
  background: var(--lumi-primary);
  animation: pulse 0.6s var(--ease-in-out) infinite;
}

.avatar-subtitle {
  position: absolute;
  bottom: var(--space-9);
  left: 50%;
  transform: translateX(-50%);
  max-width: 88%;
  padding: var(--space-2) var(--space-4);
  background: var(--surface);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
  color: var(--text-primary);
  text-align: center;
  cursor: pointer;
  z-index: 3;
  box-shadow: var(--shadow-sm);
}

.avatar-footer {
  padding: var(--space-3) var(--space-4) var(--space-4);
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

.avatar-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.ctrl-btn.lumi-btn {
  width: var(--space-7);
  height: var(--space-7);
  color: var(--text-muted);
}

.ctrl-btn:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.ctrl-btn.active {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.ctrl-btn.stop-btn {
  border-color: var(--lumi-danger);
  color: var(--lumi-danger);
  background: var(--lumi-danger-light);
}

.ctrl-btn.stop-btn:hover {
  background: var(--lumi-danger);
  color: var(--text-inverse);
}

.avatar-tip {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin: 0;
  text-align: center;
  line-height: var(--leading-normal);
}


@keyframes pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--transition-fast);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.subtitle-fade-enter-active,
.subtitle-fade-leave-active {
  transition: opacity var(--transition-fast);
}

.subtitle-fade-enter-from,
.subtitle-fade-leave-to {
  opacity: 0;
}
</style>
