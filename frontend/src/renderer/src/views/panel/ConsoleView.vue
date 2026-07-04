<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import {
  Terminal, Play, Square, Copy, ChevronRight, AlertTriangle, Info,
  CheckCircle2, XCircle, Maximize2, Minimize2, Upload, RotateCcw,
  Clock, User, Filter, RefreshCw, ChevronDown, Server, Monitor,
  Workflow, Wrench
} from 'lucide-vue-next'
import LumiButton from '../../components/common/LumiButton.vue'
import LumiEmptyState from '../../components/common/LumiEmptyState.vue'
import LumiInput from '../../components/common/LumiInput.vue'
import { useApi } from '../../composables/useApi'
import { copyToClipboard } from '../../utils/clipboard'
import { generateId } from '../../utils/id'
import type { CommandRecord, SystemLogEntry, LogUploadResponse, ExecuteCommandResponse } from '../../types'
import { formatTime, formatDuration } from '../../utils/format'

const { apiGet, apiPost, apiDelete } = useApi()

/** 工具调用记录列表项（来自 /workflow/tool-records） */
interface ToolRecordListItem {
  record_id: string
  session_id: string | null
  tool_name: string
  success: boolean
  duration_ms: number
  created_at: string
  result_preview: string
}

/** 工具调用记录详情（来自 /workflow/tool-records/{id}） */
interface ToolRecordDetail extends ToolRecordListItem {
  conversation_id: string | null
  arguments: Record<string, unknown>
  result: string
}

const activeTab = ref<'console' | 'logs' | 'workflow'>('console')
const isExpanded = ref(false)
const commandInput = ref('')

const commands = ref<CommandRecord[]>([])
const logs = ref<SystemLogEntry[]>([])
const toolRecords = ref<ToolRecordListItem[]>([])
const isLoadingCommands = ref(false)
const isLoadingLogs = ref(false)
const isLoadingToolRecords = ref(false)
const isUploading = ref(false)
const uploadResult = ref<string | null>(null)

const logFilterSource = ref<'all' | 'frontend' | 'backend'>('all')
const logFilterLevel = ref<'all' | 'info' | 'warn' | 'error' | 'success'>('all')
const cmdFilterStatus = ref<'all' | 'success' | 'failed' | 'running'>('all')
const toolFilterStatus = ref<'all' | 'success' | 'failed'>('all')

const showCmdFilter = ref(false)
const showLogFilter = ref(false)
const showToolFilter = ref(false)

/** 当前展开查看详情的工具记录 record_id */
const expandedRecordId = ref<string | null>(null)
const expandedRecordDetail = ref<ToolRecordDetail | null>(null)
const isLoadingRecordDetail = ref(false)

const logListRef = ref<HTMLElement | null>(null)
const cmdListRef = ref<HTMLElement | null>(null)
const toolListRef = ref<HTMLElement | null>(null)

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

const filteredToolRecords = computed(() => {
  if (toolFilterStatus.value === 'all') return toolRecords.value
  return toolRecords.value.filter(r => r.success === (toolFilterStatus.value === 'success'))
})

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

const fetchToolRecords = async () => {
  isLoadingToolRecords.value = true
  try {
    const resp = await apiGet<{ records: ToolRecordListItem[]; count: number }>('/workflow/tool-records?limit=100')
    toolRecords.value = resp?.records ?? []
    await nextTick()
    if (toolListRef.value) toolListRef.value.scrollTop = 0
  } catch {
    toolRecords.value = []
  } finally {
    isLoadingToolRecords.value = false
  }
}

