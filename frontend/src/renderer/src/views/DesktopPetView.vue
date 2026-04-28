﻿﻿﻿<script setup lang="ts">
import '@pixi/unsafe-eval'
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Application, Ticker } from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display-mulmotion/cubism4'
import { LUOMINEST_BUILTIN_MODELS } from '@/config/luominest-models'
import {
  Settings2, RotateCcw, Eye, EyeOff, X,
  ChevronUp, Minimize, Pin, PinOff, ArrowLeftRight
} from 'lucide-vue-next'

interface PetModelInfo {
  id: string
  name: string
  url: string
  scale: number
  type: string
  tags: string[]
}

const EXPRESSION_BLOCKLIST = ['水印', 'watermark', 'copyright', 'credit', 'logo']

const canvasRef = ref<HTMLCanvasElement | null>(null)
const isModelReady = ref(false)
const isLoading = ref(false)
const loadError = ref<string | null>(null)
const currentModelName = ref('')
const isIslandExpanded = ref(false)
const isAlwaysOnTop = ref(true)
const isMousePassthrough = ref(true)
const availableMotions = ref<string[]>([])
const availableExpressions = ref<string[]>([])

let pixiApp: Application | null = null
let currentModel: Live2DModel | null = null
let isDragging = false
let dragOffset = { x: 0, y: 0 }
let islandHideTimer: ReturnType<typeof setTimeout> | null = null
let wheelHandler: ((e: WheelEvent) => void) | null = null
let focusTargetX = 0
let focusTargetY = 0
let focusCurrentX = 0
let focusCurrentY = 0
let focusTickerCallback: (() => void) | null = null
let focusMouseMoveHandler: ((e: MouseEvent) => void) | null = null
let focusMouseLeaveHandler: (() => void) | null = null
let ipcLoadModelHandler: ((event: any, modelInfo: PetModelInfo) => void) | null = null
let ipcTriggerMotionHandler: ((event: any, group: string, index: number) => void) | null = null
let ipcTriggerExpressionHandler: ((event: any, name: string) => void) | null = null
let ipcSetPositionHandler: ((event: any, x: number, y: number) => void) | null = null
let ipcSetScaleHandler: ((event: any, scale: number) => void) | null = null
let ipcLipSyncHandler: ((event: any, value: number) => void) | null = null
let ipcPadEmotionHandler: ((event: any, pad: { pleasure: number; arousal: number; dominance: number }) => void) | null = null
let ipcSetCoreParamHandler: ((event: any, paramId: string, value: number) => void) | null = null
let ipcGetModelCapabilitiesHandler: ((event: any, requestId: string) => void) | null = null
let contextMenuHandler: ((e: MouseEvent) => void) | null = null
let retryCount = 0
let retryTimerId: ReturnType<typeof setTimeout> | null = null
let currentLoadToken = 0
const MAX_RETRIES = 3

const mapPADtoEmotion = (pleasure: number, arousal: number, dominance: number): string => {
  if (pleasure > 0.3 && arousal > 0.5) return 'happy'
  if (pleasure < -0.3 && arousal > 0.3) return 'angry'
  if (pleasure < -0.3 && arousal <= 0.3) return 'sad'
  if (arousal > 0.5 && dominance < -0.2) return 'surprise'
  if (pleasure > 0.3 && arousal < -0.2) return 'love'
  if (pleasure > 0.1 && pleasure <= 0.3 && arousal < -0.1) return 'love'
  if (pleasure < -0.1 && arousal > -0.1 && arousal < 0.2) return 'awkward'
  if (arousal > 0.2 && arousal <= 0.5 && pleasure > -0.1) return 'curious'
  if (pleasure > -0.1 && arousal < -0.2) return 'think'
  return 'neutral'
}

const cleanupFocus = () => {
  if (focusTickerCallback) {
    Ticker.shared.remove(focusTickerCallback)
    focusTickerCallback = null
  }
  if (focusMouseMoveHandler) {
    window.removeEventListener('mousemove', focusMouseMoveHandler)
    focusMouseMoveHandler = null
  }
  if (focusMouseLeaveHandler) {
    window.removeEventListener('mouseleave', focusMouseLeaveHandler)
    focusMouseLeaveHandler = null
  }
}

