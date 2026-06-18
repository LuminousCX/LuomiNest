<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Monitor,
  ArrowRight,
  Eye,
  EyeOff,
  Mail,
  Lock,
  User,
  LogIn,
  Cloud,
  ChevronRight,
} from 'lucide-vue-next'
import LumiBrandStar from '../components/common/LumiBrandStar.vue'

const router = useRouter()

type LoginMode = 'select' | 'local' | 'online'

const loginMode = ref<LoginMode>('select')

const localForm = ref({ username: '', password: '' })
const onlineForm = ref({ email: '', password: '' })
const showLocalPassword = ref(false)
const showOnlinePassword = ref(false)
const isLoggingIn = ref(false)
const loginError = ref('')

const canLocalLogin = computed(() =>
  localForm.value.username.trim().length > 0 && localForm.value.password.length > 0
)

const canOnlineLogin = computed(() =>
  onlineForm.value.email.trim().length > 0 && onlineForm.value.password.length > 0
)

const handleLocalLogin = async () => {
  if (!canLocalLogin.value) return
  loginError.value = ''
  isLoggingIn.value = true
  setTimeout(() => {
    isLoggingIn.value = false
    router.push('/workspace')
  }, 800)
}

const handleOnlineLogin = async () => {
  if (!canOnlineLogin.value) return
  loginError.value = ''
  isLoggingIn.value = true
  setTimeout(() => {
    isLoggingIn.value = false
    loginError.value = '在线登录服务暂未开放，敬请期待'
  }, 1200)
}

const handleSkip = () => {
  router.push('/workspace')
}

const goBack = () => {
  loginMode.value = 'select'
  loginError.value = ''
}
</script>

