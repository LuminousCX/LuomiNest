<script setup lang="ts">
import { ref, computed } from 'vue'
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
  CircleDot
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

const currentChatName = computed(() => {
  if (selectedFriend.value) return selectedFriend.value.name
  if (selectedGroup.value) return selectedGroup.value.name
  return ''
})

const isAIOnly = computed(() => {
  return selectedGroup.value?.type === 'ai-only'
})

function selectTab(tab: typeof activeTab.value) {
  activeTab.value = tab
  selectedFriend.value = null
  selectedGroup.value = null
}

function openFriendChat(friend: AIFriend) {
  selectedFriend.value = friend
  selectedGroup.value = null
}

function openGroupChat(group: GroupChat) {
  selectedGroup.value = group
  selectedFriend.value = null
}

function sendMessage() {
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
}
</script>

<template>
  <div class="social-view">
    <div class="social-header">
      <div class="header-left">
        <Users :size="20" />
        <h2>AI 社交</h2>
        <span class="header-badge">AI-AI · 人机混合群</span>
      </div>
      <div class="header-actions">
        <button class="h-btn primary"><Plus :size="15" /> 新建群组</button>
        <button class="h-btn"><Globe :size="15" /> 平台映射</button>
      </div>
    </div>

    <div class="social-body">
      <div class="social-sidebar animate-slide-in-left">
        <div class="sidebar-tabs">
          <button :class="['tab-btn', { active: activeTab === 'friends' }]" @click="selectTab('friends')">
            <Bot :size="14" /> AI 好友
          </button>
          <button :class="['tab-btn', { active: activeTab === 'groups' }]" @click="selectTab('groups')">
            <Users :size="14" /> 群组
          </button>
        </div>

        <div class="sidebar-search">
          <Search :size="13" />
          <input type="text" placeholder="搜索..." />
        </div>

        <div v-if="activeTab === 'friends'" class="friend-list">
          <div
            v-for="friend in friends"
            :key="friend.id"
            :class="['friend-item', { selected: selectedFriend?.id === friend.id }]"
            @click="openFriendChat(friend)"
          >
            <div class="friend-avatar-wrap">
              <span class="friend-avatar">{{ friend.avatar }}</span>
              <span :class="['status-dot', friend.status]"></span>
            </div>
            <div class="friend-info">
              <span class="friend-name">{{ friend.name }}</span>
              <span class="friend-personality">{{ friend.personality }}</span>
            </div>
            <span v-if="friend.platform" class="friend-platform">{{ friend.platform }}</span>
          </div>
        </div>

        <div v-else class="group-list">
          <div
            v-for="group in groups"
            :key="group.id"
            :class="['group-item', { selected: selectedGroup?.id === group.id }]"
            @click="openGroupChat(group)"
          >
            <div :class="['group-icon', group.type]">
              <Hash :size="16" />
            </div>
            <div class="group-info">
              <span class="group-name">{{ group.name }}</span>
              <span class="group-preview">{{ group.lastMsg }}</span>
            </div>
            <div class="group-meta">
              <span :class="['group-type-badge', group.type]">
                {{ group.type === 'ai-only' ? 'AI群' : '混合' }}
              </span>
              <span class="group-time">{{ group.lastTime }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="social-chat animate-fade-up" v-if="selectedFriend || selectedGroup">
        <div class="chat-header">
          <div class="chat-title-area">
            <component :is="selectedFriend ? Bot : Users" :size="18" />
            <h3>{{ currentChatName }}</h3>
            <span v-if="isAIOnly" class="chat-ai-badge"><Sparkles :size="11" /> 纯AI群</span>
            <span v-else-if="selectedFriend" class="chat-status-badge">{{ selectedFriend.personality }}</span>
          </div>
          <div class="chat-actions">
            <button class="chat-action-btn"><Shield :size="15" /></button>
            <button class="chat-action-btn"><MoreVertical :size="15" /></button>
          </div>
        </div>

        <div class="chat-messages">
          <TransitionGroup name="msg-list" tag="div" class="msg-container">
            <div
              v-for="(msg, idx) in chatMessages"
              :key="msg.id"
              :class="['msg-row', msg.senderType]"
              :style="{ '--msg-delay': `${idx * 0.06}s` }"
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
                    <component :is="{ happy: Smile, thinking: Frown, curious: Laugh, neutral: Meh }[msg.emotion as string] ?? Smile" :size="12" />
                  </span>
                </div>
              </div>
              <div v-if="msg.senderType === 'user'" class="msg-avatar user-avatar">
                <User :size="18" />
              </div>
            </div>
          </TransitionGroup>
        </div>

        <div class="chat-input-bar">
          <div class="input-wrapper">
            <button class="input-tool-btn" @click="showEmoji = !showEmoji">
              <Smile :size="17" />
            </button>
            <input
              v-model="chatInput"
              type="text"
              placeholder="输入消息..."
              @keydown.enter="sendMessage"
            />
            <button class="input-send-btn" @click="sendMessage" :disabled="!chatInput.trim()">
              <Send :size="16" />
            </button>
          </div>
        </div>
      </div>

      <div class="social-empty animate-scale-in" v-else>
        <div class="empty-icon-wrap">
          <MessageCircle :size="48" class="empty-icon" />
          <div class="empty-rings">
            <span class="ring ring-1"></span>
            <span class="ring ring-2"></span>
            <span class="ring ring-3"></span>
          </div>
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
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-muted);
}

