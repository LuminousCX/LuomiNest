<script setup lang="ts">
/**
 * 欢迎向导 - 步骤2：账户（创建本地账户 / 暂不创建 / 在线账户占位）
 *
 * 无内部状态：表单与注册逻辑由父级 useWelcomeWizard 持有（与 StepAiModel 同模式），
 * 注册走后端 /auth/register + /auth/login，与设置页 SettingsLoginSection 共用 JWT 登录态。
 * 在线账户（远程 Java 端）尚未接线，置灰占位。
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { UserPlus, User, KeyRound, Globe, Check, ChevronRight, Loader2 } from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import LumiInput from '../common/LumiInput.vue'
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
  next: []
  prev: []
}>()

const { t } = useI18n()

const confirmMismatch = computed(
  () => props.accountForm.confirmPassword.length > 0 && props.accountForm.password !== props.accountForm.confirmPassword
)
</script>

<template>
  <div class="welcome-step step-account">
    <div class="step-hero animate-fade-in">
      <div class="step-hero-icon account-hero-icon">
        <UserPlus :size="24" />
      </div>
      <div>
        <h2 class="step-hero-title">{{ t('welcome.accountTitle') }}</h2>
        <p class="step-hero-desc">{{ t('welcome.accountDesc') }}</p>
      </div>
    </div>

    <!-- 检测登录态中 -->
    <div v-if="hasAccount === null" class="account-loading animate-fade-in">
      <Loader2 :size="18" class="account-loading__spinner" />
      <span>{{ t('welcome.accountChecking') }}</span>
    </div>

    <!-- 已有账户：直接显示账户卡 -->
    <template v-else-if="hasAccount && currentUser">
      <div class="account-card animate-slide-up">
        <div class="account-card__avatar">
          <User :size="26" />
        </div>
        <div class="account-card__info">
          <span class="account-card__name">{{ currentUser.display_name || currentUser.username }}</span>
          <span class="account-card__meta">@{{ currentUser.username }}</span>
        </div>
        <Check :size="18" class="account-card__check" />
      </div>

      <div class="step-actions animate-fade-in">
        <LumiButton variant="ghost" size="lg" @click="$emit('prev')">
          {{ t('welcome.btnBack') }}
        </LumiButton>
        <LumiButton variant="primary" size="lg" block @click="$emit('next')">
          <span>{{ t('welcome.aiModelNext') }}</span>
          <ChevronRight :size="16" />
        </LumiButton>
      </div>
    </template>

    <!-- 未登录：创建表单 + 在线占位 + 跳过 -->
    <template v-else>
      <div class="account-body animate-slide-up">
        <div v-if="accountError" class="form-error-banner">
          <span>{{ accountError }}</span>
        </div>

        <div class="account-options">
          <div class="option-card active">
            <UserPlus :size="16" />
            <span>{{ t('welcome.accountCreateCard') }}</span>
          </div>
          <div class="option-card disabled" :title="t('welcome.accountOnlineBadge')">
            <Globe :size="16" />
            <span>{{ t('welcome.accountOnlineCard') }}</span>
            <span class="option-badge">{{ t('welcome.accountOnlineBadge') }}</span>
          </div>
        </div>

        <div class="account-form">
          <div class="form-group">
            <label>{{ t('welcome.accountUsername') }}</label>
            <LumiInput v-model="accountForm.username" type="text" :placeholder="t('welcome.accountUsernameHint')" autocomplete="username" />
          </div>
          <div class="form-group">
            <label>{{ t('welcome.accountDisplayName') }}</label>
            <LumiInput v-model="accountForm.displayName" type="text" :placeholder="t('welcome.accountDisplayNameHint')" autocomplete="nickname" />
          </div>
          <div class="form-group">
            <label>{{ t('welcome.accountPassword') }}</label>
            <LumiInput v-model="accountForm.password" type="password" :placeholder="t('welcome.accountPasswordHint')" autocomplete="new-password" />
          </div>
          <div class="form-group">
            <label>{{ t('welcome.accountConfirm') }}</label>
            <LumiInput v-model="accountForm.confirmPassword" type="password" :placeholder="t('welcome.accountConfirmHint')" autocomplete="new-password" />
            <span v-if="confirmMismatch" class="form-field-error">{{ t('welcome.accountConfirmMismatch') }}</span>
          </div>
        </div>
      </div>

      <div class="step-actions animate-fade-in">
        <LumiButton variant="ghost" size="lg" @click="$emit('prev')">
          {{ t('welcome.btnBack') }}
        </LumiButton>
        <LumiButton
          variant="primary"
          size="lg"
          block
          :loading="accountSubmitting"
          :disabled="!accountFormValid || accountSubmitting"
          @click="$emit('register')"
        >
          <template #icon>
            <KeyRound v-if="!accountSubmitting" :size="16" />
          </template>
          <span>{{ accountSubmitting ? t('welcome.accountSubmitting') : t('welcome.accountSubmit') }}</span>
        </LumiButton>
      </div>

      <div class="account-skip animate-fade-in">
        <button class="skip-link" @click="$emit('next')">{{ t('welcome.accountSkip') }}</button>
        <span class="skip-hint">{{ t('welcome.accountSkipHint') }}</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.welcome-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-6);
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

.account-hero-icon {
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

.account-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--text-muted);
  font-size: var(--text-sm);
  padding: var(--space-6) 0;
}

.account-loading__spinner {
  animation: account-spin 1s linear infinite;
}

@keyframes account-spin {
  to { transform: rotate(360deg); }
}

/* 已登录账户卡 */
.account-card {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px solid var(--lumi-brand-border);
  background: var(--lumi-brand-light);
}

.account-card__avatar {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand-gradient-soft);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.account-card__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.account-card__name {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-card__meta {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.account-card__check {
  margin-left: auto;
  color: var(--lumi-brand);
  flex-shrink: 0;
}

/* 表单体 */
.account-body {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
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

/* 选项卡：本地（激活）/ 在线（置灰） */
.account-options {
  display: flex;
  gap: var(--space-3);
}

.option-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

.option-card.active {
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.option-card.disabled {
  color: var(--text-muted);
  cursor: not-allowed;
  opacity: 0.75;
}

.option-badge {
  margin-left: auto;
  font-size: var(--text-2xs);
  padding: 2px var(--space-2);
  border-radius: var(--radius-full);
  background: var(--bg-secondary);
  color: var(--text-muted);
  flex-shrink: 0;
}

.account-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
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

/* 跳过行 */
.account-skip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
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

.step-actions .lumi-btn-text > svg {
  margin-left: var(--space-1);
}

button:focus-visible,
.lumi-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}
</style>
