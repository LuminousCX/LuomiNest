<script setup lang="ts">
/**
 * 欢迎向导 - 步骤2：账号登录（三选一）
 *
 * a) 辰汐通行证：复用设置云区的 Device Flow 交互（cloud:login → userCode 授权页 →
 *    cloud:status-changed 推送 authorized 后自动进入下一步），可「稍后在设置中登录」；
 * b) 本地账号：复用 useWelcomeWizard 的注册/登录表单（与设置页共用 JWT 登录态）；
 * c) 跳过：之后可随时在 设置 → 通行证登录 / 登录注册 中补登。
 *
 * 云端状态订阅在组件生命周期内挂载/卸载；本地表单状态由父级 composable 持有。
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Cloud,
  UserPlus,
  SkipForward,
  User,
  KeyRound,
  LogIn,
  Check,
  ChevronRight,
  Copy,
  ExternalLink,
  X,
  Loader2
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import LumiInput from '../common/LumiInput.vue'
import type { CloudAuthStatus } from '@shared/ipc-types'
import type { WizardCurrentUser } from '../../composables/useWelcomeWizard'

const props = defineProps<{
  /** null=检测中，false=未登录，true=已登录（伴随 currentUser） */
  hasAccount: boolean | null
  currentUser: WizardCurrentUser | null
  accountForm: {
    username: string
    displayName: string
    password: string
    confirmPassword: string
  }
  accountFormValid: boolean
  accountSubmitting: boolean
  accountError: string
}>()

const emit = defineEmits<{
  register: []
  login: []
  next: []
  prev: []
}>()

const { t } = useI18n()

// ── 三选一模式卡 ──
type LoginMode = 'passport' | 'local' | 'skip'
const mode = ref<LoginMode>('passport')

const modes = [
  { key: 'passport' as const, icon: Cloud },
  { key: 'local' as const, icon: UserPlus },
  { key: 'skip' as const, icon: SkipForward }
]

// ── 辰汐通行证 Device Flow（与 SettingsCloudSection 同款交互）──
const cloudStatus = ref<CloudAuthStatus>({ state: 'loggedOut' })
const cloudLoading = ref(false)
/** authorized 自动进入下一步只触发一次 */
let autoAdvanced = false
let unsubscribe: (() => void) | null = null

const applyCloudStatus = (next: CloudAuthStatus): void => {
  cloudStatus.value = next
  if (next.state === 'authorized' && !autoAdvanced) {
    autoAdvanced = true
    emit('next')
  }
}

const startPassportLogin = async (): Promise<void> => {
  if (cloudLoading.value) return
  cloudLoading.value = true
  try {
    applyCloudStatus(await window.api.cloud.login())
  } catch {
    applyCloudStatus({ state: 'error', error: 'unknown' })
  } finally {
    cloudLoading.value = false
  }
}

const cancelPassportLogin = async (): Promise<void> => {
  try {
    applyCloudStatus(await window.api.cloud.logout())
  } catch {
    // 失败时等待状态推送兜底
  }
}

const openVerification = async (): Promise<void> => {
  try {
    await window.api.cloud.openVerification()
  } catch {
    // 打开失败保持等待态，可重试
  }
}

// ── 等待授权态：复制用户码 ──
const copied = ref(false)
let copyTimer: ReturnType<typeof setTimeout> | undefined

const copyUserCode = async (): Promise<void> => {
  const code = cloudStatus.value.userCode
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    copied.value = true
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => (copied.value = false), 1500)
  } catch {
    // 剪贴板不可用时用户码仍可手动选中复制
  }
}

// ── 本地账号 ──
type LocalTab = 'register' | 'login'
const localTab = ref<LocalTab>('register')

/** 登录模式只需用户名 + 密码（无确认密码） */
const loginFormValid = computed(
  () => props.accountForm.username.trim().length >= 3 && props.accountForm.password.length >= 6
)

const confirmMismatch = computed(
  () =>
    props.accountForm.confirmPassword.length > 0 && props.accountForm.password !== props.accountForm.confirmPassword
)

/** 按当前页签提交本地账号表单（注册 / 登录） */
const submitLocal = (): void => {
  if (localTab.value === 'register') {
    emit('register')
  } else {
    emit('login')
  }
}

