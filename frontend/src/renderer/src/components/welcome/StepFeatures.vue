<script setup lang="ts">
/**
 * 欢迎向导 - 步骤1：功能一览
 */
import { Sparkles, ChevronRight } from 'lucide-vue-next'
import LumiCardIcon from '../common/LumiCardIcon.vue'
import LumiButton from '../common/LumiButton.vue'
import { FEATURES } from '../../composables/useWelcomeWizard'
import type { WelcomeI18nText } from '../../composables/useWelcomeWizard'

defineProps<{
  i18n: WelcomeI18nText
}>()

defineEmits<{
  next: []
  prev: []
}>()
</script>

<template>
  <div class="welcome-step step-features">
    <div class="feature-header animate-fade-in">
      <Sparkles :size="22" class="feature-icon" />
      <h2>{{ i18n.featureTitle }}</h2>
    </div>

    <div class="feature-grid">
      <div
        v-for="(feat, idx) in FEATURES"
        :key="feat.key"
        class="feature-card"
        :style="{ '--feat-color': `var(${feat.color})`, animationDelay: `${idx * 100}ms` }"
      >
        <LumiCardIcon
          :icon="feat.icon"
          :size="24"
          :theme="feat.theme"
        />
        <span class="feat-name">{{ i18n[feat.key] }}</span>
        <span class="feat-desc">{{ i18n[feat.keyDesc] }}</span>
      </div>
    </div>

    <div class="step-actions">
      <LumiButton variant="ghost" size="lg" @click="$emit('prev')">
        {{ i18n.btnBack }}
      </LumiButton>
      <LumiButton variant="primary" size="lg" block @click="$emit('next')">
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

.feature-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  text-align: center;
  flex-direction: column;
}

.feature-icon {
  color: var(--lumi-brand);
}

.feature-header h2 {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text);
}

.feature-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
  width: 100%;
}

.feature-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-5) var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
  text-align: center;
  transition: all var(--transition-normal);
  animation: lumi-scale-in var(--duration-slow) var(--ease-out-expo) both;
}

.feature-card:hover {
  border-color: var(--feat-color);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.feat-name {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.feat-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
  line-height: var(--leading-normal);
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
</style>
