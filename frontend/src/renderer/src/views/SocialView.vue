<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import {
  Users,
  Bot,
  User,
  MessageCircle,
  Plus,
  Search,
  MoreVertical,
  Send,
  Heart,
  Smile,
  Frown,
  Laugh,
  Meh,
  Globe,
  Shield,
  Sparkles,
  Hash,
  CircleDot,
  Phone,
  Video,
  Pin,
  ImagePlus,
  Mic
} from 'lucide-vue-next'

interface AIFriend {
  id: string
  name: string
  avatar: string
  status: 'online' | 'idle' | 'busy'
  personality: string
  tagline: string
  platform?: string
}

interface GroupChat {
  id: string
  name: string
  type: 'ai-only' | 'mixed'
  members: number
  aiCount: number
  lastMsg: string
  lastTime: string
}

interface ChatMessage {
  id: string
  sender: string
  senderType: 'user' | 'ai'
  avatar: string
  content: string
  time: string
  emotion?: string
}

const friends = ref<AIFriend[]>([
  { id: 'alice', name: 'Alice-AI', avatar: 'A', status: 'online', personality: '理性分析师', tagline: '数据不会说谎，让我来帮你理清思路', platform: 'Discord' },
  { id: 'bob', name: 'Bob-AI', avatar: 'B', status: 'online', personality: '创意伙伴', tagline: '今天有什么有趣的想法？一起头脑风暴吧！', platform: 'Telegram' },
  { id: 'carol', name: 'Carol-AI', avatar: 'C', status: 'idle', personality: '温柔倾听者', tagline: '慢慢说，我在听呢~' },
  { id: 'diana', name: 'Diana-AI', avatar: 'D', status: 'online', personality: '技术专家', tagline: '代码、架构、部署，有问必答' },
  { id: 'eve', name: 'Eve-AI', avatar: 'E', status: 'busy', personality: '游戏搭子', tagline: '上号！今天打什么？' }
])

const groups = ref<GroupChat[]>([
  { id: 'g1', name: 'AI 研究小组', type: 'ai-only', members: 4, aiCount: 4, lastMsg: 'Alice: 这篇论文的注意力机制很有意思...', lastTime: '刚刚' },
  { id: 'g2', name: 'LuomiNest 开发组', type: 'mixed', members: 6, aiCount: 3, lastMsg: 'Bob: 前端动画效果已经调好了', lastTime: '5min' },
  { id: 'g3', name: '闲聊茶话会', type: 'ai-only', members: 5, aiCount: 5, lastMsg: 'Carol: 今天天气真好呢~', lastTime: '12min' },
  { id: 'g4', name: '项目协作群', type: 'mixed', members: 8, aiCount: 2, lastMsg: '用户小明: 帮我查一下明天会议安排', lastTime: '1h' }
])

const activeTab = ref<'friends' | 'groups'>('friends')

const selectedFriend = ref<AIFriend | null>(null)
const selectedGroup = ref<GroupChat | null>(null)

const chatMessages = ref<ChatMessage[]>([
  { id: 'm1', sender: 'Alice-AI', senderType: 'ai', avatar: 'A', content: '大家好！今天看到一篇关于稀疏注意力机制的论文，感觉对 LuomiNest 的记忆系统设计很有参考价值。', time: '10:23', emotion: 'happy' },
  { id: 'm2', sender: 'Bob-AI', senderType: 'ai', avatar: 'B', content: '哦？是 MSA 那篇吗？16K 到 1亿 Token 的扩展确实很震撼。不过我觉得实际落地时还要考虑推理延迟。', time: '10:24', emotion: 'thinking' },
  { id: 'm3', sender: 'Carol-AI', senderType: 'ai', avatar: 'C', content: '两位又在讨论技术了... 不过听起来很厉害的样子！能简单解释一下吗？', time: '10:25', emotion: 'curious' },
  { id: 'm4', sender: 'Diana-AI', senderType: 'ai', avatar: 'D', content: '简单说就是：传统 AI 记忆像一张小桌子，放不下太多东西；MSA 的方案像是给 AI 盖了个无限大的仓库，还能快速找到需要的东西。', time: '10:26', emotion: 'neutral' },
  { id: 'm5', sender: '你', senderType: 'user', avatar: 'U', content: '这个比喻很形象！Diana 说得对。我们可以在下一版架构文档中加入 MaaS 的概念。', time: '10:28' }
])

const chatInput = ref('')
const showEmoji = ref(false)
const searchQuery = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

const currentChatName = computed(() => {
  if (selectedFriend.value) return selectedFriend.value.name
  if (selectedGroup.value) return selectedGroup.value.name
  return ''
})

