/**
 * LuomiNest 智能体创建向导表单状态
 *
 * 从 AgentCreateView.vue 拆分：收纳表单状态、静态配置数据、步骤导航逻辑、
 * 创建提交逻辑。静态数据（avatarOptions/skillItems 等）以命名导出供子组件直接 import。
 */
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  FileText, Brain, Terminal, Presentation,
  FileSpreadsheet, FileCode
} from 'lucide-vue-next'
import { useAgentStore } from '../stores/agent'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('AgentCreate')

// ===== 静态配置数据（子组件直接 import 使用） =====

export interface AvatarOption {
  id: string
  emoji: string
  color: string
}

export const STEP_TITLES = ['身份与模型', '技能配置', '高级设置', '确认创建']
export const STEP_SUBTITLES = ['定义智能体基础信息', '选择并配置能力模块', '调整行为参数', '预览并完成创建']
export const TOTAL_STEPS = 4

export const AVATAR_CATEGORIES = [
  { id: 'classic', label: '经典' },
  { id: 'cute', label: '萌系' },
  { id: 'tech', label: '科技' },
  { id: 'artistic', label: '艺术' }
]

export const AVATAR_OPTIONS: Record<string, AvatarOption[]> = {
  classic: [
    { id: 'c1', emoji: '\u{1F9D4}', color: 'var(--lumi-brand)' },
    { id: 'c2', emoji: '\u{1F9D3}', color: 'var(--lumi-info)' },
    { id: 'c3', emoji: '\u{1F9D1}\u200D\u{1F52C}', color: 'var(--task-purple)' }
  ],
  cute: [
    { id: 'cu1', emoji: '\u{1F978}', color: 'var(--lumi-success)' },
    { id: 'cu2', emoji: '\u{1F4A1}', color: 'var(--lumi-warning)' },
    { id: 'cu3', emoji: '\u{1F389}', color: 'var(--lumi-accent)' }
  ],
  tech: [
    { id: 't1', emoji: '\u{1F916}', color: 'var(--lumi-sky)' },
    { id: 't2', emoji: '\u{1F6E0}\uFE0F', color: 'var(--lumi-indigo)' },
    { id: 't3', emoji: '\u{26A1}', color: 'var(--lumi-amber)' }
  ],
  artistic: [
    { id: 'a1', emoji: '\u{1F3A8}', color: 'var(--task-pink)' },
    { id: 'a2', emoji: '\u{1F3B8}', color: 'var(--task-purple)' },
    { id: 'a3', emoji: '\u{2728}', color: 'var(--lumi-brand-soft)' }
  ]
}

export const STYLE_TAGS = [
  { id: 'professional', label: '专业' },
  { id: 'friendly', label: '友好' },
  { id: 'creative', label: '创意' },
  { id: 'concise', label: '简洁' },
  { id: 'casual', label: '随意' },
  { id: 'expert', label: '专家' }
]

export const MODEL_OPTIONS = [
  { id: 'auto', label: '自动' },
  { id: 'gpt4o', label: 'GPT-4o' },
  { id: 'claude', label: 'Claude' },
  { id: 'gemini', label: 'Gemini' }
]

export interface SkillItem {
  id: string
  name: string
  desc: string
  icon: typeof FileText
  defaultEnabled: boolean
}

export const SKILL_ITEMS: SkillItem[] = [
  {
    id: 'skill-search',
    name: '技能查找器',
    desc: '通过关键词搜索内置目录库，快速定位所需能力模块',
    icon: FileText,
    defaultEnabled: true
  },
  {
    id: 'skill-builder',
    name: '技能创建器',
    desc: '创建、修改、评估和优化智能体技能，支持结构化的 SKILL.md 编写',
    icon: FileCode,
    defaultEnabled: true
  },
  {
    id: 'self-learning',
    name: '智能体自我学习',
    desc: '将学习成果、错误和反思记录到每日日志中，持续提升推理与决策能力',
    icon: Brain,
    defaultEnabled: true
  },
  {
    id: 'mcp-tools',
    name: 'MCP 工具 (CLI)',
    desc: '通过 accio-mcp-cli 命令行发现和调用 MCP 工具（Notion、Square、Apify 等）',
    icon: Terminal,
    defaultEnabled: true
  },
  {
    id: 'powerpoint',
    name: 'PowerPoint',
    desc: '为供应商评审、数据汇总和战略提案生成 PowerPoint 演示文稿',
    icon: Presentation,
    defaultEnabled: false
  },
  {
    id: 'pdf',
    name: 'PDF',
    desc: '生成或解析 PDF 文档，从合同中提取关键条款及商业合规分析',
    icon: FileText,
    defaultEnabled: false
  },
  {
    id: 'word',
    name: 'Word 文档',
    desc: '创建和编辑 Word 文档，包括询价函（RFQ）、SOP 及合同模板',
    icon: FileText,
    defaultEnabled: false
  },
  {
    id: 'xlsx',
    name: 'Excel 表格',
    desc: '创建、编辑、分析和可视化 Excel 电子表格，支持公式与图表',
    icon: FileSpreadsheet,
    defaultEnabled: false
  }
]

