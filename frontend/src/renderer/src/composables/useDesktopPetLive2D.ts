/**
 * LuomiNest 桌面宠物窗口级 Live2D composable
 *
 * 从 DesktopPetView.vue 拆分，负责独立窗口内的 Live2D 模型管理：
 * - PixiJS Application 初始化（WebGL→Canvas 降级）
 * - 模型加载（动态 import cubism4，复用共享 core）
 * - 窗口适配（fitModelToWindow，含 150ms 延迟校验）
 * - 滚轮缩放（同步调整窗口尺寸 via IPC）
 * - 鼠标穿透（IPC set-ignore-mouse-events）
 * - 焦点跟踪（damping 0.12，混合头部/眼球）
 * - Canvas 拖拽（IPC start-drag/drag-window/end-drag）
 *
 * 与 useLuomiNestLive2D（应用内 canvas）的差异：
 * - damping 0.12 vs 0.08（窗口模式手感不同）
 * - 滚轮缩放同步窗口尺寸（而非仅缩放模型）
 * - 鼠标穿透（窗口级 hit test）
 * - 拖拽通过 IPC 移动窗口（而非 canvas 内移动模型）
 */
import '@pixi/unsafe-eval'
import { ref, type Ref } from 'vue'
import { Application, Ticker } from 'pixi.js'
import { resolveExpression } from '@/config/luominest-models'
import { createLuomiNestRendererLogger } from '@/utils/logger'
import {
  loadCubism4Module,
  patchIsInteractive,
  getLuomiNestCoreModel,
  scanLuomiNestModelCapabilities,
  hideLuomiNestWatermark,
  setupLuomiNestIdleAnimation,
  mapLuomiNestPadToEmotion,
  type LuomiNestLive2DModel
} from './live2d/useLuomiNestLive2DCore'

const logger = createLuomiNestRendererLogger('LuomiNestDesktopPet')

const MAX_RETRIES = 3
const MODEL_FIT_PADDING = 16
const MIN_PET_WIDTH = 280
const MIN_PET_HEIGHT = 400
const MAX_PET_WIDTH = 1200
const MAX_PET_HEIGHT = 1600
/** 焦点跟踪阻尼（窗口模式 0.12，比 canvas 模式 0.08 略大，手感更稳） */
const FOCUS_DAMPING = 0.12

/** IPC SEND 通道字面量（类型见 DesktopPetIpcChannels.SEND） */
const IPC_RESIZE_WINDOW = 'desktop-pet:resize-window'
const IPC_SET_IGNORE_MOUSE = 'desktop-pet:set-ignore-mouse-events'
const IPC_START_DRAG = 'desktop-pet:start-drag'
const IPC_DRAG_WINDOW = 'desktop-pet:drag-window'
const IPC_END_DRAG = 'desktop-pet:end-drag'

