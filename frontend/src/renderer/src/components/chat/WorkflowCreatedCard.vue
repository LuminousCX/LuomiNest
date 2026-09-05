<script setup lang="ts">
/**
 * 工作流创建卡片
 *
 * 在对话气泡中显示"已创建工作流"字样，可点击跳转到工作流页面。
 * 当 AI 在专业模式下创建工作流计划时，此卡片会出现在助手消息中。
 */
import { Workflow, ChevronRight, ListChecks } from 'lucide-vue-next'

defineProps<{
  /** 工作流会话 ID */
  sessionId: string
  /** 子任务数量 */
  taskCount: number
}>()

const emit = defineEmits<{
  navigate: []
}>()
</script>

<template>
  <div
    class="workflow-created-card lumi-card"
    role="button"
    tabindex="0"
    @click="emit('navigate')"
    @keydown.enter="emit('navigate')"
  >
    <div class="card-icon">
      <Workflow :size="18" />
    </div>
    <div class="card-body">
      <div class="card-title">已创建工作流</div>
      <div class="card-meta">
        <ListChecks :size="12" />
        <span>{{ taskCount }} 个子任务</span>
      </div>
    </div>
    <div class="card-action">
      <span class="action-text">查看流程图</span>
      <ChevronRight :size="14" />
    </div>
  </div>
</template>

<style scoped>
.workflow-created-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  margin: var(--space-2) 0;
  background: var(--lumi-primary-light);
  border: 1px solid color-mix(in srgb, var(--lumi-primary) 25%, transparent);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-fast, 0.2s ease-in-out);
  user-select: none;
}

.workflow-created-card:hover {
  background: color-mix(in srgb, var(--lumi-primary) 12%, var(--surface));
  border-color: color-mix(in srgb, var(--lumi-primary) 40%, transparent);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.card-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--lumi-primary) 15%, transparent);
  color: var(--lumi-primary);
  flex-shrink: 0;
}

.card-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.card-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.card-action {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: var(--text-xs);
  color: var(--lumi-primary);
  font-weight: 500;
  flex-shrink: 0;
}

.action-text {
  white-space: nowrap;
}
</style>
