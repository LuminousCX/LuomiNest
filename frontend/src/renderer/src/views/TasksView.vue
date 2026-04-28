﻿<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Plus,
  Search,
  Bell,
  Share2,
  Link,
  Filter,
  MoreHorizontal,
  CheckCircle2,
  Circle,
  Clock,
  Calendar,
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  Kanban,
  Table2,
  Trash2,
  Edit3,
  Image,
  Lock,
  Type,
  Palette,
  ChevronDown,
  Mic,
  Star,
  CheckSquare,
  Square
} from 'lucide-vue-next'

const currentView = ref('card')
const currentWeek = ref('1 Week')

const tasks = ref([
  {
    id: 1,
    title: '完成 Agent 对话模块设计',
    desc: '根据 SRS 文档实现沉浸式陪伴域的对话界面',
    priority: 'high' as const,
    status: 'done' as const,
    dueDate: '2026-04-08',
    assignees: ['https://picsum.photos/id/1001/40/40', 'https://picsum.photos/id/1002/40/40'],
    tags: ['UI/UX', '核心功能'],
    progress: 100,
    colorVar: '--task-yellow',
    dayIndex: 0,
    timeSlot: '10:15 - 12:15'
  },
  {
    id: 2,
    title: '浏览器内核集成',
    desc: '将 ima 风格浏览器视图嵌入桌面客户端',
    priority: 'high' as const,
    status: 'progress' as const,
    dueDate: '2026-04-09',
    assignees: ['https://picsum.photos/id/1003/40/40'],
    tags: ['嵌入式', 'Electron'],
    progress: 65,
    colorVar: '--task-blue',
    dayIndex: 0,
    timeSlot: '13:00 - 14:30'
  },
  {
    id: 3,
    title: 'MCP 工具网关开发',
    desc: '实现标准化工具接入协议',
    priority: 'medium' as const,
    status: 'pending' as const,
    dueDate: '2026-04-12',
    assignees: ['https://picsum.photos/id/1004/40/40', 'https://picsum.photos/id/1005/40/40', 'https://picsum.photos/id/1006/40/40'],
    tags: ['后端', '协议'],
    progress: 0,
    colorVar: '--task-purple',
    dayIndex: 1,
    timeSlot: '10:45 - 14:15'
  },
  {
    id: 4,
    title: '三层记忆架构实现',
    desc: '工作记忆 + 情景记忆 + 语义记忆',
    priority: 'medium' as const,
    status: 'pending' as const,
    dueDate: '2026-04-15',
    assignees: ['https://picsum.photos/id/1007/40/40'],
    tags: ['AI', '架构'],
    progress: 0,
    colorVar: '--task-pink',
    dayIndex: 3,
    timeSlot: '全天'
  },
  {
    id: 5,
    title: 'Live2D 皮套渲染',
    desc: 'Cubism 5 引擎集成与嘴型同步',
    priority: 'low' as const,
    status: 'pending' as const,
    dueDate: '2026-04-20',
    assignees: ['https://picsum.photos/id/1008/40/40', 'https://picsum.photos/id/1009/40/40'],
    tags: ['渲染', '动画'],
    progress: 0,
    colorVar: '--task-green',
    dayIndex: 2,
    timeSlot: '待安排'
  }
])

const subTasks = ref([
  { label: '需求分析', done: true },
  { label: '原型设计', done: true },
  { label: 'UI 设计', done: true },
  { label: '前端开发', done: false },
  { label: '联调测试', done: false }
])

const completedSubTasks = computed(() => subTasks.value.filter(t => t.done).length)

const teamMembers = ref([
  'https://picsum.photos/id/1001/40/40',
  'https://picsum.photos/id/1002/40/40',
  'https://picsum.photos/id/1003/40/40',
  'https://picsum.photos/id/1004/40/40'
])

