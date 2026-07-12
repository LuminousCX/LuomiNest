/**
 * LuomiNest 工作台侧边面板状态
 *
 * 从 WorkbenchView.vue 拆分：收纳历史折叠、MCP 状态、侧边面板折叠状态、
 * 记忆摘要预览、平台实例计数等布局与状态面板逻辑。
 */
import { ref, computed } from 'vue'
import { useMemoryStore } from '../stores/memory'
import { usePlatformStore } from '../stores/platform'
import { useApi } from './useApi'
import type { McpStatus, McpServerStatus } from '../components/workbench/types'

export const useWorkbenchSidebar = () => {
  const memoryStore = useMemoryStore()
  const platformStore = usePlatformStore()
  const { apiGet } = useApi()

  const isHistoryCollapsed = ref(false)
  const mcpStatus = ref<McpStatus>({ servers: [], totalTools: 0 })
  const sidePanelCollapsed = ref<Record<string, boolean>>({
    memory: true,
    mcp: true,
    platform: true,
    subagent: true,
  })

  const toggleSidePanel = (key: string): void => {
    sidePanelCollapsed.value = { ...sidePanelCollapsed.value, [key]: !sidePanelCollapsed.value[key] }
  }

  const fetchMcpStatus = async (): Promise<void> => {
    try {
      const result = await apiGet<{ servers: McpServerStatus[]; count: number }>('/mcp/servers')
      const servers = result.servers || []
      const totalTools = servers.reduce((sum, s) => sum + (s.tool_count || 0), 0)
      mcpStatus.value = { servers, totalTools }
    } catch {
      mcpStatus.value = { servers: [], totalTools: 0 }
    }
  }

  const memorySummaryPreview = computed(() => {
    const s = memoryStore.summaryContent
    if (!s) return '暂无摘要'
    return s.length > 120 ? s.slice(0, 120) + '...' : s
  })

  const activePlatformCount = computed(() => platformStore.activeInstances.length)

  return {
    isHistoryCollapsed,
    mcpStatus,
    sidePanelCollapsed,
    toggleSidePanel,
    fetchMcpStatus,
    memorySummaryPreview,
    activePlatformCount,
  }
}
