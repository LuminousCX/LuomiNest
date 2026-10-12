/**
 * 聊天输入框（PromptBar）的会话级偏好：模型选择 + 响应档位（effort）。
 *
 * 交接说明（重要，勿当成假功能静默扩散）：
 * - 模型选择：数据真实（来自模型 store 的供应商/模型列表，默认当前全局主模型），
 *   选择仅持久化到 localStorage('chat-model') 用于展示；后端仍按设置页全局配置
 *   解析每轮模型（"全局模型统一"架构），让选择生效需要后端支持按会话/按请求指定模型。
 * - 响应档位 fast/balanced/max：持久化到 localStorage('chat-effort')；
 *   "档位 → 后端模型路由"的后端能力不存在（fast=主模型 / max=推理模型 /
 *   balanced=后端按轮自动），前端不做假路由。
 */
import { computed, ref, watch } from 'vue'
import { useModelStore } from '../stores/model'
import type { PromptBarEffort, PromptBarModelOption } from '../components/common/prompt-bar'

const MODEL_STORAGE_KEY = 'chat-model'
const EFFORT_STORAGE_KEY = 'chat-effort'
const VALID_EFFORTS: PromptBarEffort[] = ['fast', 'balanced', 'max']
const DEFAULT_EFFORT: PromptBarEffort = 'balanced'

const readStored = (key: string): string | null => {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

const writeStored = (key: string, value: string): void => {
  try {
    localStorage.setItem(key, value)
  } catch {
    // localStorage 不可用时静默忽略（隐私模式等）
  }
}

export function useChatPromptPrefs() {
  const modelStore = useModelStore()

  // 供应商 → 模型展开为菜单条目（key 形如 "<providerId>::<modelId>"）
  const modelOptions = computed<PromptBarModelOption[]>(() => {
    const out: PromptBarModelOption[] = []
    for (const p of modelStore.providers) {
      for (const m of p.models) {
        out.push({ key: `${p.id}::${m.id}`, name: m.name || m.id, tag: p.name })
      }
    }
    return out
  })

  // 当前全局主模型（与后端"按设置页全局配置解析"的真实行为一致）
  const currentModelKey = computed(() => {
    const resolved = modelStore.resolveModel
    return resolved ? `${resolved.provider}::${resolved.model}` : ''
  })

  const selectedModelKey = ref<string>(readStored(MODEL_STORAGE_KEY) ?? '')
  watch(
    [modelOptions, currentModelKey],
    () => {
      // 存储的选择不在可用列表（供应商被删/首次使用）时回落当前主模型
      if (!modelOptions.value.some((m) => m.key === selectedModelKey.value)) {
        selectedModelKey.value = currentModelKey.value
      }
    },
    { immediate: true },
  )
  watch(selectedModelKey, (v) => {
    if (v) writeStored(MODEL_STORAGE_KEY, v)
  })

  const storedEffort = readStored(EFFORT_STORAGE_KEY)
  const effortKey = ref<PromptBarEffort>(
    storedEffort && (VALID_EFFORTS as string[]).includes(storedEffort)
      ? (storedEffort as PromptBarEffort)
      : DEFAULT_EFFORT,
  )
  watch(effortKey, (v) => writeStored(EFFORT_STORAGE_KEY, v))

  return { modelOptions, selectedModelKey, effortKey }
}
