import { chromium, type Browser, type Page, type BrowserContext } from 'playwright'

let browser: Browser | null = null
let contexts = new Map<string, BrowserContext>()
const pages = new Map<string, Page>()

export interface TabInfo {
  id: string
  title: string
  url: string
  active: boolean
  loading: boolean
}

export async function launchBrowser(headless = true): Promise<Browser> {
  if (browser && browser.isConnected()) return browser
  browser = await chromium.launch({
    headless,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  })
  return browser
}

export async function createTab(url?: string): Promise<TabInfo> {
  const bw = await launchBrowser(false)
  const ctx = await bw.newContext()
  const page = await ctx.newPage()
  if (url) await page.goto(url)

  const tabId = `tab-${Date.now()}`
  contexts.set(tabId, ctx)
  pages.set(tabId, page)

  page.on('load', () => updateTabTitle(tabId))

  return getTabInfo(tabId)
}

export async function closeTab(tabId: string): Promise<void> {
  const ctx = contexts.get(tabId)
  const page = pages.get(tabId)
  if (page) { await page.close(); pages.delete(tabId) }
  if (ctx) { await ctx.close(); contexts.delete(tabId) }
}

export async function navigateTab(tabId: string, url: string): Promise<TabInfo> {
  const page = pages.get(tabId)
  if (!page) throw new Error(`Tab ${tabId} not found`)
  await page.goto(url, { waitUntil: 'domcontentloaded' })
  return getTabInfo(tabId)
}

export async function executeScript(tabId: string, script: string): Promise<any> {
  const page = pages.get(tabId)
  if (!page) throw new Error(`Tab ${tabId} not found`)
  return page.evaluate(script)
}

export async function clickElement(tabId: string, selector: string): Promise<void> {
  const page = pages.get(tabId)
  if (!page) throw new Error(`Tab ${tabId} not found`)
  await page.click(selector)
}

export async function fillForm(tabId: string, selector: string, value: string): Promise<void> {
  const page = pages.get(tabId)
  if (!page) throw new Error(`Tab ${tabId} not found`)
  await page.fill(selector, value)
}

export async function takeScreenshot(tabId: string): Promise<string> {
  const page = pages.get(tabId)
  if (!page) throw new Error(`Tab ${tabId} not found`)
  const buf = await page.screenshot({ type: 'png', fullPage: false })
  return `data:image/png;base64,${buf.toString('base64')}`
}

export async function getDomContent(tabId: string): Promise<string> {
  const page = pages.get(tabId)
  if (!page) throw new Error(`Tab ${tabId} not found`)
  return page.content()
}

export async function getTabInfo(tabId: string): Promise<TabInfo> {
  const page = pages.get(tabId)
  if (!page) throw new Error(`Tab ${tabId} not found`)
  return {
    id: tabId,
    title: await page.title(),
    url: page.url(),
    active: false,
    loading: false
  }
}

function updateTabTitle(tabId: string): void {}

export async function getAllTabs(): Promise<TabInfo[]> {
  const tabs: TabInfo[] = []
  for (const [id] of pages) {
    try {
      tabs.push(await getTabInfo(id))
    } catch { /* ignore */ }
  }
  return tabs
}

export async function shutdown(): Promise<void> {
  if (browser?.isConnected()) await browser.close()
  browser = null
  contexts.clear()
  pages.clear()
}