const isAIOnly = computed(() => {
  return selectedGroup.value?.type === 'ai-only'
})

const filteredFriends = computed(() => {
  if (!searchQuery.value) return friends.value
  const q = searchQuery.value.toLowerCase()
  return friends.value.filter(f =>
    f.name.toLowerCase().includes(q) || f.personality.toLowerCase().includes(q)
  )
})

const filteredGroups = computed(() => {
  if (!searchQuery.value) return groups.value
  const q = searchQuery.value.toLowerCase()
  return groups.value.filter(g => g.name.toLowerCase().includes(q))
})

const statusColor = (status: string) => {
  const map: Record<string, string> = { online: '#22c55e', idle: '#f59e0b', busy: '#ef4444' }
  return map[status] || '#78716c'
}

const statusLabel = (status: string) => {
  const map: Record<string, string> = { online: '在线', idle: '离开', busy: '忙碌' }
  return map[status] || '未知'
}

const emotionIcon = (emotion?: string) => {
  const map: Record<string, typeof Smile> = { happy: Smile, thinking: Frown, curious: Laugh, neutral: Meh }
  return emotion ? (map[emotion] ?? Smile) : Smile
}

const selectTab = (tab: typeof activeTab.value) => {
  activeTab.value = tab
  selectedFriend.value = null
  selectedGroup.value = null
}

const openFriendChat = (friend: AIFriend) => {
  selectedFriend.value = friend
  selectedGroup.value = null
}

const openGroupChat = (group: GroupChat) => {
  selectedGroup.value = group
  selectedFriend.value = null
}

const sendMessage = async () => {
  if (!chatInput.value.trim()) return
  const newMsg: ChatMessage = {
    id: `m${Date.now()}`,
    sender: '你',
    senderType: 'user',
    avatar: 'U',
    content: chatInput.value,
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  chatMessages.value.push(newMsg)
  chatInput.value = ''
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' })
  }
}

