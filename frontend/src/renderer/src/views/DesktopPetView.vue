<script setup lang="ts">
/**
 * LuomiNest 桌面宠物视图（独立窗口）
 *
 * 仅负责组合：canvas + 3 个 composable + 3 个子组件 + 生命周期。
 * 所有 Live2D 逻辑在 useDesktopPetLive2D，IPC 在 useDesktopPetIpc，字幕在 useDesktopPetSubtitle。
 * 输入区通过 window.api.desktopPetChat 将消息转发到主应用窗口（useDesktopPetChatBridge 接收）。
 */
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { LUOMINEST_BUILTIN_MODELS } from '@/config/luominest-models'
import type { PetModelInfo } from '@shared/ipc-types'
import { useDesktopPetLive2D } from '@/composables/useDesktopPetLive2D'
import { useDesktopPetIpc } from '@/composables/useDesktopPetIpc'
import { useDesktopPetSubtitle } from '@/composables/useDesktopPetSubtitle'
import DesktopPetControls from '@/components/desktop-pet/DesktopPetControls.vue'
import DesktopPetSubtitle from '@/components/desktop-pet/DesktopPetSubtitle.vue'

const canvasRef = ref<HTMLCanvasElement | null>(null)
const isControlsVisible = ref(false)
const isAlwaysOnTop = ref(true)
// 桌宠窗口本地的流式状态（由主应用通过 IPC 反馈，用于输入区的发送/取消切换）

const {
  isModelReady,
  isLoading,
  loadError,
  currentModelName,
  currentModelId,
  availableMotions,
  availableExpressions,
  loadModel,
  setupCanvasDrag,
  triggerMotion,
  triggerExpression,
  drivePadEmotion,
  setScale,
  setCoreParam,
  resetPose,
  handleResize,
  setVisibility,
  close,
  destroy
} = useDesktopPetLive2D(canvasRef)

const { subtitleText, subtitleVisible, showSubtitle, hideSubtitle, clearSubtitleFade } = useDesktopPetSubtitle()

const { setupIpc, cleanupIpc } = useDesktopPetIpc({
  onLoadModel: async (modelInfo) => {
    currentModelName.value = modelInfo.name
    currentModelId.value = modelInfo.id
    if (canvasRef.value) {
      await loadModel(modelInfo.url, modelInfo.scale)
    }
  },
  onTriggerMotion: (group, index) => { void triggerMotion(group, index) },
  onTriggerExpression: (name) => { void triggerExpression(name) },
  onSetScale: (scale) => setScale(scale),
  onLipSync: (value) => {
    const clamped = Math.max(0, Math.min(1, value))
    setCoreParam('ParamMouthOpenY', clamped)
  },
  onPadEmotion: (pad) => drivePadEmotion(pad.pleasure, pad.arousal, pad.dominance),
  onSetCoreParam: (paramId, value) => setCoreParam(paramId, value),
  onGetModelCapabilities: (requestId) => {
    window.electron?.ipcRenderer.send('desktop-pet:model-capabilities-response', requestId, {
      motions: availableMotions.value,
      expressions: availableExpressions.value,
      modelName: currentModelName.value,
      isReady: isModelReady.value
    })
  },
  onSubtitle: (text) => showSubtitle(text),
  onSubtitleHide: () => hideSubtitle(),
  onStreamingState: () => {},
  onVisibilityChanged: (visible) => setVisibility(visible)
})

// 桌宠窗口输入区：发送消息到主应用窗口（由 useDesktopPetChatBridge 接收）

// 控制面板计时器（view 私有）
let controlsHideTimer: ReturnType<typeof setTimeout> | null = null

const showControls = (): void => {
  isControlsVisible.value = true
  if (controlsHideTimer) clearTimeout(controlsHideTimer)
}

const scheduleHideControls = (): void => {
  if (controlsHideTimer) clearTimeout(controlsHideTimer)
  controlsHideTimer = setTimeout(() => {
    isControlsVisible.value = false
  }, 3000)
}

