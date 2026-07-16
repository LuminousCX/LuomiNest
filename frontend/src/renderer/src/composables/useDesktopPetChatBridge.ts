/**
 * LuomiNest 桌宠聊天桥接 composable
 *
 * 在主应用窗口（App.vue）中初始化，监听桌宠窗口转发的聊天请求：
 * - 桌宠窗口输入文字 → IPC `desktop-pet:send-chat-message` → 主进程转发
 *   → 主应用窗口 `desktop-pet:chat-message` 事件 → 本桥接接收
 * - 本桥接调用 chatStore.sendMessage（MAIN_AGENT_ID，普通模式）
 * - LLM 流式 chunk 通过 onChunk 回调转发到全局 TTS Store（驱动桌宠 Live2D）
 * - 桌宠窗口的流式状态通过 IPC 反馈（输入区切换发送/取消按钮）
 *
 * 全局性：本 composable 在 App.vue 初始化，不随页面切换卸载，
 * 确保用户在任意页面都能与桌宠对话（陪伴优先）。
 *
 * TTS 驱动路由：当 isDesktopPetRunning=true 时，TTS drivers 始终路由到
 * avatarControl IPC（驱动桌宠窗口的 Live2D），不依赖 WorkbenchView/AvatarView 生命周期。
 */
import { onMounted, onBeforeUnmount, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import { useTtsEngineStore } from '../stores/tts-engine'
import { useAvatarControlStore } from '../stores/avatar-control'
import { useModelStore } from '../stores/model'
import { usePlatformStore } from '../stores/platform'
import { useToast } from './useToast'
import { resolveExpressionByModelUrl } from '../config/luominest-models'
import { LUOMINEST_BUILTIN_MODELS } from '../config/luominest-models'
import { MAIN_AGENT_ID, MAIN_AGENT_PROFILE } from '../constants'
import { useAgentStore } from '../stores/agent'
import type { ChatStreamChunk } from '../types'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('DesktopPetChatBridge')

// 代码块过滤状态机：跳过 ``` 包裹的代码块，不送入 TTS（与工作台/皮套工坊一致）
let inCodeBlock = false
const filterCodeForTts = (content: string): string => {
  if (!content) return ''
  const parts = content.split('```')
  let result = ''
  for (let i = 0; i < parts.length; i++) {
    if (i === 0) {
      if (!inCodeBlock) result += parts[i]
    } else {
      inCodeBlock = !inCodeBlock
      if (!inCodeBlock) result += parts[i]
    }
  }
  return result
}

const resetCodeBlockFilter = (): void => {
  inCodeBlock = false
}

export const useDesktopPetChatBridge = (): void => {
  const chatStore = useChatStore()
  const ttsEngine = useTtsEngineStore()
  const avatarControl = useAvatarControlStore()
  const modelStore = useModelStore()
  const platformStore = usePlatformStore()
  const agentStore = useAgentStore()
  const toast = useToast()

  let isProcessing = false

  // ── 桌宠专属隐藏对话：每次启动创建新对话，与工作台隔离 ──
  const ensureDesktopPetConversation = async (): Promise<void> => {
    // 确保主 Agent 已激活
    if (!agentStore.activeAgent || agentStore.activeAgent.id !== MAIN_AGENT_ID) {
      agentStore.setActiveAgent(MAIN_AGENT_PROFILE)
    }

    const mainAgent = platformStore.mainAgent
    const resolved = modelStore.resolveModel
    const model = mainAgent?.model || resolved?.model || undefined
    const provider = mainAgent?.provider || resolved?.provider || undefined

    try {
      const conv = await chatStore.createConversation(
        '桌宠陪伴',
        MAIN_AGENT_ID,
        model,
        provider,
        'normal',
        true // isHidden: 隐藏对话，不在工作台左侧列表显示
      )
      if (conv?.id) {
        chatStore.desktopPetConvId = conv.id
        logger.info('Created new hidden desktop pet conversation:', conv.id)
      }
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e)
      logger.error('Failed to create desktop pet conversation:', errMsg)
    }
  }

  // ── TTS 驱动路由：桌宠模式下始终路由到 avatarControl IPC ──
  const updateTtsDriversForDesktopPet = (): void => {
    if (!avatarControl.isDesktopPetRunning) return

    // 桌宠模式下，TTS drivers 始终路由到 avatarControl IPC
    // 模型 URL 取内置默认模型（桌宠窗口的模型由其自行管理）
    const modelUrl = LUOMINEST_BUILTIN_MODELS[0].url

    ttsEngine.setConfig({
      voice: () => 'zh-CN-XiaoxiaoNeural',
      engine: () => modelStore.ttsConfig.provider || modelStore.ttsConfig.engine || 'auto',
      ttsConfig: () => ({
        model: modelStore.ttsConfig.model,
        speed: modelStore.ttsConfig.speed,
        apiKey: modelStore.ttsConfig.apiKey,
        baseUrl: modelStore.ttsConfig.baseUrl,
      }),
      ttsEnabled: () => true,
      subtitleEnabled: () => true,
    })

    ttsEngine.setDrivers({
      driveEmotion: (emotionId: string) => {
        const resolved = resolveExpressionByModelUrl(modelUrl, emotionId)
        avatarControl.triggerExpression(resolved)
      },
      syncLipParam: (value: number) => {
        avatarControl.driveLipSync(value)
      },
      onTtsError: (err: Error) => {
        logger.warn('TTS error in desktop pet bridge:', err.message)
      },
    })

    logger.info('TTS drivers routed to desktop pet IPC')
  }

  // ── 字幕同步到桌宠窗口 ──
  const watchSubtitle = watch(
    [() => ttsEngine.subtitleVisible, () => ttsEngine.subtitleText],
    ([visible, text]) => {
      if (!avatarControl.isDesktopPetRunning) return
      if (visible && text) {
        window.api.desktopPet.sendSubtitle(text)
      } else {
        window.api.desktopPet.hideSubtitle()
      }
    }
  )

  // ── 桌宠运行状态变化时，更新 TTS 驱动路由 ──
  const watchDesktopPetStatus = watch(
    () => avatarControl.isDesktopPetRunning,
    (isRunning) => {
      if (isRunning) {
        updateTtsDriversForDesktopPet()
      }
    }
  )

  // ── 发送消息到 LLM ──
  const sendMessage = async (text: string): Promise<void> => {
    if (isProcessing) {
      logger.warn('Already processing a message, ignoring')
      return
    }

    // 空消息守卫
    if (!text.trim()) return

    // 确保桌宠隐藏对话已创建
    if (!chatStore.desktopPetConvId) {
      await ensureDesktopPetConversation()
      if (!chatStore.desktopPetConvId) {
        logger.error('Failed to create desktop pet conversation, cannot send message')
        toast.error('桌宠对话初始化失败')
        return
      }
    }

    // 确保主 Agent 已激活（chatStore 的 computed 依赖 activeAgentId）
    if (!agentStore.activeAgent || agentStore.activeAgent.id !== MAIN_AGENT_ID) {
      agentStore.setActiveAgent(MAIN_AGENT_PROFILE)
    }

    isProcessing = true
    resetCodeBlockFilter()
    window.api.desktopPet.setStreamingState(true).catch(() => {})

    // 确保 TTS drivers 路由到桌宠 IPC
    updateTtsDriversForDesktopPet()

    const mainAgent = platformStore.mainAgent
    const resolved = modelStore.resolveModel

    const options = {
      agentId: MAIN_AGENT_ID,
      model: mainAgent?.model || resolved?.model || undefined,
      provider: mainAgent?.provider || resolved?.provider || undefined,
      temperature: mainAgent?.temperature ?? modelStore.modelConfig.defaultTemperature,
      maxTokens: mainAgent?.maxTokens ?? modelStore.modelConfig.defaultMaxTokens,
      topP: modelStore.modelConfig.defaultTopP,
      chatMode: 'normal' as const,
      targetConvId: chatStore.desktopPetConvId, // 使用桌宠专属隐藏对话
      onChunk: (chunk: ChatStreamChunk) => {
        if (chunk.done) {
          ttsEngine.finishStream()
          return
        }
        const filteredContent = filterCodeForTts(chunk.content || '')
        if (filteredContent || chunk.emotion) {
          ttsEngine.feedChunk({
            ...chunk,
            content: filteredContent,
          })
        }
      },
    }

    try {
      await chatStore.sendMessage(text, options)
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e)
      logger.error('sendMessage failed:', errMsg)
      toast.error(`桌宠对话失败：${errMsg}`)
    } finally {
      isProcessing = false
      window.api.desktopPet.setStreamingState(false).catch(() => {})
    }
  }

  // ── 取消当前请求 ──
  const cancelRequest = (): void => {
    if (chatStore.desktopPetConvId) {
      chatStore.cancelConversationRequest(chatStore.desktopPetConvId)
    } else {
      chatStore.cancelCurrentRequest()
    }
    ttsEngine.stop()
    isProcessing = false
    window.api.desktopPet.setStreamingState(false).catch(() => {})
  }

  let unsubMessage: (() => void) | null = null
  let unsubCancel: (() => void) | null = null

  onMounted(async () => {
    // 监听桌宠窗口转发的聊天消息
    unsubMessage = window.api.onDesktopPetChatMessage((text: string) => {
      logger.info('Received chat message from desktop pet window:', text.slice(0, 50))
      void sendMessage(text)
    })

    // 监听桌宠窗口的取消请求
    unsubCancel = window.api.onDesktopPetChatCancel(() => {
      logger.info('Received cancel request from desktop pet window')
      cancelRequest()
    })

    // 启动时始终创建新的隐藏对话
    await ensureDesktopPetConversation()

    // 如果启动时桌宠已在运行，立即设置 TTS 驱动
    if (avatarControl.isDesktopPetRunning) {
      updateTtsDriversForDesktopPet()
    }

    logger.info('Desktop pet chat bridge initialized')
  })

  onBeforeUnmount(() => {
    unsubMessage?.()
    unsubCancel?.()
    watchSubtitle()
    watchDesktopPetStatus()
  })
}
