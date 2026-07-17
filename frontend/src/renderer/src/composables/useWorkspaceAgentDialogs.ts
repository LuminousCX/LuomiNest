/**
 * LuomiNest 工作台 Agent 增删改对话框 + 确认对话框
 *
 * 从 WorkspaceView.vue 拆分：收纳 create/edit/delete agent 与通用 confirm dialog 的状态与方法。
 * 跨关注的副作用（删除 Agent 后清空联系人选择）通过 onAgentDeleted 回调交回视图处理，
 * 保持 composable 与联系人选择状态解耦。
 *
 * 头像模式：支持「颜色」（自由切换图标颜色）和「预设头像」（固定 PNG 图片，不支持换色）两种模式。
 */
import { ref } from 'vue'
import type { AgentProfile } from '../types'
import { useAgentStore } from '../stores/agent'
import { useToast } from './useToast'

/** Agent 配色盘（创建/编辑对话框使用） */
const AGENT_COLORS: string[] = [
  'var(--lumi-brand)',
  'var(--lumi-indigo)',
  'var(--lumi-amber)',
  'var(--lumi-accent)',
  'var(--task-purple)',
  'var(--lumi-sky)',
  'var(--lumi-success)',
  'var(--task-pink)',
]

/** 预设智能体默认头像，PNG 文件存放在 public/png/agents/，通过 luominest-avatar:// 协议访问 */
export interface PresetAvatar {
  id: string
  name: string
  url: string
}
export const PRESET_AGENT_AVATARS: PresetAvatar[] = [
  { id: 'pa1', name: '编程助手', url: 'luominest-avatar://png/agents/programming-assistant.png' },
  { id: 'pa2', name: '信息研究员', url: 'luominest-avatar://png/agents/info-researcher.png' },
  { id: 'pa3', name: '灵感助手', url: 'luominest-avatar://png/agents/inspiration-assistant.png' },
  { id: 'pa4', name: '任务规划师', url: 'luominest-avatar://png/agents/task-planner.png' },
  { id: 'pa5', name: '心理专家', url: 'luominest-avatar://png/agents/psychology-expert.png' },
  { id: 'pa6', name: '信息搜集员', url: 'luominest-avatar://png/agents/info-collector.png' },
  { id: 'pa7', name: '学习帮手', url: 'luominest-avatar://png/agents/learning-helper.png' },
  { id: 'pa8', name: '日常助手', url: 'luominest-avatar://png/agents/daily-assistant.png' },
]

/** 从 unknown 错误中提取友好信息 */
const extractErrorMessage = (e: unknown, fallback: string): string => {
  const err = e as { response?: { data?: { detail?: string } }; message?: string }
  return err.response?.data?.detail || err.message || fallback
}

interface AgentFormState {
  name: string
  description: string
  systemPrompt: string
  color: string
  /** 头像模式：'color' 自由切换颜色 | 'preset' 固定预设 PNG */
  avatarMode: 'color' | 'preset'
  /** 预设头像 URL（avatarMode === 'preset' 时生效） */
  avatarUrl: string
}

const createEmptyForm = (): AgentFormState => {
  const randomAvatar = PRESET_AGENT_AVATARS[Math.floor(Math.random() * PRESET_AGENT_AVATARS.length)]
  return {
    name: '',
    description: '',
    systemPrompt: '',
    color: 'var(--lumi-brand)',
    avatarMode: 'preset',
    avatarUrl: randomAvatar.url,
  }
}

export interface UseWorkspaceAgentDialogsOptions {
  /** 删除 Agent 成功后回调（视图据此清空联系人选择） */
  onAgentDeleted: (deletedId: string) => void
}

