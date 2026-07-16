<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import type { VNodeRef } from 'vue'
import { Smile } from 'lucide-vue-next'
import { useLuomiNestLive2D } from '@/composables/useLuomiNestLive2D'
import { useAvatarTTS } from '@/composables/useAvatarTTS'
import { useTtsEngineStore } from '@/stores/tts-engine'
import { useToast } from '@/composables/useToast'
import { useAvatarControlStore } from '@/stores/avatar-control'
import { useModelStore } from '@/stores/model'
import { useChatStore } from '@/stores/chat'
import { useAgentStore } from '@/stores/agent'
import { usePlatformStore } from '@/stores/platform'
import { LUOMINEST_BUILTIN_MODELS, type LuomiNestModelInfo, resolveExpressionByModelUrl, getAvatarBinding } from '@/config/luominest-models'
import AvatarHeader from '@/components/avatar/AvatarHeader.vue'
import AvatarStage from '@/components/avatar/AvatarStage.vue'
import AvatarControls from '@/components/avatar/AvatarControls.vue'
import AvatarSkinSidebar from '@/components/avatar/AvatarSkinSidebar.vue'
import type { AvatarMode, AvatarEmotion, AvatarMotion, IdleAnimation, SkinItem } from '@/components/avatar/types'
import type { PetModelInfo } from '@shared/ipc-types'
import type { ChatStreamChunk } from '@/types'
import { MAIN_AGENT_ID, MAIN_AGENT_PROFILE } from '@/constants'

const canvasRef = ref<HTMLCanvasElement | null>(null)
const setCanvasRef: VNodeRef = (el) => {
  canvasRef.value = el as HTMLCanvasElement | null
}
const avatarControl = useAvatarControlStore()
const modelStore = useModelStore()
const chatStore = useChatStore()
const agentStore = useAgentStore()
const platformStore = usePlatformStore()
const ttsEngine = useTtsEngineStore()
const toast = useToast()

// 主 Agent 固定标识：皮套工坊与工作台共用同一主 Agent 对话流

// 桌面宠物模式状态（需在 composables 之前声明，避免 TDZ）
const isDesktopMode = ref(false)
const isDesktopPetRunning = ref(false)
const isSwitchingMode = ref(false)

const {
  isReady: isModelReady,
  isLoading,
  error: loadError,
  loadModel,
  driveEmotion,
  syncLipParam,
  resetPose,
  idleActive,
  availableExpressions,
  availableMotions,
  triggerExpression,
  triggerMotion,
  destroy: teardown
} = useLuomiNestLive2D(canvasRef)

const ttsText = ref('')
const subtitleEnabled = ref(true)
const ttsEnabled = ref(true)

const {
  isSpeaking: isAvatarSpeaking,
  isSynthesizing: isAvatarSynthesizing,
  subtitleText: manualSubtitleText,
  subtitleVisible: manualSubtitleVisible,
  speak: avatarSpeak,
  stopSpeaking: avatarStopSpeaking,
} = useAvatarTTS({
  syncLipParam: (value: number) => {
    if (isDesktopMode.value) {
      avatarControl.driveLipSync(value)
    } else {
      syncLipParam(value)
    }
  },
})

// Chat-driven avatar: LLM stream → expression + streaming TTS + subtitle
// 使用全局 TTS Store：皮套工坊与工作台共享同一 TTS 引擎，
// 桌宠模式下切换页面时 TTS 不中断（陪伴优先）。
const chatText = ref('')
const isChatStreaming = ref(false)

const currentVoice = computed(() => {
  const modelInfo = currentModelInfo.value
  if (!modelInfo) return 'zh-CN-XiaoxiaoNeural'
  const binding = getAvatarBinding(modelInfo.id)
  return binding?.voice || 'zh-CN-XiaoxiaoNeural'
})

// 配置全局 TTS 引擎（voice / engine / ttsConfig / 开关）
ttsEngine.setConfig({
  voice: () => currentVoice.value,
  engine: () => modelStore.ttsConfig.provider || modelStore.ttsConfig.engine || 'auto',
  ttsConfig: () => ({
    model: modelStore.ttsConfig.model,
    speed: modelStore.ttsConfig.speed,
    apiKey: modelStore.ttsConfig.apiKey,
    baseUrl: modelStore.ttsConfig.baseUrl,
  }),
  ttsEnabled: () => ttsEnabled.value,
  subtitleEnabled: () => subtitleEnabled.value,
})

