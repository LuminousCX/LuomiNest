<script setup lang="ts">
/**
 * 欢迎向导 - 步骤0：用户协议 + 隐私政策同意门禁
 *
 * 两个独立勾选框（协议 / 隐私政策）都勾选才能进入下一步；
 * 「查看完整协议」「查看隐私政策」经 router push 打开独立法务页，
 * 法务页根据 from=welcome 查询参数返回向导（协议门禁不可跳过）。
 * 同意记录（版本 + 时间）由父级 useWelcomeWizard 在下一步时写入 config.onboarding。
 */
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Check, ChevronRight, FileText, Shield, Scale } from 'lucide-vue-next'
import LumiBrandStar from '../common/LumiBrandStar.vue'
import LumiButton from '../common/LumiButton.vue'
import type { WelcomeI18nText } from '../../composables/useWelcomeWizard'

defineProps<{
  i18n: WelcomeI18nText
  agreedTerms: boolean
  agreedPrivacy: boolean
  agreementReady: boolean
}>()

const emit = defineEmits<{
  'update:agreedTerms': [value: boolean]
  'update:agreedPrivacy': [value: boolean]
  next: []
}>()

const { t } = useI18n()
const router = useRouter()

/** 协议要点摘要（标题走 i18n，正文为固定中文摘要，完整文本见独立法务页） */
const highlights = ['agreement', 'localFirst', 'thirdParty'] as const

const openTerms = () => router.push({ path: '/settings/terms-detail', query: { from: 'welcome' } })
const openPrivacy = () => router.push({ path: '/settings/privacy-detail', query: { from: 'welcome' } })

const highlightText = (key: string) => t(`welcome.agreePoint.${key}`)
</script>

<template>
  <div class="welcome-step step-agreement">
    <div class="agreement-hero animate-fade-in">
      <div class="agreement-hero__icons">
        <div class="agreement-hero__badge">
          <LumiBrandStar :size="30" />
        </div>
        <Scale :size="20" class="agreement-hero__scale" />
      </div>
      <h2 class="agreement-hero__title">{{ t('welcome.agreementTitle') }}</h2>
      <p class="agreement-hero__desc">{{ t('welcome.agreementDesc') }}</p>
    </div>

    <!-- 要点摘要 -->
    <div class="agreement-points animate-slide-up">
      <div v-for="key in highlights" :key="key" class="agreement-point">
        <component :is="key === 'agreement' ? FileText : key === 'localFirst' ? Shield : Scale" :size="14" />
        <p>{{ highlightText(key) }}</p>
      </div>
      <div class="agreement-links">
        <button type="button" class="agreement-link" @click.prevent="openTerms">
          {{ t('welcome.viewTerms') }}
        </button>
        <span class="agreement-links__dot">·</span>
        <button type="button" class="agreement-link" @click.prevent="openPrivacy">
          {{ t('welcome.viewPrivacy') }}
        </button>
      </div>
    </div>

    <!-- 两个独立勾选框 -->
    <div class="agreement-checks animate-fade-in">
      <label class="agree-row">
        <input
          type="checkbox"
          :checked="agreedTerms"
          class="agree-checkbox"
          @change="emit('update:agreedTerms', ($event.target as HTMLInputElement).checked)"
        />
        <span class="agree-custom">
          <Check :size="12" v-if="agreedTerms" />
        </span>
        <span class="agree-text">
          {{ t('welcome.agreeTermsPrefix') }}
          <button type="button" class="terms-link" @click.prevent.stop="openTerms">
            {{ t('welcome.termsLinkFull') }}
          </button>
        </span>
      </label>
      <label class="agree-row">
        <input
          type="checkbox"
          :checked="agreedPrivacy"
          class="agree-checkbox"
          @change="emit('update:agreedPrivacy', ($event.target as HTMLInputElement).checked)"
        />
        <span class="agree-custom">
          <Check :size="12" v-if="agreedPrivacy" />
        </span>
        <span class="agree-text">
          {{ t('welcome.agreePrivacyPrefix') }}
          <button type="button" class="terms-link" @click.prevent.stop="openPrivacy">
            {{ t('welcome.privacyLink') }}
          </button>
        </span>
      </label>
    </div>

    <div class="step-actions animate-slide-up">
      <LumiButton
        variant="primary"
        size="lg"
        block
        :disabled="!agreementReady"
        @click="emit('next')"
      >
        <span>{{ t('welcome.agreeNext') }}</span>
        <ChevronRight :size="16" />
      </LumiButton>
    </div>

    <p class="agreement-hint animate-fade-in">{{ t('welcome.agreementGateHint') }}</p>
  </div>
</template>

<style scoped>
.welcome-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-6);
}

/* 顶部品牌 + 标题 */
.agreement-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  text-align: center;
}

.agreement-hero__icons {
  position: relative;
  width: 64px;
  height: 64px;
}

.agreement-hero__badge {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-xl);
  background: var(--lumi-brand-gradient-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-md);
}

.agreement-hero__scale {
  position: absolute;
  bottom: -6px;
  right: -10px;
  color: var(--lumi-brand);
  background: var(--surface);
  border-radius: var(--radius-full);
  padding: 2px;
  box-shadow: var(--shadow-sm);
}

.agreement-hero__title {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text);
}

.agreement-hero__desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  max-width: 360px;
  line-height: var(--leading-relaxed);
}

/* 要点摘要卡 */
.agreement-points {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
}

.agreement-point {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.6;
}

.agreement-point svg {
  flex-shrink: 0;
  margin-top: 3px;
  color: var(--lumi-brand);
}

.agreement-point p {
  margin: 0;
}

.agreement-links {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  margin-top: var(--space-1);
}

.agreement-links__dot {
  color: var(--text-muted);
}

.agreement-link {
  font-size: var(--text-sm);
  color: var(--lumi-brand);
  text-decoration: underline;
  text-underline-offset: 3px;
  transition: opacity var(--transition-fast);
}

.agreement-link:hover {
  opacity: 0.8;
}

/* 勾选框 */
.agreement-checks {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.agree-row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  cursor: pointer;
  user-select: none;
}

.agree-checkbox {
  display: none;
}

.agree-custom {
  width: var(--space-5);
  height: var(--space-5);
  border-radius: var(--radius-xs);
  border: 1.5px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-inverse);
  background: var(--surface);
  transition: all var(--transition-normal);
  flex-shrink: 0;
  margin-top: 1px;
}

.agree-row:hover .agree-custom {
  border-color: var(--lumi-brand);
}

.agree-row:has(.agree-checkbox:checked) .agree-custom {
  background: var(--lumi-brand);
  border-color: var(--lumi-brand);
}

.agree-text {
  font-size: var(--text-base);
  color: var(--text-muted);
  line-height: 1.5;
}

.terms-link {
  font-size: inherit;
  color: var(--lumi-brand);
  text-decoration: underline;
  text-underline-offset: 3px;
  transition: opacity var(--transition-fast);
}

.terms-link:hover {
  opacity: 0.8;
}

/* 底部按钮 + 提示 */
.step-actions {
  display: flex;
  gap: var(--space-3);
  width: 100%;
  margin-top: var(--space-1);
}

.agreement-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-align: center;
  margin: 0;
}

button:focus-visible,
.lumi-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}
</style>
