<script setup lang="ts">
/**
 * LuomiNest 工作流画布
 *
 * VueFlow + dagre 渲染工作流流程图。通过 2 个 composable 解耦关注点：
 * - useWorkflowSessions：历史会话列表、当前显示会话、进度统计、运行控制
 * - useWorkflowFlow：VueFlow 节点/边构建、dagre 布局、节点选择
 * 侧栏与节点详情面板拆分至 components/workflow/ 子组件。
 */
import { onMounted } from 'vue'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { Sparkles, Square, Clock, Cpu, Workflow as WorkflowIcon } from 'lucide-vue-next'
import LumiButton from '../components/common/LumiButton.vue'
import LumiEmptyState from '../components/common/LumiEmptyState.vue'
import WorkflowSidebar from '../components/workflow/WorkflowSidebar.vue'
import WorkflowNodeDetail from '../components/workflow/WorkflowNodeDetail.vue'
import { useWorkflowSessions } from '../composables/useWorkflowSessions'
import { useWorkflowFlow, NODE_TYPE_ICON, STATUS_ICON, STATUS_COLOR } from '../composables/useWorkflowFlow'

// 会话列表 + 当前会话 + 进度统计
const {
  sessions,
  isLoadingSessions,
  selectedSessionId,
  currentDisplaySession,
  loadSessions,
  selectSession,
  showLiveSession,
  isRunning,
  hasLiveSession,
  livePhase,
  toggleRun,
  progressStats,
} = useWorkflowSessions()

// VueFlow 流程图（依赖 currentDisplaySession）
const {
  flowNodes,
  flowEdges,
  selectedNode,
  handleNodeClick,
  handlePaneClick,
} = useWorkflowFlow(currentDisplaySession)

onMounted(() => {
  loadSessions()
})
</script>

<template>
  <div class="workflow-view">
    <div class="workflow-header">
      <div class="header-left">
        <h1 class="page-title">
          <Sparkles :size="20" />
          工作流画布
        </h1>
        <span class="page-subtitle">AI 任务编排与可视化</span>
      </div>
      <div class="header-actions">
        <div v-if="currentDisplaySession" class="session-progress">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: progressStats.progress + '%' }"></div>
          </div>
          <span class="progress-text">{{ progressStats.completed }}/{{ progressStats.total }}</span>
        </div>
        <LumiButton variant="secondary" size="sm" title="刷新会话列表" @click="loadSessions">
          <template #icon>
            <WorkflowIcon :size="15" />
          </template>
          刷新
        </LumiButton>
        <LumiButton
          v-if="isRunning"
          variant="danger"
          size="sm"
          title="停止工作流"
          @click="toggleRun"
        >
          <template #icon>
            <Square :size="15" />
          </template>
          停止
        </LumiButton>
      </div>
    </div>

    <div class="workflow-body">
      <WorkflowSidebar
        :sessions="sessions"
        :is-loading-sessions="isLoadingSessions"
        :selected-session-id="selectedSessionId"
        :has-live-session="hasLiveSession"
        :is-running="isRunning"
        :live-phase="livePhase"
        @select-session="selectSession"
        @show-live="showLiveSession"
      />

      <main class="canvas-area">
        <LumiEmptyState
          v-if="flowNodes.length === 0"
          class="canvas-empty-state"
          icon="inbox"
          title="工作流画布"
          description="在主 Agent 工作台开启标准或超长模式后，AI 创建的执行计划将自动在此显示为流程图。"
          size="md"
        />
        <VueFlow
          v-else
          v-model:nodes="flowNodes"
          v-model:edges="flowEdges"
          :default-viewport="{ zoom: 0.85 }"
          :min-zoom="0.3"
          :max-zoom="2"
          fit-view-on-init
          @node-click="handleNodeClick"
          @pane-click="handlePaneClick"
        >
          <template #node-wfNode="props">
            <div :class="['wf-node', `wf-node-${props.data.nodeType}`, `wf-status-${props.data.status}`]">
              <div class="wf-node-icon">
                <component :is="NODE_TYPE_ICON[props.data.nodeType] || Cpu" :size="16" />
              </div>
              <div class="wf-node-body">
                <div class="wf-node-title">{{ props.data.label }}</div>
                <div v-if="props.data.toolName" class="wf-tool-name">{{ props.data.toolName }}</div>
              </div>
              <div class="wf-node-status" :style="{ color: STATUS_COLOR[props.data.status] }">
                <component
                  :is="STATUS_ICON[props.data.status] || Clock"
                  :size="14"
                  :class="{ 'spin-animation': props.data.status === 'running' }"
                />
              </div>
            </div>
          </template>

          <Background :gap="20" :size="1" pattern-color="var(--workspace-border)" />
          <Controls position="bottom-right" />
        </VueFlow>
      </main>

      <Transition name="panel-slide-right">
        <WorkflowNodeDetail
          v-if="selectedNode"
          :selected-node="selectedNode"
          @close="selectedNode = null"
        />
      </Transition>
    </div>
  </div>