// 驱动回调：按 isDesktopMode 路由到 canvas 或桌宠 IPC
const updateTtsDrivers = (): void => {
  ttsEngine.setDrivers({
    driveEmotion: (emotionId: string) => {
      if (isDesktopMode.value && isDesktopPetRunning.value) {
        const modelUrl = currentModelInfo.value?.url || ''
        const resolved = resolveExpressionByModelUrl(modelUrl, emotionId)
        avatarControl.triggerExpression(resolved)
      } else {
        driveEmotion(emotionId)
      }
    },
    syncLipParam: (value: number) => {
      if (isDesktopMode.value) {
        avatarControl.driveLipSync(value)
      } else {
        syncLipParam(value)
      }
    },
    onTtsError: (err: Error) => toast.warning(`语音合成失败：${err.message}`),
  })
}

updateTtsDrivers()

// 从全局 store 解构 TTS 状态与操作
const isChatSpeaking = computed(() => ttsEngine.isSpeaking)
const isChatSynthesizing = computed(() => ttsEngine.isSynthesizing)
const chatSubtitleText = computed(() => ttsEngine.subtitleText)
const chatSubtitleVisible = computed(() => ttsEngine.subtitleVisible)
const chatCurrentEmotion = computed(() => ttsEngine.currentEmotion)
const feedChunk = ttsEngine.feedChunk
const finishStream = ttsEngine.finishStream
const stopAvatarChat = ttsEngine.stop

// 代码块过滤状态机：跳过 ``` 包裹的代码块，不送入 TTS（与工作台一致）
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

// Unified subtitle display: chat subtitle takes priority over manual TTS subtitle
const subtitleText = computed(() => {
  if (chatSubtitleVisible.value && chatSubtitleText.value) return chatSubtitleText.value
  return manualSubtitleText.value
})
const subtitleVisible = computed(() => {
  if (chatSubtitleVisible.value) return true
  return manualSubtitleVisible.value
})

// Forward subtitle to desktop pet window when in desktop mode
watch([subtitleVisible, subtitleText, isDesktopMode], ([visible, text, desktopMode]) => {
  if (!desktopMode || !isDesktopPetRunning.value) return
  if (visible && text) {
    window.api.desktopPet.sendSubtitle(text)
  } else {
    window.api.desktopPet.hideSubtitle()
  }
})

// 模式切换时更新 TTS 驱动回调（canvas ↔ 桌宠 IPC）
watch(isDesktopMode, () => {
  updateTtsDrivers()
})

const importError = ref<string | null>(null)
const importedModels = ref<LuomiNestModelInfo[]>([])
const showImportSuccess = ref(false)
const skinSidebarVisible = ref(true)

const avatarModes: AvatarMode[] = [
  { id: 'live2d', label: 'Live2D', desc: 'Cubism 4/5', active: true },
  { id: 'vrm', label: 'VRM', desc: '3D Model', active: false },
  { id: 'pixel', label: 'PixelPet', desc: 'Q-version Pet', active: false }
]

const currentMode = ref('live2d')

// 表情列表：动态读取当前模型的 FileReferences.Expressions
// 切换模型时自动更新（由 useLuomiNestLive2D 的 scanLuomiNestModelCapabilities 扫描）
const emotions = computed<AvatarEmotion[]>(() => {
  return availableExpressions.value.map(name => ({
    id: name,
    icon: Smile,
    label: name,
    color: 'var(--lumi-primary)'
  }))
})

// 动作列表：动态读取当前模型的 FileReferences.Motions
// 切换模型时自动更新（llny 无动作，hiyori 有 Idle/TapBody）
const motions = computed<AvatarMotion[]>(() => {
  return availableMotions.value.map(name => ({
    id: name,
    label: name
  }))
})

const currentEmotionLocal = ref<AvatarEmotion | null>(null)
const currentMotionLocal = ref<AvatarMotion | null>(null)

// 模型切换后清空选中状态（新模型的表情/动作名可能不同）
watch([availableExpressions, availableMotions], () => {
  currentEmotionLocal.value = null
  currentMotionLocal.value = null
})

