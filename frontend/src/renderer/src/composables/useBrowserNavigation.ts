/**
 * LuomiNest 浏览器导航状态
 *
 * 从 BrowserView.vue 拆分：收纳地址栏、前进/后退状态、导航 API 调用、
 * 侧边栏宽度同步。不依赖标签页状态，被 useBrowserTabs 通过 options 回调使用。
 */
import { ref } from 'vue'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('Browser')

export const useBrowserNavigation = () => {
  const addressBar = ref('')
  const canGoBack = ref(false)
  const canGoForward = ref(false)

  let sidebarResizeObserver: ResizeObserver | null = null

  /** 从后端同步当前标签页的导航状态 */
  const syncNavigationState = async (): Promise<void> => {
    try {
      const state = await window.api?.tab.getNavigationState()
      if (state) {
        canGoBack.value = state.canGoBack
        canGoForward.value = state.canGoForward
      }
    } catch (e: unknown) {
      logger.error('Failed to sync navigation state:', e)
      canGoBack.value = false
      canGoForward.value = false
    }
  }

  /** 直接设置导航标志（供 tab:navigation-state IPC 处理器使用） */
  const setNavigationFlags = (back: boolean, forward: boolean): void => {
    canGoBack.value = back
    canGoForward.value = forward
  }

  /** 重置导航状态（切换到首页时调用） */
  const resetNavigation = (): void => {
    setNavigationFlags(false, false)
  }

  const goBack = async (): Promise<void> => {
    try {
      await window.api?.tab.goBack()
    } catch (e: unknown) {
      logger.error('Failed to go back:', e)
    }
  }

  const goForward = async (): Promise<void> => {
    try {
      await window.api?.tab.goForward()
    } catch (e: unknown) {
      logger.error('Failed to go forward:', e)
    }
  }

  /** 监听侧边栏宽度变化，同步到主进程（修复浏览器覆盖左侧导航） */
  const setupSidebarObserver = (): void => {
    const sidebarEl = document.querySelector('.lumi-sidebar')
    if (!sidebarEl) return

    const syncSidebarWidth = (): void => {
      const width = Math.round(sidebarEl.getBoundingClientRect().width)
      if (width > 0) {
        window.api?.tab.setBoundsConfig({ sidebarWidth: width })?.catch((e: unknown) => {
          logger.error('Failed to sync sidebar width:', e)
        })
      }
    }
    syncSidebarWidth()
    sidebarResizeObserver = new ResizeObserver(syncSidebarWidth)
    sidebarResizeObserver.observe(sidebarEl)
  }

  const teardownSidebarObserver = (): void => {
    sidebarResizeObserver?.disconnect()
    sidebarResizeObserver = null
  }

  return {
    addressBar,
    canGoBack,
    canGoForward,
    syncNavigationState,
    resetNavigation,
    setNavigationFlags,
    goBack,
    goForward,
    setupSidebarObserver,
    teardownSidebarObserver,
  }
}
