import { BrowserWindow } from 'electron'
import https from 'https'

export interface SearchResult {
  title: string
  snippet: string
  url: string
}

const BING_SEARCH_URL = 'https://cn.bing.com/search'
const SEARCH_TIMEOUT = 10000

const USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

function fetchUrl(url: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error('Search timeout'))
    }, SEARCH_TIMEOUT)

    const request = https.get(url, {
      headers: {
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
      }
    }, (res) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        clearTimeout(timeout)
        fetchUrl(res.headers.location).then(resolve).catch(reject)
        return
      }

      let data = ''
      res.setEncoding('utf-8')
      res.on('data', (chunk: string) => { data += chunk })
      res.on('end', () => {
        clearTimeout(timeout)
        resolve(data)
      })
      res.on('error', (err: Error) => {
        clearTimeout(timeout)
        reject(err)
      })
    })

    request.on('error', (err: Error) => {
      clearTimeout(timeout)
      reject(err)
    })
  })
}

function decodeHtmlEntities(text: string): string {
  return text
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x27;/g, "'")
    .replace(/&nbsp;/g, ' ')
}

function stripHtmlTags(html: string): string {
  return html.replace(/<[^>]*>/g, '').trim()
}

function parseBingResults(html: string): SearchResult[] {
  const results: SearchResult[] = []

  const algoPattern = /<li\s+class="b_algo"[^>]*>([\s\S]*?)<\/li>/gi
  let algoMatch: RegExpExecArray | null

  while ((algoMatch = algoPattern.exec(html)) !== null && results.length < 5) {
    const block = algoMatch[1]

    const titlePattern = /<h2[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/i
    const titleMatch = titlePattern.exec(block)

    if (!titleMatch) continue

    const url = decodeHtmlEntities(titleMatch[1])
    const title = stripHtmlTags(decodeHtmlEntities(titleMatch[2]))

    let snippet = ''
    const captionPattern = /<div\s+class="b_caption[^"]*"[^>]*>([\s\S]*?)<\/div>\s*<\/div>/i
    const captionMatch = captionPattern.exec(block)
    if (captionMatch) {
      const pPattern = /<p[^>]*>([\s\S]*?)<\/p>/i
      const pMatch = pPattern.exec(captionMatch[1])
      if (pMatch) {
        snippet = stripHtmlTags(decodeHtmlEntities(pMatch[1]))
      }
    }

    if (!snippet) {
      const pPattern = /<p[^>]*>([\s\S]*?)<\/p>/i
      const pMatch = pPattern.exec(block)
      if (pMatch) {
        snippet = stripHtmlTags(decodeHtmlEntities(pMatch[1]))
      }
    }

    if (title || snippet) {
      results.push({ title, snippet, url })
    }
  }

  return results
}

export async function browserSearch(
  query: string,
  _mainWindow: BrowserWindow | null
): Promise<SearchResult[]> {
  const encodedQuery = encodeURIComponent(query)
  const searchUrl = `${BING_SEARCH_URL}?q=${encodedQuery}&setmkt=zh-CN&setlang=zh`

  try {
    const html = await fetchUrl(searchUrl)
    return parseBingResults(html)
  } catch (err) {
    console.warn('[BrowserSearch] Search failed:', err)
    return []
  }
}
