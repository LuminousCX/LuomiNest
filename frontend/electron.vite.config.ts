import { resolve } from 'path'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
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
            if (id.includes('node_modules/vue/') || id.includes('node_modules/vue-router/')) {
              return 'vue-vendor'
            }
            if (id.includes('node_modules/pixi.js') || id.includes('node_modules/@pixi')) {
              return 'pixi-vendor'
            }
            if (id.includes('node_modules/pixi-live2d-display')) {
              return 'live2d-vendor'
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
