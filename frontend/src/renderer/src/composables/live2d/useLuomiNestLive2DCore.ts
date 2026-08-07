/**
 * LuomiNest Live2D 共享核心
 *
 * 提取 useLuomiNestLive2D.ts（应用内 canvas）与 DesktopPetView.vue（独立窗口）
 * 约 60% 重复的纯模型操作逻辑，作为唯一真相源。
 *
 * 两个消费者交互模型不同（canvas 拖拽 vs IPC 窗口拖拽），但以下操作与窗口/canvas 无关：
 * - cubism4 动态加载
 * - isInteractive 修补
 * - internalModel 类型化访问（消除 internalModel as any）
 * - 模型能力扫描（motions/expressions）
 * - 水印隐藏
 * - idle 动画（每帧保持水印 + 身体摇摆）
 * - PAD 情绪映射
 *
 * 约束：保持动态 import cubism4（静态 import 会在 Live2DCubismCore 未就绪时抛错）。
 */
import { Ticker, Application } from 'pixi.js'
import type { Ref } from 'vue'

/* ============================================================================
 * 常量
 * ========================================================================== */

/** 表达式过滤词（水印/版权相关，不展示给用户） */
export const EXPRESSION_BLOCKLIST = ['水印', 'watermark', 'copyright', 'credit', 'logo']

/* ============================================================================
 * 类型定义（替代 internalModel as any）
 * ========================================================================== */

/** cubism4 模块的 Live2DModel 构造器类型 */
type CubismLive2DModelCtor = typeof import('pixi-live2d-display-mulmotion/cubism4').Live2DModel
/** Live2DModel 实例类型 */
export type LuomiNestLive2DModel = InstanceType<CubismLive2DModelCtor>

/**
 * Live2D Cubism Core 模型最小接口。
 * Live2DCubismCore 是第三方原生库（无 TS 类型声明），此处定义所需方法签名。
 */
export interface LuomiNestCubismCoreModel {
  getParameterIndex: (id: string) => number
  setParameterValueByIndex: (index: number, value: number) => void
  setParameterValueById: (id: string, value: number) => void
  getParameterValueByIndex: (index: number) => number
}

/** Live2D 模型 settings（最小接口，仅包含扫描所需字段） */
export interface LuomiNestLive2DSettings {
  motions?: Record<string, unknown[]>
  expressions?: Array<{ Name?: string }>
  displayInfo?: { Parameters?: Array<{ Id: string; Name?: string }> }
}

/** Live2DModel.internalModel（最小接口） */
interface LuomiNestInternalModel {
  coreModel?: LuomiNestCubismCoreModel
  settings?: LuomiNestLive2DSettings
  destroyed?: boolean
}

/** getLuomiNestCoreModel 返回的类型化访问器 */
export interface LuomiNestCoreModelAccess {
  coreModel: LuomiNestCubismCoreModel
  settings: LuomiNestLive2DSettings
}

/* ============================================================================
 * cubism4 动态加载
 * ========================================================================== */

let live2DModelCtor: CubismLive2DModelCtor | null = null

/**
 * 延迟加载 cubism4 模块。
 *
 * cubism4 顶层会在 window.Live2DCubismCore 未定义时同步 throw。
 * Cubism Core 由 index.html 的同步 <script> 加载，在 import 前已就绪。
 * 若脚本加载失败，此处主动抛出友好错误。
 */
export const loadCubism4Module = async (): Promise<CubismLive2DModelCtor> => {
  if (live2DModelCtor) return live2DModelCtor
  const core = (window as unknown as { Live2DCubismCore?: unknown }).Live2DCubismCore
  if (typeof core === 'undefined') {
    throw new Error('Live2DCubismCore 未加载，请检查 cubism-core/live2dcubismcore.min.js 是否存在')
  }
  const mod = await import('pixi-live2d-display-mulmotion/cubism4')
  live2DModelCtor = mod.Live2DModel
  return live2DModelCtor
}

/* ============================================================================
 * isInteractive 修补
 * ========================================================================== */

/**
 * 递归修补 PIXI 容器的 isInteractive 方法。
 *
 * 某些 PIXI 版本的 isInteractive 实现不兼容 pixi-live2d-display 的事件系统，
 * 需要重写为基于 eventMode 的判断。
 *
 * @param obj - PIXI 显示对象（类型宽松，因为 PIXI Container 无精确类型导出）
 */