const idleAnimations = computed<IdleAnimation[]>(() => [
  { name: 'Breath', status: isModelReady.value ? 'running' : 'paused', progress: isModelReady.value ? 65 : 0 },
  { name: 'Blink', status: isModelReady.value ? 'running' : 'paused', progress: isModelReady.value ? 40 : 0 },
  { name: 'Idle Motion', status: idleActive.value ? 'running' : 'paused', progress: idleActive.value ? 80 : 0 },
  { name: 'Head Track', status: isModelReady.value ? 'running' : 'paused', progress: isModelReady.value ? 50 : 0 }
])

const skinList = computed<SkinItem[]>(() => {
  const builtin = LUOMINEST_BUILTIN_MODELS.map(m => ({
    name: `${m.name}`,
    type: m.type === 'live2d' ? 'Live2D' : m.type === 'vrm' ? 'VRM' : 'PixelPet',
    tags: m.tags,
    modelInfo: m as LuomiNestModelInfo | null
  }))
  const imported = importedModels.value.map(m => ({
    name: m.name,
    type: 'Live2D',
    tags: ['Imported', ...m.tags],
    modelInfo: m as LuomiNestModelInfo | null
  }))
  return [...builtin, ...imported]
})

const selectedSkin = ref(0)

const currentModelInfo = computed(() => {
  const skin = skinList.value[selectedSkin.value]
  return skin?.modelInfo ?? null
})

function selectMode(modeId: string) {
  currentMode.value = modeId
}

// 点击原生表情按钮：直接触发该模型原生表情（不走语义映射）
function selectEmotion(emo: AvatarEmotion) {
  currentEmotionLocal.value = emo
  if (isDesktopMode.value && isDesktopPetRunning.value) {
    avatarControl.triggerExpression(emo.id)
  } else {
    triggerExpression(emo.id)
  }
}

// 点击动作按钮：触发该 motion group 的第 0 个动作
function selectMotion(motion: AvatarMotion) {
  currentMotionLocal.value = motion
  if (isDesktopMode.value && isDesktopPetRunning.value) {
    avatarControl.triggerMotion(motion.id)
  } else {
    triggerMotion(motion.id)
  }
}

async function handleResetPose() {
  await resetPose()
}

async function handleSkinSelect(idx: number) {
  selectedSkin.value = idx
  const skin = skinList.value[idx]
  if (isDesktopMode.value && isDesktopPetRunning.value) {
    if (skin.modelInfo) {
      await window.api.desktopPet.loadModel(skin.modelInfo)
    }
  } else {
    if (skin.modelInfo) {
      await loadModel(skin.modelInfo.url, skin.modelInfo.scale)
    }
  }
}

async function handleImportClick() {
  importError.value = null
  try {
    const result = await window.api.avatar.importModel()
    if (!result.success) {
      if (result.error !== 'Cancelled') {
        importError.value = result.error ?? 'Import failed'
      }
      return
    }

    if (result.modelInfo) {
      const modelInfo: LuomiNestModelInfo = {
        id: result.modelInfo.id,
        name: result.modelInfo.name,
        url: result.modelInfo.url,
        scale: result.modelInfo.scale,
        type: result.modelInfo.type as LuomiNestModelInfo['type'],
        tags: result.modelInfo.tags
      }

      const existingIdx = importedModels.value.findIndex(m => m.name === modelInfo.name)
      if (existingIdx >= 0) {
        importedModels.value[existingIdx] = modelInfo
      } else {
        importedModels.value.push(modelInfo)
      }

      showImportSuccess.value = true
      setTimeout(() => { showImportSuccess.value = false }, 2000)

      if (isDesktopMode.value) {
        selectedSkin.value = skinList.value.findIndex(s => s.modelInfo?.name === modelInfo.name)
        if (selectedSkin.value < 0) selectedSkin.value = skinList.value.length - 1
        if (isDesktopPetRunning.value) {
          await window.api.desktopPet.loadModel(modelInfo)
        }
      } else {
        selectedSkin.value = skinList.value.findIndex(s => s.modelInfo?.name === modelInfo.name)
        if (selectedSkin.value < 0) selectedSkin.value = skinList.value.length - 1
        await loadModel(modelInfo.url, modelInfo.scale)
      }
    }
  } catch (err) {
    importError.value = err instanceof Error ? err.message : 'Failed to import model'
  }
}

async function toggleDesktopMode() {
  if (isSwitchingMode.value) return
  if (isDesktopMode.value) {
    await switchToInlineMode()
  } else {
    await switchToDesktopMode()
  }
}

