import { chromium, Browser, Page, BrowserContext } from 'playwright'
import { app } from 'electron'
import path from 'path'

export interface BrowserAction {
  type: 'click' | 'fill' | 'navigate' | 'screenshot' | 'evaluate' | 'hover' | 'press' | 'wait'
  selector?: string
  value?: string
  url?: string
  timeout?: number
}

export interface ActionResult {
  success: boolean
  data?: any
  error?: string
}

class PlaywrightService {
  private browser: Browser | null = null
  private context: BrowserContext | null = null
  private page: Page | null = null
  private isInitialized = false

  async initialize(): Promise<void> {
    if (this.isInitialized) return

    const userDataDir = path.join(app.getPath('userData'), 'playwright-data')
    
    this.browser = await chromium.launchPersistentContext(userDataDir, {
      headless: false,
      args: [
        '--disable-blink-features=AutomationControlled',
        '--disable-infobars',
        '--no-first-run',
        '--no-default-browser-check'
      ],
      ignoreDefaultFlags: true,
      viewport: null
    })

    this.context = this.browser as unknown as BrowserContext
    const pages = this.context.pages()
    this.page = pages[0] || await this.context.newPage()
    
    this.isInitialized = true
  }

  async close(): Promise<void> {
    if (this.browser) {
      await this.browser.close()
      this.browser = null
      this.context = null
      this.page = null
      this.isInitialized = false
    }
  }

  async executeAction(action: BrowserAction): Promise<ActionResult> {
    try {
      if (!this.page) {
        await this.initialize()
      }

      switch (action.type) {
        case 'navigate':
          return await this.navigate(action.url!, action.timeout)
        case 'click':
          return await this.click(action.selector!, action.timeout)
        case 'fill':
          return await this.fill(action.selector!, action.value!, action.timeout)
        case 'screenshot':
          return await this.screenshot()
        case 'evaluate':
          return await this.evaluate(action.value!)
        case 'hover':
          return await this.hover(action.selector!, action.timeout)
        case 'press':
          return await this.press(action.selector!, action.value!)
        case 'wait':
          return await this.waitForSelector(action.selector!, action.timeout)
        default:
          return { success: false, error: 'Unknown action type' }
      }
    } catch (error: any) {
      return { success: false, error: error.message }
    }
  }

  private async navigate(url: string, timeout = 30000): Promise<ActionResult> {
    if (!this.page) return { success: false, error: 'Page not initialized' }
    
    await this.page.goto(url, { timeout, waitUntil: 'domcontentloaded' })
    return { success: true, data: { url: this.page.url(), title: await this.page.title() } }
  }

  private async click(selector: string, timeout = 5000): Promise<ActionResult> {
    if (!this.page) return { success: false, error: 'Page not initialized' }
    
    await this.page.click(selector, { timeout })
    return { success: true }
  }

  private async fill(selector: string, value: string, timeout = 5000): Promise<ActionResult> {
    if (!this.page) return { success: false, error: 'Page not initialized' }
    
    await this.page.fill(selector, value, { timeout })
    return { success: true }
  }

  private async screenshot(): Promise<ActionResult> {
    if (!this.page) return { success: false, error: 'Page not initialized' }
    
    const buffer = await this.page.screenshot({ fullPage: false })
    const base64 = buffer.toString('base64')
    return { success: true, data: { base64, mimeType: 'image/png' } }
  }

  private async evaluate(script: string): Promise<ActionResult> {
    if (!this.page) return { success: false, error: 'Page not initialized' }
    
    const result = await this.page.evaluate(script)
    return { success: true, data: result }
  }

  private async hover(selector: string, timeout = 5000): Promise<ActionResult> {
    if (!this.page) return { success: false, error: 'Page not initialized' }
    
    await this.page.hover(selector, { timeout })
    return { success: true }
  }

  private async press(selector: string, key: string): Promise<ActionResult> {
    if (!this.page) return { success: false, error: 'Page not initialized' }
    
    await this.page.press(selector, key)
    return { success: true }
  }

  private async waitForSelector(selector: string, timeout = 5000): Promise<ActionResult> {
    if (!this.page) return { success: false, error: 'Page not initialized' }
    
    await this.page.waitForSelector(selector, { timeout })
    return { success: true }
  }

  async getPageContent(): Promise<string> {
    if (!this.page) return ''
    return await this.page.content()
  }

  async getPageTitle(): Promise<string> {
    if (!this.page) return ''
    return await this.page.title()
  }

  async getCurrentUrl(): Promise<string> {
    if (!this.page) return ''
    return this.page.url()
  }

  async getSnapshot(): Promise<string> {
    if (!this.page) return ''
    
    const snapshot = await this.page.evaluate(() => {
      const elements = document.querySelectorAll('*')
      const items: string[] = []
      
      elements.forEach((el, index) => {
        const rect = el.getBoundingClientRect()
        if (rect.width > 0 && rect.height > 0) {
          const tag = el.tagName.toLowerCase()
          const text = el.textContent?.trim().slice(0, 50) || ''
          const id = el.id || ''
          const className = el.className || ''
          items.push(`[${index}] ${tag}${id ? '#' + id : ''}${className ? '.' + className : ''} "${text}"`)
        }
      })
      
      return items.join('\n')
    })
    
    return snapshot
  }
}

export const playwrightService = new PlaywrightService()
