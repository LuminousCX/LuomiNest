<script setup lang="ts">
import { Calendar, FileText, Archive, Plus, Loader2 } from 'lucide-vue-next'

interface Props {
  conversationDailies: { id: string; title: string }[]
  dailies: string[]
  selectedDailyDate: string
  selectedConversationId: string | null
  dailyLines: string[]
  newDailyContent: string
  isAddingDaily: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'selectDaily', date: string): void
  (e: 'switchConversation', convId: string | null): void
  (e: 'handleAddDaily'): void
  (e: 'update:newDailyContent', value: string): void
  (e: 'update:selectedConversationId', value: string | null): void
}>()

function getDailyCount(_date: string): number {
  return 0
}

function getWeekday(dateStr: string): string {
  const date = new Date(dateStr)
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return weekdays[date.getDay()]
}
</script>

<template>
  <div class="detail-header">
    <Calendar :size="22" :style="{ color: 'var(--lumi-amber)' }" />
    <h3>对话历史</h3>
  </div>

  <div v-if="conversationDailies.length > 0" class="conversation-filter">
    <label class="filter-label">按对话筛选</label>
    <select
      :value="selectedConversationId"
      class="conversation-select"
      @change="emit('switchConversation', ($event.target as HTMLSelectElement).value || null); emit('update:selectedConversationId', ($event.target as HTMLSelectElement).value || null)"
    >
      <option :value="null">全部对话</option>
      <option v-for="conv in conversationDailies" :key="conv.id" :value="conv.id">
        {{ conv.title || (conv.id.length > 12 ? conv.id.slice(0, 8) + '...' : conv.id) }}
      </option>
    </select>
  </div>

  <div class="daily-layout">
    <div class="daily-sidebar">
      <div class="section-title">日期列表</div>
      <div v-if="dailies.length === 0" class="empty-section small">
        <Archive :size="20" />
        <p>暂无记录</p>
      </div>
      <div v-else class="daily-dates">
        <div
          v-for="date in [...dailies].reverse()"
          :key="date"
          :class="['daily-date-item', { active: selectedDailyDate === date }]"
          @click="emit('selectDaily', date)"
        >
          <FileText :size="13" />
          <span>{{ date }}</span>
          <span class="daily-count">{{ getDailyCount(date) }}</span>
        </div>
      </div>
    </div>

    <div class="daily-main">
      <div v-if="!selectedDailyDate" class="empty-section">
        <Calendar :size="28" />
        <p>选择日期查看记录</p>
      </div>
      <template v-else>
        <div class="daily-header">
          <span class="daily-date-label">{{ selectedDailyDate }}</span>
          <span class="daily-weekday">{{ getWeekday(selectedDailyDate) }}</span>
        </div>
        <div v-if="dailyLines.length === 0" class="empty-section small">
          <Archive :size="20" />
          <p>当天无记录</p>
        </div>
        <div v-else class="memo-items">
          <div v-for="(line, idx) in dailyLines" :key="idx" class="memo-item">
            <div class="memo-dot" :style="{ background: line.startsWith('-') ? 'var(--lumi-amber)' : 'var(--task-sky)' }"></div>
            <div class="memo-content">
              <p class="memo-text">{{ line.replace(/^-\s*/, '').replace(/^#+\s*/, '') }}</p>
            </div>
          </div>
        </div>
        <div class="add-daily-section">
          <div class="add-daily-row">
            <input
              :value="newDailyContent"
              @input="emit('update:newDailyContent', ($event.target as HTMLInputElement).value)"
              type="text"
              placeholder="添加记录..."
              class="add-daily-input"
              @keydown.enter="emit('handleAddDaily')"
            />
            <button class="h-btn primary" @click="emit('handleAddDaily')" :disabled="isAddingDaily || !newDailyContent.trim()">
              <Loader2 v-if="isAddingDaily" :size="14" class="spin-animation" />
              <Plus v-else :size="14" />
            </button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.detail-header h3 {
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--text);
}

.empty-section.small { padding: var(--space-5); }

.section-title {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  margin-bottom: var(--space-3);
  color: var(--text);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.daily-layout {
  display: flex;
  gap: var(--space-4);
  flex: 1;
  min-height: 0;
}

.conversation-filter {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  padding: 0 var(--space-1);
}

.filter-label {
  font-size: var(--text-sm);
  color: var(--text-muted);
  white-space: nowrap;
}

.conversation-select {
  flex: 1;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-xs);
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: var(--input-border);
  font-size: var(--text-sm);
  outline: none;
  cursor: pointer;
}

.conversation-select:focus {
  border-color: var(--lumi-primary);
}

.daily-sidebar {
  width: 180px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.daily-dates {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-height: 400px;
  overflow-y: auto;
}

.daily-date-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-xs);
  font-size: var(--text-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms;
}

.daily-date-item:hover { background: var(--surface-hover); color: var(--text); }
.daily-date-item.active { background: var(--lumi-sky-soft); color: var(--lumi-sky); font-weight: 600; }

.daily-count {
  font-size: var(--text-2xs);
  padding: 1px 5px;
  border-radius: var(--radius-xs);
  background: var(--border);
  margin-left: auto;
}

.daily-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.daily-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.daily-date-label {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text);
}

.daily-weekday {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.memo-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.memo-item {
  display: flex;
  gap: var(--space-3);
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid transparent;
  transition: all var(--transition-slow);
}

.memo-item:hover { border-color: var(--border); }

.memo-dot {
  width: var(--space-1);
  height: var(--space-1);
  border-radius: var(--radius-full);
  margin-top: 7px;
  flex-shrink: 0;
}

.memo-content { flex: 1; min-width: 0; }

.memo-text {
  font-size: var(--text-base);
  color: var(--text);
  line-height: 1.5;
}

.add-daily-section {
  margin-top: var(--space-3);
}

.add-daily-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.add-daily-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font-size: var(--text-base);
  outline: none;
}

.add-daily-input:focus { border-color: var(--lumi-amber); }

@media (max-width: 768px) {
  .daily-layout {
    flex-direction: column;
  }

  .daily-sidebar {
    width: 100%;
  }

  .daily-dates {
    flex-direction: row;
    flex-wrap: wrap;
    max-height: none;
    gap: 6px;
  }

  .daily-date-item {
    width: calc(33.33% - 4px);
    min-width: 100px;
    justify-content: center;
  }
}
</style>