async function switchToDesktopMode() {
  isSwitchingMode.value = true
  try {
    teardown()
    isDesktopMode.value = true
    const modelInfo = currentModelInfo.value
    await window.api.desktopPet.open(modelInfo ?? undefined)
    await avatarControl.checkDesktopPetStatus()
    isDesktopPetRunning.value = avatarControl.isDesktopPetRunning
  } finally {
    isSwitchingMode.value = false
  }
}

async function switchToInlineMode() {
  isSwitchingMode.value = true
  try {
    isDesktopMode.value = false
    await window.api.desktopPet.close()
    await avatarControl.checkDesktopPetStatus()
    isDesktopPetRunning.value = avatarControl.isDesktopPetRunning
    await nextTick()
    if (currentModelInfo.value) {
      await loadModel(currentModelInfo.value.url, currentModelInfo.value.scale)
    }
  } finally {
    isSwitchingMode.value = false
  }
}

async function handleTTSSend() {
  const text = ttsText.value.trim()
  if (!text) return
  if (isAvatarSpeaking.value) {
    avatarStopSpeaking()
    return
  }
  await avatarSpeak(text)
}

function handleTTSKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleTTSSend()
  }
}

async function handleChatSend() {
  const text = chatText.value.trim()
  if (!text || isChatStreaming.value) return

  chatText.value = ''
  isChatStreaming.value = true
  stopAvatarChat()

  // 主 Agent 配置：与工作台页面一致
  const mainAgent = platformStore.mainAgent
  const resolved = modelStore.resolveModel

  // 皮套工坊使用桌宠隐藏对话（与桌宠窗口、工作台共享同一 convId）
  const targetConvId = chatStore.desktopPetConvId || undefined

  const options: {
    agentId: string
    model?: string
    provider?: string
    temperature?: number
    maxTokens?: number
    topP?: number
    targetConvId?: string
    onChunk: (chunk: ChatStreamChunk) => void
  } = {
    agentId: MAIN_AGENT_ID,
    model: mainAgent?.model || resolved?.model || undefined,
    provider: mainAgent?.provider || resolved?.provider || undefined,
    temperature: mainAgent?.temperature ?? modelStore.modelConfig.defaultTemperature,
    maxTokens: mainAgent?.maxTokens ?? modelStore.modelConfig.defaultMaxTokens,
    topP: modelStore.modelConfig.defaultTopP,
    targetConvId,
    onChunk: (chunk: ChatStreamChunk) => {
      if (chunk.done) {
        finishStream()
        isChatStreaming.value = false
        return
      }
      const filteredContent = filterCodeForTts(chunk.content || '')
      if (filteredContent || chunk.emotion) {
        feedChunk({
          ...chunk,
          content: filteredContent,
        })
      }
    },
  }

  // 重置代码块过滤状态机
  inCodeBlock = false

  try {
    await chatStore.sendMessage(text, options)
  } catch (e: unknown) {
    const errMsg = e instanceof Error ? e.message : String(e)
    toast.error(`发送消息失败：${errMsg}`)
  } finally {
    isChatStreaming.value = false
  }
}

function stopChatStream() {
  if (chatStore.desktopPetConvId) {
    chatStore.cancelConversationRequest(chatStore.desktopPetConvId)
  } else {
    chatStore.cancelCurrentRequest()
  }
  stopAvatarChat()
  finishStream()
  isChatStreaming.value = false
}

function handleChatKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleChatSend()
  }
}

function toggleSubtitle() {
  subtitleEnabled.value = !subtitleEnabled.value
}

function toggleTTS() {
  ttsEnabled.value = !ttsEnabled.value
  if (!ttsEnabled.value) {
    stopAvatarChat()
  }
}

function toggleSkinSidebar() {
  skinSidebarVisible.value = !skinSidebarVisible.value
}

const loadPersistedModels = async () => {
  try {
    const models = await window.api.avatar.listImportedModels()
    importedModels.value = models.map((m: PetModelInfo) => ({
      id: m.id || '',
      name: m.name || 'Unknown',
      url: m.url || '',
      scale: m.scale || 1,
      type: (['live2d', 'spine', 'vrm'].includes(m.type) ? m.type : 'live2d') as LuomiNestModelInfo['type'],
      tags: Array.isArray(m.tags) ? m.tags : []
    }))
  } catch {
  }
}

