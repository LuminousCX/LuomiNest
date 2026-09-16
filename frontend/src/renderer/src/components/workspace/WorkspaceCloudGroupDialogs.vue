<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { AlertCircle } from 'lucide-vue-next'
import LumiModal from '../common/LumiModal.vue'
import LumiButton from '../common/LumiButton.vue'

/**
 * 云端群对话框组：创建云端群 + 按用户 ID 邀请成员。
 * 错误以 cloudDialogError 的 kind 传入，映射本地化文案（forbidden=仅群主/管理员可邀请）。
 */
const { t } = useI18n()

const props = defineProps<{
  showCreateDialog: boolean
  showInviteDialog: boolean
  groupName: string
  inviteUserId: string
  /** kind 错误码（'createFailed' / 'forbidden' / ...），空串隐藏 */
  errorKind: string
  creating: boolean
  inviting: boolean
}>()

const emit = defineEmits<{
  'update:showCreateDialog': [value: boolean]
  'update:showInviteDialog': [value: boolean]
  'update:groupName': [value: string]
  'update:inviteUserId': [value: string]
  create: []
  invite: []
}>()

const groupNameModel = computed({
  get: () => props.groupName,
  set: (v) => emit('update:groupName', v),
})

const inviteUserIdModel = computed({
  get: () => props.inviteUserId,
  set: (v) => emit('update:inviteUserId', v),
})

/** 错误 kind → 本地化 key（未知 kind 统一通用失败文案） */
const errorText = computed(() => {
  if (!props.errorKind) return ''
  if (props.errorKind === 'createFailed') return t('workspace.cloud.createFailed')
  if (props.errorKind === 'forbidden') return t('workspace.cloud.inviteForbidden')
  if (props.errorKind === 'rate_limited') return t('workspace.cloud.tooManyRequests')
  if (props.errorKind === 'unavailable') return t('workspace.cloud.unavailable')
  return t('workspace.cloud.actionFailed')
})
</script>

<template>
  <LumiModal
    :visible="showCreateDialog"
    :title="t('workspace.cloud.createTitle')"
    :width="460"
    @update:visible="emit('update:showCreateDialog', $event)"
  >
    <div class="form-group">
      <label class="form-label">
        {{ t('workspace.cloud.fieldGroupName') }}
        <span class="required-mark">*</span>
      </label>
      <input
        v-model="groupNameModel"
        type="text"
        class="form-input"
        :placeholder="t('workspace.cloud.phGroupName')"
        @keydown.enter="emit('create')"
      />
    </div>
    <div v-if="errorText" class="form-error">
      <AlertCircle :size="13" />
      <span>{{ errorText }}</span>
    </div>
    <template #footer>
      <LumiButton variant="secondary" size="sm" @click="emit('update:showCreateDialog', false)">
        {{ t('workspace.cancel') }}
      </LumiButton>
      <LumiButton
        variant="primary"
        size="sm"
        :disabled="!groupNameModel.trim() || creating"
        @click="emit('create')"
      >
        {{ t('workspace.cloud.create') }}
      </LumiButton>
    </template>
  </LumiModal>

  <LumiModal
    :visible="showInviteDialog"
    :title="t('workspace.cloud.inviteTitle')"
    :width="460"
    @update:visible="emit('update:showInviteDialog', $event)"
  >
    <div class="form-group">
      <label class="form-label">
        {{ t('workspace.cloud.fieldUserId') }}
        <span class="required-mark">*</span>
      </label>
      <input
        v-model="inviteUserIdModel"
        type="text"
        class="form-input"
        :placeholder="t('workspace.cloud.phUserId')"
        @keydown.enter="emit('invite')"
      />
      <p class="form-hint">{{ t('workspace.cloud.inviteHint') }}</p>
    </div>
    <div v-if="errorText" class="form-error">
      <AlertCircle :size="13" />
      <span>{{ errorText }}</span>
    </div>
    <template #footer>
      <LumiButton variant="secondary" size="sm" @click="emit('update:showInviteDialog', false)">
        {{ t('workspace.cancel') }}
      </LumiButton>
      <LumiButton
        variant="primary"
        size="sm"
        :disabled="!inviteUserIdModel.trim() || inviting"
        @click="emit('invite')"
      >
        {{ t('workspace.cloud.invite') }}
      </LumiButton>
    </template>
  </LumiModal>
</template>

<style scoped>
.form-group {
  margin-bottom: var(--space-4);
}

.form-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.required-mark {
  color: var(--lumi-danger);
  margin-left: 2px;
}

.form-input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  font-size: var(--text-base);
  color: var(--text-primary);
  background: var(--surface);
  outline: none;
  transition: border-color var(--transition-fast);
}

.form-input:focus {
  border-color: var(--lumi-brand);
}

.form-hint {
  margin: var(--space-2) 0 0;
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.form-error {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--lumi-danger);
  background: color-mix(in srgb, var(--lumi-danger) 8%, transparent);
}
</style>
