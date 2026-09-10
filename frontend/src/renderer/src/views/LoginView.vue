<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowRight, Lock, User, LogIn } from 'lucide-vue-next'
import LumiBrandStar from '../components/common/LumiBrandStar.vue'
import LumiButton from '../components/common/LumiButton.vue'
import LumiInput from '../components/common/LumiInput.vue'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

const localForm = ref({ username: '', password: '' })
const isLoggingIn = ref(false)

const canLocalLogin = computed(() =>
  localForm.value.username.trim().length > 0 && localForm.value.password.length > 0
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
  isLoggingIn.value = true
  setTimeout(() => {
    isLoggingIn.value = false
    refreshAuthState()
    router.push(resolveRedirectTarget())
  }, 800)
}

const handleSkip = () => {
  refreshAuthState()
  router.push(resolveRedirectTarget())
}
</script>

<template>
  <div class="login-view">
    <div class="login-bg">
      <div class="bg-orb login-orb-1"></div>
      <div class="bg-orb login-orb-2"></div>
    </div>

    <div class="login-container">
      <div class="login-card">
        <div class="login-brand animate-brand-enter">
          <div class="login-logo">
            <LumiBrandStar :size="40" />
          </div>
          <h1 class="login-title lumi-gradient-text">LuomiNest</h1>
          <p class="login-subtitle">{{ t('login.subtitle') }}</p>
        </div>

        <form class="login-form animate-slide-up" @submit.prevent="handleLocalLogin">
          <div class="form-field">
            <label class="field-label">
              <User :size="14" />
              {{ t('login.username') }}
            </label>
            <LumiInput
              v-model="localForm.username"
              type="text"
              :placeholder="t('login.usernamePlaceholder')"
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
              {{ t('login.password') }}
            </label>
            <LumiInput
              v-model="localForm.password"
              type="password"
              :placeholder="t('login.passwordPlaceholder')"
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
            {{ isLoggingIn ? t('login.loggingIn') : t('login.login') }}
          </LumiButton>
        </form>

        <div class="login-footer animate-fade-in">
          <LumiButton variant="ghost" size="sm" @click="handleSkip">
            <span class="skip-content">
              {{ t('login.skipUse') }}
              <ArrowRight :size="14" />
            </span>
          </LumiButton>
        </div>
      </div>
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

.login-footer {
  display: flex;
  justify-content: center;
}

.skip-content {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
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

/* Animations */
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
