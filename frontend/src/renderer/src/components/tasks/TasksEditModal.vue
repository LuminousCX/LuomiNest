<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  Plus,
  X,
  Type,
  Edit3,
  Flag,
  Circle,
  Calendar,
  Timer,
  Palette,
  Tag,
  Save,
  RotateCcw,
  Trash2,
  CheckCircle2
} from 'lucide-vue-next'
import type { LuomiNestTask, TaskPriority, TaskStatus } from './types'
import { formatDateStr } from './types'
import LumiModal from '../common/LumiModal.vue'
import LumiButton from '../common/LumiButton.vue'

interface SelectOption<T extends string> {
  value: T
  label: string
}

interface ColorOption {
  varName: string
  label: string
}

const props = defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  initialTask: LuomiNestTask | null
  priorityOptions: SelectOption<TaskPriority>[]
  statusOptions: SelectOption<TaskStatus>[]
  timeSlotOptions: string[]
  colorOptions: ColorOption[]
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  save: [task: LuomiNestTask]
  delete: [taskId: number]
}>()

const defaultTask: LuomiNestTask = {
  id: 0,
  title: '',
  desc: '',
  priority: 'medium',
  status: 'pending',
  dueDate: formatDateStr(new Date()),
  assignees: [],
  tags: [],
  progress: 0,
  colorVar: '--task-blue',
  timeSlot: '09:00 - 10:00'
}

const draft = ref<LuomiNestTask>({ ...defaultTask })
const newTagInput = ref('')

const cloneTask = (source: LuomiNestTask): LuomiNestTask => ({
  ...source,
  tags: [...source.tags],
  assignees: [...source.assignees]
})

const resetDraft = () => {
  if (props.mode === 'edit' && props.initialTask) {
    draft.value = cloneTask(props.initialTask)
  } else if (props.initialTask) {
    draft.value = { ...cloneTask(props.initialTask) }
  } else {
    draft.value = { ...defaultTask }
  }
  newTagInput.value = ''
}

watch(() => props.visible, (visible) => {
  if (visible) resetDraft()
})

const closeModal = () => {
  emit('update:visible', false)
}

const addTag = () => {
  const tag = newTagInput.value.trim()
  if (tag && !draft.value.tags.includes(tag)) {
    draft.value.tags.push(tag)
  }
  newTagInput.value = ''
}

const removeTag = (tag: string) => {
  draft.value.tags = draft.value.tags.filter(t => t !== tag)
}

const handleSave = () => {
  if (!draft.value.title.trim()) return
  if (!props.timeSlotOptions.includes(draft.value.timeSlot)) {
    draft.value.timeSlot = '待安排'
  }
  emit('save', { ...draft.value })
  closeModal()
}

const handleDelete = () => {
  emit('delete', draft.value.id)
  closeModal()
}

const modalTitle = props.mode === 'create' ? '创建新任务' : '编辑任务'
const submitLabel = props.mode === 'create' ? '创建任务' : '保存'
const modalIcon = props.mode === 'create' ? Plus : Edit3
</script>