const setIgnoreMouseEvents = (ignore: boolean) => {
  isMousePassthrough.value = ignore
  window.electron?.ipcRenderer.send('desktop-pet:set-ignore-mouse-events', ignore)
}

const setCoreParam = (paramId: string, value: number) => {
  if (!currentModel) return
  try {
    const internalModel = currentModel.internalModel
    if (internalModel && 'coreModel' in internalModel) {
      const coreModel = (internalModel as any).coreModel
      if (coreModel && typeof coreModel.setParameterValueById === 'function') {
        coreModel.setParameterValueById(paramId, value)
      }
    }
  } catch {
  }
}

const scanModelCapabilities = (model: Live2DModel) => {
  const motions: string[] = []
  const expressions: string[] = []
  try {
    const internalModel = model.internalModel as any
    const settings = internalModel?.settings
    if (settings?.motions) {
      for (const group of Object.keys(settings.motions)) {
        motions.push(group)
      }
    }
    if (settings?.expressions) {
      for (const exp of settings.expressions) {
        const name = exp?.Name ?? ''
        const isBlocked = EXPRESSION_BLOCKLIST.some(
          blocked => name.toLowerCase().includes(blocked.toLowerCase())
        )
        if (name && !isBlocked) expressions.push(name)
      }
    }
  } catch {
  }
  availableMotions.value = motions
  availableExpressions.value = expressions
}

const loadModel = async (url: string, scale: number) => {
  if (retryTimerId !== null) {
    clearTimeout(retryTimerId)
    retryTimerId = null
  }
  currentLoadToken++
  const loadToken = currentLoadToken

  isLoading.value = true
  loadError.value = null
  isModelReady.value = false

  try {
    if (!pixiApp && canvasRef.value) {
      pixiApp = new Application({
        view: canvasRef.value,
        autoStart: true,
        backgroundAlpha: 0,
        antialias: true,
        resizeTo: window,
        resolution: Math.min(window.devicePixelRatio || 1, 2),
        autoDensity: true
      } as any)
    }

    if (!pixiApp) {
      throw new Error('Failed to initialize PixiJS application')
    }

    if (loadToken !== currentLoadToken) return

    if (currentModel) {
      pixiApp.stage.removeChild(currentModel)
      currentModel.destroy()
      currentModel = null
    }

    cleanupFocus()

    const model = await Live2DModel.from(url, {
      autoHitTest: true,
      autoFocus: false,
      ticker: Ticker.shared
    })

    if (loadToken !== currentLoadToken) {
      model.destroy()
      return
    }

    const clampedScale = Math.max(0.05, Math.min(2.0, scale))
    model.scale.set(clampedScale)
    model.anchor.set(0.5, 0.5)
    model.x = window.innerWidth * 0.75
    model.y = window.innerHeight * 0.55

    try {
      const internalModel = model.internalModel as any
      if (internalModel?.coreModel) {
        const coreModel = internalModel.coreModel
        const param14Idx = coreModel.getParameterIndex('Param14')
        if (param14Idx >= 0) {
          coreModel.setParameterValueByIndex(param14Idx, 0)
        }
      }
    } catch {
    }

    model.on('hit', (hitAreas: string[]) => {
      if (hitAreas.includes('body') || hitAreas.includes('head')) {
        model.motion('TapBody', 0)
      }
    })

    model.on('pointerover', () => {
      setIgnoreMouseEvents(false)
    })

    model.on('pointerout', () => {
      if (!isDragging) {
        setIgnoreMouseEvents(true)
      }
    })

    setupDrag(model)
    setupWheel(model)
    setupFocus(model)

    pixiApp.stage.addChild(model)
    currentModel = model
    isModelReady.value = true
    retryCount = 0

    scanModelCapabilities(model)

    try {
      await model.motion('Idle', 0)
    } catch {
    }

    console.info('[INFO][LuomiNestDesktopPet] Model loaded successfully:', url)
  } catch (err) {
    if (loadToken !== currentLoadToken) return

    const message = err instanceof Error ? err.message : 'Failed to load model'
    loadError.value = message
    console.error('[ERROR][LuomiNestDesktopPet] Model load error:', message)

    if (retryCount < MAX_RETRIES) {
      retryCount++
      console.info(`[INFO][LuomiNestDesktopPet] Retrying (${retryCount}/${MAX_RETRIES})...`)
      retryTimerId = setTimeout(async () => {
        retryTimerId = null
        if (loadToken !== currentLoadToken) return
        await loadModel(url, scale)
      }, 1000 * retryCount)
    }
  } finally {
    if (loadToken === currentLoadToken) {
      isLoading.value = false
    }
  }
}

