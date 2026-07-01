/**
 * LuomiNest 智能无感跳转 Composable
 *
 * 在主 Agent 工具回调（browser_action / 工作流 module_action）触发时，
 * 自动将用户导航到对应页面（/browser 或 /workflow）。
 *
 * 防打断策略：
 * 1. 当前已在目标页 → 不跳（避免重复跳转）
 * 2. 流式响应中（chatStore.isStreaming || workflowStore.isRunning）→ 不跳
 * 3. 输入框聚焦中（input/textarea/contenteditable）→ 不跳
 *
 * 不可跳转时，调用 taskStreamStore.markPendingNavigation 显示侧边栏红点提示，
 * 用户手动点击后清除红点并正常跳转。
 */
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { useWorkflowStore } from '../stores/workflow'
import { useTaskStreamStore } from '../stores/taskStream'

export type NavigationTarget = 'browser' | 'workflow'

const TARGET_PATHS: Record<NavigationTarget, string> = {
  browser: '/browser',
  workflow: '/workflow',
}

/**
 * 检测当前是否有输入框聚焦（input / textarea / contenteditable）
 * 复用浏览器原生聚焦状态，避免新建重复状态
 */
const isInputActive = (): boolean => {
  const el = document.activeElement
  if (!el) return false
  const tag = el.tagName.toLowerCase()
  if (tag === 'input' || tag === 'textarea') return true
  if ((el as HTMLElement).isContentEditable) return true
  return false
}

export function useTaskNavigation() {
  const router = useRouter()
  const route = useRoute()
  const chatStore = useChatStore()
  const workflowStore = useWorkflowStore()
  const taskStreamStore = useTaskStreamStore()

  // 复用 WorkbenchView 的流式状态判定逻辑
  const isStreaming = computed(() => chatStore.isStreaming || workflowStore.isRunning)

  /**
   * 防打断策略：判断是否可以自动跳转到目标页
   */
  const canNavigate = (target: NavigationTarget): boolean => {
    const path = TARGET_PATHS[target]
    if (route.path === path) return false
    if (isStreaming.value) return false
    if (isInputActive()) return false
    return true
  }

  /**
   * 智能跳转：可跳则 router.push，不可跳则标记红点提示
   */
  const navigateToTask = (target: NavigationTarget): void => {
    if (canNavigate(target)) {
      router.push(TARGET_PATHS[target])
    } else {
      taskStreamStore.markPendingNavigation(target)
    }
  }

  return { navigateToTask, canNavigate, isStreaming }
}
