<script setup lang="ts">
/**
 * 欢迎向导 - 步骤3：准备就绪 + 条款同意
 */
import { Check, ArrowRight, Shield } from 'lucide-vue-next'
import LumiBrandStar from '../common/LumiBrandStar.vue'
import LumiButton from '../common/LumiButton.vue'
import type { WelcomeI18nText } from '../../composables/useWelcomeWizard'

defineProps<{
  i18n: WelcomeI18nText
  agreed: boolean
}>()

defineEmits<{
  'update:agreed': [value: boolean]
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

    <label class="agree-row animate-fade-in">
      <input
        type="checkbox"
        :checked="agreed"
        class="agree-checkbox"
        @change="$emit('update:agreed', ($event.target as HTMLInputElement).checked)"
      />
      <span class="agree-custom">
        <Check :size="12" v-if="agreed" />
      </span>
      <span class="agree-text">{{ i18n.agreeText }}</span>
    </label>

    <div class="step-actions animate-slide-up">
      <LumiButton variant="ghost" size="lg" @click="$emit('prev')">
        {{ i18n.btnBack }}
      </LumiButton>
      <LumiButton class="launch-btn" variant="primary" size="lg" block :disabled="!agreed" @click="$emit('start')">
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
  position: absolute;
  bottom: -2px;
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

.agree-row {
  display: flex;
  align-items: center;
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