</template>

<style>
/* VueFlow 核心样式（全局，不能 scoped） */
@import '@vue-flow/core/dist/style.css';
@import '@vue-flow/core/dist/theme-default.css';
@import '@vue-flow/controls/dist/style.css';
</style>

<style scoped>
.workflow-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.workflow-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-6);
  border-bottom: 1px solid var(--workspace-border);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.page-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: var(--text-sm);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  font-weight: 500;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.session-progress {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: var(--surface-hover);
  border-radius: var(--radius-full);
}

.progress-bar {
  width: 80px;
  height: 6px;
  background: var(--divider-soft);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--lumi-success);
  border-radius: var(--radius-full);
  transition: width var(--transition-normal, 0.3s ease-in-out);
}

.progress-text {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: 500;
}

.workflow-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.canvas-area {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.canvas-empty-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
}

/* VueFlow 自定义节点样式 */
.wf-node {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  min-width: 160px;
  max-width: 220px;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: all var(--transition-fast, 0.15s ease-in-out);
}

.wf-node:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--lumi-brand);
}

.wf-node-input {
  border-left: 3px solid var(--lumi-brand);
}

.wf-node-agent {
  border-left: 3px solid var(--lumi-indigo);
}

.wf-node-tool {
  border-left: 3px solid var(--lumi-info);
}

.wf-node-condition {
  border-left: 3px solid var(--lumi-amber);
}

.wf-node-output {
  border-left: 3px solid var(--lumi-success);
}

.wf-status-running {
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--lumi-info) 30%, transparent);
}

.wf-status-failed {
  border-color: color-mix(in srgb, var(--lumi-danger) 50%, transparent);
}

.wf-node-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: var(--surface-hover);
  color: var(--text-secondary);
  flex-shrink: 0;
}

.wf-node-input .wf-node-icon {
  color: var(--lumi-brand);
}

.wf-node-agent .wf-node-icon {
  color: var(--lumi-indigo);
}

.wf-node-tool .wf-node-icon {
  color: var(--lumi-info);
}

.wf-node-condition .wf-node-icon {
  color: var(--lumi-amber);
}

.wf-node-output .wf-node-icon {
  color: var(--lumi-success);
}

.wf-node-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.wf-node-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wf-tool-name {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wf-node-status {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.spin-animation {
  animation: spin 1.2s linear infinite;
}

/* 节点详情面板过渡 */
.panel-slide-right-enter-active,
.panel-slide-right-leave-active {
  transition: all var(--transition-normal, 0.25s ease-in-out);
}

.panel-slide-right-enter-from,
.panel-slide-right-leave-to {
  opacity: 0;
  transform: translateX(var(--space-5, 20px));
  width: 0;
}

button:focus-visible,
.lumi-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}
</style>
