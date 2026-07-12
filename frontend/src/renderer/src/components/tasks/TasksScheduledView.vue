<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Timer,
  RotateCcw,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  Trash2,
  Plus,
  Repeat,
  CalendarDays,
  X
} from 'lucide-vue-next'
import type { ScheduledTaskInfo } from '../../stores/taskStream'
import type { ScheduledTask } from '../../types/workflow'

/** 数据库循环任务创建载荷 */
interface CreateDbTaskPayload {
  name: string
  schedule_cron: string
  schedule_type: 'cron' | 'interval' | 'once'
  action: string
  description: string | null
  context: string | null
  created_from: 'manual' | 'workflow' | 'normal_chat'
}

const props = defineProps<{
  scheduledTasks: ScheduledTaskInfo[]
  dbScheduledTasks: ScheduledTask[]
}>()

const emit = defineEmits<{
  refresh: []
  delete: [taskId: string]
  'create-db-task': [payload: CreateDbTaskPayload]
  'delete-db-task': [taskId: string]
  'refresh-db': []
}>()

const formatScheduledTime = (isoStr: string | null): string => {
  if (!isoStr) return '未知'
  try {
    const dt = new Date(isoStr)
    return dt.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return isoStr
  }
}

// ===== 循环任务创建表单 =====
type RepeatType = 'daily' | 'weekly' | 'monthly'

const WEEKDAY_OPTIONS = [
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' },
  { value: 0, label: '周日' }
]

const showCreateForm = ref(false)
const formError = ref('')

const form = ref({
  name: '',
  action: '',
  description: '',
  repeatType: 'daily' as RepeatType,
  time: '09:00',
  weeklyDay: 1,
  monthlyDay: 1
})

const resetForm = () => {
  form.value = {
    name: '',
    action: '',
    description: '',
    repeatType: 'daily',
    time: '09:00',
    weeklyDay: 1,
    monthlyDay: 1
  }
  formError.value = ''
}

const openCreateForm = () => {
  resetForm()
  showCreateForm.value = true
}

const closeCreateForm = () => {
  showCreateForm.value = false
  resetForm()
}

/** 根据表单字段构建 cron 表达式 */
const buildCronExpression = (): string => {
  const [hourStr, minuteStr] = form.value.time.split(':')
  const hour = hourStr || '9'
  const minute = minuteStr || '0'
  switch (form.value.repeatType) {
    case 'daily':
      return `${minute} ${hour} * * *`
    case 'weekly':
      return `${minute} ${hour} * * ${form.value.weeklyDay}`
    case 'monthly':
      return `${minute} ${hour} ${form.value.monthlyDay} * *`
    default:
      return `${minute} ${hour} * * *`
  }
}