export const useWorkspaceAgentDialogs = (options: UseWorkspaceAgentDialogsOptions) => {
  const agentStore = useAgentStore()
  const toast = useToast()

  // —— 创建 Agent 对话框 ——
  const showCreateDialog = ref(false)
  const newAgentForm = ref<AgentFormState>(createEmptyForm())
  const createDialogError = ref('')

  // —— 通用确认对话框 ——
  const showConfirmDialog = ref(false)
  const confirmDialogMessage = ref('')
  const confirmDialogCallback = ref<(() => void) | null>(null)
  const confirmDialogIsDanger = ref(false)

  const openConfirmDialog = (message: string, callback: () => void, isDanger = false): void => {
    confirmDialogMessage.value = message
    confirmDialogCallback.value = callback
    confirmDialogIsDanger.value = isDanger
    showConfirmDialog.value = true
  }

  const handleConfirmDialogConfirm = (): void => {
    if (confirmDialogCallback.value) {
      confirmDialogCallback.value()
    }
    showConfirmDialog.value = false
    confirmDialogCallback.value = null
  }

  const handleConfirmDialogCancel = (): void => {
    showConfirmDialog.value = false
    confirmDialogCallback.value = null
  }

  // —— 创建 Agent ——
  const handleCreateAgent = async (): Promise<void> => {
    if (!newAgentForm.value.name.trim()) return
    createDialogError.value = ''
    try {
      await agentStore.createAgent({
        name: newAgentForm.value.name.trim(),
        description: newAgentForm.value.description.trim(),
        systemPrompt: newAgentForm.value.systemPrompt.trim(),
        color: newAgentForm.value.color,
        avatar: newAgentForm.value.avatarMode === 'preset' ? newAgentForm.value.avatarUrl : undefined,
      })
      showCreateDialog.value = false
      newAgentForm.value = createEmptyForm()
    } catch (e: unknown) {
      createDialogError.value = extractErrorMessage(e, '创建 Agent 失败')
    }
  }

  // —— 编辑 Agent 对话框 ——
  const showEditDialog = ref(false)
  const editingAgentId = ref<string | null>(null)
  const editAgentForm = ref<AgentFormState>(createEmptyForm())

  const openEditDialog = (agent: AgentProfile, e?: Event): void => {
    if (e) e.stopPropagation()
    editingAgentId.value = agent.id
    editAgentForm.value = {
      name: agent.name || '',
      description: agent.description || '',
      systemPrompt: agent.systemPrompt || '',
      color: agent.color || 'var(--lumi-brand)',
      avatarMode: agent.avatar ? 'preset' : 'color',
      avatarUrl: agent.avatar || '',
    }
    showEditDialog.value = true
  }

  const handleUpdateAgent = async (): Promise<void> => {
    if (!editingAgentId.value || !editAgentForm.value.name.trim()) return
    try {
      await agentStore.updateAgent(editingAgentId.value, {
        name: editAgentForm.value.name.trim(),
        description: editAgentForm.value.description.trim(),
        systemPrompt: editAgentForm.value.systemPrompt.trim(),
        color: editAgentForm.value.color,
        avatar: editAgentForm.value.avatarMode === 'preset' ? editAgentForm.value.avatarUrl : undefined,
      })
      showEditDialog.value = false
      editingAgentId.value = null
    } catch (e: unknown) {
      toast.error(extractErrorMessage(e, '更新 Agent 失败'))
    }
  }

  const handleDeleteAgent = async (): Promise<void> => {
    if (!editingAgentId.value) return
    const deletedId = editingAgentId.value
    try {
      await agentStore.deleteAgent(deletedId)
      showEditDialog.value = false
      editingAgentId.value = null
      options.onAgentDeleted(deletedId)
    } catch (e: unknown) {
      toast.error(extractErrorMessage(e, '删除 Agent 失败'))
    }
  }

  return {
    agentColors: AGENT_COLORS,
    presetAvatars: PRESET_AGENT_AVATARS,
    showCreateDialog,
    newAgentForm,
    createDialogError,
    showConfirmDialog,
    confirmDialogMessage,
    confirmDialogIsDanger,
    showEditDialog,
    editingAgentId,
    editAgentForm,
    openConfirmDialog,
    handleConfirmDialogConfirm,
    handleConfirmDialogCancel,
    handleCreateAgent,
    openEditDialog,
    handleUpdateAgent,
    handleDeleteAgent,
  }
}
