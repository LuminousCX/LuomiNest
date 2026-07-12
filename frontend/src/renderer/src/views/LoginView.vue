<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Monitor,
  ArrowRight,
  Mail,
  Lock,
  User,
  LogIn,
  Cloud,
  ChevronRight,
} from 'lucide-vue-next'
import LumiBrandStar from '../components/common/LumiBrandStar.vue'
import LumiButton from '../components/common/LumiButton.vue'
import LumiInput from '../components/common/LumiInput.vue'
import LumiCard from '../components/common/LumiCard.vue'

const router = useRouter()
const route = useRoute()

type LoginMode = 'select' | 'local' | 'online'

const loginMode = ref<LoginMode>('select')

const localForm = ref({ username: '', password: '' })
const onlineForm = ref({ email: '', password: '' })
const isLoggingIn = ref(false)
const loginError = ref('')

const canLocalLogin = computed(() =>
  localForm.value.username.trim().length > 0 && localForm.value.password.length > 0
)

const canOnlineLogin = computed(() =>
  onlineForm.value.email.trim().length > 0 && onlineForm.value.password.length > 0
)

// 登录成功后的目标路由：优先读取 redirect 查询参数，默认 /workspace
const resolveRedirectTarget = (): string => {
  const redirect = route.query.redirect
  return typeof redirect === 'string' && redirect.startsWith('/')
    ? redirect
    : '/workspace'
}

// 通知路由守卫重新读取 token（Electron 主进程已自动生成，此处仅刷新缓存）
const refreshAuthState = () => {
  const invalidate = window.__lumiInvalidateAuthToken
  if (typeof invalidate === 'function') {
    invalidate()
  }
}

const handleLocalLogin = async () => {
  if (!canLocalLogin.value) return
  loginError.value = ''
  isLoggingIn.value = true
  setTimeout(() => {
    isLoggingIn.value = false
    refreshAuthState()
    router.push(resolveRedirectTarget())
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
  refreshAuthState()
  router.push(resolveRedirectTarget())
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
            <LumiCard class="login-option-card" hoverable padding="none">
              <button class="login-option-inner" @click="loginMode = 'local'">
                <div class="option-icon local-icon">
                  <Monitor :size="22" />
                </div>
                <div class="option-info">
                  <span class="option-title">本地登录</span>
                  <span class="option-desc">数据保存在本地，无需网络</span>
                </div>
                <ChevronRight :size="16" class="option-arrow" />
              </button>
            </LumiCard>

            <LumiCard class="login-option-card" hoverable padding="none">
              <button class="login-option-inner" @click="loginMode = 'online'">
                <div class="option-icon online-icon">
                  <Cloud :size="22" />
                </div>
                <div class="option-info">
                  <span class="option-title">在线登录</span>
                  <span class="option-desc">多端同步，云端备份数据</span>
                </div>
                <ChevronRight :size="16" class="option-arrow" />
              </button>
            </LumiCard>
          </div>

          <div class="login-footer animate-fade-in">
            <LumiButton variant="ghost" size="sm" @click="handleSkip">
              <span class="skip-content">
                跳过，直接使用
                <ArrowRight :size="14" />
              </span>
            </LumiButton>
          </div>
        </div>

        <!-- Local Login Form -->
        <div v-else-if="loginMode === 'local'" key="local" class="login-card">
          <div class="form-header">
            <LumiButton variant="ghost" icon-only size="sm" aria-label="返回" @click="goBack">
              <ArrowRight :size="16" style="transform: rotate(180deg)" />
            </LumiButton>
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
              <LumiInput
                v-model="localForm.username"
                type="text"
                placeholder="输入用户名"
                autocomplete="username"
              >
                <template #icon>
                  <User :size="16" />
                </template>
              </LumiInput>
            </div>

            <div class="form-field">
              <label class="field-label">
                <Lock :size="14" />
                密码
              </label>
              <LumiInput
                v-model="localForm.password"
                type="password"
                placeholder="输入密码"
                autocomplete="current-password"
              >
                <template #icon>
                  <Lock :size="16" />
                </template>
              </LumiInput>
            </div>

            <LumiButton
              type="submit"
              variant="primary"
              size="lg"
              block
              :loading="isLoggingIn"
              :disabled="!canLocalLogin || isLoggingIn"
            >
              <template #icon v-if="!isLoggingIn">
                <LogIn :size="16" />
              </template>
              {{ isLoggingIn ? '登录中...' : '登录' }}
            </LumiButton>
          </form>

          <div class="form-footer">
            <LumiButton variant="ghost" size="sm" @click="handleSkip">
              <span class="skip-content">
                跳过，直接使用
                <ArrowRight :size="14" />
              </span>
            </LumiButton>
          </div>
        </div>

        <!-- Online Login Form -->
        <div v-else-if="loginMode === 'online'" key="online" class="login-card">
          <div class="form-header">
            <LumiButton variant="ghost" icon-only size="sm" aria-label="返回" @click="goBack">
              <ArrowRight :size="16" style="transform: rotate(180deg)" />
            </LumiButton>
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
              <LumiInput
                v-model="onlineForm.email"
                type="email"
                placeholder="输入邮箱地址"
                autocomplete="email"
              >
                <template #icon>
                  <Mail :size="16" />
                </template>
              </LumiInput>
            </div>

            <div class="form-field">
              <label class="field-label">
                <Lock :size="14" />
                密码
              </label>
              <LumiInput
                v-model="onlineForm.password"
                type="password"
                placeholder="输入密码"
                autocomplete="current-password"
              >
                <template #icon>
                  <Lock :size="16" />
                </template>
              </LumiInput>
            </div>

            <Transition name="toast-slide">
              <div v-if="loginError" class="form-error">
                <span>{{ loginError }}</span>
              </div>
            </Transition>

            <LumiButton
              type="submit"
              variant="primary"
              size="lg"
              block
              :loading="isLoggingIn"
              :disabled="!canOnlineLogin || isLoggingIn"
            >
              <template #icon v-if="!isLoggingIn">
                <Cloud :size="16" />
              </template>
              {{ isLoggingIn ? '连接中...' : '在线登录' }}
            </LumiButton>
          </form>

          <div class="form-footer">
            <LumiButton variant="ghost" size="sm" @click="handleSkip">
              <span class="skip-content">
                跳过，直接使用
                <ArrowRight :size="14" />
              </span>
            </LumiButton>
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
  background: var(--bg);
}

.login-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.bg-orb {
  position: absolute;
  border-radius: var(--radius-full);
  filter: blur(120px);
  opacity: 0.15;
  animation: orb-float 18s var(--ease-in-out) infinite;
  will-change: transform, opacity;
}

.login-orb-1 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, var(--lumi-brand-glow), transparent 70%);
  top: -120px;
  right: -80px;
  animation-delay: 0s;
}

