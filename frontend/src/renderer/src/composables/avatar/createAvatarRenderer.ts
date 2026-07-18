/**
 * createAvatarRenderer - Avatar 渲染器工厂
 *
 * 根据 type 动态创建对应的渲染器实现。使用动态 import 实现懒加载：
 * - Live2D：适配现有 useLuomiNestLive2D（不修改原代码）
 * - VRM：动态加载 Three.js + @pixiv/three-vrm（P1，尚未实现）
 * - Pixel：动态加载 PixiJS AnimatedSprite（P0）
 * - Spine：动态加载 pixi-spine（P2，尚未实现）
 * - PNG：纯 PIXI.Sprite 实现（P2，尚未实现）
 *
 * 懒加载策略：
 * - 同屏只激活一个渲染器，切换时 destroy() 释放 WebGL context
 * - 避免主包包含 Three.js 等大依赖（按需加载）
 */
import type { Ref } from 'vue'
import type { AvatarRendererType } from '@/types/avatar'
import type { IAvatarRenderer } from './IAvatarRenderer'
import { Live2DRendererAdapter } from './Live2DRendererAdapter'

export interface CreateRendererOptions {
  /** canvas 引用（与 useLuomiNestLive2D 一致使用 Ref） */
  canvasRef: Ref<HTMLCanvasElement | null>
  /** 模型 ID（用于日志和绑定查询，可选） */
  modelId?: string
}

export async function createAvatarRenderer(
  type: AvatarRendererType,
  options: CreateRendererOptions,
): Promise<IAvatarRenderer> {
  const { canvasRef } = options

  switch (type) {
    case 'live2d': {
      // Live2D：使用适配器包装现有 useLuomiNestLive2D（不修改原代码）
      return new Live2DRendererAdapter(canvasRef)
    }

    case 'pixel': {
      // 像素模型：动态加载 usePixelPet
      const { usePixelPet } = await import('./usePixelPet')
      return usePixelPet(canvasRef, options.modelId)
    }

    case 'vrm': {
      // VRM：P1 阶段实现，当前抛出明确错误
      // const { useVrmModel } = await import('./useVrmModel')
      // return useVrmModel(canvasRef, options.modelId)
      throw new Error('[createAvatarRenderer] VRM renderer not implemented yet (P1)')
    }

    case 'spine': {
      // Spine：P2 阶段实现
      // const { useSpineModel } = await import('./useSpineModel')
      // return useSpineModel(canvasRef, options.modelId)
      throw new Error('[createAvatarRenderer] Spine renderer not implemented yet (P2)')
    }

    case 'png': {
      // PNG Tuber：基于 pixi.js AnimatedSprite 切换 spritesheet 行（参照 Codex Pet 格式）
      const { usePngTuber } = await import('./usePngTuber')
      return usePngTuber(canvasRef, options.modelId)
    }

    default: {
      const exhaustive: never = type
      throw new Error(`[createAvatarRenderer] Unknown renderer type: ${exhaustive}`)
    }
  }
}
