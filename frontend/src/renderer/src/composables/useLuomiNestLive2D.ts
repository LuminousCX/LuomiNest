import '@pixi/unsafe-eval'
import { ref, type Ref } from 'vue'
import { Application, Ticker } from 'pixi.js'
import { validateLuomiNestModelUrl, resolveExpressionByModelUrl } from '@/config/luominest-models'
import { createLuomiNestRendererLogger } from '@/utils/logger'
import {
  LUOMINEST_DEFAULT_MODEL_SCALE,
  LUOMINEST_MIN_MODEL_SCALE,
  LUOMINEST_MAX_MODEL_SCALE,
  LUOMINEST_MAX_INITIAL_MODEL_SCALE,
  LUOMINEST_MODEL_MAX_RETRIES,
  LUOMINEST_MODEL_RETRY_BASE_DELAY_MS,
  LUOMINEST_CANVAS_READY_TIMEOUT_MS,
  LUOMINEST_MODEL_ANCHOR_Y_RATIO,
} from '@/constants'
import {
  loadCubism4Module,
  patchIsInteractive,
  getLuomiNestCoreModel,
  scanLuomiNestModelCapabilities,
  hideLuomiNestWatermark,
  setupLuomiNestIdleAnimation,
  initLuomiNestPixiApp,
  createLuomiNestFocusTracker,
  triggerLuomiNestMotion,
  triggerLuomiNestExpression,
  setLuomiNestCoreParam,
  resetLuomiNestPose,
  type LuomiNestLive2DModel
} from './live2d/useLuomiNestLive2DCore'

const logger = createLuomiNestRendererLogger('LuomiNestLive2D')

/** PIXI 指针事件最小接口（替代 e: any） */
interface PixiPointerEvent {
  data: { button: number; global: { x: number; y: number } }
}

export interface LuomiNestLive2DState {
  isReady: boolean
  isLoading: boolean
  error: string | null
  currentModelName: string
  currentModelUrl: string
  availableMotions: string[]
  availableExpressions: string[]
}

const isCanvasReady = (canvas: HTMLCanvasElement | null): boolean =>
  Boolean(canvas && canvas.isConnected && canvas.parentElement)

const waitForCanvas = (
  canvasRef: Ref<HTMLCanvasElement | null>,
  timeoutMs = LUOMINEST_CANVAS_READY_TIMEOUT_MS
): Promise<HTMLCanvasElement | null> => {
  return new Promise((resolve) => {
    const canvas = canvasRef.value
    if (isCanvasReady(canvas)) {
      resolve(canvas)
      return
    }

    const start = performance.now()
    let rafId: number | null = null

    const check = () => {
      const c = canvasRef.value
      if (isCanvasReady(c)) {
        if (rafId !== null) cancelAnimationFrame(rafId)
        resolve(c)
        return
      }
      if (performance.now() - start >= timeoutMs) {
        resolve(null)
        return
      }
      rafId = requestAnimationFrame(check)
    }

    rafId = requestAnimationFrame(check)
  })
}

