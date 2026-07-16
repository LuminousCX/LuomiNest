/**
 * IAvatarRenderer - 统一 Avatar 渲染器接口
 *
 * 所有模型类型（Live2D / VRM / Pixel / Spine / PNG）都实现此接口，
 * 上层（AvatarView / DesktopPetView）通过统一接口驱动不同模型。
 *
 * 设计原则：
 * - 接口签名与现有 useLuomiNestLive2D 返回值完全兼容（async/Promise）
 * - 不支持的能力调用应静默忽略（no-op），不抛异常
 * - 渲染器实例与 canvas 1:1 绑定，切换模型时销毁旧实例
 * - Live2D 不修改原 useLuomiNestLive2D，通过 Live2DRendererAdapter 适配
 */
import type { AvatarCapability, AvatarRendererType } from '@/types/avatar'

export interface IAvatarRenderer {
  /** 渲染器类型 */
  readonly type: AvatarRendererType
  /** 当前模型 ID */
  readonly modelId: string

  // ------------------------------------------------------------------
  // 生命周期
  // ------------------------------------------------------------------

  /** 加载模型
   * @param url 模型资源 URL（luominest-avatar:// 协议或 https URL）
   * @param opts.scale 缩放比例（默认 0.25，与 Live2D 默认一致）
   */
  loadModel(url: string, opts?: { scale?: number }): Promise<void>

  /** 销毁渲染器，释放 WebGL/PixiJS 资源 */
  destroy(): void

  // ------------------------------------------------------------------
  // 驱动接口（与 useLuomiNestLive2D 对齐）
  // ------------------------------------------------------------------

  /** 触发动作
   * @param group 动作组名（如 'TapBody' / 'Idle'）
   * @param index 动作索引（默认 0）
   */
  triggerMotion(group: string, index?: number): Promise<void>

  /** 触发表情（原生表情名，不经 expression_map 转换） */
  triggerExpression(name: string): Promise<void>

  /** 驱动语义情绪（12 个 SUPPORTED_EMOTION_IDS 之一）
   * 渲染器内部通过 expression_map 解析为原生表情名
   */
  driveEmotion(emotionId: string): Promise<void>

  /** 驱动 PAD 连续情感值
   * 不支持 PAD 的模型（如 Pixel）静默忽略
   */
  drivePadEmotion(pleasure: number, arousal: number, dominance: number): void

  /** 同步口型开合值 [0, 1] */
  syncLipParam(value: number): void

  /** 同步口型元音（a/i/u/e/o 或 VRM viseme） */
  syncLipVowel(vowel: string): void

  /** 直设核心参数（如 ParamAngleX），不支持 customParams 的模型静默忽略 */
  setCoreParam(paramId: string, value: number): void

  /** 重置姿态到默认 */
  resetPose(): Promise<void>

  // ------------------------------------------------------------------
  // 状态查询
  // ------------------------------------------------------------------

  /** 获取模型能力声明 */
  getCapabilities(): AvatarCapability

  /** 模型是否已加载就绪 */
  isReady(): boolean
}
