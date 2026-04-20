<script setup lang="ts">
import { ref } from 'vue'
import {
  Send,
  Paperclip,
  Mic,
  Wand2,
  ChevronDown,
  Sparkles,
  Bot,
  AtSign,
  Link2,
  MoreHorizontal
} from 'lucide-vue-next'

const selectedAgent = ref('代可行')

const agentCards = ref([
  {
    name: '无言',
    desc: '寡言的自由撰稿人',
    color: '#6366f1',
    avatar: null
  },
  {
    name: '代可行',
    desc: '热爱手搓的程序员',
    color: '#0d9488',
    avatar: null,
    selected: true
  },
  {
    name: '林且慢',
    desc: '少年系系的辅导员',
    color: '#f59e0b',
    avatar: null
  },
  {
    name: '自定义',
    desc: '创建全新 Agent',
    color: '#f43f5e',
    avatar: null
  }
])

const messages = ref([
  {
    id: 1,
    role: 'assistant' as const,
    content: `好嘞，你已选择Agent"代可行"，这是TA的人物介绍～\n\n• 名字：代可行\n• 一句话介绍：热爱手搓的程序员\n• 经历：计算机出身，毕业后在大厂做了四年后端开发。代码review从不废话，批注从不解释为什么，默认你能看懂。下班后爱打游戏，风险甚高。\n• 风格：极度务实，只关注能不能解决问题，以结果为导向。沉默寡言但并非冷漠，对自己要求严苛，极度自律。冷静理性，几乎不会情绪化，擅长寻找对策。`,
    time: '14:32'
  }
])

const inputText = ref('')
const showAgentPicker = ref(true)

const sendMessage = () => {
  if (!inputText.value.trim()) return
  messages.value.push({
    id: Date.now(),
    role: 'user',
    content: inputText.value,
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  })
  inputText.value = ''
}

const quickActions = [
  { label: '修改', action: 'edit' },
  { label: '很完美，就是TA了', action: 'confirm' }
]
</script>

<template>
  <div class="workspace-view">
    <div class="workspace-header">
      <div class="header-left">
        <span class="header-badge">
          <Sparkles :size="14" />
          龙虾管家
        </span>
        <span class="header-stats">
          <AtSign :size="13" />
          已用4.1万，剩余99%
        </span>
      </div>
      <div class="header-right">
        <button class="header-icon-btn" title="历史记录">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        </button>
      </div>
    </div>

    <div class="agent-selector-row">
      <div class="agent-cards-scroll">
        <button
          v-for="(card, idx) in agentCards"
          :key="card.name"
          :class="['agent-card', { selected: card.selected }]"
          :style="{ animationDelay: `${idx * 60}ms` }"
        >
          <div class="card-avatar" :style="{ background: card.color + '14', color: card.color, borderColor: card.selected ? card.color : 'transparent' }">
            <Bot v-if="card.name !== '自定义'" :size="26" />
            <Sparkles v-else :size="26" />
          </div>
          <div class="card-info">
            <span class="card-name">{{ card.name }}</span>
            <span class="card-desc">{{ card.desc }}</span>
          </div>
        </button>
      </div>
      <Transition name="selection-fade">
        <div v-if="selectedAgent" class="selection-toast">
          我选择「{{ selectedAgent }}」作为我的新Agent
        </div>
      </Transition>
    </div>

    <div class="chat-area">
      <div class="messages-container">
        <div
          v-for="msg in messages"
          :key="msg.id"
          :class="['message-row', msg.role]"
        >
          <div class="message-bubble">
            <div class="message-content" v-html="formatMessage(msg.content)"></div>
            <div v-if="msg.role === 'assistant'" class="quick-actions">
              <button
                v-for="action in quickActions"
                :key="action.label"
                class="quick-action-btn"
              >
                {{ action.label }}
              </button>
            </div>
          </div>
        </div>

        <div class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>

    <div class="input-area">
      <div class="input-wrapper">
        <textarea
          v-model="inputText"
          placeholder="可以描述任务或提问任何问题"
          rows="1"
          class="chat-input"
          @keydown.enter.exact.prevent="sendMessage"
        ></textarea>
        <div class="input-toolbar">
          <div class="toolbar-left">
            <button class="tool-btn" title="选择模型">
              <Wand2 :size="16" />
              <span>默认大模型</span>
              <ChevronDown :size="14" />
            </button>
            <button class="tool-btn" title="技能">
              <Link2 :size="16" />
              <span>技能</span>
              <ChevronDown :size="14" />
            </button>
            <button class="tool-btn" title="找灵感">
              <Sparkles :size="16" />
              <span>找灵感</span>
              <ChevronDown :size="14" />
            </button>
            <button class="tool-btn icon-only" title="更多">
              <MoreHorizontal :size="16" />
            </button>
          </div>
          <div class="toolbar-right">
            <button class="tool-btn icon-only" title="附件">
              <Paperclip :size="16" />
            </button>
            <button class="tool-btn icon-only" title="语音">
              <Mic :size="16" />
            </button>
            <button class="send-btn" title="发送" @click="sendMessage">
              <Send :size="17" />
            </button>
          </div>
        </div>
      </div>
      <div class="input-footer">
        <span>内容由AI生成，请仔细核对</span>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
