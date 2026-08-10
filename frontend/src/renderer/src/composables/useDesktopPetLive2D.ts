/**
 * LuomiNest 桌面宠物窗口级 Live2D composable
 *
 * 从 DesktopPetView.vue 拆分，负责独立窗口内的 Live2D 模型管理：
 * - PixiJS Application 初始化（WebGL→Canvas 降级）
 * - 模型加载（动态 import cubism4，复用共享 core）
 * - 窗口适配（窗口变化只同步 renderer 并重新居中，不覆盖模型 scale）
 * - 滚轮缩放（只缩放 Live2D 模型，不改变 BrowserWindow）
 * - 透明像素穿透（WebGL alpha readback + IPC set-ignore-mouse-events）
 * - 焦点跟踪（damping 0.12，混合头部/眼球）
 * - Canvas 拖拽（IPC start-drag/drag-window/end-drag）
 *
 * 与 useLuomiNestLive2D（应用内 canvas）的差异：
 * - damping 0.12 vs 0.08（窗口模式手感不同）
 * - 滚轮仅缩放模型
 * - 鼠标穿透使用实际渲染 alpha，而非矩形 bounds
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
  scanLuomiNestModelCapabilities,
  hideLuomiNestWatermark,
  setupLuomiNestIdleAnimation,
  mapLuomiNestPadToEmotion,
  initLuomiNestPixiApp,
  createLuomiNestFocusTracker,
  triggerLuomiNestMotion,
  triggerLuomiNestExpression,
  setLuomiNestCoreParam,
  resetLuomiNestPose,
  type LuomiNestLive2DModel
} from './live2d/useLuomiNestLive2DCore'

const logger = createLuomiNestRendererLogger('LuomiNestDesktopPet')

const MAX_RETRIES = 3
const MIN_MODEL_SCALE = 0.05
const MAX_MODEL_SCALE = 3
const TRANSPARENCY_SAMPLE_RADIUS = 4
const TRANSPARENCY_ALPHA_THRESHOLD = 8
const TRANSPARENCY_CHECK_INTERVAL_MS = 32

interface ViewportSize {
  width: number
  height: number
}

/** IPC SEND 通道字面量（类型见 DesktopPetIpcChannels.SEND） */
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
  let resizeFrameId: number | null = null

  // 可见性状态：窗口隐藏时降低帧率以节省资源
  let isWindowVisible = true
  const LOW_FPS = 5
  let savedMinFps = 0

  // 焦点跟踪 + 鼠标穿透共享状态（必须在同一闭包内）
  let focusTargetX = 0
  let focusTargetY = 0
  let focusTrackerCleanup: (() => void) | null = null
  let isMouseIgnored = false
  let isDraggingWindow = false
  let lastTransparencyCheckAt = 0
  let hasLoggedReadbackFailure = false

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

  const getViewportSize = (): ViewportSize => {
    // Pixi autoDensity 会给 canvas 写入旧的 inline 像素尺寸；窗口刚发生 resize 时，
    // canvas.getBoundingClientRect() 仍可能返回旧值。以 document viewport 为准，
    // 再由 renderer.resize 反向更新 canvas，避免画布比窗口大而被系统裁切。
    const root = document.documentElement
    return {
      width: Math.max(1, Math.round(root.clientWidth || window.innerWidth)),
      height: Math.max(1, Math.round(root.clientHeight || window.innerHeight))
    }
  }

  const initPixi = (): Application | null => {
    const viewport = getViewportSize()
    return initLuomiNestPixiApp(pixiApp, {
      canvasRef,
      extraConfig: {
        width: viewport.width,
        height: viewport.height,
        preserveDrawingBuffer: true,
      },
      onError: (msg) => { loadError.value = msg },
      logger,
    })
  }

  /** 窗口变化只同步渲染表面并重新居中，用户设置的模型 scale 始终保留。 */
  const syncViewportAndModel = (): void => {
    if (!pixiApp) return

    const viewport = getViewportSize()
    pixiApp.renderer.resize(viewport.width, viewport.height)

    const model = currentModel
    if (!model) return

    model.x = viewport.width / 2
    model.y = viewport.height / 2
  }

  const loadModel = async (url: string, scale: number): Promise<void> => {
    if (retryTimerId !== null) {
      clearTimeout(retryTimerId)
      retryTimerId = null
    }
    // 外部调用时重置重试计数（与原 IPC handler 的 retryCount = 0 行为一致）。
    // retry 由 attemptLoad 内部递归调用，不经过此处，避免无限重试。
    retryCount = 0
    currentLoadToken++
    const loadToken = currentLoadToken
    await attemptLoad(url, scale, loadToken)
  }

  const attemptLoad = async (url: string, scale: number, loadToken: number): Promise<void> => {
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

      // 恢复模型清单中实际配置的默认比例。此前自动 fit 忽略了该参数，
      // 导致 scale=0.25 的内置模型被按错误 bounds 放大到数倍。
      const initialScale = Math.max(MIN_MODEL_SCALE, Math.min(MAX_MODEL_SCALE, scale))
      model.scale.set(initialScale)
      model.anchor.set(0.5, 0.5)
      const viewport = getViewportSize()
      model.x = viewport.width / 2
      model.y = viewport.height / 2

      model.on('hit', (hitAreas: string[]) => {
        if (hitAreas.includes('body') || hitAreas.includes('head')) {
          model.motion('TapBody', 0)
        }
      })

      app.stage.addChild(model)
      currentModel = model
      syncViewportAndModel()
      logger.info(
        `Model layout ready: viewport=${viewport.width}x${viewport.height}, ` +
        `configuredScale=${scale}, appliedScale=${model.scale.x.toFixed(4)}`
      )

      hideLuomiNestWatermark(model)
      idleCleanup = setupLuomiNestIdleAnimation(() => currentModel).cleanup
      setupWindowWheelZoom()
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
          void attemptLoad(url, scale, loadToken)
        }, 1000 * retryCount)
      }
    } finally {
      if (loadToken === currentLoadToken) {
        isLoading.value = false
      }
    }
  }

  const setupWindowWheelZoom = (): void => {
    if (wheelHandler) {
      window.removeEventListener('wheel', wheelHandler)
    }
    wheelHandler = (e: WheelEvent) => {
      const model = currentModel
      if (!model) return
      e.preventDefault()
      const factor = e.deltaY > 0 ? 0.95 : 1.05
      const nextScale = Math.max(
        MIN_MODEL_SCALE,
        Math.min(MAX_MODEL_SCALE, model.scale.x * factor)
      )
      model.scale.set(nextScale)
    }
    window.addEventListener('wheel', wheelHandler, { passive: false })
  }

  /**
   * 读取鼠标附近的 WebGL alpha。返回 true 表示命中实际可见模型像素，
   * false 表示透明背景，null 表示当前 GPU/上下文无法读取。
   */
  const isCanvasPointOpaque = (
    gl: WebGLRenderingContext | WebGL2RenderingContext,
    canvas: HTMLCanvasElement,
    clientX: number,
    clientY: number
  ): boolean | null => {
    const rect = canvas.getBoundingClientRect()
    if (rect.width <= 0 || rect.height <= 0) return false
    if (gl.drawingBufferWidth <= 0 || gl.drawingBufferHeight <= 0) return null

    const xInCanvas = clientX - rect.left
    const yInCanvas = clientY - rect.top
    if (
      xInCanvas < 0 ||
      yInCanvas < 0 ||
      xInCanvas >= rect.width ||
      yInCanvas >= rect.height
    ) {
      return false
    }

    const scaleX = gl.drawingBufferWidth / rect.width
    const scaleY = gl.drawingBufferHeight / rect.height
    if (!Number.isFinite(scaleX) || !Number.isFinite(scaleY)) return null

    const centerX = Math.floor(xInCanvas * scaleX)
    const centerY = Math.floor(gl.drawingBufferHeight - 1 - yInCanvas * scaleY)
    const radiusX = Math.max(1, Math.ceil(TRANSPARENCY_SAMPLE_RADIUS * scaleX))
    const radiusY = Math.max(1, Math.ceil(TRANSPARENCY_SAMPLE_RADIUS * scaleY))
    const startX = Math.max(0, centerX - radiusX)
    const endX = Math.min(gl.drawingBufferWidth - 1, centerX + radiusX)
    const startY = Math.max(0, centerY - radiusY)
    const endY = Math.min(gl.drawingBufferHeight - 1, centerY + radiusY)
    const readWidth = endX - startX + 1
    const readHeight = endY - startY + 1

    if (readWidth <= 0 || readHeight <= 0) return false

    const pixels = new Uint8Array(readWidth * readHeight * 4)
    try {
      gl.readPixels(
        startX,
        startY,
        readWidth,
        readHeight,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        pixels
      )
    } catch {
      return null
    }

    for (let index = 3; index < pixels.length; index += 4) {
      if (pixels[index] >= TRANSPARENCY_ALPHA_THRESHOLD) return true
    }
    return false
  }

  const updateMousePassthrough = (clientX: number, clientY: number): void => {
    if (!currentModel || !pixiApp || !canvasRef.value) return

    const now = performance.now()
    if (now - lastTransparencyCheckAt < TRANSPARENCY_CHECK_INTERVAL_MS) return
    lastTransparencyCheckAt = now

    try {
      // preserveDrawingBuffer=true 保证这里可以读取刚完成的 Live2D 帧。
      pixiApp.render()
      const renderer = pixiApp.renderer as typeof pixiApp.renderer & {
        gl?: WebGLRenderingContext | WebGL2RenderingContext
      }
      const gl = renderer.gl ??
        canvasRef.value.getContext('webgl2') ??
        canvasRef.value.getContext('webgl')

      let isOverVisiblePixel = gl
        ? isCanvasPointOpaque(gl, canvasRef.value, clientX, clientY)
        : null

      // 极少数 GPU/驱动禁用 readPixels 时退回模型 bounds，保证模型仍可交互。
      if (isOverVisiblePixel === null) {
        if (!hasLoggedReadbackFailure) {
          hasLoggedReadbackFailure = true
          logger.warn('WebGL alpha readback unavailable; using model bounds fallback')
        }
        const bounds = currentModel.getBounds()
        isOverVisiblePixel =
          clientX >= bounds.x &&
          clientX <= bounds.x + bounds.width &&
          clientY >= bounds.y &&
          clientY <= bounds.y + bounds.height
      }

      const shouldIgnore = !isOverVisiblePixel
      if (shouldIgnore !== isMouseIgnored) {
        isMouseIgnored = shouldIgnore
        window.electron?.ipcRenderer.send(IPC_SET_IGNORE_MOUSE, shouldIgnore)
      }
    } catch {
      // 读取失败时保持当前状态，避免在模型上突然失去交互。
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
    if (focusTrackerCleanup) {
      focusTrackerCleanup()
      focusTrackerCleanup = null
    }

    // 窗口模式：阻尼 0.12（比 canvas 模式 0.08 略大，手感更稳），
    // 混合原值（头部 60%+40%，眼球 50%+50%）避免覆盖模型自身 idle 动画。
    // isMouseIgnored 为 true 时（鼠标在模型外），getTarget 返回 {0,0} 使头部平滑回归中心。
    const tracker = createLuomiNestFocusTracker({
      damping: 0.12,
      maxHeadAngle: 15,
      maxEyeBall: 0.5,
      blend: true,
      getModel: () => currentModel,
      getTarget: () => isMouseIgnored ? { x: 0, y: 0 } : { x: focusTargetX, y: focusTargetY }
    })
    focusTrackerCleanup = tracker.cleanup
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
    setLuomiNestCoreParam(currentModel, paramId, value)
  }

  const setScale = (scale: number): void => {
    if (!currentModel || !Number.isFinite(scale)) return
    currentModel.scale.set(Math.max(MIN_MODEL_SCALE, Math.min(MAX_MODEL_SCALE, scale)))
  }

  const triggerMotion = async (group: string, index: number): Promise<void> => {
    await triggerLuomiNestMotion(currentModel, group, index)
  }

  const triggerExpression = async (emotionId: string): Promise<void> => {
    const resolved = resolveEmotionForCurrentModel(emotionId)
    await triggerLuomiNestExpression(currentModel, resolved)
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
    await resetLuomiNestPose(currentModel)
  }

  const handleResize = (): void => {
    if (resizeFrameId !== null) {
      cancelAnimationFrame(resizeFrameId)
    }
    resizeFrameId = requestAnimationFrame(() => {
      resizeFrameId = null
      syncViewportAndModel()
    })
  }

  /**
   * 窗口可见性控制：隐藏时降低 PixiJS Ticker 帧率，显示时恢复。
   * 由 useDesktopPetIpc 的 onVisibilityChanged 回调调用。
   */
  const setVisibility = (visible: boolean): void => {
    isWindowVisible = visible
    const app = pixiApp
    if (!app) return

    if (visible) {
      // 恢复正常帧率
      Ticker.shared.minFPS = savedMinFps > 0 ? savedMinFps : 60
      logger.info(`Visibility restored, Ticker minFPS = ${Ticker.shared.minFPS}`)
    } else {
      // 保存当前 minFPS 并降低帧率
      if (savedMinFps === 0) {
        savedMinFps = Ticker.shared.minFPS
      }
      Ticker.shared.minFPS = LOW_FPS
      logger.info(`Window hidden, Ticker minFPS reduced to ${LOW_FPS}`)
    }
  }

  const close = (): void => {
    // 桌宠窗口自身关闭：window.api.desktopPet.close() 是 invoke('desktop-pet:close')，
    // 其 handler 的 assertTrustedSender 仅允许 mainWindow 调用，桌宠窗口会被拦截。
    // 直接调用 window.close() 关闭自身 BrowserWindow（Electron renderer 标准行为）。
    window.close()
  }

  const destroy = (): void => {
    if (resizeFrameId !== null) {
      cancelAnimationFrame(resizeFrameId)
      resizeFrameId = null
    }
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

    if (focusTrackerCleanup) {
      focusTrackerCleanup()
      focusTrackerCleanup = null
    }

    if (currentModel) {
      currentModel.destroy()
      currentModel = null
    }
    if (pixiApp) {
      pixiApp.destroy(true)
      pixiApp = null
    }

    // 恢复 Ticker 帧率（以防窗口隐藏状态下销毁）
    if (!isWindowVisible && savedMinFps > 0) {
      Ticker.shared.minFPS = savedMinFps
      savedMinFps = 0
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
    setScale,
    setCoreParam,
    resetPose,
    handleResize,
    setVisibility,
    close,
    destroy
  }
}