// ===== 表单状态与逻辑 =====

export interface AgentFormData {
  name: string
  description: string
  selectedAvatarId: string
  selectedStyle: string
  selectedModel: string
  skills: Record<string, boolean>
  temperature: number
  maxTokens: number
  systemPrompt: string
}

export const useAgentCreateForm = () => {
  const router = useRouter()
  const agentStore = useAgentStore()

  const currentStep = ref(0)
  const activeAvatarCategory = ref('classic')
  const errorMessage = ref('')

  const formData = reactive<AgentFormData>({
    name: '',
    description: '',
    selectedAvatarId: 'c1',
    selectedStyle: 'professional',
    selectedModel: 'auto',
    skills: {} as Record<string, boolean>,
    temperature: 0.7,
    maxTokens: 4096,
    systemPrompt: ''
  })

  // 初始化技能默认启用状态
  SKILL_ITEMS.forEach(skill => {
    formData.skills[skill.id] = skill.defaultEnabled
  })

  const allAvatars = computed(() => Object.values(AVATAR_OPTIONS).flat())
  const selectedAvatar = computed<AvatarOption>(() =>
    allAvatars.value.find(a => a.id === formData.selectedAvatarId) || allAvatars.value[0]
  )
  const currentAvatars = computed<AvatarOption[]>(() =>
    AVATAR_OPTIONS[activeAvatarCategory.value] || []
  )
  const enabledSkillsCount = computed<number>(() =>
    Object.values(formData.skills).filter(v => v).length
  )

  const canGoNext = computed<boolean>(() => {
    switch (currentStep.value) {
      case 0: return formData.name.trim().length > 0
      case 1: return true
      case 2: return true
      case 3: return true
      default: return false
    }
  })

  const selectAvatar = (avatarId: string): void => {
    formData.selectedAvatarId = avatarId
  }

  const toggleStyle = (styleId: string): void => {
    formData.selectedStyle = styleId
  }

  const toggleSkill = (skillId: string): void => {
    formData.skills[skillId] = !formData.skills[skillId]
  }

  const goNext = async (): Promise<void> => {
    if (currentStep.value < TOTAL_STEPS - 1) {
      currentStep.value++
    } else {
      await handleCreateAgent()
    }
  }

  const goPrev = (): void => {
    if (currentStep.value > 0) {
      currentStep.value--
    }
  }

  const handleClose = (): void => {
    router.push('/workspace')
  }

  const handleCreateAgent = async (): Promise<void> => {
    errorMessage.value = ''
    try {
      const capabilities = Object.entries(formData.skills)
        .filter(([, enabled]) => enabled)
        .map(([id]) => id)

      await agentStore.createAgent({
        name: formData.name,
        description: formData.description,
        systemPrompt: formData.systemPrompt,
        model: formData.selectedModel === 'auto' ? undefined : formData.selectedModel,
        color: selectedAvatar.value.color,
        capabilities: capabilities.length > 0 ? capabilities : ['chat']
      })
      router.push('/workspace')
    } catch (err: unknown) {
      logger.error('Failed to create agent:', err)
      // 兼容 axios 错误（response.data.detail）与普通 Error
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      const fallback = err instanceof Error ? err.message : '创建失败'
      errorMessage.value = axiosErr?.response?.data?.detail || fallback
    }
  }

  return {
    currentStep,
    activeAvatarCategory,
    errorMessage,
    formData,
    selectedAvatar,
    currentAvatars,
    enabledSkillsCount,
    canGoNext,
    selectAvatar,
    toggleStyle,
    toggleSkill,
    goNext,
    goPrev,
    handleClose,
    handleCreateAgent,
  }
}