const colors = ref([
  { varName: '--task-pink', active: true },
  { varName: '--task-yellow', active: false },
  { varName: '--task-blue', active: false },
  { varName: '--task-purple', active: false },
  { varName: '--task-green', active: false }
])

const calendarDays = ref([
  { date: 26, weekday: 'Mon', label: '周一' },
  { date: 27, weekday: 'Tue', label: '周二' },
  { date: 28, weekday: 'Wed', label: '周三' },
  { date: 29, weekday: 'Thu', label: '周四' }
])

const timeSlots = ref(['10:00', '11:00', '12:00', '13:00', '14:00'])

const statusLabel = (s: string) => {
  const map: Record<string, string> = { done: '已完成', progress: '进行中', pending: '待处理' }
  return map[s] || s
}

const getDayTasks = (dayIdx: number) => {
  return tasks.value.filter(t => t.dayIndex === dayIdx)
}
</script>

<template>
  <div class="tasks-view">
    <!-- 顶部 Header -->
    <header class="tasks-header animate-fade-in">
      <div class="header-left">
        <div class="project-indicator">
          <div class="indicator-dot"></div>
          <h1 class="page-title">LuomiNest 任务中心</h1>
        </div>
        <div class="team-avatars">
          <img v-for="(member, i) in teamMembers" :key="i" :src="member" class="avatar" alt="member" />
          <button class="avatar avatar-add">
            <Plus :size="12" />
          </button>
        </div>
        <span class="project-path">AI Agent / 前端 / 核心模块</span>
      </div>

      <div class="header-right">
        <div class="search-box">
          <Search :size="14" class="search-icon" />
          <input type="text" placeholder="搜索任务..." />
          <Mic :size="14" class="mic-icon" />
        </div>
        <button class="icon-btn">
          <Bell :size="16" />
          <span class="notification-dot"></span>
        </button>
        <button class="icon-btn">
          <Plus :size="16" />
        </button>
        <button class="action-btn">
          <Share2 :size="14" />
          分享
        </button>
        <button class="action-btn">
          <Link :size="14" />
          链接
        </button>
      </div>
    </header>

    <!-- 视图切换和工具栏 -->
    <div class="toolbar animate-slide-up">
      <div class="view-switcher">
        <button
          v-for="view in ['card', 'blocks', 'table']"
          :key="view"
          :class="['view-btn', { active: currentView === view }]"
          @click="currentView = view"
        >
          <LayoutGrid v-if="view === 'card'" :size="14" />
          <Kanban v-if="view === 'blocks'" :size="14" />
          <Table2 v-if="view === 'table'" :size="14" />
          {{ view === 'card' ? '卡片' : view === 'blocks' ? '看板' : '表格' }}
          <span v-if="view === 'card'" class="view-indicator"></span>
        </button>
      </div>

      <div class="toolbar-center">
        <button class="week-selector">
          {{ currentWeek }}
          <ChevronDown :size="12" />
        </button>
        <div class="date-nav">
          <button><ChevronLeft :size="14" /></button>
          <span class="current-date">2026年 4月</span>
          <button><ChevronRight :size="14" /></button>
        </div>
        <div class="last-update">
          <Clock :size="12" />
          30 分钟前
          <img src="https://picsum.photos/id/1010/30/30" class="update-avatar" alt="user" />
          <span>Sarah</span>
        </div>
      </div>
    </div>

    <!-- 日历视图区域 -->
    <div class="calendar-section animate-slide-up" style="animation-delay: 70ms">
      <!-- 日历头部：日期列 -->
      <div class="calendar-header-row">
        <div class="time-label-col">
          <span class="time-label-header"></span>
        </div>
        <div
          v-for="(day, idx) in calendarDays"
          :key="idx"
          class="calendar-day-header"
        >
          <div class="date-number">{{ String(day.date).padStart(2, '0') }}</div>
          <div class="date-weekday">{{ '/' }}{{ day.weekday }}</div>
        </div>
      </div>

      <!-- 日历主体：时间行 + 任务列 -->
      <div class="calendar-body">
        <!-- 左侧时间轴 -->
        <div class="time-axis">
          <div v-for="(slot, idx) in timeSlots" :key="idx" class="time-slot-label">
            {{ slot }}
          </div>
        </div>

        <!-- 右侧日期列内容 -->
        <div class="calendar-columns">
          <div
            v-for="(day, dayIdx) in calendarDays"
            :key="dayIdx"
            class="calendar-column"
            :class="{ 'has-tasks': getDayTasks(dayIdx).length > 0 }"
          >
            <!-- 该日的任务卡片列表 -->
            <div class="column-tasks">
              <div
                v-for="(task, tIdx) in getDayTasks(dayIdx)"
                :key="task.id"
                class="calendar-task-card"
                :class="[`status-${task.status}`]"
                :style="{ '--card-accent': `var(${task.colorVar})` }"
              >
                <!-- 卡片顶部装饰条 -->
                <div class="card-accent-bar"></div>

                <!-- 卡片头部标签和菜单 -->
                <div class="card-top-row">
                  <div class="card-tags">
                    <span v-for="tag in task.tags" :key="tag" class="card-tag">{{ tag }}</span>
                  </div>
                  <button class="card-menu"><MoreHorizontal :size="13" /></button>
                </div>

                <!-- 标题 -->
                <h3 class="card-title">{{ task.title }}</h3>

                <!-- 时间段 -->
                <p class="card-time">{{ task.timeSlot }}</p>

                <!-- 进度条（进行中的任务） -->
                <div v-if="task.status === 'progress'" class="progress-mini">
                  <div class="progress-bar-mini">
                    <div class="progress-fill-mini" :style="{ width: `${task.progress}%` }"></div>
                  </div>
                  <span class="progress-text">{{ task.progress }}%</span>
                </div>

                <!-- 子任务清单（第一个任务展示） -->
                <div v-if="task.id === 1" class="subtask-list">
                  <ul>
                    <li v-for="sub in subTasks" :key="sub.label" :class="{ done: sub.done }">
                      <CheckSquare v-if="sub.done" :size="11" />
                      <Square v-else :size="11" />
                      {{ sub.label }}
                    </li>
                  </ul>
                </div>

                <!-- 完成度（已完成任务） -->
                <div v-if="task.status === 'done'" class="completion-info">
                  <span>完成度 3/5</span>
                  <div class="completion-bar">
                    <div class="completion-fill" style="width: 60%"></div>
                  </div>
                </div>

                <!-- 底部信息 -->
                <div class="card-bottom">
                  <div class="bottom-left">
                    <span v-if="task.status !== 'done'" class="due-date">
                      <Calendar :size="11" /> {{ task.dueDate }}
                    </span>
                    <span :class="['status-badge', task.status]">
                      {{ statusLabel(task.status) }}
                    </span>
                  </div>
                  <div class="assignees-stack">
                    <img
                      v-for="(a, ai) in task.assignees.slice(0, 3)"
                      :key="ai"
                      :src="a"
                      class="assignee-avatar"
                      :style="{ zIndex: task.assignees.length - ai }"
                      alt=""
                    />
                  </div>
                </div>

                <!-- 悬浮操作按钮 -->
                <div class="card-actions">
                  <button class="action-chip" title="编辑"><Edit3 :size="11" /></button>
                  <button class="action-chip danger" title="删除"><Trash2 :size="11" /></button>
                </div>
              </div>

              <!-- 空白占位：添加新任务 -->
              <div v-if="dayIdx === 2 && getDayTasks(dayIdx).length === 0" class="add-task-placeholder">
                <button class="add-task-inner">
                  <div class="add-circle">
                    <Plus :size="18" />
                  </div>
                  <span class="add-text">添加新任务</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 统计概览 + 团队洞察 -->
    <div class="stats-overview animate-slide-up" style="animation-delay: 140ms">
      <div class="stat-pill" style="--pill-color: var(--task-blue)">
        <div class="pill-icon"><Clock :size="16" /></div>
        <div class="pill-content">
          <strong>{{ tasks.filter(t => t.status === 'progress').length }}</strong>
          <span>进行中</span>
        </div>
        <div class="pill-trend positive">↗</div>
      </div>
      <div class="stat-pill" style="--pill-color: var(--task-green)">
        <div class="pill-icon"><CheckCircle2 :size="16" /></div>
        <div class="pill-content">
          <strong>{{ tasks.filter(t => t.status === 'done').length }}</strong>
          <span>已完成</span>
        </div>
        <div class="pill-trend positive">↗</div>
      </div>
      <div class="stat-pill" style="--pill-color: var(--task-yellow)">
        <div class="pill-icon"><Circle :size="16" /></div>
        <div class="pill-content">
          <strong>{{ tasks.filter(t => t.status === 'pending').length }}</strong>
          <span>待处理</span>
        </div>
        <div class="pill-trend neutral">—</div>
      </div>
      <div class="insight-pill">
        <div class="insight-head">
          <span>团队效率</span>
          <span class="insight-growth">↗ +19.24%</span>
        </div>
        <div class="insight-grid">
          <div class="insight-cell">
            <small>Time Spent</small>
            <strong>9h <em>76%</em></strong>
          </div>
          <div class="insight-cell">
            <small>Tasks</small>
            <strong>10 <em>68%</em></strong>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部工具栏 -->
    <div class="bottom-toolbar animate-slide-up" style="animation-delay: 210ms">
      <div class="toolbar-left">
        <button class="filter-btn">
          <Filter :size="14" />
          筛选
        </button>
        <div class="color-filters">
          <span class="filter-label">颜色:</span>
          <button
            v-for="(color, idx) in colors"
            :key="idx"
            class="color-dot"
            :class="{ active: color.active }"
            :style="{ background: `var(${color.varName})` }"
          ></button>
          <button class="color-dot add-color">
            <Plus :size="10" />
          </button>
        </div>
      </div>

      <div class="toolbar-right">
        <button class="tool-btn"><Edit3 :size="14" /></button>
        <button class="tool-btn"><Lock :size="14" /></button>
        <button class="tool-btn"><Type :size="14" /></button>
        <button class="tool-btn"><Palette :size="14" /></button>
        <button class="tool-btn text-tool-btn">
          <Image :size="14" />
          添加图片
        </button>
        <button class="tool-btn delete-tool-btn">
          <Trash2 :size="14" />
          回收站
          <span class="delete-count">4</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ====== 基础容器 ====== */