const setupDrag = (model: Live2DModel) => {
  model.interactive = true

  model.on('pointerdown', (e: any) => {
    if (e.data.button !== 0) return
    isDragging = true
    dragOffset.x = e.data.global.x - model.x
    dragOffset.y = e.data.global.y - model.y
    setIgnoreMouseEvents(false)
  })

  model.on('pointermove', (e: any) => {
    if (!isDragging) return
    model.x = e.data.global.x - dragOffset.x
    model.y = e.data.global.y - dragOffset.y
  })

  const endDrag = () => {
    if (!isDragging) return
    isDragging = false
    setTimeout(() => {
      if (currentModel && !isDragging) {
        setIgnoreMouseEvents(true)
      }
    }, 100)
  }

  model.on('pointerup', endDrag)
  model.on('pointerupoutside', endDrag)
}

const setupWheel = (model: Live2DModel) => {
  if (wheelHandler) {
    window.removeEventListener('wheel', wheelHandler)
  }
  wheelHandler = (e: WheelEvent) => {
    if (!model) return
    e.preventDefault()
    const scaleFactor = e.deltaY > 0 ? 0.95 : 1.05
    const newScale = Math.max(0.05, Math.min(3.0, model.scale.x * scaleFactor))
    model.scale.set(newScale)
  }
  window.addEventListener('wheel', wheelHandler, { passive: false })
}

const setupFocus = (_model: Live2DModel) => {
  cleanupFocus()

  const FOCUS_DAMPING = 0.15

  const onMouseMove = (e: MouseEvent) => {
    focusTargetX = (e.clientX / window.innerWidth) * 2 - 1
    focusTargetY = -((e.clientY / window.innerHeight) * 2 - 1)
  }

  const onMouseLeave = () => {
    focusTargetX = 0
    focusTargetY = 0
  }

  focusMouseMoveHandler = onMouseMove
  focusMouseLeaveHandler = onMouseLeave

  focusTickerCallback = () => {
    if (!currentModel) return
    focusCurrentX += (focusTargetX - focusCurrentX) * FOCUS_DAMPING
    focusCurrentY += (focusTargetY - focusCurrentY) * FOCUS_DAMPING

    try {
      const internalModel = currentModel.internalModel as any
      const coreModel = internalModel?.coreModel
      if (!coreModel) return

      const angleXParam = coreModel.getParameterIndex('ParamAngleX')
      const angleYParam = coreModel.getParameterIndex('ParamAngleY')
      const eyeBallXParam = coreModel.getParameterIndex('ParamEyeBallX')
      const eyeBallYParam = coreModel.getParameterIndex('ParamEyeBallY')

      if (angleXParam >= 0) {
        const base = coreModel.getParameterValueByIndex(angleXParam)
        coreModel.setParameterValueByIndex(angleXParam, base * 0.6 + focusCurrentX * 15 * 0.4)
      }
      if (angleYParam >= 0) {
        const base = coreModel.getParameterValueByIndex(angleYParam)
        coreModel.setParameterValueByIndex(angleYParam, base * 0.6 + focusCurrentY * 15 * 0.4)
      }
      if (eyeBallXParam >= 0) {
        const base = coreModel.getParameterValueByIndex(eyeBallXParam)
        coreModel.setParameterValueByIndex(eyeBallXParam, base * 0.5 + focusCurrentX * 0.5)
      }
      if (eyeBallYParam >= 0) {
        const base = coreModel.getParameterValueByIndex(eyeBallYParam)
        coreModel.setParameterValueByIndex(eyeBallYParam, base * 0.5 + focusCurrentY * 0.5)
      }
    } catch {
    }
  }

  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseleave', onMouseLeave)
  Ticker.shared.add(focusTickerCallback)
}

