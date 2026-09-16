/**
 * LuomiNest 浏览器只读快捷操作
 *
 * 从 BrowserView.vue 拆分：收纳截图（手动 + 访问后自动截图）、截图历史、
 * 大图预览、复制/另存、toast 反馈。
 *
 * 只读化说明（2026-09）：原 DevPanel 开关、快速点击/填表、AI 搜索、
 * prompt 对话框等交互能力已随浏览器只读化移除。
 *
 * 依赖关系：不依赖标签页状态；自动截图的触发时机由 BrowserView
 * 监听 activeTab 的 loading 变化后调用 captureScreenshot。
 */
import { ref, type Ref } from 'vue'
import { i18n } from '../i18n'
import { generateId } from '../utils/id'

/** 历史条最大保留张数（本次会话内，FIFO） */
const MAX_HISTORY = 12

/** 截图历史条目 */
export interface ScreenshotHistoryItem {
  id: string
  /** 截图时的页面 URL */
  url: string
  /** 截图时的页面标题 */
  title: string
  /** data URL（base64 PNG） */
  dataUrl: string
  timestamp: number
}

export const useBrowserActions = () => {
  /** 大图预览中的历史条目（null 时不显示弹层） */
  const previewItem: Ref<ScreenshotHistoryItem | null> = ref(null)
  /** 截图历史（新→旧），本次会话内有效 */
  const history = ref<ScreenshotHistoryItem[]>([])
  const toastMessage = ref('')
  const showToast = ref(false)

  let toastTimer: ReturnType<typeof setTimeout> | null = null

  /** 显示 3 秒 toast 反馈 */
  const displayToast = (msg: string): void => {
    if (toastTimer) clearTimeout(toastTimer)
    toastMessage.value = msg
    showToast.value = true
    toastTimer = setTimeout(() => {
      showToast.value = false
      toastTimer = null
    }, 3000)
  }

  /**
   * 截图当前页面并写入历史。
   * @param context 页面上下文（url/title 写入历史条目）
   * @param silent 成功时是否静默（自动截图成功不打扰，失败仍 toast）
   * @returns 成功返回 dataURL，失败返回 null（并 toast）
   */
  const captureScreenshot = async (
    context?: { url?: string; title?: string },
    silent = false
  ): Promise<string | null> => {
    try {
      const result = await window.api?.browserAutomation?.execute('screenshot')
      if (result?.success && result.data?.screenshot) {
        const dataUrl = String(result.data.screenshot)
        const item: ScreenshotHistoryItem = {
          id: generateId('shot'),
          url: context?.url || '',
          title: context?.title || '',
          dataUrl,
          timestamp: Date.now()
        }
        history.value.unshift(item)
        if (history.value.length > MAX_HISTORY) {
          history.value.pop()
        }
        if (!silent) {
          displayToast(i18n.global.t('browser.actions.screenshotOk'))
        }
        return dataUrl
      }
      displayToast(
        i18n.global.t('browser.actions.screenshotFail', {
          msg: result?.error || i18n.global.t('browser.actions.unknownError')
        })
      )
      return null
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e)
      displayToast(i18n.global.t('browser.actions.screenshotError', { msg: message }))
      return null
    }
  }

  /** 打开大图预览 */
  const openScreenshot = (item: ScreenshotHistoryItem): void => {
    previewItem.value = item
  }

  /** 关闭大图预览 */
  const closeScreenshot = (): void => {
    previewItem.value = null
  }

  /** 复制截图到剪贴板（PNG） */
  const copyScreenshot = async (item: ScreenshotHistoryItem): Promise<void> => {
    try {
      const blob = await (await fetch(item.dataUrl)).blob()
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
      displayToast(i18n.global.t('browser.screenshotCopied'))
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e)
      displayToast(i18n.global.t('browser.screenshotCopyFail', { msg: message }))
    }
  }

  /** 另存截图为 PNG 文件 */
  const saveScreenshot = (item: ScreenshotHistoryItem): void => {
    try {
      const ts = new Date(item.timestamp)
        .toISOString()
        .replace(/[:.]/g, '-')
        .replace('T', '_')
        .slice(0, 19)
      const anchor = document.createElement('a')
      anchor.href = item.dataUrl
      anchor.download = `luominest-screenshot-${ts}.png`
      anchor.click()
      displayToast(i18n.global.t('browser.screenshotSaved'))
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e)
      displayToast(i18n.global.t('browser.screenshotSaveFail', { msg: message }))
    }
  }

  /** 卸载时清理 toast 定时器 */
  const cleanup = (): void => {
    if (toastTimer) {
      clearTimeout(toastTimer)
      toastTimer = null
    }
  }

  return {
    history,
    previewItem,
    toastMessage,
    showToast,
    displayToast,
    captureScreenshot,
    openScreenshot,
    closeScreenshot,
    copyScreenshot,
    saveScreenshot,
    cleanup,
  }
}
