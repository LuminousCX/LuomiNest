<script setup lang="ts">
/**
 * 欢迎向导 - 步骤4：准备就绪
 *
 * 协议/隐私同意已前移至第 0 步 StepAgreement（门禁，不可跳过），本步骤不再重复展示。
 */
import { ArrowRight, Shield } from 'lucide-vue-next'
import LumiBrandStar from '../common/LumiBrandStar.vue'
import LumiButton from '../common/LumiButton.vue'
import type { WelcomeI18nText } from '../../composables/useWelcomeWizard'

defineProps<{
  i18n: WelcomeI18nText
}>()

defineEmits<{
  prev: []
  start: []
}>()
</script>

<template>
  <div class="welcome-step step-ready">
    <div class="ready-hero animate-scale-in">
      <div class="ready-ring">
        <LumiBrandStar :size="64" />
      </div>
      <Shield :size="28" class="ready-shield" />
    </div>
    <h2 class="ready-title animate-fade-in">{{ i18n.readyTitle }}</h2>
    <p class="ready-desc animate-fade-in">{{ i18n.readyDesc }}</p>

    <div class="step-actions animate-slide-up">
      <LumiButton variant="ghost" size="lg" @click="$emit('prev')">
        {{ i18n.btnBack }}
      </LumiButton>
      <LumiButton class="launch-btn" variant="primary" size="lg" block @click="$emit('start')">
        <span>{{ i18n.btnStart }}</span>
        <ArrowRight :size="16" />
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

.ready-hero {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ready-ring {
  width: 96px;
  height: 96px;
  border-radius: var(--radius-2xl);
  background: var(--lumi-brand-gradient-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: ring-pulse calc(var(--duration-slow) * 6) var(--ease-in-out) infinite;
}

@keyframes ring-pulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--lumi-brand-border); }
  50% { box-shadow: 0 0 0 var(--space-3) transparent; }
}

.ready-shield {
  position: absolute;  bottom: -2px;
  right: -2px;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  background: var(--lumi-success);
  color: var(--text-inverse);
  padding: var(--space-1);
  animation: shield-pop var(--duration-enter) var(--ease-spring) var(--duration-normal) both;
}

@keyframes shield-pop {
  0% { transform: scale(0); }
  100% { transform: scale(1); }
}

.ready-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text);
}

.ready-desc {
  font-size: var(--text-md);
  color: var(--text-muted);
  max-width: 360px;
  text-align: center;
  line-height: var(--leading-relaxed);
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

.launch-btn {
  background: linear-gradient(135deg, var(--lumi-brand), var(--lumi-brand-soft));
}

.launch-btn:hover:not(:disabled) {
  box-shadow: var(--shadow-lg);
}
</style>