.tasks-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow-y: auto;
  padding: 20px 28px;
  color: var(--text-primary);
}

/* ====== Header ====== */
.tasks-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--workspace-border);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.project-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.indicator-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--lumi-primary), var(--lumi-primary-soft));
  box-shadow: 0 0 8px var(--lumi-primary-glow);
}

.page-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.2px;
}

.team-avatars {
  display: flex;
  align-items: center;
}

.avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 2px solid var(--workspace-bg);
  margin-left: -7px;
  object-fit: cover;
}

.avatar:first-child {
  margin-left: 0;
}

.avatar-add {
  background: var(--workspace-card);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  border: 1px solid var(--workspace-border);
}

.avatar-add:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.project-path {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: 2px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-box {
  position: relative;
}

.search-box input {
  width: 200px;
  padding: 7px 30px 7px 32px;
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-primary);
  font-size: 12px;
  outline: none;
  transition: all var(--transition-fast);
}

.search-box input:focus {
  border-color: var(--lumi-primary-light);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.search-box input::placeholder {
  color: var(--text-muted);
}

.search-icon {
  position: absolute;
  left: 10px;
  color: var(--text-muted);
}

.mic-icon {
  position: absolute;
  right: 8px;
  color: var(--text-muted);
  cursor: pointer;
}

.icon-btn {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
}

.icon-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.notification-dot {
  position: absolute;
  top: 7px;
  right: 7px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--lumi-accent);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.action-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

/* ====== Toolbar ====== */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.view-switcher {
  display: flex;
  gap: 3px;
  padding: 3px;
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--workspace-border);
}

