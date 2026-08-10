import { reactive, watch } from 'vue'
import { getItem, setItem } from '../utils/storage'

/**
 * 设置分区的本地状态管理（与主题 luominest-theme-* 键约定保持一致）：
 * - 首次读取 localStorage（键：luominest-settings:<section>），缺失字段以默认值补齐
 * - 任意字段变化时自动持久化
 *
 * 注意：仅用于 UI 偏好等非敏感设置。密码等敏感信息不得进入持久化通道，
 * 通过 excludeKeys 排除（字段仍保留在内存状态中供会话内使用）。
 */
export function useSectionSettings<T extends Record<string, unknown>>(
  section: string,
  defaults: T,
  excludeKeys: Array<keyof T & string> = []
): T {
  const storageKey = `luominest-settings:${section}`
  const stored = getItem<Partial<T>>(storageKey, {})
  const state = reactive({ ...defaults, ...stored }) as T

  watch(
    state,
    () => {
      const persisted: Record<string, unknown> = {}
      for (const [key, value] of Object.entries(state)) {
        if (excludeKeys.includes(key)) continue
        persisted[key] = value
      }
      setItem(storageKey, persisted)
    },
    { deep: true }
  )

  return state
}
