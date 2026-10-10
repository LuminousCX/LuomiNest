import { ref, computed } from 'vue'
import type { Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useModelStore } from '../../stores/model'
import { useToast } from '../../composables/useToast'
import { createLuomiNestRendererLogger } from '../../utils/logger'
import { toErrorMessage } from '@/utils/error'

/**
 * 供应商模型列表拉取（AiModelMainConfig / AiModelReasonerConfig 共用）。
 *
 * 职责：
 * - 由已选供应商 id 推导可选模型列表（优先 selectedModels，回退 provider.models）；
 * - 拉取供应商模型列表并写入 store（GET /models/providers/{id}/models）；
 * - 暴露 modelsUnknown 判定：已选供应商但列表为空 → 面板据此禁用模型下拉，
 *   引导用户点击刷新按钮获取。
 *
 * 反馈策略：成功不弹 toast（下拉从禁用变可用本身即反馈）；
 * 空列表 warning；失败 error（摘要 + 技术细节 description）。
 */
export function useProviderModelFetch(selectedProviderId: Ref<string>) {
  const modelStore = useModelStore()
  const toast = useToast()
  const { t } = useI18n()
  const logger = createLuomiNestRendererLogger('AiModel')

  const availableModels = computed<{ id: string; name: string }[]>(() => {
    const provider = modelStore.providers.find(p => p.id === selectedProviderId.value)
    if (!provider) return []
    if (provider.selectedModels.length > 0) {
      return provider.selectedModels.map(id => ({ id, name: id }))
    }
    return provider.models
  })

  /** 已选供应商但模型列表未知 → 模型下拉应禁用，引导点刷新按钮 */
  const modelsUnknown = computed(
    () => !!selectedProviderId.value && availableModels.value.length === 0,
  )

  /** 正在拉取模型列表的供应商 id；空串表示空闲 */
  const fetchingProviderId = ref('')

  const isFetching = (providerId: string) => !!providerId && fetchingProviderId.value === providerId

  const fetchModels = async (providerId: string): Promise<void> => {
    if (!providerId || fetchingProviderId.value) return
    fetchingProviderId.value = providerId
    try {
      const models = await modelStore.fetchProviderModels(providerId)
      if (!models || models.length === 0) {
        toast.warning(t('aiModel.common.fetchEmpty'))
      }
    } catch (e: unknown) {
      logger.error('Failed to fetch models:', e)
      toast.error(t('aiModel.common.fetchFailedTitle'), {
        description: toErrorMessage(e) || t('aiModel.common.unknownError'),
      })
    } finally {
      fetchingProviderId.value = ''
    }
  }

  return { availableModels, modelsUnknown, fetchingProviderId, isFetching, fetchModels }
}
