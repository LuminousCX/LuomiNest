import { ref, type Ref } from 'vue'
import { Application, Ticker } from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display-mulmotion/cubism4'
import { validateLuomiNestModelUrl } from '@/config/luominest-models'

const EXPRESSION_BLOCKLIST = ['水印', 'watermark', 'copyright', 'credit', 'logo']

export interface LuomiNestLive2DState {
  isReady: boolean
  isLoading: boolean
  error: string | null
  currentModelName: string
  availableMotions: string[]
  availableExpressions: string[]
}

export const useLuomiNestLive2D = (canvasRef: Ref<HTMLCanvasElement | null>) => {
  const isReady = ref(false)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const currentModelName = ref('')
  const availableMotions = ref<string[]>([])
  const availableExpressions = ref<string[]>([])

  let pixiApp: Application | null = null
  let currentModel: Live2DModel | null = null
  let focusTargetX = 0
  let focusTargetY = 0
  let focusCurrentX = 0
  let focusCurrentY = 0
  let focusTickerCallback: (() => void) | null = null
  let focusMouseMoveHandler: ((e: MouseEvent) => void) | null = null
  let focusMouseLeaveHandler: (() => void) | null = null
  let focusParentEl: HTMLElement | null = null
  let wheelHandler: ((e: WheelEvent) => void) | null = null
  let isDragging = false
  let dragOffset = { x: 0, y: 0 }
  let retryCount = 0
  let retryTimerId: ReturnType<typeof setTimeout> | null = null
  let currentLoadToken = 0
  const MAX_RETRIES = 3

  const cleanupFocus = () => {
    if (focusTickerCallback) {
      Ticker.shared.remove(focusTickerCallback)
      focusTickerCallback = null
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

  const initPixi = async (): Promise<Application | null> => {
    if (pixiApp) return pixiApp
    if (!canvasRef.value) {
      console.error('[ERROR][LuomiNestLive2D] Canvas element not found')
      error.value = 'Canvas element not available'
      return null
    }

    try {
      pixiApp = new Application({
        view: canvasRef.value,
        autoStart: true,
        backgroundAlpha: 0,
        antialias: true,
        resizeTo: canvasRef.value.parentElement ?? undefined,
        resolution: Math.min(window.devicePixelRatio || 1, 2),
        autoDensity: true,
        powerPreference: 'high-performance'
      } as any)
      console.info('[INFO][LuomiNestLive2D] PixiJS initialized successfully (WebGL)')
      return pixiApp
    } catch (webglErr) {
      console.warn('[WARN][LuomiNestLive2D] WebGL init failed, trying canvas fallback:', webglErr instanceof Error ? webglErr.message : webglErr)
      try {
        pixiApp = new Application({
          view: canvasRef.value,
          autoStart: true,
          backgroundAlpha: 0,
          antialias: true,
          resizeTo: canvasRef.value.parentElement ?? undefined,
          resolution: Math.min(window.devicePixelRatio || 1, 2),
          autoDensity: true
        } as any)
        console.info('[INFO][LuomiNestLive2D] PixiJS initialized successfully (Canvas fallback)')
        return pixiApp
      } catch (canvasErr) {
        const message = canvasErr instanceof Error ? canvasErr.message : 'Unknown error'
        error.value = `Graphics initialization failed: ${message}`
        console.error('[ERROR][LuomiNestLive2D] Both WebGL and Canvas failed:', message)
        return null
      }
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
      // intentionally ignored: expected non-fatal error
    }
    availableMotions.value = motions
    availableExpressions.value = expressions
  }

  const loadModel = async (url: string, scale: number = 0.25) => {
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

    try {
      const app = await initPixi()
      if (!app) {
        throw new Error(error.value || 'PixiJS Application not initialized. Please check graphics drivers and restart.')
      }

      if (loadToken !== currentLoadToken) return

      if (currentModel) {
        app.stage.removeChild(currentModel)
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

      const parent = canvasRef.value?.parentElement
      if (parent) {
        model.x = parent.clientWidth / 2
        model.y = parent.clientHeight / 2
      }

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
      // intentionally ignored: expected non-fatal error
      }

      setupInteraction(model)
      setupFocus(model)
      setupWheel(model)

      app.stage.addChild(model)
      currentModel = model
      isReady.value = true
      retryCount = 0

      scanModelCapabilities(model)

      const urlParts = url.split('/')
      currentModelName.value = urlParts[2] || 'Unknown'

      try {
        await model.motion('Idle', 0)
      } catch {
      // intentionally ignored: expected non-fatal error
      }

      console.info('[INFO][LuomiNestLive2D] Model loaded:', url)
    } catch (err) {
      if (loadToken !== currentLoadToken) return

      const message = err instanceof Error ? err.message : 'Failed to load model'
      error.value = message
      console.error('[ERROR][LuomiNestLive2D] Load error:', message)

      if (retryCount < MAX_RETRIES) {
        retryCount++
        console.info(`[INFO][LuomiNestLive2D] Retrying (${retryCount}/${MAX_RETRIES})...`)
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

  const setupInteraction = (model: Live2DModel) => {
    model.interactive = true

    model.on('pointerdown', (e: any) => {
      if (e.data.button !== 0) return
      isDragging = true
      dragOffset.x = e.data.global.x - model.x
      dragOffset.y = e.data.global.y - model.y
    })

    model.on('pointermove', (e: any) => {
      if (!isDragging) return
      model.x = e.data.global.x - dragOffset.x
      model.y = e.data.global.y - dragOffset.y
    })

    const endDrag = () => {
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

  const setupFocus = (_model: Live2DModel) => {
    cleanupFocus()

    const FOCUS_DAMPING = 0.12

    const onMouseMove = (e: MouseEvent) => {
      const parent = canvasRef.value?.parentElement
      if (!parent) return
      focusTargetX = (e.clientX / parent.clientWidth) * 2 - 1
      focusTargetY = -((e.clientY / parent.clientHeight) * 2 - 1)
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
      // intentionally ignored: expected non-fatal error
      }
    }

    const parent = canvasRef.value?.parentElement
    if (parent) {
      focusParentEl = parent
      parent.addEventListener('mousemove', onMouseMove)
      parent.addEventListener('mouseleave', onMouseLeave)
    }
    Ticker.shared.add(focusTickerCallback)
  }

  const setupWheel = (model: Live2DModel) => {
    if (wheelHandler) {
      canvasRef.value?.removeEventListener('wheel', wheelHandler)
    }
    wheelHandler = (e: WheelEvent) => {
      if (!model) return
      e.preventDefault()
      const scaleFactor = e.deltaY > 0 ? 0.95 : 1.05
      const newScale = Math.max(0.05, Math.min(3.0, model.scale.x * scaleFactor))
      model.scale.set(newScale)
    }
    canvasRef.value?.addEventListener('wheel', wheelHandler, { passive: false })
  }

  const triggerMotion = async (group: string, index: number = 0) => {
    if (!currentModel) return
    try {
      await currentModel.motion(group, index)
    } catch {
      // intentionally ignored: expected non-fatal error
    }
  }

  const triggerExpression = async (name: string) => {
    if (!currentModel) return
    try {
      await currentModel.expression(name)
    } catch {
      // intentionally ignored: expected non-fatal error
    }
  }

  const driveEmotion = async (emotionId: string) => {
    await triggerExpression(emotionId)
  }

  const drivePadEmotion = (pleasure: number, _arousal: number, _dominance: number) => {
    if (!currentModel) return
    try {
      const internalModel = currentModel.internalModel as any
      const coreModel = internalModel?.coreModel
      if (!coreModel) return

      const mouthFormIdx = coreModel.getParameterIndex('ParamMouthForm')
      const browLYIdx = coreModel.getParameterIndex('ParamBrowLY')
      const browRYIdx = coreModel.getParameterIndex('ParamBrowRY')
      const browLFormIdx = coreModel.getParameterIndex('ParamBrowLForm')
      const browRFormIdx = coreModel.getParameterIndex('ParamBrowRForm')
      const cheekIdx = coreModel.getParameterIndex('ParamCheek')

      if (mouthFormIdx >= 0) {
        const val = pleasure * 0.8
        coreModel.setParameterValueByIndex(mouthFormIdx, val)
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

  const syncLipParam = (value: number) => {
    if (!currentModel) return
    try {
      const internalModel = currentModel.internalModel as any
      const coreModel = internalModel?.coreModel
      if (!coreModel) return
      const mouthOpenIdx = coreModel.getParameterIndex('ParamMouthOpenY')
      if (mouthOpenIdx >= 0) {
        coreModel.setParameterValueByIndex(mouthOpenIdx, Math.max(0, Math.min(1, value)))
      }
    } catch {
      // intentionally ignored: expected non-fatal error
    }
  }

  const syncLipVowel = (vowel: string) => {
    if (!currentModel) return
    try {
      const internalModel = currentModel.internalModel as any
      const coreModel = internalModel?.coreModel
      if (!coreModel) return

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

  const setCoreParam = (paramId: string, value: number) => {
    if (!currentModel) return
    try {
      const internalModel = currentModel.internalModel as any
      const coreModel = internalModel?.coreModel
      if (coreModel && typeof coreModel.setParameterValueById === 'function') {
        coreModel.setParameterValueById(paramId, value)
      }
    } catch {
      // intentionally ignored: expected non-fatal error
    }
  }

  const resetPose = async () => {
    if (!currentModel) return
    try {
      await currentModel.motion('Idle', 0)
    } catch {
      // intentionally ignored: expected non-fatal error
    }
  }

  const destroy = () => {
    if (retryTimerId !== null) {
      clearTimeout(retryTimerId)
      retryTimerId = null
    }
    currentLoadToken++
    cleanupFocus()
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
  }

  return {
    isReady,
    isLoading,
    error,
    currentModelName,
    availableMotions,
    availableExpressions,
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
