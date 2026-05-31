<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import {
  Terminal, Play, Square, Copy, ChevronRight, AlertTriangle, Info,
  CheckCircle2, XCircle, Maximize2, Minimize2, Upload, RotateCcw,
  Clock, User, Filter, RefreshCw, ChevronDown, Server, Monitor
} from 'lucide-vue-next'
import { useApi } from '../../composables/useApi'
import type { CommandRecord, SystemLogEntry, LogUploadResponse } from '../../types'

const { apiGet, apiPost } = useApi()

const activeTab = ref<'console' | 'logs'>('console')
const isExpanded = ref(false)
const commandInput = ref('')
const isRunning = ref(false)

const commands = ref<CommandRecord[]>([])
const logs = ref<SystemLogEntry[]>([])
const isLoadingCommands = ref(false)
const isLoadingLogs = ref(false)
const isUploading = ref(false)
const uploadResult = ref<string | null>(null)

const logFilterSource = ref<'all' | 'frontend' | 'backend'>('all')
const logFilterLevel = ref<'all' | 'info' | 'warn' | 'error' | 'success'>('all')
const cmdFilterStatus = ref<'all' | 'success' | 'failed' | 'running'>('all')

const showCmdFilter = ref(false)
const showLogFilter = ref(false)

const logListRef = ref<HTMLElement | null>(null)
const cmdListRef = ref<HTMLElement | null>(null)

const filteredCommands = computed(() => {
  if (cmdFilterStatus.value === 'all') return commands.value
  return commands.value.filter(c => c.status === cmdFilterStatus.value)
})

const filteredLogs = computed(() => {
  let result = logs.value
  if (logFilterSource.value !== 'all') {
    result = result.filter(l => l.source === logFilterSource.value)
  }
  if (logFilterLevel.value !== 'all') {
    result = result.filter(l => l.level === logFilterLevel.value)
  }
  return result
})

