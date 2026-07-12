/**
 * LuomiNest 欢迎向导状态
 *
 * 从 WelcomeView.vue 拆分：收纳步骤导航、i18n 文案、AI 模型供应商配置逻辑。
 * 静态数据（FEATURES / i18n 常量）以命名导出供子组件直接 import。
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Bot, Zap, Globe, Palette } from 'lucide-vue-next'
import { useModelStore } from '../stores/model'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('Welcome')

// ===== 类型定义 =====

export type TemplateCategory = 'cloud' | 'local' | 'aggregator'

export type LangCode = 'zh' | 'en'

export interface NewProvider {
  id: string
  name: string
  vendor: string
  baseUrl: string
  apiKey: string
  defaultModel: string
  isDefault: boolean
}

export interface FeatureItem {
  icon: typeof Bot
  color: string
  theme: string
  key: 'featAgent' | 'featWorkflow' | 'featBrowser' | 'featAvatar'
  keyDesc: 'featAgentDesc' | 'featWorkflowDesc' | 'featBrowserDesc' | 'featAvatarDesc'
}

export interface WelcomeI18nText {
  title: string
  appName: string
  subtitle: string
  version: string
  langTitle: string
  langZh: string
  langEn: string
  featureTitle: string
  featAgent: string
  featAgentDesc: string
  featWorkflow: string
  featWorkflowDesc: string
  featBrowser: string
  featBrowserDesc: string
  featAvatar: string
  featAvatarDesc: string
  aiModelTitle: string
  aiModelDesc: string
  aiModelProvider: string
  aiModelSelectProvider: string
  aiModelApiUrl: string
  aiModelApiKey: string
  aiModelDefaultModel: string
  aiModelSetDefault: string
  aiModelAddProvider: string
  aiModelNoProviders: string
  aiModelSkipHint: string
  aiModelSaving: string
  aiModelAdd: string
  aiModelNext: string
  aiModelCategoryCloud: string
  aiModelCategoryLocal: string
  aiModelCategoryAggregator: string
  readyTitle: string
  readyDesc: string
  btnNext: string
  btnStart: string
  btnBack: string
  agreeText: string
  skip: string
}

// ===== 静态数据 =====

export const TOTAL_STEPS = 4

export const FEATURES: FeatureItem[] = [
  { icon: Bot, color: '--lumi-indigo', theme: 'Bot', key: 'featAgent', keyDesc: 'featAgentDesc' },
  { icon: Zap, color: '--lumi-amber', theme: 'Zap', key: 'featWorkflow', keyDesc: 'featWorkflowDesc' },
  { icon: Globe, color: '--lumi-info', theme: 'Globe', key: 'featBrowser', keyDesc: 'featBrowserDesc' },
  { icon: Palette, color: '--task-pink', theme: 'Palette', key: 'featAvatar', keyDesc: 'featAvatarDesc' }
]

// ===== i18n 文案常量（不含 version，运行时拼合） =====

const I18N_ZH: Omit<WelcomeI18nText, 'version'> = {
  title: '欢迎来到',
  appName: 'LuomiNest',
  subtitle: 'LuminousChenXi 辰汐 AI 伴侣平台',
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

const I18N_EN: Omit<WelcomeI18nText, 'version'> = {
  title: 'Welcome to',
  appName: 'LuomiNest',
  subtitle: 'LuminousChenXi AI Companion Platform',
  langTitle: 'Select Language',
  langZh: '中文',
  langEn: 'English',
  featureTitle: "What's Inside",
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
  readyDesc: "LuomiNest is ready to go. Let's start your journey.",
  btnNext: 'Next',
  btnStart: 'Get Started',
  btnBack: 'Back',
  agreeText: 'I agree to the terms and conditions',
  skip: 'Skip',
}

// ===== composable =====

export const useWelcomeWizard = () => {
  const router = useRouter()
  const modelStore = useModelStore()

  const VERSION = ref('')
  const currentStep = ref(0)
  const selectedLang = ref<LangCode>('zh')
  const agreed = ref(false)

  const i18n = computed<WelcomeI18nText>(() => {
    const base = selectedLang.value === 'en' ? I18N_EN : I18N_ZH
    const version = selectedLang.value === 'en' ? `Version ${VERSION.value}` : `版本 ${VERSION.value}`
    return { ...base, version }
  })

  // --- 步骤导航 ---
  const nextStep = (): void => {
    if (currentStep.value < TOTAL_STEPS - 1) currentStep.value++
  }

  const prevStep = (): void => {
    if (currentStep.value > 0) currentStep.value--
  }

  const startApp = (): void => {
    router.push('/splash')
  }

  const skipWizard = (): void => {
    router.push('/splash')
  }

  // --- AI Model Step ---
  const addTemplateCategory = ref<TemplateCategory>('cloud')
  const selectedTemplate = ref<string>('')
  const aiModelSaving = ref(false)
  const aiModelError = ref('')

  const newProvider = reactive<NewProvider>({
    id: '',
    name: '',
    vendor: 'openai_compatible',
    baseUrl: '',
    apiKey: '',
    defaultModel: '',
    isDefault: true,
  })

  const handleTemplateSelect = (templateId: string): void => {
    selectedTemplate.value = templateId
    const tmpl = modelStore.allTemplates.find(t => t.id === templateId)
    if (tmpl) {
      newProvider.id = tmpl.id
      newProvider.name = tmpl.name
      newProvider.vendor = tmpl.vendor
      newProvider.baseUrl = tmpl.baseUrl
      newProvider.defaultModel = tmpl.defaultModel
      if (tmpl.vendor === 'ollama') {
        newProvider.apiKey = 'ollama'
      } else if (tmpl.id === 'lmstudio') {
        newProvider.apiKey = 'lmstudio'
      } else {
        newProvider.apiKey = ''
      }
    }
  }

  const newProviderFormValid = computed<boolean>(() => {
    const hasId = newProvider.id.trim() !== ''
    const hasBaseUrl = newProvider.baseUrl.trim() !== ''
    const isCloudProvider = newProvider.vendor === 'openai_compatible'
    const hasApiKey = !isCloudProvider || newProvider.apiKey.trim() !== ''
    return hasId && hasBaseUrl && hasApiKey
  })

  const addProviderAndNext = async (): Promise<void> => {
    if (!newProviderFormValid.value) {
      aiModelError.value = selectedLang.value === 'zh' ? '请填写必填项' : 'Please fill required fields'
      return
    }
    aiModelError.value = ''
    aiModelSaving.value = true
    try {
      await modelStore.addProvider({
        id: newProvider.id.trim(),
        name: newProvider.name.trim() || newProvider.id.trim(),
        vendor: newProvider.vendor,
        baseUrl: newProvider.baseUrl.trim(),
        apiKey: newProvider.apiKey,
        defaultModel: newProvider.defaultModel.trim(),
        isDefault: newProvider.isDefault,
      })
      nextStep()
    } catch (e: unknown) {
      logger.error('Failed to add provider:', e)
      const fallback = selectedLang.value === 'zh' ? '添加失败' : 'Failed to add'
      aiModelError.value = (e instanceof Error && e.message) ? e.message : fallback
    } finally {
      aiModelSaving.value = false
    }
  }

  onMounted(async () => {
    try {
      VERSION.value = await window.api?.app?.getVersion() || ''
    } catch (e: unknown) {
      logger.warn('Failed to get app version:', e)
    }
    modelStore.fetchProviders().catch((e: unknown) => logger.warn('fetchProviders failed:', e))
    modelStore.fetchTemplates().catch((e: unknown) => logger.warn('fetchTemplates failed:', e))
    modelStore.fetchModelConfig().catch((e: unknown) => logger.warn('fetchModelConfig failed:', e))
  })

  return {
    VERSION,
    currentStep,
    selectedLang,
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
  }
}
