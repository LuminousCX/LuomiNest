<script setup lang="ts">
/**
 * LuomiNest 工作流画布
 *
 * VueFlow + dagre 渲染工作流流程图。通过 2 个 composable 解耦关注点：
 * - useWorkflowSessions：历史会话列表、当前显示会话、进度统计、运行控制
 * - useWorkflowFlow：VueFlow 节点/边构建、dagre 布局、节点选择
 * 侧栏与节点详情面板拆分至 components/workflow/ 子组件。
 */
import { ref, onMounted } from 'vue'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { Square, Clock, Cpu, Workflow as WorkflowIcon } from 'lucide-vue-next'
import LumiButton from '../components/common/LumiButton.vue'
import LumiEmptyState from '../components/common/LumiEmptyState.vue'
import WorkflowSidebar from '../components/workflow/WorkflowSidebar.vue'
import WorkflowNodeDetail from '../components/workflow/WorkflowNodeDetail.vue'
import WorkflowTemplateList from '../components/workflow/WorkflowTemplateList.vue'
import { useWorkflowSessions } from '../composables/useWorkflowSessions'
import { useWorkflowFlow, NODE_TYPE_ICON, STATUS_ICON, STATUS_COLOR } from '../composables/useWorkflowFlow'
import { useWorkflowStore } from '../stores/workflow'
import type { WorkflowTemplate } from '../types/workflow'

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
  liveSessionId,
  toggleRun,
  progressStats,
  loadSessionDetail,
} = useWorkflowSessions()

// VueFlow 流程图（依赖 currentDisplaySession）
const {
  flowNodes,
  flowEdges,
  selectedNode,
  handleNodeClick,
  handlePaneClick,
} = useWorkflowFlow(currentDisplaySession)

// Tab 切换
const activeTab = ref<'sessions' | 'templates'>('sessions')

// 模板 Store
const workflowStore = useWorkflowStore()

onMounted(() => {
  loadSessions()
})

/** 选中历史会话时同时加载详情（含节点数据，渲染流程图） */
const handleSelectSession = (sessionId: string): void => {
  selectSession(sessionId)
  loadSessionDetail(sessionId)
}

/** 切换到模板 Tab 时自动加载模板列表 */
const switchToTemplates = (): void => {
  activeTab.value = 'templates'
  workflowStore.loadTemplates()
}

/** 运行模板 */
const handleRunTemplate = async (tpl: WorkflowTemplate): Promise<void> => {
  const sessionId = await workflowStore.runTemplate(tpl.template_id, {}, tpl.auto_approve ? true : null)
  if (sessionId) {
    // 切回会话 Tab 并刷新列表
    activeTab.value = 'sessions'
    loadSessions()
  }
}

/** 定时运行模板（简单弹窗输入 cron 表达式） */
const handleScheduleTemplate = async (tpl: WorkflowTemplate): Promise<void> => {
  const schedule = window.prompt('请输入定时表达式（cron 格式，如 "0 9 * * *" 表示每天9点）', '0 9 * * *')
  if (!schedule) return
  const taskId = await workflowStore.scheduleTemplate(tpl.template_id, schedule)
  if (taskId) {
    window.alert('定时任务已创建')
  }
}

/** 删除模板 */
const handleDeleteTemplate = async (tpl: WorkflowTemplate): Promise<void> => {
  if (!window.confirm(`确定要删除模板「${tpl.name}」吗？`)) return
  await workflowStore.deleteTemplate(tpl.template_id)
}
</script>

<template>
  <div class="workflow-view">
    <div class="workflow-header animate-fade-in">
      <div class="workflow-header__text">
        <h1 class="workflow-title">工作流画布</h1>
        <p class="workflow-desc">AI 任务编排与可视化</p>
      </div>
      <div class="workflow-header__actions">
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

    <!-- Tab 切换栏 -->
    <div class="workflow-tabs">
      <button
        class="workflow-tab"
        :class="{ active: activeTab === 'sessions' }"
        @click="activeTab = 'sessions'"
      >
        历史会话
      </button>
      <button
        class="workflow-tab"
        :class="{ active: activeTab === 'templates' }"
        @click="switchToTemplates"
      >
        模板
      </button>
    </div>

    <!-- 历史会话 Tab：三栏布局 -->
    <div v-show="activeTab === 'sessions'" class="workflow-body">
      <WorkflowSidebar
        :sessions="sessions"
        :is-loading-sessions="isLoadingSessions"
        :selected-session-id="selectedSessionId"
        :has-live-session="hasLiveSession"
        :is-running="isRunning"
        :live-phase="livePhase"
        :live-session-id="liveSessionId"
        @select-session="handleSelectSession"
        @show-live="showLiveSession"
      />

      <main class="canvas-area">
        <LumiEmptyState
          v-if="flowNodes.length === 0"
          class="canvas-empty-state"
          icon="inbox"
          title="工作流画布"
          description="在主 Agent 工作台开启专业模式后，AI 创建的执行计划将自动在此显示为流程图。"
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

    <!-- 模板 Tab：模板列表 -->
    <div v-if="activeTab === 'templates'" class="workflow-body">
      <WorkflowTemplateList
        :templates="workflowStore.templates"
        :templates-loading="workflowStore.templatesLoading"
        @run="handleRunTemplate"
        @schedule="handleScheduleTemplate"
        @delete="handleDeleteTemplate"
      />
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
  padding: var(--space-6) var(--space-7) var(--space-4);
  flex-shrink: 0;
}

.workflow-header__text {
  display: flex;
  flex-direction: column;
}

.workflow-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  line-height: 1.2;
}

.workflow-desc {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.workflow-header__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.workflow-tabs {
  display: flex;
  gap: var(--space-2);
  padding: 0 var(--space-7);
  margin-bottom: var(--space-3);
  flex-shrink: 0;
}

.workflow-tab {
  padding: var(--space-1) var(--space-4);
  border-radius: var(--radius-lg);
  font-size: var(--text-sm);
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast, 0.15s ease-in-out);
  background: var(--surface-hover);
  color: var(--text-muted);
}

.workflow-tab:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.workflow-tab.active {
  background: var(--lumi-brand);
  color: #fff;
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
  gap: var(--space-4);
  padding: 0 var(--space-7) var(--space-7);
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