<template>
  <LumiModal
    :visible="visible"
    :width="520"
    @update:visible="emit('update:visible', $event)"
  >
    <template #title>
      <span class="luomi-modal-title">
        <component :is="modalIcon" :size="18" />
        {{ modalTitle }}
      </span>
    </template>

    <div class="luomi-form-stack">
            <div class="luomi-form-group">
              <label class="luomi-form-label">
                <Type :size="13" />
                任务标题
              </label>
              <input
                v-model="draft.title"
                class="luomi-form-input"
                placeholder="输入任务标题..."
                @keydown.enter="handleSave"
              />
            </div>

            <div class="luomi-form-group">
              <label class="luomi-form-label">
                <Edit3 :size="13" />
                任务描述
              </label>
              <textarea
                v-model="draft.desc"
                class="luomi-form-textarea"
                placeholder="描述任务详情..."
                rows="3"
              ></textarea>
            </div>

            <div class="luomi-form-row">
              <div class="luomi-form-group luomi-form-half">
                <label class="luomi-form-label">
                  <Flag :size="13" />
                  优先级
                </label>
                <div class="luomi-form-select-group">
                  <button
                    v-for="opt in priorityOptions"
                    :key="opt.value"
                    :class="['luomi-select-chip', `priority-${opt.value}`, { active: draft.priority === opt.value }]"
                    @click="draft.priority = opt.value"
                  >
                    {{ opt.label }}
                  </button>
                </div>
              </div>

              <div class="luomi-form-group luomi-form-half">
                <label class="luomi-form-label">
                  <Circle :size="13" />
                  状态
                </label>
                <div class="luomi-form-select-group">
                  <button
                    v-for="opt in statusOptions"
                    :key="opt.value"
                    :class="['luomi-select-chip', `status-${opt.value}`, { active: draft.status === opt.value }]"
                    @click="draft.status = opt.value"
                  >
                    {{ opt.label }}
                  </button>
                </div>
              </div>
            </div>

            <div class="luomi-form-row">
              <div class="luomi-form-group luomi-form-half">
                <label class="luomi-form-label">
                  <Calendar :size="13" />
                  截止日期
                </label>
                <input
                  v-model="draft.dueDate"
                  class="luomi-form-input"
                  type="date"
                />
              </div>

              <div class="luomi-form-group luomi-form-half">
                <label class="luomi-form-label">
                  <Timer :size="13" />
                  时间段
                </label>
                <select v-model="draft.timeSlot" class="luomi-form-select">
                  <option v-for="slot in timeSlotOptions" :key="slot" :value="slot">{{ slot }}</option>
                </select>
              </div>
            </div>

            <div class="luomi-form-group">
              <label class="luomi-form-label">
                <Palette :size="13" />
                任务颜色
              </label>
              <div class="luomi-color-picker">
                <button
                  v-for="color in colorOptions"
                  :key="color.varName"
                  :class="['luomi-color-option', { active: draft.colorVar === color.varName }]"
                  :style="{ background: `var(${color.varName})` }"
                  @click="draft.colorVar = color.varName"
                >
                  <CheckCircle2 v-if="draft.colorVar === color.varName" :size="14" />
                </button>
              </div>
            </div>

            <div class="luomi-form-group">
              <label class="luomi-form-label">
                <Tag :size="13" />
                标签
              </label>
              <div class="luomi-tags-input">
                <span v-for="tag in draft.tags" :key="tag" class="luomi-tag-item">
                  {{ tag }}
                  <button @click="removeTag(tag)"><X :size="10" /></button>
                </span>
                <input
                  v-model="newTagInput"
                  class="luomi-tag-input"
                  placeholder="添加标签..."
                  @keydown.enter.prevent="addTag"
                />
              </div>
            </div>

            <div v-if="draft.status === 'progress'" class="luomi-form-group">
              <label class="luomi-form-label">
                进度: {{ draft.progress }}%
              </label>
              <input
                v-model.number="draft.progress"
                class="luomi-form-range"
                type="range"
                min="0"
                max="100"
                step="5"
              />
            </div>
          </div>

    <template #footer>
      <LumiButton variant="secondary" size="sm" @click="closeModal">
        <template #icon>
          <RotateCcw v-if="mode === 'create'" :size="14" />
        </template>
        取消
      </LumiButton>
      <LumiButton v-if="mode === 'edit'" variant="danger" size="sm" @click="handleDelete">
        <template #icon>
          <Trash2 :size="14" />
        </template>
        删除
      </LumiButton>
      <LumiButton variant="primary" size="sm" :disabled="!draft.title.trim()" @click="handleSave">
        <template #icon>
          <Save :size="14" />
        </template>
        {{ submitLabel }}
      </LumiButton>
    </template>
  </LumiModal>
</template>

<style scoped>
.luomi-modal-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--text-primary);
}

.luomi-form-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.luomi-form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.luomi-form-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
}

.luomi-form-input {
  padding: 9px var(--space-3);
  border-radius: var(--radius-md);
  background: var(--workspace-bg);
  border: 1px solid var(--workspace-border);
  color: var(--text-primary);
  font-size: var(--text-base);
  outline: none;
  transition: all var(--transition-fast);
  font-family: inherit;
}

.luomi-form-input:focus {
  border-color: var(--lumi-brand);
  box-shadow: 0 0 0 3px var(--lumi-brand-glow);
}

.luomi-form-input::placeholder {
  color: var(--text-muted);
}

