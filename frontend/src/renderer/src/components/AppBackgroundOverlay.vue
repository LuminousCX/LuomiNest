<template>
  <!-- 全局背景覆盖层：固定在最底层，所有效果仅通过 CSS 变量控制 -->
  <div
    class="app-bg-overlay"
    :class="{
      'app-bg-overlay--active': isActive,
      'app-bg-overlay--image': hasImageLayer,
      'app-bg-overlay--gradient': hasGradientLayer,
      'app-bg-overlay--pattern': hasPatternLayer,
      [`app-bg-overlay--fit-${backgroundFit}`]: true
    }"
    aria-hidden="true"
  >
    <div class="app-bg-overlay__base" />
    <div class="app-bg-overlay__media" />
    <div class="app-bg-overlay__ambient" />
    <div class="app-bg-overlay__tint" />
    <div class="app-bg-overlay__vignette" />
    <div class="app-bg-overlay__grain" />
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const themeStore = useThemeStore()

/** 不需要背景覆盖层的路由 */
const EXCLUDED_PATHS = [
  '/desktop-pet',
  '/welcome',
  '/login',
  '/splash',
  '/settings/about',
  '/settings/license',
  '/settings/privacy-detail'
]

const shouldShow = computed(() => !EXCLUDED_PATHS.includes(route.path))
const image = computed(() => themeStore.effectiveBackground.image)
const backgroundFit = computed(() => themeStore.effectiveBackground.fit ?? 'cover')
const hasBackground = computed(() => !!image.value)
const isActive = computed(() => shouldShow.value && hasBackground.value)

const isGradient = (value: string | null): boolean =>
  !!value && /^(?:linear|radial|conic)-gradient\(/.test(value)

const isPattern = (value: string | null): boolean =>
  !!value &&
  !isGradient(value) &&
  !value.startsWith('luominest-bg://') &&
  !value.startsWith('http') &&
  !value.startsWith('data:') &&
  !value.startsWith('/') &&
  // 相对路径（内置静态背景图，如 ./themes/...）视为图片而非图案
  !value.startsWith('./')

const isImageUrl = (value: string | null): boolean =>
  !!value && !isGradient(value) && !isPattern(value)

const hasImageLayer = computed(() => isImageUrl(image.value))
const hasGradientLayer = computed(() => isGradient(image.value))
const hasPatternLayer = computed(() => isPattern(image.value))

/** 将背景值同步到 CSS 变量，供覆盖层使用 */
function applyBackgroundToOverlay() {
  const root = document.documentElement
  const value = image.value

  if (!value) {
    root.style.removeProperty('--lumi-bg-media')
    root.style.removeProperty('--lumi-bg-media-type')
    root.removeAttribute('data-lumi-background')
    return
  }

  if (isGradient(value)) {
    root.style.setProperty('--lumi-bg-media', value)
    root.style.setProperty('--lumi-bg-media-type', 'gradient')
  } else if (isPattern(value)) {
    root.style.setProperty('--lumi-bg-media', value)
    root.style.setProperty('--lumi-bg-media-type', 'pattern')
  } else {
    root.style.setProperty('--lumi-bg-media', `url('${value}')`)
    root.style.setProperty('--lumi-bg-media-type', 'image')
  }

  root.setAttribute('data-lumi-background', 'active')
}

watch(image, applyBackgroundToOverlay, { immediate: true })
</script>

<style scoped>
.app-bg-overlay {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}

.app-bg-overlay__base,
.app-bg-overlay__media,
.app-bg-overlay__ambient,
.app-bg-overlay__tint,
.app-bg-overlay__vignette,
.app-bg-overlay__grain {
  position: absolute;
  inset: 0;
  transition: opacity var(--duration-slow) var(--ease-in-out);
}

/* 基础层：主题底色，始终存在，避免切换时闪白/黑 */
.app-bg-overlay__base {
  background: var(--app-bg-base, var(--bg));
}

/* 媒体层：背景图/渐变/图案 */
.app-bg-overlay__media {
  opacity: 0;
  background: var(--lumi-bg-media, none);
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  filter: blur(var(--app-bg-blur, 0px));
  transform: scale(var(--app-bg-scale, 1));
  image-rendering: -webkit-optimize-contrast;
  image-rendering: crisp-edges;
}

.app-bg-overlay--pattern .app-bg-overlay__media {
  background-size: 24px 24px;
  background-position: 0 0;
  background-repeat: repeat;
  transform: scale(1);
  filter: none;
}

.app-bg-overlay--active .app-bg-overlay__media {
  opacity: var(--app-bg-opacity, 1);
}

.app-bg-overlay--fit-cover .app-bg-overlay__media {
  background-size: cover;
  background-position: center;
}

.app-bg-overlay--fit-contain .app-bg-overlay__media {
  background-size: contain;
  background-position: center;
  background-repeat: no-repeat;
}

.app-bg-overlay--fit-center .app-bg-overlay__media {
  background-size: auto;
  background-position: center;
  background-repeat: no-repeat;
}

.app-bg-overlay--fit-right .app-bg-overlay__media {
  background-size: cover;
  background-position: right center;
}

/* 环境光层：品牌色/主题色柔光，参考 Cyrene-Agent */
.app-bg-overlay__ambient {
  opacity: 0;
  background: var(--app-bg-ambient, transparent);
}

.app-bg-overlay--active .app-bg-overlay__ambient {
  opacity: var(--lumi-ambient-intensity, 0.3);
}

/* 色彩着色层：统一不同图片色调，提升文字可读性 */
.app-bg-overlay__tint {
  opacity: 0;
  background: var(--app-bg-overlay-tint, transparent);
}

.app-bg-overlay--active .app-bg-overlay__tint {
  opacity: 1;
}

/* 暗角层：径向暗角，增强视觉焦点 */
.app-bg-overlay__vignette {
  opacity: 0;
  background: var(--app-bg-vignette, transparent);
}

.app-bg-overlay--active .app-bg-overlay__vignette {
  opacity: 1;
}

/* 颗粒层：极微弱噪点质感 */
.app-bg-overlay__grain {
  opacity: 0;
  background-image: var(--lumi-grain-image);
  mix-blend-mode: overlay;
  /* 固定尺寸的小图平铺，降低滤镜重绘开销 */
  background-size: 200px 200px;
  background-repeat: repeat;
}

.app-bg-overlay--active .app-bg-overlay__grain {
  opacity: var(--lumi-grain-opacity);
}
</style>
