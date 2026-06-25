<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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
  ArrowRight,
  Cpu,
  Cloud,
  Monitor,
  Network,
  AlertCircle,
} from 'lucide-vue-next'
import { useModelStore } from '../stores/model'
import LumiCardIcon from '../components/common/LumiCardIcon.vue'
import LumiBrandStar from '../components/common/LumiBrandStar.vue'
import LumiButton from '../components/common/LumiButton.vue'
import LumiInput from '../components/common/LumiInput.vue'
import LumiEmptyState from '../components/common/LumiEmptyState.vue'

const router = useRouter()
const modelStore = useModelStore()

const VERSION = ref('')

const currentStep = ref(0)
const TOTAL_STEPS = 4

const selectedLang = ref<'zh' | 'en'>('zh')

const i18n = computed(() => {
  if (selectedLang.value === 'en') {
    return {
      title: 'Welcome to',
      appName: 'LuomiNest',
      subtitle: 'LuminousChenXi AI Companion Platform',
      version: `Version ${VERSION.value}`,
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
      aiModelTitle: 'AI Model Setup',
      aiModelDesc: 'Configure your first AI model provider to get started',
      aiModelProvider: 'Provider',
      aiModelSelectProvider: 'Select a provider',
      aiModelApiUrl: 'API URL',
      aiModelApiKey: 'API Key',
      aiModelDefaultModel: 'Default Model',
      aiModelSetDefault: 'Set as default',
      aiModelAddProvider: 'Add Provider',
      aiModelNoProviders: 'No providers yet. Add one to get started.',
      aiModelSkipHint: 'You can configure models later in Settings',
      aiModelSaving: 'Adding...',
      aiModelAdd: 'Add & Next',
      aiModelNext: 'Next',
      aiModelCategoryCloud: 'Cloud API',
      aiModelCategoryLocal: 'Local',
      aiModelCategoryAggregator: 'Aggregator',
      readyTitle: 'All Set!',
      readyDesc: 'LuomiNest is ready to go. Let\'s start your journey.',
      btnNext: 'Next',
      btnStart: 'Get Started',
      btnBack: 'Back',
      agreeText: 'I agree to the terms and conditions',
      skip: 'Skip',
    }
  }
  return {
    title: '欢迎来到',
    appName: 'LuomiNest',
    subtitle: 'LuminousChenXi 辰汐 AI 伴侣平台',
    version: `版本 ${VERSION.value}`,
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
    aiModelTitle: 'AI 模型',
    aiModelDesc: '配置你的第一个 AI 模型供应商，开始对话',
    aiModelProvider: '供应商',
    aiModelSelectProvider: '选择供应商',
    aiModelApiUrl: 'API 地址',
    aiModelApiKey: 'API Key',
    aiModelDefaultModel: '默认模型',
    aiModelSetDefault: '设为默认',
    aiModelAddProvider: '添加供应商',
    aiModelNoProviders: '暂无供应商，添加一个即可开始',
    aiModelSkipHint: '可以稍后在设置中配置模型',
    aiModelSaving: '添加中...',
    aiModelAdd: '添加并继续',
    aiModelNext: '下一步',
    aiModelCategoryCloud: '云端 API',
    aiModelCategoryLocal: '本地推理',
    aiModelCategoryAggregator: '聚合网关',
    readyTitle: '准备就绪！',
    readyDesc: 'LuomiNest 已就绪，开启你的旅程吧。',
    btnNext: '下一步',
    btnStart: '开始使用',
    btnBack: '上一步',
    agreeText: '我已阅读并同意相关条款',
    skip: '跳过',
  }
})

const agreed = ref(false)

const features: Array<{
  icon: any
  color: string
  theme: string
  key: 'featAgent' | 'featWorkflow' | 'featBrowser' | 'featAvatar'
  keyDesc: 'featAgentDesc' | 'featWorkflowDesc' | 'featBrowserDesc' | 'featAvatarDesc'
}> = [
  { icon: Bot, color: '--lumi-indigo', theme: 'Bot', key: 'featAgent', keyDesc: 'featAgentDesc' },
  { icon: Zap, color: '--lumi-amber', theme: 'Zap', key: 'featWorkflow', keyDesc: 'featWorkflowDesc' },
  { icon: Globe, color: '--lumi-info', theme: 'Globe', key: 'featBrowser', keyDesc: 'featBrowserDesc' },
  { icon: Palette, color: '--task-pink', theme: 'Palette', key: 'featAvatar', keyDesc: 'featAvatarDesc' }
]

function nextStep() {
  if (currentStep.value < TOTAL_STEPS - 1) currentStep.value++
}

function prevStep() {
  if (currentStep.value > 0) currentStep.value--
}

function startApp() {
  router.push('/splash')
}

function skipWizard() {
  router.push('/splash')
}

// --- AI Model Step ---
const addTemplateCategory = ref('cloud')
const selectedTemplate = ref<string>('')
const aiModelSaving = ref(false)
const aiModelError = ref('')