<template>
  <div class="login-view">
    <div class="login-bg">
      <div class="bg-orb login-orb-1"></div>
      <div class="bg-orb login-orb-2"></div>
      <div class="bg-grid"></div>
    </div>

    <div class="login-container">
      <Transition name="login-step" mode="out-in">
        <!-- Mode Selection -->
        <div v-if="loginMode === 'select'" key="select" class="login-card">
          <div class="login-brand animate-brand-enter">
            <div class="login-logo">
              <LumiBrandStar :size="40" />
            </div>
            <h1 class="login-title lumi-gradient-text">LuomiNest</h1>
            <p class="login-subtitle">选择登录方式以同步你的数据</p>
          </div>

          <div class="login-options animate-slide-up">
            <button class="login-option-card" @click="loginMode = 'local'">
              <div class="option-icon local-icon">
                <Monitor :size="22" />
              </div>
              <div class="option-info">
                <span class="option-title">本地登录</span>
                <span class="option-desc">数据保存在本地，无需网络</span>
              </div>
              <ChevronRight :size="16" class="option-arrow" />
            </button>

            <button class="login-option-card" @click="loginMode = 'online'">
              <div class="option-icon online-icon">
                <Cloud :size="22" />
              </div>
              <div class="option-info">
                <span class="option-title">在线登录</span>
                <span class="option-desc">多端同步，云端备份数据</span>
              </div>
              <ChevronRight :size="16" class="option-arrow" />
            </button>
          </div>

          <div class="login-footer animate-fade-in">
            <button class="skip-link" @click="handleSkip">
              跳过，直接使用
              <ArrowRight :size="14" />
            </button>
          </div>
        </div>

        <!-- Local Login Form -->
        <div v-else-if="loginMode === 'local'" key="local" class="login-card">
          <div class="form-header">
            <button class="back-btn" @click="goBack">
              <ArrowRight :size="16" style="transform: rotate(180deg)" />
            </button>
            <div class="form-header-info">
              <div class="form-header-icon local-icon">
                <Monitor :size="18" />
              </div>
              <div>
                <h2 class="form-title">本地登录</h2>
                <p class="form-desc">数据存储在本机</p>
              </div>
            </div>
          </div>

          <form class="login-form" @submit.prevent="handleLocalLogin">
            <div class="form-field">
              <label class="field-label">
                <User :size="14" />
                用户名
              </label>
              <div class="field-input-wrap">
                <input
                  v-model="localForm.username"
                  type="text"
                  class="field-input"
                  placeholder="输入用户名"
                  autocomplete="username"
                />
              </div>
            </div>

            <div class="form-field">
              <label class="field-label">
                <Lock :size="14" />
                密码
              </label>
              <div class="field-input-wrap">
                <input
                  v-model="localForm.password"
                  :type="showLocalPassword ? 'text' : 'password'"
                  class="field-input"
                  placeholder="输入密码"
                  autocomplete="current-password"
                />
                <button type="button" class="eye-btn" @click="showLocalPassword = !showLocalPassword">
                  <Eye v-if="!showLocalPassword" :size="14" />
                  <EyeOff v-else :size="14" />
                </button>
              </div>
            </div>

            <button
              type="submit"
              :class="['submit-btn', { disabled: !canLocalLogin || isLoggingIn }]"
              :disabled="!canLocalLogin || isLoggingIn"
            >
              <LogIn v-if="!isLoggingIn" :size="16" />
              <span v-if="isLoggingIn" class="spin-dot"></span>
              <span>{{ isLoggingIn ? '登录中...' : '登录' }}</span>
            </button>
          </form>

          <div class="form-footer">
            <button class="skip-link" @click="handleSkip">
              跳过，直接使用
              <ArrowRight :size="14" />
            </button>
          </div>
        </div>

        <!-- Online Login Form -->
        <div v-else-if="loginMode === 'online'" key="online" class="login-card">
          <div class="form-header">
            <button class="back-btn" @click="goBack">
              <ArrowRight :size="16" style="transform: rotate(180deg)" />
            </button>
            <div class="form-header-info">
              <div class="form-header-icon online-icon">
                <Cloud :size="18" />
              </div>
              <div>
                <h2 class="form-title">在线登录</h2>
                <p class="form-desc">多端同步 · 云端备份</p>
              </div>
            </div>
          </div>

          <form class="login-form" @submit.prevent="handleOnlineLogin">
            <div class="form-field">
              <label class="field-label">
                <Mail :size="14" />
                邮箱
              </label>
              <div class="field-input-wrap">
                <input
                  v-model="onlineForm.email"
                  type="email"
                  class="field-input"
                  placeholder="输入邮箱地址"
                  autocomplete="email"
                />
              </div>
            </div>

            <div class="form-field">
              <label class="field-label">
                <Lock :size="14" />
                密码
              </label>
              <div class="field-input-wrap">
                <input
                  v-model="onlineForm.password"
                  :type="showOnlinePassword ? 'text' : 'password'"
                  class="field-input"
                  placeholder="输入密码"
                  autocomplete="current-password"
                />
                <button type="button" class="eye-btn" @click="showOnlinePassword = !showOnlinePassword">
                  <Eye v-if="!showOnlinePassword" :size="14" />
                  <EyeOff v-else :size="14" />
                </button>
              </div>
            </div>

            <Transition name="toast-slide">
              <div v-if="loginError" class="form-error">
                <span>{{ loginError }}</span>
              </div>
            </Transition>

            <button
              type="submit"
              :class="['submit-btn', { disabled: !canOnlineLogin || isLoggingIn }]"
              :disabled="!canOnlineLogin || isLoggingIn"
            >
              <Cloud v-if="!isLoggingIn" :size="16" />
              <span v-if="isLoggingIn" class="spin-dot"></span>
              <span>{{ isLoggingIn ? '连接中...' : '在线登录' }}</span>
            </button>
          </form>

          <div class="form-footer">
            <button class="skip-link" @click="handleSkip">
              跳过，直接使用
              <ArrowRight :size="14" />
            </button>
          </div>
        </div>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.login-view {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  width: 100%;
  overflow: hidden;
  background: var(--workspace-bg);
}

.login-bg {
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
  opacity: 0.4;
}

.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.25;
  animation: orb-float 14s ease-in-out infinite;
}

.login-orb-1 {
  width: 320px;
  height: 320px;
  background: radial-gradient(circle, var(--lumi-primary-glow), transparent 70%);
  top: -100px;
  right: -60px;
  animation-delay: 0s;
}

.login-orb-2 {
  width: 260px;
  height: 260px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.12), transparent 70%);
  bottom: -60px;
  left: -40px;
  animation-delay: -7s;
}