.view-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.view-btn:hover {
  color: var(--text-secondary);
  background: rgba(255,255,255,0.03);
}

.view-btn.active {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.view-indicator {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--task-yellow);
}

.toolbar-center {
  display: flex;
  align-items: center;
  gap: 16px;
}

.week-selector {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.week-selector:hover {
  background: var(--workspace-hover);
}

.date-nav {
  display: flex;
  align-items: center;
  gap: 10px;
}

.date-nav button {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.date-nav button:hover {
  background: var(--workspace-card);
  color: var(--text-primary);
}

.current-date {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.last-update {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--text-muted);
}

.update-avatar {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  object-fit: cover;
}

/* ====== 日历视图 ====== */
.calendar-section {
  margin-bottom: 18px;
}

.calendar-header-row {
  display: grid;
  grid-template-columns: 48px repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 12px;
  padding: 0 4px;
}

.time-label-col {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding-bottom: 8px;
}

.time-label-header {
  content: '';
}

.calendar-day-header {
  text-align: center;
  padding: 12px 0 8px;
}

.date-number {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.date-weekday {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

/* Calendar Body */
.calendar-body {
  display: grid;
  grid-template-columns: 48px repeat(4, 1fr);
  gap: 12px;
  min-height: 320px;
}

.time-axis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 8px 0;
}

.time-slot-label {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
  line-height: 1;
  padding: 4px 0;
}

.calendar-columns {
  display: contents;
}

.calendar-column {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0;
}

.column-tasks {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
}

/* ====== 日历任务卡片 ====== */
.calendar-task-card {
  position: relative;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  padding: 14px 16px;
  transition: all var(--transition-normal);
  overflow: hidden;
}

.calendar-task-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
  border-color: rgba(255,255,255,0.1);
}

.calendar-task-card:hover .card-actions {
  opacity: 1;
}

.card-accent-bar {
  position: absolute;
  top: 0;
  left: 16px;
  right: 16px;
  height: 3px;
  border-radius: 0 0 3px 3px;
  background: var(--card-accent);
  opacity: 0.85;
}

.card-top-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 10px;
  margin-top: 4px;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.card-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 5px;
  background: var(--task-purple-soft);
  color: var(--task-purple);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.card-menu {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.card-menu:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
  line-height: 1.35;
}

.card-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 10px;
}

/* Mini Progress Bar */
.progress-mini {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.progress-bar-mini {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: var(--workspace-panel);
  overflow: hidden;
}

.progress-fill-mini {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--card-accent), rgba(255,255,255,0.25));
  transition: width 0.5s ease-in-out;
}

