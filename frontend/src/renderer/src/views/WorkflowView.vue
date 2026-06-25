<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  Bot,
  Plus,
  Play,
  Square,
  Trash2,
  GripVertical,
  Settings,
  Sparkles,
  Zap,
  FileText,
  Globe,
  Cpu,
  MousePointerClick
} from 'lucide-vue-next'
import { useWorkflowStore } from '../stores/workflow'
import LumiButton from '../components/common/LumiButton.vue'
import LumiEmptyState from '../components/common/LumiEmptyState.vue'
import LumiInput from '../components/common/LumiInput.vue'
import { generateId } from '../utils/id'

const workflowStore = useWorkflowStore()

interface WorkflowNode {
  id: string
  name: string
  type: 'input' | 'agent' | 'tool' | 'condition' | 'output'
  icon: any
  color: string
  x: number
  y: number
  config?: Record<string, any>
}

interface WorkflowConnection {
  id: string
  from: string
  to: string
  label?: string
}

const nodes = ref<WorkflowNode[]>([])

const connections = ref<WorkflowConnection[]>([])

const isRunning = ref(false)
const selectedNode = ref<string | null>(null)
const showNodePanel = ref(false)

const agentTemplates = [
  { name: '代可行', desc: '主控Agent · 任务调度', color: 'var(--lumi-indigo)' },
  { name: '无言', desc: '撰写Agent · 文档生成', color: 'var(--lumi-amber)' },
  { name: '林且慢', desc: '审核Agent · 质量把控', color: 'var(--lumi-success)' },
  { name: '浏览器助手', desc: '工具Agent · 网页操作', color: 'var(--lumi-info)' },
  { name: '代码执行器', desc: '工具Agent · 运行代码', color: 'var(--task-purple)' }
]

const toolTemplates = [
  { name: '文件读写', icon: FileText, color: 'var(--lumi-accent)' },
  { name: '网页浏览', icon: Globe, color: 'var(--lumi-info)' },
  { name: 'LLM调用', icon: Cpu, color: 'var(--task-purple)' },
  { name: '智能搜索', icon: Zap, color: 'var(--lumi-success)' }
]

function selectNode(nodeId: string) {
  selectedNode.value = nodeId
  showNodePanel.value = true
}

function deselectNode() {
  selectedNode.value = null
  showNodePanel.value = false
}

function addNode(template: typeof agentTemplates[0]) {
  const newNode: WorkflowNode = {
    id: generateId('node'),
    name: template.name,
    type: 'agent',
    icon: Bot,
    color: template.color,
    x: 100 + Math.random() * 400,
    y: 80 + Math.random() * 280,
    config: {}
  }
  nodes.value.push(newNode)
}

function removeNode(nodeId: string) {
  const idx = nodes.value.findIndex(n => n.id === nodeId)
  if (idx > -1) nodes.value.splice(idx, 1)
  connections.value = connections.value.filter(c => c.from !== nodeId && c.to !== nodeId)
  if (selectedNode.value === nodeId) deselectNode()
}

function toggleRun() {
  isRunning.value = !isRunning.value
}

function getNodePos(nodeId: string): { x: number; y: number } {
  const node = nodes.value.find(n => n.id === nodeId)
  return node ? { x: node.x, y: node.y } : { x: 0, y: 0 }
}

// 模块图标映射
const MODULE_ICONS: Record<string, any> = {
  browser: Globe,
  schedule: Settings,
  memory: Cpu,
  console: FileText,
  smart_home: Zap,
  subagent: Bot,
}

const MODULE_COLORS: Record<string, string> = {
  browser: 'var(--lumi-info)',
  schedule: 'var(--lumi-amber)',
  memory: 'var(--task-purple)',
  console: 'var(--lumi-accent)',
  smart_home: 'var(--lumi-success)',
  subagent: 'var(--lumi-indigo)',
}

/**
 * 监听工作流 store 变化，自动在画布上创建流程节点
 * 当工作流引擎创建了执行计划（plan_created）后，自动生成对应的节点和连接
 */