export const useDesktopPetLive2D = (canvasRef: Ref<HTMLCanvasElement | null>) => {
  const isModelReady = ref(false)
  const isLoading = ref(false)
  const loadError = ref<string | null>(null)
  const currentModelName = ref('')
  const currentModelId = ref('')
  const availableMotions = ref<string[]>([])
  const availableExpressions = ref<string[]>([])

  let pixiApp: Application | null = null
  let currentModel: LuomiNestLive2DModel | null = null
  let retryCount = 0
  let retryTimerId: ReturnType<typeof setTimeout> | null = null
  let currentLoadToken = 0
  let idleCleanup: (() => void) | null = null
  let modelOriginalBounds: { width: number; height: number } | null = null

  // 焦点跟踪 + 鼠标穿透共享状态（必须在同一闭包内）
  let focusTargetX = 0
  let focusTargetY = 0
  let focusCurrentX = 0
  let focusCurrentY = 0
  let focusTickerCallback: (() => void) | null = null
  let isMouseIgnored = false
  let isDraggingWindow = false

  // 事件监听器引用（便于精确移除）
  let wheelHandler: ((e: WheelEvent) => void) | null = null
  let mouseMoveHandler: ((e: MouseEvent) => void) | null = null
  let canvasMouseDownHandler: ((e: MouseEvent) => void) | null = null
  let windowMouseMoveHandler: ((e: MouseEvent) => void) | null = null
  let windowMouseUpHandler: ((e: MouseEvent) => void) | null = null

  const resolveEmotionForCurrentModel = (emotionId: string): string => {
    if (!currentModelId.value) return emotionId
    return resolveExpression(currentModelId.value, emotionId)
  }

  const initPixi = (): Application | null => {
    if (pixiApp) return pixiApp
    if (!canvasRef.value) {
      logger.error('Canvas element not found')
      loadError.value = 'Canvas element not available'
      return null
    }

    const baseConfig = {
      view: canvasRef.value,
      autoStart: true,
      backgroundAlpha: 0,
      antialias: true,
      preserveDrawingBuffer: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
      autoDensity: true
    }

    try {
      pixiApp = new Application({
        ...baseConfig,
        powerPreference: 'high-performance'
      } as Partial<ConstructorParameters<typeof Application>[0]>)
      logger.info('PixiJS initialized successfully (WebGL)')
      return pixiApp
    } catch (webglErr) {
      logger.warn('WebGL init failed, trying canvas fallback:', webglErr instanceof Error ? webglErr.message : webglErr)
      try {
        pixiApp = new Application(baseConfig as Partial<ConstructorParameters<typeof Application>[0]>)
        logger.info('PixiJS initialized successfully (Canvas fallback)')
        return pixiApp
      } catch (canvasErr) {
        const message = canvasErr instanceof Error ? canvasErr.message : 'Unknown error'
        loadError.value = `Graphics initialization failed: ${message}`
        logger.error('Both WebGL and Canvas failed:', message)
        return null
      }
    }
  }

  const fitModelToWindow = (model: LuomiNestLive2DModel): void => {
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

  const loadModel = async (url: string, _scale: number): Promise<void> => {
    if (retryTimerId !== null) {
      clearTimeout(retryTimerId)
      retryTimerId = null
    }
    // 外部调用时重置重试计数（与原 IPC handler 的 retryCount = 0 行为一致）。
    // retry 由 attemptLoad 内部递归调用，不经过此处，避免无限重试。
    retryCount = 0
    currentLoadToken++
    const loadToken = currentLoadToken
    await attemptLoad(url, _scale, loadToken)
  }

  const attemptLoad = async (url: string, _scale: number, loadToken: number): Promise<void> => {
    isLoading.value = true
    loadError.value = null
    isModelReady.value = false

    try {
      const app = initPixi()
      if (!app) {
        throw new Error(loadError.value || 'Failed to initialize PixiJS application')
      }

      if (loadToken !== currentLoadToken) return

      if (currentModel) {
        app.stage.removeChild(currentModel)
        currentModel.destroy()
        currentModel = null
      }

      if (idleCleanup) {
        idleCleanup()
        idleCleanup = null
      }

      logger.info('Loading model:', url)
      const CubismLive2DModel = await loadCubism4Module()
      const model = await CubismLive2DModel.from(url, {
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

      app.stage.addChild(model)
      currentModel = model

      // Fit the model once after loading so it is fully visible from the start.
      fitModelToWindow(model)

      hideLuomiNestWatermark(model)
      idleCleanup = setupLuomiNestIdleAnimation(() => currentModel).cleanup
      setupWindowWheelZoom(model)
      setupMousePassthrough()
      setupWindowFocusTracking()

      patchIsInteractive(model as unknown as Parameters<typeof patchIsInteractive>[0])

      isModelReady.value = true
      retryCount = 0

      const caps = scanLuomiNestModelCapabilities(model)
      availableMotions.value = caps.motions
      availableExpressions.value = caps.expressions

      try {
        await model.motion('Idle', 0)
      } catch {
        // intentionally ignored: expected non-fatal error
      }
      hideLuomiNestWatermark(model)

      logger.info('Model loaded:', url)
    } catch (err) {
      if (loadToken !== currentLoadToken) return

      const message = err instanceof Error ? err.message : 'Failed to load model'
      loadError.value = message
      logger.error('Model load error:', message)

      if (retryCount < MAX_RETRIES) {
        retryCount++
        logger.info(`Retrying (${retryCount}/${MAX_RETRIES})...`)
        retryTimerId = setTimeout(() => {
          retryTimerId = null
          if (loadToken !== currentLoadToken) return
          void attemptLoad(url, _scale, loadToken)
        }, 1000 * retryCount)
      }
    } finally {
      if (loadToken === currentLoadToken) {
        isLoading.value = false
      }
    }
  }

  const setupWindowWheelZoom = (model: LuomiNestLive2DModel): void => {
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
        window.electron?.ipcRenderer.send(IPC_RESIZE_WINDOW, newWidth, newHeight)
        model.scale.set(newScale)
      } else {
        const newScale = Math.max(0.05, Math.min(1.5, oldScale * factor))
        model.scale.set(newScale)
      }
    }
    window.addEventListener('wheel', wheelHandler, { passive: false })
  }

  const updateMousePassthrough = (clientX: number, clientY: number): void => {
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
        window.electron?.ipcRenderer.send(IPC_SET_IGNORE_MOUSE, shouldIgnore)
      }
    } catch {
      // If bounds/hit-test fails, keep mouse events enabled to stay interactive.
    }
  }

  const setupMousePassthrough = (): void => {
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
  const setupWindowFocusTracking = (): void => {
    if (focusTickerCallback) {
      Ticker.shared.remove(focusTickerCallback)
    }

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

      const access = getLuomiNestCoreModel(currentModel)
      if (!access) return

      try {
        const { coreModel } = access
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

  const setupCanvasDrag = (): void => {
    if (!canvasRef.value) return
    let lastDragSend = 0

    const onMouseDown = (e: MouseEvent) => {
      if (e.button !== 0) return
      isDraggingWindow = true
      if (isMouseIgnored) {
        isMouseIgnored = false
        window.electron?.ipcRenderer.send(IPC_SET_IGNORE_MOUSE, false)
      }
      window.electron?.ipcRenderer.send(IPC_START_DRAG, e.screenX, e.screenY)
    }

    const onMouseMove = (e: MouseEvent) => {
      if (!isDraggingWindow) return
      const now = performance.now()
      if (now - lastDragSend < 16) return
      lastDragSend = now
      window.electron?.ipcRenderer.send(IPC_DRAG_WINDOW, e.screenX, e.screenY)
    }

    const onMouseUp = () => {
      if (!isDraggingWindow) return
      isDraggingWindow = false
      window.electron?.ipcRenderer.send(IPC_END_DRAG)
    }

    canvasMouseDownHandler = onMouseDown
    windowMouseMoveHandler = onMouseMove
    windowMouseUpHandler = onMouseUp

    canvasRef.value.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  const setCoreParam = (paramId: string, value: number): void => {
    if (!currentModel) return
    const access = getLuomiNestCoreModel(currentModel)
    if (!access) return
    try {
      access.coreModel.setParameterValueById(paramId, value)
    } catch {
      // intentionally ignored
    }
  }

  const triggerMotion = async (group: string, index: number): Promise<void> => {
    if (!currentModel) return
    try {
      await currentModel.motion(group, index)
    } catch {
      // intentionally ignored
    }
  }

  const triggerExpression = async (emotionId: string): Promise<void> => {
    if (!currentModel) return
    const resolved = resolveEmotionForCurrentModel(emotionId)
    try {
      await currentModel.expression(resolved)
    } catch {
      // intentionally ignored
    }
  }

  const drivePadEmotion = (pleasure: number, arousal: number, dominance: number): void => {
    if (!currentModel) return
    const emotionId = mapLuomiNestPadToEmotion(pleasure, arousal, dominance)
    const resolved = resolveEmotionForCurrentModel(emotionId)
    try {
      currentModel.expression(resolved)
    } catch {
      // intentionally ignored
    }
  }

  const resetPose = async (): Promise<void> => {
    if (!currentModel) return
    try {
      await currentModel.motion('Idle', 0)
    } catch {
      // intentionally ignored
    }
    hideLuomiNestWatermark(currentModel)
  }

  const handleResize = (): void => {
    if (pixiApp) {
      pixiApp.renderer.resize(window.innerWidth, window.innerHeight)
    }
    if (currentModel) {
      // Keep the current scale and re-center the model after the window resizes.
      currentModel.x = window.innerWidth / 2
      currentModel.y = window.innerHeight / 2
    }
  }

  const close = (): void => {
    window.api.desktopPet.close()
  }

  const destroy = (): void => {
    if (retryTimerId !== null) {
      clearTimeout(retryTimerId)
      retryTimerId = null
    }
    currentLoadToken++

    if (idleCleanup) {
      idleCleanup()
      idleCleanup = null
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
  }

  return {
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
    setCoreParam,
    resetPose,
    handleResize,
    close,
    destroy
  }
}
