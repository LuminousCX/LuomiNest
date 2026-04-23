import { resolve } from 'path'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src/renderer/src')
    }
  },
  test: {
    environment: 'happy-dom',
    globals: true,
    include: ['src/renderer/src/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/renderer/src/stores/**', 'src/renderer/src/composables/**']
    }
  }
})