.progress-text {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
}

/* Subtask List */
.subtask-list {
  margin-bottom: 10px;
  padding: 10px;
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
}

.subtask-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.subtask-list li {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.subtask-list li.done {
  color: var(--text-muted);
  text-decoration: line-through;
}

.subtask-list li svg {
  color: var(--card-accent);
  flex-shrink: 0;
}

.subtask-list li.done svg {
  color: var(--task-green);
}

/* Completion Info */
.completion-info {
  margin-bottom: 10px;
}

.completion-info > span {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.completion-bar {
  height: 4px;
  border-radius: 2px;
  background: var(--workspace-panel);
  overflow: hidden;
}

.completion-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--card-accent);
  transition: width 0.5s ease-in-out;
}

/* Card Bottom */
.card-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 10px;
  border-top: 1px solid var(--workspace-border);
}

.bottom-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.due-date {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  color: var(--text-muted);
}

.status-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 5px;
  letter-spacing: 0.3px;
}

.status-badge.done {
  background: var(--task-green-soft);
  color: var(--task-green);
}

.status-badge.progress {
  background: var(--task-blue-soft);
  color: var(--task-blue);
}

.status-badge.pending {
  background: var(--task-yellow-soft);
  color: var(--task-yellow);
}

.assignees-stack {
  display: flex;
  align-items: center;
}

