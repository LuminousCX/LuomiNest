<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Palette,
  Sparkles,
  Heart,
  Eye,
  Smile,
  Frown,
  Meh,
  Zap,
  Volume2,
  RotateCcw,
  Maximize2,
  Download,
  Settings2
} from 'lucide-vue-next'

const avatarModes = [
  { id: 'live2d', label: 'Live2D', desc: 'Cubism 5 二次元', active: true },
  { id: 'vrm', label: 'VRM', desc: '3D 全身模型', active: false },
  { id: 'pixel', label: 'PixelPet', desc: 'Q版电子宠物', active: false }
]

const currentMode = ref('live2d')

const emotions = [
  { id: 'happy', icon: Smile, label: '开心', color: '#f59e0b' },
  { id: 'sad', icon: Frown, label: '难过', color: '#6366f1' },
  { id: 'neutral', icon: Meh, label: '平静', color: '#8b5cf6' },
  { id: 'love', icon: Heart, label: '喜爱', color: '#ec4899' },
  { id: 'surprise', icon: Zap, label: '惊讶', color: '#22c55e' }
]

const currentEmotion = ref(emotions[0])

const expressionValue = computed(() => {
  const map: Record<string, number> = {
    happy: 0.8, sad: -0.4, neutral: 0, love: 0.6, surprise: 0.7
  }
  return map[currentEmotion.value.id] ?? 0
})

const idleAnimations = [
  { name: '呼吸', status: 'running', progress: 65 },
  { name: '眨眼', status: 'running', progress: 40 },
  { name: '待机微动', status: 'running', progress: 80 },
  { name: '头部追踪', status: 'paused', progress: 0 }
]

const skinList = [
  { name: '洛洛 · 默认', type: 'Live2D', thumb: null, tags: ['默认', '日常'] },
  { name: '洛洛 · 睡衣', type: 'Live2D', thumb: null, tags: ['休闲', '夜晚'] },
  { name: '洛洛 · 学院风', type: 'VRM', thumb: null, tags: ['正式', '3D'] },
  { name: '像素洛洛', type: 'PixelPet', thumb: null, tags: ['复古', '轻量'] }
]

const selectedSkin = ref(0)

function selectMode(modeId: string) {
  currentMode.value = modeId
}

function selectEmotion(emo: typeof emotions[0]) {
  currentEmotion.value = emo
}
</script>

