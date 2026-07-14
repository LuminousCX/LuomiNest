import { resolve } from 'path'
import { rmSync, copyFileSync, mkdirSync } from 'fs'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import vue from '@vitejs/plugin-vue'

// Live2D 模型通过 luominest-avatar:// 协议 + extraResources 提供，
// 不需要 Vite 把 public/live2d 复制到输出目录。构建后清理，避免重复打包与文件锁。
const removeLive2DFromOutput = () => ({
  name: 'luominest-remove-live2d-output',
  closeBundle: () => {
    try {
      rmSync(resolve(__dirname, 'out/renderer/live2d'), { recursive: true, force: true })
    } catch {
      // 忽略：可能存在 OS 级文件锁（如 Defender 扫描），不影响打包（electron-builder files 已排除 live2d）
    }
  }
})

// 将 stealth-preload.js 复制到 out/main/ 目录，
// 供 WebContentsView 的 webPreferences.preload 使用
const copyStealthPreload = () => ({
  name: 'luominest-copy-stealth-preload',
  closeBundle: () => {
    try {
      const src = resolve(__dirname, 'src/main/services/browser/stealth-preload.js')
      const destDir = resolve(__dirname, 'out/main')
      const dest = resolve(destDir, 'stealth-preload.js')
      mkdirSync(destDir, { recursive: true })
      copyFileSync(src, dest)
    } catch {
      // 忽略：开发模式下文件可能已存在
    }
  }
})

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin(), copyStealthPreload()],
    resolve: {
      alias: {
        '@shared': resolve(__dirname, 'src/shared')
      }
    }
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    resolve: {
      alias: {
        '@shared': resolve(__dirname, 'src/shared')
      }
    }
  },
  renderer: {
    root: resolve(__dirname, 'src/renderer'),
    build: {
      // 不清空 out 目录：避免 OS 级文件锁（Defender/Search Indexer 持有 live2d 目录句柄）导致 EBUSY 失败。
      // closeBundle 插件会在构建后清理 live2d 死代码，下次构建不会有残留。
      emptyOutDir: false,
      rollupOptions: {
        input: {
          index: resolve(__dirname, 'src/renderer/index.html')
        },
        output: {
          manualChunks(id) {
            if (id.includes('lucide-vue-next')) return 'lucide-vendor'
            if (id.includes('node_modules/vue/') || id.includes('node_modules/vue-router/') || id.includes('node_modules/pinia')) return 'vue-vendor'
            if (id.includes('node_modules/pixi.js') || id.includes('node_modules/@pixi')) return 'pixi-vendor'
            if (id.includes('node_modules/pixi-live2d-display')) return 'live2d-vendor'
            if (id.includes('node_modules/marked')) return 'marked-vendor'
          }
        }
      }
    },
    plugins: [vue(), removeLive2DFromOutput()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src/renderer/src'),
        '@shared': resolve(__dirname, 'src/shared')
      }
    },
    server: {
      port: 5173,
      fs: {
        allow: [resolve(__dirname, 'resources'), resolve(__dirname, 'src')]
      }
    }
  }
})

