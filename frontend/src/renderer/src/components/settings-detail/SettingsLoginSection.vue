<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { User, LogIn, UserPlus, LogOut, ShieldCheck, AlertCircle, Loader2, KeyRound } from 'lucide-vue-next'
import { useApi } from '../../composables/useApi'
import LumiButton from '../common/LumiButton.vue'
import LumiInput from '../common/LumiInput.vue'
import { createLuomiNestRendererLogger } from '../../utils/logger'

const logger = createLuomiNestRendererLogger('SettingsLogin')
const { apiGet, apiPost } = useApi()
const { t } = useI18n()

// ── JWT Token 持久化（localStorage，供未来远程访问场景使用）──
const JWT_ACCESS_TOKEN_KEY = 'lumi_jwt_access_token'
const JWT_REFRESH_TOKEN_KEY = 'lumi_jwt_refresh_token'

const setJwtTokens = (accessToken: string, refreshToken?: string) => {
  localStorage.setItem(JWT_ACCESS_TOKEN_KEY, accessToken)
  if (refreshToken) localStorage.setItem(JWT_REFRESH_TOKEN_KEY, refreshToken)
}

const clearJwtTokens = () => {
  localStorage.removeItem(JWT_ACCESS_TOKEN_KEY)
  localStorage.removeItem(JWT_REFRESH_TOKEN_KEY)
}

// ── 状态机：'loading' | 'guest' | 'user' ──
type AuthState = 'loading' | 'guest' | 'user'
const authState = ref<AuthState>('loading')
const currentUser = ref<{
  user_id: string
  username: string
  display_name: string | null
  is_active: boolean
  token_version: number
  created_at: string | null
} | null>(null)

// ── 表单 ──
type FormMode = 'login' | 'register'
const formMode = ref<FormMode>('login')
const formData = ref({
  username: '',
  password: '',
  confirmPassword: '',
  display_name: '',
})

const isLoginMode = computed(() => formMode.value === 'login')

const canSubmit = computed(() => {
  const u = formData.value.username.trim().length >= 3
  const p = formData.value.password.length >= 6
  if (isLoginMode.value) return u && p
  const cp = formData.value.password === formData.value.confirmPassword
  return u && p && cp
})

// ── 提示消息 ──
type BannerKind = 'success' | 'error' | 'info'
const banner = ref<{ kind: BannerKind; text: string } | null>(null)
const setBanner = (kind: BannerKind, text: string) => {
  banner.value = { kind, text }
}
const clearBanner = () => { banner.value = null }

const submitting = ref(false)

// ── 当前用户信息加载 ──
const loadCurrentUser = async () => {
  // 无 JWT access_token 时直接进入 guest 状态（不调用 /auth/me，避免 401）
  if (!localStorage.getItem(JWT_ACCESS_TOKEN_KEY)) {
    authState.value = 'guest'
    return
  }
  try {
    const me = await apiGet<typeof currentUser.value>('/auth/me')
    currentUser.value = me
    authState.value = 'user'
  } catch (e) {
    logger.warn('Load current user failed, treat as guest:', e)
    clearJwtTokens()
    authState.value = 'guest'
  }
}

// ── 登录 ──
const handleLogin = async () => {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  clearBanner()
  try {
    const resp = await apiPost<{ access_token: string; refresh_token: string; token_type: string }>('/auth/login', {
      username: formData.value.username.trim(),
      password: formData.value.password,
    })
    setJwtTokens(resp.access_token, resp.refresh_token)
    setBanner('success', t('settingsEx.login.loginSuccess'))
    await loadCurrentUser()
    // 重置表单
    formData.value.password = ''
    formData.value.confirmPassword = ''
  } catch (e) {
    setBanner('error', e instanceof Error ? e.message : t('settingsEx.login.loginFailed'))
  } finally {
    submitting.value = false
  }
}

// ── 注册 ──
const handleRegister = async () => {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  clearBanner()
  try {
    await apiPost<{ user_id: string; username: string }>('/auth/register', {
      username: formData.value.username.trim(),
      password: formData.value.password,
      display_name: formData.value.display_name.trim() || null,
    })
    setBanner('success', t('settingsEx.login.registerSuccess'))
    // 注册成功后自动登录
    await handleLogin()
  } catch (e) {
    setBanner('error', e instanceof Error ? e.message : t('settingsEx.login.registerFailed'))
  } finally {
    submitting.value = false
  }
}

// ── 登出 ──
const handleLogout = async () => {
  submitting.value = true
  clearBanner()
  try {
    await apiPost('/auth/logout')
    setBanner('success', t('settingsEx.login.loggedOut'))
  } catch (e) {
    // 登出失败仍清除本地 token（避免本地状态不一致）
    logger.warn('Logout API failed, clearing local tokens anyway:', e)
    setBanner('info', t('settingsEx.login.clearedLocally'))
  } finally {
    clearJwtTokens()
    currentUser.value = null
    authState.value = 'guest'
    submitting.value = false
  }
}