<template>
  <div class="avatar-view">
    <div class="avatar-header">
      <div class="header-left">
        <Palette :size="20" />
        <h2>皮套工坊</h2>
        <span class="header-badge">Live2D / VRM / PixelPet</span>
      </div>
      <div class="header-actions">
        <button class="h-btn" title="重置姿态"><RotateCcw :size="16" /></button>
        <button class="h-btn" title="全屏模式"><Maximize2 :size="16" /></button>
        <button class="h-btn primary" title="导入皮套"><Download :size="16" /> 导入</button>
        <button class="h-btn" title="高级设置"><Settings2 :size="16" /></button>
      </div>
    </div>

    <div class="avatar-body">
      <div class="avatar-stage animate-stage-appear">
        <div class="stage-canvas">
          <div class="avatar-placeholder" :class="[`emotion-${currentEmotion.id}`]">
            <div class="avatar-ring"></div>
            <div class="avatar-core">
              <Sparkles :size="48" class="avatar-sparkle" />
              <span class="avatar-label">{{ currentMode.toUpperCase() }}</span>
            </div>
            <div class="avatar-particles">
              <span v-for="i in 6" :key="i" class="particle" :style="{ '--delay': `${i * 0.15}s` }"></span>
            </div>
          </div>
          <div class="stage-overlay">
            <div class="overlay-tag mode-tag">
              <Eye :size="12" /> {{ avatarModes.find(m => m.id === currentMode)?.label }}
            </div>
            <div class="overlay-tag emotion-tag" :style="{ borderColor: currentEmotion.color }">
              <component :is="currentEmotion.icon" :size="12" />
              {{ currentEmotion.label }}
            </div>
          </div>
        </div>

        <div class="stage-controls">
          <div class="mode-switcher">
            <button
              v-for="mode in avatarModes"
              :key="mode.id"
              :class="['mode-btn', { active: currentMode === mode.id }]"
              @click="selectMode(mode.id)"
            >
              <span class="mode-name">{{ mode.label }}</span>
              <span class="mode-desc">{{ mode.desc }}</span>
            </button>
          </div>

          <div class="emotion-panel">
            <div class="panel-title">
              <Heart :size="14" />
              <span>情感驱动</span>
              <span class="expression-value">PAD: {{ expressionValue > 0 ? '+' : '' }}{{ expressionValue.toFixed(1) }}</span>
            </div>
            <div class="emotion-grid">
              <button
                v-for="emo in emotions"
                :key="emo.id"
                :class="['emo-btn', { active: currentEmotion.id === emo.id }]"
                :style="{ '--emo-color': emo.color }"
                @click="selectEmotion(emo)"
              >
                <component :is="emo.icon" :size="20" />
                <span>{{ emo.label }}</span>
              </button>
            </div>
          </div>

          <div class="idle-panel">
            <div class="panel-title">
              <Volume2 :size="14" />
              <span>闲置动画</span>
            </div>
            <div class="idle-list">
              <div
                v-for="(anim, idx) in idleAnimations"
                :key="idx"
                class="idle-item"
              >
                <div class="idle-info">
                  <span class="idle-name">{{ anim.name }}</span>
                  <span :class="['idle-status', anim.status]">{{ anim.status === 'running' ? '运行中' : '已暂停' }}</span>
                </div>
                <div class="idle-bar">
                  <div
                    class="idle-fill"
                    :class="anim.status"
                    :style="{ width: anim.progress + '%' }"
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="skin-sidebar animate-slide-right">
        <div class="sidebar-title">皮套库</div>
        <div class="skin-list">
          <div
            v-for="(skin, idx) in skinList"
            :key="idx"
            :class="['skin-card', { selected: selectedSkin === idx }]"
            @click="selectedSkin = idx"
          >
            <div class="skin-thumb">
              <Palette :size="24" />
            </div>
            <div class="skin-info">
              <span class="skin-name">{{ skin.name }}</span>
              <span class="skin-type">{{ skin.type }}</span>
            </div>
            <div class="skin-tags">
              <span v-for="tag in skin.tags" :key="tag" class="skin-tag">{{ tag }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.avatar-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
}

.avatar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-muted);
}

.header-left h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
}

.header-badge {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 20px;
  background: rgba(13, 148, 136, 0.1);
  color: var(--lumi-primary);
  font-weight: 500;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.h-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-muted);
  transition: all 300ms ease-in-out;
  cursor: pointer;
  white-space: nowrap;
}

.h-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.h-btn.primary {
  background: var(--lumi-primary);
  color: #fff;
}

