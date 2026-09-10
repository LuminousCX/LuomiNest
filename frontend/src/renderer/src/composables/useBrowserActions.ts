/**
 * LuomiNest 浏览器快捷操作
 *
 * 从 BrowserView.vue 拆分：收纳 DevPanel 开关、截图、快速点击/填表、
 * AI 搜索、toast 反馈等快捷操作。
 *
 * CodeRabbit #5 修复：用应用内 prompt 对话框替代 window.prompt，
 * 避免 Electron 环境下原生 prompt 阻塞与样式不一致问题。
 *
 * 依赖关系：通过 options 接收 tabs composable 的 getActiveTab 回调，
 * 用于判断当前是否有可操作的活跃标签页。
 */
import { ref, watch, type Ref } from 'vue'
import { i18n } from '../i18n'
import { createLuomiNestRendererLogger } from '../utils/logger'
import type { Tab } from './useBrowserTabs'

const logger = createLuomiNestRendererLogger('Browser')

/** DevPanel 暴露给父组件的方法契约 */
export interface DevPanelHandle {
  switchMode: (mode: 'script' | 'dom') => void
}

/** prompt 对话框元数据（CodeRabbit #5） */
export interface PromptState {
  title: string
  placeholder?: string
  resolve: (input: string | null) => void
}

export interface UseBrowserActionsOptions {
  /** 获取当前活动标签页（来自 tabs composable） */
  getActiveTab: () => Tab | undefined
  /** DevPanel 组件实例 ref（由 view 定义并通过 template ref 绑定） */
  devPanelRef: Ref<DevPanelHandle | null>
}

export const useBrowserActions = (options: UseBrowserActionsOptions) => {
  const { getActiveTab, devPanelRef } = options

  const showDevPanel = ref(false)
  const screenshotUrl = ref('')
  const screenshotLoading = ref(false)
  const toastMessage = ref('')
  const showToast = ref(false)
  const promptState = ref<PromptState | null>(null)
  const promptInput = ref('')

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
   * 弹出应用内 prompt 对话框（CodeRabbit #5 替代 window.prompt）
   * @returns 用户输入文本；点击取消或关闭对话框时返回 null
   */
  const showPrompt = (title: string, placeholder?: string): Promise<string | null> => {
    promptInput.value = ''
    return new Promise<string | null>((resolve) => {
      promptState.value = { title, placeholder, resolve }
    })
  }

  /** 用户确认 prompt 输入 */
  const submitPrompt = (): void => {
    const state = promptState.value
    if (!state) return
    const input = promptInput.value
    promptState.value = null
    state.resolve(input)
  }

  /** 用户取消 prompt */
  const cancelPrompt = (): void => {
    const state = promptState.value
    if (!state) return
    promptState.value = null
    state.resolve(null)
  }

  /** 截图当前页面 */
  const captureScreenshot = async (): Promise<void> => {
    if (screenshotLoading.value) return
    screenshotLoading.value = true
    try {
      const result = await window.api?.browserAutomation?.execute('screenshot')
      if (result?.success && result.data?.screenshot) {
        screenshotUrl.value = String(result.data.screenshot)
        displayToast(i18n.global.t('browser.actions.screenshotOk'))
      } else {
        displayToast(i18n.global.t('browser.actions.screenshotFail', { msg: result?.error || i18n.global.t('browser.actions.unknownError') }))
      }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e)
      displayToast(i18n.global.t('browser.actions.screenshotError', { msg: message }))
    } finally {
      screenshotLoading.value = false
    }
  }

  /** 快速点击：弹窗输入选择器后执行点击 */
  const quickClick = async (): Promise<void> => {
    const selector = await showPrompt(
      i18n.global.t('browser.actions.clickPrompt')
    )
    if (!selector) return
    try {
      const result = await window.api?.browserAutomation?.execute('click', { selector })
      if (result?.success) {
        displayToast(i18n.global.t('browser.actions.clickOk'))
      } else {
        displayToast(i18n.global.t('browser.actions.clickFail', { msg: result?.error || i18n.global.t('browser.actions.elementNotFound') }))
      }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e)
      displayToast(i18n.global.t('browser.actions.clickError', { msg: message }))
    }
  }

  /** 快速填表：弹窗输入 selector|text 后执行填表 */
  const quickFill = async (): Promise<void> => {
    const input = await showPrompt(
      i18n.global.t('browser.actions.fillPrompt')
    )
    if (!input) return
    const sep = input.indexOf('|')
    if (sep === -1) {
      displayToast(i18n.global.t('browser.actions.fillFormatError'))
      return
    }
    const selector = input.slice(0, sep)
    const text = input.slice(sep + 1)
    try {
      const result = await window.api?.browserAutomation?.execute('type', {
        selector, text, clear: true
      })
      if (result?.success) {
        displayToast(i18n.global.t('browser.actions.fillOk'))
      } else {
        displayToast(i18n.global.t('browser.actions.fillFail', { msg: result?.error || i18n.global.t('browser.actions.elementNotFound') }))
      }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e)
      displayToast(i18n.global.t('browser.actions.fillError', { msg: message }))
    }
  }

  /** AI 搜索：弹窗输入问题后发送搜索请求 */
  const aiSearch = async (): Promise<void> => {
    const query = await showPrompt(i18n.global.t('browser.actions.searchPrompt'))
    if (!query) return
    try {
      const result = await window.api?.browserSearch?.search(query)
      if (result) {
        displayToast(i18n.global.t('browser.actions.searchSent'))
      } else {
        displayToast(i18n.global.t('browser.actions.searchNoResponse'))
      }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e)
      displayToast(i18n.global.t('browser.actions.searchError', { msg: message }))
    }
  }

  /** 关闭截图预览 */
  const closeScreenshot = (): void => {
    screenshotUrl.value = ''
  }

  /** 快捷操作统一入口（HomePage 触发） */
  const handleQuickAction = async (action: string): Promise<void> => {
    // ai-search 不需要打开网页，其余动作需要先有活跃标签页
    if (action !== 'ai-search' && !getActiveTab()?.url) {
      displayToast(i18n.global.t('browser.actions.needOpenPage'))
      return
    }

    switch (action) {
      case 'script':
        showDevPanel.value = !showDevPanel.value
        if (showDevPanel.value) devPanelRef.value?.switchMode('script')
        break
      case 'screenshot':
        await captureScreenshot()
        break
      case 'dom':
        showDevPanel.value = true
        devPanelRef.value?.switchMode('dom')
        break
      case 'click':
        await quickClick()
        break
      case 'fill':
        await quickFill()
        break
      case 'ai-search':
        await aiSearch()
        break
    }
  }

  // DevPanel 展开/收起时同步高度到主进程 tabManager
  watch(showDevPanel, async (show) => {
    try {
      await window.api?.tab.setBoundsConfig({
        devPanelHeight: show ? 220 : 0
      })
    } catch (e: unknown) {
      logger.error('Failed to set panel height:', e)
    }
  })

  /** 卸载时清理 toast 定时器 */
  const cleanup = (): void => {
    if (toastTimer) {
      clearTimeout(toastTimer)
      toastTimer = null
    }
  }

  return {
    showDevPanel,
    screenshotUrl,
    screenshotLoading,
    toastMessage,
    showToast,
    promptState,
    promptInput,
    displayToast,
    showPrompt,
    submitPrompt,
    cancelPrompt,
    captureScreenshot,
    quickClick,
    quickFill,
    aiSearch,
    closeScreenshot,
    handleQuickAction,
    cleanup,
  }
}