export const patchIsInteractive = (obj: {
  isInteractive?: () => boolean
  eventMode?: string
  children?: unknown[]
}): void => {
  if (!obj) return
  if (typeof obj.isInteractive !== 'function') {
    obj.isInteractive = function (this: { eventMode?: string }) {
      return this.eventMode === 'static' || this.eventMode === 'dynamic'
    }
  }
  if (Array.isArray(obj.children)) {
    for (const child of obj.children) {
      patchIsInteractive(child as Parameters<typeof patchIsInteractive>[0])
    }
  }
}

/* ============================================================================
 * internalModel 类型化访问
 * ========================================================================== */

/**
 * 类型化访问 Live2DModel.internalModel，消除所有 `internalModel as any`。
 *
 * @param model - Live2DModel 实例
 * @returns coreModel + settings 访问器，若不可用返回 null
 */
export const getLuomiNestCoreModel = (
  model: LuomiNestLive2DModel | null | undefined
): LuomiNestCoreModelAccess | null => {
  if (!model) return null
  try {
    // pixi-live2d-display 库的 internalModel.coreModel 类型声明为 {}，
    // 此处断言为 LuomiNestInternalModel 以类型化访问（消除 internalModel as any）。
    const internal = model.internalModel as unknown as LuomiNestInternalModel
    if (!internal?.coreModel) return null
    return {
      coreModel: internal.coreModel,
      settings: internal.settings ?? {}
    }
  } catch {
    return null
  }
}

/**
 * 检查 Live2DModel 是否已销毁（异步等待期间可能被销毁）。
 */
export const isLuomiNestModelDestroyed = (
  model: LuomiNestLive2DModel | null | undefined
): boolean => {
  if (!model) return true
  try {
    const internal = model.internalModel as unknown as LuomiNestInternalModel
    return internal?.destroyed === true
  } catch {
    return true
  }
}

/* ============================================================================
 * 模型能力扫描
 * ========================================================================== */

/**
 * 扫描 Live2D 模型的动作和表情列表。
 *
 * @param model - Live2DModel 实例
 * @returns { motions, expressions }，过滤水印相关表达式
 */
