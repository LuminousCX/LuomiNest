<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Globe,
  Sparkles,
  Bot,
  ChevronRight,
  Check,
  Zap,
  Shield,
  Palette,
  ArrowRight
} from 'lucide-vue-next'

const router = useRouter()

const VERSION = '0.1.0'

const currentStep = ref(0)

const selectedLang = ref<'zh' | 'en'>('zh')

const i18n = computed(() => {
  if (selectedLang.value === 'en') {
    return {
      title: 'Welcome to',
      appName: 'LuomiNest',
      subtitle: 'Your AI Companion Workspace',
      version: `Version ${VERSION}`,
      langTitle: 'Select Language',
      langZh: '中文',
      langEn: 'English',
      featureTitle: 'What\'s Inside',
      featAgent: 'Multi-Agent Orchestration',
      featAgentDesc: 'Collaborate with multiple AI agents seamlessly',
      featWorkflow: 'Visual Workflow Builder',
      featWorkflowDesc: 'Design and automate complex task pipelines',
      featBrowser: 'AI-Powered Browser',
      featBrowserDesc: 'Let AI navigate and operate web pages for you',
      featAvatar: 'Avatar Workshop',
      featAvatarDesc: 'Customize Live2D / VRM / PixelPet avatars',
      readyTitle: 'All Set!',
      readyDesc: 'LuomiNest is ready to go. Let\'s start your journey.',
      btnNext: 'Next',
      btnStart: 'Get Started',
      btnBack: 'Back',
      agreeText: 'I agree to the terms and conditions',
      skip: 'Skip'
    }
  }
  return {
    title: '欢迎来到',
    appName: 'LuomiNest',
    subtitle: '你的 AI 伴侣工作台',
    version: `版本 ${VERSION}`,
    langTitle: '选择语言',
    langZh: '中文',
    langEn: 'English',
    featureTitle: '功能一览',
    featAgent: '多智能体编排',
    featAgentDesc: '与多个 AI Agent 无缝协作',
    featWorkflow: '可视化工作流',
    featWorkflowDesc: '设计和自动化复杂任务管线',
    featBrowser: 'AI 驱动浏览器',
    featBrowserDesc: '让 AI 帮你操作网页',
    featAvatar: '皮套工坊',
    featAvatarDesc: '定制 Live2D / VRM / PixelPet 形象',
    readyTitle: '准备就绪！',
    readyDesc: 'LuomiNest 已就绪，开启你的旅程吧。',
    btnNext: '下一步',
    btnStart: '开始使用',
    btnBack: '上一步',
    agreeText: '我已阅读并同意相关条款',
    skip: '跳过'
  }
})

const agreed = ref(false)

const features = [
  { icon: Bot, color: '#6366f1', key: 'featAgent', keyDesc: 'featAgentDesc' },
  { icon: Zap, color: '#f59e0b', key: 'featWorkflow', keyDesc: 'featWorkflowDesc' },
  { icon: Globe, color: '#3b82f6', key: 'featBrowser', keyDesc: 'featBrowserDesc' },
  { icon: Palette, color: '#ec4899', key: 'featAvatar', keyDesc: 'featAvatarDesc' }
]

function nextStep() {
  if (currentStep.value < 2) currentStep.value++
}

function prevStep() {
  if (currentStep.value > 0) currentStep.value--
}

function startApp() {
  router.push('/workspace')
}

function skipWizard() {
  router.push('/workspace')
}
</script>

