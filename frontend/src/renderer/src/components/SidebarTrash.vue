<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  ArrowLeft,
  SquareCheck,
  Trash2,
  Undo2,
  Check,
  MessageSquare,
  AlertTriangle,
} from 'lucide-vue-next'
import { useAgentStore } from '../stores/agent'
import { useChatStore } from '../stores/chat'
import { useChatTrashStore } from '../stores/chat-trash'
import type { TrashListItem } from '../types'

const emit = defineEmits<{
  (e: 'close'): void
}>()

const agentStore = useAgentStore()
const chatStore = useChatStore()
const chatTrashStore = useChatTrashStore()

const trashBatchMode = ref(false)
const trashSelectedIds = ref<Set<string>>(new Set())

const toggleTrashBatchMode = () => {
  trashBatchMode.value = !trashBatchMode.value
  if (!trashBatchMode.value) {
    trashSelectedIds.value = new Set()
  }
}

const toggleTrashSelect = (convId: string) => {
  const next = new Set(trashSelectedIds.value)
  if (next.has(convId)) {
    next.delete(convId)
  } else {
    next.add(convId)
  }
  trashSelectedIds.value = next
}

const selectAllTrash = () => {
  const allIds = chatTrashStore.trashItems.map((t: TrashListItem) => t.id)
  if (trashSelectedIds.value.size === allIds.length) {
    trashSelectedIds.value = new Set()
  } else {
    trashSelectedIds.value = new Set(allIds)
  }
}

const handleBatchRestore = async () => {
  if (trashSelectedIds.value.size === 0) return
  try {
    await chatTrashStore.batchRestore(Array.from(trashSelectedIds.value), agentStore.activeAgent?.id, () => chatStore.fetchConversations(agentStore.activeAgent?.id))
    trashSelectedIds.value = new Set()
    trashBatchMode.value = false
  } catch (e: unknown) {
    console.error('Failed to batch restore:', e)
  }
}

const handleBatchPermanentDelete = async () => {
  if (trashSelectedIds.value.size === 0) return
  showTrashConfirm.value = true
  trashConfirmAction.value = 'batch-permanent-delete'
}

const handleRestoreItem = async (convId: string) => {
  try {
    await chatTrashStore.restoreConversation(convId, agentStore.activeAgent?.id, () => chatStore.fetchConversations(agentStore.activeAgent?.id))
  } catch (e: unknown) {
    console.error('Failed to restore:', e)
  }
}

const handlePermanentDeleteItem = async (convId: string) => {
  showTrashConfirm.value = true
  trashConfirmAction.value = 'permanent-delete'
  trashConfirmTargetId.value = convId
}

const handleEmptyTrash = () => {
  showTrashConfirm.value = true
  trashConfirmAction.value = 'empty-trash'
}

const showTrashConfirm = ref(false)
const trashConfirmAction = ref('')
const trashConfirmTargetId = ref('')

const trashConfirmMessage = computed(() => {
  if (trashConfirmAction.value === 'empty-trash') return '确定要清空回收站吗？所有对话将被永久删除，无法恢复。'
  if (trashConfirmAction.value === 'batch-permanent-delete') return `确定要永久删除选中的 ${trashSelectedIds.value.size} 个对话吗？此操作无法撤销。`
  if (trashConfirmAction.value === 'permanent-delete') return '确定要永久删除这个对话吗？此操作无法撤销。'
  return ''
})

const handleTrashConfirm = async () => {
  try {
    if (trashConfirmAction.value === 'empty-trash') {
      await chatTrashStore.emptyTrash(agentStore.activeAgent?.id)
    } else if (trashConfirmAction.value === 'batch-permanent-delete') {
      await chatTrashStore.batchPermanentDelete(Array.from(trashSelectedIds.value), agentStore.activeAgent?.id)
      trashSelectedIds.value = new Set()
      trashBatchMode.value = false
    } else if (trashConfirmAction.value === 'permanent-delete') {
      await chatTrashStore.permanentDeleteConversation(trashConfirmTargetId.value, agentStore.activeAgent?.id)
    }
  } catch (e: unknown) {
    console.error('Failed to execute trash action:', e)
  }
  showTrashConfirm.value = false
  trashConfirmAction.value = ''
  trashConfirmTargetId.value = ''
}

