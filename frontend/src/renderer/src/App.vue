<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import TitleBar from './components/TitleBar.vue'
import LumiSidebar from './components/LumiSidebar.vue'
import ToastContainer from './components/common/ToastContainer.vue'
import AppBackgroundOverlay from '@/components/AppBackgroundOverlay.vue'
import { useDesktopPetChatBridge } from './composables/useDesktopPetChatBridge'
import { useThemeStore } from './stores/theme'

const route = useRoute()
const themeStore = useThemeStore()

const isWelcomePage = computed(() => route.path === '/welcome')
const isSplashPage = computed(() => route.path === '/splash')
const isLoginPage = computed(() => route.path === '/login')
const isDesktopPetPage = computed(() => route.path === '/desktop-pet')
const isMinimalLayout = computed(() => isWelcomePage.value || isSplashPage.value || isLoginPage.value || isDesktopPetPage.value)
const isBackgroundExcluded = computed(() =>
  ['/settings/about', '/settings/license', '/settings/privacy-detail'].includes(route.path)
)
const hasBackground = computed(() =>
  !isMinimalLayout.value && !isBackgroundExcluded.value && !!themeStore.effectiveBackground.image
)

watch(isDesktopPetPage, (val) => {
  if (val) {
    document.documentElement.classList.add('desktop-pet')
  } else {
    document.documentElement.classList.remove('desktop-pet')
  }
}, { immediate: true })

// 桌宠聊天桥接：监听桌宠窗口转发的聊天请求，调用主 Agent (MAIN_AGENT_ID) 的 LLM 流式输出，
// TTS 全局 Store 驱动桌宠窗口的 Live2D（陪伴优先：任意页面都能与桌宠对话）。
// 仅在主应用窗口（非桌宠窗口、非登录/欢迎页）初始化。
if (!isDesktopPetPage.value && !isWelcomePage.value && !isLoginPage.value && !isSplashPage.value) {
  useDesktopPetChatBridge()
}
</script>

<template>
  <div
    class="lumi-app"
    :class="{
      'welcome-mode': isWelcomePage,
      'desktop-pet-mode': isDesktopPetPage,
      'lumi-app--bg-active': hasBackground
    }"
  >
    <AppBackgroundOverlay />
    <TitleBar v-if="!isMinimalLayout" title="LuomiNest" />
    <div class="lumi-body" v-if="!isMinimalLayout">
      <LumiSidebar />
      <main class="lumi-main" :class="{ 'lumi-main--glass': hasBackground }">
        <router-view v-slot="{ Component }">
          <Transition name="page-switch" mode="out-in">
            <component :is="Component" :key="route.path" />
          </Transition>
        </router-view>
      </main>
    </div>
    <router-view v-else v-slot="{ Component }">
      <Transition name="page-fade" mode="out-in">
        <component :is="Component" :key="route.path" />
      </Transition>
    </router-view>
    <ToastContainer />
    <div v-if="!isDesktopPetPage" class="resize-handle resize-n"></div>
    <div v-if="!isDesktopPetPage" class="resize-handle resize-s"></div>
    <div v-if="!isDesktopPetPage" class="resize-handle resize-e"></div>
    <div v-if="!isDesktopPetPage" class="resize-handle resize-w"></div>
    <div v-if="!isDesktopPetPage" class="resize-handle resize-ne"></div>
    <div v-if="!isDesktopPetPage" class="resize-handle resize-nw"></div>
    <div v-if="!isDesktopPetPage" class="resize-handle resize-se"></div>
    <div v-if="!isDesktopPetPage" class="resize-handle resize-sw"></div>
  </div>
</template>

<style scoped>
.lumi-app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: var(--bg);
  position: relative;
  isolation: isolate;
}

.lumi-app--bg-active {
  background: transparent;
}

.lumi-app.welcome-mode .resize-handle {
  display: none;
}

.lumi-app.desktop-pet-mode {
  background: transparent !important;
}

.lumi-app.desktop-pet-mode :deep(*) {
  background-color: transparent !important;
}

.lumi-body {
  display: flex;
  flex: 1;
  overflow: visible;
  min-height: 0;
  position: relative;
  z-index: 1;
}

.lumi-main {
  flex: 1;
  overflow: hidden;
  position: relative;
  min-width: 0;
  background: var(--bg);
}

.lumi-main--glass {
  background: color-mix(in srgb, var(--bg) 72%, transparent);
  -webkit-backdrop-filter: var(--glass-blur);
  backdrop-filter: var(--glass-blur);
}

.lumi-main--glass > * {
  background: transparent;
}

.lumi-app > router-view {
  position: relative;
  z-index: 1;
}

.resize-handle {
  position: absolute;
  z-index: 1000;
  transition: background var(--transition-fast);
}

.resize-n {
  top: 0; left: var(--space-2); right: var(--space-2); height: var(--space-1);
  cursor: n-resize;
}
.resize-s {
  bottom: 0; left: var(--space-2); right: var(--space-2); height: var(--space-1);
  cursor: s-resize;
}
.resize-e {
  top: var(--space-2); right: 0; bottom: var(--space-2); width: var(--space-1);
  cursor: e-resize;
}
.resize-w {
  top: var(--space-2); left: 0; bottom: var(--space-2); width: var(--space-1);
  cursor: w-resize;
}
.resize-ne {
  top: 0; right: 0; width: var(--space-2); height: var(--space-2);
  cursor: ne-resize;
}
.resize-nw {
  top: 0; left: 0; width: var(--space-2); height: var(--space-2);
  cursor: nw-resize;
}
.resize-se {
  bottom: 0; right: 0; width: var(--space-2); height: var(--space-2);
  cursor: se-resize;
}
.resize-sw {
  bottom: 0; left: 0; width: var(--space-2); height: var(--space-2);
  cursor: sw-resize;
}

.resize-handle:hover {
  background: var(--lumi-primary);
  opacity: 0.3;
}

/*
 * 页面切换动画：使用 opacity-only 淡入淡出。
 *
 * 原因：
 * - scale 会在每一帧触发整个页面的重绘/重排，对包含 Live2D Canvas、
 *   大量 DOM 的 Workbench / Avatar 视图尤其昂贵，导致 rAF handler 耗时 200ms+。
 * - opacity 可由浏览器直接合成，不触发 layout/paint，切换更流畅。
 * - will-change 仅在 enter/leave-active 阶段声明，动画结束后移除，避免长期占用合成层内存。
 */
.page-switch-enter-active,
.page-switch-leave-active {
  transition: opacity var(--page-switch-enter-duration) var(--ease-out-expo);
  will-change: opacity;
}

.page-switch-enter-from,
.page-switch-leave-to {
  opacity: 0;
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity var(--page-fade-enter-duration) var(--ease-out-expo);
  will-change: opacity;
}

.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}
</style>
