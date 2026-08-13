/**
 * CxPlugins Store — 统一管理前端插件 + 后端插件 + 技能状态。
 *
 - 前端插件：通过 cxFrontendPluginLoader 管理（本地 reactive 状态）
 - 后端插件/技能：通过 /api/v1/plugins 与 /api/v1/skills REST API 管理
 *
 - 组件通过此 store 获取数据与调用操作，避免直接访问 loader 和 API。
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '../composables/useApi'
import { cxFrontendPluginLoader } from '../plugins'
import { useToast } from '../composables/useToast'
import type {
  CxFrontendPluginInstance,
  CxBackendPlugin,
  CxBackendSkill,
  CxPluginStats,
  CxSkillStats,
  CxSkillWriteResult,
  CxSkillDeleteResult,
  CxSkillValidateResult,
  CxConfigSuggestion,
  CxSettingPatch,
  CxConfigApplyResult,
  CxPluginConfigResult,
  CxPluginConfigResetResult,
  CxPluginConfigExplain,
  CxPluginScaffold,
  CxPluginScaffoldWriteResult,
} from '../plugins/types'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('PluginsStore')

export const usePluginsStore = defineStore('plugins', () => {
  const { apiGet, apiPost } = useApi()
  const toast = useToast()

  // ---------------- 内部状态 ----------------
  const frontendPlugins = ref<CxFrontendPluginInstance[]>([])
  const backendPlugins = ref<CxBackendPlugin[]>([])
  const skills = ref<CxBackendSkill[]>([])
  const frontendStats = ref({ total: 0, active: 0, inactive: 0, error: 0, disabled: 0 })
  const backendStats = ref<CxPluginStats>({ total: 0, active: 0, disabled: 0, disabled_ids: [] })
  const skillStats = ref<CxSkillStats>({ total: 0, active: 0, disabled: 0, disabled_ids: [] })
  const loadingBackend = ref(false)
  const operating = ref(false)

  // ---------------- 计算属性 ----------------
  const totalActivePlugins = computed(
    () => frontendStats.value.active + backendStats.value.active
  )
  const totalSkills = computed(() => skillStats.value.total)

  /**
   * 操作状态包装器 —— 统一 operating 标志的 set/try/finally 模式，
   * 消除 15+ 个 CRUD 函数中重复的样板代码。
   */
  const withOperating = async <T>(fn: () => Promise<T>): Promise<T> => {
    operating.value = true
    try {
      return await fn()
    } finally {
      operating.value = false
    }
  }

  // ---------------- 前端插件操作 ----------------

  const refreshFrontend = () => {
    frontendPlugins.value = cxFrontendPluginLoader.listPlugins()
    frontendStats.value = cxFrontendPluginLoader.getStats()
  }

  const enableFrontendPlugin = async (pluginId: string): Promise<boolean> =>
    withOperating(async () => {
      const ok = await cxFrontendPluginLoader.enablePlugin(pluginId)
      if (ok) {
        refreshFrontend()
        toast.success(`前端插件已启用：${pluginId}`)
      } else {
        toast.error(`前端插件启用失败：${pluginId}`)
      }
      return ok
    })

  const disableFrontendPlugin = async (pluginId: string): Promise<boolean> =>
    withOperating(async () => {
      const ok = await cxFrontendPluginLoader.disablePlugin(pluginId)
      if (ok) {
        refreshFrontend()
        toast.success(`前端插件已禁用：${pluginId}`)
      } else {
        toast.error(`前端插件禁用失败：${pluginId}`)
      }
      return ok
    })

  // ---------------- 后端插件操作 ----------------

  const refreshBackend = async () => {
    loadingBackend.value = true
    try {
      // useApi 已自动解包 {code,message,data} 信封（code===0 时直接返回 data），
      // 此处直接使用返回值，不要再访问 .data（否则列表永远为空）
      const [pluginsResp, statsResp] = await Promise.all([
        apiGet<CxBackendPlugin[]>('/plugins'),
        apiGet<CxPluginStats>('/plugins/stats'),
      ])
      backendPlugins.value = Array.isArray(pluginsResp) ? pluginsResp : []
      backendStats.value = statsResp ?? { total: 0, active: 0, disabled: 0, disabled_ids: [] }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      logger.warn('Failed to load backend plugins:', msg)
      toast.error(`加载后端插件失败：${msg}`)
    } finally {
      loadingBackend.value = false
    }
  }

  const enableBackendPlugin = async (pluginId: string): Promise<boolean> =>
    withOperating(async () => {
      try {
        // useApi 已自动解包信封并抛出业务错误，成功时直接返回 data
        await apiPost<CxBackendPlugin>(`/plugins/${pluginId}/enable`)
        await refreshBackend()
        toast.success(`后端插件已启用：${pluginId}`)
        return true
      } catch (e) {
        toast.error(`后端插件启用失败：${e instanceof Error ? e.message : String(e)}`)
        return false
      }
    })

  const disableBackendPlugin = async (pluginId: string): Promise<boolean> =>
    withOperating(async () => {
      try {
        await apiPost<CxBackendPlugin>(`/plugins/${pluginId}/disable`)
        await refreshBackend()
        toast.success(`后端插件已禁用：${pluginId}`)
        return true
      } catch (e) {
        toast.error(`后端插件禁用失败：${e instanceof Error ? e.message : String(e)}`)
        return false
      }
    })

  const reloadBackendPlugin = async (pluginId: string): Promise<boolean> =>
    withOperating(async () => {
      try {
        await apiPost<CxBackendPlugin>(`/plugins/${pluginId}/reload`)
        await refreshBackend()
        toast.success(`后端插件已重载：${pluginId}`)
        return true
      } catch (e) {
        toast.error(`后端插件重载失败：${e instanceof Error ? e.message : String(e)}`)
        return false
      }
    })

  const reloadAllBackendPlugins = async (): Promise<boolean> =>
    withOperating(async () => {
      try {
        const result = await apiPost<{ loaded_count: number }>('/plugins/reload-all')
        await refreshBackend()
        toast.success(`已重载全部后端插件（共 ${result?.loaded_count ?? 0} 个）`)
        return true
      } catch (e) {
        toast.error(`重载全部后端插件失败：${e instanceof Error ? e.message : String(e)}`)
        return false
      }
    })

  // ---------------- 技能操作 ----------------

  const refreshSkills = async () => {
    loadingBackend.value = true
    try {
      // useApi 已自动解包 {code,message,data} 信封，直接使用返回值
      const [skillsResp, statsResp] = await Promise.all([
        apiGet<CxBackendSkill[]>('/skills'),
        apiGet<CxSkillStats>('/skills/stats'),
      ])
      skills.value = Array.isArray(skillsResp) ? skillsResp : []
      skillStats.value = statsResp ?? { total: 0, active: 0, disabled: 0, disabled_ids: [] }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      logger.warn('Failed to load skills:', msg)
      toast.error(`加载技能列表失败：${msg}`)
    } finally {
      loadingBackend.value = false
    }
  }

  const enableSkill = async (skillId: string): Promise<boolean> =>
    withOperating(async () => {
      try {
        await apiPost<CxBackendSkill>(`/skills/${skillId}/enable`)
        await refreshSkills()
        toast.success(`技能已启用：${skillId}`)
        return true
      } catch (e) {
        toast.error(`技能启用失败：${e instanceof Error ? e.message : String(e)}`)
        return false
      }
    })

  const disableSkill = async (skillId: string): Promise<boolean> =>
    withOperating(async () => {
      try {
        await apiPost<CxBackendSkill>(`/skills/${skillId}/disable`)
        await refreshSkills()
        toast.success(`技能已禁用：${skillId}`)
        return true
      } catch (e) {
        toast.error(`技能禁用失败：${e instanceof Error ? e.message : String(e)}`)
        return false
      }
    })

  const reloadSkill = async (skillId: string): Promise<boolean> =>
    withOperating(async () => {
      try {
        await apiPost<CxBackendSkill>(`/skills/${skillId}/reload`)
        await refreshSkills()
        toast.success(`技能已重载：${skillId}`)
        return true
      } catch (e) {
        toast.error(`技能重载失败：${e instanceof Error ? e.message : String(e)}`)
        return false
      }
    })

  const reloadAllSkills = async (): Promise<boolean> =>
    withOperating(async () => {
      try {
        const result = await apiPost<{ loaded_count: number }>('/skills/reload-all')
        await refreshSkills()
        toast.success(`已重载全部技能（共 ${result?.loaded_count ?? 0} 个）`)
        return true
      } catch (e) {
        toast.error(`重载全部技能失败：${e instanceof Error ? e.message : String(e)}`)
        return false
      }
    })

  // ---------------- 技能创建 / 编辑 / 删除 ----------------

  /** 读取 SKILL.md 原文（用于编辑回填） */
  const getSkillRaw = async (skillId: string): Promise<string | null> => {
    try {
      const result = await apiGet<{ skill_id: string; content: string }>(
        `/skills/${skillId}/raw`,
      )
      return result?.content ?? ''
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      toast.error(`读取技能原文失败：${msg}`)
      return null
    }
  }

  /** 校验 SKILL.md 内容（不写入磁盘）。skillId 为预期 ID（新建时也需提供） */
  const validateSkill = async (
    skillId: string,
    content: string,
  ): Promise<CxSkillValidateResult | null> => {
    try {
      return await apiPost<CxSkillValidateResult>(
        '/skills/validate',
        { skill_id: skillId, content, overwrite: true },
      )
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      toast.error(`技能校验失败：${msg}`)
      return null
    }
  }

  /** 写入（创建/更新）SKILL.md */
  const writeSkill = async (
    skillId: string,
    content: string,
    overwrite: boolean = true,
  ): Promise<CxSkillWriteResult | null> =>
    withOperating(async () => {
      try {
        const result = await apiPost<CxSkillWriteResult>('/skills/write', {
          skill_id: skillId,
          content,
          overwrite,
        })
        await refreshSkills()
        toast.success(`技能已保存：${skillId}`)
        return result
      } catch (e) {
        toast.error(`技能保存失败：${e instanceof Error ? e.message : String(e)}`)
        return null
      }
    })

  /** 删除技能 */
  const deleteSkill = async (skillId: string): Promise<boolean> =>
    withOperating(async () => {
      try {
        await apiPost<CxSkillDeleteResult>('/skills/delete', {
          skill_id: skillId,
        })
        await refreshSkills()
        toast.success(`技能已删除：${skillId}`)
        return true
      } catch (e) {
        toast.error(`技能删除失败：${e instanceof Error ? e.message : String(e)}`)
        return false
      }
    })

  // ---------------- 插件配置 AI 助手 ----------------

  /** 获取插件当前配置（合并 manifest 默认值与 KV 存储值） */
  const getPluginConfig = async (
    pluginId: string,
  ): Promise<CxPluginConfigResult | null> => {
    try {
      return await apiGet<CxPluginConfigResult>(
        `/plugins/assistant/config/${pluginId}`,
      )
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      toast.error(`读取插件配置失败：${msg}`)
      return null
    }
  }

  /** 重置插件配置到 manifest 默认值 */
  const resetPluginConfig = async (
    pluginId: string,
  ): Promise<CxPluginConfigResetResult | null> =>
    withOperating(async () => {
      try {
        const result = await apiPost<CxPluginConfigResetResult>(
          '/plugins/assistant/config/reset',
          { plugin_id: pluginId },
        )
        toast.success(`插件配置已重置：${pluginId}`)
        return result
      } catch (e) {
        toast.error(`重置插件配置失败：${e instanceof Error ? e.message : String(e)}`)
        return null
      }
    })

  /** LLM 根据自然语言生成配置 patch 建议 */
  const suggestPluginConfig = async (
    pluginId: string,
    userRequest: string,
  ): Promise<CxConfigSuggestion | null> =>
    withOperating(async () => {
      try {
        return await apiPost<CxConfigSuggestion>(
          '/plugins/assistant/suggest',
          { plugin_id: pluginId, user_request: userRequest },
        )
      } catch (e) {
        toast.error(`生成配置建议失败：${e instanceof Error ? e.message : String(e)}`)
        return null
      }
    })

  /** 应用配置 patch 到插件 KV 存储 */
  const applyPluginConfigPatches = async (
    pluginId: string,
    patches: CxSettingPatch[],
    skipInvalid: boolean = true,
  ): Promise<CxConfigApplyResult | null> =>
    withOperating(async () => {
      try {
        const result = await apiPost<CxConfigApplyResult>(
          '/plugins/assistant/apply',
          {
            plugin_id: pluginId,
            patches: patches.map((p) => ({
              op: p.op,
              key: p.key,
              value: p.value,
              reason: p.reason ?? '',
              validation_error: p.validation_error ?? '',
            })),
            skip_invalid: skipInvalid,
          },
        )
        toast.success(`配置已应用：${result?.applied ?? 0} 项`)
        return result
      } catch (e) {
        toast.error(`应用配置失败：${e instanceof Error ? e.message : String(e)}`)
        return null
      }
    })

  /** LLM 解释插件当前配置 */
  const explainPluginConfig = async (
    pluginId: string,
  ): Promise<CxPluginConfigExplain | null> =>
    withOperating(async () => {
      try {
        return await apiPost<CxPluginConfigExplain>(
          '/plugins/assistant/explain',
          { plugin_id: pluginId },
        )
      } catch (e) {
        toast.error(`配置解释失败：${e instanceof Error ? e.message : String(e)}`)
        return null
      }
    })

  /** 生成新插件脚手架（不写入磁盘） */
  const generatePluginScaffold = async (payload: {
    pluginId: string
    name: string
    description: string
    author?: string
    category?: string
    permissions?: string[]
    capabilities?: string[]
    settingsDecl?: Record<string, unknown>
  }): Promise<CxPluginScaffold | null> =>
    withOperating(async () => {
      try {
        const result = await apiPost<CxPluginScaffold>(
          '/plugins/assistant/scaffold/generate',
          {
            plugin_id: payload.pluginId,
            name: payload.name,
            description: payload.description,
            author: payload.author ?? 'LuminousCX',
            category: payload.category ?? 'tool',
            permissions: payload.permissions,
            capabilities: payload.capabilities,
            settings_decl: payload.settingsDecl,
          },
        )
        toast.success(`脚手架已生成：${payload.pluginId}`)
        return result
      } catch (e) {
        toast.error(`生成脚手架失败：${e instanceof Error ? e.message : String(e)}`)
        return null
      }
    })

  /** 将已生成的脚手架写入 plugins/ 目录 */
  const writePluginScaffold = async (
    pluginId: string,
    overwrite: boolean = false,
  ): Promise<CxPluginScaffoldWriteResult | null> =>
    withOperating(async () => {
      try {
        const result = await apiPost<CxPluginScaffoldWriteResult>(
          '/plugins/assistant/scaffold/write',
          { plugin_id: pluginId, overwrite },
        )
        await refreshBackend()
        toast.success(`脚手架已写入磁盘：${pluginId}`)
        return result
      } catch (e) {
        toast.error(`写入脚手架失败：${e instanceof Error ? e.message : String(e)}`)
        return null
      }
    })

  /** 列出所有历史脚手架记录 */
  const listPluginScaffolds = async (): Promise<CxPluginScaffold[]> => {
    try {
      const result = await apiGet<CxPluginScaffold[]>('/plugins/assistant/scaffolds')
      return Array.isArray(result) ? result : []
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      logger.warn('Failed to list plugin scaffolds:', msg)
      return []
    }
  }

  // ---------------- 初始化 ----------------

  const initAll = async () => {
    refreshFrontend()
    await Promise.all([refreshBackend(), refreshSkills()])
  }

  return {
    // 状态
    frontendPlugins,
    backendPlugins,
    skills,
    frontendStats,
    backendStats,
    skillStats,
    loadingBackend,
    operating,
    // 计算
    totalActivePlugins,
    totalSkills,
    // 前端插件
    refreshFrontend,
    enableFrontendPlugin,
    disableFrontendPlugin,
    // 后端插件
    refreshBackend,
    enableBackendPlugin,
    disableBackendPlugin,
    reloadBackendPlugin,
    reloadAllBackendPlugins,
    // 技能
    refreshSkills,
    enableSkill,
    disableSkill,
    reloadSkill,
    reloadAllSkills,
    // 技能创建 / 编辑 / 删除
    getSkillRaw,
    validateSkill,
    writeSkill,
    deleteSkill,
    // 插件配置 AI 助手
    getPluginConfig,
    resetPluginConfig,
    suggestPluginConfig,
    applyPluginConfigPatches,
    explainPluginConfig,
    generatePluginScaffold,
    writePluginScaffold,
    listPluginScaffolds,
    // 初始化
    initAll,
  }
})
