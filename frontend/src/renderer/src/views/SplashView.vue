<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Zap } from 'lucide-vue-next'
import { useApi } from '../composables/useApi'

const router = useRouter()
const { checkHealth } = useApi()

const progressPercent = ref(0)
const backendStatus = ref<'pending' | 'loading' | 'ready' | 'error'>('pending')
const healthRetries = ref(0)
const MAX_RETRIES = 30
let pollTimer: ReturnType<typeof setTimeout> | null = null

const startLoading = async () => {
  progressPercent.value = 30
  backendStatus.value = 'loading'

  await pollBackend()

  if (backendStatus.value === 'ready') {
    progressPercent.value = 100
    setTimeout(() => router.push('/login'), 400)
  } else {
    progressPercent.value = 100
  }
}

const pollBackend = (): Promise<void> =>
  new Promise((resolve) => {
    const tryCheck = async () => {
      const ok = await checkHealth()
      if (ok) {
        backendStatus.value = 'ready'
        resolve()
        return
      }
      healthRetries.value++
      if (healthRetries.value >= MAX_RETRIES) {
        backendStatus.value = 'error'
        resolve()
        return
      }
      pollTimer = setTimeout(tryCheck, 1000)
    }
    tryCheck()
  })

const retryBackend = async () => {
  healthRetries.value = 0
  backendStatus.value = 'loading'
  progressPercent.value = 30
  await pollBackend()
  if (backendStatus.value === 'ready') {
    progressPercent.value = 100
    setTimeout(() => router.push('/login'), 400)
  }
}

onMounted(() => {
  startLoading()
})

onBeforeUnmount(() => {
  if (pollTimer) clearTimeout(pollTimer)
})
</script>

<template>
  <div class="splash-view">
    <div class="splash-bg">
      <div class="bg-orb splash-orb-1"></div>
      <div class="bg-orb splash-orb-2"></div>
    </div>

    <div class="splash-content">
      <div class="splash-brand animate-brand-enter">
        <h1 class="splash-title lumi-gradient-text">LuomiNest</h1>
      </div>

      <div class="splash-bar animate-slide-up">
        <div class="bar-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>

      <div v-if="backendStatus === 'error'" class="splash-error animate-fade-in">
        <p class="error-hint">后端服务未响应，请确认 LuomiNest 后端已启动</p>
        <div class="error-actions">
          <button class="splash-retry-btn" @click="retryBackend">
            <Zap :size="13" />
            <span>重新连接</span>
          </button>
          <button class="splash-skip-btn" @click="router.push('/login')">
            跳过
          </button>
        </div>
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

.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(140px);
  opacity: 0.12;
  animation: orb-drift 24s ease-in-out infinite;
}

.splash-orb-1 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, var(--lumi-primary-glow), transparent 70%);
  top: -150px;
  left: 30%;
}

.splash-orb-2 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, var(--lumi-primary-glow), transparent 70%);
  bottom: -100px;
  right: 20%;
  animation-delay: -12s;
}

@keyframes orb-drift {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(20px, -15px) scale(1.05); }
}

.splash-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
  width: 100%;
  max-width: 320px;
  padding: 40px;
}

.splash-brand {
  text-align: center;
}

.splash-title {
  font-size: 36px;
  font-weight: 700;
  letter-spacing: -1px;
}

/* 加载条 */
.splash-bar {
  width: 100%;
  height: 2px;
  border-radius: 1px;
  background: var(--workspace-panel);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 1px;
  background: var(--lumi-primary);
  transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}

/* 错误状态 */
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
}

.error-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.splash-retry-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 600;
  background: var(--lumi-primary);
  color: var(--text-inverse);
  cursor: pointer;
  transition: all 250ms ease-in-out;
}

.splash-retry-btn:hover {
  background: var(--lumi-primary-hover);
}

.splash-skip-btn {
  padding: 8px 16px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms ease-in-out;
  border-radius: var(--radius-md);
}

.splash-skip-btn:hover {
  color: var(--text-secondary);
}

/* 底部 */
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
  opacity: 0.5;
}

.footer-bar {
  width: 100px;
  height: 1px;
  background: var(--workspace-panel);
  overflow: hidden;
}

.footer-bar-fill {
  height: 100%;
  background: var(--lumi-primary);
  transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}

/* 动画 */
.animate-brand-enter {
  animation: brand-enter 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.animate-slide-up {
  animation: lumi-slide-up 0.4s ease-out 0.2s both;
}

.animate-fade-in {
  animation: lumi-fade-in 0.3s ease-out both;
}

@keyframes brand-enter {
  0% { opacity: 0; transform: translateY(20px); filter: blur(2px); }
  100% { opacity: 1; transform: translateY(0); filter: blur(0); }
}
</style>
