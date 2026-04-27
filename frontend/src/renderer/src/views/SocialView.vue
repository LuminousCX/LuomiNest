﻿<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import {
  Users,
  Bot,
  User,
  MessageCircle,
  Plus,
  Search,
  MoreVertical,
  Send,
  Hash,
  ImagePlus,
  Mic,
  Trash2,
  UserPlus,
  X,
  Loader2,
} from 'lucide-vue-next'
import { useSocialStore } from '../stores/social'
import { useAgentStore } from '../stores/agent'
import type { GroupInfo } from '../types'

const socialStore = useSocialStore()
const agentStore = useAgentStore()

const activeTab = ref<'friends' | 'groups'>('groups')
const selectedGroupId = ref<string | null>(null)
const chatInput = ref('')
const searchQuery = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const showAddAgentDialog = ref(false)
const showCreateGroupDialog = ref(false)
const addAgentRole = ref('')
const addAgentId = ref('')
const newGroupName = ref('')
const newGroupDesc = ref('')
const sendingMessage = ref(false)

const selectedGroup = computed(() => {
  if (!selectedGroupId.value) return null
  return socialStore.groups.find(g => g.id === selectedGroupId.value) || null
})

const groupMessages = computed(() => socialStore.groupMessages)

const filteredGroups = computed(() => {
  if (!searchQuery.value) return socialStore.groups
  const q = searchQuery.value.toLowerCase()
  return socialStore.groups.filter(g => g.name.toLowerCase().includes(q))
})

const availableAgentsForGroup = computed(() => {
  if (!selectedGroup.value) return agentStore.agents
  const memberIds = selectedGroup.value.members.map(m => m.agentId)
  return agentStore.agents.filter(a => !memberIds.includes(a.id))
})

const selectTab = (tab: typeof activeTab.value) => {
  activeTab.value = tab
  selectedGroupId.value = null
}

const openGroupChat = (group: GroupInfo) => {
  selectedGroupId.value = group.id
  socialStore.currentGroup = group
}

const sendMessage = async () => {
  if (!chatInput.value.trim() || !selectedGroupId.value) return
  sendingMessage.value = true
  try {
    await socialStore.sendGroupMessage(selectedGroupId.value, chatInput.value)
    chatInput.value = ''
    await nextTick()
    if (messagesContainer.value) {
      messagesContainer.value.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' })
    }
  } catch (e) {
    console.error('Failed to send message:', e)
  } finally {
    sendingMessage.value = false
  }
}

const createGroup = async () => {
  if (!newGroupName.value.trim()) return
  try {
    const group = await socialStore.createGroup(newGroupName.value.trim(), newGroupDesc.value.trim())
    newGroupName.value = ''
    newGroupDesc.value = ''
    showCreateGroupDialog.value = false
    if (group) {
      selectedGroupId.value = group.id
    }
  } catch (e) {
    console.error('Failed to create group:', e)
  }
}

const deleteGroup = async (groupId: string) => {
  try {
    await socialStore.deleteGroup(groupId)
    if (selectedGroupId.value === groupId) {
      selectedGroupId.value = null
    }
  } catch (e) {
    console.error('Failed to delete group:', e)
  }
}

const addAgentToGroup = async () => {
  if (!addAgentId.value || !selectedGroupId.value) return
  try {
    await socialStore.addAgentToGroup(selectedGroupId.value, addAgentId.value, addAgentRole.value || '成员')
    addAgentId.value = ''
    addAgentRole.value = ''
    showAddAgentDialog.value = false
  } catch (e) {
    console.error('Failed to add agent:', e)
  }
}

const removeAgentFromGroup = async (groupId: string, agentId: string) => {
  try {
    await socialStore.removeAgentFromGroup(groupId, agentId)
  } catch (e) {
    console.error('Failed to remove agent:', e)
  }
}

const formatTime = (dateStr: string) => {
  try {
    const d = new Date(dateStr)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

watch(groupMessages, () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' })
    }
  })
}, { deep: true })

onMounted(async () => {
  await Promise.all([
    socialStore.fetchGroups(),
    socialStore.fetchAvailableAgents(),
    agentStore.fetchAgents(),
  ])
})
</script>

