/**
 * LuomiNest 聊天会话公共层
 *
 * 收纳 useWorkbenchMessages（工作台）与 useWorkspaceMessages（对话页）的平行段：
 * 输入/技能选择/推理折叠状态、对话模式（普通/专业）选项与切换守卫、
 * 全局模型与生成参数拼装。
 * 发送编排（工作流分支/文件上传/TTS 驱动等）、chat_mode 同步 watch、
 * canSend 判定在两端差异较大，仍保留在各自 composable 中。
 */
import { ref, computed } from 'vue'
import { i18n } from '../i18n'
import { useChatStore } from '../stores/chat'
import { useModelStore } from '../stores/model'
import { useToast } from './useToast'
import type { ChatModeLevel, WorkflowModeOption } from '../components/workbench/types'

export interface UseChatSessionOptions {
  /** 当前生效对话 ID（selectChatMode 的上下文隔离守卫按它取消息列表） */
  getActiveConvId: () => string | null
}

export const useChatSession = (options: UseChatSessionOptions) => {
  const chatStore = useChatStore()
  const modelStore = useModelStore()
  const toast = useToast()

  // —— 输入与 UI 状态 ——
  const inputText = ref('')
  const selectedSkillIds = ref<string[]>([])
  const showReasoning = ref<Record<string, boolean>>({})

  // —— 对话模式（普通/专业） ——
  const chatMode = ref<ChatModeLevel>('normal')
  const chatModeOptions = computed<WorkflowModeOption[]>(() => [
    { value: 'normal', label: i18n.global.t('chat.modeNormal'), title: i18n.global.t('chat.modeNormalTitle') },
    { value: 'standard', label: i18n.global.t('chat.modePro'), title: i18n.global.t('chat.modeProTitle') },
  ])
  const isWorkflowMode = computed(() => chatMode.value !== 'normal')

  const selectChatMode = (mode: ChatModeLevel): void => {
    // 上下文隔离：如果当前对话已有消息，禁止切换模式，三种模式间不允许相互切换
    const convId = options.getActiveConvId()
    if (convId) {
      const currentMessages = chatStore.convMessages[convId] || []
      if (currentMessages.length > 0 && chatMode.value !== mode) {
        toast.warning(i18n.global.t('chat.modeSwitchBlocked'))
        return
      }
    }

    // 2026-08 全局模型统一：切换模式不再改动全局主模型。
    // 专业模式（standard）由后端按轮路由到推理模型（设置页配置），
    // 推理模型不可用时后端退化为主模型并通过 SSE notice 通知前端 toast。
    chatMode.value = mode
  }

  // —— 全局生成参数（2026-08 全局模型统一：发送一律使用全局主模型与全局生成参数） ——
  const resolveSendParams = () => {
    const resolved = modelStore.resolveModel
    return {
      model: resolved?.model || undefined,
      provider: resolved?.provider || undefined,
      temperature: modelStore.modelConfig.defaultTemperature,
      maxTokens: modelStore.modelConfig.defaultMaxTokens,
      topP: modelStore.modelConfig.defaultTopP,
    }
  }

  return {
    // 输入与 UI 状态
    inputText,
    selectedSkillIds,
    showReasoning,
    // 对话模式
    chatMode,
    chatModeOptions,
    isWorkflowMode,
    selectChatMode,
    // 全局生成参数
    resolveSendParams,
  }
}
