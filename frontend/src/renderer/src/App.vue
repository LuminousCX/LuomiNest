<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import TitleBar from './components/TitleBar.vue'
import LumiSidebar from './components/LumiSidebar.vue'
import { useThemeStore } from './stores/theme'

const route = useRoute()
const themeStore = useThemeStore()

const isWelcomePage = computed(() => route.path === '/welcome')
const isDesktopPetPage = computed(() => route.path === '/desktop-pet')
const isAgentCreatePage = computed(() => route.path === '/agent/create')
const isMinimalLayout = computed(() => isWelcomePage.value || isDesktopPetPage.value)

watch(isDesktopPetPage, (val) => {
  if (val) {
    document.documentElement.classList.add('desktop-pet')
  } else {
    document.documentElement.classList.remove('desktop-pet')
  }
}, { immediate: true })
</script>

<template>
  <div class="lumi-app" :class="{ 'welcome-mode': isWelcomePage, 'desktop-pet-mode': isDesktopPetPage }">
    <TitleBar v-if="!isMinimalLayout" title="LuomiNest" />
    <div class="lumi-body" v-if="!isMinimalLayout">
      <LumiSidebar />
      <main class="lumi-main">
        <router-view />
      </main>
    </div>
    <router-view v-else />
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
  overflow: hidden;
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
  top: 0; left: 8px; right: 8px; height: 4px;
  cursor: n-resize;
}
.resize-s {
  bottom: 0; left: 8px; right: 8px; height: 4px;
  cursor: s-resize;
}
.resize-e {
  top: 8px; right: 0; bottom: 8px; width: 4px;
  cursor: e-resize;
}
.resize-w {
  top: 8px; left: 0; bottom: 8px; width: 4px;
  cursor: w-resize;
}
.resize-ne {
  top: 0; right: 0; width: 8px; height: 8px;
  cursor: ne-resize;
}
.resize-nw {
  top: 0; left: 0; width: 8px; height: 8px;
  cursor: nw-resize;
}
.resize-se {
  bottom: 0; right: 0; width: 8px; height: 8px;
  cursor: se-resize;
}
.resize-sw {
  bottom: 0; left: 0; width: 8px; height: 8px;
  cursor: sw-resize;
}

.resize-handle:hover {
  background: var(--lumi-primary);
  opacity: 0.3;
}
</style>
