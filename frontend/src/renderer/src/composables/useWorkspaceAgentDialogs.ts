/**
 * LuomiNest 工作台 Agent 增删改对话框 + 确认对话框
 *
 * 从 WorkspaceView.vue 拆分：收纳 create/edit/delete agent 与通用 confirm dialog 的状态与方法。
 * 跨关注的副作用（删除 Agent 后清空联系人选择）通过 onAgentDeleted 回调交回视图处理，
 * 保持 composable 与联系人选择状态解耦。
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
}

const createEmptyForm = (): AgentFormState => ({
  name: '',
  description: '',
  systemPrompt: '',
  color: 'var(--lumi-brand)',
})

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
