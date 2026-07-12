/**
 * LuomiNest 工作台工具调用与子 Agent 活动追踪
 *
 * 从 WorkbenchView.vue 拆分：收纳工具调用活动、子 Agent 活动的状态追踪与展开/折叠 UI 状态，
 * 以及 handleSubagentEvent 事件处理。供消息/工作流 composable 调用。
 */
import { ref } from 'vue'
import type { SubagentEvent } from '../types'
import type { ToolActivity, SubagentActivity } from '../components/workbench/types'

export const useWorkbenchSubAgents = () => {
  const toolActivities = ref<ToolActivity[]>([])
  const expandedToolOutputs = ref<Record<string, boolean>>({})
  const subagentActivities = ref<SubagentActivity[]>([])
  const expandedSubagents = ref<Record<string, boolean>>({})
  const expandedSubagentTools = ref<Record<string, boolean>>({})

  const toggleToolOutput = (id: string): void => {
    expandedToolOutputs.value = { ...expandedToolOutputs.value, [id]: !expandedToolOutputs.value[id] }
  }

  const toggleSubagent = (id: string): void => {
    expandedSubagents.value = { ...expandedSubagents.value, [id]: !expandedSubagents.value[id] }
  }

  const toggleSubagentTools = (id: string): void => {
    expandedSubagentTools.value = { ...expandedSubagentTools.value, [id]: !expandedSubagentTools.value[id] }
  }

  const handleSubagentEvent = (event: SubagentEvent): void => {
    const existing = subagentActivities.value.find((a) => a.id === event.subagent_id)

    if (event.status === 'started') {
      if (existing) {
        existing.status = 'running'
        existing.task = event.task
        existing.depth = event.depth
        existing.iteration = 0
        existing.toolCalls = []
        existing.progress = undefined
        existing.result = undefined
        existing.error = undefined
      } else {
        subagentActivities.value.push({
          id: event.subagent_id,
          task: event.task,
          depth: event.depth,
          status: 'running',
          iteration: 0,
          toolCalls: [],
        })
      }
      return
    }

    if (!existing) return

    if (event.status === 'running') {
      existing.status = 'running'
      if (event.iteration !== undefined) existing.iteration = event.iteration
      if (event.progress) existing.progress = event.progress

      if (event.tool_name) {
        if (event.tool_output !== undefined) {
          const lastCall = [...existing.toolCalls]
            .reverse()
            .find((c) => c.name === event.tool_name && c.status === 'running')
          if (lastCall) {
            lastCall.status = 'completed'
            lastCall.output = event.tool_output
          }
        } else {
          existing.toolCalls.push({
            name: event.tool_name,
            args: event.tool_args,
            status: 'running',
          })
        }
      }
      return
    }

    if (event.status === 'completed') {
      existing.status = 'completed'
      if (event.result) existing.result = event.result
      existing.progress = undefined
      for (const tc of existing.toolCalls) {
        if (tc.status === 'running') tc.status = 'completed'
      }
      return
    }

    if (event.status === 'failed') {
      existing.status = 'failed'
      if (event.error) existing.error = event.error
      existing.progress = undefined
      for (const tc of existing.toolCalls) {
        if (tc.status === 'running') tc.status = 'completed'
      }
    }
  }

  return {
    toolActivities,
    expandedToolOutputs,
    subagentActivities,
    expandedSubagents,
    expandedSubagentTools,
    toggleToolOutput,
    toggleSubagent,
    toggleSubagentTools,
    handleSubagentEvent,
  }
}