<template>
  <div class="social-view">
    <div class="social-header">
      <div class="header-left">
        <div class="header-icon-wrap">
          <Users :size="18" />
        </div>
        <div class="header-text">
          <h2>AI 社交</h2>
          <span class="header-sub">LuomiNest Social</span>
        </div>
      </div>
      <div class="header-actions">
        <button class="h-btn primary" @click="showCreateGroupDialog = true">
          <Plus :size="14" />
          新建群组
        </button>
      </div>
    </div>

    <div class="social-body">
      <div class="social-sidebar">
        <div class="sidebar-tabs">
          <button
            :class="['tab-btn', { active: activeTab === 'friends' }]"
            @click="selectTab('friends')"
          >
            <Bot :size="14" />
            <span>AI Agents</span>
            <span class="tab-count">{{ agentStore.agents.length }}</span>
          </button>
          <button
            :class="['tab-btn', { active: activeTab === 'groups' }]"
            @click="selectTab('groups')"
          >
            <Users :size="14" />
            <span>群组</span>
            <span class="tab-count">{{ socialStore.groups.length }}</span>
          </button>
        </div>

        <div class="sidebar-search">
          <Search :size="14" class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索..." />
        </div>

        <div v-if="activeTab === 'friends'" class="friend-list">
          <div
            v-for="agent in agentStore.agents"
            :key="agent.id"
            class="friend-item"
          >
            <div class="friend-avatar-wrap">
              <span class="friend-avatar" :style="{ background: agent.color + '14', color: agent.color }">
                <Bot :size="18" />
              </span>
              <span class="status-indicator online"></span>
            </div>
            <div class="friend-info">
              <div class="friend-top-row">
                <span class="friend-name">{{ agent.name }}</span>
              </div>
              <span class="friend-personality">{{ agent.description || '暂无描述' }}</span>
            </div>
          </div>
          <div v-if="agentStore.agents.length === 0" class="list-empty">
            <Bot :size="24" />
            <p>暂无 Agent，请先在聊天页面创建</p>
          </div>
        </div>

        <div v-else class="group-list">
          <div
            v-for="group in filteredGroups"
            :key="group.id"
            :class="['group-item', { selected: selectedGroupId === group.id }]"
            @click="openGroupChat(group)"
          >
            <div :class="['group-icon', group.type]">
              <Hash :size="16" />
            </div>
            <div class="group-info">
              <div class="group-top-row">
                <span class="group-name">{{ group.name }}</span>
                <span class="group-member-count">{{ group.aiCount }} AI</span>
              </div>
              <span class="group-preview">{{ group.description || '暂无描述' }}</span>
            </div>
            <button class="group-delete-btn" @click.stop="deleteGroup(group.id)">
              <Trash2 :size="12" />
            </button>
          </div>
          <div v-if="socialStore.groups.length === 0" class="list-empty">
            <Users :size="24" />
            <p>暂无群组，点击右上角创建</p>
          </div>
        </div>
      </div>

      <div class="social-chat" v-if="selectedGroup">
        <div class="chat-header">
          <div class="chat-title-area">
            <div class="chat-avatar-mini">
              <Users :size="14" />
            </div>
            <div class="chat-title-text">
              <h3>{{ selectedGroup.name }}</h3>
              <span class="chat-status-line">
                {{ selectedGroup.members.length }} 成员 · {{ selectedGroup.aiCount }} AI
              </span>
            </div>
          </div>
          <div class="chat-actions">
            <button class="chat-action-btn" title="添加 Agent" @click="showAddAgentDialog = true">
              <UserPlus :size="15" />
            </button>
            <button class="chat-action-btn"><MoreVertical :size="15" /></button>
          </div>
        </div>

        <div class="chat-members-bar" v-if="selectedGroup.members.length > 0">
          <div class="members-scroll">
            <div
              v-for="member in selectedGroup.members"
              :key="member.agentId"
              class="member-chip"
              :style="{ background: member.color + '14', color: member.color }"
            >
              <Bot :size="12" />
              <span>{{ member.name }}</span>
              <span class="member-role">{{ member.role }}</span>
              <button class="member-remove" @click="removeAgentFromGroup(selectedGroup!.id, member.agentId)">
                <X :size="10" />
              </button>
            </div>
          </div>
        </div>

        <div ref="messagesContainer" class="chat-messages">
          <div
            v-for="msg in groupMessages"
            :key="msg.id"
            :class="['msg-row', msg.senderType]"
          >
            <div v-if="msg.senderType === 'agent'" class="msg-avatar">
              <div class="avatar-agent">
                <Bot :size="14" />
              </div>
            </div>
            <div :class="['msg-bubble', msg.senderType]">
              <span class="msg-sender" v-if="msg.senderType === 'agent'">
                {{ msg.senderName || 'AI' }}
                <span v-if="msg.role" class="msg-role-tag">{{ msg.role }}</span>
              </span>
              <p class="msg-text">{{ msg.content }}</p>
              <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
            </div>
            <div v-if="msg.senderType === 'user'" class="msg-avatar user-avatar">
              <User :size="16" />
            </div>
          </div>
          <div v-if="groupMessages.length === 0" class="chat-empty">
            <MessageCircle :size="32" />
            <p>群聊已创建，添加 Agent 开始协作</p>
          </div>
        </div>

        <div class="chat-input-bar">
          <div class="input-tools">
            <button class="input-tool-btn"><ImagePlus :size="16" /></button>
            <button class="input-tool-btn"><Mic :size="16" /></button>
          </div>
          <div class="input-main">
            <input
              v-model="chatInput"
              type="text"
              placeholder="发送消息到群聊..."
              :disabled="sendingMessage"
              @keydown.enter="sendMessage"
            />
            <button class="input-send-btn" @click="sendMessage" :disabled="!chatInput.trim() || sendingMessage">
              <Loader2 v-if="sendingMessage" :size="15" class="spin-animation" />
              <Send v-else :size="15" />
            </button>
          </div>
        </div>
      </div>

      <div class="social-empty" v-else>
        <div class="empty-visual">
          <div class="empty-orb">
            <MessageCircle :size="36" />
          </div>
        </div>
        <h3>选择一个群组开始协作</h3>
        <p>在左侧选择已有群组，或创建新群组邀请 AI Agent 加入</p>
        <button class="empty-action-btn" @click="showCreateGroupDialog = true">
          <Plus :size="16" />
          创建群组
        </button>
      </div>
    </div>

    <Transition name="selection-fade">
      <div v-if="showCreateGroupDialog" class="dialog-overlay" @click.self="showCreateGroupDialog = false">
        <div class="add-dialog">
          <h3>创建群组</h3>
          <div class="form-group">
            <label class="form-label">群组名称 <span class="required-mark">*</span></label>
            <input v-model="newGroupName" type="text" class="form-input" placeholder="如: 项目讨论组" />
          </div>
          <div class="form-group">
            <label class="form-label">描述</label>
            <input v-model="newGroupDesc" type="text" class="form-input" placeholder="群组用途描述" />
          </div>
          <div class="dialog-actions">
            <button class="dialog-btn cancel" @click="showCreateGroupDialog = false">取消</button>
            <button class="dialog-btn confirm" :disabled="!newGroupName.trim()" @click="createGroup">创建</button>
          </div>
        </div>
      </div>
    </Transition>

    <Transition name="selection-fade">
      <div v-if="showAddAgentDialog" class="dialog-overlay" @click.self="showAddAgentDialog = false">
        <div class="add-dialog">
          <h3>添加 Agent 到群组</h3>
          <div v-if="availableAgentsForGroup.length === 0" class="dialog-empty">
            <Bot :size="24" />
            <p>所有 Agent 都已在群组中，或暂无可用 Agent</p>
          </div>
          <div v-else class="agent-select-list">
            <div
              v-for="agent in availableAgentsForGroup"
              :key="agent.id"
              :class="['agent-select-item', { selected: addAgentId === agent.id }]"
              @click="addAgentId = agent.id"
            >
              <div class="agent-select-avatar" :style="{ background: agent.color + '14', color: agent.color }">
                <Bot :size="18" />
              </div>
              <div class="agent-select-info">
                <span class="agent-select-name">{{ agent.name }}</span>
                <span class="agent-select-desc">{{ agent.description || '暂无描述' }}</span>
              </div>
            </div>
          </div>
          <div v-if="addAgentId" class="form-group">
            <label class="form-label">角色定位</label>
            <input v-model="addAgentRole" type="text" class="form-input" placeholder="如: 代码审查员、文档撰写者" />
          </div>
          <div class="dialog-actions">
            <button class="dialog-btn cancel" @click="showAddAgentDialog = false">取消</button>
            <button class="dialog-btn confirm" :disabled="!addAgentId" @click="addAgentToGroup">添加</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.social-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--workspace-bg);
  overflow: hidden;
}

