import { readdirSync, statSync, rmSync, mkdirSync } from 'fs'
import { join } from 'path'
import { PATHS } from './paths'

const CACHE_DIRS = [
  PATHS.live2dCache,
  PATHS.ttsCache,
  PATHS.imageCache,
]

const getDirSize = (dir: string): number => {
  if (!dir) return 0
  try {
    let totalSize = 0
    const entries = readdirSync(dir, { withFileTypes: true })
    for (const entry of entries) {
      const fullPath = join(dir, entry.name)
      if (entry.isDirectory()) {
        totalSize += getDirSize(fullPath)
      } else if (entry.isFile()) {
        try {
          totalSize += statSync(fullPath).size
        } catch {
          // skip inaccessible files
        }
      }
    }
    return totalSize
  } catch {
    return 0
  }
}

const emptyDir = (dir: string): void => {
  try {
    const entries = readdirSync(dir, { withFileTypes: true })
    for (const entry of entries) {
      const fullPath = join(dir, entry.name)
      if (entry.isDirectory()) {
        rmSync(fullPath, { recursive: true, force: true })
      } else {
        try {
          rmSync(fullPath, { force: true })
        } catch {
          // skip locked files
        }
      }
    }
  } catch {
    // directory may not exist
  }
}

export const cacheManager = {
  getCacheSize: (): number => {
    return CACHE_DIRS.reduce((total, dir) => total + getDirSize(dir), 0)
  },

  getCacheSizeMB: (): number => {
    return Math.round(cacheManager.getCacheSize() / (1024 * 1024) * 100) / 100
  },

  getCacheBreakdown: (): Record<string, number> => {
    const breakdown: Record<string, number> = {}
    for (const dir of CACHE_DIRS) {
      const name = dir.split(/[/\\]/).pop() || 'unknown'
      breakdown[name] = getDirSize(dir)
    }
    return breakdown
  },

  clearAllCache: (): void => {
    for (const dir of CACHE_DIRS) {
      emptyDir(dir)
      mkdirSync(dir, { recursive: true })
    }
    console.info('[INFO][LuomiNestCache] All cache cleared')
  },

  clearCacheDir: (dirName: string): boolean => {
    const target = CACHE_DIRS.find(d => d.endsWith(dirName))
    if (!target) return false
    emptyDir(target)
    mkdirSync(target, { recursive: true })
    console.info(`[INFO][LuomiNestCache] Cache dir "${dirName}" cleared`)
    return true
  },

  isOverLimit: (maxSizeMB: number): boolean => {
    return cacheManager.getCacheSizeMB() > maxSizeMB
  },
}
