<script setup lang="ts">
import '@pixi/unsafe-eval'
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Application, Ticker } from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display-mulmotion/cubism4'
import { LUOMINEST_BUILTIN_MODELS, resolveExpression } from '@/config/luominest-models'
import {
  RotateCcw, X, Pin, PinOff
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
const LUMINEST_PET_SUBTITLE_FADE_DELAY = 2000

const canvasRef = ref<HTMLCanvasElement | null>(null)
const isModelReady = ref(false)
const isLoading = ref(false)
const loadError = ref<string | null>(null)
const currentModelName = ref('')
const currentModelId = ref('')
const isControlsVisible = ref(false)
const isAlwaysOnTop = ref(true)
const availableMotions = ref<string[]>([])
const availableExpressions = ref<string[]>([])
const subtitleText = ref('')
const subtitleVisible = ref(false)

let pixiApp: Application | null = null
let currentModel: Live2DModel | null = null
let ipcLoadModelHandler: ((event: any, modelInfo: PetModelInfo) => void) | null = null
let ipcTriggerMotionHandler: ((event: any, group: string, index: number) => void) | null = null
let ipcTriggerExpressionHandler: ((event: any, name: string) => void) | null = null
let ipcLipSyncHandler: ((event: any, value: number) => void) | null = null
let ipcPadEmotionHandler: ((event: any, pad: { pleasure: number; arousal: number; dominance: number }) => void) | null = null
let ipcSetCoreParamHandler: ((event: any, paramId: string, value: number) => void) | null = null
let ipcGetModelCapabilitiesHandler: ((event: any, requestId: string) => void) | null = null
let contextMenuHandler: ((e: MouseEvent) => void) | null = null
let ipcSubtitleHandler: ((event: any, text: string) => void) | null = null
let ipcSubtitleHideHandler: ((event: any) => void) | null = null
let idleTickerCallback: (() => void) | null = null
let idleStartTime = 0
let subtitleFadeTimer: ReturnType<typeof setTimeout> | null = null
let retryCount = 0
let retryTimerId: ReturnType<typeof setTimeout> | null = null
let currentLoadToken = 0
let controlsHideTimer: ReturnType<typeof setTimeout> | null = null
let resizeHandler: (() => void) | null = null
let isDraggingWindow = false
let canvasMouseDownHandler: ((e: MouseEvent) => void) | null = null
let windowMouseMoveHandler: ((e: MouseEvent) => void) | null = null
let windowMouseUpHandler: ((e: MouseEvent) => void) | null = null
let wheelHandler: ((e: WheelEvent) => void) | null = null
let mouseMoveHandler: ((e: MouseEvent) => void) | null = null
let isMouseIgnored = false
let modelOriginalBounds: { width: number; height: number } | null = null
// 鼠标跟踪相关变量
let focusTargetX = 0
let focusTargetY = 0
let focusCurrentX = 0
let focusCurrentY = 0
let focusTickerCallback: (() => void) | null = null
const MAX_RETRIES = 3

const resolveEmotionForCurrentModel = (emotionId: string): string => {
  if (!currentModelId.value) return emotionId
  return resolveExpression(currentModelId.value, emotionId)
}

const clearSubtitleFade = () => {
  if (subtitleFadeTimer !== null) {
    clearTimeout(subtitleFadeTimer)
    subtitleFadeTimer = null
  }
}

const showSubtitle = (text: string) => {
  if (!text.trim()) return
  clearSubtitleFade()
  subtitleText.value = text.trim()
  subtitleVisible.value = true
}

const hideSubtitle = () => {
  clearSubtitleFade()
  subtitleFadeTimer = setTimeout(() => {
    subtitleVisible.value = false
    subtitleFadeTimer = null
  }, LUMINEST_PET_SUBTITLE_FADE_DELAY)
}

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

const setCoreParam = (paramId: string, value: number) => {
  if (!currentModel) return
  try {
    const internalModel = currentModel.internalModel as any
    const coreModel = internalModel?.coreModel
    if (coreModel && typeof coreModel.setParameterValueById === 'function') {
      coreModel.setParameterValueById(paramId, value)
    }
  } catch {
    // intentionally ignored
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
    // intentionally ignored
  }
  availableMotions.value = motions
  availableExpressions.value = expressions
}

const hideWatermark = (model: Live2DModel) => {
  try {
    const internalModel = model.internalModel as any
    if (!internalModel?.coreModel) return
    const coreModel = internalModel.coreModel

    const param14Idx = coreModel.getParameterIndex('Param14')
    if (param14Idx >= 0) {
      coreModel.setParameterValueByIndex(param14Idx, 1)
    }

    const settings = internalModel?.settings
    const displayInfo = settings?.displayInfo
    if (displayInfo?.Parameters) {
      for (const param of displayInfo.Parameters) {
        const rawName = String(param?.Name ?? '')
        const lowerName = rawName.toLowerCase()
        if (rawName.includes('水印') || lowerName.includes('watermark') || lowerName.includes('copyright')) {
          const idx = coreModel.getParameterIndex(param.Id)
          if (idx >= 0) {
            coreModel.setParameterValueByIndex(idx, 1)
          }
        }
      }
    }
  } catch {
    // intentionally ignored
  }
}

const cleanupIdle = () => {
  if (idleTickerCallback) {
    Ticker.shared.remove(idleTickerCallback)
    idleTickerCallback = null
  }
}

const setupIdleAnimation = () => {
  cleanupIdle()
  idleStartTime = Date.now()

  idleTickerCallback = () => {
    if (!currentModel) return
    try {
      const internalModel = currentModel.internalModel as any
      const coreModel = internalModel?.coreModel
      if (!coreModel) return

      const param14Idx = coreModel.getParameterIndex('Param14')
      if (param14Idx >= 0) {
        coreModel.setParameterValueByIndex(param14Idx, 1)
      }

      const t = (Date.now() - idleStartTime) / 1000
      const bodyXIdx = coreModel.getParameterIndex('ParamBodyAngleX')
      const bodyYIdx = coreModel.getParameterIndex('ParamBodyAngleY')
      const bodyZIdx = coreModel.getParameterIndex('ParamBodyAngleZ')

      if (bodyXIdx >= 0) {
        coreModel.setParameterValueByIndex(bodyXIdx, Math.sin(t * 0.6) * 3 + Math.sin(t * 1.2) * 0.8)
      }
      if (bodyYIdx >= 0) {
        coreModel.setParameterValueByIndex(bodyYIdx, Math.sin(t * 0.4 + 1.5) * 2.5)
      }
      if (bodyZIdx >= 0) {
        coreModel.setParameterValueByIndex(bodyZIdx, Math.sin(t * 0.5 + 3) * 2)
      }
    } catch {
      // intentionally ignored
    }
  }

  Ticker.shared.add(idleTickerCallback)
}

const MODEL_FIT_PADDING = 16

const fitModelToWindow = (model: Live2DModel) => {
  // Ensure the renderer matches the current window size; this also seems to
  // help Live2DModel's anchor/pivot take effect during initial load.
  if (pixiApp) {
    pixiApp.renderer.resize(window.innerWidth, window.innerHeight)
  }
  // Reset to original size, force transform update, render once, then measure.
  model.scale.set(1)
  model.updateTransform()
  pixiApp?.render()
  const bounds = model.getLocalBounds()
  if (bounds.width > 0 && bounds.height > 0) {
    modelOriginalBounds = { width: bounds.width, height: bounds.height }
    const targetWidth = Math.max(1, window.innerWidth - MODEL_FIT_PADDING * 2)
    const targetHeight = Math.max(1, window.innerHeight - MODEL_FIT_PADDING * 2)
    const scale = Math.min(targetWidth / bounds.width, targetHeight / bounds.height)
    model.scale.set(scale)
    // Use the model's anchor to center it. If the anchor is not respected
    // immediately, the delayed verification below will correct it.
    model.x = window.innerWidth / 2
    model.y = window.innerHeight / 2
    // Verify after a short delay and correct if the rendered bounds are off.
    window.setTimeout(() => {
      if (!pixiApp || !currentModel) return
      pixiApp.render()
      const gb = currentModel.getBounds()
      if (
        gb.x < 0 ||
        gb.y < 0 ||
        gb.x + gb.width > window.innerWidth ||
        gb.y + gb.height > window.innerHeight
      ) {
        currentModel.x += (window.innerWidth - gb.width) / 2 - gb.x
        currentModel.y += (window.innerHeight - gb.height) / 2 - gb.y
      }
    }, 150)
  }
}

const loadModel = async (url: string, _scale: number) => {
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
        preserveDrawingBuffer: true,
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

    cleanupIdle()

    console.info('[LuomiNestDesktopPet] Loading model:', url)
    const model = await Live2DModel.from(url, {
      autoHitTest: true,
      autoFocus: false,
      ticker: Ticker.shared
    })

    if (loadToken !== currentLoadToken) {
      model.destroy()
      return
    }

    model.anchor.set(0.5, 0.5)
    // Position the model before fitting; scale will be set by fitModelToWindow.
    model.x = window.innerWidth / 2
    model.y = window.innerHeight / 2

    model.on('hit', (hitAreas: string[]) => {
      if (hitAreas.includes('body') || hitAreas.includes('head')) {
        model.motion('TapBody', 0)
      }
    })

    pixiApp.stage.addChild(model)
    currentModel = model

    // Fit the model once after loading so it is fully visible from the start.
    fitModelToWindow(model)

    hideWatermark(model)
    setupIdleAnimation()
    setupWheelZoom(model)
    setupMousePassthrough()
    setupFocusTracking()

    isModelReady.value = true
    retryCount = 0

    scanModelCapabilities(model)

    try {
      await model.motion('Idle', 0)
    } catch {
      // intentionally ignored
    }
    hideWatermark(model)

    console.info('[LuomiNestDesktopPet] Model loaded:', url)
  } catch (err) {
    if (loadToken !== currentLoadToken) return

    const message = err instanceof Error ? err.message : 'Failed to load model'
    loadError.value = message
    console.error('[LuomiNestDesktopPet] Model load error:', message)

    if (retryCount < MAX_RETRIES) {
      retryCount++
      console.info(`[LuomiNestDesktopPet] Retrying (${retryCount}/${MAX_RETRIES})...`)
      retryTimerId = setTimeout(() => {
        retryTimerId = null
        if (loadToken !== currentLoadToken) return
        loadModel(url, _scale)
      }, 1000 * retryCount)
    }
  } finally {
    if (loadToken === currentLoadToken) {
      isLoading.value = false
    }
  }
}