.login-orb-2 {
  width: 350px;
  height: 350px;
  background: radial-gradient(circle, var(--lumi-brand-glow), transparent 70%);
  bottom: -80px;
  left: -60px;
  animation-delay: -9s;
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
  padding: var(--space-8);
}

.login-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-7);
}

.login-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  text-align: center;
}

.login-logo {
  width: var(--space-10);
  height: var(--space-10);
  border-radius: var(--radius-lg);
  background: var(--lumi-brand-gradient-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-md);
}

.login-title {
  font-size: var(--text-4xl);
  font-weight: var(--font-bold);
  letter-spacing: -0.3px;
}

.login-subtitle {
  font-size: var(--text-md);
  color: var(--text-muted);
}

.login-options {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.login-option-card {
  width: 100%;
}

.login-option-inner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-3) var(--space-4);
  text-align: left;
  background: transparent;
  border: none;
  cursor: pointer;
}

.login-option-card:hover {
  border-color: var(--lumi-brand-border);
}

.login-option-inner:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}

.option-icon {
  width: 42px;
  height: 42px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.local-icon {
  background: var(--lumi-brand-gradient-soft);
  color: var(--lumi-brand);
}

.online-icon {
  background: linear-gradient(135deg, var(--task-purple-soft), var(--task-purple-bg));
  color: var(--task-purple);
}

.option-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: calc(var(--space-1) / 2);
}

.option-title {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.option-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.option-arrow {
  color: var(--text-muted);
  flex-shrink: 0;
  transition: transform var(--transition-fast);
}

.login-option-card:hover .option-arrow {
  color: var(--lumi-brand);
  transform: translateX(3px);
}

.login-footer,
.form-footer {
  display: flex;
  justify-content: center;
}

.skip-content {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

/* Form Header */
.form-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.form-header-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.form-header-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.form-title {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text);
}

.form-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-top: calc(var(--space-1) / 4);
}

/* Login Form */
.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: calc(var(--space-1) * 1.5);
}

.field-label {
  display: flex;
  align-items: center;
  gap: calc(var(--space-1) * 1.5);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
}

.field-label svg {
  color: var(--text-muted);
}

.form-error {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}

/* Transitions */
.login-step-enter-active {
  transition: all var(--duration-slow) var(--ease-out-expo);
}

.login-step-leave-active {
  transition: all var(--duration-leave) var(--ease-default);
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
  transition: all var(--duration-normal) var(--ease-default);
}

.toast-slide-leave-active {
  transition: all var(--duration-leave) var(--ease-default);
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
  animation: brand-enter var(--duration-enter) var(--ease-out-expo) both;
}

.animate-slide-up {
  animation: lumi-slide-up var(--duration-slow) var(--ease-default) 0.15s both;
}

.animate-fade-in {
  animation: lumi-fade-in var(--duration-enter) var(--ease-default) 0.3s both;
}

@keyframes brand-enter {
  0% { opacity: 0; transform: translateY(24px) scale(0.95); filter: blur(3px); }
  100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
}

button:focus-visible,
.lumi-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}

</style>