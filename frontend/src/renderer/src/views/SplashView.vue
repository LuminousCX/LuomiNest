<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Cpu, Zap, Database, Shield, Check, Loader2 } from 'lucide-vue-next'
import { useApi } from '../composables/useApi'
import LumiBrandStar from '../components/common/LumiBrandStar.vue'

const router = useRouter()
const { checkHealth } = useApi()

const BOOT_PHASES = [
  { key: 'init', label: '初始化核心引擎', icon: Cpu, color: '#147EBC' },
  { key: 'config', label: '加载配置与资源', icon: Database, color: '#8b5cf6' },
  { key: 'backend', label: '连接后端服务', icon: Zap, color: '#f59e0b' },
  { key: 'auth', label: '准备认证模块', icon: Shield, color: '#22c55e' },
] as const

type PhaseKey = typeof BOOT_PHASES[number]['key']

const phaseStates = ref<Record<PhaseKey, 'pending' | 'running' | 'done' | 'error'>>({
  init: 'pending',
  config: 'pending',
  backend: 'pending',
  auth: 'pending',
})
const progressPercent = ref(0)
const showParticles = ref(true)
const backendReady = ref(false)
const healthRetries = ref(0)
const MAX_RETRIES = 30
let pollTimer: ReturnType<typeof setInterval> | null = null
let phaseTimer: ReturnType<typeof setTimeout> | null = null

const advancePhase = async () => {
  for (let i = 0; i < BOOT_PHASES.length; i++) {
    const phase = BOOT_PHASES[i]
    phaseStates.value[phase.key] = 'running'

    if (phase.key === 'backend') {
      await pollBackend()
    } else {
      await simulateDelay(phase.key === 'init' ? 600 : phase.key === 'config' ? 500 : 300)
    }

    if (phase.key === 'backend' && !backendReady.value) {
      phaseStates.value[phase.key] = 'error'
      return
    }

    phaseStates.value[phase.key] = 'done'
    progressPercent.value = Math.round(((i + 1) / BOOT_PHASES.length) * 100)
  }

  setTimeout(() => {
    showParticles.value = false
    setTimeout(() => router.push('/login'), 400)
  }, 500)
}

const simulateDelay = (ms: number): Promise<void> =>
  new Promise((resolve) => {
    phaseTimer = setTimeout(resolve, ms)
  })

const pollBackend = (): Promise<void> =>
  new Promise((resolve) => {
    const tryCheck = async () => {
      const ok = await checkHealth()
      if (ok) {
        backendReady.value = true
        resolve()
        return
      }
      healthRetries.value++
      if (healthRetries.value >= MAX_RETRIES) {
        resolve()
        return
      }
      pollTimer = setTimeout(tryCheck, 1000)
    }
    tryCheck()
  })

const retryBackend = async () => {
  phaseStates.value.backend = 'running'
  healthRetries.value = 0
  backendReady.value = false
  await pollBackend()
  if (backendReady.value) {
    phaseStates.value.backend = 'done'
    progressPercent.value = Math.round((3 / BOOT_PHASES.length) * 100)
    phaseStates.value.auth = 'running'
    await simulateDelay(300)
    phaseStates.value.auth = 'done'
    progressPercent.value = 100
    setTimeout(() => {
      showParticles.value = false
      setTimeout(() => router.push('/login'), 400)
    }, 500)
  } else {
    phaseStates.value.backend = 'error'
  }
}

onMounted(() => {
  advancePhase()
})

onBeforeUnmount(() => {
  if (pollTimer) clearTimeout(pollTimer)
  if (phaseTimer) clearTimeout(phaseTimer)
})
</script>