watch(
  () => workflowStore.currentSession,
  (session) => {
    if (!session) return

    // 当计划创建后，生成画布节点
    if (session.plan && session.tasks.length > 0) {
      // 清除旧节点，添加输入节点
      nodes.value = [{
        id: 'node-input',
        name: '用户输入',
        type: 'input',
        icon: MousePointerClick,
        color: 'var(--lumi-brand)',
        x: 80,
        y: 200,
      }]
      connections.value = []

      const startX = 80
      const startY = 200

      session.tasks.forEach((task, idx) => {
        const module = task.tool_name.split('.')[0] || 'tool'
        const icon = MODULE_ICONS[module] || Cpu
        const color = MODULE_COLORS[module] || 'var(--lumi-indigo)'

        const nodeId = `wf-${task.task_id}`
        if (!nodes.value.find(n => n.id === nodeId)) {
          nodes.value.push({
            id: nodeId,
            name: task.title,
            type: 'tool',
            icon,
            color,
            x: startX + 200 + (idx % 3) * 200,
            y: startY + Math.floor(idx / 3) * 120 - 100,
            config: {
              tool_name: task.tool_name,
              status: task.status,
              task_type: task.task_type,
            },
          })

          // 创建连接：输入节点 → 第一个任务，任务间按依赖关系连接
          if (task.depends_on.length === 0) {
            connections.value.push({
              id: `conn-wf-${task.task_id}`,
              from: 'node-input',
              to: nodeId,
              label: '执行',
            })
          } else {
            for (const dep of task.depends_on) {
              connections.value.push({
                id: `conn-wf-${dep}-${task.task_id}`,
                from: `wf-${dep}`,
                to: nodeId,
                label: '依赖',
              })
            }
          }
        }
      })

      // 添加输出节点
      const lastTask = session.tasks[session.tasks.length - 1]
      if (lastTask) {
        const outputId = 'wf-output'
        if (!nodes.value.find(n => n.id === outputId)) {
          const lastNode = nodes.value[nodes.value.length - 1]
          nodes.value.push({
            id: outputId,
            name: '执行结果',
            type: 'output',
            icon: FileText,
            color: 'var(--lumi-accent)',
            x: lastNode.x + 200,
            y: lastNode.y,
          })
          connections.value.push({
            id: 'conn-wf-output',
            from: `wf-${lastTask.task_id}`,
            to: outputId,
            label: '输出',
          })
        }
      }
    }

    // 实时更新节点状态
    if (session.tasks.length > 0) {
      for (const task of session.tasks) {
        const node = nodes.value.find(n => n.id === `wf-${task.task_id}`)
        if (node && node.config) {
          node.config.status = task.status
        }
      }
    }

    // 工作流运行状态同步
    isRunning.value = workflowStore.isRunning
  },
  { deep: true }
)
</script>