.social-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--divider-soft);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-text h2 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.header-sub {
  font-size: 11px;
  color: var(--text-muted);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.h-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 300ms ease-in-out;
}

.h-btn.primary {
  background: var(--lumi-primary);
  color: white;
}

.h-btn.primary:hover {
  background: var(--lumi-primary-hover);
}

.h-btn.ghost {
  color: var(--text-secondary);
  background: var(--workspace-card);
}

.h-btn.ghost:hover {
  background: var(--workspace-hover);
}

.social-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.social-sidebar {
  width: 280px;
  flex-shrink: 0;
  border-right: 1px solid var(--divider-vertical);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-tabs {
  display: flex;
  padding: 8px;
  gap: 4px;
  flex-shrink: 0;
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 300ms ease-in-out;
}

.tab-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.tab-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.tab-count {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background: var(--workspace-panel);
}

.tab-btn.active .tab-count {
  background: rgba(20, 126, 188, 0.15);
}

.sidebar-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  flex-shrink: 0;
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.sidebar-search input {
  flex: 1;
  background: var(--workspace-panel);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-primary);
}

.sidebar-search input::placeholder {
  color: var(--text-muted);
}

.friend-list,
.group-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px;
}

.friend-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 300ms ease-in-out;
}

.friend-item:hover {
  background: var(--workspace-hover);
}

