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

const themeMap: Record<string, {
  gradient: string
  glow: string
  iconColor: string
  animClass: string
}> = {
  Brain: {
    gradient: 'linear-gradient(135deg, rgba(236, 72, 153, 0.12), rgba(236, 72, 153, 0.04))',
    glow: '0 4px 16px rgba(236, 72, 153, 0.15)',
    iconColor: '#ec4899',
    animClass: 'anim-pulse',
  },
  Bot: {
    gradient: 'linear-gradient(135deg, rgba(20, 126, 188, 0.12), rgba(98, 169, 200, 0.06))',
    glow: '0 4px 16px rgba(20, 126, 188, 0.15)',
    iconColor: 'var(--lumi-primary)',
    animClass: 'anim-float',
  },
  Zap: {
    gradient: 'linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(245, 158, 11, 0.04))',
    glow: '0 4px 16px rgba(245, 158, 11, 0.15)',
    iconColor: '#f59e0b',
    animClass: 'anim-shimmer',
  },
  Globe: {
    gradient: 'linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(59, 130, 246, 0.04))',
    glow: '0 4px 16px rgba(59, 130, 246, 0.15)',
    iconColor: '#3b82f6',
    animClass: 'anim-float',
  },
  Palette: {
    gradient: 'linear-gradient(135deg, rgba(236, 72, 153, 0.12), rgba(244, 114, 182, 0.06))',
    glow: '0 4px 16px rgba(236, 72, 153, 0.15)',
    iconColor: '#ec4899',
    animClass: 'anim-float',
  },
  Cpu: {
    gradient: 'linear-gradient(135deg, rgba(20, 126, 188, 0.12), rgba(59, 130, 246, 0.06))',
    glow: '0 4px 16px rgba(20, 126, 188, 0.15)',
    iconColor: '#147ebc',
    animClass: 'anim-pulse',
  },
  Lightbulb: {
    gradient: 'linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(251, 191, 36, 0.06))',
    glow: '0 4px 16px rgba(245, 158, 11, 0.15)',
    iconColor: '#f59e0b',
    animClass: 'anim-glow',
  },
  Terminal: {
    gradient: 'linear-gradient(135deg, rgba(34, 197, 94, 0.12), rgba(34, 197, 94, 0.04))',
    glow: '0 4px 16px rgba(34, 197, 94, 0.15)',
    iconColor: '#22c55e',
    animClass: 'anim-shimmer',
  },
  Code: {
    gradient: 'linear-gradient(135deg, rgba(34, 197, 94, 0.12), rgba(16, 185, 129, 0.06))',
    glow: '0 4px 16px rgba(34, 197, 94, 0.15)',
    iconColor: '#22c55e',
    animClass: 'anim-float',
  },
  MessageCircle: {
    gradient: 'linear-gradient(135deg, rgba(20, 126, 188, 0.12), rgba(59, 130, 246, 0.06))',
    glow: '0 4px 16px rgba(20, 126, 188, 0.15)',
    iconColor: '#3b82f6',
    animClass: 'anim-pulse',
  },
  MessageSquare: {
    gradient: 'linear-gradient(135deg, rgba(20, 126, 188, 0.12), rgba(59, 130, 246, 0.06))',
    glow: '0 4px 16px rgba(20, 126, 188, 0.15)',
    iconColor: '#3b82f6',
    animClass: 'anim-pulse',
  },
  Search: {
    gradient: 'linear-gradient(135deg, rgba(139, 92, 246, 0.12), rgba(139, 92, 246, 0.04))',
    glow: '0 4px 16px rgba(139, 92, 246, 0.15)',
    iconColor: '#8b5cf6',
    animClass: 'anim-shimmer',
  },
  Shield: {
    gradient: 'linear-gradient(135deg, rgba(34, 197, 94, 0.12), rgba(34, 197, 94, 0.04))',
    glow: '0 4px 16px rgba(34, 197, 94, 0.15)',
    iconColor: '#22c55e',
    animClass: 'anim-float',
  },
  Heart: {
    gradient: 'linear-gradient(135deg, rgba(239, 68, 68, 0.12), rgba(239, 68, 68, 0.04))',
    glow: '0 4px 16px rgba(239, 68, 68, 0.15)',
    iconColor: '#ef4444',
    animClass: 'anim-pulse',
  },
  HeartPulse: {
    gradient: 'linear-gradient(135deg, rgba(239, 68, 68, 0.12), rgba(239, 68, 68, 0.04))',
    glow: '0 4px 16px rgba(239, 68, 68, 0.15)',
    iconColor: '#ef4444',
    animClass: 'anim-pulse',
  },
  Users: {
    gradient: 'linear-gradient(135deg, rgba(20, 126, 188, 0.12), rgba(59, 130, 246, 0.06))',
    glow: '0 4px 16px rgba(20, 126, 188, 0.15)',
    iconColor: '#3b82f6',
    animClass: 'anim-float',
  },
  User: {
    gradient: 'linear-gradient(135deg, rgba(20, 126, 188, 0.12), rgba(59, 130, 246, 0.06))',
    glow: '0 4px 16px rgba(20, 126, 188, 0.15)',
    iconColor: '#3b82f6',
    animClass: 'anim-float',
  },
  BookOpen: {
    gradient: 'linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(245, 158, 11, 0.04))',
    glow: '0 4px 16px rgba(245, 158, 11, 0.15)',
    iconColor: '#f59e0b',
    animClass: 'anim-float',
  },
  GraduationCap: {
    gradient: 'linear-gradient(135deg, rgba(139, 92, 246, 0.12), rgba(139, 92, 246, 0.04))',
    glow: '0 4px 16px rgba(139, 92, 246, 0.15)',
    iconColor: '#8b5cf6',
    animClass: 'anim-float',
  },
  BarChart3: {
    gradient: 'linear-gradient(135deg, rgba(20, 126, 188, 0.12), rgba(59, 130, 246, 0.06))',
    glow: '0 4px 16px rgba(20, 126, 188, 0.15)',
    iconColor: '#3b82f6',
    animClass: 'anim-shimmer',
  },
  TrendingUp: {
    gradient: 'linear-gradient(135deg, rgba(34, 197, 94, 0.12), rgba(34, 197, 94, 0.04))',
    glow: '0 4px 16px rgba(34, 197, 94, 0.15)',
    iconColor: '#22c55e',
    animClass: 'anim-shimmer',
  },
  Puzzle: {
    gradient: 'linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(245, 158, 11, 0.04))',
    glow: '0 4px 16px rgba(245, 158, 11, 0.15)',
    iconColor: '#f59e0b',
    animClass: 'anim-shimmer',
  },
  Wrench: {
    gradient: 'linear-gradient(135deg, rgba(107, 114, 128, 0.12), rgba(107, 114, 128, 0.04))',
    glow: '0 4px 16px rgba(107, 114, 128, 0.15)',
    iconColor: '#6b7280',
    animClass: 'anim-shimmer',
  },
  Package: {
    gradient: 'linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(245, 158, 11, 0.04))',
    glow: '0 4px 16px rgba(245, 158, 11, 0.15)',
    iconColor: '#f59e0b',
    animClass: 'anim-float',
  },
  Image: {
    gradient: 'linear-gradient(135deg, rgba(236, 72, 153, 0.12), rgba(244, 114, 182, 0.06))',
    glow: '0 4px 16px rgba(236, 72, 153, 0.15)',
    iconColor: '#ec4899',
    animClass: 'anim-shimmer',
  },
  Volume2: {
    gradient: 'linear-gradient(135deg, rgba(236, 72, 153, 0.12), rgba(244, 114, 182, 0.06))',
    glow: '0 4px 16px rgba(236, 72, 153, 0.15)',
    iconColor: '#ec4899',
    animClass: 'anim-pulse',
  },
  PenTool: {
    gradient: 'linear-gradient(135deg, rgba(139, 92, 246, 0.12), rgba(139, 92, 246, 0.04))',
    glow: '0 4px 16px rgba(139, 92, 246, 0.15)',
    iconColor: '#8b5cf6',
    animClass: 'anim-float',
  },
  Laptop: {
    gradient: 'linear-gradient(135deg, rgba(107, 114, 128, 0.12), rgba(107, 114, 128, 0.04))',
    glow: '0 4px 16px rgba(107, 114, 128, 0.15)',
    iconColor: '#6b7280',
    animClass: 'anim-float',
  },
  Home: {
    gradient: 'linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(245, 158, 11, 0.04))',
    glow: '0 4px 16px rgba(245, 158, 11, 0.15)',
    iconColor: '#f59e0b',
    animClass: 'anim-float',
  },
  RefreshCw: {
    gradient: 'linear-gradient(135deg, rgba(34, 197, 94, 0.12), rgba(34, 197, 94, 0.04))',
    glow: '0 4px 16px rgba(34, 197, 94, 0.15)',
    iconColor: '#22c55e',
    animClass: 'anim-pulse',
  },
  Scale: {
    gradient: 'linear-gradient(135deg, rgba(139, 92, 246, 0.12), rgba(139, 92, 246, 0.04))',
    glow: '0 4px 16px rgba(139, 92, 246, 0.15)',
    iconColor: '#8b5cf6',
    animClass: 'anim-float',
  },
  LayoutGrid: {
    gradient: 'linear-gradient(135deg, rgba(20, 126, 188, 0.12), rgba(59, 130, 246, 0.06))',
    glow: '0 4px 16px rgba(20, 126, 188, 0.15)',
    iconColor: '#3b82f6',
    animClass: 'anim-shimmer',
  },
  default: {
    gradient: 'linear-gradient(135deg, rgba(20, 126, 188, 0.10), rgba(98, 169, 200, 0.05))',
    glow: '0 4px 16px rgba(20, 126, 188, 0.12)',
    iconColor: 'var(--lumi-primary)',
    animClass: 'anim-float',
  },
}