const showControls = () => {
  isControlsVisible.value = true
  if (controlsHideTimer) clearTimeout(controlsHideTimer)
}

const scheduleHideControls = () => {
  if (controlsHideTimer) clearTimeout(controlsHideTimer)
  controlsHideTimer = setTimeout(() => {
    isControlsVisible.value = false
  }, 3000)
}

const handleResetPose = async () => {
  showControls()
  if (currentModel) {
    try {
      await currentModel.motion('Idle', 0)
    } catch {
      // intentionally ignored
    }
    hideWatermark(currentModel)
  }
  scheduleHideControls()
}

const handleToggleAlwaysOnTop = () => {
  showControls()
  isAlwaysOnTop.value = !isAlwaysOnTop.value
  window.electron?.ipcRenderer.send('desktop-pet:set-ignore-mouse-events', !isAlwaysOnTop.value)
  scheduleHideControls()
}

const handleClose = () => {
  window.api.desktopPet.close()
}

const MIN_PET_WIDTH = 280
const MIN_PET_HEIGHT = 400
const MAX_PET_WIDTH = 1200
const MAX_PET_HEIGHT = 1600

const setupWheelZoom = (model: Live2DModel) => {
  if (wheelHandler) {
    window.removeEventListener('wheel', wheelHandler)
  }
  wheelHandler = (e: WheelEvent) => {
    if (!model) return
    e.preventDefault()
    const oldScale = model.scale.x
    const factor = e.deltaY > 0 ? 0.95 : 1.05

    const bounds = modelOriginalBounds
    if (bounds) {
      // Keep window and model in sync: stop scaling once the window hits its
      // minimum or maximum allowed size.
      const minScale = Math.max(
        (MIN_PET_WIDTH - MODEL_FIT_PADDING * 2) / bounds.width,
        (MIN_PET_HEIGHT - MODEL_FIT_PADDING * 2) / bounds.height
      )
      const maxScale = Math.min(
        (MAX_PET_WIDTH - MODEL_FIT_PADDING * 2) / bounds.width,
        (MAX_PET_HEIGHT - MODEL_FIT_PADDING * 2) / bounds.height
      )
      const newScale = Math.max(minScale, Math.min(maxScale, oldScale * factor))
      const newWidth = Math.round(bounds.width * newScale + MODEL_FIT_PADDING * 2)
      const newHeight = Math.round(bounds.height * newScale + MODEL_FIT_PADDING * 2)
      window.electron?.ipcRenderer.send('desktop-pet:resize-window', newWidth, newHeight)
      model.scale.set(newScale)
    } else {
      const newScale = Math.max(0.05, Math.min(1.5, oldScale * factor))
      model.scale.set(newScale)
    }
  }
  window.addEventListener('wheel', wheelHandler, { passive: false })
}

