<template>
  <div v-if="hasBackground && shouldShow" class="app-bg-overlay" :style="bgStyle" />
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const themeStore = useThemeStore()

// 检测是否为桌宠窗口（通过 Electron IPC 判断）
const isDesktopPetWindow = ref(false)
onMounted(() => {
  isDesktopPetWindow.value = !!(window as any).api?.isDesktopPetWindow?.()
})

// 仅在主窗口页面渲染背景覆盖层
// 排除桌宠页、欢迎页、登录页、启动页等非主窗口路由
const EXCLUDED_PATHS = ['/desktop-pet', '/welcome', '/login', '/splash']
const shouldShow = computed(
  () => !isDesktopPetWindow.value && !EXCLUDED_PATHS.includes(route.path)
)

const hasBackground = computed(() => !!themeStore.background.image)

const bgStyle = computed(() => {
  if (!themeStore.background.image) return {}
  const imageUrl = themeStore.background.image
  // CSS 渐变直接使用，协议 URL 包裹 url()
  const isGradient = /^(?:linear|radial|conic)-gradient\(/.test(imageUrl)
  return {
    '--app-bg-image': isGradient ? imageUrl : `url('${imageUrl}')`,
    '--app-bg-blur': `${themeStore.background.blur}px`,
    '--app-bg-opacity': String(themeStore.background.opacity / 100)
  }
})
</script>

<style scoped>
.app-bg-overlay {
  position: fixed;
  inset: 0;
  z-index: -1;
  background-image: var(--app-bg-image);
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  opacity: var(--app-bg-opacity);
  filter: blur(var(--app-bg-blur));
  pointer-events: none;
  will-change: opacity, filter;
  transition: opacity 0.3s ease, filter 0.3s ease;
}
</style>