const formatDeleteTime = (dateStr: string) => {
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="sidebar-trash">
    <div class="trash-header">
      <button class="trash-back-btn" title="返回" @click="emit('close')">
        <ArrowLeft :size="16" />
      </button>
      <span class="trash-title">回收站</span>
      <button
        :class="['batch-toggle-btn', { active: trashBatchMode }]"
        title="批量操作"
        @click="toggleTrashBatchMode"
      >
        <SquareCheck :size="15" />
      </button>
    </div>

    <div v-if="trashBatchMode" class="batch-toolbar">
      <button class="batch-action-btn" @click="selectAllTrash">全选</button>
      <span class="batch-count">已选 {{ trashSelectedIds.size }} 项</span>
      <button
        :class="['batch-restore-btn', { disabled: trashSelectedIds.size === 0 }]"
        :disabled="trashSelectedIds.size === 0"
        title="批量恢复"
        @click="handleBatchRestore"
      >
        <Undo2 :size="13" />
        恢复
      </button>
      <button
        :class="['batch-delete-btn', { disabled: trashSelectedIds.size === 0 }]"
        :disabled="trashSelectedIds.size === 0"
        title="批量永久删除"
        @click="handleBatchPermanentDelete"
      >
        <Trash2 :size="13" />
        删除
      </button>
    </div>

    <div class="trash-toolbar" v-if="!trashBatchMode && chatTrashStore.trashItems.length > 0">
      <button class="empty-trash-btn" title="清空回收站" @click="handleEmptyTrash">
        <Trash2 :size="12" />
        清空回收站
      </button>
    </div>

    <div class="trash-list">
      <div v-if="chatTrashStore.trashItems.length === 0" class="history-empty">
        <Trash2 :size="24" />
        <span>回收站为空</span>
      </div>
      <div
        v-for="item in chatTrashStore.trashItems"
        :key="item.id"
        :class="['trash-item']"
        @click="trashBatchMode ? toggleTrashSelect(item.id) : undefined"
      >
        <div v-if="trashBatchMode" class="history-item-checkbox" @click.stop="toggleTrashSelect(item.id)">
          <div :class="['checkbox-box', { checked: trashSelectedIds.has(item.id) }]">
            <Check v-if="trashSelectedIds.has(item.id)" :size="10" />
          </div>
        </div>
        <MessageSquare :size="14" class="history-item-icon" />
        <div class="trash-item-content">
          <span class="history-item-title">{{ item.title }}</span>
          <span class="trash-item-deleted-time">{{ formatDeleteTime(item.deleted_at) }}</span>
        </div>
        <div v-if="!trashBatchMode" class="trash-item-actions">
          <button class="trash-action-btn restore" title="恢复" @click.stop="handleRestoreItem(item.id)">
            <Undo2 :size="13" />
          </button>
          <button class="trash-action-btn delete" title="永久删除" @click.stop="handlePermanentDeleteItem(item.id)">
            <Trash2 :size="13" />
          </button>
        </div>
      </div>
    </div>

    <Transition name="selection-fade">
      <div v-if="showTrashConfirm" class="create-dialog-overlay" @click.self="showTrashConfirm = false">
        <div class="confirm-dialog">
          <div class="confirm-dialog-icon">
            <AlertTriangle :size="24" />
          </div>
          <p class="confirm-dialog-message">{{ trashConfirmMessage }}</p>
          <div class="confirm-dialog-actions">
            <button class="dialog-btn danger" @click="handleTrashConfirm">删除</button>
            <button class="dialog-btn cancel" @click="showTrashConfirm = false">取消</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.sidebar-trash {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
}

.trash-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--divider-horizontal);
}