function formatMessage(text: string): string {
  return text
    .replace(/\n/g, '<br>')
    .replace(/•\s*/g, '<span class="bullet">•</span>&nbsp;')
}
</script>

<style scoped>
.workspace-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  flex-shrink: 0;
  position: relative;
}

.workspace-header::after {
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
  gap: 16px;
}

.header-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.header-stats {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.header-right {
  display: flex;
  gap: 4px;
}

.header-icon-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.header-icon-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.agent-selector-row {
  padding: 16px 24px 0;
  position: relative;
  flex-shrink: 0;
}

.agent-cards-scroll {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 12px;
  scrollbar-width: none;
}

.agent-cards-scroll::-webkit-scrollbar {
  display: none;
}

.agent-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px 10px 10px;
  border-radius: var(--radius-lg);
  border: 1.5px solid transparent;
  background: var(--workspace-card);
  cursor: pointer;
  transition: all var(--transition-normal);
  flex-shrink: 0;
  animation: lumi-fade-in 0.4s ease-out both;
  box-shadow: var(--shadow-xs);
}

.agent-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.agent-card.selected {
  border-color: var(--lumi-primary);
  background: white;
  box-shadow: 0 4px 20px rgba(13, 148, 136, 0.12);
}

.card-avatar {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid transparent;
  transition: border-color var(--transition-fast);
}

.card-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
}

.card-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.card-desc {
  font-size: 11px;
  color: var(--text-muted);
  max-width: 120px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.selection-toast {
  margin-top: 10px;
  text-align: center;
  font-size: 13px;
  color: var(--lumi-accent);
  background: var(--lumi-accent-light);
  padding: 8px 20px;
  border-radius: var(--radius-full);
  display: inline-block;
  width: 100%;
}

.selection-fade-enter-active {
  animation: lumi-fade-in 0.3s ease-out;
}

.selection-fade-leave-active {
  animation: lumi-fade-in 0.2s ease-out reverse;
}

.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.messages-container {
  max-width: 800px;
  margin: 0 auto;
}

.message-row {
  margin-bottom: 20px;
  animation: lumi-slide-up 0.3s ease-out both;
}

.message-bubble {
  max-width: 85%;
}

.message-content {
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-primary);
  padding: 16px 20px;
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  box-shadow: var(--shadow-xs);
}

.message-content :deep(.bullet) {
  color: var(--lumi-primary);
  font-weight: 600;
}

.message-row.assistant .message-bubble {
  border-top-left-radius: 4px;
}

.message-row.user .message-bubble {
  margin-left: auto;
  border-top-right-radius: 4px;
  background: linear-gradient(135deg, var(--lumi-primary), #14b8a6);
  color: white;
}

.quick-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  padding: 0 4px;
}

.quick-action-btn {
  padding: 7px 18px;
  border-radius: var(--radius-full);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.quick-action-btn:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.typing-indicator {
  display: flex;
  gap: 5px;
  padding: 12px 16px;
  opacity: 0.4;
}

.typing-indicator span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: lumi-pulse-soft 1.4s ease-in-out infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

.input-area {
  padding: 12px 24px 16px;
  flex-shrink: 0;
}

.input-wrapper {
  background: var(--workspace-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm), var(--shadow-inset);
  overflow: hidden;
  transition: all var(--transition-fast);
}

.input-wrapper:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow), var(--shadow-lg);
}

.chat-input {
  width: 100%;
  padding: 14px 20px;
  font-size: 14px;
  resize: none;
  min-height: 48px;
  max-height: 120px;
  background: transparent;
  color: var(--text-primary);
  line-height: 1.5;
}

.chat-input::placeholder {
  color: var(--text-muted);
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px 12px;
  position: relative;
}

.input-toolbar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 16px;
  right: 16px;
  height: 1px;
  background: var(--divider-soft);
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.tool-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
}

.tool-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.tool-btn.icon-only {
  padding: 6px;
}

.send-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: var(--lumi-primary);
  color: white;
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-left: 4px;
}

.send-btn:hover {
  background: var(--lumi-primary-hover);
  transform: scale(1.05);
}

.send-btn:active {
  transform: scale(0.95);
}

.input-footer {
  text-align: center;
  margin-top: 8px;
}

.input-footer span {
  font-size: 11px;
  color: var(--text-muted);
}
</style>