const updateMousePassthrough = (clientX: number, clientY: number) => {
  if (!currentModel || !pixiApp) return
  try {
    // Render once so bounds reflect the latest pose/scale before hit testing.
    pixiApp.render()
    const bounds = currentModel.getBounds()
    const isOverModel =
      clientX >= bounds.x &&
      clientX <= bounds.x + bounds.width &&
      clientY >= bounds.y &&
      clientY <= bounds.y + bounds.height
    const shouldIgnore = !isOverModel
    if (shouldIgnore !== isMouseIgnored) {
      isMouseIgnored = shouldIgnore
      window.electron?.ipcRenderer.send('desktop-pet:set-ignore-mouse-events', shouldIgnore)
    }
  } catch {
    // If bounds/hit-test fails, keep mouse events enabled to stay interactive.
  }
}

const setupMousePassthrough = () => {
  if (mouseMoveHandler) return
  mouseMoveHandler = (e: MouseEvent) => {
    if (isDraggingWindow) return
    updateMousePassthrough(e.clientX, e.clientY)
    // 鼠标在模型上时，更新跟踪目标（归一化到 [-1, 1]）
    if (!isMouseIgnored && currentModel) {
      const bounds = currentModel.getBounds()
      const centerX = bounds.x + bounds.width / 2
      const centerY = bounds.y + bounds.height / 2
      focusTargetX = Math.max(-1, Math.min(1, (e.clientX - centerX) / (bounds.width / 2)))
      focusTargetY = Math.max(-1, Math.min(1, -((e.clientY - centerY) / (bounds.height / 2))))
    }
  }
  window.addEventListener('mousemove', mouseMoveHandler)
}