<template>
  <div class="welcome-view">
    <div class="welcome-bg">
      <div class="bg-orb bg-orb-1"></div>
      <div class="bg-orb bg-orb-2"></div>
      <div class="bg-grid"></div>
    </div>

    <button class="skip-btn" @click="skipWizard" :title="i18n.skip">
      {{ i18n.skip }}
    </button>

    <div class="welcome-container">
      <Transition name="step-fade" mode="out-in">
        <div v-if="currentStep === 0" key="step-0" class="welcome-step step-lang">
          <div class="brand-hero animate-brand-enter">
            <div class="brand-icon-wrap">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
                <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"
                  fill="var(--lumi-primary)" stroke="var(--lumi-primary)" stroke-width="1.5"/>
              </svg>
            </div>
            <h1 class="brand-title">
              <span class="brand-greeting">{{ i18n.title }}</span>
              <span class="brand-name">{{ i18n.appName }}</span>
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
                :class="['lang-card', { active: selectedLang === 'zh' }]"
                @click="selectedLang = 'zh'"
              >
                <span class="lang-flag">中</span>
                <span class="lang-label">{{ i18n.langZh }}</span>
                <Check v-if="selectedLang === 'zh'" :size="16" class="lang-check" />
              </button>
              <button
                :class="['lang-card', { active: selectedLang === 'en' }]"
                @click="selectedLang = 'en'"
              >
                <span class="lang-flag">EN</span>
                <span class="lang-label">{{ i18n.langEn }}</span>
                <Check v-if="selectedLang === 'en'" :size="16" class="lang-check" />
              </button>
            </div>
          </div>

          <div class="step-actions animate-fade-in">
            <button class="primary-btn" @click="nextStep">
              <span>{{ i18n.btnNext }}</span>
              <ChevronRight :size="16" />
            </button>
          </div>
        </div>

        <div v-else-if="currentStep === 1" key="step-1" class="welcome-step step-features">
          <div class="feature-header animate-fade-in">
            <Sparkles :size="22" class="feature-icon" />
            <h2>{{ i18n.featureTitle }}</h2>
          </div>

          <div class="feature-grid">
            <div
              v-for="(feat, idx) in features"
              :key="feat.key"
              class="feature-card"
              :style="{ '--feat-color': feat.color, animationDelay: `${idx * 100}ms` }"
            >
              <div class="feat-icon-wrap">
                <component :is="feat.icon" :size="24" />
              </div>
              <span class="feat-name">{{ i18n[feat.key] }}</span>
              <span class="feat-desc">{{ i18n[feat.keyDesc] }}</span>
            </div>
          </div>

          <div class="step-actions">
            <button class="ghost-btn" @click="prevStep">
              {{ i18n.btnBack }}
            </button>
            <button class="primary-btn" @click="nextStep">
              <span>{{ i18n.btnNext }}</span>
              <ChevronRight :size="16" />
            </button>
          </div>
        </div>

        <div v-else key="step-2" class="welcome-step step-ready">
          <div class="ready-hero animate-scale-in">
            <div class="ready-ring">
              <svg width="64" height="64" viewBox="0 0 24 24" fill="none">
                <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"
                  fill="var(--lumi-primary)" stroke="var(--lumi-primary)" stroke-width="1"/>
              </svg>
            </div>
            <Shield :size="28" class="ready-shield" />
          </div>
          <h2 class="ready-title animate-fade-in">{{ i18n.readyTitle }}</h2>
          <p class="ready-desc animate-fade-in">{{ i18n.readyDesc }}</p>

          <label class="agree-row animate-fade-in">
            <input type="checkbox" v-model="agreed" class="agree-checkbox" />
            <span class="agree-custom">
              <Check :size="12" v-if="agreed" />
            </span>
            <span class="agree-text">{{ i18n.agreeText }}</span>
          </label>

          <div class="step-actions animate-slide-up">
            <button class="ghost-btn" @click="prevStep">
              {{ i18n.btnBack }}
            </button>
            <button class="primary-btn launch-btn" @click="startApp" :disabled="!agreed">
              <span>{{ i18n.btnStart }}</span>
              <ArrowRight :size="16" />
            </button>
          </div>
        </div>
      </Transition>

      <div class="step-dots">
        <button
          v-for="s in 3"
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
  background: var(--workspace-bg);
}

.welcome-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(13, 148, 136, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(13, 148, 136, 0.03) 1px, transparent 1px);
  background-size: 40px 40px;
}

.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.4;
  animation: orb-float 12s ease-in-out infinite;
}

.bg-orb-1 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(13, 148, 136, 0.15), transparent 70%);
  top: -100px;
  right: -80px;
  animation-delay: 0s;
}

.bg-orb-2 {
  width: 320px;
  height: 320px;
  background: radial-gradient(circle, rgba(20, 184, 166, 0.12), transparent 70%);
  bottom: -60px;
  left: -60px;
  animation-delay: -6s;
}

@keyframes orb-float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(20px, -15px) scale(1.05); }
  66% { transform: translate(-10px, 10px) scale(0.97); }
}

.skip-btn {
  position: absolute;
  top: 20px;
  right: 24px;
  padding: 6px 16px;
  font-size: 13px;
  color: var(--text-muted);
  border-radius: var(--radius-full);
  transition: all 300ms ease-in-out;
  z-index: 10;
}

.skip-btn:hover {
  background: var(--workspace-panel);
  color: var(--text-secondary);
}

.welcome-container {
  position: relative;
  width: 100%;
  max-width: 520px;
  padding: 40px;
  z-index: 1;
}

.welcome-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
}

.brand-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  text-align: center;
}

.brand-icon-wrap {
  width: 72px;
  height: 72px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(13, 148, 136, 0.1), rgba(20, 184, 166, 0.08));
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 32px rgba(13, 148, 136, 0.15);
}

.brand-title {
  font-size: 32px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.5px;
}

.brand-greeting {
  display: block;
  font-size: 18px;
  font-weight: 400;
  color: var(--text-secondary);
}

.brand-name {
  display: block;
  background: linear-gradient(135deg, var(--lumi-primary), #14b8a6, #2dd4bf);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.brand-subtitle {
  font-size: 15px;
  color: var(--text-muted);
  margin-top: 4px;
}

.version-badge {
  font-size: 11px;
  padding: 3px 12px;
  border-radius: var(--radius-full);
  background: var(--workspace-panel);
  color: var(--text-muted);
  font-weight: 500;
  border: 1px solid var(--workspace-border);
}

.lang-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.section-header svg {
  color: var(--lumi-primary);
}

.lang-options {
  display: flex;
  gap: 12px;
}

.lang-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  border-radius: var(--radius-lg);
  border: 1.5px solid var(--workspace-border);
  background: var(--workspace-card);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  position: relative;
}

