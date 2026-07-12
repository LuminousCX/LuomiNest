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
import { Ticker } from 'pixi.js'

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
  getModel: () => LuomiNestLive2DModel | null
): { cleanup: () => void } => {
  const startTime = Date.now()

  const callback = () => {
    const model = getModel()
    if (!model) return
    const access = getLuomiNestCoreModel(model)
    if (!access) return

    try {
      const { coreModel } = access

      // Keep watermark hidden every frame (Param14 = 1)
      const param14Idx = coreModel.getParameterIndex('Param14')
      if (param14Idx >= 0) {
        coreModel.setParameterValueByIndex(param14Idx, 1)
      }

      // Gentle body sway using layered sine waves for natural idle movement
      const t = (Date.now() - startTime) / 1000
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
