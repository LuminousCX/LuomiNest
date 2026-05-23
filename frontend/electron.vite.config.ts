import { resolve } from 'path'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import vue from '@vitejs/plugin-vue'
import { copyFileSync, mkdirSync } from 'fs'

function copyStaticFilesPlugin() {
  return {
    name: 'copy-static-files',
    writeBundle(options: any) {
      const outDir = options.dir || resolve(__dirname, 'out/main')
      const staticFiles = [
        'src/main/services/browser/stealth-preload.js',
        'src/main/services/browser/home-preload.js',
        'src/main/services/browser/home.html'
      ]
      for (const file of staticFiles) {
        const src = resolve(__dirname, file)
        const dest = resolve(outDir, file.split('/').pop()!)
        try {
          copyFileSync(src, dest)
        } catch (err) {
          console.warn(`[copy-static-files] Failed to copy ${src}:`, err)
        }
      }
    }
  }
}

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin(), copyStaticFilesPlugin()],
    build: {
      rollupOptions: {
        input: {
          index: resolve(__dirname, 'src/main/index.ts')
        }
      }
    }
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        input: {
          index: resolve(__dirname, 'src/preload/index.ts')
        }
      }
    }
  },
  renderer: {
    root: resolve(__dirname, 'src/renderer'),
    build: {
      rollupOptions: {
        input: {
          index: resolve(__dirname, 'src/renderer/index.html')
        },
        output: {
          manualChunks(id) {
            if (id.includes('lucide-vue-next')) {
              return 'lucide-vendor'
            }
            if (id.includes('node_modules/vue/') || id.includes('node_modules/vue-router/') || id.includes('node_modules/pinia')) {
              return 'vue-vendor'
            }
            if (id.includes('node_modules/pixi.js') || id.includes('node_modules/@pixi')) {
              return 'pixi-vendor'
            }
            if (id.includes('node_modules/pixi-live2d-display')) {
              return 'live2d-vendor'
            }
            if (id.includes('node_modules/marked')) {
              return 'marked-vendor'
            }
          }
        }
      }
    },
    plugins: [vue()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src/renderer/src')
      }
    },
    server: {
      fs: {
        allow: [
          resolve(__dirname, 'resources'),
          resolve(__dirname, 'src')
        ]
      }
    }
  }
})
