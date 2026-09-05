<script setup lang="ts">
import { computed, nextTick } from 'vue'
import {
  Plus,
  MessageSquare,
  Clock,
  Trash2,
  Pencil,
  ChevronLeft,
  PanelLeftOpen,
  Loader2,
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import SearchInput from '../common/SearchInput.vue'
import { highlightSnippet } from '../../utils/highlight'
import type { ConversationSearchResult } from '../../types'
import type { TimeGroup } from './types'

const props = defineProps<{
  searchQuery: string
  isSearchMode: boolean
  searchResults: ConversationSearchResult[]
  isSearching: boolean
  timeGroups: TimeGroup[]
  currentConvId: string
  renamingConvId: string | null
  renamingTitle: string
  isHistoryCollapsed: boolean
}>()

const emit = defineEmits<{
  'update:searchQuery': [query: string]
  'update:renamingTitle': [title: string]
  select: [convId: string, searchKeyword?: string]
  'new-conversation': []
  'start-rename': [convId: string, currentTitle: string]
  'confirm-rename': []
  'cancel-rename': []
  'delete-conversation': [convId: string]
  collapse: []
  expand: []
}>()

const searchQueryModel = computed<string>({
  get: () => props.searchQuery,
  set: (value) => emit('update:searchQuery', value),
})

const renamingTitleModel = computed<string>({
  get: () => props.renamingTitle,
  set: (value) => emit('update:renamingTitle', value),
})

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const MODE_LABELS: Record<string, string> = {
  normal: '普通',
  standard: '专业',
}

const modeLabel = (chatMode?: string): string => {
  if (!chatMode || chatMode === 'normal') return ''
  return MODE_LABELS[chatMode] || ''
}

const formatTime = (dateStr: string) => {
  const d = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diffDays = Math.floor((today.getTime() - target.getTime()) / 86400000)
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

  if (diffDays <= 0) return time
  if (diffDays === 1) return `昨天 ${time}`
  if (diffDays <= 7) return `${WEEKDAYS[d.getDay()]} ${time}`
  if (d.getFullYear() === now.getFullYear()) return `${d.getMonth() + 1}月${d.getDate()}日`
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

const snippetHtml = (snippet: string): string =>
  highlightSnippet(snippet, props.searchQuery)

const onStartRename = (convId: string, currentTitle: string) => {
  emit('start-rename', convId, currentTitle)
  nextTick(() => {
    const input = document.querySelector('.workbench-rename-input') as HTMLInputElement
    if (input) {
      input.focus()
      input.select()
    }
  })
}
</script>

<template>
  <div class="workbench-history-wrapper">
    <Transition name="history-slide">
      <div v-if="!isHistoryCollapsed" class="workbench-history">
        <button class="history-collapse-triangle" aria-label="收起历史记录" @click="emit('collapse')">
          <ChevronLeft :size="14" />
        </button>

        <div class="history-search">
          <SearchInput v-model="searchQueryModel" size="sm" placeholder="搜索对话..." :loading="isSearching" />
        </div>

        <LumiButton variant="primary" size="sm" block class="new-conv-btn" @click="emit('new-conversation')">
          <Plus :size="15" />
          <span>新建对话</span>
        </LumiButton>

        <div class="history-list">
          <template v-if="isSearchMode">
            <div v-if="isSearching" class="history-empty">
              <Loader2 :size="20" class="spin-animation" />
              <span>搜索中...</span>
            </div>
            <template v-else>
              <div
                v-for="result in searchResults"
                :key="result.id"
                :class="['history-item', { active: currentConvId === result.id }]"
                @click="emit('select', result.id, searchQuery.trim())"
              >
                <MessageSquare :size="14" class="history-item-icon" />
                <div class="history-item-content">
                  <span class="history-item-title">{{ result.title }}</span>
                  <span class="history-item-snippet" v-html="snippetHtml(result.snippet)"></span>
                </div>
              </div>
              <div v-if="searchResults.length === 0" class="history-empty">
                <MessageSquare :size="24" />
                <span>未找到匹配的会话</span>
              </div>
            </template>
          </template>

          <template v-else>
            <template v-for="group in timeGroups" :key="group.label">
              <div class="time-group">
                <div class="time-group-label">
                  <Clock :size="12" />
                  <span>{{ group.label }}</span>
                </div>
                <div
                  v-for="conv in group.items"
                  :key="conv.id"
                  :class="['history-item', { active: currentConvId === conv.id }]"
                  @click="emit('select', conv.id)"
                >
                  <MessageSquare :size="14" class="history-item-icon" />
                  <div class="history-item-content">
                    <template v-if="renamingConvId === conv.id">
                      <input
                        v-model="renamingTitleModel"
                        class="lumi-input workbench-rename-input"
                        maxlength="200"
                        @keydown.enter="emit('confirm-rename')"
                        @keydown.escape="emit('cancel-rename')"
                        @blur="emit('confirm-rename')"
                        @click.stop
                      />
                    </template>
                    <template v-else>
                      <span class="history-item-title">
                        {{ conv.title }}
                        <span v-if="modeLabel(conv.chat_mode)" :class="['mode-tag', `mode-tag-${conv.chat_mode}`]">{{ modeLabel(conv.chat_mode) }}</span>
                      </span>
                      <span class="history-item-time">{{ formatTime(conv.updated_at) }}</span>
                    </template>
                  </div>
                  <template v-if="renamingConvId !== conv.id">
                    <LumiButton
                      variant="ghost"
                      size="sm"
                      icon-only
                      aria-label="重命名"
                      class="history-item-rename"
                      @click.stop="onStartRename(conv.id, conv.title)"
                    >
                      <template #icon>
                        <Pencil :size="13" />
                      </template>
                    </LumiButton>
                    <LumiButton
                      variant="danger-ghost"
                      size="sm"
                      icon-only
                      aria-label="删除对话"
                      class="history-item-delete"
                      @click.stop="emit('delete-conversation', conv.id)"
                    >
                      <template #icon>
                        <Trash2 :size="13" />
                      </template>
                    </LumiButton>
                  </template>
                </div>
              </div>
            </template>

            <div v-if="timeGroups.length === 0" class="history-empty">
              <MessageSquare :size="24" />
              <span>暂无历史记录</span>
            </div>
          </template>
        </div>
      </div>
    </Transition>

    <LumiButton
      v-if="isHistoryCollapsed"
      variant="ghost"
      size="sm"
      icon-only
      aria-label="展开历史记录"
      class="history-expand-toggle"
      @click="emit('expand')"
    >
      <template #icon>
        <PanelLeftOpen :size="15" />
      </template>
    </LumiButton>
  </div>
</template>

<style scoped>
button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}

.workbench-history-wrapper {
  display: flex;
  align-items: center;
  height: 100%;
  flex-shrink: 0;
}

.workbench-history {
  width: 260px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-light);
  flex-shrink: 0;
  overflow: hidden;
  position: relative;
}

