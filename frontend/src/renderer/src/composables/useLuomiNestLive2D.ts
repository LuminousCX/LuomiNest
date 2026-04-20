import { ref, shallowRef, onUnmounted } from 'vue'
import { Application, Ticker } from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display-mulmotion/cubism4'

export interface LuomiNestEmotion {
  id: string
  label: string
  intensity: number
}

export interface LuomiNestPadVector {
  pleasure: number
  arousal: number
  dominance: number
}

export interface LuomiNestAvatarConfig {
  url: string
  scale?: number
  position?: { x: number; y: number }
  autoInteract?: boolean
}

export interface LuomiNestModelInfo {
  id: string
  name: string
  url: string
  scale: number
  type: 'live2d' | 'vrm' | 'pixelpet'
  tags: string[]
}

/**
 * 口型同步参数映射
 * 用于语音驱动口型动画
 */
const LIP_SYNC_PARAMS = {
  mouthOpenY: 'ParamMouthOpenY',
  mouthForm: 'ParamMouthForm',
  mouthSize: 'ParamMouthSize'
} as const

/**
 * 水印控制参数
 * 某些 Live2D 模型（如 llny）内置水印图层，通过参数控制显示/隐藏
 * Param14 = 0 隐藏水印，Param14 = 1 显示水印
 */
const WATERMARK_PARAM = {
  id: 'Param14',
  hideValue: 0,
  showValue: 1
} as const

const EXPRESSION_BLOCKLIST = ['水印', 'watermark', 'copyright', 'credit', 'logo']

const VOWEL_LIP_MAP: Record<string, { open: number; form: number }> = {
  a: { open: 1.0, form: 0.0 },
  e: { open: 0.5, form: 0.3 },
  i: { open: 0.2, form: 1.0 },
  o: { open: 0.7, form: -0.5 },
  u: { open: 0.3, form: -1.0 },
  n: { open: 0.1, form: 0.0 },
  s: { open: 0.1, form: 0.0 },
  ' ': { open: 0.0, form: 0.0 }
}

/**
 * 模型边界约束常量
 * 用于限制缩放和位置范围
 */
const AVATAR_BOUNDS = {
  MIN_SCALE: 0.05,
  MAX_SCALE: 2.0,
  SCALE_FACTOR: 0.03,
  POSITION_MARGIN: 50
} as const

const FOCUS_DAMPING = 0.15

const DEFAULT_AVATAR_CONFIG: Partial<LuomiNestAvatarConfig> = {
  scale: 0.25,
  position: { x: 0.5, y: 0.5 },
  autoInteract: false
}