export const useLuomiNestLive2D = (canvasRef: Ref<HTMLCanvasElement | null>) => {
  const isReady = ref(false)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const currentModelName = ref('')
  const currentModelUrl = ref('')
  const availableMotions = ref<string[]>([])
  const availableExpressions = ref<string[]>([])
  const idleActive = ref(false)

  let pixiApp: Application | null = null
  let currentModel: LuomiNestLive2DModel | null = null
  let focusTargetX = 0
  let focusTargetY = 0
  let focusTrackerCleanup: (() => void) | null = null
  let focusMouseMoveHandler: ((e: MouseEvent) => void) | null = null
  let focusMouseLeaveHandler: (() => void) | null = null
  let focusParentEl: HTMLElement | null = null
  let wheelHandler: ((e: WheelEvent) => void) | null = null
  let isDragging = false
  let dragOffset = { x: 0, y: 0 }
  let retryCount = 0
  let retryTimerId: ReturnType<typeof setTimeout> | null = null
  let currentLoadToken = 0
  let idleCleanup: (() => void) | null = null
  let visibilityHandler: (() => void) | null = null
  let lastRequestedUrl = ''
  let lastRequestedScale = LUOMINEST_DEFAULT_MODEL_SCALE

  const cleanupFocus = (): void => {
    if (focusTrackerCleanup) {
      focusTrackerCleanup()
      focusTrackerCleanup = null
    }
    if (focusMouseMoveHandler && focusParentEl) {
      focusParentEl.removeEventListener('mousemove', focusMouseMoveHandler)
    }
    if (focusMouseLeaveHandler && focusParentEl) {
      focusParentEl.removeEventListener('mouseleave', focusMouseLeaveHandler)
    }
    focusMouseMoveHandler = null
    focusMouseLeaveHandler = null
    focusParentEl = null
  }

  const cleanupIdle = (): void => {
    if (idleCleanup) {
      idleCleanup()
      idleCleanup = null
    }
    idleActive.value = false
  }

  /**
   * 根据页面可见性暂停/恢复 Pixi ticker，减少后台标签页的 GPU/CPU 占用。
   * PixiJS 的 Application 默认使用 Ticker.shared，暂停渲染循环可降低
   * requestAnimationFrame  handler 耗时。
   */
  const setupVisibilityControl = (app: Application): void => {
    if (visibilityHandler) {
      document.removeEventListener('visibilitychange', visibilityHandler)
    }

    // 若旧 handler 因页面隐藏停止了 ticker，重新加载模型时需恢复 ticker 运行，
    // 否则新模型挂载后不会渲染（ticker 未启动则不会驱动 stage 更新）
    if (!app.ticker.started && !document.hidden) {
      app.ticker.start()
    }

    visibilityHandler = () => {
      if (document.hidden) {
        app.ticker.stop()
      } else {
        app.ticker.start()
      }
    }
    document.addEventListener('visibilitychange', visibilityHandler)
  }

  const initPixi = async (): Promise<Application | null> => {
    // 保存初始化结果到模块级 pixiApp，使后续调用可复用/销毁旧 App。
    // 此前未赋值导致 pixiApp 始终为 null，每次 loadModel 都新建 Application，
    // 旧 App 泄漏且 canvas 脱离检测分支无法命中。
    pixiApp = initLuomiNestPixiApp(pixiApp, {
      canvasRef,
      extraConfig: {
        resizeTo: canvasRef.value?.parentElement ?? undefined,
      },
      onError: (msg) => { error.value = msg },
      logger,
    })
    return pixiApp
  }

  const loadModel = async (url: string, scale: number = LUOMINEST_DEFAULT_MODEL_SCALE): Promise<void> => {
    // 去重：正在加载同一模型时跳过，避免页面切换/多 watcher 触发重复加载
    if (isLoading.value && url === lastRequestedUrl && scale === lastRequestedScale) {
      return
    }
    lastRequestedUrl = url
    lastRequestedScale = scale

    if (retryTimerId !== null) {
      clearTimeout(retryTimerId)
      retryTimerId = null
    }
    currentLoadToken++
    const loadToken = currentLoadToken

    isLoading.value = true
    error.value = null
    isReady.value = false

    if (!validateLuomiNestModelUrl(url)) {
      error.value = `Invalid model URL: ${url}`
      isLoading.value = false
      return
    }

    // 等待 canvas 真正挂载到 DOM，避免在 v-if 切换或页面过渡期间初始化失败
    const readyCanvas = await waitForCanvas(canvasRef)
    if (!readyCanvas) {
      if (loadToken === currentLoadToken) {
        error.value = 'Canvas element not available'
        isLoading.value = false
      }
      return
    }

    try {
      const app = await initPixi()
      if (!app || loadToken !== currentLoadToken) {
        if (loadToken === currentLoadToken) {
          throw new Error(error.value || 'PixiJS Application not initialized. Please check graphics drivers and restart.')
        }
        return
      }

      // 此处 loadToken === currentLoadToken 已由上方守卫保证，移除冗余比较
      setupVisibilityControl(app)

      if (currentModel) {
        app.stage.removeChild(currentModel)
        currentModel.destroy()
        currentModel = null
      }

      cleanupFocus()
      cleanupIdle()

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

      const clampedScale = Math.max(LUOMINEST_MIN_MODEL_SCALE, Math.min(LUOMINEST_MAX_INITIAL_MODEL_SCALE, scale))
      model.scale.set(clampedScale)
      model.anchor.set(0.5, 0.5)

      const parent = canvasRef.value?.parentElement
      if (parent) {
        model.x = parent.clientWidth / 2
        // 模型中心下移至容器底部附近，让头、肩、胸、肚子露出
        model.y = parent.clientHeight * LUOMINEST_MODEL_ANCHOR_Y_RATIO
      }

      hideLuomiNestWatermark(model)

      setupInteraction(model)
      setupFocus(model)
      idleCleanup = setupLuomiNestIdleAnimation(() => currentModel).cleanup
      idleActive.value = true
      setupWheel(model)

      patchIsInteractive(model as unknown as Parameters<typeof patchIsInteractive>[0])

      app.stage.addChild(model)
      currentModel = model
      isReady.value = true
      retryCount = 0

      const caps = scanLuomiNestModelCapabilities(model)
      availableMotions.value = caps.motions
      availableExpressions.value = caps.expressions

      const urlParts = url.split('/')
      currentModelName.value = urlParts[2] || 'Unknown'
      currentModelUrl.value = url

      try {
        await model.motion('Idle', 0)
      } catch {
        // intentionally ignored: expected non-fatal error
      }

      logger.info('Model loaded:', url)
    } catch (err) {
      if (loadToken !== currentLoadToken) return

      const message = err instanceof Error ? err.message : 'Failed to load model'
      error.value = message
      logger.error('Load error:', message)

      if (retryCount < LUOMINEST_MODEL_MAX_RETRIES) {
        retryCount++
        logger.info(`Retrying (${retryCount}/${LUOMINEST_MODEL_MAX_RETRIES})...`)
        retryTimerId = setTimeout(async () => {
          retryTimerId = null
          if (loadToken !== currentLoadToken) return
          await loadModel(url, scale)
        }, LUOMINEST_MODEL_RETRY_BASE_DELAY_MS * retryCount)
      }
    } finally {
      if (loadToken === currentLoadToken) {
        isLoading.value = false
      }
    }
  }

  const setupInteraction = (model: LuomiNestLive2DModel): void => {
    model.eventMode = 'static'

    model.on('pointerdown', (e: PixiPointerEvent) => {
      if (e.data.button !== 0) return
      isDragging = true
      dragOffset.x = e.data.global.x - model.x
      dragOffset.y = e.data.global.y - model.y
    })

    model.on('pointermove', (e: PixiPointerEvent) => {
      if (!isDragging) return
      model.x = e.data.global.x - dragOffset.x
      model.y = e.data.global.y - dragOffset.y
    })

    const endDrag = (): void => {
      isDragging = false
    }
    model.on('pointerup', endDrag)
    model.on('pointerupoutside', endDrag)

    model.on('hit', (hitAreas: string[]) => {
      if (hitAreas.includes('body')) {
        model.motion('TapBody', 0)
      }
    })
  }

  const setupFocus = (_model: LuomiNestLive2DModel): void => {
    cleanupFocus()

    // 较小的阻尼系数让头部跟随更平滑，避免鼠标移动时猛地转头
    // canvas 模式：直接设置参数值，避免反馈循环导致角度跃升
    const tracker = createLuomiNestFocusTracker({
      damping: 0.08,
      maxHeadAngle: 10,
      maxEyeBall: 0.6,
      blend: false,
      getModel: () => currentModel,
      getTarget: () => ({ x: focusTargetX, y: focusTargetY })
    })
    focusTrackerCleanup = tracker.cleanup

    const onMouseMove = (e: MouseEvent): void => {
      const parent = canvasRef.value?.parentElement
      if (!parent) return
      focusTargetX = (e.clientX / parent.clientWidth) * 2 - 1
      focusTargetY = -((e.clientY / parent.clientHeight) * 2 - 1)
    }

    const onMouseLeave = (): void => {
      focusTargetX = 0
      focusTargetY = 0
    }

    focusMouseMoveHandler = onMouseMove
    focusMouseLeaveHandler = onMouseLeave

    const parent = canvasRef.value?.parentElement
    if (parent) {
      focusParentEl = parent
      parent.addEventListener('mousemove', onMouseMove)
      parent.addEventListener('mouseleave', onMouseLeave)
    }
  }

  const setupWheel = (model: LuomiNestLive2DModel): void => {
    if (wheelHandler) {
      canvasRef.value?.removeEventListener('wheel', wheelHandler)
    }
    wheelHandler = (e: WheelEvent) => {
      if (!model) return
      e.preventDefault()
      const scaleFactor = e.deltaY > 0 ? 0.95 : 1.05
      const newScale = Math.max(LUOMINEST_MIN_MODEL_SCALE, Math.min(LUOMINEST_MAX_MODEL_SCALE, model.scale.x * scaleFactor))
      model.scale.set(newScale)
    }
    canvasRef.value?.addEventListener('wheel', wheelHandler, { passive: false })
  }

  const triggerMotion = async (group: string, index: number = 0): Promise<void> => {
    await triggerLuomiNestMotion(currentModel, group, index)
  }

  const triggerExpression = async (name: string): Promise<void> => {
    await triggerLuomiNestExpression(currentModel, name)
  }

  const driveEmotion = async (emotionId: string): Promise<void> => {
    const expressionName = resolveExpressionByModelUrl(currentModelUrl.value, emotionId)
    await triggerExpression(expressionName)
  }

  const drivePadEmotion = (pleasure: number, _arousal: number, _dominance: number): void => {
    if (!currentModel) return
    const access = getLuomiNestCoreModel(currentModel)
    if (!access) return

    try {
      const { coreModel } = access
      const mouthFormIdx = coreModel.getParameterIndex('ParamMouthForm')
      const browLYIdx = coreModel.getParameterIndex('ParamBrowLY')
      const browRYIdx = coreModel.getParameterIndex('ParamBrowRY')
      const browLFormIdx = coreModel.getParameterIndex('ParamBrowLForm')
      const browRFormIdx = coreModel.getParameterIndex('ParamBrowRForm')
      const cheekIdx = coreModel.getParameterIndex('ParamCheek')

      if (mouthFormIdx >= 0) {
        coreModel.setParameterValueByIndex(mouthFormIdx, pleasure * 0.8)
      }
      if (browLYIdx >= 0) {
        const val = pleasure > 0 ? pleasure * 0.5 : -pleasure * 0.3
        coreModel.setParameterValueByIndex(browLYIdx, val)
      }
      if (browRYIdx >= 0) {
        const val = pleasure > 0 ? pleasure * 0.5 : -pleasure * 0.3
        coreModel.setParameterValueByIndex(browRYIdx, val)
      }
      if (browLFormIdx >= 0) {
        const val = pleasure > 0 ? -pleasure * 0.5 : pleasure * 0.3
        coreModel.setParameterValueByIndex(browLFormIdx, val)
      }
      if (browRFormIdx >= 0) {
        const val = pleasure > 0 ? -pleasure * 0.5 : pleasure * 0.3
        coreModel.setParameterValueByIndex(browRFormIdx, val)
      }
      if (cheekIdx >= 0 && pleasure > 0.3) {
        coreModel.setParameterValueByIndex(cheekIdx, pleasure * 0.5)
      }
    } catch {
      // intentionally ignored: expected non-fatal error
    }
  }

  const syncLipParam = (value: number): void => {
    if (!currentModel) return
    const access = getLuomiNestCoreModel(currentModel)
    if (!access) return
    try {
      const { coreModel } = access
      const mouthOpenIdx = coreModel.getParameterIndex('ParamMouthOpenY')
      if (mouthOpenIdx >= 0) {
        coreModel.setParameterValueByIndex(mouthOpenIdx, Math.max(0, Math.min(1, value)))
      }
    } catch {
      // intentionally ignored: expected non-fatal error
    }
  }

  const syncLipVowel = (vowel: string): void => {
    if (!currentModel) return
    const access = getLuomiNestCoreModel(currentModel)
    if (!access) return
    try {
      const { coreModel } = access
      const mouthOpenIdx = coreModel.getParameterIndex('ParamMouthOpenY')
      const mouthFormIdx = coreModel.getParameterIndex('ParamMouthForm')

      const vowelMap: Record<string, { open: number; form: number }> = {
        a: { open: 0.8, form: 0.8 },
        i: { open: 0.3, form: -0.6 },
        u: { open: 0.2, form: -0.8 },
        e: { open: 0.5, form: -0.3 },
        o: { open: 0.6, form: -0.5 }
      }

      const mapping = vowelMap[vowel.toLowerCase()]
      if (mapping) {
        if (mouthOpenIdx >= 0) coreModel.setParameterValueByIndex(mouthOpenIdx, mapping.open)
        if (mouthFormIdx >= 0) coreModel.setParameterValueByIndex(mouthFormIdx, mapping.form)
      }
    } catch {
      // intentionally ignored: expected non-fatal error
    }
  }

  const setCoreParam = (paramId: string, value: number): void => {
    setLuomiNestCoreParam(currentModel, paramId, value)
  }

  const resetPose = async (): Promise<void> => {
    await resetLuomiNestPose(currentModel)
  }

  const destroy = (): void => {
    if (retryTimerId !== null) {
      clearTimeout(retryTimerId)
      retryTimerId = null
    }
    currentLoadToken++
    cleanupFocus()
    cleanupIdle()
    if (visibilityHandler) {
      document.removeEventListener('visibilitychange', visibilityHandler)
      visibilityHandler = null
    }
    if (wheelHandler) {
      canvasRef.value?.removeEventListener('wheel', wheelHandler)
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
    isReady.value = false
    currentModelUrl.value = ''
    lastRequestedUrl = ''
  }

  return {
    isReady,
    isLoading,
    error,
    currentModelName,
    currentModelUrl,
    availableMotions,
    availableExpressions,
    idleActive,
    loadModel,
    triggerMotion,
    triggerExpression,
    driveEmotion,
    drivePadEmotion,
    syncLipParam,
    syncLipVowel,
    setCoreParam,
    resetPose,
    destroy
  }
}