onMounted(() => {
  unsubscribe = window.api.cloud?.onStatus?.(applyCloudStatus) ?? null
  // 若进入向导前已是 authorized（本次会话早前登录过），不自动跳步，仅记录状态
  window.api.cloud
    ?.status?.()
    .then((s) => {
      // 只同步展示状态，不触发自动跳步（autoAdvanced 保持 false 由推送置位）
      if (cloudStatus.value.state === 'loggedOut') cloudStatus.value = s
    })
    .catch(() => {})
})

onUnmounted(() => {
  unsubscribe?.()
  unsubscribe = null
  if (copyTimer) clearTimeout(copyTimer)
})
</script>

<template>
  <div class="welcome-step step-login">
    <div class="step-hero animate-fade-in">
      <div class="step-hero-icon login-hero-icon">
        <KeyRound :size="24" />
      </div>
      <div>
        <h2 class="step-hero-title">{{ t('welcome.loginTitle') }}</h2>
        <p class="step-hero-desc">{{ t('welcome.loginDesc') }}</p>
      </div>
    </div>

    <!-- 三选一模式卡 -->
    <div class="login-modes animate-slide-up">
      <button
        v-for="m in modes"
        :key="m.key"
        :class="['login-mode-card', { active: mode === m.key }]"
        @click="mode = m.key"
      >
        <component :is="m.icon" :size="18" />
        <span class="login-mode-card__label">{{ t(`welcome.loginMode.${m.key}`) }}</span>
        <Check v-if="mode === m.key" :size="14" class="login-mode-card__check" />
      </button>
    </div>

    <!-- a) 辰汐通行证 -->
    <div v-if="mode === 'passport'" class="login-body animate-fade-in">
      <!-- 等待授权确认 -->
      <template v-if="cloudStatus.state === 'pendingAuth'">
        <p class="login-hint">{{ t('welcome.passportPendingHint') }}</p>
        <div class="passport-user-code">{{ cloudStatus.userCode || '—' }}</div>
        <div class="passport-tools">
          <button type="button" class="passport-copy-btn" @click="copyUserCode">
            <Check v-if="copied" :size="13" />
            <Copy v-else :size="13" />
            <span>{{ t(copied ? 'welcome.passportCopied' : 'welcome.passportCopy') }}</span>
          </button>
        </div>
        <div class="step-actions">
          <LumiButton variant="primary" size="lg" block @click="openVerification">
            <template #icon>
              <ExternalLink :size="16" />
            </template>
            <span>{{ t('welcome.passportOpenPage') }}</span>
          </LumiButton>
          <LumiButton variant="ghost" size="lg" @click="cancelPassportLogin">
            <template #icon>
              <X :size="16" />
            </template>
            <span>{{ t('welcome.passportCancel') }}</span>
          </LumiButton>
        </div>
        <div class="passport-waiting">
          <Loader2 :size="14" class="passport-waiting__spinner" />
          <span>{{ t('welcome.passportWaiting') }}</span>
        </div>
      </template>

      <!-- 登录失败 -->
      <template v-else-if="cloudStatus.state === 'error'">
        <div class="form-error-banner">
          <span>{{ t('welcome.passportError') }}</span>
        </div>
        <div class="step-actions">
          <LumiButton variant="primary" size="lg" block :loading="cloudLoading" @click="startPassportLogin">
            <template #icon>
              <Cloud v-if="!cloudLoading" :size="16" />
            </template>
            <span>{{ t('welcome.passportRetry') }}</span>
          </LumiButton>
        </div>
        <div class="login-skip-row">
          <button class="skip-link" @click="emit('next')">{{ t('welcome.loginLater') }}</button>
        </div>
      </template>

      <!-- 未开始 / 未登录（已登录过则按钮置禁用并提示） -->
      <template v-else>
        <p class="login-hint">
          {{ cloudStatus.state === 'authorized' ? t('welcome.passportAlready') : t('welcome.passportHint') }}
        </p>
        <div v-if="cloudStatus.state === 'authorized'" class="step-actions">
          <LumiButton variant="primary" size="lg" block @click="emit('next')">
            <span>{{ t('welcome.btnNext') }}</span>
            <ChevronRight :size="16" />
          </LumiButton>
        </div>
        <div v-else class="step-actions">
          <LumiButton variant="primary" size="lg" block :loading="cloudLoading" @click="startPassportLogin">
            <template #icon>
              <Cloud v-if="!cloudLoading" :size="16" />
            </template>
            <span>{{ cloudLoading ? t('welcome.passportStarting') : t('welcome.passportStart') }}</span>
          </LumiButton>
        </div>
        <div v-if="cloudStatus.state !== 'authorized'" class="login-skip-row">
          <button class="skip-link" @click="emit('next')">{{ t('welcome.loginLater') }}</button>
          <span class="skip-hint">{{ t('welcome.loginLaterHint') }}</span>
        </div>
      </template>
    </div>

    <!-- b) 本地账号 -->
    <div v-else-if="mode === 'local'" class="login-body animate-fade-in">
      <div v-if="accountError" class="form-error-banner">
        <span>{{ accountError }}</span>
      </div>

      <!-- 已有账户：直接显示账户卡 -->
      <template v-if="hasAccount === null">
        <div class="login-checking">
          <Loader2 :size="18" class="passport-waiting__spinner" />
          <span>{{ t('welcome.accountChecking') }}</span>
        </div>
      </template>
      <template v-else-if="hasAccount && currentUser">
        <div class="local-account-card">
          <div class="local-account-card__avatar">
            <User :size="24" />
          </div>
          <div class="local-account-card__info">
            <span class="local-account-card__name">{{ currentUser.display_name || currentUser.username }}</span>
            <span class="local-account-card__meta">@{{ currentUser.username }}</span>
          </div>
          <Check :size="18" class="local-account-card__check" />
        </div>
        <div class="step-actions">
          <LumiButton variant="primary" size="lg" block @click="emit('next')">
            <span>{{ t('welcome.btnNext') }}</span>
            <ChevronRight :size="16" />
          </LumiButton>
        </div>
      </template>

      <!-- 未登录：注册 / 登录 双页签表单 -->
      <template v-else>
        <div class="local-tabs">
          <button :class="['local-tab', { active: localTab === 'register' }]" @click="localTab = 'register'">
            {{ t('welcome.loginLocalTabRegister') }}
          </button>
          <button :class="['local-tab', { active: localTab === 'login' }]" @click="localTab = 'login'">
            {{ t('welcome.loginLocalTabLogin') }}
          </button>
        </div>

        <div class="local-form">
          <div class="form-group">
            <label>{{ t('welcome.accountUsername') }}</label>
            <LumiInput
              v-model="accountForm.username"
              type="text"
              :placeholder="t('welcome.accountUsernameHint')"
              autocomplete="username"
            />
          </div>
          <div v-if="localTab === 'register'" class="form-group">
            <label>{{ t('welcome.accountDisplayName') }}</label>
            <LumiInput
              v-model="accountForm.displayName"
              type="text"
              :placeholder="t('welcome.accountDisplayNameHint')"
              autocomplete="nickname"
            />
          </div>
          <div class="form-group">
            <label>{{ t('welcome.accountPassword') }}</label>
            <LumiInput
              v-model="accountForm.password"
              type="password"
              :placeholder="t('welcome.accountPasswordHint')"
              :autocomplete="localTab === 'register' ? 'new-password' : 'current-password'"
            />
          </div>
          <div v-if="localTab === 'register'" class="form-group">
            <label>{{ t('welcome.accountConfirm') }}</label>
            <LumiInput
              v-model="accountForm.confirmPassword"
              type="password"
              :placeholder="t('welcome.accountConfirmHint')"
              autocomplete="new-password"
            />
            <span v-if="confirmMismatch" class="form-field-error">{{ t('welcome.accountConfirmMismatch') }}</span>
          </div>
        </div>

        <div class="step-actions">
          <LumiButton
            variant="primary"
            size="lg"
            block
            :loading="accountSubmitting"
            :disabled="accountSubmitting || (localTab === 'register' ? !accountFormValid : !loginFormValid)"
            @click="submitLocal"
          >
            <template #icon>
              <LogIn v-if="!accountSubmitting" :size="16" />
            </template>
            <span>
              {{
                accountSubmitting
                  ? t('welcome.accountSubmitting')
                  : localTab === 'register'
                    ? t('welcome.accountSubmit')
                    : t('welcome.loginLocalLoginBtn')
              }}
            </span>
          </LumiButton>
        </div>

        <div class="login-skip-row">
          <button class="skip-link" @click="emit('next')">{{ t('welcome.loginLater') }}</button>
          <span class="skip-hint">{{ t('welcome.loginLaterHint') }}</span>
        </div>
      </template>
    </div>

    <!-- c) 跳过 -->
    <div v-else class="login-body animate-fade-in">
      <p class="login-hint">{{ t('welcome.loginSkipDesc') }}</p>
      <div class="step-actions">
        <LumiButton variant="primary" size="lg" block @click="emit('next')">
          <span>{{ t('welcome.loginSkipBtn') }}</span>
          <ChevronRight :size="16" />
        </LumiButton>
      </div>
      <div class="login-skip-row">
        <span class="skip-hint">{{ t('welcome.loginLaterHint') }}</span>
      </div>
    </div>

    <div class="step-back animate-fade-in">
      <button class="skip-link" @click="emit('prev')">{{ t('welcome.btnBack') }}</button>
    </div>
  </div>
