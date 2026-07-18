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
import { useAvatarWorkshop } from '@/composables/avatar/useAvatarWorkshop'
import { useAvatarStageRenderer, type StageDriver, type Live2DDriver } from '@/composables/avatar/useAvatarStageRenderer'
import AvatarHeader from '@/components/avatar/AvatarHeader.vue'
import AvatarStage from '@/components/avatar/AvatarStage.vue'
import PixelPetStage from '@/components/avatar/PixelPetStage.vue'
import PngTuberStage from '@/components/avatar/PngTuberStage.vue'
import AvatarControls from '@/components/avatar/AvatarControls.vue'
import AvatarSkinSidebar from '@/components/avatar/AvatarSkinSidebar.vue'
import type { AvatarMode, AvatarEmotion, AvatarMotion, IdleAnimation, ManifestSkinItem } from '@/components/avatar/types'
import type { AvatarRendererType, AvatarManifestModel } from '@/types/avatar'
import type { ChatStreamChunk } from '@/types'
import type { PetModelInfo } from '@shared/ipc-types'
import { MAIN_AGENT_ID, MAIN_AGENT_PROFILE } from '@/constants'

// ===========================================================================
// 基础 stores & composables
// ===========================================================================

const avatarControl = useAvatarControlStore()
const modelStore = useModelStore()
const chatStore = useChatStore()
const agentStore = useAgentStore()
const platformStore = usePlatformStore()
const ttsEngine = useTtsEngineStore()
const toast = useToast()

// ===========================================================================
// 皮套工坊核心状态（manifest 驱动的单一真相源）
// ===========================================================================

const workshop = useAvatarWorkshop()

const {
  currentMode,
  currentModelId,
  displayMode,
  currentBinding,
  currentCapabilities,
  currentModel,
  modelsByCurrentMode,
  availableModelTypes,
  manifest,
  importedModels,
} = workshop

// ===========================================================================
// Stage 渲染器统一驱动路由
// ===========================================================================

const stageRenderer = useAvatarStageRenderer()

// ===========================================================================
// 桌面宠物模式状态
// ===========================================================================

const isSwitchingDisplayMode = ref(false)

const isDesktopMode = computed(() => displayMode.value === 'desktop')

// 桌宠运行状态：直接复用 avatarControl store 的单一真相源，避免状态重复
const isDesktopPetRunning = computed(() => avatarControl.isDesktopPetRunning)

// ===========================================================================
// Live2D 渲染器（仅 Live2D 模式使用，不修改原 composable）
// ===========================================================================

const canvasRef = ref<HTMLCanvasElement | null>(null)
const setCanvasRef: VNodeRef = (el) => {
  canvasRef.value = el as HTMLCanvasElement | null
}

const {
  isReady: isModelReady,
  isLoading,
  error: loadError,
  loadModel,
  driveEmotion: live2dDriveEmotion,
  drivePadEmotion: live2dDrivePadEmotion,
  syncLipParam: live2dSyncLipParam,
  syncLipVowel: live2dSyncLipVowel,
  resetPose: live2dResetPose,
  idleActive,
  triggerExpression: live2dTriggerExpression,
  triggerMotion: live2dTriggerMotion,
  destroy: teardown
} = useLuomiNestLive2D(canvasRef)

// 将 Live2D composable 的方法封装为 Live2DDriver 接口
const live2dDriver: Live2DDriver = {
  driveEmotion: live2dDriveEmotion,
  drivePadEmotion: live2dDrivePadEmotion,
  syncLipParam: live2dSyncLipParam,
  syncLipVowel: live2dSyncLipVowel,
  triggerMotion: live2dTriggerMotion,
  triggerExpression: live2dTriggerExpression,
  resetPose: live2dResetPose,
  isReady: () => isModelReady.value,
}

stageRenderer.setLive2DDriver(live2dDriver)
stageRenderer.setMode(currentMode.value)

// ===========================================================================
// Pixel Stage 组件 ref（通过 defineExpose 暴露驱动方法）
// ===========================================================================

const setPixelStageRef = (el: unknown): void => {
  stageRenderer.setStageRef(el as StageDriver | null)
}

// PNG Tuber Stage 组件 ref
const setPngTuberStageRef = (el: unknown): void => {
  stageRenderer.setStageRef(el as StageDriver | null)
}

// PNG Tuber manifest URL（从 currentModel.path 解析）
const pngManifestUrl = computed(() => {
  const model = currentModel.value
  if (!model || model.type !== 'png') return ''
  return manifestPathToAvatarUrl(model.path)
})

