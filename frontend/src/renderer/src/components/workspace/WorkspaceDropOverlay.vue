<script setup lang="ts">
import { UploadCloud } from 'lucide-vue-next'

const props = defineProps<{
  visible: boolean
}>()
</script>

<template>
  <Transition name="global-drop-fade">
    <div v-if="props.visible" class="global-drop-overlay" @dragover.prevent @drop.prevent>
      <div class="drop-content">
        <div class="drop-icon-wrapper">
          <UploadCloud :size="64" class="drop-main-icon" />
          <div class="drop-particles">
            <span class="particle p1"></span>
            <span class="particle p2"></span>
            <span class="particle p3"></span>
            <span class="particle p4"></span>
            <span class="particle p5"></span>
          </div>
        </div>
        <h3 class="drop-title">在此处拖放文件</h3>
        <p class="drop-desc">
          支持图片、文档、代码等常见格式
        </p>
        <p class="drop-hint">或按 Ctrl+V 粘贴文件</p>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.global-drop-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: var(--z-modal);
  background: var(--overlay-bg);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.drop-content {
  text-align: center;
  padding: 60px 80px;
  border-radius: var(--radius-2xl);
  background: var(--surface);
  border: 2px dashed var(--lumi-brand-border);
  box-shadow: 0 20px 60px var(--overlay-subtle), 0 0 80px var(--lumi-brand-light);
  max-width: 560px;
}

.drop-icon-wrapper {
  position: relative;
  display: inline-block;
  margin-bottom: var(--space-6);
}

.drop-main-icon {
  color: var(--lumi-brand);
  animation: drop-bounce 2s var(--ease-in-out) infinite;
}

.drop-particles {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 140px;
  height: 140px;
  pointer-events: none;
}

.particle {
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
  animation: float-particle 3s var(--ease-in-out) infinite;
  opacity: 0.7;
}

.p1 { top: -10px; left: 10px; animation-delay: 0s; }
.p2 { top: 0; right: -5px; animation-delay: 0.4s; }
.p3 { bottom: 5px; right: 0; animation-delay: 0.8s; }
.p4 { bottom: calc(-1 * var(--space-2)); left: 5px; animation-delay: 1.2s; }
.p5 { top: 5px; left: -5px; animation-delay: 1.6s; }

@keyframes drop-bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-12px); }
}

@keyframes float-particle {
  0%, 100% { transform: translate(0, 0) rotate(0deg); }
  25% { transform: translate(6px, -8px) rotate(10deg); }
  50% { transform: translate(-4px, -14px) rotate(-5deg); }
  75% { transform: translate(8px, -4px) rotate(8deg); }
}

.drop-title {
  font-size: var(--text-3xl);
  font-weight: 700;
  color: var(--text);
  margin: 0 0 var(--space-4);
  letter-spacing: 0.3px;
}

.drop-desc {
  font-size: var(--text-base);
  color: var(--text-secondary);
  margin: 0 0 10px;
  line-height: 1.7;
  word-break: break-all;
}

.drop-hint {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin: 0;
}

.global-drop-fade-enter-active,
.global-drop-fade-leave-active {
  transition: all var(--duration-normal) var(--ease-default);
}

.global-drop-fade-enter-from,
.global-drop-fade-leave-to {
  opacity: 0;
}
</style>