</template>

<style scoped>
.welcome-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-5);
}

.step-hero {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  width: 100%;
}

.step-hero-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: var(--shadow-sm);
}

.login-hero-icon {
  background: var(--lumi-brand-gradient-soft);
  color: var(--lumi-brand);
}

.step-hero-title {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text);
}

.step-hero-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

/* 三选一模式卡 */
.login-modes {
  width: 100%;
  display: flex;
  gap: var(--space-2);
}

.login-mode-card {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.login-mode-card:hover {
  border-color: var(--lumi-brand-border);
}

.login-mode-card.active {
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.login-mode-card__check {
  flex-shrink: 0;
}

/* 内容体 */
.login-body {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.login-hint {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
  text-align: center;
}

.form-error-banner {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--lumi-danger) 12%, transparent);
  color: var(--lumi-danger);
  font-size: var(--text-sm);
}

/* 通行证等待授权 */
.passport-user-code {
  padding: var(--space-4);
  border: 1px dashed var(--border-light);
  border-radius: var(--radius-md);
  background: var(--surface-hover);
  font-family: var(--font-mono, monospace);
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
  letter-spacing: 0.35em;
  text-align: center;
  color: var(--lumi-brand);
  user-select: all;
}

.passport-tools {
  display: flex;
  justify-content: center;
  margin-top: calc(var(--space-1) * -1);
}

.passport-copy-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px 8px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  font-size: var(--text-xs);
  color: var(--text-muted);
  cursor: pointer;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.passport-copy-btn:hover {
  color: var(--lumi-brand);
  background: var(--surface-hover);
}

.passport-waiting {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.passport-waiting__spinner {
  animation: passport-spin 1s linear infinite;
  color: var(--lumi-brand);
}

@keyframes passport-spin {
  to { transform: rotate(360deg); }
}

.login-checking {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--text-muted);
  font-size: var(--text-sm);
  padding: var(--space-6) 0;
}

/* 本地账户已登录卡 */
.local-account-card {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px solid var(--lumi-brand-border);
  background: var(--lumi-brand-light);
}

.local-account-card__avatar {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand-gradient-soft);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.local-account-card__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.local-account-card__name {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.local-account-card__meta {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.local-account-card__check {
  margin-left: auto;
  color: var(--lumi-brand);
  flex-shrink: 0;
}

/* 注册 / 登录 页签 */
.local-tabs {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-1);
  border-radius: var(--radius-lg);
  background: var(--bg-secondary);
}

.local-tab {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.local-tab.active {
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow-sm);
}

.local-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-group label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}

.form-field-error {
  font-size: var(--text-xs);
  color: var(--lumi-danger);
}

/* 跳过 / 返回行 */
.login-skip-row {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
}

.step-back {
  display: flex;
  justify-content: center;
}

.skip-link {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  text-decoration: underline;
  text-underline-offset: 3px;
  transition: color var(--transition-fast);
}

.skip-link:hover {
  color: var(--lumi-brand);
}

.skip-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.step-actions {
  display: flex;
  gap: var(--space-3);
  width: 100%;
  margin-top: var(--space-1);
}

.step-actions .lumi-btn--block {
  flex: 1;
}

button:focus-visible,
.lumi-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}
</style>