.h-btn.primary:hover {
  background: var(--lumi-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(13, 148, 136, 0.3);
}

.avatar-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.avatar-stage {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.stage-canvas {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 320px;
  background:
    radial-gradient(circle at 50% 50%, rgba(13, 148, 136, 0.04) 0%, transparent 70%),
    var(--surface);
  overflow: hidden;
}

.avatar-placeholder {
  position: relative;
  width: 260px;
  height: 340px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 24px;
  background: linear-gradient(145deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
  border: 1px solid var(--border);
  transition: all 500ms ease-in-out;
}

.avatar-ring {
  position: absolute;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  border: 1.5px dashed rgba(13, 148, 136, 0.25);
  animation: ring-spin 12s linear infinite;
}

@keyframes ring-spin {
  to { transform: rotate(360deg); }
}

.avatar-core {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  z-index: 1;
}

.avatar-sparkle {
  color: var(--lumi-primary);
  opacity: 0.6;
  animation: sparkle-pulse 2s ease-in-out infinite;
}

@keyframes sparkle-pulse {
  0%, 100% { opacity: 0.4; transform: scale(1); }
  50% { opacity: 0.9; transform: scale(1.1); }
}

.avatar-label {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 3px;
  color: var(--text-muted);
}

.avatar-particles {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.particle {
  position: absolute;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--lumi-primary);
  opacity: 0;
  animation: particle-float 3s ease-in-out infinite;
  animation-delay: var(--delay);
}

@keyframes particle-float {
  0% { opacity: 0; transform: translateY(0) scale(0); }
  30% { opacity: 0.6; }
  100% { opacity: 0; transform: translateY(-120px) scale(1); }
}

.stage-overlay {
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  gap: 8px;
}

.overlay-tag {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 500;
  backdrop-filter: blur(8px);
  background: rgba(0,0,0,0.35);
  border: 1px solid rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.85);
}

.emotion-tag {
  border-color: var(--emo-color, var(--lumi-primary));
  color: var(--emo-color, var(--lumi-primary));
}

.stage-controls {
  display: flex;
  gap: 16px;
  padding: 16px 20px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
  overflow-x: auto;
}

.mode-switcher {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.mode-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 10px 18px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  white-space: nowrap;
}

.mode-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.mode-btn.active {
  background: rgba(13, 148, 136, 0.1);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.mode-name {
  font-size: 13px;
  font-weight: 600;
}

.mode-desc {
  font-size: 10px;
  opacity: 0.6;
}

.emotion-panel,
.idle-panel {
  flex-shrink: 0;
  min-width: 200px;
  max-width: 240px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.expression-value {
  margin-left: auto;
  font-family: monospace;
  font-size: 11px;
  color: var(--lumi-primary);
  opacity: 0.7;
}

.emotion-grid {
  display: flex;
  gap: 6px;
}

.emo-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  font-size: 11px;
}

.emo-btn:hover {
  background: color-mix(in srgb, var(--emo-color, #888) 8%, transparent);
  color: var(--text);
  transform: translateY(-2px);
}

.emo-btn.active {
  background: color-mix(in srgb, var(--emo-color, #888) 14%, transparent);
  border-color: var(--emo-color, var(--lumi-primary));
  color: var(--emo-color, var(--lumi-primary));
  box-shadow: 0 2px 12px color-mix(in srgb, var(--emo-color, #888) 18%, transparent);
}

.idle-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.idle-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.idle-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.idle-name {
  font-size: 12px;
  color: var(--text);
}

.idle-status {
  font-size: 10px;
  padding: 1px 8px;
  border-radius: 10px;
}

.idle-status.running {
  background: rgba(34, 197, 94, 0.12);
  color: #22c55e;
}

.idle-status.paused {
  background: rgba(107, 114, 128, 0.12);
  color: #6b7280;
}

.idle-bar {
  height: 3px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
}

.idle-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 1000ms ease-in-out;
}

.idle-fill.running {
  background: linear-gradient(90deg, var(--lumi-primary), #22c55e);
  animation: bar-pulse 2s ease-in-out infinite;
}

@keyframes bar-pulse {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}

.skin-sidebar {
  width: 260px;
  border-left: 1px solid var(--border);
  padding: 20px 16px;
  overflow-y: auto;
  flex-shrink: 0;
  background: var(--surface);
}

.sidebar-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--text);
}

.skin-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skin-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all 300ms ease-in-out;
}

.skin-card:hover {
  background: var(--surface-hover);
  border-color: rgba(13, 148, 136, 0.3);
}

.skin-card.selected {
  background: rgba(13, 148, 136, 0.08);
  border-color: var(--lumi-primary);
}

.skin-thumb {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  background: var(--surface-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  flex-shrink: 0;
}

.skin-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.skin-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}

.skin-type {
  font-size: 11px;
  color: var(--text-muted);
}

.skin-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.skin-tag {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 8px;
  background: var(--surface-hover);
  color: var(--text-muted);
}

@keyframes stage-appear {
  0% { opacity: 0; transform: scale(0.96); }
  100% { opacity: 1; transform: scale(1); }
}

.animate-stage-appear {
  animation: stage-appear 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes slide-right {
  0% { opacity: 0; transform: translateX(30px); }
  100% { opacity: 1; transform: translateX(0); }
}

.animate-slide-right {
  animation: slide-right 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}
</style>