@keyframes orb-float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(20px, -15px) scale(1.05); }
  66% { transform: translate(-10px, 10px) scale(0.97); }
}

.login-container {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 400px;
  padding: 40px;
}

.login-card {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.login-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  text-align: center;
}

.login-logo {
  width: 64px;
  height: 64px;
  border-radius: 18px;
  background: var(--lumi-primary-gradient-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 32px var(--lumi-primary-glow);
}

.login-title {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.3px;
}

.login-subtitle {
  font-size: 14px;
  color: var(--text-muted);
}

.login-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.login-option-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border-radius: var(--radius-lg);
  border: 1.5px solid var(--workspace-border);
  background: var(--workspace-card);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  text-align: left;
  width: 100%;
}

.login-option-card:hover {
  border-color: var(--lumi-primary-border);
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.option-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.local-icon {
  background: linear-gradient(135deg, rgba(20, 126, 188, 0.12), rgba(20, 126, 188, 0.04));
  color: var(--lumi-primary);
}

.online-icon {
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.12), rgba(139, 92, 246, 0.04));
  color: var(--task-purple);
}

.option-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.option-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.option-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.option-arrow {
  color: var(--text-muted);
  flex-shrink: 0;
  transition: transform 200ms ease-in-out;
}

.login-option-card:hover .option-arrow {
  color: var(--lumi-primary);
  transform: translateX(3px);
}

.login-footer {
  display: flex;
  justify-content: center;
}

.skip-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  font-size: 13px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms ease-in-out;
  border-radius: var(--radius-full);
}

.skip-link:hover {
  color: var(--lumi-primary);
  background: var(--lumi-primary-subtle);
}

/* Form Header */
.form-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms ease-in-out;
  flex-shrink: 0;
}

.back-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.form-header-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.form-header-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.form-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.form-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 1px;
}

/* Login Form */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.field-label svg {
  color: var(--text-muted);
}

.field-input-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 14px;
  border-radius: var(--radius-md);
  border: 1.5px solid var(--workspace-border);
  background: var(--workspace-card);
  transition: all 300ms ease-in-out;
}

.field-input-wrap:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-light);
}

.field-input {
  flex: 1;
  padding: 11px 0;
  font-size: 14px;
  color: var(--text-primary);
  background: transparent;
  border: none;
  outline: none;
}

.field-input::placeholder {
  color: var(--text-muted);
}

.eye-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms ease-in-out;
  flex-shrink: 0;
}

.eye-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.form-error {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
  font-size: 12px;
  font-weight: 500;
}

.submit-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 24px;
  border-radius: var(--radius-lg);
  font-size: 14px;
  font-weight: 600;
  background: var(--lumi-primary);
  color: var(--text-inverse);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  margin-top: 4px;
}

.submit-btn:hover:not(.disabled) {
  background: var(--lumi-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 6px 20px var(--lumi-primary-border);
}

.submit-btn:active:not(.disabled) {
  transform: translateY(0) scale(0.98);
}

.submit-btn.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.spin-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: var(--text-inverse);
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.form-footer {
  display: flex;
  justify-content: center;
}

/* Transitions */
.login-step-enter-active {
  transition: all 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}

.login-step-leave-active {
  transition: all 0.2s cubic-bezier(0.4, 0, 1, 1);
}

.login-step-enter-from {
  opacity: 0;
  transform: translateX(24px);
}

.login-step-leave-to {
  opacity: 0;
  transform: translateX(-16px);
}

.toast-slide-enter-active {
  transition: all 0.3s ease-out;
}

.toast-slide-leave-active {
  transition: all 0.2s ease-in;
}

.toast-slide-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}

.toast-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.95);
}

.animate-brand-enter {
  animation: brand-enter 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.animate-slide-up {
  animation: lumi-slide-up 0.5s ease-out 0.15s both;
}

.animate-fade-in {
  animation: lumi-fade-in 0.4s ease-out 0.3s both;
}

@keyframes brand-enter {
  0% { opacity: 0; transform: translateY(24px) scale(0.95); filter: blur(3px); }
  100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
}
</style>
