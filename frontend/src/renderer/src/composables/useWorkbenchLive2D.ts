/**
 * LuomiNest 工作台 Live2D 集成 + TTS/字幕 + 模型选择
 *
 * 从 WorkbenchView.vue 拆分：收纳 Live2D 加载/销毁、TTS 语音合成、字幕显示、
 * 模型切换、模型下拉选择等逻辑。桌面宠物模式与内嵌模式通过 isDesktopMode 切换。
 * 消息/工作流 composable 通过 feedChunk/finishStream/filterCodeForTts 驱动 TTS。
 */
import { ref, computed, watch, nextTick, type ComputedRef, type VNodeRef } from 'vue'
import { useModelStore } from '../stores/model'
import { usePlatformStore } from '../stores/platform'
import { useAvatarControlStore } from '../stores/avatar-control'
import { useLuomiNestLive2D } from './useLuomiNestLive2D'
import { useAvatarChat } from './useAvatarChat'
import { useToast } from './useToast'
import { getProviderLogo } from '../config/provider-logos'
import { LUOMINEST_BUILTIN_MODELS, getAvatarBinding, resolveExpressionByModelUrl } from '../config/luominest-models'

export interface UseWorkbenchLive2DOptions {
  isDesktopMode: ComputedRef<boolean>
}

/** LLM 模型下拉选项（非 Live2D 模型） */
export interface WorkbenchModelOption {
  providerId: string
  providerName: string
  providerLogo: ReturnType<typeof getProviderLogo>
  modelId: string
  modelName: string
}

export const useWorkbenchLive2D = (options: UseWorkbenchLive2DOptions) => {
  const { isDesktopMode } = options
  const modelStore = useModelStore()
  const platformStore = usePlatformStore()
  const avatarControl = useAvatarControlStore()
  const toast = useToast()

  // Live2D 画布引用
  const canvasRef = ref<HTMLCanvasElement | null>(null)
  const setCanvasRef: VNodeRef = (el) => {
    canvasRef.value = el as HTMLCanvasElement | null
  }

  const {
    isReady: isModelReady,
    isLoading: isModelLoading,
    error: loadError,
    loadModel,
    driveEmotion,
    syncLipParam,
    destroy: teardownLive2D,
  } = useLuomiNestLive2D(canvasRef)

  // TTS / 字幕开关
  const ttsEnabled = ref(true)
  const subtitleEnabled = ref(true)
  const currentModelInfo = ref(LUOMINEST_BUILTIN_MODELS[0])
  const currentBinding = computed(() => getAvatarBinding(currentModelInfo.value.id))

  // 代码块过滤状态（跨 chunk 保持，发送/重生成时需重置）
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

  const {
    isSpeaking,
    isSynthesizing,
    subtitleText,
    subtitleVisible,
    feedChunk,
    finishStream,
    stop: stopTts,
    dismissSubtitle,
  } = useAvatarChat({
    voice: () => currentBinding.value?.voice || 'zh-CN-XiaoxiaoNeural',
    engine: () => modelStore.ttsConfig.provider || modelStore.ttsConfig.engine || 'auto',
    ttsConfig: () => ({
      model: modelStore.ttsConfig.model,
      speed: modelStore.ttsConfig.speed,
      apiKey: modelStore.ttsConfig.apiKey,
      baseUrl: modelStore.ttsConfig.baseUrl,
    }),
    driveEmotion: (emotionId: string) => {
      if (isDesktopMode.value) {
        const modelUrl = currentModelInfo.value.url
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

  // 桌面宠物模式字幕同步
  watch([subtitleVisible, subtitleText, isDesktopMode], ([visible, text, desktopMode]) => {
    if (!desktopMode) return
    if (visible && text) {
      window.api.desktopPet.sendSubtitle(text)
    } else {
      window.api.desktopPet.hideSubtitle()
    }
  })

  // 模型切换（Live2D 内嵌模式加载到画布，桌面宠物模式通过 IPC 通知）
  const switchModel = async (model: typeof LUOMINEST_BUILTIN_MODELS[0]): Promise<void> => {
    currentModelInfo.value = model
    if (isDesktopMode.value) {
      await window.api.desktopPet.loadModel(model)
    } else {
      await loadModel(model.url, model.scale)
    }
  }

  // 模型下拉选择（切换 LLM provider/model，非 Live2D 模型）
  const showModelDropdown = ref(false)

  const currentModel = computed(() => {
    const resolved = modelStore.resolveModel
    return resolved?.model || '未配置模型'
  })

  const currentProvider = computed(() => {
    const resolved = modelStore.resolveModel
    return resolved?.provider || ''
  })

  const currentProviderLogo = computed(() => getProviderLogo(currentProvider.value))

  const hasProvider = computed(() => modelStore.providers.length > 0)

  const availableModelOptions = computed<WorkbenchModelOption[]>(() => {
    const options: WorkbenchModelOption[] = []
    for (const provider of modelStore.providers) {
      const logo = getProviderLogo(provider.id)
      const modelIds = provider.selectedModels.length > 0
        ? provider.selectedModels
        : (provider.defaultModel ? [provider.defaultModel] : [])
      for (const modelId of modelIds) {
        options.push({
          providerId: provider.id,
          providerName: provider.name,
          providerLogo: logo,
          modelId,
          modelName: modelId,
        })
      }
    }
    return options
  })

  const selectModel = async (providerId: string, modelId: string): Promise<void> => {
    try {
      await platformStore.updateMainAgent({ provider: providerId, model: modelId })
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : '未知错误'
      toast.error(`切换模型失败：${errMsg}`)
    }
    showModelDropdown.value = false
  }

  // 桌面宠物模式切换时加载/卸载 Live2D
  watch(isDesktopMode, async (desktopMode) => {
    if (desktopMode) {
      teardownLive2D()
    } else {
      await nextTick()
      const modelToLoad = currentModelInfo.value
      await loadModel(modelToLoad.url, modelToLoad.scale)
    }
  })

  return {
    // 画布
    canvasRef,
    setCanvasRef,
    // Live2D 状态
    isModelReady,
    isModelLoading,
    loadError,
    loadModel,
    teardownLive2D,
    // TTS / 字幕
    ttsEnabled,
    subtitleEnabled,
    currentModelInfo,
    isSpeaking,
    isSynthesizing,
    subtitleText,
    subtitleVisible,
    feedChunk,
    finishStream,
    stopTts,
    dismissSubtitle,
    filterCodeForTts,
    resetCodeBlockFilter,
    // 模型切换
    switchModel,
    // LLM 模型下拉
    showModelDropdown,
    currentModel,
    currentProvider,
    currentProviderLogo,
    hasProvider,
    availableModelOptions,
    selectModel,
  }
}
