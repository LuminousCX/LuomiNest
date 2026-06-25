<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'

const props = withDefaults(defineProps<{
  icon: Component
  size?: number
  theme?: string
  animated?: boolean
}>(), {
  size: 24,
  theme: 'default',
  animated: true,
})

interface ThemeConfig {
  colorVar: string
  animClass: string
}

const themeMap: Record<string, ThemeConfig> = {
  Brain: { colorVar: '--task-pink', animClass: 'anim-pulse' },
  Bot: { colorVar: '--lumi-brand', animClass: 'anim-float' },
  Zap: { colorVar: '--lumi-amber', animClass: 'anim-shimmer' },
  Globe: { colorVar: '--lumi-info', animClass: 'anim-float' },
  Palette: { colorVar: '--task-pink', animClass: 'anim-float' },
  Cpu: { colorVar: '--lumi-brand', animClass: 'anim-pulse' },
  Lightbulb: { colorVar: '--lumi-amber', animClass: 'anim-glow' },
  Terminal: { colorVar: '--lumi-success', animClass: 'anim-shimmer' },
  Code: { colorVar: '--lumi-success', animClass: 'anim-float' },
  MessageCircle: { colorVar: '--lumi-info', animClass: 'anim-pulse' },
  MessageSquare: { colorVar: '--lumi-info', animClass: 'anim-pulse' },
  Search: { colorVar: '--task-purple', animClass: 'anim-shimmer' },
  Shield: { colorVar: '--lumi-success', animClass: 'anim-float' },
  Heart: { colorVar: '--lumi-danger', animClass: 'anim-pulse' },
  HeartPulse: { colorVar: '--lumi-danger', animClass: 'anim-pulse' },
  Users: { colorVar: '--lumi-info', animClass: 'anim-float' },
  User: { colorVar: '--lumi-info', animClass: 'anim-float' },
  BookOpen: { colorVar: '--lumi-amber', animClass: 'anim-float' },
  GraduationCap: { colorVar: '--task-purple', animClass: 'anim-float' },
  BarChart3: { colorVar: '--lumi-info', animClass: 'anim-shimmer' },
  TrendingUp: { colorVar: '--lumi-success', animClass: 'anim-shimmer' },
  Puzzle: { colorVar: '--lumi-amber', animClass: 'anim-shimmer' },
  Wrench: { colorVar: '--text-muted', animClass: 'anim-shimmer' },
  Package: { colorVar: '--lumi-amber', animClass: 'anim-float' },
  Image: { colorVar: '--task-pink', animClass: 'anim-shimmer' },
  Volume2: { colorVar: '--task-pink', animClass: 'anim-pulse' },
  PenTool: { colorVar: '--task-purple', animClass: 'anim-float' },
  Laptop: { colorVar: '--text-muted', animClass: 'anim-float' },
  Home: { colorVar: '--lumi-amber', animClass: 'anim-float' },
  RefreshCw: { colorVar: '--lumi-success', animClass: 'anim-pulse' },
  Scale: { colorVar: '--task-purple', animClass: 'anim-float' },
  LayoutGrid: { colorVar: '--lumi-info', animClass: 'anim-shimmer' },
  default: { colorVar: '--lumi-brand', animClass: 'anim-float' },
}

const currentTheme = computed(() => themeMap[props.theme] || themeMap.default)

const makeGradient = (colorVar: string) =>
  `linear-gradient(135deg, color-mix(in srgb, var(${colorVar}) 12%, transparent) 0%, color-mix(in srgb, var(${colorVar}) 4%, transparent) 100%)`

const makeGlow = (colorVar: string) =>
  `0 4px 16px color-mix(in srgb, var(${colorVar}) 15%, transparent)`

const iconStyle = computed(() => ({
  background: makeGradient(currentTheme.value.colorVar),
  color: `var(${currentTheme.value.colorVar})`,
}))

const glow = computed(() => makeGlow(currentTheme.value.colorVar))

const containerSize = computed(() => `${props.size + 24}px`)
const borderRadius = computed(() => `${Math.round((props.size + 24) * 0.25)}px`)
</script>

<template>
  <div
    :class="['lumi-card-icon', { [currentTheme.animClass]: animated }]"
    :style="{
      '--icon-size': containerSize,
      '--icon-radius': borderRadius,
      '--icon-glow-shadow': glow,
      ...iconStyle,
    }"
  >
    <div class="icon-inner">
      <component :is="icon" :size="size" />
    </div>
    <div class="icon-glow" :style="{ background: `var(${currentTheme.colorVar})` }" />
  </div>
</template>

<style scoped>
.lumi-card-icon {
  position: relative;
  width: var(--icon-size);
  height: var(--icon-size);
  border-radius: var(--icon-radius);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
  transition: all var(--transition-slow);
}

.lumi-card-icon:hover {
  transform: translateY(calc(var(--space-1) / -2)) scale(1.05);
  box-shadow: var(--icon-glow-shadow, var(--shadow-md));
}

.icon-inner {
  position: relative;
  z-index: var(--z-base);
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-glow {
  position: absolute;
  width: 60%;
  height: 60%;
  border-radius: var(--radius-full);
  opacity: 0;
  filter: blur(12px);
  transition: opacity var(--transition-slow);
  pointer-events: none;
}

.lumi-card-icon:hover .icon-glow {
  opacity: 0.2;
}

/* Animations */
.anim-float {
  animation: lumi-float calc(var(--duration-slow) * 8 + var(--duration-fast)) var(--ease-in-out) infinite;
}

.anim-pulse {
  animation: lumi-pulse calc(var(--duration-slow) * 7 + var(--duration-fast)) var(--ease-in-out) infinite;
}

.anim-shimmer {
  animation: lumi-shimmer calc(var(--duration-slow) * 8 + var(--duration-fast)) var(--ease-in-out) infinite;
}

.anim-glow {
  animation: lumi-glow calc(var(--duration-normal) * 8) var(--ease-in-out) infinite;
}

@keyframes lumi-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(calc(var(--space-1) / -1)); }
}

@keyframes lumi-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.04); }
}

@keyframes lumi-shimmer {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.85; }
}

@keyframes lumi-glow {
  0%, 100% { filter: brightness(1); }
  50% { filter: brightness(1.15); }
}

/* Hover overrides animation */
.lumi-card-icon:hover {
  animation-play-state: paused;
}

</style>
