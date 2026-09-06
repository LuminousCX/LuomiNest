<script setup lang="ts">
/**
 * LuomiNest 欢迎向导
 *
 * 4 步向导壳层：背景装饰 + 跳过按钮 + 步骤内容 Transition + 步骤指示点。
 * 状态与逻辑由 useWelcomeWizard composable 管理，
 * 各步骤模板与样式拆分至 components/welcome/ 子组件。
 */
import StepLanguage from '../components/welcome/StepLanguage.vue'
import StepFeatures from '../components/welcome/StepFeatures.vue'
import StepAiModel from '../components/welcome/StepAiModel.vue'
import StepReady from '../components/welcome/StepReady.vue'
import { useWelcomeWizard, TOTAL_STEPS } from '../composables/useWelcomeWizard'

const {
  currentStep,
  selectedLang,
  selectLang,
  agreed,
  i18n,
  addTemplateCategory,
  selectedTemplate,
  aiModelSaving,
  aiModelError,
  newProvider,
  newProviderFormValid,
  handleTemplateSelect,
  addProviderAndNext,
  nextStep,
  prevStep,
  startApp,
  skipWizard,
} = useWelcomeWizard()
</script>

<template>
  <div class="welcome-view">
    <div class="welcome-bg">
      <div class="bg-orb bg-orb-1"></div>
      <div class="bg-orb bg-orb-2"></div>
    </div>

    <button class="skip-btn" @click="skipWizard" :title="i18n.skip">
      {{ i18n.skip }}
    </button>

    <div class="welcome-container">
      <Transition name="step-fade" mode="out-in">
        <StepLanguage
          v-if="currentStep === 0"
          key="step-0"
          :i18n="i18n"
          :selected-lang="selectedLang"
          @update:selected-lang="selectLang"
          @next="nextStep"
        />

        <StepFeatures
          v-else-if="currentStep === 1"
          key="step-1"
          :i18n="i18n"
          @next="nextStep"
          @prev="prevStep"
        />

        <StepAiModel
          v-else-if="currentStep === 2"
          key="step-2"
          :i18n="i18n"
          :add-template-category="addTemplateCategory"
          :selected-template="selectedTemplate"
          :ai-model-error="aiModelError"
          :ai-model-saving="aiModelSaving"
          :new-provider="newProvider"
          :new-provider-form-valid="newProviderFormValid"
          @update:add-template-category="addTemplateCategory = $event"
          @select-template="handleTemplateSelect"
          @add-provider-and-next="addProviderAndNext"
          @next="nextStep"
          @prev="prevStep"
        />

        <StepReady
          v-else-if="currentStep === 3"
          key="step-3"
          :i18n="i18n"
          :agreed="agreed"
          @update:agreed="agreed = $event"
          @prev="prevStep"
          @start="startApp"
        />
      </Transition>

      <div class="step-dots">
        <button
          v-for="s in TOTAL_STEPS"
          :key="s - 1"
          :class="['dot', { active: currentStep === s - 1 }]"
          @click="currentStep = s - 1"
        ></button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.welcome-view {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  width: 100%;
  overflow: hidden;
  background: var(--bg);
}

.welcome-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.bg-orb {
  position: absolute;
  border-radius: var(--radius-full);
  filter: blur(120px);
  opacity: 0.2;
  animation: orb-float 18s var(--ease-in-out) infinite;
  will-change: transform, opacity;
}

.bg-orb-1 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, var(--lumi-brand-glow), transparent 70%);
  top: -150px;
  right: -120px;
  animation-delay: 0s;
}

.bg-orb-2 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, var(--lumi-brand-glow), transparent 70%);
  bottom: -100px;
  left: -100px;
  animation-delay: -9s;
}

.skip-btn {
  position: absolute;
  top: var(--space-5);
  right: var(--space-6);
  padding: var(--space-1) var(--space-4);
  font-size: var(--text-base);
  color: var(--text-muted);
  border-radius: var(--radius-full);
  transition: all var(--transition-normal);
  z-index: 10;
}

.skip-btn:hover {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.welcome-container {
  position: relative;
  width: 100%;
  max-width: 480px;
  padding: var(--space-9);
  z-index: 1;
}

.step-dots {
  display: flex;
  gap: var(--space-2);
  justify-content: center;
  margin-top: var(--space-2);
}

.dot {
  width: var(--space-2);
  height: var(--space-2);
  border-radius: var(--radius-full);
  background: var(--border);
  border: none;
  cursor: pointer;
  transition: all var(--transition-normal);
  padding: 0;
}

.dot.active {
  width: var(--space-6);
  border-radius: var(--radius-xs);
  background: var(--lumi-brand);
}

.step-fade-enter-active {
  transition: all var(--duration-enter) var(--ease-out-expo);
}

.step-fade-leave-active {
  transition: all var(--duration-leave) var(--ease-default);
}

.step-fade-enter-from {
  opacity: 0;
  transform: translateX(30px);
}

.step-fade-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

button:focus-visible,
.lumi-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}
</style>