<template>
  <div class="splash-view">
    <div class="splash-bg">
      <div class="bg-orb splash-orb-1"></div>
      <div class="bg-orb splash-orb-2"></div>
      <div class="bg-orb splash-orb-3"></div>
      <div class="bg-grid"></div>
    </div>

    <Transition name="particles-fade">
      <div v-if="showParticles" class="splash-particles">
        <span v-for="i in 12" :key="i" class="particle-dot" :style="{
          '--delay': `${i * 0.3}s`,
          '--x': `${10 + (i * 7) % 80}%`,
          '--y': `${15 + (i * 11) % 70}%`,
          '--size': `${2 + (i % 3)}px`,
        }"></span>
      </div>
    </Transition>

    <div class="splash-content">
      <div class="splash-brand animate-brand-enter">
        <div class="splash-logo-ring">
          <LumiBrandStar :size="56" />
          <div class="ring-glow"></div>
        </div>
        <h1 class="splash-title lumi-gradient-text">LuomiNest</h1>
        <p class="splash-subtitle">LuminousChenXi AI Companion Platform</p>
      </div>

      <div class="boot-sequence animate-slide-up">
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
        </div>

        <div class="boot-phases">
          <div
            v-for="(phase, idx) in BOOT_PHASES"
            :key="phase.key"
            :class="['boot-phase', phaseStates[phase.key]]"
            :style="{ '--phase-color': phase.color, '--phase-delay': `${idx * 80}ms` }"
          >
            <div class="phase-icon">
              <Check v-if="phaseStates[phase.key] === 'done'" :size="14" />
              <Loader2 v-else-if="phaseStates[phase.key] === 'running'" :size="14" class="spin-animation" />
              <component v-else :is="phase.icon" :size="14" />
            </div>
            <span class="phase-label">{{ phase.label }}</span>
            <span v-if="phase.key === 'backend' && phaseStates[phase.key] === 'running'" class="phase-detail">
              {{ healthRetries > 0 ? `重试中 (${healthRetries}/${MAX_RETRIES})` : '等待响应...' }}
            </span>
            <span v-if="phaseStates[phase.key] === 'error'" class="phase-error">
              连接失败
            </span>
          </div>
        </div>
      </div>

      <div v-if="phaseStates.backend === 'error'" class="splash-error animate-fade-in">
        <p class="error-hint">后端服务未响应，请确认 LuomiNest 后端已启动 (端口 18000)</p>
        <button class="splash-retry-btn" @click="retryBackend">
          <Zap :size="14" />
          <span>重新连接</span>
        </button>
        <button class="splash-skip-btn" @click="router.push('/login')">
          跳过，直接进入
        </button>
      </div>
    </div>

    <div class="splash-footer">
      <span class="footer-text">LuomiNest Engine Warming Up...</span>
      <div class="footer-bar">
        <div class="footer-bar-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.splash-view {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  width: 100%;
  overflow: hidden;
  background: var(--workspace-bg);
}

.splash-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--lumi-primary-subtle) 1px, transparent 1px),
    linear-gradient(90deg, var(--lumi-primary-subtle) 1px, transparent 1px);
  background-size: 40px 40px;
  opacity: 0.5;
}

.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.3;
  animation: orb-drift 15s ease-in-out infinite;
}

.splash-orb-1 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, var(--lumi-primary-glow), transparent 70%);
  top: -80px;
  left: 30%;
  animation-delay: 0s;
}

.splash-orb-2 {
  width: 250px;
  height: 250px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.15), transparent 70%);
  bottom: -40px;
  right: 20%;
  animation-delay: -5s;
}

.splash-orb-3 {
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, rgba(245, 158, 11, 0.1), transparent 70%);
  top: 40%;
  left: -60px;
  animation-delay: -10s;
}

@keyframes orb-drift {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -20px) scale(1.08); }
  66% { transform: translate(-15px, 15px) scale(0.95); }
}

.splash-particles {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.particle-dot {
  position: absolute;
  width: var(--size);
  height: var(--size);
  border-radius: 50%;
  background: var(--lumi-primary);
  left: var(--x);
  top: var(--y);
  opacity: 0;
  animation: particle-float 4s ease-in-out infinite;
  animation-delay: var(--delay);
}

@keyframes particle-float {
  0% { opacity: 0; transform: translateY(0) scale(0.5); }
  20% { opacity: 0.6; }
  50% { opacity: 0.4; transform: translateY(-20px) scale(1); }
  80% { opacity: 0.2; }
  100% { opacity: 0; transform: translateY(-40px) scale(0.3); }
}

.particles-fade-leave-active {
  transition: opacity 0.4s ease-in-out;
}

.particles-fade-leave-to {
  opacity: 0;
}

.splash-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 40px;
  width: 100%;
  max-width: 420px;
  padding: 40px;
}

.splash-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
}

