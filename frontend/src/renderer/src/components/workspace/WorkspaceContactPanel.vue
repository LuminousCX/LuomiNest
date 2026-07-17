<script setup lang="ts">
import { computed } from 'vue'
import {
  Bot,
  Users,
  User,
  Plus,
  Search,
  Hash,
  MoreVertical,
  Trash2,
} from 'lucide-vue-next'
import type { AgentProfile, GroupInfo } from '../../types'
import type { ContactType } from './types'

const props = defineProps<{
  agents: AgentProfile[]
  groups: GroupInfo[]
  searchQuery: string
  selectedType: ContactType | null
  selectedAgentId: string | null
  selectedGroupId: string | null
}>()

const emit = defineEmits<{
  'update:searchQuery': [query: string]
  'select-agent': [agent: AgentProfile]
  'select-group': [group: GroupInfo]
  'create-agent': []
  'create-group': []
  'delete-group': [groupId: string]
  'edit-agent': [agent: AgentProfile]
  'market-agent-installed': [agentId: string]
}>()

const searchQueryModel = computed<string>({
  get: () => props.searchQuery,
  set: (value) => emit('update:searchQuery', value),
})

const filteredAgents = computed(() => {
  if (!props.searchQuery) return props.agents
  const q = props.searchQuery.toLowerCase()
  return props.agents.filter(a => a.name.toLowerCase().includes(q) || (a.description || '').toLowerCase().includes(q))
})

const filteredGroups = computed(() => {
  if (!props.searchQuery) return props.groups
  const q = props.searchQuery.toLowerCase()
  return props.groups.filter(g => g.name.toLowerCase().includes(q))
})
</script>

<template>
  <div class="contact-panel">
    <div class="contact-header">
      <div class="contact-search">
        <Search :size="14" class="search-icon" />
        <input v-model="searchQueryModel" type="text" placeholder="搜索联系人..." />
      </div>
      <button class="contact-add-btn" title="新建 Agent" @click="emit('create-agent')">
        <Plus :size="14" />
      </button>
    </div>

    <div class="contact-list">
      <!-- Agent 分组 -->
      <div class="contact-section" v-if="filteredAgents.length > 0">
        <div class="contact-section-label">
          <User :size="12" />
          <span>Agent</span>
          <span class="section-count">{{ filteredAgents.length }}</span>
        </div>
        <div
          v-for="agent in filteredAgents"
          :key="agent.id"
          :class="['contact-item', { active: selectedType === 'agent' && selectedAgentId === agent.id }]"
          @click="emit('select-agent', agent)"
        >
          <div class="contact-avatar" :style="{ background: `color-mix(in srgb, ${agent.color} 10%, transparent)`, color: agent.color }">
            <img v-if="agent.avatar" :src="agent.avatar" class="contact-avatar-img" :alt="agent.name" />
            <Bot v-else :size="16" />
          </div>
          <div class="contact-info">
            <span class="contact-name">{{ agent.name }}</span>
            <span class="contact-desc">{{ agent.description || '智能AI' }}</span>
          </div>
          <button class="contact-edit-btn" title="编辑" @click.stop="emit('edit-agent', agent)">
            <MoreVertical :size="12" />
          </button>
        </div>
      </div>

      <!-- 群聊分组 -->
      <div class="contact-section">
        <div class="contact-section-label">
          <Hash :size="12" />
          <span>群聊</span>
          <span class="section-count">{{ filteredGroups.length }}</span>
          <button class="section-add-btn" title="新建群组" @click="emit('create-group')">
            <Plus :size="12" />
          </button>
        </div>
        <div
          v-for="group in filteredGroups"
          :key="group.id"
          :class="['contact-item', { active: selectedType === 'group' && selectedGroupId === group.id }]"
          @click="emit('select-group', group)"
        >
          <div class="contact-avatar group-avatar">
            <Users :size="16" />
          </div>
          <div class="contact-info">
            <div class="contact-top-row">
              <span class="contact-name">{{ group.name }}</span>
              <span class="contact-meta">{{ group.aiCount }} AI</span>
            </div>
            <span class="contact-desc">{{ group.description || '暂无描述' }}</span>
          </div>
          <button class="contact-edit-btn" title="删除群组" @click.stop="emit('delete-group', group.id)">
            <Trash2 :size="12" />
          </button>
        </div>
        <div v-if="filteredGroups.length === 0 && !searchQuery" class="contact-empty-mini">
          暂无群组
        </div>
      </div>

      <div v-if="filteredAgents.length === 0 && filteredGroups.length === 0" class="contact-empty">
        <Bot :size="28" />
        <p>{{ searchQuery ? '未找到匹配的联系人' : '暂无联系人' }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.contact-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.contact-header {
  padding: var(--space-3) var(--space-3) var(--space-2);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.contact-search {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 10px;
  background: var(--workspace-panel);
  border-radius: var(--radius-sm);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-fast);
}

.contact-search:focus-within {
  border-color: var(--lumi-brand-border);
  background: var(--surface);
}

.contact-search .search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.contact-search input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--text-base);
  color: var(--text-primary);
  min-width: 0;
}

.contact-search input::placeholder {
  color: var(--text-muted);
}

.contact-add-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.contact-add-btn:hover {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.contact-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-1) var(--space-2) var(--space-3);
}

.contact-section {
  margin-bottom: var(--space-2);
}

.contact-section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: var(--space-2) var(--space-2) 6px;
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.contact-section-label .section-count {
  background: var(--workspace-panel);
  padding: 1px 6px;
  border-radius: 10px;
  font-size: var(--text-2xs);
  font-weight: 500;
}

.section-add-btn {
  margin-left: auto;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.section-add-btn:hover {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.contact-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: var(--space-2) 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
  background: transparent;
  border: none;
  width: 100%;
  text-align: left;
}

.contact-item:hover {
  background: var(--workspace-hover);
}

.contact-item.active {
  background: var(--lumi-brand-light);
}

.contact-avatar {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}

.contact-avatar-img {
  width: 100%;
  height: 100%;
  border-radius: inherit;
  object-fit: cover;
}

.contact-avatar.group-avatar {
  background: var(--lumi-brand-glow);
  color: var(--lumi-brand);
}

.contact-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.contact-top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.contact-name {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.contact-meta {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  flex-shrink: 0;
}

.contact-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.contact-edit-btn {
  width: 22px;
  height: 22px;
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

.contact-item:hover .contact-edit-btn {
  opacity: 1;
}

.contact-edit-btn:hover {
  background: var(--overlay-subtle);
  color: var(--text-secondary);
}

.contact-empty-mini {
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-align: center;
}

.contact-empty {
  padding: var(--space-7) var(--space-4);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-muted);
}

.contact-empty p {
  font-size: var(--text-sm);
  margin: 0;
}
</style>