.friend-avatar-wrap {
  position: relative;
  flex-shrink: 0;
}

.friend-avatar {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
}

.status-indicator {
  position: absolute;
  bottom: -1px;
  right: -1px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid var(--workspace-bg);
  background: var(--status-color, #78716c);
}

.status-indicator.online {
  --status-color: #22c55e;
}

.friend-info {
  flex: 1;
  min-width: 0;
}

.friend-top-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.friend-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.friend-personality {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}

.group-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  position: relative;
}

.group-item:hover {
  background: var(--workspace-hover);
}

.group-item.selected {
  background: var(--lumi-primary-light);
}

.group-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.group-icon.ai-only {
  background: rgba(139, 92, 246, 0.1);
  color: #8b5cf6;
}

.group-icon.mixed {
  background: rgba(20, 126, 188, 0.1);
  color: var(--lumi-primary);
}

.group-info {
  flex: 1;
  min-width: 0;
}

.group-top-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.group-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.group-member-count {
  font-size: 11px;
  color: var(--text-muted);
}

.group-preview {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}

.group-delete-btn {
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  opacity: 0;
  transition: all 300ms ease-in-out;
  flex-shrink: 0;
}

.group-item:hover .group-delete-btn {
  opacity: 1;
}

.group-delete-btn:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.list-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--text-muted);
  gap: 8px;
}

.list-empty p {
  font-size: 12px;
  text-align: center;
}

.social-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--divider-soft);
  flex-shrink: 0;
}

.chat-title-area {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-avatar-mini {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-title-text h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.chat-status-line {
  font-size: 11px;
  color: var(--text-muted);
}

.chat-actions {
  display: flex;
  gap: 4px;
}

.chat-action-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all 300ms ease-in-out;
}

.chat-action-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.chat-members-bar {
  padding: 8px 20px;
  border-bottom: 1px solid var(--divider-soft);
  flex-shrink: 0;
}

.members-scroll {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: none;
}

.members-scroll::-webkit-scrollbar {
  display: none;
}

.member-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  flex-shrink: 0;
}

.member-role {
  font-size: 10px;
  opacity: 0.7;
}

.member-remove {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 200ms ease-in-out;
}

.member-chip:hover .member-remove {
  opacity: 1;
}