const formatTimestamp = (iso: string) => {
  const d = new Date(iso)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const formatDuration = (ms: number | null) => {
  if (ms === null) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}min`
}

const statusLabel = (status: CommandRecord['status']) => {
  const map: Record<CommandRecord['status'], string> = {
    success: '成功',
    failed: '失败',
    running: '运行中',
  }
  return map[status]
}

const levelIcon = (level: SystemLogEntry['level']) => {
  const map = { info: Info, warn: AlertTriangle, error: XCircle, success: CheckCircle2 }
  return map[level]
}

const fetchCommands = async () => {
  isLoadingCommands.value = true
  try {
    const data = await apiGet<CommandRecord[]>('/console/commands')
    commands.value = data
    await nextTick()
    if (cmdListRef.value) cmdListRef.value.scrollTop = 0
  } catch {
    commands.value = []
  } finally {
    isLoadingCommands.value = false
  }
}

const fetchLogs = async () => {
  isLoadingLogs.value = true
  try {
    const data = await apiGet<SystemLogEntry[]>('/console/logs')
    logs.value = data
    await nextTick()
    if (logListRef.value) logListRef.value.scrollTop = 0
  } catch {
    logs.value = []
  } finally {
    isLoadingLogs.value = false
  }
}

const uploadLogs = async () => {
  if (filteredLogs.value.length === 0) return
  isUploading.value = true
  uploadResult.value = null
  try {
    const resp = await apiPost<LogUploadResponse>('/console/logs/upload', {
      logs: filteredLogs.value,
      uploaded_by: 'frontend',
      session_id: `session_${Date.now()}`,
    })
    uploadResult.value = `上传成功 (ID: ${resp.upload_id}, 共 ${resp.received_count} 条)`
  } catch (e: any) {
    uploadResult.value = `上传失败: ${e.message}`
  } finally {
    isUploading.value = false
    setTimeout(() => { uploadResult.value = null }, 4000)
  }
}

const copyLogs = () => {
  const entries = activeTab.value === 'console'
    ? filteredCommands.value.map(c =>
        `[${c.started_at}] [${c.status.toUpperCase()}] [${c.executed_by}] ${c.command} -> ${c.output || c.error || '-'}`
      ).join('\n')
    : filteredLogs.value.map(l =>
        `[${l.timestamp}] [${l.level.toUpperCase()}] [${l.source}] [${l.module || '-'}] ${l.message}`
      ).join('\n')
  navigator.clipboard.writeText(entries)
}

const handleCommand = () => {
  const cmd = commandInput.value.trim()
  if (!cmd) return
  commandInput.value = ''

  if (cmd === 'help') {
    console.info('[LuomiNest Console] Available commands: help, refresh, clear')
  } else if (cmd === 'refresh') {
    if (activeTab.value === 'console') fetchCommands()
    else fetchLogs()
  } else if (cmd === 'clear') {
    if (activeTab.value === 'console') commands.value = []
    else logs.value = []
  }
}

let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchCommands()
  fetchLogs()
  pollTimer = setInterval(() => {
    if (activeTab.value === 'console') fetchCommands()
    else fetchLogs()
  }, 30000)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="console-view">
    <div class="console-header">
      <div class="header-info">
        <h1 class="header-title">控制台</h1>
        <p class="header-desc">AI 命令执行记录、系统日志与运行状态</p>
      </div>
      <div class="header-actions">
        <button class="action-btn ghost" @click="copyLogs" title="复制内容">
          <Copy :size="14" />
        </button>
        <button :class="['action-btn ghost', { active: isExpanded }]" @click="isExpanded = !isExpanded" title="全屏">
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

    <!-- 命令行 Tab -->
    <template v-if="activeTab === 'console'">
      <div class="toolbar">
        <div class="toolbar-left">
          <div class="filter-group">
            <button class="filter-btn" @click="showCmdFilter = !showCmdFilter">
              <Filter :size="13" />
              <span>{{ cmdFilterStatus === 'all' ? '全部状态' : statusLabel(cmdFilterStatus) }}</span>
              <ChevronDown :size="12" />
            </button>
            <div v-if="showCmdFilter" class="filter-dropdown">
              <button :class="['filter-option', { active: cmdFilterStatus === 'all' }]" @click="cmdFilterStatus = 'all'; showCmdFilter = false">全部</button>
              <button :class="['filter-option', { active: cmdFilterStatus === 'success' }]" @click="cmdFilterStatus = 'success'; showCmdFilter = false">成功</button>
              <button :class="['filter-option', { active: cmdFilterStatus === 'failed' }]" @click="cmdFilterStatus = 'failed'; showCmdFilter = false">失败</button>
              <button :class="['filter-option', { active: cmdFilterStatus === 'running' }]" @click="cmdFilterStatus = 'running'; showCmdFilter = false">运行中</button>
            </div>
          </div>
          <span class="record-count">{{ filteredCommands.length }} 条记录</span>
        </div>
        <button class="action-btn ghost" @click="fetchCommands" :disabled="isLoadingCommands" title="刷新">
          <RefreshCw :size="14" :class="{ spinning: isLoadingCommands }" />
        </button>
      </div>

      <div class="console-body">
        <div ref="cmdListRef" class="cmd-list">
          <div v-for="cmd in filteredCommands" :key="cmd.id" :class="['cmd-card', cmd.status]">
            <div class="cmd-card-header">
              <div class="cmd-card-left">
                <component :is="cmd.status === 'success' ? CheckCircle2 : cmd.status === 'failed' ? XCircle : Play" :size="14" class="cmd-status-icon" />
                <code class="cmd-text">{{ cmd.command }}</code>
              </div>
              <span :class="['cmd-badge', cmd.status]">{{ statusLabel(cmd.status) }}</span>
            </div>
            <div class="cmd-card-body">
              <p class="cmd-desc">{{ cmd.description }}</p>
              <div class="cmd-meta">
                <span class="meta-item"><User :size="12" />{{ cmd.executed_by }}</span>
                <span class="meta-item"><Clock :size="12" />{{ formatTimestamp(cmd.started_at) }}</span>
                <span class="meta-item"><Clock :size="12" />{{ formatDuration(cmd.duration_ms) }}</span>
                <span v-if="cmd.exit_code !== null" class="meta-item">exit: {{ cmd.exit_code }}</span>
              </div>
              <div v-if="cmd.output" class="cmd-output">
                <span class="output-label">输出:</span>
                <code>{{ cmd.output }}</code>
              </div>
              <div v-if="cmd.error" class="cmd-error">
                <span class="output-label">错误:</span>
                <code>{{ cmd.error }}</code>
              </div>
              <div v-if="cmd.rollback_command" class="cmd-rollback">
                <RotateCcw :size="12" />
                <code>{{ cmd.rollback_command }}</code>
              </div>
            </div>
          </div>
          <div v-if="filteredCommands.length === 0 && !isLoadingCommands" class="log-empty">
            <Terminal :size="24" />
            <span>暂无命令记录</span>
          </div>
        </div>
      </div>
    </template>

    <!-- 系统日志 Tab -->
    <template v-if="activeTab === 'logs'">
      <div class="toolbar">
        <div class="toolbar-left">
          <div class="filter-group">
            <button class="filter-btn" @click="showLogFilter = !showLogFilter">
              <Filter :size="13" />
              <span>{{ logFilterSource === 'all' ? '全部来源' : logFilterSource === 'frontend' ? '前端' : '后端' }}</span>
              <ChevronDown :size="12" />
            </button>
            <div v-if="showLogFilter" class="filter-dropdown">
              <button :class="['filter-option', { active: logFilterSource === 'all' }]" @click="logFilterSource = 'all'; showLogFilter = false">全部来源</button>
              <button :class="['filter-option', { active: logFilterSource === 'frontend' }]" @click="logFilterSource = 'frontend'; showLogFilter = false">
                <Monitor :size="12" /> 前端
              </button>
              <button :class="['filter-option', { active: logFilterSource === 'backend' }]" @click="logFilterSource = 'backend'; showLogFilter = false">
                <Server :size="12" /> 后端
              </button>
            </div>
          </div>
          <div class="filter-group">
            <select v-model="logFilterLevel" class="level-select">
              <option value="all">全部级别</option>
              <option value="info">Info</option>
              <option value="warn">Warn</option>
              <option value="error">Error</option>
              <option value="success">Success</option>
            </select>
          </div>
          <span class="record-count">{{ filteredLogs.length }} 条日志</span>
        </div>
        <div class="toolbar-right">
          <button class="action-btn ghost" @click="fetchLogs" :disabled="isLoadingLogs" title="刷新">
            <RefreshCw :size="14" :class="{ spinning: isLoadingLogs }" />
          </button>
          <button :class="['upload-btn', { uploading: isUploading }]" @click="uploadLogs" :disabled="isUploading || filteredLogs.length === 0" title="上传日志">
            <Upload :size="14" />
            <span>{{ isUploading ? '上传中...' : '上传日志' }}</span>
          </button>
        </div>
      </div>
      <div v-if="uploadResult" :class="['upload-toast', { error: uploadResult.includes('失败') }]">
        {{ uploadResult }}
      </div>

      <div class="console-body">
        <div ref="logListRef" class="log-list">
          <div v-for="log in filteredLogs" :key="log.id" :class="['log-entry', log.level]">
            <span class="log-time">{{ formatTimestamp(log.timestamp) }}</span>
            <component :is="levelIcon(log.level)" :size="13" class="log-level-icon" />
            <span :class="['log-source', log.source]">
              <Monitor v-if="log.source === 'frontend'" :size="11" />
              <Server v-else :size="11" />
              {{ log.source === 'frontend' ? '前端' : '后端' }}
            </span>
            <span v-if="log.module" class="log-module">{{ log.module }}</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
          <div v-if="filteredLogs.length === 0 && !isLoadingLogs" class="log-empty">
            <Terminal :size="24" />
            <span>暂无日志</span>
          </div>
        </div>
      </div>
    </template>

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

.action-btn.ghost:hover:not(:disabled) {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.action-btn.ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-group {
  position: relative;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--surface);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.filter-btn:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.filter-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 10;
  min-width: 140px;
  padding: 4px;
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-md);
}

.filter-option {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 7px 12px;
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.filter-option:hover {
  background: var(--surface-hover);
}

.filter-option.active {
  color: var(--lumi-primary);
  font-weight: 600;
}

.level-select {
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--surface);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.level-select:hover {
  border-color: var(--lumi-primary);
}

.record-count {
  font-size: 12px;
  color: var(--text-muted);
}

.console-body {
  flex: 1;
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  overflow: hidden;
  min-height: 0;
}

.cmd-list {
  height: 100%;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cmd-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  overflow: hidden;
  transition: all var(--transition-fast);
}

.cmd-card:hover {
  border-color: var(--border);
  box-shadow: var(--shadow-xs);
}

.cmd-card.success {
  border-left: 3px solid var(--lumi-success);
}

.cmd-card.failed {
  border-left: 3px solid var(--lumi-accent);
}

.cmd-card.running {
  border-left: 3px solid var(--lumi-warning);
}

.cmd-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--bg-secondary);
}

.cmd-card-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.cmd-status-icon {
  flex-shrink: 0;
}

.cmd-card.success .cmd-status-icon {
  color: var(--lumi-success);
}

.cmd-card.failed .cmd-status-icon {
  color: var(--lumi-accent);
}

.cmd-card.running .cmd-status-icon {
  color: var(--lumi-warning);
}

.cmd-text {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cmd-badge {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.cmd-badge.success {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.cmd-badge.failed {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.cmd-badge.running {
  background: var(--task-yellow-soft);
  color: var(--lumi-warning);
}

.cmd-card-body {
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cmd-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

.cmd-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.cmd-output,
.cmd-error {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 11px;
}

.cmd-output {
  background: var(--task-green-soft);
}

.cmd-output code {
  color: var(--lumi-success);
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

.cmd-error {
  background: var(--lumi-accent-light);
}

.cmd-error code {
  color: var(--lumi-accent);
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

.output-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  flex-shrink: 0;
}

.cmd-rollback {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 4px;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  font-size: 11px;
}

.cmd-rollback code {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
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
  display: flex;
  align-items: center;
  gap: 3px;
  font-weight: 600;
  font-size: 11px;
  flex-shrink: 0;
  padding: 1px 6px;
  border-radius: 4px;
}

.log-source.frontend {
  color: var(--lumi-info);
  background: var(--task-blue-soft);
}

.log-source.backend {
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.log-module {
  font-size: 11px;
  color: var(--text-muted);
  flex-shrink: 0;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.upload-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  color: white;
  background: var(--lumi-primary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.upload-btn:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.upload-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.upload-btn.uploading {
  background: var(--lumi-primary-soft);
}

.upload-toast {
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  background: var(--task-green-soft);
  color: var(--lumi-success);
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.upload-toast.error {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
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

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