.assignee-avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid var(--workspace-card);
  margin-left: -7px;
  object-fit: cover;
}

.assignee-avatar:first-child {
  margin-left: 0;
}

/* Card Actions */
.card-actions {
  position: absolute;
  top: 12px;
  right: 38px;
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.action-chip {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--workspace-hover);
  border: 1px solid var(--workspace-border);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.action-chip:hover {
  background: rgba(255,255,255,0.08);
  color: var(--text-primary);
}

.action-chip.danger:hover {
  background: var(--task-red-soft);
  color: var(--task-red);
}

/* Status for Cards */
.calendar-task-card.status-done {
  opacity: 0.85;
}

.calendar-task-card.status-done .card-title {
  text-decoration: line-through;
  color: var(--text-muted);
}

/* Add Task Placeholder */
.add-task-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed var(--workspace-border);
  border-radius: var(--radius-lg);
  min-height: 160px;
  transition: all var(--transition-normal);
}

.add-task-placeholder:hover {
  border-color: var(--lumi-primary-light);
  background: var(--lumi-primary-light);
}

.add-task-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
}

.add-circle {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--lumi-primary), var(--lumi-primary-soft));
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: var(--shadow-glow-sm);
  transition: all var(--transition-fast);
}

.add-task-inner:hover .add-circle {
  transform: scale(1.06);
  box-shadow: var(--shadow-glow-md);
}

.add-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ====== Stats Overview Row ====== */
.stats-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 18px;
}

.stat-pill {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-normal);
}

.stat-pill:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.pill-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.03);
  color: var(--pill-color);
}

.pill-content {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.pill-content strong {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.pill-content span {
  font-size: 11px;
  color: var(--text-muted);
}

.pill-trend {
  margin-left: auto;
  font-size: 14px;
  font-weight: 700;
}

.pill-trend.positive {
  color: var(--task-green);
}

.pill-trend.neutral {
  color: var(--text-muted);
}

/* Insight Pill */
.insight-pill {
  padding: 14px 16px;
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
}

.insight-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.insight-head span:first-child {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.insight-growth {
  font-size: 11px;
  color: var(--task-green);
  font-weight: 600;
}

.insight-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.insight-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.insight-cell small {
  font-size: 10px;
  color: var(--text-muted);
}

.insight-cell strong {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
}

.insight-cell em {
  font-style: normal;
  font-size: 11px;
  color: var(--task-green);
  font-weight: 500;
  margin-left: 4px;
}

/* ====== Bottom Toolbar ====== */
.bottom-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid var(--workspace-border);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 12px;
  border-radius: var(--radius-md);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.filter-btn:hover {
  background: var(--workspace-hover);
}

.color-filters {
  display: flex;
  align-items: center;
  gap: 7px;
}

.filter-label {
  font-size: 11px;
  color: var(--text-muted);
}

.color-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.color-dot.active {
  border-color: white;
  box-shadow: 0 0 0 2px var(--workspace-bg);
}

.color-dot:hover {
  transform: scale(1.12);
}

.add-color {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 5px;
}

.tool-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tool-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.text-tool-btn,
.delete-tool-btn {
  width: auto;
  padding: 0 10px;
  gap: 5px;
  font-size: 11px;
  font-weight: 500;
}

.delete-count {
  background: var(--task-red-soft);
  color: var(--task-red);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
}

/* Scrollbar */
.tasks-view::-webkit-scrollbar {
  width: 5px;
}

.tasks-view::-webkit-scrollbar-track {
  background: transparent;
}

.tasks-view::-webkit-scrollbar-thumb {
  background: var(--workspace-border);
  border-radius: 10px;
}

.tasks-view::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}
</style>
