<script setup lang="ts">
/**
 * LuomiNest 工作流页面
 *
 * 使用 VueFlow + dagre 渲染工作流流程图：
 * 1. 实时显示当前工作流会话的节点和依赖关系
 * 2. 支持从后端加载历史工作流会话
 * 3. 节点状态实时同步（pending/running/completed/failed）
 * 4. dagre 自动布局，左到右流向
 */
import { ref, computed, watch, onMounted } from 'vue'
import { VueFlow, type Node, type Edge, type NodeMouseEvent } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import dagre from 'dagre'
import {
  Sparkles,
  Play,
  Square,
  Settings,
  Bot,
  FileText,
  Cpu,
  Zap,
  MousePointerClick,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Workflow as WorkflowIcon,
} from 'lucide-vue-next'
import { useWorkflowStore } from '../stores/workflow'
import { useApi } from '../composables/useApi'
import LumiButton from '../components/common/LumiButton.vue'
import LumiEmptyState from '../components/common/LumiEmptyState.vue'
import type { WorkflowSession } from '../types/workflow'

const workflowStore = useWorkflowStore()
const { apiGet } = useApi()

// 历史工作流会话列表
const sessions = ref<WorkflowSession[]>([])
const isLoadingSessions = ref(false)
// 当前选中的会话 ID（null 表示显示 store 中的实时会话）
const selectedSessionId = ref<string | null>(null)

// VueFlow 节点和边
const flowNodes = ref<Node[]>([])
const flowEdges = ref<Edge[]>([])

// 模块图标映射
const NODE_TYPE_ICON: Record<string, any> = {
  input: MousePointerClick,
  agent: Bot,
  tool: Cpu,
  condition: Settings,
  output: FileText,
}

const STATUS_ICON: Record<string, any> = {
  pending: Clock,
  running: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
  cancelled: AlertTriangle,
  skipped: AlertTriangle,
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'var(--text-muted)',
  running: 'var(--lumi-info)',
  completed: 'var(--lumi-success)',
  failed: 'var(--lumi-danger)',
  cancelled: 'var(--text-muted)',
  skipped: 'var(--text-muted)',
}

/**
 * 使用 dagre 计算节点布局
 */
const layoutWithDagre = (nodes: Node[], edges: Edge[]): { nodes: Node[]; edges: Edge[] } => {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 60, ranksep: 140, marginx: 40, marginy: 40 })
  g.setDefaultEdgeLabel(() => ({}))

  const nodeWidth = 200
  const nodeHeight = 64

  nodes.forEach((node) => {
    g.setNode(node.id, { width: nodeWidth, height: nodeHeight })
  })
  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target)
  })

  dagre.layout(g)

  return {
    nodes: nodes.map((node) => {
      const dagreNode = g.node(node.id)
      return {
        ...node,
        position: {
          x: dagreNode.x - nodeWidth / 2,
          y: dagreNode.y - nodeHeight / 2,
        },
      }
    }),
    edges,
  }
}

/**
 * 从工作流会话构建 VueFlow 节点和边
 */