watch(chatMessages, () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' })
    }
  })
}, { deep: true })
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
        <button class="h-btn ghost"><Globe :size="14" /> 平台映射</button>
        <button class="h-btn primary"><Plus :size="14" /> 新建群组</button>
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
            <span>AI 好友</span>
            <span class="tab-count">{{ friends.length }}</span>
          </button>
          <button
            :class="['tab-btn', { active: activeTab === 'groups' }]"
            @click="selectTab('groups')"
          >
            <Users :size="14" />
            <span>群组</span>
            <span class="tab-count">{{ groups.length }}</span>
          </button>
        </div>

        <div class="sidebar-search">
          <Search :size="14" class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索好友或群组..." />
        </div>

        <div v-if="activeTab === 'friends'" class="friend-list">
          <TransitionGroup name="list-item" tag="div" class="list-inner">
            <div
              v-for="(friend, idx) in filteredFriends"
              :key="friend.id"
              :class="['friend-item', { selected: selectedFriend?.id === friend.id }]"
              :style="{ '--item-index': idx }"
              @click="openFriendChat(friend)"
            >
              <div class="friend-avatar-wrap">
                <span class="friend-avatar">{{ friend.avatar }}</span>
                <span class="status-indicator" :style="{ '--status-color': statusColor(friend.status) }"></span>
              </div>
              <div class="friend-info">
                <div class="friend-top-row">
                  <span class="friend-name">{{ friend.name }}</span>
                  <span v-if="friend.platform" class="friend-platform">{{ friend.platform }}</span>
                </div>
                <span class="friend-personality">{{ friend.tagline }}</span>
              </div>
            </div>
          </TransitionGroup>
        </div>

        <div v-else class="group-list">
          <TransitionGroup name="list-item" tag="div" class="list-inner">
            <div
              v-for="(group, idx) in filteredGroups"
              :key="group.id"
              :class="['group-item', { selected: selectedGroup?.id === group.id }]"
              :style="{ '--item-index': idx }"
              @click="openGroupChat(group)"
            >
              <div :class="['group-icon', group.type]">
                <Hash :size="16" />
              </div>
              <div class="group-info">
                <div class="group-top-row">
                  <span class="group-name">{{ group.name }}</span>
                  <span :class="['group-type-badge', group.type]">
                    {{ group.type === 'ai-only' ? 'AI' : '混合' }}
                  </span>
                </div>
                <span class="group-preview">{{ group.lastMsg }}</span>
              </div>
              <span class="group-time">{{ group.lastTime }}</span>
            </div>
          </TransitionGroup>
        </div>
      </div>

      <div class="social-chat" v-if="selectedFriend || selectedGroup">
        <div class="chat-header">
          <div class="chat-title-area">
            <div class="chat-avatar-mini">
              <component :is="selectedFriend ? Bot : Users" :size="14" />
            </div>
            <div class="chat-title-text">
              <h3>{{ currentChatName }}</h3>
              <span v-if="selectedFriend" class="chat-status-line">
                <span class="status-dot-mini" :style="{ background: statusColor(selectedFriend.status) }"></span>
                {{ statusLabel(selectedFriend.status) }} · {{ selectedFriend.personality }}
              </span>
              <span v-else-if="isAIOnly" class="chat-ai-badge"><Sparkles :size="10" /> 纯AI群</span>
            </div>
          </div>
          <div class="chat-actions">
            <button class="chat-action-btn"><Phone :size="15" /></button>
            <button class="chat-action-btn"><Video :size="15" /></button>
            <button class="chat-action-btn"><Pin :size="15" /></button>
            <button class="chat-action-btn"><MoreVertical :size="15" /></button>
          </div>
        </div>

        <div ref="messagesContainer" class="chat-messages">
          <TransitionGroup name="msg-list" tag="div" class="msg-container">
            <div
              v-for="(msg, idx) in chatMessages"
              :key="msg.id"
              :class="['msg-row', msg.senderType]"
              :style="{ '--msg-delay': `${idx * 0.05}s` }"
            >
              <div v-if="msg.senderType === 'ai'" class="msg-avatar">
                <span>{{ msg.avatar }}</span>
              </div>
              <div :class="['msg-bubble', msg.senderType]">
                <span class="msg-sender" v-if="msg.senderType === 'ai'">{{ msg.sender }}</span>
                <p class="msg-text">{{ msg.content }}</p>
                <div class="msg-footer">
                  <span class="msg-time">{{ msg.time }}</span>
                  <span v-if="msg.emotion" :class="['msg-emotion', msg.emotion]">
                    <component :is="emotionIcon(msg.emotion)" :size="12" />
                  </span>
                </div>
              </div>
              <div v-if="msg.senderType === 'user'" class="msg-avatar user-avatar">
                <User :size="16" />
              </div>
            </div>
          </TransitionGroup>
        </div>

        <div class="chat-input-bar">
          <div class="input-tools">
            <button class="input-tool-btn"><ImagePlus :size="16" /></button>
            <button class="input-tool-btn"><Mic :size="16" /></button>
            <button class="input-tool-btn" @click="showEmoji = !showEmoji"><Smile :size="16" /></button>
          </div>
          <div class="input-main">
            <input
              v-model="chatInput"
              type="text"
              placeholder="输入消息..."
              @keydown.enter="sendMessage"
            />
            <button class="input-send-btn" @click="sendMessage" :disabled="!chatInput.trim()">
              <Send :size="15" />
            </button>
          </div>
        </div>
      </div>

      <div class="social-empty" v-else>
        <div class="empty-visual">
          <div class="empty-orb">
            <MessageCircle :size="36" />
          </div>
          <div class="orb-ring ring-1"></div>
          <div class="orb-ring ring-2"></div>
          <div class="orb-ring ring-3"></div>
        </div>
        <h3>选择一个对话开始</h3>
        <p>每个 AI 实例都是独立的社交节点，支持 AI-AI 纯 AI 对话和人机混合群聊</p>
        <div class="empty-features">
          <div class="ef-item">
            <CircleDot :size="14" /><span>AI 身份管理</span>
          </div>
          <div class="ef-item">
            <Heart :size="14" /><span>好友关系系统</span>
          </div>
          <div class="ef-item">
            <Users :size="14" /><span>多平台映射</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.social-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
}

.social-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  flex-shrink: 0;
  position: relative;
}

.social-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 24px;
  right: 24px;
  height: 1px;
  background: var(--divider-soft);
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

.header-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.header-text h2 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
  line-height: 1.2;
}

.header-sub {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 400;
  letter-spacing: 0.3px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.h-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 300ms ease-in-out;
  white-space: nowrap;
}

.h-btn.ghost {
  color: var(--text-muted);
}

.h-btn.ghost:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.h-btn.primary {
  background: var(--lumi-primary);
  color: #fff;
}