.history-collapse-triangle {
  position: absolute;
  top: 50%;
  right: -1px;
  transform: translateY(-50%);
  width: 16px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-right: none;
  border-radius: var(--radius-sm) 0 0 var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  z-index: 10;
}

.history-collapse-triangle:hover {
  color: var(--text-primary);
  background: var(--surface-hover);
  width: 20px;
}

.history-search {
  padding: 0 var(--space-4) var(--space-2);
}

.new-conv-btn {
  margin: 0 var(--space-4) var(--space-2);
  width: calc(100% - var(--space-4) * 2);
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 var(--space-2) var(--space-2);
}

.time-group {
  margin-bottom: var(--space-2);
}

.time-group-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3) var(--space-1);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  transition: background-color var(--transition-fast), color var(--transition-fast);
  position: relative;
}

.history-item:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.history-item.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.history-item-icon {
  flex-shrink: 0;
  color: inherit;
}

.history-item-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.history-item-title {
  font-size: var(--text-base);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mode-tag {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  line-height: 1;
  padding: 2px 5px;
  margin-left: 4px;
  border-radius: 3px;
  vertical-align: middle;
  white-space: nowrap;
}

.mode-tag-standard {
  color: var(--primary-color, var(--text-link));
  background: var(--primary-bg, rgba(0, 122, 255, 0.1));
}

.history-item-time {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.history-item-snippet {
  font-size: var(--text-xs);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: var(--space-1);
}

.history-item-snippet :deep(mark) {
  background: var(--lumi-primary-glow);
  color: var(--lumi-primary);
  padding: 0 var(--space-1);
  border-radius: var(--radius-xs);
}

.workbench-rename-input {
  width: 100%;
  height: var(--space-6);
  background: var(--surface);
  border: 1px solid var(--lumi-primary);
  border-radius: var(--radius-sm);
  padding: 0 var(--space-1);
  font-size: var(--text-base);
  color: var(--text-primary);
  outline: none;
  box-sizing: border-box;
}

.history-item-rename,
.history-item-delete {
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.history-item:hover .history-item-rename,
.history-item:hover .history-item-delete {
  opacity: 1;
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-10) var(--space-4);
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.history-expand-toggle {
  width: 28px;
  height: 60px;
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  color: var(--text-muted);
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-left: none;
  flex-shrink: 0;
  z-index: 5;
}

.history-expand-toggle:hover {
  color: var(--lumi-primary);
  background: var(--surface-hover);
}

.history-slide-enter-active,
.history-slide-leave-active {
  transition: width var(--transition-normal), opacity var(--transition-normal);
  overflow: hidden;
}

.history-slide-enter-from,
.history-slide-leave-to {
  width: 0;
  opacity: 0;
}
</style>
