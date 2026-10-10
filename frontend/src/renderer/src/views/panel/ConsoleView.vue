<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Terminal, Play, Square, Copy, ChevronRight, Info,
  CheckCircle2, XCircle, Maximize2, Minimize2, RotateCcw,
  Clock, User, Filter, RefreshCw, ChevronDown,
  Workflow, Wrench
} from 'lucide-vue-next'
import LumiButton from '../../components/common/LumiButton.vue'
import LumiEmptyState from '../../components/common/LumiEmptyState.vue'
import LumiInput from '../../components/common/LumiInput.vue'
import SegmentTabs from '../../components/common/SegmentTabs.vue'
import type { SegmentTabOption } from '../../components/common/SegmentTabs.vue'
import UnifiedLogPanel from '../../components/panel/UnifiedLogPanel.vue'
import { useApi } from '../../composables/useApi'
import { copyToClipboard } from '../../utils/clipboard'
import type { CommandRecord, ExecuteCommandResponse } from '../../types'
import { formatTime, formatDuration } from '../../utils/format'
import LumiPageHeader from '../../components/common/LumiPageHeader.vue'
import { toErrorMessage } from '@/utils/error'

const { apiGet, apiPost, apiDelete } = useApi()
const { t } = useI18n()

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

type ConsoleTabKey = 'console' | 'logs' | 'workflow'
const activeTab = ref<ConsoleTabKey>('console')

/** 顶层主 tab（SegmentTabs lg 档：命令行 / 日志 / 工作流） */
const tabOptions = computed<SegmentTabOption<ConsoleTabKey>[]>(() => [
  { value: 'console', label: t('console.tabConsole'), icon: Terminal },
  { value: 'logs', label: t('console.tabLogs'), icon: Info },
  { value: 'workflow', label: t('console.tabWorkflow'), icon: Workflow },
])

const isExpanded = ref(false)
const commandInput = ref('')

const commands = ref<CommandRecord[]>([])
const toolRecords = ref<ToolRecordListItem[]>([])
const isLoadingCommands = ref(false)
const isLoadingToolRecords = ref(false)

const cmdFilterStatus = ref<'all' | 'success' | 'failed' | 'running'>('all')
const toolFilterStatus = ref<'all' | 'success' | 'failed'>('all')

const showCmdFilter = ref(false)
const showToolFilter = ref(false)

/** 当前展开查看详情的工具记录 record_id */
const expandedRecordId = ref<string | null>(null)
const expandedRecordDetail = ref<ToolRecordDetail | null>(null)
const isLoadingRecordDetail = ref(false)

/** 日志 Tab：数据与操作委托给 UnifiedLogPanel（主进程 log-hub 四路来源） */
const logPanelRef = ref<InstanceType<typeof UnifiedLogPanel> | null>(null)

const cmdListRef = ref<HTMLElement | null>(null)
const toolListRef = ref<HTMLElement | null>(null)

const filteredCommands = computed(() => {
  if (cmdFilterStatus.value === 'all') return commands.value
  return commands.value.filter(c => c.status === cmdFilterStatus.value)
})

const filteredToolRecords = computed(() => {
  if (toolFilterStatus.value === 'all') return toolRecords.value
  return toolRecords.value.filter(r => r.success === (toolFilterStatus.value === 'success'))
})