const currentTheme = computed(() => themeMap[props.theme] || themeMap.default)

const iconStyle = computed(() => ({
  background: currentTheme.value.gradient,
  color: currentTheme.value.iconColor,
}))

const containerSize = computed(() => `${props.size + 24}px`)
const borderRadius = computed(() => `${Math.round((props.size + 24) * 0.25)}px`)
</script>

<template>
  <div
    :class="['lumi-card-icon', { [currentTheme.animClass]: animated }]"
    :style="{
      '--icon-size': containerSize,
      '--icon-radius': borderRadius,
      ...iconStyle,
    }"
  >
    <div class="icon-inner">
      <component :is="icon" :size="size" />
    </div>
    <div class="icon-glow" :style="{ background: currentTheme.iconColor }" />
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
  transition: all 300ms ease-in-out;
}

.lumi-card-icon:hover {
  transform: translateY(-2px) scale(1.05);
  box-shadow: var(--icon-glow-shadow, 0 6px 20px rgba(20, 126, 188, 0.2));
}

.icon-inner {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-glow {
  position: absolute;
  width: 60%;
  height: 60%;
  border-radius: 50%;
  opacity: 0;
  filter: blur(12px);
  transition: opacity 300ms ease-in-out;
  pointer-events: none;
}

.lumi-card-icon:hover .icon-glow {
  opacity: 0.2;
}

/* Animations */
.anim-float {
  animation: lumi-float 3s ease-in-out infinite;
}

.anim-pulse {
  animation: lumi-pulse 2.5s ease-in-out infinite;
}

.anim-shimmer {
  animation: lumi-shimmer 3s ease-in-out infinite;
}

.anim-glow {
  animation: lumi-glow 2s ease-in-out infinite;
}

@keyframes lumi-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
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
  transform: translateY(-2px) scale(1.05);
}
</style>