.trash-back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: var(--surface-hover);
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s ease-in-out;
}

.trash-back-btn:hover {
  background: var(--surface-active);
  color: var(--text-primary);
}

.trash-title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.batch-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  background: var(--surface-hover);
  color: var(--text-muted);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s ease-in-out;
}

.batch-toggle-btn:hover {
  background: var(--surface-active);
  color: var(--text-primary);
}

.batch-toggle-btn.active {
  background: var(--lumi-primary);
  color: var(--text-inverse);
}

.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--divider-horizontal);
}

.batch-action-btn {
  padding: 4px 10px;
  border: 1px solid var(--divider-horizontal);
  background: var(--surface);
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s ease-in-out;
}

.batch-action-btn:hover {
  background: var(--surface-hover);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.batch-count {
  font-size: 12px;
  color: var(--text-muted);
  flex: 1;
}

.batch-restore-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: none;
  background: var(--lumi-primary);
  color: var(--text-inverse);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 12px;
  transition: opacity 0.15s ease-in-out;
}

.batch-restore-btn:hover {
  opacity: 0.85;
}

.batch-restore-btn.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.batch-delete-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: none;
  background: var(--color-danger);
  color: var(--text-inverse);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 12px;
  transition: opacity 0.15s ease-in-out;
}

.batch-delete-btn:hover {
  opacity: 0.85;
}

.batch-delete-btn.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.trash-toolbar {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 14px;
}

.empty-trash-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid var(--color-danger);
  background: transparent;
  color: var(--color-danger);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s ease-in-out;
}

.empty-trash-btn:hover {
  background: var(--color-danger);
  color: var(--text-inverse);
}

.trash-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px;
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 20px;
  color: var(--text-muted);
  font-size: 13px;
}

.history-item-checkbox {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  cursor: pointer;
}

.checkbox-box {
  width: 16px;
  height: 16px;
  border: 1.5px solid var(--divider-vertical);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease-in-out;
  color: var(--text-inverse);
}

.checkbox-box.checked {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
}

.history-item-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.history-item-title {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.trash-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  cursor: default;
  transition: background 0.15s ease-in-out;
}

.trash-item:hover {
  background: var(--surface-hover);
}

.trash-item-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.trash-item-deleted-time {
  font-size: 11px;
  color: var(--text-muted);
}

.trash-item-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.trash-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s ease-in-out;
}

.trash-action-btn.restore {
  color: var(--lumi-primary);
}

.trash-action-btn.restore:hover {
  background: var(--lumi-primary-soft);
}

.trash-action-btn.delete {
  color: var(--color-danger);
}

.trash-action-btn.delete:hover {
  background: var(--color-danger-soft);
}

.create-dialog-overlay {
  position: fixed;
  inset: 0;
  background: var(--overlay-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.confirm-dialog {
  background: var(--surface);
  border-radius: var(--radius-lg);
  padding: 24px;
  max-width: 360px;
  width: 90%;
  box-shadow: var(--shadow-lg);
}

.confirm-dialog-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: var(--radius-full);
  background: var(--color-danger-soft);
  color: var(--color-danger);
  margin: 0 auto 16px;
}

.confirm-dialog-message {
  text-align: center;
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.5;
  margin: 0 0 20px;
}

.confirm-dialog-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}

.dialog-btn {
  padding: 8px 20px;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.15s ease-in-out;
}

.dialog-btn.danger {
  background: var(--color-danger);
  color: var(--text-inverse);
}

.dialog-btn.danger:hover {
  opacity: 0.85;
}

.dialog-btn.cancel {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.dialog-btn.cancel:hover {
  background: var(--surface-active);
}

.selection-fade-enter-active {
  animation: selection-fade-in 0.15s ease-in-out;
}

.selection-fade-leave-active {
  animation: selection-fade-out 0.1s ease-in-out;
}

@keyframes selection-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes selection-fade-out {
  from { opacity: 1; }
  to { opacity: 0; }
}
</style>
