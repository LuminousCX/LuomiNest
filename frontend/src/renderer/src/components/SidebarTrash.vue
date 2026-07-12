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
import LumiButton from './common/LumiButton.vue'
import LumiEmptyState from './common/LumiEmptyState.vue'
import LumiModal from './common/LumiModal.vue'
import { useAgentStore } from '../stores/agent'
import { useChatStore } from '../stores/chat'
import { useChatTrashStore } from '../stores/chat-trash'
import type { TrashListItem } from '../types'
import { formatDateTime } from '../utils/format'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('SidebarTrash')

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
    logger.error('Failed to batch restore:', e)
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
    logger.error('Failed to restore:', e)
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
    logger.error('Failed to execute trash action:', e)
  }
  showTrashConfirm.value = false
  trashConfirmAction.value = ''
  trashConfirmTargetId.value = ''
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
      <LumiButton
        variant="primary"
        size="sm"
        :disabled="trashSelectedIds.size === 0"
        @click="handleBatchRestore"
      >
        <template #icon>
          <Undo2 :size="13" />
        </template>
        恢复
      </LumiButton>
      <LumiButton
        variant="danger"
        size="sm"
        :disabled="trashSelectedIds.size === 0"
        @click="handleBatchPermanentDelete"
      >
        <template #icon>
          <Trash2 :size="13" />
        </template>
        删除
      </LumiButton>
    </div>

    <div class="trash-toolbar" v-if="!trashBatchMode && chatTrashStore.trashItems.length > 0">
      <button class="empty-trash-btn" title="清空回收站" @click="handleEmptyTrash">
        <Trash2 :size="12" />
        清空回收站
      </button>
    </div>

    <div class="trash-list">
      <LumiEmptyState v-if="chatTrashStore.trashItems.length === 0" :icon="Trash2" title="回收站为空" size="sm" />
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
          <span class="trash-item-deleted-time">{{ formatDateTime(item.deleted_at) }}</span>
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

    <LumiModal v-model:visible="showTrashConfirm" title="确认删除" size="sm">
      <div class="confirm-dialog-content">
        <div class="confirm-dialog-icon">
          <AlertTriangle :size="24" />
        </div>
        <p class="confirm-dialog-message">{{ trashConfirmMessage }}</p>
        <div class="confirm-dialog-actions">
          <LumiButton variant="danger" size="md" @click="handleTrashConfirm">删除</LumiButton>
          <LumiButton variant="secondary" size="md" @click="showTrashConfirm = false">取消</LumiButton>
        </div>
      </div>
    </LumiModal>
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
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-light);
}

.trash-back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: calc(var(--space-5) + var(--space-2));
  height: calc(var(--space-5) + var(--space-2));
  border: none;
  background: var(--surface-hover);
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.trash-back-btn:hover {
  background: var(--surface-active);
  color: var(--text);
}

.trash-title {
  flex: 1;
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.batch-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--btn-height-md);
  height: var(--btn-height-md);
  border: none;
  background: var(--surface-hover);
  color: var(--text-muted);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.batch-toggle-btn:hover {
  background: var(--surface-active);
  color: var(--text);
}

.batch-toggle-btn.active {
  background: var(--lumi-brand);
  color: var(--text-inverse);
}

.batch-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--border-light);
}

.batch-action-btn {
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--border-light);
  background: var(--surface);
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--text-sm);
  transition: all var(--transition-fast);
}

.batch-action-btn:hover {
  background: var(--surface-hover);
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
}

.batch-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
  flex: 1;
}

.trash-toolbar {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-2) var(--space-4);
}

.empty-trash-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--lumi-danger);
  background: transparent;
  color: var(--lumi-danger);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--text-sm);
  transition: all var(--transition-fast);
}

.empty-trash-btn:hover {
  background: var(--lumi-danger);
  color: var(--text-inverse);
}

.trash-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-1) var(--space-2);
}

.history-item-checkbox {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-5);
  height: var(--space-5);
  flex-shrink: 0;
  cursor: pointer;
}

.checkbox-box {
  width: var(--space-4);
  height: var(--space-4);
  border: 1.5px solid var(--border);
  border-radius: var(--space-1);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
  color: var(--text-inverse);
}

.checkbox-box.checked {
  background: var(--lumi-brand);
  border-color: var(--lumi-brand);
}

.history-item-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.history-item-title {
  font-size: var(--text-base);
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.trash-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  cursor: default;
  transition: background var(--transition-fast);
}

.trash-item:hover {
  background: var(--surface-hover);
}

.trash-item-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: calc(var(--space-1) / 2);
}

.trash-item-deleted-time {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.trash-item-actions {
  display: flex;
  gap: var(--space-1);
  flex-shrink: 0;
}

.trash-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: calc(var(--space-5) + var(--space-2));
  height: calc(var(--space-5) + var(--space-2));
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.trash-action-btn.restore {
  color: var(--lumi-brand);
}

.trash-action-btn.restore:hover {
  background: var(--lumi-brand-soft);
}

.trash-action-btn.delete {
  color: var(--lumi-danger);
}

.trash-action-btn.delete:hover {
  background: var(--lumi-danger-light);
}

.confirm-dialog-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.confirm-dialog-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: calc(var(--space-6) * 2);
  height: calc(var(--space-6) * 2);
  border-radius: var(--radius-full);
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
  margin-bottom: var(--space-4);
}

.confirm-dialog-message {
  text-align: center;
  font-size: var(--text-md);
  color: var(--text);
  line-height: var(--leading-normal);
  margin: 0 0 var(--space-5);
}

.confirm-dialog-actions {
  display: flex;
  gap: var(--space-2);
  justify-content: center;
}

</style>