export const scanLuomiNestModelCapabilities = (
  model: LuomiNestLive2DModel
): { motions: string[]; expressions: string[] } => {
  const motions: string[] = []
  const expressions: string[] = []
  const access = getLuomiNestCoreModel(model)
  if (!access) return { motions, expressions }

  try {
    if (access.settings.motions) {
      for (const group of Object.keys(access.settings.motions)) {
        motions.push(group)
      }
    }
    if (access.settings.expressions) {
      for (const exp of access.settings.expressions) {
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
  return { motions, expressions }
}

/* ============================================================================
 * 水印隐藏
 * ========================================================================== */

/**
 * 隐藏 Live2D 模型水印。
 *
 * Param14 通常是"去掉水印"参数，设为 1 隐藏。
 * 同时扫描 displayInfo.Parameters 查找其他水印相关参数。
 *
 * @param model - Live2DModel 实例
 */
export const hideLuomiNestWatermark = (model: LuomiNestLive2DModel): void => {
  const access = getLuomiNestCoreModel(model)
  if (!access) return

  try {
    const { coreModel, settings } = access

    // Param14 is "去掉水印" (Remove Watermark) - set to 1 to hide
    const param14Idx = coreModel.getParameterIndex('Param14')
    if (param14Idx >= 0) {
      coreModel.setParameterValueByIndex(param14Idx, 1)
    }

    // Scan displayInfo for other watermark-related parameters
    const parameters = settings.displayInfo?.Parameters
    if (parameters) {
      for (const param of parameters) {
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
    // intentionally ignored: expected non-fatal error
  }
}

/* ============================================================================
 * Idle 动画
 * ========================================================================== */

/**
 * 创建 idle 动画 ticker callback。
 *
 * 每帧：
 * 1. 保持水印隐藏（Param14 = 1）
 * 2. 身体摇摆（ParamBodyAngleX/Y/Z 的分层正弦波）
 *
 * @param getModel - 获取当前模型的函数（返回值可能为 null）
 * @returns cleanup 函数（移除 ticker）
 */
export const setupLuomiNestIdleAnimation = (
  getModel: () => LuomiNestLive2DModel | null,
  fps: number = 30
): { cleanup: () => void } => {
  const startTime = Date.now()
  const targetFps = Ticker.targetFPMS ? 1 / Ticker.targetFPMS : 60
  const frameSkip = Math.max(1, Math.round(targetFps / fps))
  let frameCount = 0

  // Cache parameter indices outside the per-frame callback to avoid repeated string lookups
  let param14Index = -1
  let bodyAngleXIndex = -1
  let bodyAngleYIndex = -1
  let bodyAngleZIndex = -1
  let indicesCached = false

  const callback = () => {
    frameCount++
    if (frameCount % frameSkip !== 0) return

    const model = getModel()
    if (!model) return
    const access = getLuomiNestCoreModel(model)
    if (!access) return

    try {
      const { coreModel } = access

      // Lazily cache parameter indices on first frame with a valid model
      if (!indicesCached) {
        param14Index = coreModel.getParameterIndex('Param14')
        bodyAngleXIndex = coreModel.getParameterIndex('ParamBodyAngleX')
        bodyAngleYIndex = coreModel.getParameterIndex('ParamBodyAngleY')
        bodyAngleZIndex = coreModel.getParameterIndex('ParamBodyAngleZ')
        indicesCached = true
      }

      // Keep watermark hidden every frame (Param14 = 1)
      if (param14Index >= 0) {
        coreModel.setParameterValueByIndex(param14Index, 1)
      }

      // Gentle body sway using layered sine waves for natural idle movement
      const t = (Date.now() - startTime) / 1000

      if (bodyAngleXIndex >= 0) {
        coreModel.setParameterValueByIndex(bodyAngleXIndex, Math.sin(t * 0.6) * 3 + Math.sin(t * 1.2) * 0.8)
      }
      if (bodyAngleYIndex >= 0) {
        coreModel.setParameterValueByIndex(bodyAngleYIndex, Math.sin(t * 0.4 + 1.5) * 2.5)
      }
      if (bodyAngleZIndex >= 0) {
        coreModel.setParameterValueByIndex(bodyAngleZIndex, Math.sin(t * 0.5 + 3) * 2)
      }
    } catch {
      // intentionally ignored: expected non-fatal error
    }
  }

  Ticker.shared.add(callback)

  return {
    cleanup: () => {
      Ticker.shared.remove(callback)
    }
  }
}

/* ============================================================================
 * PAD 情绪映射
 * ========================================================================== */

/**
 * PAD（Pleasure-Arousal-Dominance）情绪向量映射为情绪字符串。
 *
 * 用于桌面宠物：收到 PAD 向量后映射为情绪 ID，再通过 resolveExpression 解析为模型表情名。
 *
 * @param pleasure - 愉悦度 [-1, 1]
 * @param arousal - 唤醒度 [-1, 1]
 * @param dominance - 支配度 [-1, 1]
 * @returns 情绪 ID（happy/angry/sad/surprise/love/awkward/curious/think/neutral）
 */
export const mapLuomiNestPadToEmotion = (
  pleasure: number,
  arousal: number,
  dominance: number
): string => {
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

/* ============================================================================
 * GPU 检测
 * ========================================================================== */

export type LuomiNestGpuType = 'discrete' | 'integrated' | 'software' | 'unknown'

export interface LuomiNestGpuInfo {
  type: LuomiNestGpuType
  renderer: string
  webglAvailable: boolean
}

/**
 * 检测当前设备的 GPU 类型与 WebGL 可用性。
 *
 * 通过创建临时 WebGL context 读取 UNMASKED_RENDERER 字符串判断：
 * - discrete: 独立显卡（NVIDIA / AMD / Radeon / GeForce / Quadro）
 * - integrated: 核显（Intel HD/UHD/Iris、Apple M、Mali、Adreno、PowerVR）
 * - software: 软件渲染（SwiftShader / LLVMpipe / Microsoft Basic Render）
 * - unknown: 无法识别（按核显处理）
 *
 * Live2D（pixi-live2d-display）强依赖 WebGL，PixiJS 7 已移除 Canvas 2D 渲染器，
 * 纯软件渲染无法正常运行。
 *
 * @returns GPU 信息
 */
export const detectLuomiNestGpu = (): LuomiNestGpuInfo => {
  try {
    const canvas = document.createElement('canvas')
    const gl = (canvas.getContext('webgl2') || canvas.getContext('webgl')) as WebGLRenderingContext | null
    if (!gl) return { type: 'software', renderer: 'No WebGL context', webglAvailable: false }

    const debugInfo = gl.getExtension('WEBGL_debug_renderer_info')
    const renderer = debugInfo
      ? String(gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL))
      : String(gl.getParameter(gl.RENDERER) || 'Unknown')

    const lower = renderer.toLowerCase()
    let type: LuomiNestGpuType = 'unknown'

    if (
      lower.includes('swiftshader') ||
      lower.includes('llvmpipe') ||
      lower.includes('software') ||
      lower.includes('microsoft basic')
    ) {
      type = 'software'
    } else if (
      lower.includes('nvidia') ||
      lower.includes('amd') ||
      lower.includes('radeon') ||
      lower.includes('geforce') ||
      lower.includes('quadro')
    ) {
      type = 'discrete'
    } else if (
      lower.includes('intel') ||
      lower.includes('hd graphics') ||
      lower.includes('uhd graphics') ||
      lower.includes('iris') ||
      lower.includes('apple m') ||
      lower.includes('mali') ||
      lower.includes('adreno') ||
      lower.includes('powervr')
    ) {
      type = 'integrated'
    }

    return { type, renderer, webglAvailable: true }
  } catch {
    return { type: 'software', renderer: 'Detection failed', webglAvailable: false }
  }
}

/* ============================================================================
 * PixiJS Application 初始化（GPU 检测 + 智能降级）
 * ========================================================================== */

export interface InitPixiOptions {
  canvasRef: Ref<HTMLCanvasElement | null>
  /** 额外配置（如 resizeTo、preserveDrawingBuffer） */
  extraConfig?: Record<string, unknown>
  /** 错误回调：设置外部 error ref */
  onError?: (msg: string) => void
  /** 日志 logger */
  logger?: { info: (msg: string) => void; warn: (msg: string, err?: unknown) => void; error: (msg: string) => void }
}

/**
 * 初始化 PixiJS Application（GPU 检测 + 智能降级）。
 *
 * 策略：
 * 1. 检测 GPU 类型（独显/核显/软件渲染）与 WebGL 可用性
 * 2. Live2D 依赖 WebGL：若 WebGL 不可用，直接报错（PixiJS 7 无 Canvas 2D 渲染器，无法降级）
 * 3. powerPreference：独显用 high-performance 优先调用独显；核显/未知用 default，
 *    避免在核显设备上强制切换独显造成的延迟与功耗
 * 4. 性能优化：软件渲染时降低 resolution（1x）并关闭 antialias 减轻 CPU 负担；
 *    正常设备 resolution 上限 2x（devicePixelRatio）
 *
 * 两个 Live2D composable 共享此逻辑。
 */
const isCanvasConnected = (canvas: HTMLCanvasElement | null | undefined): boolean =>
  Boolean(canvas && canvas.isConnected && canvas.parentElement)

export const initLuomiNestPixiApp = (
  existingApp: Application | null,
  opts: InitPixiOptions
): Application | null => {
  const canvas = opts.canvasRef.value

  // 如果已有 App 但 canvas 已被移除（页面切换/条件渲染），必须销毁旧 App 重新创建，
  // 否则 Pixi 会尝试在一个已脱离 DOM 的 canvas 上渲染，导致后续所有模型加载失败。
  if (existingApp && !isCanvasConnected(existingApp.view as HTMLCanvasElement | undefined)) {
    try {
      existingApp.destroy(true)
    } catch {
      // intentionally ignored
    }
    existingApp = null
  }

  if (existingApp) return existingApp

  if (!isCanvasConnected(canvas)) {
    opts.logger?.error('Canvas element not found or not attached to DOM')
    opts.onError?.('Canvas element not available')
    return null
  }

  const gpu = detectLuomiNestGpu()

  // Live2D（pixi-live2d-display）强依赖 WebGL，PixiJS 7 已移除 Canvas 2D 渲染器，
  // 若 WebGL 不可用则无法渲染，直接报错而非无效降级。
  if (!gpu.webglAvailable) {
    const msg = '当前设备不支持 WebGL，Live2D 无法渲染，请检查显卡驱动或硬件加速是否开启。'
    opts.onError?.(msg)
    opts.logger?.error(`WebGL not available: ${gpu.renderer}`)
    return null
  }

  // 独显用 high-performance 优先调用独显；核显/未知用 default 避免切换独显的延迟
  const powerPreference: 'high-performance' | 'default' =
    gpu.type === 'discrete' ? 'high-performance' : 'default'

  // 软件渲染降级画质（降低 resolution、关闭抗锯齿），减轻 CPU 负担
  const isSoftware = gpu.type === 'software'
  const resolution = isSoftware ? 1 : Math.min(window.devicePixelRatio || 1, 2)
  const antialias = !isSoftware

  const baseConfig = {
    view: opts.canvasRef.value,
    autoStart: true,
    backgroundAlpha: 0,
    antialias,
    resolution,
    autoDensity: true,
    ...opts.extraConfig,
  }

  try {
    const app = new Application({
      ...baseConfig,
      powerPreference,
    } as Partial<ConstructorParameters<typeof Application>[0]>)
    opts.logger?.info(`PixiJS initialized (GPU: ${gpu.type} / ${gpu.renderer})`)
    return app
  } catch (webglErr) {
    opts.logger?.warn(
      'WebGL init failed, retry without powerPreference:',
      webglErr instanceof Error ? webglErr.message : webglErr
    )
    try {
      const app = new Application(baseConfig as Partial<ConstructorParameters<typeof Application>[0]>)
      opts.logger?.info(`PixiJS initialized (fallback, GPU: ${gpu.type} / ${gpu.renderer})`)
      return app
    } catch (canvasErr) {
      const message = canvasErr instanceof Error ? canvasErr.message : 'Unknown error'
      opts.onError?.(`图形初始化失败：${message}`)
      opts.logger?.error(`PixiJS init failed: ${message}`)
      return null
    }
  }
}

/* ============================================================================
 * Focus Tracking（焦点跟踪）
 * ========================================================================== */

export interface FocusTrackerOptions {
  /** 阻尼系数（越小越平滑，canvas 模式 0.08，窗口模式 0.12） */
  damping: number
  /** 头部最大角度（canvas 模式 10，窗口模式 15） */
  maxHeadAngle: number
  /** 眼球最大偏移（canvas 模式 0.6，窗口模式 0.5） */
  maxEyeBall: number
  /** 是否混合原参数值（窗口模式用 true，避免覆盖模型自身 idle 动画） */
  blend: boolean
  /** 获取当前模型 */
  getModel: () => LuomiNestLive2DModel | null
  /** 获取目标焦点（归一化 [-1, 1]，鼠标离开时返回 {0,0} 平滑回归中心） */
  getTarget: () => { x: number; y: number }
}

export interface LuomiNestFocusTracker {
  /** 移除 ticker（调用后焦点跟踪停止） */
  cleanup: () => void
}

/**
 * 创建焦点跟踪器。
 *
 * 每帧根据目标焦点值，阻尼插值后驱动头部角度与眼球偏移：
 * - blend=false（canvas 模式）：直接设置参数值，避免反馈循环导致角度跃升
 * - blend=true（窗口模式）：混合原值（头部 60%+40%，眼球 50%+50%），
 *   避免覆盖模型自身的 idle 动画
 *
 * 两个 Live2D composable 共享此逻辑，仅 damping/maxAngle/blend 配置不同。
 * 鼠标离开交互区时，getTarget 返回 {0,0} 使头部平滑回归中心。
 *
 * @returns tracker，含 cleanup 方法
 */
export const createLuomiNestFocusTracker = (
  opts: FocusTrackerOptions,
  fps: number = 30
): LuomiNestFocusTracker => {
  let currentX = 0
  let currentY = 0
  const targetFps = Ticker.targetFPMS ? 1 / Ticker.targetFPMS : 60
  const frameSkip = Math.max(1, Math.round(targetFps / fps))
  let frameCount = 0

  // Cache parameter indices outside the per-frame callback
  let angleXIndex = -1
  let angleYIndex = -1
  let eyeBallXIndex = -1
  let eyeBallYIndex = -1
  let indicesCached = false

  const callback = (): void => {
    frameCount++
    if (frameCount % frameSkip !== 0) return

    const model = opts.getModel()
    if (!model) return

    const target = opts.getTarget()
    currentX += (target.x - currentX) * opts.damping
    currentY += (target.y - currentY) * opts.damping

    const access = getLuomiNestCoreModel(model)
    if (!access) return

    try {
      const { coreModel } = access

      // Lazily cache parameter indices on first frame with a valid model
      if (!indicesCached) {
        angleXIndex = coreModel.getParameterIndex('ParamAngleX')
        angleYIndex = coreModel.getParameterIndex('ParamAngleY')
        eyeBallXIndex = coreModel.getParameterIndex('ParamEyeBallX')
        eyeBallYIndex = coreModel.getParameterIndex('ParamEyeBallY')
        indicesCached = true
      }

      if (opts.blend) {
        // 窗口模式：混合原值，避免覆盖模型 idle 动画
        if (angleXIndex >= 0) {
          const base = coreModel.getParameterValueByIndex(angleXIndex)
          coreModel.setParameterValueByIndex(angleXIndex, base * 0.6 + currentX * opts.maxHeadAngle * 0.4)
        }
        if (angleYIndex >= 0) {
          const base = coreModel.getParameterValueByIndex(angleYIndex)
          coreModel.setParameterValueByIndex(angleYIndex, base * 0.6 + currentY * opts.maxHeadAngle * 0.4)
        }
        if (eyeBallXIndex >= 0) {
          const base = coreModel.getParameterValueByIndex(eyeBallXIndex)
          coreModel.setParameterValueByIndex(eyeBallXIndex, base * 0.5 + currentX * 0.5)
        }
        if (eyeBallYIndex >= 0) {
          const base = coreModel.getParameterValueByIndex(eyeBallYIndex)
          coreModel.setParameterValueByIndex(eyeBallYIndex, base * 0.5 + currentY * 0.5)
        }
      } else {
        // canvas 模式：直接设置，避免反馈循环导致角度跃升到 2 倍目标值
        if (angleXIndex >= 0) {
          coreModel.setParameterValueByIndex(angleXIndex, currentX * opts.maxHeadAngle)
        }
        if (angleYIndex >= 0) {
          coreModel.setParameterValueByIndex(angleYIndex, currentY * opts.maxHeadAngle)
        }
        if (eyeBallXIndex >= 0) {
          coreModel.setParameterValueByIndex(eyeBallXIndex, currentX * opts.maxEyeBall)
        }
        if (eyeBallYIndex >= 0) {
          coreModel.setParameterValueByIndex(eyeBallYIndex, currentY * opts.maxEyeBall)
        }
      }
    } catch {
      // intentionally ignored: expected non-fatal error
    }
  }

  Ticker.shared.add(callback)

  return {
    cleanup: () => {
      Ticker.shared.remove(callback)
    }
  }
}

/* ============================================================================
 * 通用模型操作工具函数
 * ========================================================================== */

/** 触发模型动作（忽略非致命错误） */
export const triggerLuomiNestMotion = async (
  model: LuomiNestLive2DModel | null,
  group: string,
  index: number = 0
): Promise<void> => {
  if (!model || isLuomiNestModelDestroyed(model)) return
  try {
    await model.motion(group, index)
  } catch {
    // intentionally ignored: expected non-fatal error
  }
}

/** 触发模型表情（忽略非致命错误，空名称跳过） */
export const triggerLuomiNestExpression = async (
  model: LuomiNestLive2DModel | null,
  name: string
): Promise<void> => {
  if (!model || isLuomiNestModelDestroyed(model)) return
  if (!name || !name.trim()) return
  try {
    await model.expression(name)
  } catch {
    // intentionally ignored: expression switch failure is non-fatal
  }
}

/** 设置模型核心参数（按 ID） */
export const setLuomiNestCoreParam = (
  model: LuomiNestLive2DModel | null,
  paramId: string,
  value: number
): void => {
  if (!model) return
  const access = getLuomiNestCoreModel(model)
  if (!access) return
  try {
    if (typeof access.coreModel.setParameterValueById === 'function') {
      access.coreModel.setParameterValueById(paramId, value)
    }
  } catch {
    // intentionally ignored: expected non-fatal error
  }
}

/** 重置姿势（回到 Idle 动作 + 隐藏水印） */
export const resetLuomiNestPose = async (
  model: LuomiNestLive2DModel | null
): Promise<void> => {
  await triggerLuomiNestMotion(model, 'Idle', 0)
  if (model) {
    hideLuomiNestWatermark(model)
  }
}
