import { WebContentsView, BrowserWindow } from 'electron'
import { createBrowserView, attachView, detachView, setViewBounds, isViewDestroyed } from './view'
import { calculateBounds } from './view'
import { DEFAULT_BROWSER_CONFIG } from './types'

export interface SearchResult {
  title: string
  snippet: string
  url: string
}

const BING_SEARCH_URL = 'https://cn.bing.com/search'
const SEARCH_TIMEOUT = 15000

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
