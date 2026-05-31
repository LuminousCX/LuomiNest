<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { Terminal, Play, Square, Trash2, Copy, ChevronRight, AlertTriangle, Info, CheckCircle2, XCircle, Maximize2, Minimize2 } from 'lucide-vue-next'

interface LogEntry {
  id: number
  timestamp: string
  level: 'info' | 'warn' | 'error' | 'success'
  source: string
  message: string
}

const commandInput = ref('')
const isRunning = ref(false)
const isExpanded = ref(false)
const activeTab = ref<'console' | 'logs'>('console')
const logs = ref<LogEntry[]>([])
const logIdCounter = ref(0)

const addLog = (level: LogEntry['level'], source: string, message: string) => {
  const now = new Date()
  const ts = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  logs.value.unshift({
    id: logIdCounter.value++,
    timestamp: ts,
    level,
    source,
    message,
  })
  if (logs.value.length > 200) {
    logs.value = logs.value.slice(0, 200)
  }
}

onMounted(() => {
  addLog('info', 'System', 'LuomiNest 控制台已启动')
  addLog('success', 'API', '所有模型接口连接正常')
  addLog('info', 'Memory', '长期记忆已加载 (45 条)')
  addLog('warn', 'IoT', 'HomeAssistant 中控连接超时，正在重试...')
  addLog('error', 'Plugin', '插件 "weather-v2" 加载失败: 缺少依赖')
  addLog('info', 'System', '桌面宠物模式就绪')
  addLog('success', 'Agent', 'Agent "小助手" 已激活')
  addLog('info', 'TTS', '语音引擎初始化完成 (采样率: 24000Hz)')
})

const handleCommand = () => {
  const cmd = commandInput.value.trim()
  if (!cmd) return
  addLog('info', 'CMD', `> ${cmd}`)
  commandInput.value = ''

  if (cmd === 'help') {
    addLog('info', 'CMD', '可用命令: help, status, agents, clear, restart <service>')
  } else if (cmd === 'status') {
    addLog('success', 'CMD', '系统状态: 正常运行 | 内存: 256MB | CPU: 12%')
  } else if (cmd === 'agents') {
    addLog('info', 'CMD', '活跃 Agent: 小助手, 代码审查员, 翻译官')
  } else if (cmd === 'clear') {
    logs.value = []
  } else if (cmd.startsWith('restart ')) {
    const service = cmd.replace('restart ', '')
    addLog('warn', 'CMD', `正在重启服务: ${service}...`)
    setTimeout(() => addLog('success', 'CMD', `服务 ${service} 已重启`), 1000)
  } else {
    addLog('error', 'CMD', `未知命令: ${cmd}，输入 help 查看帮助`)
  }
}

const levelIcon = (level: LogEntry['level']) => {
  const map = { info: Info, warn: AlertTriangle, error: XCircle, success: CheckCircle2 }
  return map[level]
}

const copyLogs = () => {
  const text = logs.value.map(l => `[${l.timestamp}] [${l.level.toUpperCase()}] [${l.source}] ${l.message}`).join('\n')
  navigator.clipboard.writeText(text)
}
</script>

<template>
  <div class="console-view">
    <div class="console-header">
      <div class="header-info">
        <h1 class="header-title">控制台</h1>
        <p class="header-desc">执行命令、查看系统日志与运行状态</p>
      </div>
      <div class="header-actions">
        <button class="action-btn ghost" @click="copyLogs">
          <Copy :size="14" />
        </button>
        <button :class="['action-btn ghost', { active: isExpanded }]" @click="isExpanded = !isExpanded">
          <Maximize2 v-if="!isExpanded" :size="14" />
          <Minimize2 v-else :size="14" />
        </button>
      </div>
    </div>

    <div class="tab-bar">
      <button :class="['tab-btn', { active: activeTab === 'console' }]" @click="activeTab = 'console'">
        <Terminal :size="14" />
        命令行
      </button>
      <button :class="['tab-btn', { active: activeTab === 'logs' }]" @click="activeTab = 'logs'">
        <Info :size="14" />
        系统日志
      </button>
    </div>

    <div class="console-body">
      <div class="log-list">
        <div v-for="log in logs" :key="log.id" :class="['log-entry', log.level]">
          <span class="log-time">{{ log.timestamp }}</span>
          <component :is="levelIcon(log.level)" :size="13" class="log-level-icon" />
          <span class="log-source">{{ log.source }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
        <div v-if="logs.length === 0" class="log-empty">
          <Terminal :size="24" />
          <span>暂无日志</span>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'console'" class="command-bar">
      <ChevronRight :size="16" class="prompt-icon" />
      <input
        v-model="commandInput"
        type="text"
        class="command-input"
        placeholder="输入命令 (help 查看帮助)..."
        @keydown.enter="handleCommand"
      />
      <button :class="['run-btn', { active: isRunning }]" @click="isRunning = !isRunning">
        <Square v-if="isRunning" :size="14" />
        <Play v-else :size="14" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.console-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px 28px;
  gap: 12px;
  overflow: hidden;
}

.console-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.header-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}

.header-actions {
  display: flex;
  gap: 4px;
}

.action-btn.ghost {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.action-btn.ghost:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.action-btn.ghost.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.tab-bar {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  width: fit-content;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab-btn.active {
  background: var(--surface);
  color: var(--lumi-primary);
  box-shadow: var(--shadow-xs);
}

.console-body {
  flex: 1;
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  overflow: hidden;
  min-height: 0;
}

.log-list {
  height: 100%;
  overflow-y: auto;
  padding: 12px 16px;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.8;
}

.log-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
  border-radius: 4px;
}

.log-time {
  color: var(--text-muted);
  font-size: 11px;
  flex-shrink: 0;
  width: 70px;
}

.log-level-icon {
  flex-shrink: 0;
}

.log-entry.info .log-level-icon {
  color: var(--lumi-primary);
}

.log-entry.warn .log-level-icon {
  color: var(--lumi-warning);
}

.log-entry.error .log-level-icon {
  color: var(--lumi-accent);
}

.log-entry.success .log-level-icon {
  color: var(--lumi-success);
}

.log-source {
  color: var(--lumi-primary);
  font-weight: 600;
  flex-shrink: 0;
  width: 80px;
}

.log-entry.warn .log-source {
  color: var(--lumi-warning);
}

.log-entry.error .log-source {
  color: var(--lumi-accent);
}

.log-entry.success .log-source {
  color: var(--lumi-success);
}

.log-message {
  color: var(--text-secondary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 60px 0;
  color: var(--text-muted);
  font-family: var(--font-sans);
}

.command-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  flex-shrink: 0;
}

.command-bar:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.prompt-icon {
  color: var(--lumi-primary);
  flex-shrink: 0;
}

.command-input {
  flex: 1;
  background: transparent;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  color: var(--text-primary);
}

.command-input::placeholder {
  color: var(--text-muted);
}

.run-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary);
  color: white;
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.run-btn:hover {
  background: var(--lumi-primary-hover);
}

.run-btn.active {
  background: var(--lumi-accent);
}
</style>