// ── 提交分发 ──
const handleSubmit = () => {
  if (isLoginMode.value) {
    void handleLogin()
  } else {
    void handleRegister()
  }
}

// ── 切换模式 ──
const switchMode = (mode: FormMode) => {
  if (mode === formMode.value) return
  formMode.value = mode
  clearBanner()
  formData.value.password = ''
  formData.value.confirmPassword = ''
}

onMounted(() => {
  void loadCurrentUser()
})
</script>

<template>
  <div class="settings-panel animate-slide-up">
    <!-- 加载中 -->
    <section v-if="authState === 'loading'" class="settings-card">
      <div class="settings-card__body settings-card__body--compact auth-loading">
        <Loader2 :size="20" class="auth-loading__spinner" />
        <span>{{ t('settingsEx.login.loading') }}</span>
      </div>
    </section>

    <!-- 已登录：账户信息卡 -->
    <template v-else-if="authState === 'user' && currentUser">
      <section class="settings-card">
        <div class="settings-card__header">
          <ShieldCheck :size="16" />
          <span class="settings-card__title">{{ t('settingsEx.login.currentAccount') }}</span>
        </div>
        <div class="settings-card__body">
          <div class="auth-profile">
            <div class="auth-profile__avatar">
              <User :size="32" />
            </div>
            <div class="auth-profile__info">
              <div class="auth-profile__name">{{ currentUser.display_name || currentUser.username }}</div>
              <div class="auth-profile__meta">@{{ currentUser.username }}</div>
              <div class="auth-profile__meta auth-profile__meta--muted">
                {{ t('settingsEx.login.userIdLabel', { id: currentUser.user_id }) }}
              </div>
            </div>
          </div>

          <div class="auth-meta-grid">
            <div class="auth-meta-item">
              <span class="auth-meta-item__label">{{ t('settingsEx.login.accountStatus') }}</span>
              <span class="auth-meta-item__value auth-meta-item__value--ok">
                {{ currentUser.is_active ? t('settingsEx.login.active') : t('settingsEx.login.deactivated') }}
              </span>
            </div>
            <div class="auth-meta-item">
              <span class="auth-meta-item__label">{{ t('settingsEx.login.tokenVersion') }}</span>
              <span class="auth-meta-item__value">{{ currentUser.token_version }}</span>
            </div>
            <div class="auth-meta-item">
              <span class="auth-meta-item__label">{{ t('settingsEx.login.registeredAt') }}</span>
              <span class="auth-meta-item__value">
                {{ currentUser.created_at ? new Date(currentUser.created_at).toLocaleString('zh-CN') : '—' }}
              </span>
            </div>
          </div>

          <div class="auth-actions">
            <LumiButton variant="danger-ghost" size="md" :loading="submitting" @click="handleLogout">
              <template #icon>
                <LogOut v-if="!submitting" :size="16" />
              </template>
              {{ t('settingsEx.login.logout') }}
            </LumiButton>
          </div>
        </div>
      </section>

      <section class="settings-card settings-card--dimmed">
        <div class="settings-card__body settings-card__body--compact">
          <div class="auth-tip">
            <KeyRound :size="14" />
            <span>{{ t('settingsEx.login.logoutTip') }}</span>
          </div>
        </div>
      </section>
    </template>

    <!-- 未登录：登录/注册表单 -->
    <template v-else>
      <section class="settings-card">
        <div class="settings-card__header">
          <User :size="16" />
          <span class="settings-card__title">{{ t('settingsEx.login.loginRegister') }}</span>
        </div>
        <div class="settings-card__body">
          <!-- 模式切换 Tab -->
          <div class="auth-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              :aria-selected="isLoginMode"
              class="auth-tab"
              :class="{ 'auth-tab--active': isLoginMode }"
              @click="switchMode('login')"
            >
              <LogIn :size="14" />
              {{ t('settingsEx.login.login') }}
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="!isLoginMode"
              class="auth-tab"
              :class="{ 'auth-tab--active': !isLoginMode }"
              @click="switchMode('register')"
            >
              <UserPlus :size="14" />
              {{ t('settingsEx.login.register') }}
            </button>
          </div>

          <!-- 提示横幅 -->
          <div v-if="banner" class="auth-banner" :class="`auth-banner--${banner.kind}`" role="status">
            <AlertCircle :size="14" />
            <span>{{ banner.text }}</span>
          </div>

          <!-- 表单 -->
          <form class="auth-form" @submit.prevent="handleSubmit">
            <div class="auth-form-field">
              <label class="auth-form-field__label">
                <User :size="13" />
                {{ t('settingsEx.login.username') }}
              </label>
              <LumiInput
                v-model="formData.username"
                type="text"
                :placeholder="t('settingsEx.login.usernamePlaceholder')"
                autocomplete="username"
              />
            </div>

            <div v-if="!isLoginMode" class="auth-form-field">
              <label class="auth-form-field__label">
                <User :size="13" />
                {{ t('settingsEx.login.displayName') }}
              </label>
              <LumiInput
                v-model="formData.display_name"
                type="text"
                :placeholder="t('settingsEx.login.displayNamePlaceholder')"
                autocomplete="nickname"
              />
            </div>

            <div class="auth-form-field">
              <label class="auth-form-field__label">
                <KeyRound :size="13" />
                {{ t('settingsEx.login.password') }}
              </label>
              <LumiInput
                v-model="formData.password"
                type="password"
                :placeholder="t('settingsEx.login.passwordPlaceholder')"
                autocomplete="current-password"
              />
            </div>

            <div v-if="!isLoginMode" class="auth-form-field">
              <label class="auth-form-field__label">
                <KeyRound :size="13" />
                {{ t('settingsEx.login.confirmPassword') }}
              </label>
              <LumiInput
                v-model="formData.confirmPassword"
                type="password"
                :placeholder="t('settingsEx.login.confirmPasswordPlaceholder')"
                autocomplete="new-password"
              />
              <span
                v-if="formData.confirmPassword && formData.password !== formData.confirmPassword"
                class="auth-form-field__hint auth-form-field__hint--error"
              >
                {{ t('settingsEx.login.passwordMismatch') }}
              </span>
            </div>

            <LumiButton
              type="submit"
              variant="primary"
              size="lg"
              block
              :loading="submitting"
              :disabled="!canSubmit || submitting"
            >
              <template #icon>
                <component :is="isLoginMode ? LogIn : UserPlus" v-if="!submitting" :size="16" />
              </template>
              {{ isLoginMode ? (submitting ? t('settingsEx.login.loggingIn') : t('settingsEx.login.login')) : (submitting ? t('settingsEx.login.registering') : t('settingsEx.login.register')) }}
            </LumiButton>
          </form>
        </div>
      </section>

      <section class="settings-card settings-card--dimmed">
        <div class="settings-card__body settings-card__body--compact">
          <div class="auth-tip">
            <ShieldCheck :size="14" />
            <span>{{ t('settingsEx.login.noAuthTip') }}</span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.auth-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-6);
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.auth-loading__spinner {
  color: var(--lumi-primary);
  animation: spin 1s linear infinite;
}


