/**
 * LuomiNest 工作流流程图状态
 *
 * 从 WorkflowView.vue 拆分：VueFlow 节点/边的构建、dagre 自动布局、节点选择。
 * 静态数据（NODE_TYPE_ICON / STATUS_ICON / STATUS_COLOR）以命名导出供子组件直接 import。
 */
import { shallowRef, watch, type Ref, type ShallowRef } from 'vue'
import type { Node, Edge, NodeMouseEvent } from '@vue-flow/core'
import dagre from 'dagre'
import {
  Bot,
  FileText,
  Cpu,
  Settings,
  MousePointerClick,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
} from 'lucide-vue-next'
import type { WorkflowSession } from '../types/workflow'

// ===== 静态图标/颜色映射 =====

export const NODE_TYPE_ICON: Record<string, typeof Cpu> = {
  input: MousePointerClick,
  agent: Bot,
  tool: Cpu,
  condition: Settings,
  output: FileText,
}

export const STATUS_ICON: Record<string, typeof Clock> = {
  pending: Clock,
  running: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
  cancelled: AlertTriangle,
  skipped: AlertTriangle,
}

export const STATUS_COLOR: Record<string, string> = {
  pending: 'var(--text-muted)',
  running: 'var(--lumi-info)',
  completed: 'var(--lumi-success)',
  failed: 'var(--lumi-danger)',
  cancelled: 'var(--text-muted)',
  skipped: 'var(--text-muted)',
}

// ===== dagre 布局 =====

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

// ===== 从会话构建流程图 =====

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

// ===== composable =====

export interface UseWorkflowFlowReturn {
  flowNodes: ShallowRef<Node[]>
  flowEdges: ShallowRef<Edge[]>
  selectedNode: ShallowRef<Node | null>
  handleNodeClick: (event: NodeMouseEvent) => void
  handlePaneClick: () => void
}

export const useWorkflowFlow = (currentDisplaySession: Ref<WorkflowSession | null>): UseWorkflowFlowReturn => {
  // 使用 shallowRef 而非 ref：VueFlow 的 Node/Edge 类型含 csstype 深层嵌套属性，
  // ref() 内部的 UnwrapNestedRefs 会触发 TS2589（类型实例化过深）。
  // flowNodes/flowEdges/selectedNode 都是整体替换（.value = ...），shallowRef 完全等价且性能更优。
  const flowNodes = shallowRef<Node[]>([])
  const flowEdges = shallowRef<Edge[]>([])

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
  const selectedNode = shallowRef<Node | null>(null)

  const handleNodeClick = (event: NodeMouseEvent): void => {
    selectedNode.value = event.node
  }

  const handlePaneClick = (): void => {
    selectedNode.value = null
  }

  return {
    flowNodes,
    flowEdges,
    selectedNode,
    handleNodeClick,
    handlePaneClick,
  }
}