.splash-logo-ring {
  position: relative;
  width: 88px;
  height: 88px;
  border-radius: 24px;
  background: var(--lumi-primary-gradient-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 32px var(--lumi-primary-glow);
}

.ring-glow {
  position: absolute;
  inset: -8px;
  border-radius: 32px;
  border: 1.5px solid var(--lumi-primary-border);
  opacity: 0;
  animation: ring-breathe 2s ease-in-out infinite;
}

@keyframes ring-breathe {
  0%, 100% { opacity: 0; transform: scale(0.95); }
  50% { opacity: 0.6; transform: scale(1.02); }
}

.splash-title {
  font-size: 36px;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.splash-subtitle {
  font-size: 14px;
  color: var(--text-muted);
  letter-spacing: 0.5px;
}

.boot-sequence {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.progress-track {
  width: 100%;
  height: 3px;
  border-radius: 2px;
  background: var(--workspace-panel);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--lumi-primary);
  transition: width 0.5s cubic-bezier(0.22, 1, 0.36, 1);
  box-shadow: 0 0 8px var(--lumi-primary-glow);
}

.boot-phases {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.boot-phase {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  transition: all 300ms ease-in-out;
  animation: phase-enter 0.3s ease-out both;
  animation-delay: var(--phase-delay);
}

@keyframes phase-enter {
  from { opacity: 0; transform: translateX(-8px); }
  to { opacity: 1; transform: translateX(0); }
}

.boot-phase.running {
  background: color-mix(in srgb, var(--phase-color) 6%, transparent);
  border: 1px solid color-mix(in srgb, var(--phase-color) 15%, transparent);
}

.boot-phase.done {
  opacity: 0.6;
}

.boot-phase.error {
  background: var(--lumi-accent-light);
  border: 1px solid var(--lumi-accent-border);
}

.phase-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--text-muted);
  background: var(--workspace-panel);
  transition: all 300ms ease-in-out;
}

.boot-phase.running .phase-icon {
  background: color-mix(in srgb, var(--phase-color) 12%, transparent);
  color: var(--phase-color);
}

.boot-phase.done .phase-icon {
  background: color-mix(in srgb, var(--lumi-success) 12%, transparent);
  color: var(--lumi-success);
}

.boot-phase.error .phase-icon {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.phase-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  flex: 1;
}

.boot-phase.running .phase-label {
  color: var(--text-primary);
  font-weight: 600;
}

.boot-phase.done .phase-label {
  color: var(--text-muted);
}

.boot-phase.error .phase-label {
  color: var(--lumi-accent);
  font-weight: 600;
}

.phase-detail {
  font-size: 11px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.phase-error {
  font-size: 11px;
  color: var(--lumi-accent);
  font-weight: 500;
}

.splash-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.error-hint {
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
  line-height: 1.6;
}

.splash-retry-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 12px 24px;
  border-radius: var(--radius-lg);
  font-size: 14px;
  font-weight: 600;
  background: var(--lumi-primary);
  color: var(--text-inverse);
  cursor: pointer;
  transition: all 300ms ease-in-out;
}

.splash-retry-btn:hover {
  background: var(--lumi-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 6px 20px var(--lumi-primary-border);
}

.splash-skip-btn {
  padding: 8px 16px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms ease-in-out;
  border-radius: var(--radius-full);
}

.splash-skip-btn:hover {
  color: var(--text-secondary);
  background: var(--workspace-panel);
}

.splash-footer {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  z-index: 1;
}

.footer-text {
  font-size: 11px;
  color: var(--text-muted);
  letter-spacing: 1px;
  text-transform: uppercase;
  opacity: 0.6;
  animation: lumi-pulse-soft 2s ease-in-out infinite;
}

.footer-bar {
  width: 120px;
  height: 2px;
  border-radius: 1px;
  background: var(--workspace-panel);
  overflow: hidden;
}

.footer-bar-fill {
  height: 100%;
  border-radius: 1px;
  background: var(--lumi-primary);
  transition: width 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}

.animate-brand-enter {
  animation: brand-enter 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.animate-slide-up {
  animation: lumi-slide-up 0.5s ease-out 0.3s both;
}

.animate-fade-in {
  animation: lumi-fade-in 0.4s ease-out both;
}

@keyframes brand-enter {
  0% { opacity: 0; transform: translateY(30px) scale(0.94); filter: blur(4px); }
  100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
}
</style>
