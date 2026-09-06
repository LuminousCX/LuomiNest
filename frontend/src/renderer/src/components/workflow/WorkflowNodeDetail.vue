<script setup lang="ts">
/**
 * 工作流节点详情面板 - 显示选中节点的详细信息
 */
import { Clock } from 'lucide-vue-next'
import type { Node } from '@vue-flow/core'
import { STATUS_ICON, STATUS_COLOR } from '../../composables/useWorkflowFlow'

defineProps<{
  selectedNode: Node
}>()

defineEmits<{
  close: []
}>()
</script>

<template>
  <aside class="node-detail-panel">
    <div class="panel-header">
      <span class="panel-title">节点详情</span>
      <button class="panel-close" title="关闭" aria-label="关闭" @click="$emit('close')">&times;</button>
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
          <component
            :is="STATUS_ICON[selectedNode.data.status] || Clock"
            :size="14"
            :class="{ 'spin-animation': selectedNode.data.status === 'running' }"
          />
          <span>{{ selectedNode.data.status }}</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
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


button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}
</style>
