/**
 * LuomiNest 欢迎向导状态
 *
 * 从 WelcomeView.vue 拆分：收纳步骤导航、i18n 文案、AI 模型供应商配置逻辑。
 * 静态数据（FEATURES）以命名导出供子组件直接 import。
 *
 * 文案走全局 vue-i18n（stores/locale.ts 持久化语言选择），
 * 这里把 welcome.* 的 key 映射为 WelcomeI18nText 结构传给各步骤组件。
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Bot, Zap, Globe, Palette } from 'lucide-vue-next'
import { useModelStore } from '../stores/model'
import { useLocaleStore } from '../stores/locale'
import { useApi } from './useApi'
import type { AppLocale } from '../i18n'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('Welcome')

// ===== 类型定义 =====

export type TemplateCategory = 'cloud' | 'local' | 'aggregator'

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
  langJa: string
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
  aiModelApiUrl: string
  aiModelApiKey: string
  aiModelDefaultModel: string
  aiModelNoProviders: string
  aiModelSkipHint: string
  aiModelSaving: string
  aiModelAdd: string
  aiModelNext: string
  aiModelCategoryCloud: string
  aiModelCategoryLocal: string
  aiModelCategoryAggregator: string
  testBtn: string
  testTesting: string
  readyTitle: string
  readyDesc: string
  btnNext: string
  btnStart: string
  btnBack: string
  skip: string
}

export interface WizardCurrentUser {
  user_id: string
  username: string
  display_name: string | null
}

// ===== 静态数据 =====

export const TOTAL_STEPS = 5

export const FEATURES: FeatureItem[] = [
  { icon: Bot, color: '--lumi-indigo', theme: 'Bot', key: 'featAgent', keyDesc: 'featAgentDesc' },
  { icon: Zap, color: '--lumi-amber', theme: 'Zap', key: 'featWorkflow', keyDesc: 'featWorkflowDesc' },
  { icon: Globe, color: '--lumi-info', theme: 'Globe', key: 'featBrowser', keyDesc: 'featBrowserDesc' },
  { icon: Palette, color: '--task-pink', theme: 'Palette', key: 'featAvatar', keyDesc: 'featAvatarDesc' }
]

// ===== composable =====

export const useWelcomeWizard = () => {
  const router = useRouter()
  const modelStore = useModelStore()
  const localeStore = useLocaleStore()
  const { t } = useI18n()
  const { apiGet, apiPost } = useApi()

  const VERSION = ref('')
  const currentStep = ref(0)
  const agreed = ref(false)

  /** 当前语言 = 全局 locale store（向导第 0 步的选择即全局切换） */
  const selectedLang = computed<AppLocale>(() => localeStore.locale)

  const selectLang = (lang: AppLocale): void => {
    localeStore.setLocale(lang)
  }

  const i18n = computed<WelcomeI18nText>(() => ({
    title: t('welcome.title'),
    appName: 'LuomiNest',
    subtitle: t('welcome.subtitle'),
    version: t('welcome.version', { version: VERSION.value }),
    langTitle: t('welcome.langTitle'),
    langZh: t('welcome.langZh'),
    langEn: t('welcome.langEn'),
    langJa: t('welcome.langJa'),
    featureTitle: t('welcome.featureTitle'),
    featAgent: t('welcome.featAgent'),
    featAgentDesc: t('welcome.featAgentDesc'),
    featWorkflow: t('welcome.featWorkflow'),
    featWorkflowDesc: t('welcome.featWorkflowDesc'),
    featBrowser: t('welcome.featBrowser'),
    featBrowserDesc: t('welcome.featBrowserDesc'),
    featAvatar: t('welcome.featAvatar'),
    featAvatarDesc: t('welcome.featAvatarDesc'),
    aiModelTitle: t('welcome.aiModelTitle'),
    aiModelDesc: t('welcome.aiModelDesc'),
    aiModelApiUrl: t('welcome.aiModelApiUrl'),
    aiModelApiKey: t('welcome.aiModelApiKey'),
    aiModelDefaultModel: t('welcome.aiModelDefaultModel'),
    aiModelNoProviders: t('welcome.aiModelNoProviders'),
    aiModelSkipHint: t('welcome.aiModelSkipHint'),
    aiModelSaving: t('welcome.aiModelSaving'),
    aiModelAdd: t('welcome.aiModelAdd'),
    aiModelNext: t('welcome.aiModelNext'),
    aiModelCategoryCloud: t('welcome.aiModelCategoryCloud'),
    aiModelCategoryLocal: t('welcome.aiModelCategoryLocal'),
    aiModelCategoryAggregator: t('welcome.aiModelCategoryAggregator'),
    testBtn: t('welcome.testBtn'),
    testTesting: t('welcome.testTesting'),
    readyTitle: t('welcome.readyTitle'),
    readyDesc: t('welcome.readyDesc'),
    btnNext: t('welcome.btnNext'),
    btnStart: t('welcome.btnStart'),
    btnBack: t('welcome.btnBack'),
    skip: t('common.skip'),
  }))

  // --- 步骤导航 ---
  const nextStep = (): void => {
    if (currentStep.value < TOTAL_STEPS - 1) currentStep.value++
  }

  const prevStep = (): void => {
    if (currentStep.value > 0) currentStep.value--
  }

  /**
   * 标记欢迎向导已完成并跳转到 splash。
   * 持久化到主进程 config，使后续启动直接跳过欢迎页。
   */
  const completeAndEnterApp = async (): Promise<void> => {
    try {
      await window.api?.app?.setWelcomeCompleted?.(true)
    } catch (e: unknown) {
      logger.warn('Failed to persist welcomeCompleted:', e)
    }
    // 刷新路由缓存，避免本次会话再次被 beforeEach 重定向
    const invalidate = (window as unknown as { __lumiInvalidateWelcome?: () => void }).__lumiInvalidateWelcome
    if (typeof invalidate === 'function') invalidate()
    router.push('/splash')
  }

  const startApp = (): void => {
    completeAndEnterApp()
  }

  const skipWizard = (): void => {
    completeAndEnterApp()
  }

  // --- AI Model Step ---
  const addTemplateCategory = ref<TemplateCategory>('cloud')
  const selectedTemplate = ref<string>('')
  const aiModelSaving = ref(false)
  const aiModelError = ref('')

  // --- 连通性测试（testProvider，向导内即可发现填错的 key/地址） ---
  const testState = ref<'idle' | 'testing' | 'ok' | 'fail'>('idle')
  const testResultText = ref('')

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
    testState.value = 'idle'
    testResultText.value = ''
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
      aiModelError.value = t('welcome.errorRequired')
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
      const fallback = t('welcome.errorAdd')
      aiModelError.value = (e instanceof Error && e.message) ? e.message : fallback
    } finally {
      aiModelSaving.value = false
    }
  }

  /**
   * 测试所选供应商连通性（不落库，仅用表单当前值探测）。
   */
  const testConnection = async (): Promise<void> => {
    if (testState.value === 'testing') return
    testState.value = 'testing'
    testResultText.value = ''
    try {
      const result = await modelStore.testProvider({
        vendor: newProvider.vendor,
        baseUrl: newProvider.baseUrl.trim(),
        apiKey: newProvider.apiKey,
        defaultModel: newProvider.defaultModel.trim(),
      })
      if (result.success) {
        testState.value = 'ok'
        testResultText.value = t('welcome.testOk', { count: result.models.length })
      } else {
        testState.value = 'fail'
        testResultText.value = result.error || t('welcome.testFail')
      }
    } catch (e: unknown) {
      testState.value = 'fail'
      testResultText.value = (e instanceof Error && e.message) ? e.message : t('welcome.testFail')
    }
  }

  // --- Account Step ---
  // 与 SettingsLoginSection.vue 共用同一组 localStorage key，保证两处登录态互通
  const JWT_ACCESS_TOKEN_KEY = 'lumi_jwt_access_token'
  const JWT_REFRESH_TOKEN_KEY = 'lumi_jwt_refresh_token'

  const accountSubmitting = ref(false)
  const accountError = ref('')
  /** null=检测中，false=未登录（显示创建表单），true 伴随 currentUser=已登录（显示账户卡） */
  const hasAccount = ref<boolean | null>(null)
  const currentUser = ref<WizardCurrentUser | null>(null)

  const accountForm = reactive({
    username: '',
    displayName: '',
    password: '',
    confirmPassword: '',
  })

  const accountFormValid = computed<boolean>(() => {
    const u = accountForm.username.trim().length >= 3
    const p = accountForm.password.length >= 6
    const cp = accountForm.password === accountForm.confirmPassword
    return u && p && cp
  })

  const checkExistingAccount = async (): Promise<void> => {
    const token = localStorage.getItem(JWT_ACCESS_TOKEN_KEY)
    if (!token) {
      hasAccount.value = false
      return
    }
    try {
      currentUser.value = await apiGet<WizardCurrentUser>('/auth/me')
      hasAccount.value = true
    } catch {
      localStorage.removeItem(JWT_ACCESS_TOKEN_KEY)
      localStorage.removeItem(JWT_REFRESH_TOKEN_KEY)
      hasAccount.value = false
    }
  }

  /**
   * 创建本地账户并自动登录（POST /auth/register → /auth/login），
   * JWT 存 localStorage 后进入下一步。
   */
  const registerAndNext = async (): Promise<void> => {
    if (!accountFormValid.value || accountSubmitting.value) return
    accountSubmitting.value = true
    accountError.value = ''
    try {
      await apiPost('/auth/register', {
        username: accountForm.username.trim(),
        password: accountForm.password,
        display_name: accountForm.displayName.trim() || null,
      })
      const resp = await apiPost<{ access_token: string; refresh_token: string }>('/auth/login', {
        username: accountForm.username.trim(),
        password: accountForm.password,
      })
      localStorage.setItem(JWT_ACCESS_TOKEN_KEY, resp.access_token)
      if (resp.refresh_token) localStorage.setItem(JWT_REFRESH_TOKEN_KEY, resp.refresh_token)
      nextStep()
    } catch (e: unknown) {
      logger.warn('Wizard register failed:', e)
      accountError.value = (e instanceof Error && e.message) ? e.message : t('welcome.accountErrorFallback')
    } finally {
      accountSubmitting.value = false
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
    checkExistingAccount().catch((e: unknown) => logger.warn('checkExistingAccount failed:', e))
  })

  return {
    VERSION,
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
    testState,
    testResultText,
    testConnection,
    accountSubmitting,
    accountError,
    hasAccount,
    currentUser,
    accountForm,
    accountFormValid,
    registerAndNext,
    nextStep,
    prevStep,
    startApp,
    skipWizard,
  }
}
