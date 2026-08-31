import { defineStore } from 'pinia'
import { computed } from 'vue'
import { useSectionSettings } from '../composables/useSectionSettings'
import { useThemeStore } from './theme'

/**
 * 皮套工坊舞台背景设置
 *
 * - 状态通过 useSectionSettings 持久化到 localStorage
 *   （键：luominest-settings:avatar-stage-bg，与其他设置分区约定一致）
 * - 自定义图片复用外观主题的上传链路：dialog:selectBackgroundImage
 *   将图片复制到 userData/Backgrounds 并返回 luominest-bg:// 协议 URL。
 *   开发/生产环境 userData 目录天然隔离，与设置页皮肤图片同一套机制。
 */

export type StageBackgroundMode = 'default' | 'color' | 'image'

/** 快速替换用的预设底色 */
export const STAGE_BG_PRESET_COLORS = [
  { id: 'red', hex: '#E8604C' },
  { id: 'yellow', hex: '#F5B940' },
  { id: 'green', hex: '#4FB286' }
] as const

export type StageBgUploadResult =
  | { success: true; url: string; width: number; height: number; warning?: string }
  | { success: false; error?: string; cancelled?: boolean }

type StageBackgroundState = {
  mode: StageBackgroundMode
  color: string | null
  imageUrl: string | null
}

export const useStageBackgroundStore = defineStore('avatar-stage-background', () => {
  // ─── 持久化状态（luominest-settings:avatar-stage-bg） ───
  const settings = useSectionSettings<StageBackgroundState>('avatar-stage-bg', {
    mode: 'default',
    color: null,
    imageUrl: null
  })

  // ─── 归一化：历史数据可能写入非法 mode，加载时收敛到 default ───
  if (settings.mode !== 'default' && settings.mode !== 'color' && settings.mode !== 'image') {
    settings.mode = 'default'
  }

  /**
   * 应用到 .stage-canvas 容器的 CSS background 值。
   * 三种舞台（Live2D/Pixel/PNG）的渲染画布均为透明底（backgroundAlpha: 0），
   * 直接覆盖容器背景即可，无需触碰渲染器。
   * 空字符串表示使用组件自带的默认渐变底。
   */
  const backgroundStyle = computed<string>(() => {
    if (settings.mode === 'color' && settings.color) {
      // 叠加一层极淡的中心提亮，避免纯色底过于呆板
      return `radial-gradient(circle at 50% 42%, rgba(255, 255, 255, 0.16) 0%, rgba(255, 255, 255, 0) 62%), ${settings.color}`
    }
    if (settings.mode === 'image' && settings.imageUrl) {
      return `url("${settings.imageUrl}") center / cover no-repeat`
    }
    return ''
  })

  // ─── Actions ─────────────────────────────────

  function applyColor(color: string): void {
    settings.mode = 'color'
    settings.color = color
  }

  function applyImage(url: string): void {
    settings.mode = 'image'
    settings.imageUrl = url
  }

  function reset(): void {
    settings.mode = 'default'
  }

  /**
   * 上传自定义背景图片（一次仅保留一张）。
   *
   * 复用外观主题的 dialog:selectBackgroundImage：主进程弹出文件选择框，
   * 校验格式/大小后复制到 userData/Backgrounds，返回 luominest-bg:// URL。
   * 上传成功后自动清理上一张不再被引用的图片文件。
   */
  async function uploadImage(): Promise<StageBgUploadResult> {
    const api = window.api?.dialog
    if (!api) {
      return { success: false, error: '当前环境不可用' }
    }

    const result = await api.selectBackgroundImage()
    if (!result.success) {
      return result
    }
    if (typeof result.url !== 'string' || !result.url.startsWith('luominest-bg:')) {
      console.error('[StageBackground] invalid background url:', result.url)
      return { success: false, error: '背景图片地址格式异常' }
    }

    const previous = settings.imageUrl
    settings.imageUrl = result.url
    settings.mode = 'image'

    if (previous && previous !== result.url) {
      void deleteImageFileIfUnused(previous)
    }
    return result
  }

  /**
   * 清理不再使用的背景图片文件。
   * 图片与外观主题皮肤共用 userData/Backgrounds 目录，
   * 删除前检查是否仍被主题皮肤引用，避免误删共享资源。
   */
  async function deleteImageFileIfUnused(url: string): Promise<void> {
    try {
      const themeStore = useThemeStore()
      const referencedBySkin = themeStore.allSkins.some((s) => s.background.image === url)
      if (referencedBySkin) return
      await window.api?.dialog.deleteBackgroundImage(url)
    } catch {
      // 删除失败不阻断主流程，残留文件可由后续清理回收
    }
  }

  return {
    settings,
    backgroundStyle,
    applyColor,
    applyImage,
    reset,
    uploadImage
  }
})