// ===========================================================================
// Manifest 路径 → 模型加载 URL 转换
// ===========================================================================

const LUOMINEST_DEFAULT_SCALE = 0.25

/** 将 manifest 中的相对路径转换为 luominest-avatar:// URL */
function manifestPathToAvatarUrl(path: string): string {
  // builtin Live2D: "live2d/{name}/{file}.model3.json" → "luominest-avatar://{name}/{file}.model3.json"
  if (path.startsWith('live2d/')) {
    return 'luominest-avatar://' + path.slice('live2d/'.length)
  }
  // PNG Tuber: "png/{model}/manifest.json" → "luominest-avatar://png/{model}/manifest.json"
  // 新格式：hostname 是模型类型前缀，avatar-protocol.ts 已支持
  if (path.startsWith('png/')) {
    return 'luominest-avatar://' + path
  }
  return path
}

/** 解析 manifest 模型为可加载的 {url, scale}（仅 Live2D 需要，Pixel/VRM 由各自 Stage 内部加载） */
function resolveModelLoadInfo(model: AvatarManifestModel): { url: string; scale: number } | null {
  if (model.type !== 'live2d') {
    return null
  }

  if (model.source === 'builtin') {
    return {
      url: manifestPathToAvatarUrl(model.path),
      scale: LUOMINEST_DEFAULT_SCALE,
    }
  }

  // 导入模型：通过名称在 IPC 导入列表中查找 URL
  const imported = importedModels.value.find(m => m.name === model.name)
  if (imported) {
    return { url: imported.url, scale: imported.scale || LUOMINEST_DEFAULT_SCALE }
  }

  // 回退：直接转换路径
  return {
    url: manifestPathToAvatarUrl(model.path),
    scale: LUOMINEST_DEFAULT_SCALE,
  }
}

/** 从当前模型绑定解析语义情绪 ID → 原生表情名（用于桌宠 IPC） */
function resolveEmotionFromBinding(emotionId: string): string {
  const binding = currentBinding.value
  if (!binding) return emotionId
  return binding.expression_map[emotionId] ?? binding.default_expression ?? emotionId
}

// ===========================================================================
// TTS 配置
// ===========================================================================

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
      stageRenderer.syncLipParam(value)
    }
  },
})

// Chat-driven avatar: LLM stream → expression + streaming TTS + subtitle
const chatText = ref('')
const isChatStreaming = ref(false)

