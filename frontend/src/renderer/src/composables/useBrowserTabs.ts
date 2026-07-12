/**
 * LuomiNest 浏览器标签页管理
 *
 * 从 BrowserView.vue 拆分：收纳标签页状态、CRUD、IPC 事件订阅、
 * taskStream 主 Agent 创建标签页请求监听。
 *
 * 依赖关系：通过 options 接收 navigation composable 的地址栏 ref 与导航回调，
 * 避免直接耦合 navigation 内部状态。
 *
 * CodeRabbit #4 修复：closeTab 关闭非活动标签页时不再强制切换活动标签。
 */
import { ref, computed, watch, type Ref } from 'vue'
import type { TabInfo } from '@shared/ipc-types'
import { useTaskStreamStore } from '../stores/taskStream'
import { generateId } from '../utils/id'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('Browser')

/** 渲染进程标签页模型（基于 TabInfo 精简） */
export interface Tab {
  id: string
  title: string
  url: string
  favicon?: string
  loading?: boolean
  error?: { code: number; title: string; message: string }
  active?: boolean
  captchaDetected?: boolean
  sleeping?: boolean
}

export interface UseBrowserTabsOptions {
  /** 地址栏 ref，由 navigation composable 提供，标签切换时同步 */
  addressBar: Ref<string>
  /** 从后端同步当前标签页导航状态（前进/后退可用性） */
  syncNavigationState: () => Promise<void>
  /** 重置导航状态为不可前进/后退 */
  resetNavigation: () => void
  /** 直接设置导航标志（供 tab:navigation-state IPC 处理器使用） */
  setNavigationFlags: (canBack: boolean, canForward: boolean) => void
}

