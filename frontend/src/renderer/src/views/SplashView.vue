<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Zap } from 'lucide-vue-next'
import { useApi } from '../composables/useApi'
import LumiButton from '../components/common/LumiButton.vue'

interface BackendStageData {
  stage: string
  detail?: string
}

interface LuomiNestApi {
  api?: {
    backend?: {
      subscribeStage?: (callback: (data: BackendStageData) => void) => (() => void)
    }
  }
}

const router = useRouter()
const { checkHealth } = useApi()

const progressPercent = ref(0)
const backendStatus = ref<'pending' | 'loading' | 'ready' | 'error'>('pending')
const statusText = ref('正在启动 LuomiNest 后端服务...')
const healthRetries = ref(0)
const MAX_RETRIES = 15
let pollTimer: ReturnType<typeof setTimeout> | null = null
let progressTimer: ReturnType<typeof setInterval> | null = null

const startProgressAnimation = (): void => {
  if (progressTimer) return
  progressTimer = setInterval(() => {
    if (progressPercent.value < 90) {
      progressPercent.value += 1
    }
  }, 600)
}

const stopProgressAnimation = (): void => {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

const startLoading = async (): Promise<void> => {
  backendStatus.value = 'loading'
  startProgressAnimation()

  await pollBackend()

  const status: string = backendStatus.value
  if (status === 'ready') {
    stopProgressAnimation()
    progressPercent.value = 100
    statusText.value = '后端服务已就绪'
    setTimeout(() => router.push('/login'), 400)
  } else {
    stopProgressAnimation()
    progressPercent.value = 100
    statusText.value = '后端服务未响应'
  }
}

const pollBackend = (): Promise<void> =>
  new Promise((resolve) => {
    const tryCheck = async (): Promise<void> => {
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

const retryBackend = async (): Promise<void> => {
  healthRetries.value = 0
  backendStatus.value = 'loading'
  progressPercent.value = 0
  statusText.value = '正在重新连接后端服务...'
  await pollBackend()
  const status: string = backendStatus.value
  if (status === 'ready') {
    stopProgressAnimation()
    progressPercent.value = 100
    statusText.value = '后端服务已就绪'
    setTimeout(() => router.push('/login'), 400)
  } else {
    stopProgressAnimation()
    progressPercent.value = 100
    statusText.value = '后端服务未响应'
  }
}

const skipToLogin = (): void => {
  if (pollTimer) clearTimeout(pollTimer)
  stopProgressAnimation()
  router.push('/login')
}

// 订阅主进程后端启动状态，实时更新文案
const subscribeBackendStage = (() => {
  const win = window as unknown as LuomiNestApi
  return win.api?.backend?.subscribeStage
    ? (cb: (data: BackendStageData) => void) => win.api!.backend!.subscribeStage!(cb)
    : undefined
})()

let unsubscribe: (() => void) | undefined

onMounted(() => {
  if (subscribeBackendStage) {
    unsubscribe = subscribeBackendStage((data) => {
      const stageMap: Record<string, string> = {
        spawning: '正在启动后端进程...',
        waiting: '等待后端健康检查...',
        ready: '后端服务已就绪',
        failed: '后端服务启动失败'
      }
      statusText.value = stageMap[data.stage] ?? statusText.value
    })
  }
  startLoading()
})

onBeforeUnmount(() => {
  if (pollTimer) clearTimeout(pollTimer)
  stopProgressAnimation()
  if (unsubscribe) unsubscribe()
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

      <p class="splash-status animate-fade-in">{{ statusText }}</p>

      <div v-if="backendStatus === 'error'" class="splash-error animate-fade-in">
        <p class="error-hint">后端服务未响应，请确认 LuomiNest 后端已启动</p>
        <div class="error-actions">
          <LumiButton variant="primary" size="sm" @click="retryBackend">
            <template #icon>
              <Zap :size="13" />
            </template>
            重新连接
          </LumiButton>
        </div>
      </div>
    </div>

    <div class="splash-footer">
      <div class="footer-bar">
        <div class="footer-bar-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>
      <LumiButton variant="ghost" size="sm" class="footer-skip" @click="skipToLogin">
        跳过
      </LumiButton>
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
  background: var(--bg);
}

.splash-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.bg-orb {
  position: absolute;
  border-radius: var(--radius-full);
  filter: blur(140px);
  opacity: 0.12;
  will-change: transform, opacity;
  animation: orb-drift 24s var(--ease-in-out) infinite;
}

.splash-orb-1 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, var(--lumi-brand-glow), transparent 70%);
  top: -150px;
  left: 30%;
}

.splash-orb-2 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, var(--lumi-brand-glow), transparent 70%);
  bottom: -100px;
  right: 20%;
  animation-delay: -12s;
}

.splash-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-7);
  width: 100%;
  max-width: 320px;
  padding: var(--space-8);
}

.splash-brand {
  text-align: center;
}

.splash-title {
  font-size: var(--text-5xl);
  font-weight: var(--font-bold);
  letter-spacing: -1px;
}

/* 加载条 */
.splash-bar {
  width: 100%;
  height: 2px;
  border-radius: var(--radius-xs);
  background: var(--bg-secondary);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: var(--radius-xs);
  background: var(--lumi-brand);
  transition: width var(--transition-normal);
}

/* 状态文案 */
.splash-status {
  font-size: var(--text-sm);
  color: var(--text-muted);
  text-align: center;
  margin: 0;
}

/* 错误状态 */
.splash-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
}

.error-hint {
  font-size: var(--text-sm);
  color: var(--text-muted);
  text-align: center;
}

.error-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

/* 底部 */
.splash-footer {
  position: absolute;
  bottom: var(--space-6);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  z-index: 1;
}

.footer-bar {
  width: 100px;
  height: 1px;
  background: var(--bg-secondary);
  overflow: hidden;
}

.footer-bar-fill {
  height: 100%;
  background: var(--lumi-brand);
  transition: width var(--transition-normal);
}

.footer-skip {
  opacity: 0.6;
  transition: opacity var(--transition-normal);
}

.footer-skip:hover {
  opacity: 1;
}

/* 动画 */
.animate-brand-enter {
  animation: brand-enter var(--duration-enter) var(--ease-out-expo) both;
}

.animate-slide-up {
  animation: lumi-slide-up var(--duration-enter) var(--ease-out-expo) var(--duration-leave) both;
}

.animate-fade-in {
  animation: lumi-fade-in var(--duration-slow) var(--ease-out-expo) both;
}

@keyframes brand-enter {
  0% { opacity: 0; transform: translateY(20px); filter: blur(2px); }
  100% { opacity: 1; transform: translateY(0); filter: blur(0); }
}

button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}

</style>