/** 鼠标跟踪：头部和眼球跟随鼠标，鼠标离开模型时平滑回归中心 */
const setupFocusTracking = () => {
  if (focusTickerCallback) {
    Ticker.shared.remove(focusTickerCallback)
  }

  const FOCUS_DAMPING = 0.12

  focusTickerCallback = () => {
    if (!currentModel) return

    // 鼠标不在模型上时，回归中心
    if (isMouseIgnored) {
      focusTargetX = 0
      focusTargetY = 0
    }

    // 阻尼平滑插值
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

      // 头部混合：原值 60% + 鼠标 40%（最大 15 度）
      if (angleXParam >= 0) {
        const base = coreModel.getParameterValueByIndex(angleXParam)
        coreModel.setParameterValueByIndex(angleXParam, base * 0.6 + focusCurrentX * 15 * 0.4)
      }
      if (angleYParam >= 0) {
        const base = coreModel.getParameterValueByIndex(angleYParam)
        coreModel.setParameterValueByIndex(angleYParam, base * 0.6 + focusCurrentY * 15 * 0.4)
      }
      // 眼球混合：原值 50% + 鼠标 50%
      if (eyeBallXParam >= 0) {
        const base = coreModel.getParameterValueByIndex(eyeBallXParam)
        coreModel.setParameterValueByIndex(eyeBallXParam, base * 0.5 + focusCurrentX * 0.5)
      }
      if (eyeBallYParam >= 0) {
        const base = coreModel.getParameterValueByIndex(eyeBallYParam)
        coreModel.setParameterValueByIndex(eyeBallYParam, base * 0.5 + focusCurrentY * 0.5)
      }
    } catch {
      // intentionally ignored
    }
  }

  Ticker.shared.add(focusTickerCallback)
}

