import { BrowserView, BrowserWindow } from 'electron'

interface ManagedTab {
  id: string
  view: BrowserView
  title: string
  url: string
  active: boolean
}

let mainWindow: BrowserWindow | null = null
const managedTabs = new Map<string, ManagedTab>()
let activeTabId: string | null = null

export function setMainWindow(win: BrowserWindow): void {
  mainWindow = win
}

export async function createManagedTab(url = 'about:blank'): Promise<ManagedTab> {
  if (!mainWindow) throw new Error('Main window not initialized')

  const tabId = `managed-${Date.now()}`
  const view = new BrowserView({
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  mainWindow.addBrowserView(view)
  const bounds = getAvailableBounds()
  view.setBounds(bounds)
  view.setAutoResize({ width: true, height: true })

  await view.webContents.loadURL(url)

  const tab: ManagedTab = {
    id: tabId,
    view,
    title: '新标签页',
    url,
    active: false
  }

  view.webContents.on('page-title-updated', (_e, title) => {
    tab.title = title
  })

  view.webContents.on('did-navigate', (_e, url) => {
    tab.url = url
  })

  managedTabs.set(tabId, tab)
  return tab
}

export function activateTab(tabId: string): void {
  if (!mainWindow) return

  managedTabs.forEach((tab) => {
    if (tab.id === tabId) {
      mainWindow!.addBrowserView(tab.view)
      const bounds = getAvailableBounds()
      tab.view.setBounds(bounds)
      tab.active = true
      activeTabId = tabId
    } else {
      mainWindow!.removeBrowserView(tab.view)
      tab.active = false
    }
  })
}

export function closeManagedTab(tabId: string): void {
  const tab = managedTabs.get(tabId)
  if (!tab) return

  if (mainWindow) mainWindow.removeBrowserView(tab.view)
  tab.view.webContents.close()
  managedTabs.delete(tabId)

  if (activeTabId === tabId) {
    const remaining = Array.from(managedTabs.keys())
    activeTabId = remaining.length > 0 ? remaining[remaining.length - 1] : null
    if (activeTabId) activateTab(activeTabId)
  }
}

export function getAllManagedTabs(): ManagedTab[] {
  return Array.from(managedTabs.values()).map(t => ({
    ...t,
    view: null as any
  }))
}

export function getActiveTab(): ManagedTab | undefined {
  if (!activeTabId) return undefined
  return managedTabs.get(activeTabId)
}

function getAvailableBounds(): { x: number; y: number; width: number; height: number } {
  if (!mainWindow) return { x: 0, y: 80, width: 800, height: 600 }
  const [x, y] = mainWindow.getPosition()
  const [width, height] = mainWindow.getSize()
  return {
    x: 0,
    y: 90,
    width,
    height: height - 90
  }
}
