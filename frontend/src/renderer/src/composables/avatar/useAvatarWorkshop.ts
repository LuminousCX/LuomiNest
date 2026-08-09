/**
 * useAvatarWorkshop - 皮套工坊核心状态管理
 *
 * 集中管理：
 * 1. 当前模型类型（currentMode: live2d/vrm/pixel/spine/png）
 * 2. 当前模型 ID（currentModelId）
 * 3. 显示模式（displayMode: inline/desktop）— 与模型类型正交
 * 4. 后端 manifest（从 /avatar/manifest 拉取）
 * 5. 当前模型的绑定与能力声明
 * 6. 模型导入/删除（通过 Electron IPC，与后端 manifest 同步）
 *
 * 设计原则：
 * - 单一真相源：模型列表来自后端 manifest，不再前端硬编码
 * - 切换模型类型时自动选中该类型的第一个模型
 * - 切换模型时并发拉取 binding + capabilities
 * - 不管理渲染器实例（由各 Stage 组件自行管理 PIXI/Three.js）
 * - 驱动调用通过返回的 currentBinding/currentCapabilities 由上层路由
 *
 * 与现有 useLuomiNestLive2D 的关系：
 * - useLuomiNestLive2D 仍由 AvatarView 直接调用（Live2D 模式）
 * - 本 composable 只管状态，不管渲染
 * - 上层根据 currentMode 决定渲染哪个 Stage 组件
 */
import { ref, computed, readonly } from 'vue'
import { useApi } from '../useApi'
import { useToast } from '../useToast'
import { createLuomiNestRendererLogger } from '@/utils/logger'
import {
  AVATAR_MODEL_TYPES,
  type AvatarRendererType,
  type AvatarManifest,
  type AvatarManifestModel,
  type AvatarBinding,
  type AvatarCapability,
  type WorkshopDisplayMode,
  type ModelTypeInfo,
  type WorkshopState,
} from '@/types/avatar'
import type { PetModelInfo } from '@shared/ipc-types'

const logger = createLuomiNestRendererLogger('AvatarWorkshop')

// ---------------------------------------------------------------------------
// 默认值
// ---------------------------------------------------------------------------

const DEFAULT_MODE: AvatarRendererType = 'live2d'
const DEFAULT_LIVE2D_MODEL_ID = 'builtin-live2d-llny'

// ---------------------------------------------------------------------------
// Composable
// ---------------------------------------------------------------------------