const setupCanvasDrag = () => {
  if (!canvasRef.value) return
  let lastDragSend = 0

  const onMouseDown = (e: MouseEvent) => {
    if (e.button !== 0) return
    isDraggingWindow = true
    if (isMouseIgnored) {
      isMouseIgnored = false
      window.electron?.ipcRenderer.send('desktop-pet:set-ignore-mouse-events', false)
    }
    window.electron?.ipcRenderer.send('desktop-pet:start-drag', e.screenX, e.screenY)
  }

  const onMouseMove = (e: MouseEvent) => {
    if (!isDraggingWindow) return
    const now = performance.now()
    if (now - lastDragSend < 16) return
    lastDragSend = now
    window.electron?.ipcRenderer.send('desktop-pet:drag-window', e.screenX, e.screenY)
  }

  const onMouseUp = () => {
    if (!isDraggingWindow) return
    isDraggingWindow = false
    window.electron?.ipcRenderer.send('desktop-pet:end-drag')
  }

  canvasMouseDownHandler = onMouseDown
  windowMouseMoveHandler = onMouseMove
  windowMouseUpHandler = onMouseUp

  canvasRef.value.addEventListener('mousedown', onMouseDown)
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

const setupIpc = () => {
  ipcLoadModelHandler = async (_event: any, modelInfo: PetModelInfo) => {
    currentModelName.value = modelInfo.name
    currentModelId.value = modelInfo.id
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
        // intentionally ignored
      }
    }
  }
  window.electron?.ipcRenderer.on('desktop-pet:trigger-motion', ipcTriggerMotionHandler)

  ipcTriggerExpressionHandler = async (_event: any, name: string) => {
    if (currentModel) {
      const resolved = resolveEmotionForCurrentModel(name)
      try {
        await currentModel.expression(resolved)
      } catch {
        // intentionally ignored
      }
    }
  }
  window.electron?.ipcRenderer.on('desktop-pet:trigger-expression', ipcTriggerExpressionHandler)

  ipcLipSyncHandler = (_event: any, value: number) => {
    const clamped = Math.max(0, Math.min(1, value))
    setCoreParam('ParamMouthOpenY', clamped)
  }
  window.electron?.ipcRenderer.on('desktop-pet:lip-sync', ipcLipSyncHandler)

  ipcPadEmotionHandler = (_event: any, pad: { pleasure: number; arousal: number; dominance: number }) => {
    const emotionId = mapPADtoEmotion(pad.pleasure, pad.arousal, pad.dominance)
    if (currentModel) {
      const resolved = resolveEmotionForCurrentModel(emotionId)
      try {
        currentModel.expression(resolved)
      } catch {
        // intentionally ignored
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

  ipcSubtitleHandler = (_event: any, text: string) => {
    showSubtitle(text)
  }
  window.electron?.ipcRenderer.on('desktop-pet:subtitle', ipcSubtitleHandler)

  ipcSubtitleHideHandler = () => {
    hideSubtitle()
  }
  window.electron?.ipcRenderer.on('desktop-pet:subtitle-hide', ipcSubtitleHideHandler)
}

const cleanupIpc = () => {
  const handlers = [
    { name: 'desktop-pet:load-model', ref: ipcLoadModelHandler, setter: (v: any) => { ipcLoadModelHandler = v } },
    { name: 'desktop-pet:trigger-motion', ref: ipcTriggerMotionHandler, setter: (v: any) => { ipcTriggerMotionHandler = v } },
    { name: 'desktop-pet:trigger-expression', ref: ipcTriggerExpressionHandler, setter: (v: any) => { ipcTriggerExpressionHandler = v } },
    { name: 'desktop-pet:lip-sync', ref: ipcLipSyncHandler, setter: (v: any) => { ipcLipSyncHandler = v } },
    { name: 'desktop-pet:pad-emotion', ref: ipcPadEmotionHandler, setter: (v: any) => { ipcPadEmotionHandler = v } },
    { name: 'desktop-pet:set-core-param', ref: ipcSetCoreParamHandler, setter: (v: any) => { ipcSetCoreParamHandler = v } },
    { name: 'desktop-pet:get-model-capabilities', ref: ipcGetModelCapabilitiesHandler, setter: (v: any) => { ipcGetModelCapabilitiesHandler = v } },
    { name: 'desktop-pet:subtitle', ref: ipcSubtitleHandler, setter: (v: any) => { ipcSubtitleHandler = v } },
    { name: 'desktop-pet:subtitle-hide', ref: ipcSubtitleHideHandler, setter: (v: any) => { ipcSubtitleHideHandler = v } }
  ]

  for (const h of handlers) {
    if (h.ref) {
      window.electron?.ipcRenderer.removeListener(h.name, h.ref)
      h.setter(null)
    }
  }
}

onMounted(async () => {
  await nextTick()

  const modelInfoStr = new URLSearchParams(window.location.hash.split('?')[1] || '').get('model')
  let modelToLoad: PetModelInfo | null = null

  if (modelInfoStr) {
    try {
      modelToLoad = JSON.parse(decodeURIComponent(modelInfoStr))
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

  contextMenuHandler = (e: MouseEvent) => {
    e.preventDefault()
    window.electron?.ipcRenderer.send('desktop-pet:show-context-menu')
  }
  window.addEventListener('contextmenu', contextMenuHandler)

  resizeHandler = () => {
    if (pixiApp) {
      pixiApp.renderer.resize(window.innerWidth, window.innerHeight)
    }
    if (currentModel) {
      // Keep the current scale and re-center the model after the window resizes.
      currentModel.x = window.innerWidth / 2
      currentModel.y = window.innerHeight / 2
    }
  }
  window.addEventListener('resize', resizeHandler)

  if (canvasRef.value) {
    await loadModel(modelToLoad.url, modelToLoad.scale)
  }

  setupCanvasDrag()
})

onBeforeUnmount(() => {
  if (retryTimerId !== null) {
    clearTimeout(retryTimerId)
    retryTimerId = null
  }
  currentLoadToken++
  if (controlsHideTimer) clearTimeout(controlsHideTimer)
  clearSubtitleFade()
  cleanupIdle()
  cleanupIpc()

  if (contextMenuHandler) {
    window.removeEventListener('contextmenu', contextMenuHandler)
    contextMenuHandler = null
  }

  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
    resizeHandler = null
  }

  if (canvasRef.value && canvasMouseDownHandler) {
    canvasRef.value.removeEventListener('mousedown', canvasMouseDownHandler)
    canvasMouseDownHandler = null
  }
  if (windowMouseMoveHandler) {
    window.removeEventListener('mousemove', windowMouseMoveHandler)
    windowMouseMoveHandler = null
  }
  if (windowMouseUpHandler) {
    window.removeEventListener('mouseup', windowMouseUpHandler)
    windowMouseUpHandler = null
  }

  if (wheelHandler) {
    window.removeEventListener('wheel', wheelHandler)
    wheelHandler = null
  }

  if (mouseMoveHandler) {
    window.removeEventListener('mousemove', mouseMoveHandler)
    mouseMoveHandler = null
  }

  if (focusTickerCallback) {
    Ticker.shared.remove(focusTickerCallback)
    focusTickerCallback = null
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

    <Transition name="pet-subtitle-fade">
      <div
        v-if="subtitleVisible && subtitleText"
        class="pet-subtitle-overlay"
      >
        <span class="pet-subtitle-text">{{ subtitleText }}</span>
      </div>
    </Transition>

    <div
      class="controls-anchor"
      @mouseenter="showControls"
      @mouseleave="scheduleHideControls"
    >
      <Transition name="controls-fade">
        <div v-if="isControlsVisible" class="controls-panel">
          <button class="control-btn" title="Reset Pose" @click="handleResetPose">
            <RotateCcw :size="16" />
          </button>
          <button
            class="control-btn"
            :class="{ active: isAlwaysOnTop }"
            :title="isAlwaysOnTop ? 'Unpin' : 'Pin on Top'"
            @click="handleToggleAlwaysOnTop"
          >
            <component :is="isAlwaysOnTop ? Pin : PinOff" :size="16" />
          </button>
          <button class="control-btn danger" title="Close Pet" @click="handleClose">
            <X :size="16" />
          </button>
        </div>
      </Transition>
    </div>
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
  z-index: 1;
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
  z-index: 10;
  pointer-events: none;
}

.pet-loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--lumi-primary-border);
  border-top-color: var(--lumi-primary);
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
  background: var(--task-red-soft);
  color: var(--lumi-danger);
  font-size: 11px;
  z-index: 10;
  white-space: nowrap;
  pointer-events: none;
}

.pet-subtitle-overlay {
  position: fixed;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 50;
  max-width: 90%;
  padding: 6px 14px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--surface) 85%, transparent);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow: 0 2px 10px var(--shadow-color);
  pointer-events: none;
}

.pet-subtitle-text {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text);
  text-align: center;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.pet-subtitle-fade-enter-active {
  transition: opacity 250ms ease-in-out, transform 250ms ease-in-out;
}

.pet-subtitle-fade-leave-active {
  transition: opacity 600ms ease-in-out, transform 600ms ease-in-out;
}

.pet-subtitle-fade-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(6px);
}