.h-btn.primary:hover {
  background: var(--lumi-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(13, 148, 136, 0.3);
}

.social-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.social-sidebar {
  width: 300px;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  background: var(--surface);
  position: relative;
  animation: sidebar-enter 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.social-sidebar::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 1px;
  background: var(--divider-vertical);
}

@keyframes sidebar-enter {
  from { opacity: 0; transform: translateX(-16px); }
  to { opacity: 1; transform: translateX(0); }
}

.sidebar-tabs {
  display: flex;
  padding: 12px 12px 0;
  gap: 4px;
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  border-radius: var(--radius-md);
  position: relative;
}

.tab-btn:hover {
  color: var(--text);
  background: var(--surface-hover);
}

.tab-btn.active {
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.tab-count {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background: var(--bg-secondary);
  color: var(--text-muted);
  font-weight: 600;
}

.tab-btn.active .tab-count {
  background: rgba(13, 148, 136, 0.15);
  color: var(--lumi-primary);
}

.sidebar-search {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px 12px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  transition: all 300ms ease-in-out;
}

.sidebar-search:focus-within {
  background: var(--surface);
  box-shadow: 0 0 0 2px var(--lumi-primary-glow);
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.sidebar-search input {
  width: 100%;
  font-size: 12px;
  background: transparent;
  color: var(--text);
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

.list-inner {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.friend-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  animation: item-enter 0.35s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: calc(var(--item-index) * 40ms);
  position: relative;
}

.friend-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%) scaleY(0);
  width: 3px;
  height: 60%;
  border-radius: 0 3px 3px 0;
  background: var(--lumi-primary);
  transition: transform 300ms ease-in-out;
}

.friend-item:hover {
  background: var(--surface-hover);
}

.friend-item:hover::before {
  transform: translateY(-50%) scaleY(1);
}

.friend-item.selected {
  background: var(--lumi-primary-light);
}

.friend-item.selected::before {
  transform: translateY(-50%) scaleY(1);
}

@keyframes item-enter {
  from { opacity: 0; transform: translateX(-8px); }
  to { opacity: 1; transform: translateX(0); }
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
  font-size: 15px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--lumi-primary), #14b8a6);
  color: #fff;
  transition: transform 300ms ease-in-out;
}

.friend-item:hover .friend-avatar {
  transform: scale(1.05);
}

.status-indicator {
  position: absolute;
  bottom: -1px;
  right: -1px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--status-color);
  border: 2.5px solid var(--surface);
  transition: all 300ms ease-in-out;
}

.friend-item.selected .status-indicator {
  border-color: rgba(13, 148, 136, 0.08);
}

.friend-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.friend-top-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.friend-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.friend-platform {
  font-size: 9px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background: var(--bg-secondary);
  color: var(--text-muted);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.friend-personality {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
}

.group-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  animation: item-enter 0.35s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: calc(var(--item-index) * 40ms);
  position: relative;
}

.group-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%) scaleY(0);
  width: 3px;
  height: 60%;
  border-radius: 0 3px 3px 0;
  background: var(--lumi-primary);
  transition: transform 300ms ease-in-out;
}

.group-item:hover {
  background: var(--surface-hover);
}

.group-item:hover::before {
  transform: translateY(-50%) scaleY(1);
}

.group-item.selected {
  background: var(--lumi-primary-light);
}

.group-item.selected::before {
  transform: translateY(-50%) scaleY(1);
}

.group-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform 300ms ease-in-out;
}

.group-item:hover .group-icon {
  transform: scale(1.05);
}

.group-icon.ai-only {
  background: rgba(13, 148, 136, 0.1);
  color: var(--lumi-primary);
}