export function useAvatarWorkshop() {
  const api = useApi()
  const toast = useToast()

  // ------------------------------------------------------------------
  // 响应式状态
  // ------------------------------------------------------------------

  /** 当前模型类型（live2d/vrm/pixel/spine/png） */
  const currentMode = ref<AvatarRendererType>(DEFAULT_MODE)

  /** 当前模型 ID（manifest 中的 id 字段，如 builtin-live2d-llny） */
  const currentModelId = ref<string>(DEFAULT_LIVE2D_MODEL_ID)

  /** 显示模式：内嵌画布 or 桌面宠物窗口 */
  const displayMode = ref<WorkshopDisplayMode>('inline')

  /** 后端 manifest（单一真相源） */
  const manifest = ref<AvatarManifest | null>(null)

  /** 当前模型的绑定配置 */
  const currentBinding = ref<AvatarBinding | null>(null)

  /** 当前模型的能力声明 */
  const currentCapabilities = ref<AvatarCapability | null>(null)

  /** 加载状态 */
  const isLoadingManifest = ref(false)
  const isSwitchingMode = ref(false)
  const isSwitchingModel = ref(false)
  const isSwitchingDisplayMode = ref(false)

  /** 工坊级错误（manifest 加载失败等） */
  const workshopError = ref<string | null>(null)

  /** 通过 Electron IPC 管理的本地导入模型（与 manifest 中的 imported 模型对应） */
  const importedModels = ref<PetModelInfo[]>([])

  // ------------------------------------------------------------------
  // 计算属性
  // ------------------------------------------------------------------

  /** 所有模型类型（含未实现标记，UI 据此禁用） */
  const availableModelTypes = readonly(computed<ModelTypeInfo[]>(() => AVATAR_MODEL_TYPES))

  /** 已实现的模型类型（用于过滤 UI 显示） */
  const implementedModelTypes = computed<ModelTypeInfo[]>(() =>
    AVATAR_MODEL_TYPES.filter(t => t.implemented),
  )

  /** 当前类型下的所有模型 */
  const modelsByCurrentMode = computed<AvatarManifestModel[]>(() => {
    if (!manifest.value) return []
    return manifest.value.models.filter(m => m.type === currentMode.value)
  })

  /** 当前选中的模型对象 */
  const currentModel = computed<AvatarManifestModel | null>(() => {
    return modelsByCurrentMode.value.find(m => m.id === currentModelId.value) ?? null
  })

  /** 各类型下的模型数量（用于 UI 徽章） */
  const modelCountByType = computed<Record<AvatarRendererType, number>>(() => {
    const counts: Record<AvatarRendererType, number> = {
      live2d: 0, vrm: 0, pixel: 0, spine: 0, png: 0,
    }
    if (manifest.value) {
      for (const m of manifest.value.models) {
        counts[m.type] = (counts[m.type] ?? 0) + 1
      }
    }
    return counts
  })

  /** manifest 是否已加载 */
  const isManifestLoaded = computed(() => manifest.value !== null)

  /** 工坊状态快照（调试用） */
  const stateSnapshot = computed<WorkshopState>(() => ({
    currentMode: currentMode.value,
    currentModelId: currentModelId.value,
    displayMode: displayMode.value,
    manifestLoaded: isManifestLoaded.value,
    modelCount: manifest.value?.models.length ?? 0,
  }))

  // ------------------------------------------------------------------
  // Manifest 管理
  // ------------------------------------------------------------------

  /** 从后端拉取完整 manifest（builtin + imported） */
  async function fetchManifest(): Promise<void> {
    isLoadingManifest.value = true
    workshopError.value = null
    try {
      const result = await api.apiGet<AvatarManifest>('/avatar/manifest')
      manifest.value = result
      logger.info(`Manifest loaded: ${result.models.length} models`)
    } catch (err) {
      workshopError.value = err instanceof Error ? err.message : '加载模型清单失败'
      logger.error('fetchManifest failed', err)
    } finally {
      isLoadingManifest.value = false
    }
  }

  /** 拉取指定模型的绑定配置 */
  async function fetchBinding(modelId: string): Promise<void> {
    try {
      const result = await api.apiGet<AvatarBinding>(
        `/avatar/models/${modelId}/binding`,
      )
      currentBinding.value = result
    } catch (err) {
      logger.warn('fetchBinding failed, using null', err)
      currentBinding.value = null
    }
  }

  /** 拉取指定模型的能力声明 */
  async function fetchCapabilities(modelId: string): Promise<void> {
    try {
      const result = await api.apiGet<AvatarCapability>(
        `/avatar/models/${modelId}/capabilities`,
      )
      currentCapabilities.value = result
    } catch (err) {
      logger.warn('fetchCapabilities failed, using null', err)
      currentCapabilities.value = null
    }
  }

  // ------------------------------------------------------------------
  // 模式与模型切换
  // ------------------------------------------------------------------

  /**
   * 切换模型类型（live2d → pixel 等）
   *
   * 切换流程：
   * 1. 校验目标类型已实现
   * 2. 更新 currentMode
   * 3. 自动选中该类型的第一个模型（触发 switchModel）
   */
  async function switchMode(mode: AvatarRendererType): Promise<boolean> {
    if (currentMode.value === mode) {
      logger.debug(`switchMode: already in ${mode}`)
      return true
    }

    const typeInfo = AVATAR_MODEL_TYPES.find(t => t.type === mode)
    if (!typeInfo) {
      toast.error(`未知模型类型：${mode}`)
      return false
    }
    if (!typeInfo.implemented) {
      toast.warning(`${typeInfo.label} 渲染器尚未实现，敬请期待`)
      return false
    }
    if (isSwitchingMode.value) {
      logger.debug('switchMode: another switch in progress')
      return false
    }

    isSwitchingMode.value = true
    try {
      currentMode.value = mode
      logger.info(`Mode switched to ${mode}`)

      // 自动选中该类型的第一个模型
      const firstModel = manifest.value?.models.find(m => m.type === mode)
      if (firstModel) {
        await switchModel(firstModel.id)
      } else {
        currentModelId.value = ''
        currentBinding.value = null
        currentCapabilities.value = null
        logger.warn(`No models found for type ${mode}`)
      }
      return true
    } finally {
      isSwitchingMode.value = false
    }
  }

  /**
   * 切换当前类型下的模型
   *
   * 并发拉取 binding + capabilities，不阻塞渲染器加载
   * （渲染器加载由各 Stage 组件自行管理）
   */
  async function switchModel(modelId: string): Promise<boolean> {
    if (currentModelId.value === modelId) {
      logger.debug(`switchModel: already on ${modelId}`)
      return true
    }
    if (isSwitchingModel.value) {
      logger.debug('switchModel: another switch in progress')
      return false
    }

    isSwitchingModel.value = true
    try {
      currentModelId.value = modelId
      // 并发拉取绑定和能力（失败不阻塞，使用 null 回退）
      await Promise.all([
        fetchBinding(modelId),
        fetchCapabilities(modelId),
      ])
      logger.info(`Model switched to ${modelId}`, {
        binding: !!currentBinding.value,
        capabilities: !!currentCapabilities.value,
      })
      return true
    } finally {
      isSwitchingModel.value = false
    }
  }

  /**
   * 切换显示模式（inline ↔ desktop）
   *
   * 注意：此函数只更新状态，实际桌宠窗口的开关由 AvatarView 调用
   * avatarControl.openDesktopPet / closeDesktopPet 完成。
   * 这样设计是因为桌宠窗口开关涉及 IPC 和模型加载，逻辑较重，
   * 不适合放在状态管理 composable 中。
   */
  async function switchDisplayMode(mode: WorkshopDisplayMode): Promise<boolean> {
    if (displayMode.value === mode) return true
    if (isSwitchingDisplayMode.value) return false

    isSwitchingDisplayMode.value = true
    try {
      displayMode.value = mode
      logger.info(`Display mode switched to ${mode}`)
      return true
    } finally {
      isSwitchingDisplayMode.value = false
    }
  }

  // ------------------------------------------------------------------
  // 导入/删除模型（通过 Electron IPC）
  // ------------------------------------------------------------------

  /** 从 Electron IPC 加载本地导入的模型列表 */
  async function loadImportedModels(): Promise<void> {
    try {
      const models = await window.api.avatar.listImportedModels()
      importedModels.value = models
      logger.debug(`Loaded ${models.length} imported models`)
    } catch (err) {
      logger.error('loadImportedModels failed', err)
    }
  }

  /**
   * 导入模型（打开文件选择对话框）
   *
   * 流程：
   * 1. 调用 IPC 打开文件选择
   * 2. 文件落盘到 userData/avatar/{type}/
   * 3. 刷新本地导入列表 + 后端 manifest
   *
   * 返回导入的模型信息，失败返回 null
   */
  async function importModel(): Promise<PetModelInfo | null> {
    try {
      const result = await window.api.avatar.importModel()
      if (!result.success || !result.modelInfo) {
        if (result.error && result.error !== 'Cancelled') {
          toast.error(`导入失败：${result.error}`)
        }
        return null
      }

      // 刷新本地列表和后端 manifest
      await Promise.all([
        loadImportedModels(),
        fetchManifest(),
      ])

      toast.success('模型导入成功')
      logger.info(`Model imported: ${result.modelInfo.name}`)
      return result.modelInfo
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      toast.error(`导入失败：${msg}`)
      logger.error('importModel failed', err)
      return null
    }
  }

  /**
   * 删除已导入的模型
   *
   * 注意：builtin 模型不可删除（后端会拒绝）
   */
  async function deleteModel(modelName: string): Promise<boolean> {
    try {
      const result = await window.api.avatar.deleteModel(modelName)
      if (!result.success) {
        toast.error(`删除失败：${result.error ?? '未知错误'}`)
        return false
      }

      await Promise.all([
        loadImportedModels(),
        fetchManifest(),
      ])

      toast.success('模型已删除')
      logger.info(`Model deleted: ${modelName}`)
      return true
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      toast.error(`删除失败：${msg}`)
      logger.error('deleteModel failed', err)
      return false
    }
  }

  // ------------------------------------------------------------------
  // 绑定更新
  // ------------------------------------------------------------------

  /**
   * 更新当前模型的绑定配置
   *
   * 调用后端 PUT /avatar/models/{id}/binding，
   * 成功后更新本地 currentBinding。
   */
  async function updateBinding(
    updates: Partial<AvatarBinding>,
  ): Promise<boolean> {
    if (!currentModelId.value) {
      toast.warning('请先选择一个模型')
      return false
    }

    try {
      const result = await api.apiPut<AvatarBinding>(
        `/avatar/models/${currentModelId.value}/binding`,
        updates,
      )
      currentBinding.value = result
      toast.success('绑定配置已更新')
      logger.info('Binding updated', updates)
      return true
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      toast.error(`更新失败：${msg}`)
      logger.error('updateBinding failed', err)
      return false
    }
  }

  // ------------------------------------------------------------------
  // 初始化
  // ------------------------------------------------------------------

  /**
   * 初始化工坊：拉取 manifest + 导入列表，选中默认模型
   *
   * 在 AvatarView onMounted 中调用。
   */
  async function init(): Promise<void> {
    logger.info('Initializing avatar workshop')

    await Promise.all([
      fetchManifest(),
      loadImportedModels(),
    ])

    // 校验当前 modelId 是否存在于 manifest
    if (manifest.value) {
      const exists = manifest.value.models.some(m => m.id === currentModelId.value)
      if (!exists) {
        // 回退到当前类型的第一个模型
        const firstModel = manifest.value.models.find(m => m.type === currentMode.value)
        if (firstModel) {
          await switchModel(firstModel.id)
        } else {
          // 当前类型无模型，回退到任意可用模型
          const anyModel = manifest.value.models[0]
          if (anyModel) {
            await switchMode(anyModel.type)
          }
        }
      } else {
        // modelId 有效，拉取 binding + capabilities
        await Promise.all([
          fetchBinding(currentModelId.value),
          fetchCapabilities(currentModelId.value),
        ])
      }
    }

    logger.info('Avatar workshop initialized', stateSnapshot.value)
  }

  // ------------------------------------------------------------------
  // 返回
  // ------------------------------------------------------------------

  return {
    // 状态（只读 ref，避免外部直接修改）
    currentMode: readonly(currentMode),
    currentModelId: readonly(currentModelId),
    displayMode: readonly(displayMode),
    manifest: readonly(manifest),
    currentBinding: readonly(currentBinding),
    currentCapabilities: readonly(currentCapabilities),
    isLoadingManifest: readonly(isLoadingManifest),
    isSwitchingMode: readonly(isSwitchingMode),
    isSwitchingModel: readonly(isSwitchingModel),
    isSwitchingDisplayMode: readonly(isSwitchingDisplayMode),
    workshopError: readonly(workshopError),
    importedModels: readonly(importedModels),

    // 计算属性
    availableModelTypes,
    implementedModelTypes,
    modelsByCurrentMode,
    currentModel,
    modelCountByType,
    isManifestLoaded,
    stateSnapshot,

    // 方法
    init,
    fetchManifest,
    fetchBinding,
    fetchCapabilities,
    switchMode,
    switchModel,
    switchDisplayMode,
    loadImportedModels,
    importModel,
    deleteModel,
    updateBinding,
  }
}