const currentVoice = computed(() => {
  return currentBinding.value?.voice || 'zh-CN-XiaoxiaoNeural'
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

// 驱动回调：按 isDesktopMode 路由到 stageRenderer 或桌宠 IPC
const updateTtsDrivers = (): void => {
  ttsEngine.setDrivers({
    driveEmotion: (emotionId: string) => {
      if (isDesktopMode.value && isDesktopPetRunning.value) {
        const resolved = resolveEmotionFromBinding(emotionId)
        avatarControl.triggerExpression(resolved)
      } else {
        stageRenderer.driveEmotion(emotionId)
      }
    },
    syncLipParam: (value: number) => {
      if (isDesktopMode.value) {
        avatarControl.driveLipSync(value)
      } else {
        stageRenderer.syncLipParam(value)
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

// 代码块过滤状态机：跳过 ``` 包裹的代码块，不送入 TTS
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

// Unified subtitle display
const subtitleText = computed(() => {
  if (chatSubtitleVisible.value && chatSubtitleText.value) return chatSubtitleText.value
  return manualSubtitleText.value
})
const subtitleVisible = computed(() => {
  if (chatSubtitleVisible.value) return true
  return manualSubtitleVisible.value
})

// Forward subtitle to desktop pet window
watch([subtitleVisible, subtitleText, isDesktopMode], ([visible, text, desktopMode]) => {
  if (!desktopMode || !isDesktopPetRunning.value) return
  if (visible && text) {
    window.api.desktopPet.sendSubtitle(text)
  } else {
    window.api.desktopPet.hideSubtitle()
  }
})

// ===========================================================================
// 工坊 UI 状态
// ===========================================================================

const importError = ref<string | null>(null)
const showImportSuccess = ref(false)
const skinSidebarVisible = ref(true)

// 模式列表（从 workshop 的 availableModelTypes 映射）
const avatarModes = computed<AvatarMode[]>(() => {
  return availableModelTypes.value.map(t => ({
    id: t.type,
    label: t.label,
    desc: t.desc,
    implemented: t.implemented,
  }))
})

// 表情列表：从 manifest capabilities 读取（Live2D 用 expressions，Pixel 用 states）
const emotions = computed<AvatarEmotion[]>(() => {
  const caps = currentCapabilities.value
  if (!caps) return []

  // Live2D: 使用 expressions 列表
  // Pixel: expressions 为空，使用 states 列表作为可触发项
  const items = caps.expressions.length > 0
    ? caps.expressions
    : (caps.states ?? [])

  return items.map(name => ({
    id: name,
    icon: Smile,
    label: name,
    color: 'var(--lumi-primary)'
  }))
})

// 动作列表：从 manifest capabilities 读取
const motions = computed<AvatarMotion[]>(() => {
  const caps = currentCapabilities.value
  if (!caps) return []
  return caps.motions.map(name => ({
    id: name,
    label: name
  }))
})

const currentEmotionLocal = ref<AvatarEmotion | null>(null)
const currentMotionLocal = ref<AvatarMotion | null>(null)

// 模型切换后清空选中状态
watch([currentCapabilities, currentModelId], () => {
  currentEmotionLocal.value = null
  currentMotionLocal.value = null
})

// Idle 动画：仅 Live2D 模式显示（Pixel 有自己的 idle 行为）
const idleAnimations = computed<IdleAnimation[]>(() => {
  if (currentMode.value !== 'live2d') return []
  return [
    { name: 'Breath', status: isModelReady.value ? 'running' : 'paused', progress: isModelReady.value ? 65 : 0 },
    { name: 'Blink', status: isModelReady.value ? 'running' : 'paused', progress: isModelReady.value ? 40 : 0 },
    { name: 'Idle Motion', status: idleActive.value ? 'running' : 'paused', progress: idleActive.value ? 80 : 0 },
    { name: 'Head Track', status: isModelReady.value ? 'running' : 'paused', progress: isModelReady.value ? 50 : 0 }
  ]
})

// 侧边栏模型列表：当前模式下的所有模型（从 manifest 驱动）
const skinList = computed<ManifestSkinItem[]>(() => {
  return modelsByCurrentMode.value.map(m => ({
    id: m.id,
    name: m.name,
    type: m.type,
    source: m.source,
    tags: m.tags,
    thumbnail: m.thumbnail,
    capabilities: {
      expressionCount: m.capabilities.expressions.length,
      motionCount: m.capabilities.motions.length,
      stateCount: m.capabilities.states?.length ?? 0,
      lipSync: m.capabilities.lip_sync,
      focusTracking: m.capabilities.focus_tracking,
    }
  }))
})

// 当前选中模型索引（从 workshop.currentModelId 映射到 skinList 索引）
const selectedSkin = computed(() => {
  return skinList.value.findIndex(s => s.id === currentModelId.value)
})

// ===========================================================================
// 模式与模型切换
// ===========================================================================

async function selectMode(modeId: string) {
  await workshop.switchMode(modeId as AvatarRendererType)
}

// 点击原生表情按钮：直接触发该表情/状态
function selectEmotion(emo: AvatarEmotion) {
  currentEmotionLocal.value = emo
  if (isDesktopMode.value && isDesktopPetRunning.value) {
    avatarControl.triggerExpression(emo.id)
  } else {
    stageRenderer.triggerExpression(emo.id)
  }
}

// 点击动作按钮：触发该 motion group
function selectMotion(motion: AvatarMotion) {
  currentMotionLocal.value = motion
  if (isDesktopMode.value && isDesktopPetRunning.value) {
    avatarControl.triggerMotion(motion.id)
  } else {
    stageRenderer.triggerMotion(motion.id)
  }
}

async function handleResetPose() {
  if (isDesktopMode.value && isDesktopPetRunning.value) {
    // 桌宠模式：通过 IPC 重置（如果支持）
    return
  }
  await stageRenderer.resetPose()
}

async function handleSkinSelect(idx: number) {
  const skin = skinList.value[idx]
  if (!skin) return
  await workshop.switchModel(skin.id)
}

// ===========================================================================
// 模型加载（currentModelId 变化时触发）
// ===========================================================================

async function loadCurrentModel(): Promise<void> {
  if (isDesktopMode.value) return

  const model = currentModel.value
  if (!model) return

  // 仅 Live2D 模型需要在此处加载；Pixel/VRM 由各自 Stage 组件 onMounted 加载
  if (model.type === 'live2d') {
    const loadInfo = resolveModelLoadInfo(model)
    if (loadInfo) {
      await loadModel(loadInfo.url, loadInfo.scale)
    }
  }
}

// 模型 ID 变化时加载模型
watch(currentModelId, async () => {
  await nextTick()
  await loadCurrentModel()
})

// 模式变化时更新 stageRenderer 模式，并释放离开模式的资源
watch(currentMode, (newMode, oldMode) => {
  stageRenderer.setMode(newMode)
  // 离开 Live2D 模式时销毁 PIXI 资源（避免 canvas 已移除后 ticker 继续运行）
  if (oldMode === 'live2d' && newMode !== 'live2d') {
    teardown()
  }
})

// 桌面模式变化时更新 TTS 驱动
watch(isDesktopMode, () => {
  updateTtsDrivers()
})

// ===========================================================================
// 模型导入
// ===========================================================================

async function handleImportClick() {
  importError.value = null
  const imported = await workshop.importModel()
  if (!imported) return

  showImportSuccess.value = true
  setTimeout(() => { showImportSuccess.value = false }, 2000)

  // 在刷新后的 manifest 中查找导入的模型并切换到它
  const manifestModel = manifest.value?.models.find(
    m => m.name === imported.name && m.source === 'imported'
  )
  if (manifestModel) {
    if (currentMode.value !== manifestModel.type) {
      await workshop.switchMode(manifestModel.type)
    }
    await workshop.switchModel(manifestModel.id)

    // 桌宠模式下同步加载
    if (isDesktopMode.value && isDesktopPetRunning.value) {
      await window.api.desktopPet.loadModel(imported)
    }
  }
}

// ===========================================================================
// 桌面宠物模式切换
// ===========================================================================

/**
 * 从当前 manifest 模型构建纯对象 PetModelInfo
 *
 * 关键：必须显式复制字段（尤其是 tags 数组），去除 Vue Proxy 包装。
 * Electron IPC 使用结构化克隆算法，Vue Proxy 不可克隆会导致
 * "An object could not be cloned." 错误。
 */
function buildPetModelInfo(model: AvatarManifestModel | null): PetModelInfo | null {
  if (!model) return null
  const loadInfo = resolveModelLoadInfo(model)
  if (!loadInfo) return null
  return {
    id: String(model.id),
    name: String(model.name),
    url: String(loadInfo.url),
    scale: Number(loadInfo.scale),
    type: String(model.type),
    tags: Array.isArray(model.tags) ? model.tags.map((t: string) => String(t)) : [],
  }
}

async function toggleDesktopMode() {
  if (isSwitchingDisplayMode.value) return
  if (isDesktopMode.value) {
    await switchToInlineMode()
  } else {
    await switchToDesktopMode()
  }
}

/**
 * 切换到桌宠模式
 *
 * 流程顺序很重要：
 * 1. 先释放内联 Live2D 资源
 * 2. 通过 IPC 打开桌宠窗口（store 内部已防御性复制参数）
 * 3. 仅当 IPC 成功后才切换 displayMode（避免状态不一致）
 * 4. 失败时 toast 提示并保持内联模式
 */
async function switchToDesktopMode() {
  if (isSwitchingDisplayMode.value) return
  isSwitchingDisplayMode.value = true
  try {
    // 1. 释放内联 Live2D 资源（避免 canvas 移除后 ticker 继续运行）
    if (currentMode.value === 'live2d') {
      teardown()
    }

    // 2. 构建桌宠加载信息（纯对象，去除 Vue Proxy）
    const petModelInfo = buildPetModelInfo(currentModel.value)

    // 3. 通过 store 打开桌宠窗口（内部已防御性复制 + 错误处理）
    const opened = await avatarControl.openDesktopPet(petModelInfo ?? undefined)
    if (!opened) {
      toast.error('桌宠窗口打开失败，请重试')
      return // 保持内联模式，不切换 displayMode
    }

    // 4. IPC 成功后再切换 displayMode（确保状态一致）
    await workshop.switchDisplayMode('desktop')
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err)
    toast.error(`切换桌宠模式失败：${msg}`)
    // 回滚：确保 displayMode 与实际窗口状态一致
    await workshop.switchDisplayMode('inline')
  } finally {
    isSwitchingDisplayMode.value = false
  }
}

/**
 * 切回内联模式
 *
 * 流程顺序：
 * 1. 先关闭桌宠窗口
 * 2. 切换 displayMode 回 inline
 * 3. 重新加载内联模型
 */
async function switchToInlineMode() {
  if (isSwitchingDisplayMode.value) return
  isSwitchingDisplayMode.value = true
  try {
    // 1. 关闭桌宠窗口
    const closed = await avatarControl.closeDesktopPet()
    if (!closed) {
      toast.warning('桌宠窗口关闭失败，可能需要手动关闭')
    }

    // 2. 切换 displayMode
    await workshop.switchDisplayMode('inline')

    // 3. 重新加载内联模型
    await nextTick()
    await loadCurrentModel()
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err)
    toast.error(`切回内联模式失败：${msg}`)
  } finally {
    isSwitchingDisplayMode.value = false
  }
}

// ===========================================================================
// TTS 手动输入
// ===========================================================================

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

// ===========================================================================
// Chat 发送（与工作台共用主 Agent 对话流）
// ===========================================================================

async function handleChatSend() {
  const text = chatText.value.trim()
  if (!text || isChatStreaming.value) return

  chatText.value = ''
  isChatStreaming.value = true
  stopAvatarChat()

  const mainAgent = platformStore.mainAgent
  const resolved = modelStore.resolveModel

  const targetConvId = chatStore.agentCurrentConvId[MAIN_AGENT_ID] || undefined

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
  const mainConvId = chatStore.agentCurrentConvId[MAIN_AGENT_ID]
  if (mainConvId) {
    chatStore.cancelConversationRequest(mainConvId)
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

// ===========================================================================
// 生命周期
// ===========================================================================

onMounted(async () => {
  agentStore.setActiveAgent(MAIN_AGENT_PROFILE)

  // 初始化工坊：拉取 manifest + 导入列表
  await workshop.init()

  // 同步桌宠运行状态（store 是单一真相源，computed 自动反映）
  await avatarControl.checkDesktopPetStatus()

  // 如果桌宠已在运行（如上次未关闭），同步 displayMode
  if (isDesktopPetRunning.value) {
    await workshop.switchDisplayMode('desktop')
  }

  // 并发加载后端状态
  await Promise.all([
    chatStore.checkBackend(),
    platformStore.fetchMainAgent(),
    modelStore.fetchProviders(),
    modelStore.fetchModelConfig(),
  ])
  if (chatStore.isBackendReady) {
    await chatStore.fetchConversations(MAIN_AGENT_ID)
  }

  // 加载初始模型（仅内嵌 + Live2D 模式）
  if (!isDesktopPetRunning.value) {
    await nextTick()
    await loadCurrentModel()
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
      :is-switching-mode="isSwitchingDisplayMode"
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
        <!-- Live2D Stage -->
        <AvatarStage
          v-if="currentMode === 'live2d'"
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

        <!-- Pixel Pet Stage -->
        <PixelPetStage
          v-else-if="currentMode === 'pixel'"
          :ref="setPixelStageRef"
          :is-desktop-mode="isDesktopMode"
          :current-emotion-local="currentEmotionLocal"
          :current-mode="currentMode"
          :avatar-modes="avatarModes"
          :subtitle-enabled="subtitleEnabled"
          :subtitle-text="subtitleText"
          :subtitle-visible="subtitleVisible"
          @toggle-desktop-mode="toggleDesktopMode"
        />

        <!-- PNG Tuber Stage -->
        <PngTuberStage
          v-else-if="currentMode === 'png'"
          :ref="setPngTuberStageRef"
          :is-desktop-mode="isDesktopMode"
          :current-emotion-local="currentEmotionLocal"
          :current-mode="currentMode"
          :avatar-modes="avatarModes"
          :subtitle-enabled="subtitleEnabled"
          :subtitle-text="subtitleText"
          :subtitle-visible="subtitleVisible"
          :manifest-url="pngManifestUrl"
          @toggle-desktop-mode="toggleDesktopMode"
        />

        <!-- 未实现的模式占位 -->
        <div v-else class="stage-placeholder">
          <span>{{ currentMode }} renderer not yet implemented</span>
        </div>

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
        :current-mode="currentMode"
        :model-count-by-type="workshop.modelCountByType.value"
        @toggle-sidebar="toggleSkinSidebar"
        @skin-select="handleSkinSelect"
        @import-click="handleImportClick"
        @switch-mode="selectMode"
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

.stage-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: var(--text-base);
}

@keyframes stage-appear {
  0% { opacity: 0; transform: scale(0.96); }
  100% { opacity: 1; transform: scale(1); }
}

.animate-stage-appear {
  animation: stage-appear 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}
</style>