const newProvider = ref({
  id: '',
  name: '',
  vendor: 'openai_compatible',
  baseUrl: '',
  apiKey: '',
  defaultModel: '',
  isDefault: true,
})

const templateCategories = computed(() => [
  { id: 'cloud', label: i18n.value.aiModelCategoryCloud, icon: Cloud },
  { id: 'local', label: i18n.value.aiModelCategoryLocal, icon: Monitor },
  { id: 'aggregator', label: i18n.value.aiModelCategoryAggregator, icon: Network },
])

const handleTemplateSelect = (templateId: string) => {
  selectedTemplate.value = templateId
  const tmpl = modelStore.allTemplates.find(t => t.id === templateId)
  if (tmpl) {
    newProvider.value.id = tmpl.id
    newProvider.value.name = tmpl.name
    newProvider.value.vendor = tmpl.vendor
    newProvider.value.baseUrl = tmpl.baseUrl
    newProvider.value.defaultModel = tmpl.defaultModel
    if (tmpl.vendor === 'ollama') {
      newProvider.value.apiKey = 'ollama'
    } else if (tmpl.id === 'lmstudio') {
      newProvider.value.apiKey = 'lmstudio'
    } else {
      newProvider.value.apiKey = ''
    }
  }
}

const newProviderFormValid = computed(() => {
  const hasId = newProvider.value.id.trim() !== ''
  const hasBaseUrl = newProvider.value.baseUrl.trim() !== ''
  const isCloudProvider = newProvider.value.vendor === 'openai_compatible'
  const hasApiKey = !isCloudProvider || newProvider.value.apiKey.trim() !== ''
  return hasId && hasBaseUrl && hasApiKey
})

const addProviderAndNext = async () => {
  if (!newProviderFormValid.value) {
    aiModelError.value = selectedLang.value === 'zh' ? '请填写必填项' : 'Please fill required fields'
    return
  }
  aiModelError.value = ''
  aiModelSaving.value = true
  try {
    await modelStore.addProvider({
      id: newProvider.value.id.trim(),
      name: newProvider.value.name.trim() || newProvider.value.id.trim(),
      vendor: newProvider.value.vendor,
      baseUrl: newProvider.value.baseUrl.trim(),
      apiKey: newProvider.value.apiKey,
      defaultModel: newProvider.value.defaultModel.trim(),
      isDefault: newProvider.value.isDefault,
    })
    nextStep()
  } catch (e: any) {
    aiModelError.value = e.message || (selectedLang.value === 'zh' ? '添加失败' : 'Failed to add')
  } finally {
    aiModelSaving.value = false
  }
}