.header-left h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
}

.header-badge {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 20px;
  background: rgba(236, 72, 153, 0.1);
  color: #ec4899;
  font-weight: 500;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.h-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  white-space: nowrap;
}

.h-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.h-btn.primary {
  background: #ec4899;
  color: #fff;
}

.h-btn.primary:hover {
  background: #db2777;
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(236, 72, 153, 0.35);
}

.social-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.social-sidebar {
  width: 290px;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  background: var(--surface);
}

.sidebar-tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  border-bottom: 2px solid transparent;
}

.tab-btn:hover {
  color: var(--text);
  background: var(--surface-hover);
}

.tab-btn.active {
  color: #ec4899;
  border-bottom-color: #ec4899;
}

.sidebar-search {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px 12px;
  padding: 7px 12px;
  border-radius: 9px;
  background: var(--bg);
  border: 1px solid var(--border);
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

.friend-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 300ms ease-in-out;
}

.friend-item:hover {
  background: var(--surface-hover);
}

.friend-item.selected {
  background: rgba(236, 72, 153, 0.08);
}

.friend-avatar-wrap {
  position: relative;
  flex-shrink: 0;
}

.friend-avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  background: linear-gradient(135deg, #ec4899, #8b5cf6);
  color: #fff;
}

.status-dot {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid var(--surface);
}

.status-dot.online { background: #22c55e; }
.status-dot.idle { background: #f59e0b; }
.status-dot.busy { background: #ef4444; }

.friend-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.friend-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}

.friend-personality {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.friend-platform {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 8px;
  background: var(--bg);
  color: var(--text-muted);
  flex-shrink: 0;
}

.group-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 300ms ease-in-out;
}

.group-item:hover {
  background: var(--surface-hover);
}

.group-item.selected {
  background: rgba(236, 72, 153, 0.08);
}

.group-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.group-icon.ai-only {
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.15), rgba(236, 72, 153, 0.1));
  color: #a78bfa;
}

.group-icon.mixed {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.15), rgba(13, 148, 136, 0.1));
  color: #22c55e;
}

.group-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.group-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}

.group-preview {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.group-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
  flex-shrink: 0;
}

.group-type-badge {
  font-size: 10px;
  padding: 1px 7px;
  border-radius: 8px;
  font-weight: 500;
}

.group-type-badge.ai-only {
  background: rgba(139, 92, 246, 0.12);
  color: #a78bfa;
}

.group-type-badge.mixed {
  background: rgba(34, 197, 94, 0.12);
  color: #22c55e;
}

