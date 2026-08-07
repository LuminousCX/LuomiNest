/**
 * useAvatarStageRenderer - 统一 Stage 驱动接口
 *
 * 问题：
 * - Live2D 模式：AvatarView 直接调用 useLuomiNestLive2D 的返回值
 * - Pixel 模式：PixelPetStage 通过 defineExpose 暴露驱动方法
 * - VRM/Spine/PNG：未来各自的 Stage 组件
 *
 * 不同模式的驱动方法获取方式不同，TTS 引擎和 chat stream 需要统一的调用入口。
 * 本 composable 提供统一的路由层：根据 currentMode 把驱动调用转发到当前激活的 Stage。
 *
 * 设计：
 * - Live2D：AvatarView 直接传入 useLuomiNestLive2D 的返回值
 * - Pixel/VRM/...：通过 stageRef 获取 defineExpose 的方法
 * - 所有驱动方法均为 no-op safe（未就绪时静默忽略）
 *
 * 使用方式：
 * ```ts
 * const stageRenderer = useAvatarStageRenderer()
 * // Live2D 模式：设置 live2dDriver
 * stageRenderer.setLive2DDriver(live2dComposable)
 * // Pixel 模式：设置 stageRef
 * stageRenderer.setStageRef(pixelStageRef)
 * // 统一调用
 * stageRenderer.driveEmotion('happy')
 * stageRenderer.syncLipParam(0.8)
 * ```
 */
import { ref, shallowRef, type ShallowRef } from 'vue'
import { createLuomiNestRendererLogger } from '@/utils/logger'
import type { AvatarRendererType } from '@/types/avatar'

const logger = createLuomiNestRendererLogger('StageRenderer')

// ---------------------------------------------------------------------------
// Stage 组件暴露的驱动接口（与 IAvatarRenderer 的驱动方法对齐）
// ---------------------------------------------------------------------------

export interface StageDriver {
  driveEmotion(emotionId: string): Promise<void> | void
  drivePadEmotion(pleasure: number, arousal: number, dominance: number): void
  syncLipParam(value: number): void
  syncLipVowel(vowel: string): void
  triggerMotion(group: string, index?: number): Promise<void> | void
  triggerExpression(name: string): Promise<void> | void
  resetPose(): Promise<void> | void
  isReady(): boolean
}

// ---------------------------------------------------------------------------
// useLuomiNestLive2D 返回值的子集（仅驱动相关）
// ---------------------------------------------------------------------------

export interface Live2DDriver {
  driveEmotion(emotionId: string): Promise<void>
  drivePadEmotion(pleasure: number, arousal: number, dominance: number): void
  syncLipParam(value: number): void
  syncLipVowel(vowel: string): void
  triggerMotion(group: string, index?: number): Promise<void>
  triggerExpression(name: string): Promise<void>
  resetPose(): Promise<void>
  isReady(): boolean
}

// ---------------------------------------------------------------------------
// Composable
// ---------------------------------------------------------------------------

export function useAvatarStageRenderer() {
  /** 当前模式（由 useAvatarWorkshop 同步） */
  const currentMode = ref<AvatarRendererType>('live2d')

  /** Live2D 驱动（直接持有 useLuomiNestLive2D 返回值） */
  const live2dDriver = shallowRef<Live2DDriver | null>(null)

  /** 其他 Stage 的组件 ref（PixelPetStage / VrmStage 等） */
  const stageRef = shallowRef<StageDriver | null>(null)

  // -------------------------------------------------------------------------
  // 设置器
  // -------------------------------------------------------------------------

  /** 设置当前模式（切换时由 AvatarView 调用） */
  function setMode(mode: AvatarRendererType): void {
    currentMode.value = mode
    logger.debug(`Stage renderer mode set to ${mode}`)
  }

  /** Live2D 模式：注入 useLuomiNestLive2D 返回值 */
  function setLive2DDriver(driver: Live2DDriver | null): void {
    live2dDriver.value = driver
    logger.debug('Live2D driver set', { hasDriver: !!driver })
  }

  /** Pixel/VRM 模式：注入 Stage 组件 ref（通过 defineExpose 暴露的驱动接口） */
  function setStageRef(ref: ShallowRef<StageDriver | null> | StageDriver | null): void {
    if (ref && 'value' in ref) {
      stageRef.value = ref.value
    } else {
      stageRef.value = ref as StageDriver | null
    }
    logger.debug('Stage ref set', { hasRef: !!stageRef.value })
  }

  // -------------------------------------------------------------------------
  // 统一驱动接口（no-op safe）
  // -------------------------------------------------------------------------

  /** 获取当前激活的驱动器 */
  function getActiveDriver(): StageDriver | Live2DDriver | null {
    if (currentMode.value === 'live2d') {
      return live2dDriver.value
    }
    return stageRef.value
  }

  async function driveEmotion(emotionId: string): Promise<void> {
    const driver = getActiveDriver()
    if (!driver) {
      logger.debug('driveEmotion: no active driver', { mode: currentMode.value })
      return
    }
    try {
      await driver.driveEmotion(emotionId)
    } catch (err) {
      logger.warn('driveEmotion failed', err)
    }
  }

  function drivePadEmotion(pleasure: number, arousal: number, dominance: number): void {
    const driver = getActiveDriver()
    if (!driver) return
    try {
      driver.drivePadEmotion(pleasure, arousal, dominance)
    } catch (err) {
      logger.warn('drivePadEmotion failed', err)
    }
  }

  function syncLipParam(value: number): void {
    const driver = getActiveDriver()
    if (!driver) return
    try {
      driver.syncLipParam(value)
    } catch (err) {
      logger.warn('syncLipParam failed', err)
    }
  }

  function syncLipVowel(vowel: string): void {
    const driver = getActiveDriver()
    if (!driver) return
    try {
      driver.syncLipVowel(vowel)
    } catch (err) {
      logger.warn('syncLipVowel failed', err)
    }
  }

  async function triggerMotion(group: string, index: number = 0): Promise<void> {
    const driver = getActiveDriver()
    if (!driver) return
    try {
      await driver.triggerMotion(group, index)
    } catch (err) {
      logger.warn('triggerMotion failed', err)
    }
  }

  async function triggerExpression(name: string): Promise<void> {
    const driver = getActiveDriver()
    if (!driver) return
    try {
      await driver.triggerExpression(name)
    } catch (err) {
      logger.warn('triggerExpression failed', err)
    }
  }

  async function resetPose(): Promise<void> {
    const driver = getActiveDriver()
    if (!driver) return
    try {
      await driver.resetPose()
    } catch (err) {
      logger.warn('resetPose failed', err)
    }
  }

  function isReady(): boolean {
    const driver = getActiveDriver()
    if (!driver) return false
    try {
      return driver.isReady()
    } catch {
      return false
    }
  }

  return {
    currentMode,
    // 设置器
    setMode,
    setLive2DDriver,
    setStageRef,
    // 统一驱动接口
    driveEmotion,
    drivePadEmotion,
    syncLipParam,
    syncLipVowel,
    triggerMotion,
    triggerExpression,
    resetPose,
    isReady,
  }
}