const statusLabel = (status: CommandRecord['status']) => {
  const map: Record<CommandRecord['status'], string> = {
    success: t('console.success'),
    failed: t('console.failed'),
    running: t('console.running'),
  }
  return map[status]
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

const copyLogs = () => {
  let entries = ''
  if (activeTab.value === 'console') {
    entries = filteredCommands.value.map(c =>
      `[${c.started_at}] [${c.status.toUpperCase()}] [${c.executed_by}] ${c.command} -> ${c.output || c.error || '-'}`
    ).join('\n')
  } else if (activeTab.value === 'logs') {
    entries = logPanelRef.value?.getCopyText() ?? ''
  } else {
    entries = filteredToolRecords.value.map(r =>
      `[${r.created_at}] [${r.success ? 'SUCCESS' : 'FAILED'}] [${r.tool_name}] (${r.duration_ms}ms) ${r.result_preview}`
    ).join('\n')
  }
  copyToClipboard(entries)
}

const isExecuting = ref(false)
const executeResult = ref<string | null>(null)
const executeResultIsError = ref(false)

const handleCommand = async () => {
  const cmd = commandInput.value.trim()
  if (!cmd || isExecuting.value) return
  commandInput.value = ''

  // 本地命令
  if (cmd === 'help') {
    executeResult.value = t('console.help')
    setTimeout(() => { executeResult.value = null }, 4000)
    return
  }
  if (cmd === 'refresh') {
    if (activeTab.value === 'console') fetchCommands()
    else if (activeTab.value === 'logs') void logPanelRef.value?.reload()
    else fetchToolRecords()
    return
  }
  if (cmd === 'clear') {
    if (activeTab.value === 'console') {
      await apiDelete('/console/commands').catch(() => {})
      commands.value = []
    } else if (activeTab.value === 'logs') {
      await logPanelRef.value?.clearAll()
    } else {
      toolRecords.value = []
    }
    return
  }

  // 真实执行命令
  isExecuting.value = true
  executeResult.value = null
  executeResultIsError.value = false
  try {
    const resp = await apiPost<ExecuteCommandResponse>('/console/execute', {
      command: cmd,
      executed_by: 'user',
    })
    if (resp.status === 'success') {
      executeResult.value = t('console.execSuccess', { ms: resp.duration_ms, code: resp.exit_code })
    } else {
      executeResult.value = t('console.execFailed', { msg: resp.error || t('console.unknownError') })
      executeResultIsError.value = true
    }
    await fetchCommands()
  } catch (e: unknown) {
    executeResult.value = t('console.execFailed', { msg: toErrorMessage(e) })
    executeResultIsError.value = true
  } finally {
    isExecuting.value = false
    setTimeout(() => { executeResult.value = null }, 5000)
  }
}

let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchCommands()
  fetchToolRecords()
  pollTimer = setInterval(() => {
    if (activeTab.value === 'console') fetchCommands()
    else if (activeTab.value === 'workflow') fetchToolRecords()
  }, 30000)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="console-view">
    <LumiPageHeader :title="t('console.title')" :desc="t('console.desc')">
      <template #actions>
        <LumiButton
          variant="ghost"
          size="sm"
          icon-only
          :class="['header-action-btn', { 'is-active': false }]"
          :aria-label="t('console.copy')"
          @click="copyLogs"
        >
          <template #icon><Copy :size="14" /></template>
        </LumiButton>
        <LumiButton
          variant="ghost"
          size="sm"
          icon-only
          :class="['header-action-btn', { 'is-active': isExpanded }]"
          :aria-label="isExpanded ? t('console.exitFullscreen') : t('console.fullscreen')"
          @click="isExpanded = !isExpanded"
        >
          <template #icon>
            <Maximize2 v-if="!isExpanded" :size="14" />
            <Minimize2 v-else :size="14" />
          </template>
        </LumiButton>
      </template>
    </LumiPageHeader>

    <SegmentTabs v-model="activeTab" :options="tabOptions" size="lg" />

    <!-- 命令行 Tab -->
    <template v-if="activeTab === 'console'">
      <div class="toolbar">
        <div class="toolbar-left lumi-row-3">
          <div class="filter-group">
            <button class="filter-btn" @click="showCmdFilter = !showCmdFilter">
              <Filter :size="13" />
              <span>{{ cmdFilterStatus === 'all' ? t('console.allStatus') : statusLabel(cmdFilterStatus) }}</span>
              <ChevronDown :size="12" />
            </button>
            <div v-if="showCmdFilter" class="filter-dropdown">
              <button :class="['filter-option', { active: cmdFilterStatus === 'all' }]" @click="cmdFilterStatus = 'all'; showCmdFilter = false">{{ t('console.all') }}</button>
              <button :class="['filter-option', { active: cmdFilterStatus === 'success' }]" @click="cmdFilterStatus = 'success'; showCmdFilter = false">{{ t('console.success') }}</button>
              <button :class="['filter-option', { active: cmdFilterStatus === 'failed' }]" @click="cmdFilterStatus = 'failed'; showCmdFilter = false">{{ t('console.failed') }}</button>
              <button :class="['filter-option', { active: cmdFilterStatus === 'running' }]" @click="cmdFilterStatus = 'running'; showCmdFilter = false">{{ t('console.running') }}</button>
            </div>
          </div>
          <span class="record-count">{{ t('console.recordCount', { n: filteredCommands.length }) }}</span>
        </div>
        <LumiButton
          variant="ghost"
          size="sm"
          icon-only
          :loading="isLoadingCommands"
          :aria-label="t('console.refresh')"
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
                <code class="cmd-text lumi-clip-sm">{{ cmd.command }}</code>
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
                <span class="output-label">{{ t('console.outputLabel') }}</span>
                <code>{{ cmd.output }}</code>
              </div>
              <div v-if="cmd.error" class="cmd-error">
                <span class="output-label">{{ t('console.errorLabel') }}</span>
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
            :title="t('console.emptyCommands')"
            size="md"
          />
        </div>
      </div>
    </template>

    <!-- 日志 Tab：统一日志面板（前端/主进程/后端/平台 log-hub） -->
    <UnifiedLogPanel v-if="activeTab === 'logs'" ref="logPanelRef" />

    <!-- 工作流 Tab（工具调用记录） -->
    <template v-if="activeTab === 'workflow'">
      <div class="toolbar">
        <div class="toolbar-left lumi-row-3">
          <div class="filter-group">
            <button class="filter-btn" @click="showToolFilter = !showToolFilter">
              <Filter :size="13" />
              <span>{{ toolFilterStatus === 'all' ? t('console.allStatus') : toolFilterStatus === 'success' ? t('console.success') : t('console.failed') }}</span>
              <ChevronDown :size="12" />
            </button>
            <div v-if="showToolFilter" class="filter-dropdown">
              <button :class="['filter-option', { active: toolFilterStatus === 'all' }]" @click="toolFilterStatus = 'all'; showToolFilter = false">{{ t('console.all') }}</button>
              <button :class="['filter-option', { active: toolFilterStatus === 'success' }]" @click="toolFilterStatus = 'success'; showToolFilter = false">{{ t('console.success') }}</button>
              <button :class="['filter-option', { active: toolFilterStatus === 'failed' }]" @click="toolFilterStatus = 'failed'; showToolFilter = false">{{ t('console.failed') }}</button>
            </div>
          </div>
          <span class="record-count">{{ t('console.recordCount', { n: filteredToolRecords.length }) }}</span>
        </div>
        <LumiButton
          variant="ghost"
          size="sm"
          icon-only
          :loading="isLoadingToolRecords"
          :aria-label="t('console.refresh')"
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
                <code class="cmd-text lumi-clip-sm">{{ record.tool_name }}</code>
              </div>
              <div class="tool-record-meta">
                <span class="meta-item"><Clock :size="12" />{{ formatDuration(record.duration_ms) }}</span>
                <span class="meta-item"><Clock :size="12" />{{ formatTime(record.created_at, { seconds: true }) }}</span>
                <span :class="['cmd-badge', record.success ? 'success' : 'failed']">
                  {{ record.success ? t('console.success') : t('console.failed') }}
                </span>
              </div>
            </div>

            <div v-if="record.result_preview" class="cmd-card-body">
              <div class="cmd-output">
                <span class="output-label">{{ t('console.previewLabel') }}</span>
                <code>{{ record.result_preview }}</code>
              </div>
            </div>

            <!-- 展开详情 -->
            <div v-if="expandedRecordId === record.record_id" class="tool-detail">
              <div v-if="isLoadingRecordDetail" class="detail-loading">{{ t('console.loading') }}</div>
              <template v-else-if="expandedRecordDetail">
                <div class="detail-section">
                  <span class="output-label">{{ t('console.argsLabel') }}</span>
                  <pre class="detail-json">{{ JSON.stringify(expandedRecordDetail.arguments, null, 2) }}</pre>
                </div>
                <div class="detail-section">
                  <span class="output-label">{{ t('console.resultLabel') }}</span>
                  <pre class="detail-json">{{ expandedRecordDetail.result }}</pre>
                </div>
              </template>
              <div v-else class="detail-loading">{{ t('console.loadFailed') }}</div>
            </div>
          </div>
          <LumiEmptyState
            v-if="filteredToolRecords.length === 0 && !isLoadingToolRecords"
            icon="file"
            :title="t('console.emptyTools')"
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
        :placeholder="isExecuting ? t('console.executingPlaceholder') : t('console.inputPlaceholder')"
        :disabled="isExecuting"
        @enter="handleCommand"
      />
      <LumiButton
        :variant="isExecuting ? 'danger' : 'primary'"
        size="sm"
        icon-only
        :disabled="isExecuting"
        :aria-label="t('console.execute')"
        @click="handleCommand"
      >
        <template #icon>
          <Square v-if="isExecuting" :size="14" />
          <Play v-else :size="14" />
        </template>
      </LumiButton>
    </div>
    <Transition name="fade">
      <div v-if="executeResult" :class="['execute-toast', { error: executeResultIsError }]">
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

/* header → LumiPageHeader */

:deep(.header-action-btn.is-active) {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

:deep(.header-action-btn.is-active:hover:not(:disabled)) {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand-hover);
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
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
