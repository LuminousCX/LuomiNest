<script setup lang="ts">
import {
  Bot,
  Users,
  ChevronLeft,
  Zap,
  UserPlus,
  X,
} from 'lucide-vue-next'
import type { GroupInfo } from '../../types'

const props = defineProps<{
  group: GroupInfo | null
  collaborationMode: boolean
}>()

const emit = defineEmits<{
  back: []
  'toggle-collaboration-mode': []
  'add-agent': []
  'remove-agent': [agentId: string]
}>()
</script>

<template>
  <div class="group-info-panel">
    <div class="left-panel-header">
      <button class="back-btn" title="返回联系人" @click="emit('back')">
        <ChevronLeft :size="16" />
      </button>
      <div class="left-panel-title">
        <div class="left-panel-avatar group-avatar">
          <Users :size="14" />
        </div>
        <div class="left-panel-title-text">
          <span class="left-panel-name">{{ group?.name }}</span>
          <span class="left-panel-sub">{{ group?.members.length }} 成员 · {{ group?.aiCount }} AI</span>
        </div>
      </div>
    </div>

    <div class="group-actions">
      <button
        :class="['group-action-btn', { active: collaborationMode }]"
        title="协作模式"
        @click="emit('toggle-collaboration-mode')"
      >
        <Zap :size="14" />
        <span>协作模式</span>
      </button>
      <button class="group-action-btn" title="添加 Agent" @click="emit('add-agent')">
        <UserPlus :size="14" />
        <span>添加成员</span>
      </button>
    </div>

    <div class="group-members">
      <div class="members-label">
        <Bot :size="12" />
        <span>群成员</span>
      </div>
      <div
        v-for="member in group?.members"
        :key="member.agent_id"
        class="member-item"
      >
        <div class="member-avatar" :style="{ background: `color-mix(in srgb, ${member.color} 8%, transparent)`, color: member.color }">
          <Bot :size="14" />
        </div>
        <div class="member-info">
          <span class="member-name">{{ member.name }}</span>
          <span class="member-role">{{ member.role }}</span>
        </div>
        <button class="member-remove-btn" title="移除成员" @click="emit('remove-agent', member.agent_id)">
          <X :size="12" />
        </button>
      </div>
      <div v-if="!group?.members.length" class="conv-empty">
        <Bot :size="24" />
        <span>暂无成员，点击上方添加</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.group-info-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.left-panel-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 10px var(--space-3);
  flex-shrink: 0;
  border-bottom: 1px solid var(--workspace-border);
}

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
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.left-panel-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  flex: 1;
}

.left-panel-title-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.left-panel-avatar {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-xs);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.left-panel-avatar.group-avatar {
  background: var(--lumi-brand-glow);
  color: var(--lumi-brand);
}

.left-panel-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.left-panel-sub {
  font-size: var(--text-xs);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.group-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0 var(--space-3) var(--space-2);
  flex-shrink: 0;
}

.group-action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  background: var(--surface);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.group-action-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.group-action-btn.active {
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  border-color: var(--lumi-brand-border);
}

.group-members {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-1) var(--space-3) var(--space-3);
}

.members-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) 0 6px;
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.member-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px var(--space-2);
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast);
}

.member-item:hover {
  background: var(--workspace-hover);
}

.member-avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-xs);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.member-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.member-name {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.member-role {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.member-remove-btn {
  width: var(--space-5);
  height: var(--space-5);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  opacity: 0;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.member-item:hover .member-remove-btn {
  opacity: 1;
}

.member-remove-btn:hover {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.conv-empty {
  padding: var(--space-7) var(--space-4);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-muted);
}

.conv-empty span {
  font-size: var(--text-sm);
}
</style>