/** 将 cron 表达式转为中文可读描述 */
const cronToChinese = (cron: string, scheduleType: string): string => {
  if (!cron || scheduleType === 'once') return '单次任务'
  if (scheduleType === 'interval') return '间隔执行'
  const parts = cron.trim().split(/\s+/)
  if (parts.length < 5) return cron
  const [minute, hour, dom, , dow] = parts
  const timeStr = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`
  if (dom !== '*' && dow === '*') {
    return `每月 ${dom} 日 ${timeStr}`
  }
  if (dom === '*' && dow !== '*') {
    const dowMap: Record<string, string> = {
      '0': '周日', '1': '周一', '2': '周二', '3': '周三',
      '4': '周四', '5': '周五', '6': '周六', '7': '周日'
    }
    return `每${dowMap[dow] || `周${dow}`} ${timeStr}`
  }
  if (dom === '*' && dow === '*') {
    return `每天 ${timeStr}`
  }
  return cron
}

const repeatPreview = computed(() => {
  return cronToChinese(buildCronExpression(), 'cron')
})

const validateForm = (): boolean => {
  if (!form.value.name.trim()) {
    formError.value = '请输入任务名称'
    return false
  }
  if (!form.value.action.trim()) {
    formError.value = '请输入执行指令'
    return false
  }
  if (!/^\d{1,2}:\d{2}$/.test(form.value.time)) {
    formError.value = '时间格式应为 HH:MM'
    return false
  }
  const [h, m] = form.value.time.split(':').map(Number)
  if (h < 0 || h > 23 || m < 0 || m > 59) {
    formError.value = '时间范围无效'
    return false
  }
  if (form.value.repeatType === 'monthly' && (form.value.monthlyDay < 1 || form.value.monthlyDay > 31)) {
    formError.value = '日期范围应为 1-31'
    return false
  }
  return true
}

const handleCreateTask = () => {
  if (!validateForm()) return
  emit('create-db-task', {
    name: form.value.name.trim(),
    schedule_cron: buildCronExpression(),
    schedule_type: 'cron',
    action: form.value.action.trim(),
    description: form.value.description.trim() || null,
    context: null,
    created_from: 'manual'
  })
  showCreateForm.value = false
  resetForm()
}

// ===== 来源标签映射 =====
const SOURCE_LABELS: Record<string, string> = {
  manual: '手动',
  workflow: '工作流',
  normal_chat: '对话'
}
</script>

<template>
  <div class="scheduled-section animate-slide-up" style="animation-delay: 70ms">
    <!-- 循环任务（数据库持久化） -->
    <div class="db-section">
      <div class="scheduled-header">
        <div class="scheduled-title">
          <Repeat :size="18" />
          <span>循环任务</span>
          <span class="scheduled-count">{{ dbScheduledTasks.length }}</span>
        </div>
        <div class="header-actions">
          <button class="scheduled-refresh-btn" @click="emit('refresh-db')">
            <RotateCcw :size="14" />
            刷新
          </button>
          <button class="create-btn" @click="openCreateForm">
            <Plus :size="14" />
            新建循环任务
          </button>
        </div>
      </div>

      <div v-if="dbScheduledTasks.length === 0" class="scheduled-empty db-empty">
        <Repeat :size="40" />
        <p>暂无循环任务</p>
        <span>创建每日/每周/每月循环任务，由数据库持久化存储</span>
      </div>

      <div v-else class="scheduled-list">
        <div
          v-for="task in dbScheduledTasks"
          :key="task.task_id"
          :class="['scheduled-card', 'db-card', { inactive: !task.is_active }]"
        >
          <div class="scheduled-card-header">
            <div class="scheduled-status-icon db-icon">
              <CalendarDays :size="16" />
            </div>
            <div class="scheduled-card-info">
              <div class="scheduled-card-title">{{ task.name }}</div>
              <div class="scheduled-card-meta">
                <span class="scheduled-type">{{ cronToChinese(task.schedule_cron, task.schedule_type) }}</span>
                <span class="source-tag">{{ SOURCE_LABELS[task.created_from] || task.created_from }}</span>
                <span v-if="!task.is_active" class="inactive-tag">已停用</span>
              </div>
            </div>
            <button class="scheduled-delete-btn" @click="emit('delete-db-task', task.task_id)">
              <Trash2 :size="14" />
            </button>
          </div>

          <div v-if="task.action" class="scheduled-card-desc">
            <span class="desc-label">指令：</span>{{ task.action }}
          </div>
          <div v-if="task.description" class="scheduled-card-desc">
            <span class="desc-label">描述：</span>{{ task.description }}
          </div>
          <div class="scheduled-card-meta footer-meta">
            <span>创建：{{ formatScheduledTime(task.created_at) }}</span>
            <span v-if="task.last_run_at">上次执行：{{ formatScheduledTime(task.last_run_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 创建循环任务表单 -->
    <div v-if="showCreateForm" class="create-form-overlay" @click.self="closeCreateForm">
      <div class="create-form">
        <div class="form-header">
          <div class="form-title">
            <Plus :size="18" />
            <span>新建循环任务</span>
          </div>
          <button class="form-close-btn" @click="closeCreateForm">
            <X :size="18" />
          </button>
        </div>

        <div class="form-body">
          <div class="form-field">
            <label class="form-label">任务名称 <span class="required">*</span></label>
            <input
              v-model="form.name"
              type="text"
              class="form-input"
              placeholder="例如：每日早报"
              maxlength="64"
            />
          </div>

          <div class="form-field">
            <label class="form-label">执行指令 <span class="required">*</span></label>
            <textarea
              v-model="form.action"
              class="form-input form-textarea"
              placeholder="AI 将执行的指令，例如：整理今日待办并生成早报"
              rows="3"
              maxlength="500"
            />
          </div>

          <div class="form-field">
            <label class="form-label">描述（可选）</label>
            <input
              v-model="form.description"
              type="text"
              class="form-input"
              placeholder="任务的补充说明"
              maxlength="200"
            />
          </div>

          <div class="form-field">
            <label class="form-label">循环频率</label>
            <div class="repeat-type-group">
              <button
                :class="['repeat-type-btn', { active: form.repeatType === 'daily' }]"
                @click="form.repeatType = 'daily'"
              >每天</button>
              <button
                :class="['repeat-type-btn', { active: form.repeatType === 'weekly' }]"
                @click="form.repeatType = 'weekly'"
              >每周</button>
              <button
                :class="['repeat-type-btn', { active: form.repeatType === 'monthly' }]"
                @click="form.repeatType = 'monthly'"
              >每月</button>
            </div>
          </div>

          <div class="form-row">
            <div class="form-field">
              <label class="form-label">执行时间</label>
              <input
                v-model="form.time"
                type="time"
                class="form-input"
              />
            </div>

            <div v-if="form.repeatType === 'weekly'" class="form-field">
              <label class="form-label">星期</label>
              <select v-model="form.weeklyDay" class="form-input">
                <option v-for="opt in WEEKDAY_OPTIONS" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </div>

            <div v-if="form.repeatType === 'monthly'" class="form-field">
              <label class="form-label">日期</label>
              <select v-model="form.monthlyDay" class="form-input">
                <option v-for="d in 31" :key="d" :value="d">{{ d }} 日</option>
              </select>
            </div>
          </div>

          <div class="form-preview">
            <Clock :size="14" />
            <span>预览：{{ repeatPreview }}</span>
          </div>

          <div v-if="formError" class="form-error">
            <AlertCircle :size="14" />
            <span>{{ formError }}</span>
          </div>
        </div>

        <div class="form-footer">
          <button class="form-cancel-btn" @click="closeCreateForm">取消</button>
          <button class="form-submit-btn" @click="handleCreateTask">
            <Plus :size="14" />
            创建任务
          </button>
        </div>
      </div>
    </div>

    <!-- 运行时任务（内存调度器） -->
    <div class="runtime-section">
      <div class="scheduled-header">
        <div class="scheduled-title">
          <Timer :size="18" />
          <span>运行时任务</span>
          <span class="scheduled-count">{{ scheduledTasks.length }}</span>
        </div>
        <button class="scheduled-refresh-btn" @click="emit('refresh')">
          <RotateCcw :size="14" />
          刷新
        </button>
      </div>

      <div v-if="scheduledTasks.length === 0" class="scheduled-empty runtime-empty">
        <Timer :size="40" />
        <p>暂无运行时任务</p>
        <span>主 Agent 可通过 create_scheduled_task 工具创建定时任务</span>
      </div>

      <div v-else class="scheduled-list">
        <div
          v-for="task in scheduledTasks"
          :key="task.id"
          :class="['scheduled-card', `status-${task.status}`]"
        >
          <div class="scheduled-card-header">
            <div class="scheduled-status-icon">
              <Loader2 v-if="task.status === 'running'" :size="16" class="spin-animation" />
              <CheckCircle2 v-else-if="task.status === 'completed'" :size="16" />
              <XCircle v-else-if="task.status === 'failed'" :size="16" />
              <Clock v-else-if="task.status === 'pending'" :size="16" />
              <AlertCircle v-else :size="16" />
            </div>
            <div class="scheduled-card-info">
              <div class="scheduled-card-title">{{ task.name }}</div>
              <div class="scheduled-card-meta">
                <span class="scheduled-type">{{ task.task_type }}</span>
                <span v-if="task.next_run_time" class="scheduled-next">
                  下次: {{ formatScheduledTime(task.next_run_time) }}
                </span>
                <span v-if="task.last_run_time" class="scheduled-last">
                  上次: {{ formatScheduledTime(task.last_run_time) }}
                </span>
              </div>
            </div>
            <button class="scheduled-delete-btn" @click="emit('delete', task.id)">
              <Trash2 :size="14" />
            </button>
          </div>

          <div v-if="task.description" class="scheduled-card-desc">{{ task.description }}</div>

          <div v-if="task.last_result" class="scheduled-card-result">
            <div class="scheduled-result-label">
              <CheckCircle2 :size="12" />
              <span>执行结果</span>
            </div>
            <div class="scheduled-result-content">{{ task.last_result }}</div>
          </div>

          <div v-if="task.last_error" class="scheduled-card-error">
            <div class="scheduled-error-label">
              <XCircle :size="12" />
              <span>错误信息</span>
            </div>
            <div class="scheduled-error-content">{{ task.last_error }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scheduled-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  overflow: hidden;
}

.db-section,
.runtime-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.scheduled-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-1);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.scheduled-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text);
}

.scheduled-count {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-muted);
  padding: 2px var(--space-2);
  background: var(--workspace-hover);
  border-radius: var(--radius-full);
}

.scheduled-refresh-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-muted);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-leave) var(--ease-in-out);
}

.scheduled-refresh-btn:hover {
  color: var(--text);
  background: var(--workspace-hover);
}

.create-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px var(--space-3);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--lumi-brand, var(--text));
  background: var(--workspace-card);
  border: 1px solid var(--lumi-brand, var(--workspace-border));
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-leave) var(--ease-in-out);
}

.create-btn:hover {
  background: var(--workspace-hover);
}

.scheduled-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-6) var(--space-2);
  color: var(--text-muted);
}

.db-empty {
  min-height: 140px;
}

.runtime-empty {
  flex: 1;
  min-height: 200px;
}

.scheduled-empty p {
  font-size: var(--text-md);
  font-weight: 500;
  margin: var(--space-2) 0 0;
}

.scheduled-empty span {
  font-size: var(--text-sm);
}

.scheduled-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: var(--space-1);
  max-height: 480px;
  overflow-y: auto;
}

.runtime-section .scheduled-list {
  max-height: none;
}

.scheduled-card {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  padding: 14px var(--space-4);
  transition: border-color var(--duration-leave) var(--ease-in-out);
}

.db-card {
  border-left: 3px solid var(--lumi-brand, var(--workspace-border));
}

.db-card.inactive {
  opacity: 0.6;
}

.scheduled-card.status-running {
  border-color: var(--lumi-brand);
}

.scheduled-card.status-failed {
  border-color: var(--lumi-danger);
}

.scheduled-card.status-completed {
  border-color: var(--lumi-success);
}

.scheduled-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.scheduled-status-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-6);
  height: var(--space-6);
  flex-shrink: 0;
}

.db-icon {
  color: var(--lumi-brand, var(--text-muted));
}

.scheduled-status-icon .spin-animation {
  animation: spin 1s linear infinite;
  color: var(--lumi-brand);
}

.status-completed .scheduled-status-icon {
  color: var(--lumi-success);
}

.status-failed .scheduled-status-icon {
  color: var(--lumi-danger);
}

.status-pending .scheduled-status-icon {
  color: var(--text-muted);
}

.scheduled-card-info {
  flex: 1;
  min-width: 0;
}

.scheduled-card-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text);
  margin-bottom: var(--space-1);
}

.scheduled-card-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-muted);
  flex-wrap: wrap;
}

.scheduled-type {
  padding: 1px 6px;
  background: var(--workspace-hover);
  border-radius: 4px;
  font-family: var(--font-mono);
}

.source-tag {
  padding: 1px 6px;
  background: var(--workspace-hover);
  border-radius: 4px;
  font-size: var(--text-xs);
}

.inactive-tag {
  padding: 1px 6px;
  background: var(--lumi-danger-light, var(--workspace-hover));
  color: var(--lumi-danger, var(--text-muted));
  border-radius: 4px;
}

.footer-meta {
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px dashed var(--workspace-border);
  font-size: var(--text-xs);
}

.desc-label {
  font-weight: 600;
  color: var(--text-muted);
}

.scheduled-delete-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-in-out);
}

.scheduled-delete-btn:hover {
  color: var(--lumi-danger);
  background: var(--workspace-hover);
}

.scheduled-card-desc {
  margin-top: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: 1.5;
  word-break: break-word;
}

.scheduled-card-result,
.scheduled-card-error {
  margin-top: 10px;
  padding: var(--space-2) 10px;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
}

.scheduled-card-result {
  background: var(--lumi-success-light);
  border-left: 2px solid var(--lumi-success);
}

.scheduled-card-error {
  background: var(--lumi-danger-light);
  border-left: 2px solid var(--lumi-danger);
}

.scheduled-result-label,
.scheduled-error-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-weight: 600;
  margin-bottom: var(--space-1);
}

.scheduled-result-label {
  color: var(--lumi-success);
}

.scheduled-error-label {
  color: var(--lumi-danger);
}

.scheduled-result-content,
.scheduled-error-content {
  color: var(--text);
  line-height: 1.5;
  max-height: 120px;
  overflow-y: auto;
  word-break: break-word;
  white-space: pre-wrap;
}

/* ===== 创建表单 ===== */
.create-form-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fade-in var(--duration-enter) var(--ease-in-out);
}

.create-form {
  width: 480px;
  max-width: 90vw;
  max-height: 85vh;
  background: var(--workspace-bg, var(--workspace-card));
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slide-up var(--duration-enter) var(--ease-in-out);
}

.form-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--workspace-border);
}

.form-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text);
}

.form-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-in-out);
}

.form-close-btn:hover {
  color: var(--text);
  background: var(--workspace-hover);
}

.form-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-row {
  display: flex;
  gap: var(--space-3);
}

.form-row .form-field {
  flex: 1;
}

.form-label {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text);
}

.required {
  color: var(--lumi-danger);
}

.form-input {
  padding: 8px var(--space-3);
  font-size: var(--text-sm);
  color: var(--text);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-sm);
  outline: none;
  transition: border-color var(--duration-fast) var(--ease-in-out);
  font-family: inherit;
}

.form-input:focus {
  border-color: var(--lumi-brand);
}

.form-textarea {
  resize: vertical;
  min-height: 60px;
  font-family: inherit;
}

.repeat-type-group {
  display: flex;
  gap: var(--space-2);
}

.repeat-type-btn {
  flex: 1;
  padding: 8px var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-muted);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-in-out);
}

.repeat-type-btn:hover {
  background: var(--workspace-hover);
}

.repeat-type-btn.active {
  color: var(--lumi-brand);
  border-color: var(--lumi-brand);
  background: var(--workspace-hover);
}

.form-preview {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-muted);
  background: var(--workspace-hover);
  border-radius: var(--radius-sm);
}

.form-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  color: var(--lumi-danger);
  background: var(--lumi-danger-light);
  border-radius: var(--radius-sm);
}

.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--workspace-border);
}

.form-cancel-btn {
  padding: 8px var(--space-4);
  font-size: var(--text-sm);
  color: var(--text-muted);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-in-out);
}

.form-cancel-btn:hover {
  background: var(--workspace-hover);
}

.form-submit-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px var(--space-4);
  font-size: var(--text-sm);
  font-weight: 500;
  color: #fff;
  background: var(--lumi-brand);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: opacity var(--duration-fast) var(--ease-in-out);
}

.form-submit-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.form-submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slide-up {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