.lang-card:hover {
  border-color: rgba(13, 148, 136, 0.4);
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.lang-card.active {
  border-color: var(--lumi-primary);
  background: rgba(13, 148, 136, 0.04);
  box-shadow: 0 4px 16px rgba(13, 148, 136, 0.1);
}

.lang-flag {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: var(--workspace-panel);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.lang-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.lang-check {
  margin-left: auto;
  color: var(--lumi-primary);
}

.feature-header {
  display: flex;
  align-items: center;
  gap: 10px;
  text-align: center;
  flex-direction: column;
}

.feature-icon {
  color: var(--lumi-primary);
}

.feature-header h2 {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.feature-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  width: 100%;
}

.feature-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 22px 16px;
  border-radius: var(--radius-lg);
  border: 1.5px solid var(--workspace-border);
  background: var(--workspace-card);
  text-align: center;
  transition: all 300ms ease-in-out;
  animation: lumi-scale-in 0.35s ease-out both;
}

.feature-card:hover {
  border-color: var(--feat-color);
  box-shadow: 0 6px 24px color-mix(in srgb, var(--feat-color) 12%, transparent);
  transform: translateY(-3px);
}

.feat-icon-wrap {
  width: 46px;
  height: 46px;
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--feat-color) 10%, transparent);
  color: var(--feat-color);
  display: flex;
  align-items: center;
  justify-content: center;
}

.feat-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.feat-desc {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.5;
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
  border-radius: 28px;
  background: linear-gradient(135deg, rgba(13, 148, 136, 0.08), rgba(20, 184, 166, 0.06));
  display: flex;
  align-items: center;
  justify-content: center;
  animation: ring-pulse 2s ease-in-out infinite;
}

@keyframes ring-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(13, 148, 136, 0.2); }
  50% { box-shadow: 0 0 0 12px rgba(13, 148, 136, 0); }
}

.ready-shield {
  position: absolute;
  bottom: -2px;
  right: -2px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--lumi-success);
  color: white;
  padding: 5px;
  animation: shield-pop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) 0.3s both;
}

@keyframes shield-pop {
  0% { transform: scale(0); }
  100% { transform: scale(1); }
}

.ready-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
}

.ready-desc {
  font-size: 14px;
  color: var(--text-muted);
  max-width: 360px;
  text-align: center;
  line-height: 1.6;
}

.agree-row {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.agree-checkbox {
  display: none;
}

.agree-custom {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  border: 1.5px solid var(--workspace-border);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  background: var(--workspace-card);
  transition: all 300ms ease-in-out;
  flex-shrink: 0;
}

.agree-row:hover .agree-custom {
  border-color: var(--lumi-primary);
}

.agree-row:has(.agree-checkbox:checked) .agree-custom {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
}

.agree-text {
  font-size: 13px;
  color: var(--text-muted);
}

.step-actions {
  display: flex;
  gap: 12px;
  width: 100%;
  margin-top: 8px;
}

.primary-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex: 1;
  padding: 13px 28px;
  border-radius: var(--radius-lg);
  font-size: 14px;
  font-weight: 600;
  background: var(--lumi-primary);
  color: white;
  cursor: pointer;
  transition: all 300ms ease-in-out;
}

.primary-btn:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(13, 148, 136, 0.25);
}

.primary-btn:active:not(:disabled) {
  transform: translateY(0) scale(0.98);
}

.primary-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.launch-btn {
  background: linear-gradient(135deg, var(--lumi-primary), #14b8a6);
}

.launch-btn:hover:not(:disabled) {
  box-shadow: 0 8px 28px rgba(13, 148, 136, 0.35);
}

.ghost-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 13px 24px;
  border-radius: var(--radius-lg);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  border: 1px solid var(--workspace-border);
  background: transparent;
}

.ghost-btn:hover {
  background: var(--workspace-panel);
  color: var(--text-secondary);
  border-color: var(--workspace-border);
}

.step-dots {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-top: 8px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--workspace-border);
  border: none;
  cursor: pointer;
  transition: all 300ms ease-in-out;
  padding: 0;
}

.dot.active {
  width: 24px;
  border-radius: 4px;
  background: var(--lumi-primary);
}

@keyframes brand-enter {
  0% { opacity: 0; transform: translateY(30px) scale(0.94); filter: blur(4px); }
  100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
}

.animate-brand-enter {
  animation: brand-enter 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.step-fade-enter-active {
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}

.step-fade-leave-active {
  transition: all 0.25s cubic-bezier(0.4, 0, 1, 1);
}

.step-fade-enter-from {
  opacity: 0;
  transform: translateX(30px);
}

.step-fade-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}
</style>
