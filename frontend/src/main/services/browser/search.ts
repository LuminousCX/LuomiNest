import { WebContentsView, BrowserWindow } from 'electron'
import { createBrowserView, isViewDestroyed } from './view'
import { DEFAULT_BROWSER_CONFIG } from './types'

export interface SearchResult {
  title: string
  snippet: string
  url: string
}

const BING_SEARCH_URL = 'https://cn.bing.com/search'
const SEARCH_TIMEOUT = 15000
const FETCH_URL_TIMEOUT = 15000

export async function browserSearch(
  query: string,
  mainWindow: BrowserWindow | null
): Promise<SearchResult[]> {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return []
  }

  const encodedQuery = encodeURIComponent(query)
  const searchUrl = `${BING_SEARCH_URL}?q=${encodedQuery}&setmkt=zh-CN&setlang=zh`

  const view = createBrowserView()

  try {
    view.webContents.setBackgroundThrottling(false)

    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Search timeout'))
      }, SEARCH_TIMEOUT)

      view.webContents.on('did-finish-load', () => {
        clearTimeout(timeout)
        resolve()
      })

      view.webContents.on('did-fail-load', (_event, errorCode) => {
        clearTimeout(timeout)
        reject(new Error(`Load failed: ${errorCode}`))
      })

      view.webContents.loadURL(searchUrl).catch((err: Error) => {
        clearTimeout(timeout)
        reject(err)
      })
    })

    const results = await view.webContents.executeJavaScript(`
      (function() {
        var items = document.querySelectorAll('li.b_algo');
        var results = [];
        for (var i = 0; i < Math.min(items.length, 5); i++) {
          var el = items[i];
          var titleEl = el.querySelector('h2 a');
          var snippetEl = el.querySelector('p') || el.querySelector('.b_caption p');
          var title = titleEl ? titleEl.textContent.trim() : '';
          var snippet = snippetEl ? snippetEl.textContent.trim() : '';
          var url = titleEl ? titleEl.href : '';
          if (title || snippet) {
            results.push({ title: title, snippet: snippet, url: url });
          }
        }
        return results;
      })()
    `) as SearchResult[]

    return results || []
  } catch (err) {
    console.warn('[BrowserSearch] Search failed:', err)
    return []
  } finally {
    try {
      if (!isViewDestroyed(view)) {
        view.webContents.close()
      }
    } catch {}
  }
}

export async function fetchUrl(
  url: string,
  mainWindow: BrowserWindow | null
): Promise<string> {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return ''
  }

  const view = new WebContentsView({
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: false,
      partition: 'persist:fetch-url',
      webgl: false,
      plugins: false,
      enableWebSQL: false,
      spellcheck: false,
    }
  })

  try {
    view.webContents.setBackgroundThrottling(false)

    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Fetch URL timeout'))
      }, FETCH_URL_TIMEOUT)

      view.webContents.on('did-finish-load', () => {
        clearTimeout(timeout)
        // 等待 JS 动态渲染完成
        setTimeout(resolve, 2000)
      })

      view.webContents.on('did-fail-load', (_event, errorCode) => {
        clearTimeout(timeout)
        reject(new Error(`Load failed: ${errorCode}`))
      })

      view.webContents.loadURL(url).catch((err: Error) => {
        clearTimeout(timeout)
        reject(err)
      })
    })

    const text = await view.webContents.executeJavaScript(`
      (function() {
        var title = document.title || '';
        var body = document.body ? document.body.innerText : '';
        var maxLen = 4000;
        var content = body.substring(0, maxLen);
        if (body.length > maxLen) content += '...[内容已截断]';
        return title + '\\n\\n' + content;
      })()
    `) as string

    return text || ''
  } catch (err) {
    console.warn('[BrowserSearch] Fetch URL failed:', err)
    return ''
  } finally {
    try {
      if (!view.webContents.isDestroyed()) {
        view.webContents.close()
      }
    } catch {}
  }
}