const toggleIsland = () => {
  isIslandExpanded.value = !isIslandExpanded.value
  if (isIslandExpanded.value) {
    setIgnoreMouseEvents(false)
    resetIslandTimer()
  }
}

const resetIslandTimer = () => {
  if (islandHideTimer) clearTimeout(islandHideTimer)
  if (isIslandExpanded.value) {
    islandHideTimer = setTimeout(() => {
      isIslandExpanded.value = false
    }, 4000)
  }
}

const handleIslandMouseEnter = () => {
  if (islandHideTimer) clearTimeout(islandHideTimer)
  setIgnoreMouseEvents(false)
}

const handleIslandMouseLeave = () => {
  resetIslandTimer()
  setTimeout(() => {
    if (!isDragging) {
      setIgnoreMouseEvents(true)
    }
  }, 200)
}

const handleResetPose = async () => {
  if (currentModel) {
    try {
      await currentModel.motion('Idle', 0)
    } catch {
    }
  }
  resetIslandTimer()
}

const handleToggleAlwaysOnTop = () => {
  isAlwaysOnTop.value = !isAlwaysOnTop.value
  resetIslandTimer()
}

const handleClose = () => {
  window.api.desktopPet.close()
}

onMounted(async () => {
  await nextTick()

  const modelInfoStr = new URLSearchParams(window.location.hash.split('?')[1] || '').get('model')
  let modelToLoad: PetModelInfo | null = null

  if (modelInfoStr) {
    try {
      modelToLoad = JSON.parse(decodeURIComponent(modelInfoStr))
    } catch {
    }
  }

  if (!modelToLoad) {
    const builtin = LUOMINEST_BUILTIN_MODELS[0]
    modelToLoad = { id: builtin.id, name: builtin.name, url: builtin.url, scale: builtin.scale, type: builtin.type, tags: builtin.tags }
  }

  currentModelName.value = modelToLoad.name

  if (canvasRef.value) {
    await loadModel(modelToLoad.url, modelToLoad.scale)
  }

  ipcLoadModelHandler = async (_event: any, modelInfo: PetModelInfo) => {
    currentModelName.value = modelInfo.name
    retryCount = 0
    if (canvasRef.value) {
      await loadModel(modelInfo.url, modelInfo.scale)
    }
  }
  window.electron?.ipcRenderer.on('desktop-pet:load-model', ipcLoadModelHandler)

  ipcTriggerMotionHandler = async (_event: any, group: string, index: number) => {
    if (currentModel) {
      try {
        await currentModel.motion(group, index)
      } catch {
      }
    }
  }
  window.electron?.ipcRenderer.on('desktop-pet:trigger-motion', ipcTriggerMotionHandler)

  ipcTriggerExpressionHandler = async (_event: any, name: string) => {
    if (currentModel) {
      try {
        await currentModel.expression(name)
      } catch {
      }
    }
  }
  window.electron?.ipcRenderer.on('desktop-pet:trigger-expression', ipcTriggerExpressionHandler)

  ipcSetPositionHandler = (_event: any, x: number, y: number) => {
    if (currentModel) {
      currentModel.x = x
      currentModel.y = y
    }
  }
  window.electron?.ipcRenderer.on('desktop-pet:set-position', ipcSetPositionHandler)

  ipcSetScaleHandler = (_event: any, scale: number) => {
    if (currentModel) {
      const clamped = Math.max(0.05, Math.min(3.0, scale))
      currentModel.scale.set(clamped)
    }
  }
  window.electron?.ipcRenderer.on('desktop-pet:set-scale', ipcSetScaleHandler)

  ipcLipSyncHandler = (_event: any, value: number) => {
    const clamped = Math.max(0, Math.min(1, value))
    setCoreParam('ParamMouthOpenY', clamped)
  }
  window.electron?.ipcRenderer.on('desktop-pet:lip-sync', ipcLipSyncHandler)

  ipcPadEmotionHandler = (_event: any, pad: { pleasure: number; arousal: number; dominance: number }) => {
    const emotionId = mapPADtoEmotion(pad.pleasure, pad.arousal, pad.dominance)
    if (currentModel) {
      try {
        currentModel.expression(emotionId)
      } catch {
      }
    }
  }
  window.electron?.ipcRenderer.on('desktop-pet:pad-emotion', ipcPadEmotionHandler)

  ipcSetCoreParamHandler = (_event: any, paramId: string, value: number) => {
    setCoreParam(paramId, value)
  }
  window.electron?.ipcRenderer.on('desktop-pet:set-core-param', ipcSetCoreParamHandler)

  ipcGetModelCapabilitiesHandler = (_event: any, requestId: string) => {
    window.electron?.ipcRenderer.send(
      'desktop-pet:model-capabilities-response',
      requestId,
      {
        motions: availableMotions.value,
        expressions: availableExpressions.value,
        modelName: currentModelName.value,
        isReady: isModelReady.value
      }
    )
  }
  window.electron?.ipcRenderer.on('desktop-pet:get-model-capabilities', ipcGetModelCapabilitiesHandler)

  contextMenuHandler = (e: MouseEvent) => {
    e.preventDefault()
    setIgnoreMouseEvents(false)
    window.electron?.ipcRenderer.send('desktop-pet:show-context-menu')
    setTimeout(() => setIgnoreMouseEvents(true), 1000)
  }
  window.addEventListener('contextmenu', contextMenuHandler)
})