/* ── 用户资料卡 ── */
.auth-profile {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-2) 0;
}

.auth-profile__avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: var(--radius-full);
  background: color-mix(in srgb, var(--lumi-primary) 12%, transparent);
  color: var(--lumi-primary);
  flex-shrink: 0;
}

.auth-profile__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.auth-profile__name {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.auth-profile__meta {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.auth-profile__meta--muted {
  color: var(--text-muted);
  font-size: var(--text-xs);
  font-family: var(--font-mono, monospace);
}

/* ── 元信息网格 ── */
.auth-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-top: 1px solid var(--divider-soft);
  border-bottom: 1px solid var(--divider-soft);
}

.auth-meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.auth-meta-item__label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.auth-meta-item__value {
  font-size: var(--text-sm);
  color: var(--text-primary);
  font-weight: 500;
}

.auth-meta-item__value--ok {
  color: var(--lumi-success);
}

.auth-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}

/* ── Tab 切换 ── */
.auth-tabs {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-1);
  background: var(--surface-hover);
  border-radius: var(--radius-md);
}

.auth-tab {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-muted);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.auth-tab:hover {
  color: var(--text-primary);
}

.auth-tab--active {
  background: var(--workspace-card);
  color: var(--lumi-primary);
  box-shadow: var(--shadow-xs);
}

/* ── 横幅 ── */
.auth-banner {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
}

.auth-banner--success {
  background: color-mix(in srgb, var(--lumi-success) 12%, transparent);
  color: var(--lumi-success);
}

.auth-banner--error {
  background: color-mix(in srgb, var(--lumi-danger) 12%, transparent);
  color: var(--lumi-danger);
}

.auth-banner--info {
  background: color-mix(in srgb, var(--lumi-info) 12%, transparent);
  color: var(--lumi-info);
}

/* ── 表单 ── */
.auth-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.auth-form-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.auth-form-field__label {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
}

.auth-form-field__label svg {
  color: var(--text-muted);
}

.auth-form-field__hint {
  font-size: var(--text-xs);
}

.auth-form-field__hint--error {
  color: var(--lumi-danger);
}

/* ── 提示 ── */
.auth-tip {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: var(--text-muted);
  line-height: 1.5;
}

.auth-tip svg {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--lumi-primary);
  opacity: 0.7;
}

/* ── 响应式 ── */
@media (max-width: 640px) {
  .auth-meta-grid {
    grid-template-columns: 1fr;
    gap: var(--space-2);
  }
}
</style>
