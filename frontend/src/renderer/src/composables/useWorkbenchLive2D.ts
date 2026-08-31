/**
 * LuomiNest 工作台 Live2D 集成 + TTS/字幕 + 全局主模型展示
 *
 * 从 WorkbenchView.vue 拆分：收纳 Live2D 加载/销毁、TTS 语音合成、字幕显示、
 * 全局主模型徽章展示等逻辑。桌面宠物模式与内嵌模式通过 isDesktopMode 切换。
 * 消息/工作流 composable 通过 feedChunk/finishStream/filterCodeForTts 驱动 TTS。
 *
 * 2026-08 全局模型统一：工作台不再提供模型切换下拉，模型切换统一收口到
 * 设置页 → 模型设置。本 composable 仅暴露 currentModel/currentProviderLogo
 * 供徽章只读展示。
 *
 * TTS 引擎已迁移至全局 Pinia store（useTtsEngineStore），桌宠模式下切换页面时
 * TTS 不中断（陪伴优先）。驱动回调与配置由本 composable 按模式动态设置。
 */
import { ref, computed, watch, nextTick, type ComputedRef, type VNodeRef } from 'vue'
import { useModelStore } from '../stores/model'
import { useAvatarControlStore } from '../stores/avatar-control'
import { useTtsEngineStore } from '../stores/tts-engine'
import { useLuomiNestLive2D } from './useLuomiNestLive2D'
import { useToast } from './useToast'
import { getProviderLogo } from '../config/provider-logos'
import { LUOMINEST_BUILTIN_MODELS, getAvatarBinding, resolveExpressionByModelUrl } from '../config/luominest-models'

export interface UseWorkbenchLive2DOptions {
  isDesktopMode: ComputedRef<boolean>
}

export const useWorkbenchLive2D = (options: UseWorkbenchLive2DOptions) => {
  const { isDesktopMode } = options
  const modelStore = useModelStore()
  const avatarControl = useAvatarControlStore()
  const ttsEngine = useTtsEngineStore()
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

  // ── 配置全局 TTS 引擎（voice / engine / ttsConfig / 开关） ──
  ttsEngine.setConfig({
    voice: () => currentBinding.value?.voice || 'zh-CN-XiaoxiaoNeural',
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

  // ── 驱动回调：按 isDesktopMode 路由到 canvas 或桌宠 IPC ──
  const updateTtsDrivers = (): void => {
    ttsEngine.setDrivers({
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
      onTtsError: (err: Error) => toast.warning(`语音合成失败：${err.message}`),
    })
  }

  updateTtsDrivers()

  // 桌面宠物模式字幕同步
  watch([() => ttsEngine.subtitleVisible, () => ttsEngine.subtitleText, isDesktopMode], ([visible, text, desktopMode]) => {
    if (!desktopMode) return
    if (visible && text) {
      window.api.desktopPet.sendSubtitle(text)
    } else {
      window.api.desktopPet.hideSubtitle()
    }
  })

  // 模式切换时更新驱动回调（canvas ↔ 桌宠 IPC）
  watch(isDesktopMode, () => {
    updateTtsDrivers()
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

  // 全局主模型徽章展示（2026-08 全局模型统一：工作台不再提供模型切换下拉，
  // 切换请前往 设置 → 模型设置）
  const currentModel = computed(() => {
    const resolved = modelStore.resolveModel
    return resolved?.model || '未配置模型'
  })

  const currentProvider = computed(() => {
    const resolved = modelStore.resolveModel
    return resolved?.provider || ''
  })

  const currentProviderLogo = computed(() => getProviderLogo(currentProvider.value))

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
    // TTS / 字幕（来自全局 store）
    ttsEnabled,
    subtitleEnabled,
    currentModelInfo,
    isSpeaking: computed(() => ttsEngine.isSpeaking),
    isSynthesizing: computed(() => ttsEngine.isSynthesizing),
    subtitleText: computed(() => ttsEngine.subtitleText),
    subtitleVisible: computed(() => ttsEngine.subtitleVisible),
    feedChunk: ttsEngine.feedChunk,
    finishStream: ttsEngine.finishStream,
    stopTts: ttsEngine.stop,
    dismissSubtitle: ttsEngine.dismissSubtitle,
    filterCodeForTts,
    resetCodeBlockFilter,
    // Live2D 模型切换
    switchModel,
    // 全局主模型徽章展示
    currentModel,
    currentProviderLogo,
  }
}
