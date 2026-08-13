<script setup lang="ts">
/**
 * LuomiNest 智能体创建向导
 *
 * 4 步向导壳层：头部（步骤标题）+ 主体（步骤内容 Transition）+ 底部（导航按钮）。
 * 表单状态与逻辑由 useAgentCreateForm composable 管理，
 * 各步骤模板与样式拆分至 components/agent-create/ 子组件。
 */
import { X, Sparkles, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import LumiButton from '../components/common/LumiButton.vue'
import StepIdentity from '../components/agent-create/StepIdentity.vue'
import StepSkills from '../components/agent-create/StepSkills.vue'
import StepSettings from '../components/agent-create/StepSettings.vue'
import StepConfirm from '../components/agent-create/StepConfirm.vue'
import {
  useAgentCreateForm,
  STEP_TITLES, STEP_SUBTITLES, TOTAL_STEPS
} from '../composables/useAgentCreateForm'

const {
  currentStep,
  activeAvatarCategory,
  errorMessage,
  formData,
  selectedAvatar,
  currentAvatars,
  canGoNext,
  selectAvatar,
  toggleStyle,
  toggleSkill,
  goNext,
  goPrev,
  handleClose,
} = useAgentCreateForm()

const dismissError = (): void => {
  errorMessage.value = ''
}
</script>

<template>
  <div class="wizard-overlay" @click.self="handleClose">
    <div class="wizard-container animate-scale-in">
      <div class="wizard-header">
        <div class="header-left">
          <div class="header-icon-wrap">
            <Sparkles :size="20" />
          </div>
          <div class="header-titles">
            <h2 class="wizard-title">{{ STEP_TITLES[currentStep] }}</h2>
            <p class="wizard-subtitle">第 {{ currentStep + 1 }} 步 > {{ STEP_SUBTITLES[currentStep] }}</p>
          </div>
        </div>
        <LumiButton
          variant="ghost"
          size="sm"
          icon-only
          aria-label="关闭"
          @click="handleClose"
        >
          <template #icon><X :size="18" /></template>
        </LumiButton>
      </div>

      <div class="wizard-body">
        <Transition name="step-fade" mode="out-in">
          <StepIdentity
            v-if="currentStep === 0"
            key="step-1"
            :form-data="formData"
            :active-avatar-category="activeAvatarCategory"
            :current-avatars="currentAvatars"
            :selected-avatar="selectedAvatar"
            :current-step="currentStep"
            @select-avatar="selectAvatar"
            @select-style="toggleStyle"
            @select-category="activeAvatarCategory = $event"
          />

          <StepSkills
            v-else-if="currentStep === 1"
            key="step-2"
            :form-data="formData"
            @toggle-skill="toggleSkill"
          />

          <StepSettings
            v-else-if="currentStep === 2"
            key="step-3"
            :form-data="formData"
          />

          <StepConfirm
            v-else-if="currentStep === 3"
            key="step-4"
            :form-data="formData"
            :error-message="errorMessage"
            :selected-avatar="selectedAvatar"
            @dismiss-error="dismissError"
          />
        </Transition>
      </div>

      <div class="wizard-footer">
        <LumiButton
          variant="secondary"
          size="md"
          :disabled="currentStep === 0"
          @click="goPrev"
        >
          <ChevronLeft :size="16" />
          <span>上一步</span>
        </LumiButton>
        <LumiButton
          variant="primary"
          size="md"
          :disabled="!canGoNext"
          @click="goNext"
        >
          <span>{{ currentStep === TOTAL_STEPS - 1 ? '创建 Agent' : `下一步: ${currentStep === 0 ? '技能' : currentStep === 1 ? '设置' : '确认'}` }}</span>
          <ChevronRight :size="16" />
        </LumiButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wizard-overlay {
  background: var(--overlay-bg);
  backdrop-filter: blur(var(--space-2));
  -webkit-backdrop-filter: blur(var(--space-2));
  padding: var(--space-6);
}

.wizard-container {
  width: 100%;
  max-width: 900px;
  max-height: 88vh;
  border-radius: var(--radius-xl);
  background: var(--surface);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border-light);
}

.wizard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5) var(--space-7) var(--space-4);
  flex-shrink: 0;
  border-bottom: 1px solid var(--border-light);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.header-icon-wrap {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-titles {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.wizard-title {
  font-size: var(--text-lg);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  line-height: 1.3;
}

.wizard-subtitle {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.wizard-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6) var(--space-7);
  min-height: 0;
}

.wizard-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-7);
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

/* 步骤切换过渡 */
.step-fade-enter-active {
  transition: all var(--duration-slow) var(--ease-in-out);
}

.step-fade-leave-active {
  transition: all var(--duration-normal) var(--ease-in-out);
}

.step-fade-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.step-fade-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

@media (max-width: 768px) {
  .wizard-container {
    max-height: 92vh;
  }
}
</style>
