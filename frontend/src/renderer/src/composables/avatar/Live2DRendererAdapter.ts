/**
 * Live2DRendererAdapter - 适配 useLuomiNestLive2D 到 IAvatarRenderer 接口
 *
 * 设计原则：
 * - 不修改原 useLuomiNestLive2D.ts 一行代码
 * - 仅做接口适配：把 useLuomiNestLive2D 返回值包装为 IAvatarRenderer
 * - 保留原 composable 的响应式状态（isReady/isLoading/error 等），
 *   上层仍可直接访问 ref，本适配器额外提供同步 getter 方法
 *
 * 注意：useLuomiNestLive2D 接收 Ref<HTMLCanvasElement | null>，
 * 而不是直接 canvas，因此本适配器也接收 Ref。
 */
import type { Ref } from 'vue'
import { useLuomiNestLive2D } from '../useLuomiNestLive2D'
import type { AvatarCapability } from '@/types/avatar'
import type { IAvatarRenderer } from './IAvatarRenderer'

export class Live2DRendererAdapter implements IAvatarRenderer {
  readonly type = 'live2d' as const
  readonly modelId: string = ''

  private readonly _inner: ReturnType<typeof useLuomiNestLive2D>

  constructor(canvasRef: Ref<HTMLCanvasElement | null>) {
    this._inner = useLuomiNestLive2D(canvasRef)
  }

  /** 暴露内部响应式状态（上层 AvatarView 可直接使用 ref） */
  get state() {
    return this._inner
  }

  async loadModel(url: string, opts?: { scale?: number }): Promise<void> {
    await this._inner.loadModel(url, opts?.scale ?? 0.25)
  }

  destroy(): void {
    this._inner.destroy()
  }

  async triggerMotion(group: string, index: number = 0): Promise<void> {
    await this._inner.triggerMotion(group, index)
  }

  async triggerExpression(name: string): Promise<void> {
    await this._inner.triggerExpression(name)
  }

  async driveEmotion(emotionId: string): Promise<void> {
    await this._inner.driveEmotion(emotionId)
  }

  drivePadEmotion(pleasure: number, arousal: number, dominance: number): void {
    this._inner.drivePadEmotion(pleasure, arousal, dominance)
  }

  syncLipParam(value: number): void {
    this._inner.syncLipParam(value)
  }

  syncLipVowel(vowel: string): void {
    this._inner.syncLipVowel(vowel)
  }

  setCoreParam(paramId: string, value: number): void {
    this._inner.setCoreParam(paramId, value)
  }

  async resetPose(): Promise<void> {
    await this._inner.resetPose()
  }

  getCapabilities(): AvatarCapability {
    return {
      expressions: this._inner.availableExpressions.value,
      motions: this._inner.availableMotions.value,
      states: null,
      visemes: null,
      lip_sync: true,
      focus_tracking: true,
      pad_emotion: true,
      custom_params: null,
    }
  }

  isReady(): boolean {
    return this._inner.isReady.value
  }
}
