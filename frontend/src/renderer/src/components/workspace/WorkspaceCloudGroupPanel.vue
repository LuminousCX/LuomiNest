<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Cloud, ChevronLeft, UserPlus, Users } from 'lucide-vue-next'
import type { CloudGroupVo } from '@shared/ipc-types'

/**
 * 云端群左侧信息面板（选中云端群时显示）：
 * 群名 / 成员数 / 我的角色 + 邀请成员入口。
 * 成员明细服务端契约暂未提供，仅展示摘要。
 */
const { t } = useI18n()

const props = defineProps<{
  group: CloudGroupVo | null
}>()

const emit = defineEmits<{
  back: []
  invite: []
}>()

const roleLabel = computed(() => {
  const role = props.group?.myRole || ''
  if (role === 'owner') return t('workspace.cloud.roleOwner')
  if (role === 'admin') return t('workspace.cloud.roleAdmin')
  return t('workspace.cloud.roleMember')
})
</script>

<template>
  <div class="cloud-group-panel">
    <div class="left-panel-header">
      <button class="back-btn" :title="t('workspace.backToContacts')" @click="emit('back')">
        <ChevronLeft :size="16" />
      </button>
      <div class="left-panel-title">
        <div class="left-panel-avatar cloud-avatar">
          <Cloud :size="14" />
        </div>
        <div class="left-panel-title-text">
          <span class="left-panel-name">{{ group?.name }}</span>
          <span class="left-panel-sub">
            {{ t('workspace.cloud.memberCount', { n: group?.memberCount ?? 0 }) }} · {{ roleLabel }}
          </span>
        </div>
      </div>
    </div>

    <div class="cloud-actions">
      <button class="cloud-action-btn" @click="emit('invite')">
        <UserPlus :size="14" />
        <span>{{ t('workspace.cloud.inviteMember') }}</span>
      </button>
    </div>

    <div class="cloud-note">
      <Users :size="14" />
      <span>{{ t('workspace.cloud.panelNote') }}</span>
    </div>
  </div>
</template>

<style scoped src="./workspace-shared.css"></style>
<style scoped>
/* back-btn 整块留本地：本份 hover 用 --workspace-hover（另两份用 --lumi-brand-light），待拍板（报告 §4/§7.1） */
.back-btn {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.back-btn:hover {
  background: var(--workspace-hover);
}

/* gap:10px 无 flex:1 变体留本地；flex: initial 抵消共享 .left-panel-title 的 flex:1（报告 §7.1） */
.left-panel-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: initial;
}

/* avatar var(--space-7)/radius-sm 变体与 AgentHistory 30px/radius-xs 不同，留本地（报告 §7.1） */
.left-panel-avatar {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.cloud-avatar {
  background: var(--lumi-brand-glow);
  color: var(--lumi-brand);
}

.left-panel-title-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.left-panel-sub {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.cloud-actions {
  padding: var(--space-3);
  flex-shrink: 0;
}

.cloud-action-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  border: 1px solid var(--lumi-brand-border);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.cloud-action-btn:hover {
  background: var(--lumi-brand-glow);
}

.cloud-note {
  margin: 0 var(--space-3);
  display: flex;
  align-items: center;
  gap: 6px;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  color: var(--text-muted);
  background: var(--workspace-panel);
}
</style>