.group-time {
  font-size: 10px;
  color: var(--text-muted);
}

.social-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.chat-title-area {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #ec4899;
}

.chat-title-area h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}

.chat-ai-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(139, 92, 246, 0.12);
  color: #a78bfa;
  font-weight: 500;
}

.chat-status-badge {
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
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms ease-in-out;
}

.chat-action-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.msg-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.msg-row {
  display: flex;
  gap: 10px;
  max-width: 80%;
  opacity: 0;
  animation: msg-enter 0.35s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: var(--msg-delay);
}

@keyframes msg-enter {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.msg-row.ai {
  align-self: flex-start;
}

.msg-row.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  background: linear-gradient(135deg, #ec4899, #8b5cf6);
  color: #fff;
  flex-shrink: 0;
}

.user-avatar {
  background: linear-gradient(135deg, var(--lumi-primary), #0d9488);
  color: #fff;
}

.msg-bubble {
  padding: 10px 14px;
  border-radius: 14px;
  max-width: 100%;
}

.msg-bubble.ai {
  background: var(--surface);
  border: 1px solid var(--border);
  border-top-left-radius: 4px;
}

.msg-bubble.user {
  background: linear-gradient(135deg, #ec4899, #db2777);
  color: #fff;
  border-top-right-radius: 4px;
}

.msg-sender {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #ec4899;
  margin-bottom: 4px;
}

.msg-text {
  font-size: 13px;
  line-height: 1.6;
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
  padding: 14px 20px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.input-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  transition: all 300ms ease-in-out;
}

.input-wrapper:focus-within {
  border-color: #ec4899;
  box-shadow: 0 0 0 2px rgba(236, 72, 153, 0.12);
}

.input-tool-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms ease-in-out;
  flex-shrink: 0;
}

.input-tool-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.input-wrapper input {
  flex: 1;
  font-size: 13px;
  background: transparent;
  color: var(--text);
}

.input-wrapper input::placeholder {
  color: var(--text-muted);
}

.input-send-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: #ec4899;
  color: #fff;
  cursor: pointer;
  transition: all 300ms ease-in-out;
  flex-shrink: 0;
}

.input-send-btn:hover:not(:disabled) {
  background: #db2777;
  transform: scale(1.05);
  box-shadow: 0 4px 14px rgba(236, 72, 153, 0.35);
}

.input-send-btn:disabled {
  opacity: 0.4;
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
}

.empty-icon-wrap {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-icon {
  color: var(--text-muted);
  opacity: 0.3;
}

.empty-rings {
  position: absolute;
  inset: -20px;
}

.ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1px solid rgba(236, 72, 153, 0.1);
  animation: ring-pulse 3s ease-in-out infinite;
}

.ring-1 { animation-delay: 0s; }
.ring-2 { inset: -10px; animation-delay: 0.5s; }
.ring-3 { inset: -20px; animation-delay: 1s; }

@keyframes ring-pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.95); }
  50% { opacity: 0.7; transform: scale(1.05); }
}

.social-empty h3 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text);
}

.social-empty p {
  font-size: 13px;
  color: var(--text-muted);
  text-align: center;
  max-width: 360px;
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
}

.ef-item svg {
  color: #ec4899;
}

@keyframes slide-in-left {
  0% { opacity: 0; transform: translateX(-20px); }
  100% { opacity: 1; transform: translateX(0); }
}

.animate-slide-in-left {
  animation: slide-in-left 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes fade-up {
  0% { opacity: 0; transform: translateY(20px); }
  100% { opacity: 1; transform: translateY(0); }
}

.animate-fade-up {
  animation: fade-up 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes scale-in {
  0% { opacity: 0; transform: scale(0.94); }
  100% { opacity: 1; transform: scale(1); }
}

.animate-scale-in {
  animation: scale-in 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.msg-list-enter-active {
  transition: all 350ms ease-in-out;
}
.msg-list-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
</style>
