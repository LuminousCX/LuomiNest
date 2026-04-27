﻿<script setup lang="ts">
import { ref } from 'vue'
import {
  Plus,
  Calendar,
  CheckCircle2,
  Circle,
  Trash2,
  Edit3
} from 'lucide-vue-next'

const tasks = ref([
  {
    id: 1,
    title: '完成 Agent 对话模块设计',
    desc: '根据 SRS 文档实现沉浸式陪伴域的对话界面',
    priority: 'high' as const,
    status: 'done' as const,
    dueDate: '2026-04-08'
  },
  {
    id: 2,
    title: '浏览器内核集成',
    desc: '将 ima 风格浏览器视图嵌入桌面客户端',
    priority: 'high' as const,
    status: 'progress' as const,
    dueDate: '2026-04-09'
  },
  {
    id: 3,
    title: 'MCP 工具网关开发',
    desc: '实现标准化工具接入协议',
    priority: 'medium' as const,
    status: 'pending' as const,
    dueDate: '2026-04-12'
  },
  {
    id: 4,
    title: '三层记忆架构实现',
    desc: '工作记忆 + 情景记忆 + 语义记忆',
    priority: 'medium' as const,
    status: 'pending' as const,
    dueDate: '2026-04-15'
  },
  {
    id: 5,
    title: 'Live2D 皮套渲染',
    desc: 'Cubism 5 引擎集成与嘴型同步',
    priority: 'low' as const,
    status: 'pending' as const,
    dueDate: '2026-04-20'
  }
])

const stats = ref([
  { label: '进行中', value: 1, color: '#3b82f6' },
  { label: '已完成', value: 1, color: '#22c55e' },
  { label: '待处理', value: 3, color: '#f59e0b' }
])
</script>

<template>
  <div class="tasks-view">
    <div class="tasks-header animate-fade-in">
      <div>
        <h1 class="page-title">任务中心</h1>
        <p class="page-subtitle">管理你的 AI Agent 开发进度</p>
      </div>
      <button class="add-task-btn">
        <Plus :size="16" />
        新建任务
      </button>
    </div>

    <div class="stats-row animate-slide-up">
      <div
        v-for="stat in stats"
        :key="stat.label"
        class="stat-pill"
        :style="{ '--pill-color': stat.color }"
      >
        <span class="pill-dot"></span>
        <span class="pill-value">{{ stat.value }}</span>
        <span class="pill-label">{{ stat.label }}</span>
      </div>
    </div>

    <div class="task-list">
      <div
        v-for="(task, idx) in tasks"
        :key="task.id"
        :class="['task-card', `priority-${task.priority}`, `status-${task.status}`]"
        :style="{ animationDelay: `${idx * 70}ms` }"
        class="animate-slide-up"
      >
        <button class="task-check">
          <CheckCircle2 v-if="task.status === 'done'" :size="20" />
          <Circle v-else :size="20" />
        </button>
        <div class="task-body">
          <div class="task-top">
            <h3 class="task-title">{{ task.title }}</h3>
            <span :class="['priority-badge', task.priority]">
              {{ task.priority === 'high' ? '高' : task.priority === 'medium' ? '中' : '低' }}
            </span>
          </div>
          <p class="task-desc">{{ task.desc }}</p>
          <div class="task-meta">
            <span class="meta-item">
              <Calendar :size="13" />
              {{ task.dueDate }}
            </span>
            <span :class="['status-tag', task.status]">
              {{ task.status === 'done' ? '已完成' : task.status === 'progress' ? '进行中' : '待处理' }}
            </span>
          </div>
        </div>
        <div class="task-actions">
          <button class="action-btn" title="编辑"><Edit3 :size="14" /></button>
          <button class="action-btn danger" title="删除"><Trash2 :size="14" /></button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tasks-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow-y: auto;
  padding: 28px 32px;
}

.tasks-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 2px;
}

.add-task-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  border-radius: var(--radius-md);
  background: var(--lumi-primary);
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.add-task-btn:hover {
  background: var(--lumi-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(20, 126, 188, 0.25);
}

.stats-row {
  display: flex;
  gap: 10px;
  margin-bottom: 24px;
}

.stat-pill {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 8px 16px;
  border-radius: var(--radius-full);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  font-size: 13px;
}

.pill-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--pill-color);
}

.pill-value {
  font-weight: 700;
  color: var(--text-primary);
}

.pill-label {
  color: var(--text-muted);
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 18px 20px;
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-normal);
  position: relative;
  overflow: hidden;
}

.task-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
}

.task-card.priority-high::before { background: #ef4444; }
.task-card.priority-medium::before { background: #f59e0b; }
.task-card.priority-low::before { background: #22c55e; }

.task-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateX(2px);
}

.task-card.status-done {
  opacity: 0.65;
}

.task-card.status-done .task-title {
  text-decoration: line-through;
  color: var(--text-muted);
}

.task-check {
  color: var(--text-muted);
  padding: 2px;
  margin-top: 2px;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.task-check:hover {
  color: var(--lumi-primary);
}

.task-body {
  flex: 1;
  min-width: 0;
}

.task-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.task-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.priority-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.priority-badge.high {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}
.priority-badge.medium {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}
.priority-badge.low {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.task-desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.55;
  margin-bottom: 10px;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 14px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.status-tag {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.status-tag.done { background: rgba(34, 197, 94, 0.1); color: #16a34a; }
.status-tag.progress { background: rgba(59, 130, 246, 0.1); color: #2563eb; }
.status-tag.pending { background: rgba(245, 158, 11, 0.1); color: #d97706; }

.task-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity var(--transition-fast);
  flex-shrink: 0;
}

.task-card:hover .task-actions {
  opacity: 1;
}

.action-btn {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.action-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.action-btn.danger:hover {
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}
</style>