const handleResetPose = async (): Promise<void> => {
  showControls()
  await resetPose()
  scheduleHideControls()
}

const handleToggleAlwaysOnTop = (): void => {
  showControls()
  isAlwaysOnTop.value = !isAlwaysOnTop.value
  window.electron?.ipcRenderer.send('desktop-pet:set-always-on-top', isAlwaysOnTop.value)
  scheduleHideControls()
}

const handleClose = (): void => {
  close()
}

// 窗口级事件监听器
let resizeHandler: (() => void) | null = null

onMounted(async () => {
  await nextTick()

  const modelInfoStr = new URLSearchParams(window.location.hash.split('?')[1] || '').get('model')
  let modelToLoad: PetModelInfo | null = null

  if (modelInfoStr) {
    try {
      modelToLoad = JSON.parse(decodeURIComponent(modelInfoStr)) as PetModelInfo
    } catch {
      // intentionally ignored
    }
  }

  if (!modelToLoad) {
    const builtin = LUOMINEST_BUILTIN_MODELS[0]
    modelToLoad = { id: builtin.id, name: builtin.name, url: builtin.url, scale: builtin.scale, type: builtin.type, tags: builtin.tags }
  }

  currentModelName.value = modelToLoad.name
  currentModelId.value = modelToLoad.id

  setupIpc()

  resizeHandler = () => {
    handleResize()
  }
  window.addEventListener('resize', resizeHandler)

  if (canvasRef.value) {
    await loadModel(modelToLoad.url, modelToLoad.scale)
  }

  setupCanvasDrag()
})

onBeforeUnmount(() => {
  cleanupIpc()
  destroy()
  clearSubtitleFade()

  if (controlsHideTimer) clearTimeout(controlsHideTimer)

  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
    resizeHandler = null
  }
})
</script>

<template>
  <div class="desktop-pet-view">
    <canvas ref="canvasRef" class="pet-canvas"></canvas>

    <div v-if="isLoading" class="pet-loading">
      <div class="pet-loading-spinner"></div>
    </div>

    <div v-if="loadError" class="pet-error">
      <span>{{ loadError }}</span>
    </div>

    <DesktopPetSubtitle :visible="subtitleVisible" :text="subtitleText" />

    <DesktopPetControls
      :visible="isControlsVisible"
      :is-always-on-top="isAlwaysOnTop"
      @reset-pose="handleResetPose"
      @toggle-always-on-top="handleToggleAlwaysOnTop"
      @close="handleClose"
      @mouseenter="showControls"
      @mouseleave="scheduleHideControls"
    />

  </div>
</template>

<style scoped>
.desktop-pet-view {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: transparent !important;
  position: relative;
  margin: 0;
  padding: 0;
  /* Use the system drag region for transparent windows to avoid the white
     background flash caused by manual setPosition during dragging. */
  -webkit-app-region: drag;
}

:global(html.desktop-pet),
:global(html.desktop-pet body),
:global(html.desktop-pet #app) {
  background: transparent !important;
}

.pet-canvas {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: var(--z-base);
  background: transparent;
  /* The canvas handles its own mouse events (hit tests, wheel zoom). */
  -webkit-app-region: no-drag;
}

.pet-loading {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-sticky);
  pointer-events: none;
}

.pet-loading-spinner {
  width: var(--space-6);
  height: var(--space-6);
  border: 2px solid var(--lumi-brand-border);
  border-top-color: var(--lumi-brand);
  border-radius: var(--radius-full);
  animation: pet-spin var(--duration-enter) linear infinite;
}

@keyframes pet-spin {
  to { transform: rotate(360deg); }
}

.pet-error {
  position: fixed;
  bottom: var(--space-2);
  left: 50%;
  transform: translateX(-50%);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--task-red-soft);
  color: var(--lumi-danger);
  font-size: var(--text-xs);
  z-index: var(--z-sticky);
  white-space: nowrap;
  pointer-events: none;
}
</style>