<template>
  <div class="workflow-view">
    <div class="workflow-header">
      <div class="header-left">
        <h1 class="page-title">
          <Sparkles :size="20" />
          工作流画布
        </h1>
        <span class="page-subtitle">Multi-Agent 协作编排</span>
      </div>
      <div class="header-actions">
        <LumiButton variant="secondary" size="sm" title="设置">
          <template #icon>
            <Settings :size="15" />
          </template>
          配置
        </LumiButton>
        <LumiButton
          :variant="isRunning ? 'danger' : 'primary'"
          size="sm"
          :title="isRunning ? '停止' : '运行'"
          @click="toggleRun"
        >
          <template #icon>
            <component :is="isRunning ? Square : Play" :size="15" />
          </template>
          {{ isRunning ? '停止' : '运行' }}
        </LumiButton>
      </div>
    </div>

    <div class="workflow-body">
      <aside class="workflow-sidebar">
        <div class="sidebar-section">
          <div class="section-label">
            <Bot :size="14" />
            <span>Agent 节点</span>
          </div>
          <div class="template-list">
            <button
              v-for="tpl in agentTemplates"
              :key="tpl.name"
              class="template-item"
              @click="addNode(tpl)"
            >
              <span class="dot" :style="{ background: tpl.color }"></span>
              <span class="tpl-name">{{ tpl.name }}</span>
              <span class="tpl-desc">{{ tpl.desc }}</span>
            </button>
          </div>
        </div>

        <div class="sidebar-section">
          <div class="section-label">
            <Zap :size="14" />
            <span>工具节点</span>
          </div>
          <div class="template-list">
            <button
              v-for="tpl in toolTemplates"
              :key="tpl.name"
              class="template-item tool"
            >
              <component :is="tpl.icon" :size="14" :style="{ color: tpl.color }" />
              <span class="tpl-name">{{ tpl.name }}</span>
            </button>
          </div>
        </div>

        <div class="sidebar-footer">
          <LumiButton variant="outline" size="sm" block>
            <template #icon>
              <Plus :size="14" />
            </template>
            新建工作流
          </LumiButton>
        </div>
      </aside>

      <main class="canvas-area" @click.self="deselectNode">
        <LumiEmptyState
          v-if="nodes.length === 0"
          class="canvas-empty-state"
          icon="inbox"
          title="工作流画布"
          description="在主 Agent 工作台开启工作流模式后，执行计划将自动生成节点；也可以从左侧拖拽节点手动编排。"
          size="md"
        />
        <svg class="connections-layer">
          <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="var(--text-muted)" />
            </marker>
          </defs>
          <line
            v-for="conn in connections"
            :key="conn.id"
            :x1="getNodePos(conn.from).x + 70"
            :y1="getNodePos(conn.from).y + 30"
            :x2="getNodePos(conn.to).x"
            :y2="getNodePos(conn.to).y + 30"
            stroke="var(--text-muted)"
            stroke-width="1.5"
            marker-end="url(#arrowhead)"
            class="conn-line"
          />
          <text
            v-for="conn in connections"
            :key="'label-' + conn.id"
            :x="(getNodePos(conn.from).x + getNodePos(conn.to).x) / 2 + 35"
            :y="(getNodePos(conn.from).y + getNodePos(conn.to).y) / 2 + 24"
            class="conn-label"
          >{{ conn.label }}</text>
        </svg>

        <div
          v-for="node in nodes"
          :key="node.id"
          :class="['workflow-node', { selected: selectedNode === node.id, running: isRunning && node.type === 'agent' }]"
          :style="{ left: node.x + 'px', top: node.y + 'px' }"
          @click.stop="selectNode(node.id)"
        >
          <div class="node-drag-handle">
            <GripVertical :size="12" />
          </div>
          <div
            class="node-icon-wrap"
            :style="{
              background: `color-mix(in srgb, ${node.color} 8%, transparent)`,
              borderColor: selectedNode === node.id ? node.color : 'transparent'
            }"
          >
            <component :is="node.icon" :size="18" :style="{ color: node.color }" />
          </div>
          <div class="node-info">
            <span class="node-name">{{ node.name }}</span>
            <span class="node-type-badge">{{ node.type }}</span>
          </div>
          <button
            v-if="selectedNode === node.id"
            class="node-remove-btn"
            @click.stop="removeNode(node.id)"
            title="删除节点"
          >
            <Trash2 :size="12" />
          </button>
          <div class="node-port node-port-out"></div>
          <div class="node-port node-port-in"></div>
        </div>
      </main>

      <Transition name="panel-slide-right">
        <aside v-if="showNodePanel && selectedNode" class="node-config-panel">
          <div class="panel-header">
            <span class="panel-title">节点配置</span>
            <button class="panel-close" @click="deselectNode">&times;</button>
          </div>
          <div class="panel-body">
            <template v-for="node in nodes" :key="node.id">
              <div v-if="node.id === selectedNode" class="config-content">
                <div class="config-field">
                  <label>节点名称</label>
                  <LumiInput :model-value="node.name" size="sm" />
                </div>
                <div class="config-field">
                  <label>节点类型</label>
                  <select class="config-select">
                    <option value="agent" :selected="node.type === 'agent'">Agent</option>
                    <option value="tool" :selected="node.type === 'tool'">工具</option>
                    <option value="condition" :selected="node.type === 'condition'">条件判断</option>
                    <option value="output" :selected="node.type === 'output'">输出</option>
                  </select>
                </div>
                <div class="config-field">
                  <label>模型选择</label>
                  <div class="model-selector">
                    <button class="model-chip active">GPT-4o</button>
                    <button class="model-chip">Claude</button>
                    <button class="model-chip">DeepSeek</button>
                  </div>
                </div>
                <div class="config-field">
                  <label>Prompt 模板</label>
                  <textarea class="config-textarea" rows="4" placeholder="输入系统提示词..."></textarea>
                </div>
                <div class="config-field">
                  <label>输出格式</label>
                  <select class="config-select">
                    <option>文本</option>
                    <option>JSON</option>
                    <option>Markdown</option>
                  </select>
                </div>
                <div class="config-actions">
                  <LumiButton variant="primary" size="sm">
                    <template #icon>
                      <Play :size="13" />
                    </template>
                    单独运行
                  </LumiButton>
                </div>
              </div>
            </template>
          </div>
        </aside>
      </Transition>
    </div>
  </div>
</template>

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
  gap: var(--space-2);
}

