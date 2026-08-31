<script setup lang="ts">
/**
 * 工作流模板列表 - 展示可复用的工作流模板
 *
 * Props:
 * - templates: 模板数组
 * - templatesLoading: 是否正在加载
 *
 * Emits:
 * - run: 运行模板
 * - schedule: 定时运行模板
 * - delete: 删除模板
 */
import { Loader2, Play, Clock, Trash2 } from 'lucide-vue-next'
import type { WorkflowTemplate } from '../../types/workflow'
import { formatDateRelative } from '../../utils/format'

defineProps<{
  templates: WorkflowTemplate[]
  templatesLoading: boolean
}>()

defineEmits<{
  run: [template: WorkflowTemplate]
  schedule: [template: WorkflowTemplate]
  delete: [template: WorkflowTemplate]
}>()
</script>

<template>
  <div class="template-list">
    <div v-if="templatesLoading" class="template-loading">
      <Loader2 :size="20" class="spin-animation" />
      <span>加载中...</span>
    </div>
    <div v-else-if="templates.length === 0" class="template-empty">
      <p class="template-empty-title">暂无模板</p>
      <p class="template-empty-hint">在工作流执行过程中，点击「保存为模板」可创建可复用模板</p>
    </div>
    <div v-else class="template-grid">
      <div
        v-for="tpl in templates"
        :key="tpl.template_id"
        class="template-card"
      >
        <div class="template-card-header">
          <div class="template-card-info">
            <h3 class="template-card-name">{{ tpl.name }}</h3>
            <p class="template-card-desc">{{ tpl.description || '无描述' }}</p>
          </div>
          <span
            class="template-card-badge"
            :class="tpl.created_from === 'ai' ? 'badge-ai' : 'badge-user'"
          >
            {{ tpl.created_from === 'ai' ? 'AI 生成' : '用户创建' }}
          </span>
        </div>
        <div class="template-card-meta">
          <span>{{ formatDateRelative(tpl.updated_at) }}</span>
          <span class="meta-divider">·</span>
          <span>{{ tpl.auto_approve ? '免审批' : '需审批' }}</span>
        </div>
        <div class="template-card-actions">
          <button class="action-btn action-btn-primary" @click="$emit('run', tpl)">
            <Play :size="13" />
            <span>运行</span>
          </button>
          <button class="action-btn action-btn-secondary" @click="$emit('schedule', tpl)">
            <Clock :size="13" />
            <span>定时</span>
          </button>
          <button class="action-btn action-btn-danger" @click="$emit('delete', tpl)">
            <Trash2 :size="13" />
            <span>删除</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.template-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4) 0;
}

.template-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-12) 0;
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.template-empty {
  text-align: center;
  padding: var(--space-12) var(--space-4);
}

.template-empty-title {
  font-size: var(--text-lg);
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.template-empty-hint {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.template-grid {
  display: grid;
  gap: var(--space-3);
}

.template-card {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition-fast, 0.15s ease-in-out);
}

.template-card:hover {
  box-shadow: var(--shadow-md);
}

.template-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.template-card-info {
  min-width: 0;
  flex: 1;
}

.template-card-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
}

.template-card-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-top: var(--space-1);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.template-card-badge {
  flex-shrink: 0;
  font-size: var(--text-2xs);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-weight: 500;
  white-space: nowrap;
}

.badge-user {
  background: color-mix(in srgb, var(--lumi-brand) 12%, transparent);
  color: var(--lumi-brand);
}

.badge-ai {
  background: color-mix(in srgb, var(--lumi-indigo) 12%, transparent);
  color: var(--lumi-indigo);
}

.template-card-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.meta-divider {
  opacity: 0.5;
}

.template-card-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-sm);
  font-weight: 500;
  border-radius: var(--radius-md);
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast, 0.15s ease-in-out);
  line-height: 1.4;
}

.action-btn-primary {
  background: var(--lumi-brand);
  color: #fff;
}

.action-btn-primary:hover {
  background: color-mix(in srgb, var(--lumi-brand) 85%, #000);
}

.action-btn-secondary {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.action-btn-secondary:hover {
  background: var(--workspace-hover);
}

.action-btn-danger {
  background: transparent;
  color: var(--lumi-danger);
}

.action-btn-danger:hover {
  background: color-mix(in srgb, var(--lumi-danger) 8%, transparent);
}

.spin-animation {
  animation: spin 1.2s linear infinite;
}

button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}
</style>
