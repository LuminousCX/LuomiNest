<script setup lang="ts">
/**
 * 统一确认弹窗：LumiModal 封装，覆盖"标题 + 一句话 + 取消/确定"场景。
 * danger 时确认按钮为危险色并带警示图标；loading 时按钮禁用并转圈。
 */
import { AlertCircle } from 'lucide-vue-next'
import LumiModal from './LumiModal.vue'
import LumiButton from './LumiButton.vue'

interface Props {
  visible: boolean
  message: string
  title?: string
  danger?: boolean
  confirmText?: string
  cancelText?: string
  loading?: boolean
}

withDefaults(defineProps<Props>(), {
  title: '',
  danger: false,
  confirmText: '确定',
  cancelText: '取消',
  loading: false,
})

const emit = defineEmits<{
  confirm: []
  cancel: []
  'update:visible': [visible: boolean]
}>()

const handleCancel = () => {
  emit('update:visible', false)
  emit('cancel')
}
</script>

<template>
  <LumiModal
    :visible="visible"
    :title="title"
    size="sm"
    :mask-closable="!loading"
    @close="handleCancel"
  >
    <div :class="['confirm-dialog__body', { 'is-danger': danger }]">
      <AlertCircle v-if="danger" :size="22" class="confirm-dialog__icon" />
      <p class="confirm-dialog__message">{{ message }}</p>
    </div>
    <template #footer>
      <LumiButton size="sm" :disabled="loading" @click="handleCancel">
        {{ cancelText }}
      </LumiButton>
      <LumiButton
        :variant="danger ? 'danger' : 'primary'"
        size="sm"
        :loading="loading"
        @click="emit('confirm')"
      >
        {{ confirmText }}
      </LumiButton>
    </template>
  </LumiModal>
</template>

<style scoped>
.confirm-dialog__body {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) 0;
}

.confirm-dialog__body.is-danger {
  align-items: flex-start;
}

.confirm-dialog__icon {
  flex-shrink: 0;
  color: var(--lumi-danger);
}

.confirm-dialog__message {
  margin: 0;
  font-size: var(--text-md);
  line-height: var(--leading-normal);
  color: var(--text);
}
</style>
