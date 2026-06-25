<script setup lang="ts">
import { computed } from 'vue'
import {
  Brain,
  Server,
  Radio,
  Cpu,
  ChevronRight,
} from 'lucide-vue-next'
import type { PlatformInstance } from '../../types'
import type { McpStatus, SubagentActivity } from './types'

const props = defineProps<{
  memoryFactCount: number
  memoryProfileName: string
  memorySummaryPreview: string
  mcpStatus: McpStatus
  platformInstances: PlatformInstance[]
  activePlatformCount: number
  subagentActivities: SubagentActivity[]
  collapsed: Record<string, boolean>
}>()

const emit = defineEmits<{
  'toggle-panel': [key: string]
}>()

const connectedMcpCount = computed(
  () => props.mcpStatus.servers.filter((s) => s.status === 'connected').length
)
</script>

<template>
  <div class="agent-panels">
    <!-- 记忆快览 -->
    <div class="agent-panel lumi-card">
      <div class="agent-panel-header" @click="emit('toggle-panel', 'memory')">
        <Brain :size="14" />
        <span class="agent-panel-title">记忆</span>
        <span class="agent-panel-badge">{{ memoryFactCount }}</span>
        <ChevronRight :size="14" class="agent-panel-chevron" :class="{ expanded: !collapsed.memory }" />
      </div>
      <Transition name="panel-slide">
        <div v-show="!collapsed.memory" class="agent-panel-body">
          <div class="memory-profile">
            <span class="memory-label">用户画像</span>
            <span class="memory-value">{{ memoryProfileName || '未设置' }}</span>
          </div>
          <div class="memory-summary">{{ memorySummaryPreview }}</div>
        </div>
      </Transition>
    </div>

    <!-- MCP 工具状态 -->
    <div class="agent-panel lumi-card">
      <div class="agent-panel-header" @click="emit('toggle-panel', 'mcp')">
        <Server :size="14" />
        <span class="agent-panel-title">MCP 工具</span>
        <span class="agent-panel-badge">{{ connectedMcpCount }}/{{ mcpStatus.servers.length }}</span>
        <ChevronRight :size="14" class="agent-panel-chevron" :class="{ expanded: !collapsed.mcp }" />
      </div>
      <Transition name="panel-slide">
        <div v-show="!collapsed.mcp" class="agent-panel-body">
          <div v-if="mcpStatus.servers.length === 0" class="panel-empty">未配置 MCP 服务器</div>
          <template v-else>
            <div
              v-for="server in mcpStatus.servers"
              :key="server.name"
              class="mcp-server-item"
            >
              <span class="mcp-server-dot" :class="server.status"></span>
              <span class="mcp-server-name">{{ server.name }}</span>
              <span class="mcp-server-tools">{{ server.tool_count }} 工具</span>
            </div>
            <div class="mcp-total">共 {{ mcpStatus.totalTools }} 个工具可用</div>
          </template>
        </div>
      </Transition>
    </div>

    <!-- 消息平台状态 -->
    <div class="agent-panel lumi-card">
      <div class="agent-panel-header" @click="emit('toggle-panel', 'platform')">
        <Radio :size="14" />
        <span class="agent-panel-title">消息平台</span>
        <span class="agent-panel-badge">{{ activePlatformCount }}/{{ platformInstances.length }}</span>
        <ChevronRight :size="14" class="agent-panel-chevron" :class="{ expanded: !collapsed.platform }" />
      </div>
      <Transition name="panel-slide">
        <div v-show="!collapsed.platform" class="agent-panel-body">
          <div v-if="platformInstances.length === 0" class="panel-empty">未配置消息平台</div>
          <template v-else>
            <div
              v-for="inst in platformInstances"
              :key="inst.id"
              class="platform-item"
            >
              <span class="platform-dot" :class="{ active: inst.status === 'running' }"></span>
              <span class="platform-name">{{ inst.name }}</span>
              <span class="platform-type">{{ inst.displayName }}</span>
            </div>
          </template>
        </div>
      </Transition>
    </div>

    <!-- 子 Agent 能力提示 -->
    <div class="agent-panel lumi-card">
      <div class="agent-panel-header" @click="emit('toggle-panel', 'subagent')">
        <Cpu :size="14" />
        <span class="agent-panel-title">子 Agent</span>
        <span class="agent-panel-badge">{{ subagentActivities.length }}</span>
        <ChevronRight :size="14" class="agent-panel-chevron" :class="{ expanded: !collapsed.subagent }" />
      </div>
      <Transition name="panel-slide">
        <div v-show="!collapsed.subagent" class="agent-panel-body">
          <div v-if="subagentActivities.length === 0" class="panel-empty">主 Agent 按需创建子 Agent</div>
          <template v-else>
            <div
              v-for="agent in subagentActivities"
              :key="agent.id"
              class="subagent-side-item"
            >
              <span class="subagent-side-dot" :class="agent.status"></span>
              <span class="subagent-side-task">{{ agent.task }}</span>
              <span class="subagent-side-depth">d{{ agent.depth }}</span>
            </div>
            <div class="mcp-total">共 {{ subagentActivities.length }} 个子 Agent</div>
          </template>
        </div>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.agent-panels {
  flex-shrink: 0;
  border-top: 1px solid var(--border-light);
  max-height: 40%;
  overflow-y: auto;
  padding: var(--space-2) var(--space-2) 0;
}

.agent-panel {
  margin-bottom: var(--space-2);
}

.agent-panel:last-child {
  margin-bottom: 0;
}

.agent-panel-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  transition: background-color var(--transition-fast);
}

.agent-panel-header:hover {
  background: var(--surface-hover);
}

.agent-panel-title {
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.agent-panel-badge {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  padding: var(--space-1);
  background: var(--surface-hover);
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.agent-panel-chevron {
  color: var(--text-muted);
  transition: transform var(--transition-fast);
  flex-shrink: 0;
}

.agent-panel-chevron.expanded {
  transform: rotate(90deg);
}

.agent-panel-body {
  padding: var(--space-2) var(--space-4) var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.panel-empty {
  color: var(--text-muted);
  font-size: var(--text-xs);
  padding: var(--space-1) 0;
}

.memory-profile {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.memory-label {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  flex-shrink: 0;
}

.memory-value {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--text-primary);
}

.memory-summary {
  font-size: var(--text-xs);
  color: var(--text-muted);
  line-height: var(--leading-normal);
  max-height: 60px;
  overflow-y: auto;
  word-break: break-word;
}

.mcp-server-item,
.platform-item,
.subagent-side-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) 0;
}

.mcp-server-dot,
.platform-dot,
.subagent-side-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--text-muted);
  flex-shrink: 0;
}

.mcp-server-dot.connected,
.platform-dot.active,
.subagent-side-dot.running {
  background: var(--lumi-success);
}

.mcp-server-dot.connecting {
  background: var(--lumi-warning);
}

.mcp-server-dot.error,
.mcp-server-dot.disconnected {
  background: var(--text-muted);
}

.subagent-side-dot.completed {
  background: var(--lumi-success);
}

.subagent-side-dot.failed {
  background: var(--lumi-danger);
}

.mcp-server-name,
.platform-name,
.subagent-side-task {
  flex: 1;
  font-size: var(--text-xs);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mcp-server-tools,
.platform-type,
.subagent-side-depth {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  flex-shrink: 0;
}

.mcp-total {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border-light);
}

.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: max-height var(--transition-normal), opacity var(--transition-fast);
  overflow: hidden;
}

.panel-slide-enter-from,
.panel-slide-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