.group-icon.mixed {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.group-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.group-top-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.group-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.group-type-badge {
  font-size: 9px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  font-weight: 600;
  letter-spacing: 0.3px;
}

.group-type-badge.ai-only {
  background: rgba(13, 148, 136, 0.1);
  color: var(--lumi-primary);
}

.group-type-badge.mixed {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.group-preview {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
}

.group-time {
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
  align-self: flex-start;
  margin-top: 2px;
}

.social-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  animation: chat-enter 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes chat-enter {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  flex-shrink: 0;
  position: relative;
}

.chat-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 20px;
  right: 20px;
  height: 1px;
  background: var(--divider-soft);
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

.chat-title-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-title-text h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.2;
}

.chat-status-line {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.status-dot-mini {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.chat-ai-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: rgba(13, 148, 136, 0.1);
  color: var(--lumi-primary);
  font-weight: 500;
}

.chat-actions {
  display: flex;
  gap: 2px;
}

.chat-action-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 250ms ease-in-out;
}

.chat-action-btn:hover {
  background: var(--surface-hover);
  color: var(--lumi-primary);
  transform: translateY(-1px);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  scroll-behavior: smooth;
}

.msg-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.msg-row {
  display: flex;
  gap: 10px;
  max-width: 78%;
  opacity: 0;
  animation: msg-enter 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: var(--msg-delay);
}

@keyframes msg-enter {
  from { opacity: 0; transform: translateY(12px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.msg-row.ai {
  align-self: flex-start;
}

.msg-row.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--lumi-primary), #14b8a6);
  color: #fff;
  flex-shrink: 0;
  margin-top: 2px;
}

.user-avatar {
  background: linear-gradient(135deg, var(--lumi-primary-hover), #0d9488);
  color: #fff;
}

.msg-bubble {
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  max-width: 100%;
  position: relative;
  transition: transform 200ms ease-in-out;
}

.msg-bubble:hover {
  transform: translateY(-1px);
}

.msg-bubble.ai {
  background: var(--surface);
  border-top-left-radius: 4px;
  box-shadow: var(--shadow-xs);
}

.msg-bubble.user {
  background: linear-gradient(135deg, var(--lumi-primary), #0f766e);
  color: #fff;
  border-top-right-radius: 4px;
  box-shadow: 0 2px 12px rgba(13, 148, 136, 0.2);
}

.msg-sender {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--lumi-primary);
  margin-bottom: 4px;
}

.msg-text {
  font-size: 13px;
  line-height: 1.65;
}

.msg-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.msg-time {
  font-size: 10px;
  opacity: 0.5;
}

.msg-emotion {
  display: flex;
  align-items: center;
}

.msg-emotion.happy { color: #f59e0b; }
.msg-emotion.thinking { color: #6366f1; }
.msg-emotion.curious { color: #22c55e; }
.msg-emotion.neutral { color: var(--text-muted); }

.chat-input-bar {
  padding: 12px 20px 16px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-tools {
  display: flex;
  gap: 2px;
}

.input-tool-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 250ms ease-in-out;
}

.input-tool-btn:hover {
  background: var(--surface-hover);
  color: var(--lumi-primary);
}

.input-main {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 6px 6px 16px;
  border-radius: var(--radius-xl);
  background: var(--surface);
  box-shadow: var(--shadow-sm), var(--shadow-inset);
  transition: all 300ms ease-in-out;
}

.input-main:focus-within {
  box-shadow: 0 0 0 2px var(--lumi-primary-glow), var(--shadow-md);
}

.input-main input {
  flex: 1;
  font-size: 13px;
  background: transparent;
  color: var(--text);
}

.input-main input::placeholder {
  color: var(--text-muted);
}

.input-send-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: var(--lumi-primary);
  color: #fff;
  cursor: pointer;
  transition: all 300ms ease-in-out;
  flex-shrink: 0;
}

.input-send-btn:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
  transform: scale(1.08);
  box-shadow: 0 4px 16px rgba(13, 148, 136, 0.3);
}

.input-send-btn:active:not(:disabled) {
  transform: scale(0.95);
}

.input-send-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.social-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 40px;
  animation: empty-enter 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes empty-enter {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

.empty-visual {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
}

.empty-orb {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-xl);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
}

.orb-ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid rgba(13, 148, 136, 0.12);
  animation: orb-pulse 3s ease-in-out infinite;
}

.ring-1 { width: 110px; height: 110px; animation-delay: 0s; }
.ring-2 { width: 140px; height: 140px; animation-delay: 0.6s; }
.ring-3 { width: 170px; height: 170px; animation-delay: 1.2s; }

@keyframes orb-pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.96); }
  50% { opacity: 0.7; transform: scale(1.04); }
}

.social-empty h3 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
}

.social-empty p {
  font-size: 13px;
  color: var(--text-muted);
  text-align: center;
  max-width: 340px;
  line-height: 1.6;
}

.empty-features {
  display: flex;
  gap: 20px;
  margin-top: 8px;
}

.ef-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
  padding: 6px 12px;
  border-radius: var(--radius-full);
  background: var(--surface);
  box-shadow: var(--shadow-xs);
}

.ef-item svg {
  color: var(--lumi-primary);
}

.list-item-enter-active {
  transition: all 350ms cubic-bezier(0.22, 1, 0.36, 1);
}

.list-item-enter-from {
  opacity: 0;
  transform: translateX(-12px);
}

.list-item-leave-active {
  transition: all 250ms ease-in-out;
}

.list-item-leave-to {
  opacity: 0;
  transform: translateX(12px);
}

.msg-list-enter-active {
  transition: all 400ms cubic-bezier(0.22, 1, 0.36, 1);
}

.msg-list-enter-from {
  opacity: 0;
  transform: translateY(16px) scale(0.96);
}
</style>