export const useLuomiNestAvatar = () => {
  const renderHost = shallowRef<Application | null>(null)
  const avatarModel = shallowRef<Live2DModel | null>(null)
  const isLoading = ref(false)
  const loadError = ref<string | null>(null)
  const activeEmotionState = ref<LuomiNestEmotion>({ id: 'neutral', label: 'Calm', intensity: 0 })
  const padVector = ref<LuomiNestPadVector>({ pleasure: 0, arousal: 0, dominance: 0 })
  const isModelReady = ref(false)
  const currentModelInfo = ref<LuomiNestModelInfo | null>(null)
  const availableMotions = ref<string[]>([])
  const availableExpressions = ref<string[]>([])
  const avatarScale = ref(DEFAULT_AVATAR_CONFIG.scale ?? 0.25)

  let resizeObserver: ResizeObserver | null = null
  let isDragging = false
  let dragOffset = { x: 0, y: 0 }
  let focusTargetX = 0
  let focusTargetY = 0
  let focusCurrentX = 0
  let focusCurrentY = 0
  let focusTickerCallback: (() => void) | null = null

  /**
   * 限制模型位置在容器范围内
   */
  const clampPosition = (model: Live2DModel, containerWidth: number, containerHeight: number) => {
    const halfW = (model.width * model.scale.x) / 2
    const halfH = (model.height * model.scale.y) / 2
    const margin = AVATAR_BOUNDS.POSITION_MARGIN
    model.x = Math.max(halfW - margin, Math.min(containerWidth - halfW + margin, model.x))
    model.y = Math.max(halfH - margin, Math.min(containerHeight - halfH + margin, model.y))
  }

  /**
   * 限制缩放值在有效范围内
   */
  const clampScale = (scale: number): number => {
    return Math.max(AVATAR_BOUNDS.MIN_SCALE, Math.min(AVATAR_BOUNDS.MAX_SCALE, scale))
  }

  /**
   * 扫描模型支持的动作和表情
   */
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
    } catch (err) {
      console.warn('[WARNING][LuomiNestAvatar] scanModelCapabilities error:', err)
    }
    availableMotions.value = motions
    availableExpressions.value = expressions
  }

  /**
   * 初始化 PixiJS 渲染环境
   */
  const initRenderHost = async (canvas: HTMLCanvasElement) => {
    if (renderHost.value) return renderHost.value

    const parent = canvas.parentElement
    const width = parent?.clientWidth ?? 800
    const height = parent?.clientHeight ?? 600

    const app = new Application({
      view: canvas,
      autoStart: true,
      resizeTo: parent ?? undefined,
      backgroundAlpha: 0,
      antialias: true,
      width,
      height,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
      autoDensity: true
    })

    renderHost.value = app

    if (parent) {
      resizeObserver = new ResizeObserver(() => {
        app.renderer.resize(parent.clientWidth, parent.clientHeight)
        if (avatarModel.value) {
          clampPosition(avatarModel.value, parent.clientWidth, parent.clientHeight)
        }
      })
      resizeObserver.observe(parent)
    }

    return app
  }

  /**
   * 设置模型初始位置（居中显示）
   */
  const positionAvatar = (model: Live2DModel, containerWidth: number, containerHeight: number) => {
    const config = { ...DEFAULT_AVATAR_CONFIG }
    model.anchor.set(0.5, 0.5)
    model.x = containerWidth * (config.position?.x ?? 0.5)
    model.y = containerHeight * (config.position?.y ?? 0.5)
  }

  /**
   * 绑定拖拽和滚轮缩放事件
   */
  const bindDragEvents = (canvas: HTMLCanvasElement) => {
    const onPointerDown = (e: PointerEvent) => {
      if (!avatarModel.value) return
      isDragging = true
      dragOffset.x = e.clientX - avatarModel.value.x
      dragOffset.y = e.clientY - avatarModel.value.y
      canvas.setPointerCapture(e.pointerId)
    }

    const onPointerMove = (e: PointerEvent) => {
      if (!isDragging || !avatarModel.value) return
      const parent = canvas.parentElement
      if (!parent) return
      avatarModel.value.x = e.clientX - dragOffset.x
      avatarModel.value.y = e.clientY - dragOffset.y
      clampPosition(avatarModel.value, parent.clientWidth, parent.clientHeight)
    }

    const onPointerUp = () => {
      isDragging = false
    }

    const onWheel = (e: WheelEvent) => {
      if (!avatarModel.value) return
      e.preventDefault()
      const scaleFactor = e.deltaY > 0
        ? (1 - AVATAR_BOUNDS.SCALE_FACTOR)
        : (1 + AVATAR_BOUNDS.SCALE_FACTOR)
      const newScale = clampScale(avatarModel.value.scale.x * scaleFactor)
      avatarModel.value.scale.set(newScale)
      avatarScale.value = newScale
      const parent = canvas.parentElement
      if (parent) {
        clampPosition(avatarModel.value, parent.clientWidth, parent.clientHeight)
      }
    }

    canvas.addEventListener('pointerdown', onPointerDown)
    canvas.addEventListener('pointermove', onPointerMove)
    canvas.addEventListener('pointerup', onPointerUp)
    canvas.addEventListener('pointercancel', onPointerUp)
    canvas.addEventListener('wheel', onWheel, { passive: false })

    const cleanup = () => {
      canvas.removeEventListener('pointerdown', onPointerDown)
      canvas.removeEventListener('pointermove', onPointerMove)
      canvas.removeEventListener('pointerup', onPointerUp)
      canvas.removeEventListener('pointercancel', onPointerUp)
      canvas.removeEventListener('wheel', onWheel)
    }

    return cleanup
  }

  const setupDampenedFocus = (canvas: HTMLCanvasElement, model: Live2DModel) => {
    if (focusTickerCallback) {
      Ticker.shared.remove(focusTickerCallback)
      focusTickerCallback = null
    }

    const onMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect()
      focusTargetX = ((e.clientX - rect.left) / rect.width) * 2 - 1
      focusTargetY = -(((e.clientY - rect.top) / rect.height) * 2 - 1)
    }

    const onMouseLeave = () => {
      focusTargetX = 0
      focusTargetY = 0
    }

    focusTickerCallback = () => {
      if (!avatarModel.value) return
      focusCurrentX += (focusTargetX - focusCurrentX) * FOCUS_DAMPING
      focusCurrentY += (focusTargetY - focusCurrentY) * FOCUS_DAMPING

      try {
        const internalModel = avatarModel.value.internalModel as any
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
        // ignore parameter errors
      }
    }

    canvas.addEventListener('mousemove', onMouseMove)
    canvas.addEventListener('mouseleave', onMouseLeave)
    Ticker.shared.add(focusTickerCallback)
  }

  /**
   * 加载并挂载 Live2D 模型到画布
   */
  const mountAvatar = async (canvas: HTMLCanvasElement, config: LuomiNestAvatarConfig) => {
    isLoading.value = true
    loadError.value = null
    isModelReady.value = false

    try {
      const app = await initRenderHost(canvas)
      const mergedConfig = { ...DEFAULT_AVATAR_CONFIG, ...config }

      if (avatarModel.value) {
        app.stage.removeChild(avatarModel.value)
        avatarModel.value.destroy()
        avatarModel.value = null
      }

      const model = await Live2DModel.from(mergedConfig.url, {
        autoHitTest: true,
        autoFocus: false,
        ticker: Ticker.shared
      })

      const scale = clampScale(mergedConfig.scale ?? 0.25)
      model.scale.set(scale)
      avatarScale.value = scale

      positionAvatar(model, app.renderer.width / (app.renderer.resolution || 1), app.renderer.height / (app.renderer.resolution || 1))

      model.on('hit', (hitAreas: string[]) => {
        if (hitAreas.includes('body')) {
          triggerMotion('TapBody', 0)
        } else if (hitAreas.includes('head')) {
          triggerMotion('TapBody', 0)
        }
      })

      app.stage.addChild(model)
      avatarModel.value = model
      isModelReady.value = true

      setCoreParam(WATERMARK_PARAM.id, WATERMARK_PARAM.hideValue)

      scanModelCapabilities(model)
      bindDragEvents(canvas)
      setupDampenedFocus(canvas, model)

      try {
        await triggerMotion('Idle', 0)
      } catch {
        // idle motion may not exist
      }

      console.info('[INFO][LuomiNestAvatar] Model loaded successfully:', config.url)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load LuomiNest avatar model'
      loadError.value = message
      console.error('[ERROR][LuomiNestAvatar] Model load error:', message)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 使用模型信息加载模型
   */
  const mountAvatarFromModelInfo = async (canvas: HTMLCanvasElement, modelInfo: LuomiNestModelInfo) => {
    currentModelInfo.value = modelInfo
    await mountAvatar(canvas, {
      url: modelInfo.url,
      scale: modelInfo.scale
    })
  }

  /**
   * 触发模型动作
   */
  const triggerMotion = async (group: string, index: number): Promise<void> => {
    if (!avatarModel.value) return
    try {
      await avatarModel.value.motion(group, index)
    } catch (err) {
      console.warn(`[WARNING][LuomiNestAvatar] Motion "${group}[${index}]" not available:`, err)
    }
  }

  /**
   * 应用表情
   */
  const applyExpression = async (name: string): Promise<void> => {
    if (!avatarModel.value) return
    try {
      await avatarModel.value.expression(name)
    } catch (err) {
      console.warn(`[WARNING][LuomiNestAvatar] Expression "${name}" not available:`, err)
    }
  }

  /**
   * 同步口型参数（数值模式）
   */
  const syncLipParam = (value: number): void => {
    if (!avatarModel.value) return
    const clamped = Math.max(0, Math.min(value, 1))
    setCoreParam(LIP_SYNC_PARAMS.mouthOpenY, clamped)
  }

  /**
   * 同步口型参数（元音模式）
   */
  const syncLipVowel = (vowel: string): void => {
    const mapping = VOWEL_LIP_MAP[vowel.toLowerCase()]
    if (!mapping) return
    setCoreParam(LIP_SYNC_PARAMS.mouthOpenY, mapping.open)
    setCoreParam(LIP_SYNC_PARAMS.mouthForm, mapping.form)
  }

  /**
   * 设置 Live2D 核心参数
   * 用于直接控制模型参数值
   */
  const setCoreParam = (paramId: string, value: number): void => {
    if (!avatarModel.value) return
    try {
      const internalModel = avatarModel.value.internalModel
      if (internalModel && 'coreModel' in internalModel) {
        const coreModel = (internalModel as any).coreModel
        if (coreModel && typeof coreModel.setParameterValueById === 'function') {
          coreModel.setParameterValueById(paramId, value)
        }
      }
    } catch (err) {
      console.warn(`[WARNING][LuomiNestAvatar] setCoreParam("${paramId}") error:`, err)
    }
  }

  /**
   * 驱动情感表情
   */
  const driveEmotion = (emotion: LuomiNestEmotion): void => {
    activeEmotionState.value = emotion
    applyExpression(emotion.id)
  }

  /**
   * 驱动 PAD 情感向量
   * PAD = Pleasure(愉悦度), Arousal(激活度), Dominance(支配度)
   */
  const drivePadEmotion = (pad: LuomiNestPadVector): void => {
    padVector.value = pad
    const { pleasure, arousal, dominance } = pad
    let emotionId = 'neutral'
    let intensity = 0
    if (pleasure > 0.3 && arousal > 0.3) { emotionId = 'happy'; intensity = pleasure }
    else if (pleasure < -0.3 && arousal > 0) { emotionId = 'angry'; intensity = Math.abs(pleasure) }
    else if (pleasure < -0.3 && arousal < -0.2) { emotionId = 'sad'; intensity = Math.abs(pleasure) }
    else if (pleasure > 0 && arousal < -0.3) { emotionId = 'love'; intensity = pleasure }
    else if (arousal > 0.5 && dominance < -0.2) { emotionId = 'surprise'; intensity = arousal }
    driveEmotion({ id: emotionId, label: emotionId, intensity })
  }

  /**
   * 驱动肢体参数
   */
  const driveLimbParam = (paramId: string, value: number): void => {
    setCoreParam(paramId, value)
  }

  /**
   * 驱动面部参数
   */
  const driveFaceParam = (paramId: string, value: number): void => {
    setCoreParam(paramId, value)
  }

  /**
   * 重置模型姿势
   */
  const resetAvatarPose = (): void => {
    if (!avatarModel.value) return
    try {
      const internalModel = avatarModel.value.internalModel as any
      if (internalModel?.poseModel) {
        internalModel.poseModel.resetPose()
      }
    } catch (err) {
      console.warn('[WARNING][LuomiNestAvatar] resetAvatarPose error:', err)
    }
  }

  /**
   * 调整模型缩放比例
   */
  const adjustAvatarScale = (scale: number): void => {
    if (!avatarModel.value) return
    const clamped = clampScale(scale)
    avatarModel.value.scale.set(clamped)
    avatarScale.value = clamped
  }

  /**
   * 销毁模型和渲染资源
   */
  const teardown = (): void => {
    if (focusTickerCallback) {
      Ticker.shared.remove(focusTickerCallback)
      focusTickerCallback = null
    }
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
    if (avatarModel.value) {
      avatarModel.value.destroy()
      avatarModel.value = null
    }
    if (renderHost.value) {
      renderHost.value.destroy(true)
      renderHost.value = null
    }
    isModelReady.value = false
    currentModelInfo.value = null
    availableMotions.value = []
    availableExpressions.value = []
  }

  onUnmounted(() => {
    teardown()
  })

  return {
    renderHost,
    avatarModel,
    isLoading,
    loadError,
    isModelReady,
    activeEmotionState,
    padVector,
    currentModelInfo,
    availableMotions,
    availableExpressions,
    avatarScale,
    mountAvatar,
    mountAvatarFromModelInfo,
    triggerMotion,
    applyExpression,
    syncLipParam,
    syncLipVowel,
    driveEmotion,
    drivePadEmotion,
    driveLimbParam,
    driveFaceParam,
    resetAvatarPose,
    adjustAvatarScale,
    teardown
  }
}
