<script setup lang="ts">
/**
 * 欢迎向导 - 步骤0：品牌展示与语言选择
 */
import { Globe, Check, ChevronRight } from 'lucide-vue-next'
import LumiBrandStar from '../common/LumiBrandStar.vue'
import LumiButton from '../common/LumiButton.vue'
import type { WelcomeI18nText } from '../../composables/useWelcomeWizard'
import type { AppLocale } from '../../i18n'

defineProps<{
  i18n: WelcomeI18nText
  selectedLang: AppLocale
}>()

const emit = defineEmits<{
  'update:selectedLang': [lang: AppLocale]
  next: []
}>()
</script>

<template>
  <div class="welcome-step step-lang">
    <div class="brand-hero animate-brand-enter">
      <div class="brand-icon-wrap">
        <LumiBrandStar :size="48" />
      </div>
      <h1 class="brand-title">
        <span class="brand-greeting">{{ i18n.title }}</span>
        <span class="brand-name lumi-gradient-text">{{ i18n.appName }}</span>
      </h1>
      <p class="brand-subtitle">{{ i18n.subtitle }}</p>
      <span class="version-badge">{{ i18n.version }}</span>
    </div>

    <div class="lang-section animate-slide-up">
      <div class="section-header">
        <Globe :size="18" />
        <span>{{ i18n.langTitle }}</span>
      </div>
      <div class="lang-options">
        <button
          :class="['lang-card', { active: selectedLang === 'zh-CN' }]"
          @click="emit('update:selectedLang', 'zh-CN')"
        >
          <span class="lang-flag">中</span>
          <span class="lang-label">{{ i18n.langZh }}</span>
          <Check v-if="selectedLang === 'zh-CN'" :size="16" class="lang-check" />
        </button>
        <button
          :class="['lang-card', { active: selectedLang === 'en-US' }]"
          @click="emit('update:selectedLang', 'en-US')"
        >
          <span class="lang-flag">EN</span>
          <span class="lang-label">{{ i18n.langEn }}</span>
          <Check v-if="selectedLang === 'en-US'" :size="16" class="lang-check" />
        </button>
        <button
          :class="['lang-card', { active: selectedLang === 'ja-JP' }]"
          @click="emit('update:selectedLang', 'ja-JP')"
        >
          <span class="lang-flag">日</span>
          <span class="lang-label">{{ i18n.langJa }}</span>
          <Check v-if="selectedLang === 'ja-JP'" :size="16" class="lang-check" />
        </button>
      </div>
    </div>

    <div class="step-actions animate-fade-in">
      <LumiButton variant="primary" size="lg" block @click="emit('next')">
        <span>{{ i18n.btnNext }}</span>
        <ChevronRight :size="16" />
      </LumiButton>
    </div>
  </div>
</template>

<style scoped>
.welcome-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-7);
}

.brand-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  text-align: center;
}

.brand-icon-wrap {
  width: 72px;
  height: 72px;
  border-radius: var(--radius-xl);
  background: var(--lumi-brand-gradient-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-md);
}

.brand-title {
  font-size: var(--text-4xl);
  font-weight: var(--font-bold);
  line-height: 1.2;
  letter-spacing: -0.5px;
}

.brand-greeting {
  display: block;
  font-size: var(--text-2xl);
  font-weight: var(--font-normal);
  color: var(--text-secondary);
}

.brand-name {
  display: block;
}

.brand-subtitle {
  font-size: var(--text-lg);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.version-badge {
  font-size: var(--text-xs);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  background: var(--bg-secondary);
  color: var(--text-muted);
  font-weight: var(--font-medium);
  border: 1px solid var(--border);
}

.lang-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.section-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.section-header svg {
  color: var(--lumi-brand);
}

.lang-options {
  display: flex;
  gap: var(--space-3);
}

.lang-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
  cursor: pointer;
  transition: all var(--transition-normal);
  position: relative;
}

.lang-card:hover {
  border-color: var(--lumi-brand-border);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.lang-card.active {
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  box-shadow: var(--shadow-sm);
}

.lang-flag {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-md);
  font-weight: var(--font-bold);
  color: var(--text-secondary);
  flex-shrink: 0;
}

.lang-label {
  font-size: var(--text-md);
  font-weight: var(--font-medium);
  color: var(--text);
}

.lang-check {
  margin-left: auto;
  color: var(--lumi-brand);
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

@keyframes brand-enter {
  0% { opacity: 0; transform: translateY(30px) scale(0.94); filter: blur(4px); }
  100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
}

.animate-brand-enter {
  animation: brand-enter var(--duration-enter) var(--ease-out-expo) both;
}

button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}
</style>