const buildFlowFromSession = (session: WorkflowSession | null): { nodes: Node[]; edges: Edge[] } => {
  if (!session || !session.tasks || session.tasks.length === 0) {
    return { nodes: [], edges: [] }
  }

  const nodes: Node[] = []
  const edges: Edge[] = []

  // 输入节点
  nodes.push({
    id: 'wf-input',
    type: 'wfNode',
    position: { x: 0, y: 0 },
    data: {
      label: '用户输入',
      nodeType: 'input',
      status: 'completed',
      toolName: '',
      description: session.user_message?.slice(0, 60) || '',
    },
  })

  // 构建 title → task_id 映射（兼容 depends_on 使用 title 的情况）
  const titleToId = new Map<string, string>()
  session.tasks.forEach((task) => {
    titleToId.set(task.title, task.task_id)
  })

  // 任务节点
  session.tasks.forEach((task) => {
    nodes.push({
      id: task.task_id,
      type: 'wfNode',
      position: { x: 0, y: 0 },
      data: {
        label: task.title,
        nodeType: task.node_type || 'tool',
        status: task.status,
        toolName: task.tool_name,
        description: task.description,
      },
    })

    // 依赖边
    if (!task.depends_on || task.depends_on.length === 0) {
      edges.push({
        id: `e-input-${task.task_id}`,
        source: 'wf-input',
        target: task.task_id,
        animated: task.status === 'running',
      })
    } else {
      task.depends_on.forEach((dep) => {
        // dep 可能是 task_id 或 title，统一解析为 task_id
        const sourceId = titleToId.has(dep) ? titleToId.get(dep)! : dep
        // 只在源节点存在时创建边
        if (session.tasks.some((t) => t.task_id === sourceId) || sourceId === 'wf-input') {
          edges.push({
            id: `e-${sourceId}-${task.task_id}`,
            source: sourceId,
            target: task.task_id,
            animated: task.status === 'running',
          })
        } else {
          // 找不到依赖源，连接到输入节点
          edges.push({
            id: `e-input-fallback-${task.task_id}`,
            source: 'wf-input',
            target: task.task_id,
            animated: task.status === 'running',
          })
        }
      })
    }
  })

  // 输出节点（只在工作流有最终结果或已完成时添加）
  if (session.phase === 'completed' || session.phase === 'synthesizing') {
    const lastTask = session.tasks[session.tasks.length - 1]
    if (lastTask) {
      nodes.push({
        id: 'wf-output',
        type: 'wfNode',
        position: { x: 0, y: 0 },
        data: {
          label: '执行结果',
          nodeType: 'output',
          status: session.phase === 'completed' ? 'completed' : 'running',
          toolName: '',
          description: session.final_result?.slice(0, 60) || '',
        },
      })
      edges.push({
        id: `e-${lastTask.task_id}-output`,
        source: lastTask.task_id,
        target: 'wf-output',
        animated: session.phase === 'synthesizing',
      })
    }
  }

  return layoutWithDagre(nodes, edges)
}

/**
 * 当前显示的会话（优先显示 store 中的实时会话，否则显示选中的历史会话）
 */
const currentDisplaySession = computed<WorkflowSession | null>(() => {
  if (workflowStore.currentSession && workflowStore.isRunning) {
    return {
      session_id: workflowStore.currentSession.session_id,
      user_message: '',
      phase: workflowStore.currentSession.phase,
      plan: workflowStore.currentSession.plan,
      tasks: workflowStore.currentSession.tasks,
      final_result: workflowStore.currentSession.final_result,
      error: workflowStore.currentSession.error,
      created_at: workflowStore.currentSession.created_at,
      completed_at: workflowStore.currentSession.completed_at,
      conversation_id: workflowStore.currentSession.conversation_id,
      stats: {
        total: workflowStore.currentSession.tasks.length,
        completed: workflowStore.currentSession.tasks.filter((t) => t.status === 'completed').length,
        failed: workflowStore.currentSession.tasks.filter((t) => t.status === 'failed').length,
      },
    }
  }
  // 显示选中的历史会话
  if (selectedSessionId.value) {
    return sessions.value.find((s) => s.session_id === selectedSessionId.value) || null
  }
  return null
})

// 监听会话变化，更新流程图
watch(
  currentDisplaySession,
  (session) => {
    const result = buildFlowFromSession(session)
    flowNodes.value = result.nodes
    flowEdges.value = result.edges
  },
  { deep: true, immediate: true }
)

// 选中节点
const selectedNode = ref<Node | null>(null)
const handleNodeClick = (event: NodeMouseEvent) => {
  selectedNode.value = event.node
}
const handlePaneClick = () => {
  selectedNode.value = null
}

