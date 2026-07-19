<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import TitleBar from './components/TitleBar.vue'
import LumiSidebar from './components/LumiSidebar.vue'
import ToastContainer from './components/common/ToastContainer.vue'
import AppBackgroundOverlay from '@/components/AppBackgroundOverlay.vue'
import { useDesktopPetChatBridge } from './composables/useDesktopPetChatBridge'

const route = useRoute()

const isWelcomePage = computed(() => route.path === '/welcome')
const isSplashPage = computed(() => route.path === '/splash')
const isLoginPage = computed(() => route.path === '/login')
const isDesktopPetPage = computed(() => route.path === '/desktop-pet')
const isMinimalLayout = computed(() => isWelcomePage.value || isSplashPage.value || isLoginPage.value || isDesktopPetPage.value)

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
  <div class="lumi-app" :class="{ 'welcome-mode': isWelcomePage, 'desktop-pet-mode': isDesktopPetPage }">
    <AppBackgroundOverlay />
    <TitleBar v-if="!isMinimalLayout" title="LuomiNest" />
    <div class="lumi-body" v-if="!isMinimalLayout">
      <LumiSidebar />
      <main class="lumi-main">
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
}

.lumi-main {
  flex: 1;
  overflow: hidden;
  position: relative;
  min-width: 0;
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

.page-switch-enter-active {
  transition: opacity 0.35s cubic-bezier(0.4, 0, 0.2, 1), transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.page-switch-leave-active {
  transition: opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1), transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.page-switch-enter-from {
  opacity: 0;
  transform: translateY(16px) scale(0.985);
}

.page-switch-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.99);
}

.page-fade-enter-active {
  transition: opacity 0.4s cubic-bezier(0.4, 0, 0.2, 1), transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.page-fade-leave-active {
  transition: opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1), transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.page-fade-enter-from {
  opacity: 0;
  transform: scale(0.97);
}

.page-fade-leave-to {
  opacity: 0;
  transform: scale(1.01);
}
</style>