onBeforeUnmount(() => {
  if (retryTimerId !== null) {
    clearTimeout(retryTimerId)
    retryTimerId = null
  }
  currentLoadToken++
  if (islandHideTimer) clearTimeout(islandHideTimer)
  cleanupFocus()

  if (ipcLoadModelHandler) {
    window.electron?.ipcRenderer.removeListener('desktop-pet:load-model', ipcLoadModelHandler)
    ipcLoadModelHandler = null
  }
  if (ipcTriggerMotionHandler) {
    window.electron?.ipcRenderer.removeListener('desktop-pet:trigger-motion', ipcTriggerMotionHandler)
    ipcTriggerMotionHandler = null
  }
  if (ipcTriggerExpressionHandler) {
    window.electron?.ipcRenderer.removeListener('desktop-pet:trigger-expression', ipcTriggerExpressionHandler)
    ipcTriggerExpressionHandler = null
  }
  if (ipcSetPositionHandler) {
    window.electron?.ipcRenderer.removeListener('desktop-pet:set-position', ipcSetPositionHandler)
    ipcSetPositionHandler = null
  }
  if (ipcSetScaleHandler) {
    window.electron?.ipcRenderer.removeListener('desktop-pet:set-scale', ipcSetScaleHandler)
    ipcSetScaleHandler = null
  }
  if (ipcLipSyncHandler) {
    window.electron?.ipcRenderer.removeListener('desktop-pet:lip-sync', ipcLipSyncHandler)
    ipcLipSyncHandler = null
  }
  if (ipcPadEmotionHandler) {
    window.electron?.ipcRenderer.removeListener('desktop-pet:pad-emotion', ipcPadEmotionHandler)
    ipcPadEmotionHandler = null
  }
  if (ipcSetCoreParamHandler) {
    window.electron?.ipcRenderer.removeListener('desktop-pet:set-core-param', ipcSetCoreParamHandler)
    ipcSetCoreParamHandler = null
  }
  if (ipcGetModelCapabilitiesHandler) {
    window.electron?.ipcRenderer.removeListener('desktop-pet:get-model-capabilities', ipcGetModelCapabilitiesHandler)
    ipcGetModelCapabilitiesHandler = null
  }

  if (contextMenuHandler) {
    window.removeEventListener('contextmenu', contextMenuHandler)
    contextMenuHandler = null
  }

  if (wheelHandler) {
    window.removeEventListener('wheel', wheelHandler)
    wheelHandler = null
  }

  if (currentModel) {
    currentModel.destroy()
    currentModel = null
  }
  if (pixiApp) {
    pixiApp.destroy(true)
    pixiApp = null
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

    <div
      class="controls-island"
      @mouseenter="handleIslandMouseEnter"
      @mouseleave="handleIslandMouseLeave"
    >
      <Transition
        enter-active-class="island-enter-active"
        leave-active-class="island-leave-active"
        enter-from-class="island-enter-from"
        leave-to-class="island-leave-to"
      >
        <div v-if="isIslandExpanded" class="island-panel">
          <div class="island-grid">
            <button class="island-btn" title="Reset Pose" @click="handleResetPose">
              <RotateCcw :size="16" />
            </button>
            <button class="island-btn" title="Switch Model (Coming Soon)" disabled aria-disabled="true">
              <ArrowLeftRight :size="16" />
            </button>
            <button
              class="island-btn"
              :class="{ active: isAlwaysOnTop }"
              :title="isAlwaysOnTop ? 'Unpin' : 'Pin on Top'"
              @click="handleToggleAlwaysOnTop"
            >
              <component :is="isAlwaysOnTop ? Pin : PinOff" :size="16" />
            </button>
            <button class="island-btn" title="Settings">
              <Settings2 :size="16" />
            </button>
            <button
              class="island-btn"
              :class="{ active: !isMousePassthrough }"
              :title="isMousePassthrough ? 'Disable Passthrough' : 'Enable Passthrough'"
              @click="setIgnoreMouseEvents(!isMousePassthrough); resetIslandTimer()"
            >
              <component :is="isMousePassthrough ? EyeOff : Eye" :size="16" />
            </button>
            <button class="island-btn danger" title="Close Pet" @click="handleClose">
              <X :size="16" />
            </button>
          </div>

          <div v-if="currentModelName" class="island-model-name">
            {{ currentModelName }}
          </div>
        </div>
      </Transition>

      <button class="island-toggle" @click="toggleIsland" :title="isIslandExpanded ? 'Collapse' : 'Expand'">
        <component :is="isIslandExpanded ? Minimize : ChevronUp" :size="14" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.desktop-pet-view {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: transparent;
  position: relative;
  -webkit-app-region: no-drag;
  margin: 0;
  padding: 0;
}

.pet-canvas {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
  background: transparent;
}

.pet-loading {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  pointer-events: none;
}

.pet-loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(20, 126, 188, 0.3);
  border-top-color: #147EBC;
  border-radius: 50%;
  animation: pet-spin 0.8s linear infinite;
}

@keyframes pet-spin {
  to { transform: rotate(360deg); }
}

.pet-error {
  position: fixed;
  bottom: 8px;
  left: 50%;
  transform: translateX(-50%);
  padding: 4px 12px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  font-size: 11px;
  z-index: 10;
  white-space: nowrap;
  pointer-events: none;
}

.controls-island {
  position: fixed;
  bottom: 12px;
  right: 12px;
  z-index: 100;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.island-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border-radius: 16px;
  background: rgba(30, 30, 30, 0.75);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.island-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}

.island-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: all 200ms ease-in-out;
}

.island-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.95);
  transform: scale(1.05);
}

.island-btn.active {
  background: rgba(20, 126, 188, 0.2);
  border-color: rgba(20, 126, 188, 0.4);
  color: #147EBC;
}

.island-btn.danger:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.4);
  color: #ef4444;
}

.island-model-name {
  text-align: center;
  font-size: 10px;
  color: rgba(255, 255, 255, 0.4);
  padding-top: 2px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.island-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(30, 30, 30, 0.6);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  transition: all 200ms ease-in-out;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.island-toggle:hover {
  background: rgba(30, 30, 30, 0.8);
  color: rgba(255, 255, 255, 0.9);
  transform: scale(1.1);
}

.island-enter-active {
  transition: all 400ms cubic-bezier(0.32, 0.72, 0, 1);
}
.island-leave-active {
  transition: all 300ms cubic-bezier(0.32, 0.72, 0, 1);
}
.island-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.9);
}
.island-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.95);
}
</style>