onMounted(async () => {
  try {
    VERSION.value = await window.api?.app?.getVersion() || ''
  } catch {}
  modelStore.fetchProviders().catch(() => {})
  modelStore.fetchTemplates().catch(() => {})
  modelStore.fetchModelConfig().catch(() => {})
})
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
        <!-- Step 0: Language -->
        <div v-if="currentStep === 0" key="step-0" class="welcome-step step-lang">
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
            <LumiButton variant="primary" size="lg" block @click="nextStep">
              <span>{{ i18n.btnNext }}</span>
              <ChevronRight :size="16" />
            </LumiButton>
          </div>
        </div>

        <!-- Step 1: Features -->
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
            <LumiButton variant="ghost" size="lg" @click="prevStep">
              {{ i18n.btnBack }}
            </LumiButton>
            <LumiButton variant="primary" size="lg" block @click="nextStep">
              <span>{{ i18n.btnNext }}</span>
              <ChevronRight :size="16" />
            </LumiButton>
          </div>
        </div>

        <!-- Step 2: AI Model -->
        <div v-else-if="currentStep === 2" key="step-2" class="welcome-step step-ai-model">
          <div class="step-hero animate-fade-in">
            <div class="step-hero-icon ai-hero-icon">
              <Cpu :size="24" />
            </div>
            <div>
              <h2 class="step-hero-title">{{ i18n.aiModelTitle }}</h2>
              <p class="step-hero-desc">{{ i18n.aiModelDesc }}</p>
            </div>
          </div>

          <div class="ai-model-form animate-slide-up">
            <div v-if="aiModelError" class="form-error-banner">
              <AlertCircle :size="14" />
              <span>{{ aiModelError }}</span>
            </div>

            <div class="category-tabs">
              <button
                v-for="cat in templateCategories"
                :key="cat.id"
                :class="['category-tab', { active: addTemplateCategory === cat.id }]"
                @click="addTemplateCategory = cat.id"
              >
                <component :is="cat.icon" :size="14" />
                <span>{{ cat.label }}</span>
              </button>
            </div>

            <div class="template-scroll">
              <LumiEmptyState
                v-if="!(modelStore.templatesByCategory[addTemplateCategory] || []).length"
                icon="inbox"
                :title="i18n.aiModelNoProviders"
              />
              <button
                v-for="tmpl in (modelStore.templatesByCategory[addTemplateCategory] || [])"
                :key="tmpl.id"
                :class="['template-card', { selected: selectedTemplate === tmpl.id }]"
                @click="handleTemplateSelect(tmpl.id)"
              >
                <div class="lumi-icon-wrap lumi-icon-wrap--sm template-card-logo" :style="{ background: tmpl.color }">
                  <span class="template-initials">{{ tmpl.initials }}</span>
                </div>
                <div class="template-card-info">
                  <span class="template-card-name">{{ tmpl.name }}</span>
                  <span class="template-card-desc">{{ tmpl.description }}</span>
                </div>
                <Check v-if="selectedTemplate === tmpl.id" :size="16" class="template-card-check" />
              </button>
            </div>

            <div v-if="selectedTemplate" class="provider-config">
              <div class="form-group">
                <label>{{ i18n.aiModelApiUrl }}</label>
                <LumiInput v-model="newProvider.baseUrl" type="text" placeholder="https://api.openai.com/v1" />
              </div>
              <div class="form-group">
                <label>{{ i18n.aiModelApiKey }}</label>
                <LumiInput v-model="newProvider.apiKey" type="password" placeholder="sk-..." />
              </div>
              <div class="form-group">
                <label>{{ i18n.aiModelDefaultModel }}</label>
                <LumiInput v-model="newProvider.defaultModel" type="text" placeholder="gpt-4o-mini" />
              </div>
            </div>

            <p class="skip-hint">{{ i18n.aiModelSkipHint }}</p>
          </div>

          <div class="step-actions">
            <LumiButton variant="ghost" size="lg" @click="prevStep">
              {{ i18n.btnBack }}
            </LumiButton>
            <LumiButton
              v-if="selectedTemplate && newProviderFormValid"
              variant="primary"
              size="lg"
              block
              :loading="aiModelSaving"
              @click="addProviderAndNext"
            >
              <span>{{ aiModelSaving ? i18n.aiModelSaving : i18n.aiModelAdd }}</span>
              <ChevronRight v-if="!aiModelSaving" :size="16" />
            </LumiButton>
            <LumiButton v-else variant="primary" size="lg" block @click="nextStep">
              <span>{{ i18n.aiModelNext }}</span>
              <ChevronRight :size="16" />
            </LumiButton>
          </div>
        </div>

        <!-- Step 3: Ready -->
        <div v-else-if="currentStep === 3" key="step-3" class="welcome-step step-ready">
          <div class="ready-hero animate-scale-in">
            <div class="ready-ring">
              <LumiBrandStar :size="64" />
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
            <LumiButton variant="ghost" size="lg" @click="prevStep">
              {{ i18n.btnBack }}
            </LumiButton>
            <LumiButton class="launch-btn" variant="primary" size="lg" block :disabled="!agreed" @click="startApp">
              <span>{{ i18n.btnStart }}</span>
              <ArrowRight :size="16" />
            </LumiButton>
          </div>
        </div>
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

@keyframes orb-float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(20px, -15px) scale(1.05); }
  66% { transform: translate(-10px, 10px) scale(0.97); }
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

/* Step Hero (Profile & AI Model) */
.step-hero {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  width: 100%;
}

.step-hero-icon {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ai-hero-icon {
  background: linear-gradient(135deg, var(--task-purple-soft), color-mix(in srgb, var(--task-purple) 4%, transparent));
  color: var(--task-purple);
}

.step-hero-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text);
}

.step-hero-desc {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
  line-height: var(--leading-normal);
}

/* AI Model Form */
.ai-model-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.form-error-banner {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}

.category-tabs {
  display: flex;
  gap: var(--space-1);
}

.category-tab {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  background: var(--surface);
  border: 1px solid var(--border);
  transition: all var(--transition-normal);
  cursor: pointer;
}

.category-tab:hover {
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
}

.category-tab.active {
  background: var(--lumi-brand-light);
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
  font-weight: var(--font-semibold);
}

.template-scroll {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-height: 200px;
  overflow-y: auto;
  padding-right: var(--space-1);
}

.template-card {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border);
  transition: all var(--transition-normal);
  cursor: pointer;
  text-align: left;
  width: 100%;
}

.template-card:hover {
  border-color: var(--lumi-brand-border);
  box-shadow: var(--shadow-sm);
}

.template-card.selected {
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

.template-card-logo {
  flex-shrink: 0;
}

.template-initials {
  font-size: var(--text-2xs);
  font-weight: var(--font-bold);
  color: var(--text-inverse);
  letter-spacing: 0.5px;
}

.template-card-info {
  display: flex;
  flex-direction: column;
  gap: calc(var(--space-1) / 4);
  flex: 1;
  min-width: 0;
}

.template-card-name {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.template-card-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-card-check {
  color: var(--lumi-brand);
  flex-shrink: 0;
}

.provider-config {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-lg);
  background: var(--surface);
  border: 1px solid var(--border);
}

/* Ready Step */
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

@keyframes brand-enter {
  0% { opacity: 0; transform: translateY(30px) scale(0.94); filter: blur(4px); }
  100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
}

.animate-brand-enter {
  animation: brand-enter var(--duration-enter) var(--ease-out-expo) both;
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
