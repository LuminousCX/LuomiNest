<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import type { VNodeRef } from 'vue'
import { Smile, Frown, Meh, Heart, Zap } from 'lucide-vue-next'
import { useLuomiNestLive2D } from '@/composables/useLuomiNestLive2D'
import { useAvatarTTS } from '@/composables/useAvatarTTS'
import { useAvatarChat } from '@/composables/useAvatarChat'
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
import type { AvatarMode, AvatarEmotion, IdleAnimation, SkinItem } from '@/components/avatar/types'
import type { PetModelInfo } from '../vite-env.d'
import type { AgentProfile, ChatStreamChunk } from '@/types'

const canvasRef = ref<HTMLCanvasElement | null>(null)
const setCanvasRef: VNodeRef = (el) => {
  canvasRef.value = el as HTMLCanvasElement | null
}
const avatarControl = useAvatarControlStore()
const modelStore = useModelStore()
const chatStore = useChatStore()
const agentStore = useAgentStore()
const platformStore = usePlatformStore()
const toast = useToast()

// 主 Agent 固定标识：皮套工坊与工作台共用同一主 Agent 对话流
const MAIN_AGENT_ID = 'luominest_main_agent'
const MAIN_AGENT_PROFILE: AgentProfile = {
  id: MAIN_AGENT_ID,
  name: '主智能体',
  description: 'LuomiNest 工作台主 Agent，驱动 Live2D、记忆、工具、MCP 和子 Agent',
  color: 'var(--lumi-brand)',
  isMain: true,
  isActive: true,
}

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
const chatText = ref('')
const isChatStreaming = ref(false)

const currentVoice = computed(() => {
  const modelInfo = currentModelInfo.value
  if (!modelInfo) return 'zh-CN-XiaoxiaoNeural'
  const binding = getAvatarBinding(modelInfo.id)
  return binding?.voice || 'zh-CN-XiaoxiaoNeural'
})

const {
  isSpeaking: isChatSpeaking,
  isSynthesizing: isChatSynthesizing,
  subtitleText: chatSubtitleText,
  subtitleVisible: chatSubtitleVisible,
  currentEmotion: chatCurrentEmotion,
  feedChunk,
  finishStream,
  stop: stopAvatarChat,
} = useAvatarChat({
  voice: () => currentVoice.value,
  engine: () => modelStore.ttsConfig.provider || modelStore.ttsConfig.engine || 'auto',
  ttsConfig: () => ({
    model: modelStore.ttsConfig.model,
    speed: modelStore.ttsConfig.speed,
    apiKey: modelStore.ttsConfig.apiKey,
    baseUrl: modelStore.ttsConfig.baseUrl,
  }),
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
  ttsEnabled: () => ttsEnabled.value,
  subtitleEnabled: () => subtitleEnabled.value,
  onTtsError: (err: Error) => toast.warning(`语音合成失败：${err.message}`),
})

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

const emotions: AvatarEmotion[] = [
  { id: 'happy', icon: Smile, label: 'Happy', color: 'var(--lumi-amber)' },
  { id: 'sad', icon: Frown, label: 'Sad', color: 'var(--lumi-indigo)' },
  { id: 'neutral', icon: Meh, label: 'Neutral', color: 'var(--task-purple)' },
  { id: 'love', icon: Heart, label: 'Love', color: 'var(--task-pink)' },
  { id: 'surprise', icon: Zap, label: 'Surprise', color: 'var(--lumi-success)' }
]

const currentEmotionLocal = ref(emotions[2])

const expressionValue = computed(() => {
  const map: Record<string, number> = {
    happy: 0.8, sad: -0.4, neutral: 0, love: 0.6, surprise: 0.7
  }
  return map[currentEmotionLocal.value.id] ?? 0
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

function selectEmotion(emo: AvatarEmotion) {
  currentEmotionLocal.value = emo
  if (isDesktopMode.value && isDesktopPetRunning.value) {
    const modelUrl = currentModelInfo.value?.url || ''
    const resolved = resolveExpressionByModelUrl(modelUrl, emo.id)
    avatarControl.triggerExpression(resolved)
  } else {
    driveEmotion(emo.id)
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

  const options: {
    agentId: string
    model?: string
    provider?: string
    temperature?: number
    maxTokens?: number
    topP?: number
    onChunk: (chunk: ChatStreamChunk) => void
  } = {
    agentId: MAIN_AGENT_ID,
    model: mainAgent?.model || resolved?.model || undefined,
    provider: mainAgent?.provider || resolved?.provider || undefined,
    temperature: mainAgent?.temperature ?? modelStore.modelConfig.defaultTemperature,
    maxTokens: mainAgent?.maxTokens ?? modelStore.modelConfig.defaultMaxTokens,
    topP: modelStore.modelConfig.defaultTopP,
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
  chatStore.cancelCurrentRequest()
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
          :expression-value="expressionValue"
          :idle-animations="idleAnimations"
          @select-mode="selectMode"
          @update:chat-text="chatText = $event"
          @chat-send="handleChatSend"
          @chat-keydown="handleChatKeydown"
          @update:tts-text="ttsText = $event"
          @tts-send="handleTTSSend"
          @tts-keydown="handleTTSKeydown"
          @select-emotion="selectEmotion"
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