const checkDesktopPetStatus = async () => {
  try {
    isDesktopPetRunning.value = await window.api.desktopPet.isRunning()
  } catch {
    isDesktopPetRunning.value = false
  }
}

onMounted(async () => {
  // 设置虚拟主 Agent Profile，使 chat store 的 computed 基于 MAIN_AGENT_ID 工作（与工作台一致）
  agentStore.setActiveAgent(MAIN_AGENT_PROFILE)

  await loadPersistedModels()
  await checkDesktopPetStatus()
  await avatarControl.checkDesktopPetStatus()

  // Sync desktop mode with actual pet running state (e.g. pet still running from previous session)
  if (isDesktopPetRunning.value) {
    isDesktopMode.value = true
  }

  // 并发加载：后端状态 / 主 Agent 配置 / 模型配置 / 对话历史
  await Promise.all([
    chatStore.checkBackend(),
    platformStore.fetchMainAgent(),
    modelStore.fetchProviders(),
    modelStore.fetchModelConfig(),
  ])
  if (chatStore.isBackendReady) {
    await chatStore.fetchConversations(MAIN_AGENT_ID)
  }

  await nextTick()
  if (!isDesktopPetRunning.value) {
    const defaultModel = LUOMINEST_BUILTIN_MODELS[0]
    await loadModel(defaultModel.url, defaultModel.scale)
  }
})

onBeforeUnmount(() => {
  stopChatStream()
  stopAvatarChat()
  teardown()
})
</script>

<template>
  <div class="avatar-view">
    <AvatarHeader
      :is-desktop-mode="isDesktopMode"
      :is-switching-mode="isSwitchingMode"
      :tts-enabled="ttsEnabled"
      :subtitle-enabled="subtitleEnabled"
      @toggle-desktop-mode="toggleDesktopMode"
      @reset-pose="handleResetPose"
      @toggle-tts="toggleTTS"
      @toggle-subtitle="toggleSubtitle"
      @import-click="handleImportClick"
    />

    <div class="avatar-body">
      <div class="avatar-stage animate-stage-appear">
        <AvatarStage
          :set-canvas-ref="setCanvasRef"
          :is-desktop-mode="isDesktopMode"
          :is-loading="isLoading"
          :load-error="loadError"
          :is-model-ready="isModelReady"
          :current-emotion-local="currentEmotionLocal"
          :current-mode="currentMode"
          :avatar-modes="avatarModes"
          :subtitle-enabled="subtitleEnabled"
          :subtitle-text="subtitleText"
          :subtitle-visible="subtitleVisible"
          @toggle-desktop-mode="toggleDesktopMode"
        />
        <AvatarControls
          v-if="!isDesktopMode"
          :current-mode="currentMode"
          :avatar-modes="avatarModes"
          :chat-text="chatText"
          :is-chat-streaming="isChatStreaming"
          :is-chat-synthesizing="isChatSynthesizing"
          :is-chat-speaking="isChatSpeaking"
          :chat-current-emotion="chatCurrentEmotion"
          :tts-text="ttsText"
          :is-avatar-speaking="isAvatarSpeaking"
          :is-avatar-synthesizing="isAvatarSynthesizing"
          :emotions="emotions"
          :current-emotion-local="currentEmotionLocal"
          :motions="motions"
          :current-motion-local="currentMotionLocal"
          :idle-animations="idleAnimations"
          @select-mode="selectMode"
          @update:chat-text="chatText = $event"
          @chat-send="handleChatSend"
          @chat-keydown="handleChatKeydown"
          @update:tts-text="ttsText = $event"
          @tts-send="handleTTSSend"
          @tts-keydown="handleTTSKeydown"
          @select-emotion="selectEmotion"
          @select-motion="selectMotion"
        />
      </div>

      <AvatarSkinSidebar
        :skin-sidebar-visible="skinSidebarVisible"
        :import-error="importError"
        :show-import-success="showImportSuccess"
        :skin-list="skinList"
        :selected-skin="selectedSkin"
        @toggle-sidebar="toggleSkinSidebar"
        @skin-select="handleSkinSelect"
        @import-click="handleImportClick"
      />
    </div>
  </div>
</template>

<style scoped>
.avatar-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
}

.avatar-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.avatar-stage {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

@keyframes stage-appear {
  0% { opacity: 0; transform: scale(0.96); }
  100% { opacity: 1; transform: scale(1); }
}

.animate-stage-appear {
  animation: stage-appear 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}
</style>