/** 展开/折叠工具调用记录详情 */
const toggleRecordDetail = async (recordId: string) => {
  if (expandedRecordId.value === recordId) {
    expandedRecordId.value = null
    expandedRecordDetail.value = null
    return
  }
  expandedRecordId.value = recordId
  expandedRecordDetail.value = null
  isLoadingRecordDetail.value = true
  try {
    const detail = await apiGet<ToolRecordDetail>(`/workflow/tool-records/${recordId}`)
    expandedRecordDetail.value = detail
  } catch {
    expandedRecordDetail.value = null
  } finally {
    isLoadingRecordDetail.value = false
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
      session_id: generateId('session'),
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
  let entries = ''
  if (activeTab.value === 'console') {
    entries = filteredCommands.value.map(c =>
      `[${c.started_at}] [${c.status.toUpperCase()}] [${c.executed_by}] ${c.command} -> ${c.output || c.error || '-'}`
    ).join('\n')
  } else if (activeTab.value === 'logs') {
    entries = filteredLogs.value.map(l =>
      `[${l.timestamp}] [${l.level.toUpperCase()}] [${l.source}] [${l.module || '-'}] ${l.message}`
    ).join('\n')
  } else {
    entries = filteredToolRecords.value.map(r =>
      `[${r.created_at}] [${r.success ? 'SUCCESS' : 'FAILED'}] [${r.tool_name}] (${r.duration_ms}ms) ${r.result_preview}`
    ).join('\n')
  }
  copyToClipboard(entries)
}

const isExecuting = ref(false)
const executeResult = ref<string | null>(null)

const handleCommand = async () => {
  const cmd = commandInput.value.trim()
  if (!cmd || isExecuting.value) return
  commandInput.value = ''

  // 本地命令
  if (cmd === 'help') {
    executeResult.value = '可用命令: help 查看帮助, refresh 刷新, clear 清空, 其他命令将真实执行（受白名单限制）'
    setTimeout(() => { executeResult.value = null }, 4000)
    return
  }
  if (cmd === 'refresh') {
    if (activeTab.value === 'console') fetchCommands()
    else if (activeTab.value === 'logs') fetchLogs()
    else fetchToolRecords()
    return
  }
  if (cmd === 'clear') {
    if (activeTab.value === 'console') {
      await apiDelete('/console/commands').catch(() => {})
      commands.value = []
    } else if (activeTab.value === 'logs') {
      await apiDelete('/console/logs').catch(() => {})
      logs.value = []
    } else {
      toolRecords.value = []
    }
    return
  }

  // 真实执行命令
  isExecuting.value = true
  executeResult.value = null
  try {
    const resp = await apiPost<ExecuteCommandResponse>('/console/execute', {
      command: cmd,
      executed_by: 'user',
    })
    if (resp.status === 'success') {
      executeResult.value = `执行成功 (${resp.duration_ms}ms, exit=${resp.exit_code})`
    } else {
      executeResult.value = `执行失败: ${resp.error || '未知错误'}`
    }
    await fetchCommands()
  } catch (e: any) {
    executeResult.value = `执行失败: ${e.message || e}`
  } finally {
    isExecuting.value = false
    setTimeout(() => { executeResult.value = null }, 5000)
  }
}

let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchCommands()
  fetchLogs()
  fetchToolRecords()
  pollTimer = setInterval(() => {
    if (activeTab.value === 'console') fetchCommands()
    else if (activeTab.value === 'logs') fetchLogs()
    else fetchToolRecords()
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
        <LumiButton
          variant="ghost"
          size="sm"
          icon-only
          :class="['header-action-btn', { 'is-active': false }]"
          aria-label="复制内容"
          @click="copyLogs"
        >
          <template #icon><Copy :size="14" /></template>
        </LumiButton>
        <LumiButton
          variant="ghost"
          size="sm"
          icon-only
          :class="['header-action-btn', { 'is-active': isExpanded }]"
          :aria-label="isExpanded ? '退出全屏' : '全屏'"
          @click="isExpanded = !isExpanded"
        >
          <template #icon>
            <Maximize2 v-if="!isExpanded" :size="14" />
            <Minimize2 v-else :size="14" />
          </template>
        </LumiButton>
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
      <button :class="['tab-btn', { active: activeTab === 'workflow' }]" @click="activeTab = 'workflow'">
        <Workflow :size="14" />
        工作流
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
        <LumiButton
          variant="ghost"
          size="sm"
          icon-only
          :loading="isLoadingCommands"
          aria-label="刷新"
          @click="fetchCommands"
        >
          <template #icon><RefreshCw :size="14" /></template>
        </LumiButton>
      </div>

      <div class="console-body">
        <div ref="cmdListRef" class="cmd-list">
          <div v-for="cmd in filteredCommands" :key="cmd.id" :class="['cmd-card', cmd.status]">
            <div class="cmd-card-header">
              <div class="cmd-card-left">
                <component :is="cmd.status === 'success' ? CheckCircle2 : cmd.status === 'failed' ? XCircle : Play" :size="14" class="cmd-status-icon shrink-0" />
                <code class="cmd-text">{{ cmd.command }}</code>
              </div>
              <span :class="['cmd-badge', cmd.status]">{{ statusLabel(cmd.status) }}</span>
            </div>
            <div class="cmd-card-body">
              <p class="cmd-desc">{{ cmd.description }}</p>
              <div class="cmd-meta">
                <span class="meta-item"><User :size="12" />{{ cmd.executed_by }}</span>
                <span class="meta-item"><Clock :size="12" />{{ formatTime(cmd.started_at, { seconds: true }) }}</span>
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
          <LumiEmptyState
            v-if="filteredCommands.length === 0 && !isLoadingCommands"
            icon="file"
            title="暂无命令记录"
            size="md"
          />
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
          <LumiButton
            variant="ghost"
            size="sm"
            icon-only
            :loading="isLoadingLogs"
            aria-label="刷新"
            @click="fetchLogs"
          >
            <template #icon><RefreshCw :size="14" /></template>
          </LumiButton>
          <LumiButton
            variant="primary"
            size="sm"
            :loading="isUploading"
            :disabled="filteredLogs.length === 0"
            @click="uploadLogs"
          >
            <template #icon><Upload :size="14" /></template>
            <span>{{ isUploading ? '上传中...' : '上传日志' }}</span>
          </LumiButton>
        </div>
      </div>
      <div v-if="uploadResult" :class="['upload-toast', { error: uploadResult.includes('失败') }]">
        {{ uploadResult }}
      </div>

      <div class="console-body">
        <div ref="logListRef" class="log-list">
          <div v-for="log in filteredLogs" :key="log.id" :class="['log-entry', log.level]">
            <span class="log-time">{{ formatTime(log.timestamp, { seconds: true }) }}</span>
            <component :is="levelIcon(log.level)" :size="13" class="log-level-icon shrink-0" />
            <span :class="['log-source', log.source]">
              <Monitor v-if="log.source === 'frontend'" :size="11" />
              <Server v-else :size="11" />
              {{ log.source === 'frontend' ? '前端' : '后端' }}
            </span>
            <span v-if="log.module" class="log-module">{{ log.module }}</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
          <LumiEmptyState
            v-if="filteredLogs.length === 0 && !isLoadingLogs"
            icon="file"
            title="暂无日志"
            size="md"
          />
        </div>
      </div>
    </template>

    <!-- 工作流 Tab（工具调用记录） -->
    <template v-if="activeTab === 'workflow'">
      <div class="toolbar">
        <div class="toolbar-left">
          <div class="filter-group">
            <button class="filter-btn" @click="showToolFilter = !showToolFilter">
              <Filter :size="13" />
              <span>{{ toolFilterStatus === 'all' ? '全部状态' : toolFilterStatus === 'success' ? '成功' : '失败' }}</span>
              <ChevronDown :size="12" />
            </button>
            <div v-if="showToolFilter" class="filter-dropdown">
              <button :class="['filter-option', { active: toolFilterStatus === 'all' }]" @click="toolFilterStatus = 'all'; showToolFilter = false">全部</button>
              <button :class="['filter-option', { active: toolFilterStatus === 'success' }]" @click="toolFilterStatus = 'success'; showToolFilter = false">成功</button>
              <button :class="['filter-option', { active: toolFilterStatus === 'failed' }]" @click="toolFilterStatus = 'failed'; showToolFilter = false">失败</button>
            </div>
          </div>
          <span class="record-count">{{ filteredToolRecords.length }} 条记录</span>
        </div>
        <LumiButton
          variant="ghost"
          size="sm"
          icon-only
          :loading="isLoadingToolRecords"
          aria-label="刷新"
          @click="fetchToolRecords"
        >
          <template #icon><RefreshCw :size="14" /></template>
        </LumiButton>
      </div>

      <div class="console-body">
        <div ref="toolListRef" class="cmd-list">
          <div
            v-for="record in filteredToolRecords"
            :key="record.record_id"
            :class="['cmd-card', record.success ? 'success' : 'failed']"
          >
            <div class="cmd-card-header tool-record-header" @click="toggleRecordDetail(record.record_id)">
              <div class="cmd-card-left">
                <component
                  :is="record.success ? CheckCircle2 : XCircle"
                  :size="14"
                  class="cmd-status-icon shrink-0"
                />
                <Wrench :size="12" class="tool-icon shrink-0" />
                <code class="cmd-text">{{ record.tool_name }}</code>
              </div>
              <div class="tool-record-meta">
                <span class="meta-item"><Clock :size="12" />{{ formatDuration(record.duration_ms) }}</span>
                <span class="meta-item"><Clock :size="12" />{{ formatTime(record.created_at, { seconds: true }) }}</span>
                <span :class="['cmd-badge', record.success ? 'success' : 'failed']">
                  {{ record.success ? '成功' : '失败' }}
                </span>
              </div>
            </div>

            <div v-if="record.result_preview" class="cmd-card-body">
              <div class="cmd-output">
                <span class="output-label">预览:</span>
                <code>{{ record.result_preview }}</code>
              </div>
            </div>

            <!-- 展开详情 -->
            <div v-if="expandedRecordId === record.record_id" class="tool-detail">
              <div v-if="isLoadingRecordDetail" class="detail-loading">加载中...</div>
              <template v-else-if="expandedRecordDetail">
                <div class="detail-section">
                  <span class="output-label">参数:</span>
                  <pre class="detail-json">{{ JSON.stringify(expandedRecordDetail.arguments, null, 2) }}</pre>
                </div>
                <div class="detail-section">
                  <span class="output-label">结果:</span>
                  <pre class="detail-json">{{ expandedRecordDetail.result }}</pre>
                </div>
              </template>
              <div v-else class="detail-loading">加载失败</div>
            </div>
          </div>
          <LumiEmptyState
            v-if="filteredToolRecords.length === 0 && !isLoadingToolRecords"
            icon="file"
            title="暂无工具调用记录"
            size="md"
          />
        </div>
      </div>
    </template>

    <div v-if="activeTab === 'console'" class="command-bar">
      <ChevronRight :size="16" class="prompt-icon" />
      <LumiInput
        v-model="commandInput"
        type="text"
        class="command-input"
        :placeholder="isExecuting ? '执行中...' : '输入命令 (help 查看帮助, 受白名单限制)...'"
        :disabled="isExecuting"
        @enter="handleCommand"
      />
      <LumiButton
        :variant="isExecuting ? 'danger' : 'primary'"
        size="sm"
        icon-only
        :disabled="isExecuting"
        aria-label="执行命令"
        @click="handleCommand"
      >
        <template #icon>
          <Square v-if="isExecuting" :size="14" />
          <Play v-else :size="14" />
        </template>
      </LumiButton>
    </div>
    <Transition name="fade">
      <div v-if="executeResult" :class="['execute-toast', { error: executeResult.includes('失败') }]">
        {{ executeResult }}
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.console-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--space-6) var(--space-7);
  gap: var(--space-3);
  overflow: hidden;
}

.console-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.header-desc {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.header-actions {
  display: flex;
  gap: var(--space-1);
}

:deep(.header-action-btn.is-active) {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

:deep(.header-action-btn.is-active:hover:not(:disabled)) {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand-hover);
}

.tab-bar {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-1);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  width: fit-content;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-5);
  border-radius: var(--radius-sm);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab-btn.active {
  background: var(--surface);
  color: var(--lumi-brand);
  box-shadow: var(--shadow-xs);
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.filter-group {
  position: relative;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  background: var(--surface);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.filter-btn:hover {
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
}

.filter-dropdown {
  position: absolute;
  top: calc(100% + var(--space-1));
  left: 0;
  z-index: var(--z-sticky);
  min-width: 140px;
  padding: var(--space-1);
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-md);
}

.filter-option {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  width: 100%;
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-xs);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.filter-option:hover {
  background: var(--surface-hover);
}

.filter-option.active {
  color: var(--lumi-brand);
  font-weight: var(--font-semibold);
}

.level-select {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  background: var(--surface);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.level-select:hover {
  border-color: var(--lumi-brand);
}

.record-count {
  font-size: var(--text-sm);
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
  padding: var(--space-3) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
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
  padding: var(--space-3) var(--space-4);
  background: var(--bg-secondary);
}

.cmd-card-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  flex: 1;
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
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cmd-badge {
  padding: 2px var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  flex-shrink: 0;
}

.cmd-badge.success {
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.cmd-badge.failed {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.cmd-badge.running {
  background: var(--lumi-warning-light);
  color: var(--lumi-warning);
}

.cmd-card-body {
  padding: var(--space-3) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.cmd-desc {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.cmd-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.cmd-output,
.cmd-error {
  display: flex;
  align-items: flex-start;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
}

.cmd-output {
  background: var(--lumi-success-light);
}

.cmd-output code {
  color: var(--lumi-success);
  font-family: var(--font-mono);
}

.cmd-error {
  background: var(--lumi-accent-light);
}

.cmd-error code {
  color: var(--lumi-accent);
  font-family: var(--font-mono);
}

.output-label {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--text-muted);
  flex-shrink: 0;
}

.cmd-rollback {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-xs);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  font-size: var(--text-xs);
}

.cmd-rollback code {
  font-family: var(--font-mono);
}

.log-list {
  height: 100%;
  overflow-y: auto;
  padding: var(--space-3) var(--space-4);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
}

.log-entry {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) 0;
  border-radius: var(--radius-xs);
}

.log-time {
  color: var(--text-muted);
  font-size: var(--text-xs);
  flex-shrink: 0;
  width: 70px;
}

.log-entry.info .log-level-icon {
  color: var(--lumi-brand);
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
  font-weight: var(--font-semibold);
  font-size: var(--text-xs);
  flex-shrink: 0;
  padding: 1px var(--space-1);
  border-radius: var(--radius-xs);
}

.log-source.frontend {
  color: var(--lumi-info);
  background: var(--lumi-info-light);
}

.log-source.backend {
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

.log-module {
  font-size: var(--text-xs);
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

.upload-toast {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  background: var(--lumi-success-light);
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
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  flex-shrink: 0;
}

.command-bar:focus-within {
  border-color: var(--lumi-brand);
  box-shadow: var(--input-focus-ring);
}

.prompt-icon {
  color: var(--lumi-brand);
  flex-shrink: 0;
}

.command-bar :deep(.lumi-input-root) {
  flex: 1;
  min-width: 0;
}

.command-bar :deep(.lumi-input) {
  background: transparent;
  font-family: var(--font-mono);
  font-size: var(--text-base);
  color: var(--text-primary);
  border-color: transparent;
  box-shadow: none;
}

.command-bar :deep(.lumi-input:focus) {
  border-color: transparent;
  box-shadow: none;
  background: transparent;
}

.command-bar :deep(.lumi-input::placeholder) {
  color: var(--text-muted);
}

.execute-toast {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  background: var(--lumi-success-light);
  color: var(--lumi-success);
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.execute-toast.error {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-fast) var(--ease-in-out);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.spinning {
  animation: spin 1s linear infinite;
}

/* ===== 工作流 Tab ===== */
.tool-record-header {
  cursor: pointer;
  transition: background var(--transition-fast);
}

.tool-record-header:hover {
  background: var(--surface-hover);
}

.tool-icon {
  color: var(--text-muted);
}

.tool-record-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.tool-detail {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border-light);
  background: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.detail-json {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  background: var(--surface);
  border-radius: var(--radius-xs);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-loading {
  font-size: var(--text-sm);
  color: var(--text-muted);
  text-align: center;
  padding: var(--space-2);
}

</style>