// 加载历史工作流会话列表
const loadSessions = async () => {
  isLoadingSessions.value = true
  try {
    const data = await apiGet<{ sessions: WorkflowSession[] }>('/workflow/db/sessions?limit=20')
    sessions.value = data.sessions || []
  } catch (err) {
    console.error('[WorkflowView] 加载工作流会话列表失败:', err)
  } finally {
    isLoadingSessions.value = false
  }
}

// 选中历史会话
const selectSession = (sessionId: string) => {
  selectedSessionId.value = sessionId
}

// 返回实时会话视图
const showLiveSession = () => {
  selectedSessionId.value = null
}

// 工作流运行状态
const isRunning = computed(() => workflowStore.isRunning)

const toggleRun = () => {
  if (isRunning.value) {
    workflowStore.cancelWorkflow()
  }
}

// 进度统计
const progressStats = computed(() => {
  const session = currentDisplaySession.value
  if (!session) return { total: 0, completed: 0, failed: 0, progress: 0 }
  const total = session.tasks.length
  const completed = session.tasks.filter((t) => t.status === 'completed').length
  const failed = session.tasks.filter((t) => t.status === 'failed').length
  const progress = total === 0 ? 0 : Math.round((completed / total) * 100)
  return { total, completed, failed, progress }
})

// 格式化时间
const formatTime = (iso: string | null): string => {
  if (!iso) return '--'
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return '--'
  }
}

// 阶段中文标签
const PHASE_LABELS: Record<string, string> = {
  analyzing: '分析中',
  planning: '规划中',
  waiting_confirmation: '待确认',
  executing: '执行中',
  synthesizing: '综合中',
  completed: '已完成',
  failed: '已失败',
}

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
      <aside class="workflow-sidebar">
        <div class="sidebar-section">
          <div class="section-label">
            <Zap :size="14" />
            <span>实时工作流</span>
          </div>
          <button
            class="session-item"
            :class="{ active: selectedSessionId === null && workflowStore.currentSession } "
            @click="showLiveSession"
          >
            <div class="session-item-icon" :class="{ running: isRunning }">
              <Loader2 v-if="isRunning" :size="14" class="spin-animation" />
              <Play v-else :size="14" />
            </div>
            <div class="session-item-info">
              <span class="session-item-title">
                {{ workflowStore.currentSession ? '当前执行中' : '无实时工作流' }}
              </span>
              <span class="session-item-meta">
                {{ isRunning ? PHASE_LABELS[workflowStore.currentSession?.phase || ''] || '' : '空闲' }}
              </span>
            </div>
          </button>
        </div>

        <div class="sidebar-section sidebar-sessions">
          <div class="section-label">
            <Clock :size="14" />
            <span>历史工作流</span>
          </div>
          <div v-if="isLoadingSessions" class="loading-hint">
            <Loader2 :size="14" class="spin-animation" />
            <span>加载中...</span>
          </div>
          <div v-else-if="sessions.length === 0" class="empty-hint">
            暂无历史工作流
          </div>
          <div v-else class="session-list">
            <button
              v-for="session in sessions"
              :key="session.session_id"
              class="session-item"
              :class="{ active: selectedSessionId === session.session_id }"
              @click="selectSession(session.session_id)"
            >
              <div class="session-item-icon" :class="session.phase">
                <CheckCircle2 v-if="session.phase === 'completed'" :size="14" />
                <XCircle v-else-if="session.phase === 'failed'" :size="14" />
                <Loader2 v-else :size="14" class="spin-animation" />
              </div>
              <div class="session-item-info">
                <span class="session-item-title">{{ session.user_message?.slice(0, 30) || '未命名工作流' }}</span>
                <span class="session-item-meta">
                  {{ formatTime(session.created_at) }} · {{ session.stats.total }} 个任务
                </span>
              </div>
            </button>
          </div>
        </div>
      </aside>

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
                <component :is="STATUS_ICON[props.data.status] || Clock" :size="14" :class="{ 'spin-animation': props.data.status === 'running' }" />
              </div>
            </div>
          </template>

          <Background :gap="20" :size="1" pattern-color="var(--workspace-border)" />
          <Controls position="bottom-right" />
        </VueFlow>
      </main>

      <Transition name="panel-slide-right">
        <aside v-if="selectedNode" class="node-detail-panel">
          <div class="panel-header">
            <span class="panel-title">节点详情</span>
            <button class="panel-close" @click="selectedNode = null">&times;</button>
          </div>
          <div class="panel-body">
            <div class="detail-field">
              <label>节点名称</label>
              <div class="detail-value">{{ selectedNode.data.label }}</div>
            </div>
            <div class="detail-field">
              <label>节点类型</label>
              <div class="detail-badge" :class="`wf-node-${selectedNode.data.nodeType}`">{{ selectedNode.data.nodeType }}</div>
            </div>
            <div v-if="selectedNode.data.toolName" class="detail-field">
              <label>工具名称</label>
              <div class="detail-value detail-mono">{{ selectedNode.data.toolName }}</div>
            </div>
            <div v-if="selectedNode.data.description" class="detail-field">
              <label>描述</label>
              <div class="detail-value detail-desc">{{ selectedNode.data.description }}</div>
            </div>
            <div class="detail-field">
              <label>状态</label>
              <div class="detail-status" :style="{ color: STATUS_COLOR[selectedNode.data.status] }">
                <component :is="STATUS_ICON[selectedNode.data.status] || Clock" :size="14" :class="{ 'spin-animation': selectedNode.data.status === 'running' }" />
                <span>{{ selectedNode.data.status }}</span>
              </div>
            </div>
          </div>
        </aside>
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