.luomi-form-textarea {
  padding: 9px var(--space-3);
  border-radius: var(--radius-md);
  background: var(--workspace-bg);
  border: 1px solid var(--workspace-border);
  color: var(--text-primary);
  font-size: var(--text-base);
  outline: none;
  transition: all var(--transition-fast);
  font-family: inherit;
  resize: vertical;
  min-height: 60px;
}

.luomi-form-textarea:focus {
  border-color: var(--lumi-brand);
  box-shadow: 0 0 0 3px var(--lumi-brand-glow);
}

.luomi-form-textarea::placeholder {
  color: var(--text-muted);
}

.luomi-form-select {
  padding: 9px var(--space-3);
  border-radius: var(--radius-md);
  background: var(--workspace-bg);
  border: 1px solid var(--workspace-border);
  color: var(--text-primary);
  font-size: var(--text-base);
  outline: none;
  transition: all var(--transition-fast);
  font-family: inherit;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236B7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;
  padding-right: 30px;
}

.luomi-form-select:focus {
  border-color: var(--lumi-brand);
  box-shadow: 0 0 0 3px var(--lumi-brand-glow);
}

.luomi-form-row {
  display: flex;
  gap: var(--space-3);
}

.luomi-form-half {
  flex: 1;
}

.luomi-form-select-group {
  display: flex;
  gap: var(--space-1);
}

.luomi-select-chip {
  padding: 6px var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: 500;
  border: 1px solid var(--workspace-border);
  background: var(--workspace-bg);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.luomi-select-chip:hover {
  border-color: var(--text-muted);
}

.luomi-select-chip.active.priority-high {
  background: var(--task-red-soft);
  border-color: var(--task-red);
  color: var(--task-red);
}

.luomi-select-chip.active.priority-medium {
  background: var(--task-yellow-soft);
  border-color: var(--task-yellow);
  color: var(--task-yellow);
}

.luomi-select-chip.active.priority-low {
  background: var(--task-green-soft);
  border-color: var(--task-green);
  color: var(--task-green);
}

.luomi-select-chip.active.status-pending {
  background: var(--task-yellow-soft);
  border-color: var(--task-yellow);
  color: var(--task-yellow);
}

.luomi-select-chip.active.status-progress {
  background: var(--task-blue-soft);
  border-color: var(--task-blue);
  color: var(--task-blue);
}

.luomi-select-chip.active.status-done {
  background: var(--task-green-soft);
  border-color: var(--task-green);
  color: var(--task-green);
}

.luomi-color-picker {
  display: flex;
  gap: var(--space-2);
}

.luomi-color-option {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-sm);
  border: 2px solid transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-fast);
  color: var(--text-inverse);
}

.luomi-color-option:hover {
  transform: scale(1.1);
}

.luomi-color-option.active {
  border-color: var(--text-inverse);
  box-shadow: 0 0 0 2px var(--workspace-bg), var(--shadow-sm);
  transform: scale(1.1);
}

.luomi-tags-input {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: var(--space-2) 10px;
  border-radius: var(--radius-md);
  background: var(--workspace-bg);
  border: 1px solid var(--workspace-border);
  min-height: 38px;
  align-items: center;
  transition: all var(--transition-fast);
}

.luomi-tags-input:focus-within {
  border-color: var(--lumi-brand);
  box-shadow: 0 0 0 3px var(--lumi-brand-glow);
}

.luomi-tag-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: 3px var(--space-2);
  border-radius: 5px;
  background: var(--task-sky-soft);
  color: var(--task-sky);
  font-size: var(--text-xs);
  font-weight: 600;
}

.luomi-tag-item button {
  display: flex;
  align-items: center;
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  opacity: 0.6;
  transition: opacity var(--transition-fast);
}

.luomi-tag-item button:hover {
  opacity: 1;
}

.luomi-tag-input {
  flex: 1;
  min-width: 80px;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: var(--text-sm);
  outline: none;
  font-family: inherit;
}

.luomi-tag-input::placeholder {
  color: var(--text-muted);
}

.luomi-form-range {
  width: 100%;
  height: var(--space-1);
  border-radius: 2px;
  background: var(--workspace-panel);
  outline: none;
  appearance: none;
  cursor: pointer;
}

.luomi-form-range::-webkit-slider-thumb {
  appearance: none;
  width: var(--space-4);
  height: var(--space-4);
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
  border: 2px solid var(--surface);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
}

</style>