.workflow-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.workflow-sidebar {
  width: 220px;
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

.template-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.template-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  text-align: left;
  transition: all var(--transition-fast);
  cursor: pointer;
}

.template-item:hover {
  background: var(--workspace-hover);
}

.template-item.tool {
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
}

.dot {
  width: var(--space-2);
  height: var(--space-2);
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.tpl-name {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
}

.tpl-desc {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  margin-left: auto;
}

.sidebar-footer {
  padding: var(--space-3);
  margin-top: auto;
}

.canvas-area {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: radial-gradient(circle at 1px 1px, var(--workspace-border) 1px, transparent 1px);
  background-size: var(--space-6) var(--space-6);
}

.canvas-empty-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.connections-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.conn-line {
  transition: stroke-width var(--duration-leave) var(--ease-in-out);
}

.conn-line:hover {
  stroke: var(--lumi-brand);
  stroke-width: 2.5;
}

.conn-label {
  font-size: var(--text-2xs);
  fill: var(--text-muted);
  pointer-events: none;
}

.workflow-node {
  position: absolute;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  min-width: 140px;
  background: var(--workspace-card);
  border: 1px solid transparent;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  cursor: grab;
  z-index: var(--z-base);
  transition: all var(--transition-normal);
  animation: lumi-scale-in var(--duration-normal) var(--ease-out-expo) both;
}

.workflow-node:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.workflow-node.selected {
  border-color: var(--lumi-brand);
  box-shadow: var(--shadow-glow-md);
}

.workflow-node.running .node-icon-wrap {
  animation: pulse-glow var(--duration-slow) var(--ease-in-out) infinite;
}

@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 0 0 var(--lumi-brand-border); }
  50% { box-shadow: 0 0 0 8px transparent; }
}

.node-drag-handle {
  opacity: 0.3;
  cursor: grab;
  color: var(--text-muted);
  transition: opacity var(--transition-fast);
}

.workflow-node:hover .node-drag-handle {
  opacity: 0.6;
}

.node-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid transparent;
  flex-shrink: 0;
  transition: all var(--transition-fast);
}

.node-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.node-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-type-badge {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  background: var(--workspace-panel);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-xs);
  width: fit-content;
}

.node-remove-btn {
  width: var(--space-6);
  height: var(--space-6);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  flex-shrink: 0;
  transition: all var(--transition-fast);
}

.node-remove-btn:hover {
  background: var(--task-red-soft);
  color: var(--lumi-danger);
}

.node-port {
  position: absolute;
  width: var(--space-3);
  height: var(--space-3);
  border-radius: var(--radius-full);
  border: 2px solid var(--workspace-border);
  background: var(--workspace-card);
  transition: all var(--transition-fast);
}

.node-port-out {
  right: -5px;
  top: 50%;
  transform: translateY(-50%);
}

.node-port-in {
  left: -5px;
  top: 50%;
  transform: translateY(-50%);
}

.workflow-node:hover .node-port {
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  transform: scale(1.3);
  transform-origin: center;
}

.node-port-out.workflow-node:hover .node-port-out {
  transform: translateY(-50%) scale(1.3);
}

.node-port-in.workflow-node:hover .node-port-in {
  transform: translateY(-50%) scale(1.3);
}

.node-config-panel {
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
  transition: all var(--transition-fast);
}

.panel-close:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.panel-body {
  padding: var(--space-4);
}

.config-field {
  margin-bottom: var(--space-4);
}

.config-field > label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.config-input,
.config-select {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  font-size: var(--text-base);
  color: var(--text-primary);
  transition: border-color var(--transition-fast);
}

.config-input:focus,
.config-select:focus {
  border-color: var(--lumi-brand);
}

.config-textarea {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  font-size: var(--text-sm);
  color: var(--text-primary);
  resize: vertical;
  min-height: calc(var(--space-8) * 1.5);
  line-height: var(--leading-normal);
  font-family: var(--font-sans);
}

.model-selector {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.model-chip {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--text-muted);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.model-chip.active {
  background: var(--lumi-brand-light);
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
}

.model-chip:hover {
  border-color: var(--lumi-brand);
}

.config-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.panel-slide-right-enter-active,
.panel-slide-right-leave-active {
  transition: all var(--transition-normal);
}

.panel-slide-right-enter-from,
.panel-slide-right-leave-to {
  opacity: 0;
  transform: translateX(var(--space-5));
  width: 0;
}

</style>