.workflow-sidebar {
  width: 240px;
  background: var(--workspace-sidebar);
  border-right: 1px solid var(--workspace-border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow-y: auto;
}

.sidebar-section {
  padding: var(--space-4) var(--space-3);
  border-bottom: 1px solid var(--workspace-border);
}

.sidebar-sessions {
  flex: 1;
  overflow-y: auto;
}

.section-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--text-muted);
  margin-bottom: var(--space-3);
}

.session-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  text-align: left;
  transition: background var(--transition-fast, 0.15s ease-in-out);
  cursor: pointer;
  margin-bottom: var(--space-1);
}

.session-item:hover {
  background: var(--workspace-hover);
}

.session-item.active {
  background: var(--lumi-brand-light);
}

.session-item-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  background: var(--surface-hover);
  color: var(--text-muted);
  flex-shrink: 0;
}

.session-item-icon.running {
  color: var(--lumi-info);
}

.session-item-icon.completed {
  color: var(--lumi-success);
}

.session-item-icon.failed {
  color: var(--lumi-danger);
}

.session-item-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: 1;
}

.session-item-title {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-item-meta {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.loading-hint,
.empty-hint {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.session-list {
  display: flex;
  flex-direction: column;
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

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 节点详情面板 */
.node-detail-panel {
  width: 280px;
  background: var(--workspace-card);
  border-left: 1px solid var(--workspace-border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow-y: auto;
  z-index: 2;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4);
  border-bottom: 1px solid var(--workspace-border);
}

.panel-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
}

.panel-close {
  width: var(--space-6);
  height: var(--space-6);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  font-size: var(--text-2xl);
  color: var(--text-muted);
  transition: all var(--transition-fast, 0.15s ease-in-out);
}

.panel-close:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.panel-body {
  padding: var(--space-4);
}

.detail-field {
  margin-bottom: var(--space-4);
}

.detail-field > label {
  display: block;
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: var(--space-1);
}

.detail-value {
  font-size: var(--text-sm);
  color: var(--text-primary);
  word-break: break-word;
}

.detail-mono {
  font-family: var(--font-mono, monospace);
  font-size: var(--text-xs);
  background: var(--surface-hover);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
}

.detail-desc {
  color: var(--text-secondary);
  line-height: var(--leading-relaxed, 1.6);
}

.detail-badge {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: 500;
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.detail-status {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  font-weight: 500;
}

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
</style>