.pet-subtitle-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(0);
}

.controls-anchor {
  position: fixed;
  bottom: 0;
  right: 0;
  width: 80px;
  height: 80px;
  z-index: 100;
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  padding: 12px;
  /* Allow clicking the controls instead of starting a window drag. */
  -webkit-app-region: no-drag;
}

.controls-panel {
  display: flex;
  gap: 8px;
  padding: 8px;
  border-radius: 14px;
  background: var(--overlay-bg);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-lg);
}

.control-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid var(--border-light);
  background: color-mix(in srgb, var(--surface) 8%, transparent);
  color: var(--text-inverse);
  cursor: pointer;
  transition: all 200ms ease-in-out;
}

.control-btn:hover {
  background: color-mix(in srgb, var(--surface) 14%, transparent);
  transform: scale(1.05);
}

.control-btn.active {
  background: var(--lumi-primary-border);
  border-color: var(--lumi-primary-border);
  color: var(--lumi-primary);
}

.control-btn.danger:hover {
  background: var(--task-red-border);
  border-color: var(--task-red-border);
  color: var(--lumi-danger);
}

.controls-fade-enter-active {
  transition: opacity 200ms ease-in-out, transform 200ms ease-in-out;
}

.controls-fade-leave-active {
  transition: opacity 150ms ease-in-out, transform 150ms ease-in-out;
}

.controls-fade-enter-from,
.controls-fade-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.95);
}
</style>
