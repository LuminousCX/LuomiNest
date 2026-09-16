<script setup lang="ts">
/**
 * LuomiNest 欢迎向导
 *
 * 5 步向导壳层：背景装饰 + 跳过按钮 + 步骤内容 Transition + 步骤指示点。
 * 流程（2026 重编排）：
 *   0. StepAgreement — 用户协议/隐私政策同意门禁（不可跳过，全局跳过按钮在此步隐藏）
 *   1. StepLanguage  — 语言选择
 *   2. StepLogin     — 辰汐通行证 / 本地账号 / 跳过（可稍后在设置补登）
 *   3. StepTour      — 新手指引功能亮点
 *   4. StepReady     — 准备就绪
 * 状态与逻辑由 useWelcomeWizard composable 管理，
 * 各步骤模板与样式拆分至 components/welcome/ 子组件。
 */
import { ref, watch } from 'vue'
import StepAgreement from '../components/welcome/StepAgreement.vue'
import StepLanguage from '../components/welcome/StepLanguage.vue'
import StepLogin from '../components/welcome/StepLogin.vue'
import StepTour from '../components/welcome/StepTour.vue'
import StepReady from '../components/welcome/StepReady.vue'
import { useWelcomeWizard, TOTAL_STEPS } from '../composables/useWelcomeWizard'

const {
  currentStep,
  selectedLang,
  selectLang,
  i18n,
  agreedTerms,
  agreedPrivacy,
  agreementReady,
  agreeAndNext,
  markTutorialDone,
  accountSubmitting,
  accountError,
  hasAccount,
  currentUser,
  accountForm,
  accountFormValid,
  registerAndNext,
  loginAndNext,
  nextStep,
  prevStep,
  startApp,
  skipWizard,
} = useWelcomeWizard()

/** 教程最后一卡「开始使用」：记录 tutorialDone 后进入准备就绪步 */
const finishTour = (): void => {
  markTutorialDone()
  nextStep()
}

/** 已到达过的最远步骤：协议门禁步（0）未通过时不允许经步骤点跳过到后续步骤 */
const maxVisitedStep = ref(0)
watch(currentStep, (s) => {
  if (s > maxVisitedStep.value) maxVisitedStep.value = s
})
const jumpTo = (idx: number): void => {
  if (idx <= maxVisitedStep.value) currentStep.value = idx
}
</script>

<template>
  <div class="welcome-view">
    <div class="welcome-bg">
      <div class="bg-orb bg-orb-1"></div>
      <div class="bg-orb bg-orb-2"></div>
    </div>

    <!-- 协议门禁步隐藏全局跳过：跳过仅针对登录/教程，协议同意不可跳过 -->
    <button v-if="currentStep > 0" class="skip-btn" @click="skipWizard" :title="i18n.skip">
      {{ i18n.skip }}
    </button>

    <div class="welcome-container">
      <Transition name="step-fade" mode="out-in">
        <StepAgreement
          v-if="currentStep === 0"
          key="step-0"
          :i18n="i18n"
          :agreed-terms="agreedTerms"
          :agreed-privacy="agreedPrivacy"
          :agreement-ready="agreementReady"
          @update:agreed-terms="agreedTerms = $event"
          @update:agreed-privacy="agreedPrivacy = $event"
          @next="agreeAndNext"
        />

        <StepLanguage
          v-else-if="currentStep === 1"
          key="step-1"
          :i18n="i18n"
          :selected-lang="selectedLang"
          @update:selected-lang="selectLang"
          @next="nextStep"
        />

        <StepLogin
          v-else-if="currentStep === 2"
          key="step-2"
          :has-account="hasAccount"
          :current-user="currentUser"
          :account-form="accountForm"
          :account-form-valid="accountFormValid"
          :account-submitting="accountSubmitting"
          :account-error="accountError"
          @register="registerAndNext"
          @login="loginAndNext"
          @next="nextStep"
          @prev="prevStep"
        />

        <StepTour v-else-if="currentStep === 3" key="step-3" @finish="finishTour" @prev="prevStep" />

        <StepReady v-else-if="currentStep === 4" key="step-4" :i18n="i18n" @prev="prevStep" @start="startApp" />
      </Transition>

      <div class="step-dots">
        <button
          v-for="s in TOTAL_STEPS"
          :key="s - 1"
          :class="['dot', { active: currentStep === s - 1 }]"
          :disabled="s - 1 > maxVisitedStep"
          @click="jumpTo(s - 1)"
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

.dot:disabled {
  cursor: default;
  opacity: 0.55;
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