.member-remove:hover {
  background: rgba(0, 0, 0, 0.1);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.msg-row {
  margin-bottom: 16px;
  display: flex;
  gap: 8px;
  align-items: flex-start;
  animation: msg-slide-in 0.3s ease-out both;
}

@keyframes msg-slide-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-avatar {
  flex-shrink: 0;
}

.avatar-agent {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.msg-bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: var(--radius-lg);
  font-size: 13px;
  line-height: 1.6;
}

.msg-bubble.agent {
  background: var(--workspace-card);
  color: var(--text-primary);
  border-top-left-radius: 4px;
}

.msg-bubble.user {
  background: linear-gradient(135deg, rgba(20, 126, 188, 0.08), rgba(20, 126, 188, 0.04));
  color: var(--text-primary);
  border-top-right-radius: 4px;
}

.msg-sender {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.msg-role-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background: rgba(20, 126, 188, 0.1);
  color: var(--lumi-primary);
  font-weight: 500;
}

.msg-text {
  margin: 0;
  word-break: break-word;
}

.msg-time {
  font-size: 10px;
  color: var(--text-muted);
  display: block;
  margin-top: 4px;
}

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: rgba(20, 126, 188, 0.1);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--text-muted);
  gap: 8px;
}

.chat-empty p {
  font-size: 13px;
}

.chat-input-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--divider-soft);
  flex-shrink: 0;
}

.input-tools {
  display: flex;
  gap: 4px;
}

.input-tool-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all 300ms ease-in-out;
}

.input-tool-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.input-main {
  flex: 1;
  display: flex;
  gap: 8px;
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  padding: 4px 4px 4px 14px;
  box-shadow: var(--shadow-xs);
}

.input-main input {
  flex: 1;
  background: transparent;
  font-size: 13px;
  color: var(--text-primary);
  padding: 6px 0;
}

.input-main input::placeholder {
  color: var(--text-muted);
}

.input-send-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: var(--lumi-primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 300ms ease-in-out;
  flex-shrink: 0;
}

.input-send-btn:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.input-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spin-animation {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.social-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.empty-visual {
  position: relative;
  margin-bottom: 8px;
}

.empty-orb {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.social-empty h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.social-empty p {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
}

.empty-action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  background: var(--lumi-primary);
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 300ms ease-in-out;
  margin-top: 8px;
}

.empty-action-btn:hover {
  background: var(--lumi-primary-hover);
  transform: translateY(-1px);
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  backdrop-filter: blur(4px);
}

.add-dialog {
  background: var(--workspace-card);
  border-radius: var(--radius-xl);
  padding: 24px;
  width: 420px;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: var(--shadow-xl);
  animation: dialog-enter 0.3s ease-out both;
}

@keyframes dialog-enter {
  from { opacity: 0; transform: scale(0.95) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.add-dialog h3 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 16px;
}

.form-group {
  margin-bottom: 12px;
}

.form-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.required-mark {
  color: var(--lumi-accent);
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-primary);
  transition: all 300ms ease-in-out;
}

.form-input:focus {
  box-shadow: 0 0 0 2px var(--lumi-primary-glow);
}

.form-input::placeholder {
  color: var(--text-muted);
}

.agent-select-list {
  max-height: 200px;
  overflow-y: auto;
  margin-bottom: 12px;
}

.agent-select-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 300ms ease-in-out;
}

.agent-select-item:hover {
  background: var(--workspace-hover);
}

.agent-select-item.selected {
  background: var(--lumi-primary-light);
}

.agent-select-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.agent-select-info {
  flex: 1;
  min-width: 0;
}

.agent-select-name {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.agent-select-desc {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dialog-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
  color: var(--text-muted);
  gap: 8px;
}

.dialog-empty p {
  font-size: 12px;
  text-align: center;
}

.dialog-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 16px;
}

.dialog-btn {
  padding: 8px 20px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 300ms ease-in-out;
}

.dialog-btn.cancel {
  color: var(--text-muted);
  background: var(--workspace-panel);
}

.dialog-btn.cancel:hover {
  background: var(--workspace-hover);
}

.dialog-btn.confirm {
  color: white;
  background: var(--lumi-primary);
}

.dialog-btn.confirm:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.dialog-btn.confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.selection-fade-enter-active {
  animation: lumi-fade-in 0.3s ease-out;
}

.selection-fade-leave-active {
  animation: lumi-fade-in 0.2s ease-out reverse;
}
</style>