export const useBrowserTabs = (options: UseBrowserTabsOptions) => {
  const { addressBar, syncNavigationState, resetNavigation, setNavigationFlags } = options
  const taskStreamStore = useTaskStreamStore()

  const tabs = ref<Tab[]>([])
  const showHomePage = ref(true)

  const activeTab = computed<Tab | undefined>(() => tabs.value.find(t => t.active))
  const showCaptchaBanner = computed<boolean>(() =>
    activeTab.value?.captchaDetected === true && activeTab.value?.loading !== true
  )

  /** 从后端同步所有标签页状态（mount 时调用） */
  const syncTabs = async (): Promise<void> => {
    try {
      const allTabs = await window.api?.tab.getAll() || []
      if (allTabs.length === 0) {
        tabs.value = [{ id: 'home', title: '新标签页', url: '', active: true }]
        showHomePage.value = true
      } else {
        tabs.value = allTabs.map((t: TabInfo) => ({
          id: t.id,
          title: t.title || '加载中...',
          url: t.url,
          active: t.active,
          loading: t.loading,
          favicon: t.favicon,
          error: t.error,
          captchaDetected: t.captchaDetected,
          sleeping: t.sleeping
        }))
        const active = tabs.value.find(t => t.active)
        if (active?.url) {
          showHomePage.value = false
          addressBar.value = active.url
          if (!active.sleeping) {
            await syncNavigationState()
          }
        }
      }
    } catch (e: unknown) {
      logger.error('Failed to sync tabs:', e)
      tabs.value = [{ id: 'home', title: '新标签页', url: '', active: true }]
    }
  }

  /** 创建标签页；url 为空时进入首页 */
  const createTab = async (url: string = ''): Promise<void> => {
    tabs.value.forEach(t => t.active = false)

    if (!url) {
      tabs.value.push({ id: generateId('home'), title: '新标签页', url: '', active: true })
      showHomePage.value = true
      addressBar.value = ''
      resetNavigation()
      await window.api?.tab.hideAll()
      return
    }

    showHomePage.value = false
    addressBar.value = url

    try {
      const newTab = await window.api?.tab.create(url)
      if (newTab) {
        tabs.value.push({
          id: newTab.id,
          title: newTab.title || '加载中...',
          url: newTab.url,
          active: true,
          loading: newTab.loading,
          error: newTab.error,
          captchaDetected: newTab.captchaDetected,
          sleeping: newTab.sleeping
        })
      }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e)
      logger.error('Failed to create tab:', e)
      tabs.value.push({
        id: generateId('error'),
        title: '加载失败',
        url,
        active: true,
        error: { code: -1, title: '加载失败', message }
      })
    }
  }

  /** 切换到指定标签页 */
  const selectTab = async (tabId: string): Promise<void> => {
    const tab = tabs.value.find(t => t.id === tabId)
    if (!tab) return

    tabs.value.forEach(t => t.active = t.id === tabId)

    if (tab.url) {
      try {
        if (tab.sleeping) {
          tab.sleeping = false
          tab.loading = true
        }
        await window.api?.tab.activate(tabId)
        showHomePage.value = false
        addressBar.value = tab.url
        await syncNavigationState()
      } catch (e: unknown) {
        logger.error('Failed to switch tab:', e)
      }
    } else {
      showHomePage.value = true
      addressBar.value = ''
      resetNavigation()
      await window.api?.tab.hideAll()
    }
  }

  /**
   * 关闭指定标签页
   * CodeRabbit #4 修复：记录关闭前是否为活动标签，仅当关闭活动标签时才切换到相邻标签。
   * 关闭非活动标签不再强制改变当前活动标签。
   */
  const closeTab = async (tabId: string): Promise<void> => {
    const idx = tabs.value.findIndex(t => t.id === tabId)
    if (idx === -1) return

    const tab = tabs.value[idx]
    const wasActive = tab.active === true
    const isHomeTab = !tab.url

    if (!isHomeTab) {
      try {
        await window.api?.tab.close(tabId)
      } catch (e: unknown) {
        logger.error('Failed to close tab:', e)
      }
    }

    tabs.value.splice(idx, 1)

    // 无剩余标签页 → 回到默认首页
    if (tabs.value.length === 0) {
      tabs.value = [{ id: generateId('home'), title: '新标签页', url: '', active: true }]
      showHomePage.value = true
      addressBar.value = ''
      resetNavigation()
      await window.api?.tab.hideAll()
      return
    }

    // 关闭的是非活动标签 → 无需切换，保持当前活动标签不变
    if (!wasActive) return

    // 关闭的是活动标签 → 切换到相邻标签
    tabs.value.forEach(t => t.active = false)
    const newActiveIdx = Math.min(idx, tabs.value.length - 1)
    const newActiveTab = tabs.value[newActiveIdx]
    newActiveTab.active = true

    if (newActiveTab.url) {
      await selectTab(newActiveTab.id)
    } else {
      showHomePage.value = true
      addressBar.value = ''
      resetNavigation()
      await window.api?.tab.hideAll()
    }
  }

  /** 地址栏导航：若当前是首页标签则替换，否则新建标签 */
  const navigateToUrl = async (url: string): Promise<void> => {
    if (!url.trim()) return

    let normalizedUrl = url.trim()
    if (!normalizedUrl.startsWith('http://') && !normalizedUrl.startsWith('https://')) {
      normalizedUrl = 'https://' + normalizedUrl
    }

    const tab = activeTab.value
    if (tab && !tab.url) {
      // 当前活动标签是首页空标签 → 移除后新建
      const idx = tabs.value.findIndex(t => t.id === tab.id)
      if (idx !== -1) {
        tabs.value.splice(idx, 1)
      }
    }

    await createTab(normalizedUrl)
  }

  /** 刷新当前活动标签页 */
  const refreshTab = async (): Promise<void> => {
    const tab = activeTab.value
    if (!tab?.url) return

    try {
      if (tab.sleeping) {
        tab.sleeping = false
        tab.loading = true
      }
      await window.api?.tab.reload(tab.id)
    } catch (e: unknown) {
      logger.error('Failed to reload tab:', e)
    }
  }

  /**
   * 恢复活动标签页显示（mount 时调用）
   * - 活动且非休眠 → showActive 直接显示
   * - 活动但休眠 → activate 唤醒
   */
  const restoreActiveTab = async (): Promise<void> => {
    const active = tabs.value.find(t => t.active)
    if (!active?.url) return

    try {
      if (active.sleeping) {
        await window.api?.tab.activate(active.id)
      } else {
        await window.api?.tab.showActive()
      }
    } catch (e: unknown) {
      logger.error('Failed to restore active tab:', e)
    }
  }

  // ===== IPC 事件处理器 =====

  const handleTabUpdated = (
    _event: unknown,
    data: { tabId: string; updates: Partial<Tab> }
  ): void => {
    const tab = tabs.value.find(t => t.id === data.tabId)
    if (!tab) return
    Object.assign(tab, data.updates)
    if (tab.active && data.updates.url !== undefined) {
      addressBar.value = data.updates.url
    }
    if (data.updates.sleeping !== undefined && !data.updates.sleeping && tab.active) {
      syncNavigationState()
    }
  }

  const handleNewTabRequest = (_event: unknown, data: { url: string }): void => {
    createTab(data.url)
  }

  const handleNavigationState = (
    _event: unknown,
    data: { tabId: string; canGoBack: boolean; canGoForward: boolean }
  ): void => {
    const tab = tabs.value.find(t => t.id === data.tabId)
    if (tab?.active) {
      setNavigationFlags(data.canGoBack, data.canGoForward)
    }
  }

  /** 订阅主 Agent 通过 create_browser_tab 工具发起的标签页创建请求 */
  watch(
    () => taskStreamStore.pendingBrowserTasks,
    (pendingTasks) => {
      for (const task of pendingTasks) {
        if (task.url) {
          logger.info(`主 Agent 请求打开标签页: ${task.url}`)
          createTab(task.url)
          taskStreamStore.markBrowserTabOpened(task.tab_id)
        }
      }
    },
    { deep: true }
  )

  return {
    tabs,
    showHomePage,
    activeTab,
    showCaptchaBanner,
    syncTabs,
    createTab,
    selectTab,
    closeTab,
    navigateToUrl,
    refreshTab,
    restoreActiveTab,
    handleTabUpdated,
    handleNewTabRequest,
    handleNavigationState,
  }
}
