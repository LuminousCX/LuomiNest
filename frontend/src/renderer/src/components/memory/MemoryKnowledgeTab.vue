<script setup lang="ts">
import { FileText, Edit3, X, Save, Loader2, BookOpen } from 'lucide-vue-next'
import type { KnowledgeSection } from '../../stores/memory'

interface Props {
  isEditingKnowledge: boolean
  editKnowledgeContent: string
  isSaving: boolean
  knowledgeHasChanges: boolean
  knowledgeSectionCards: KnowledgeSection[]
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'startEditKnowledge'): void
  (e: 'cancelEditKnowledge'): void
  (e: 'saveEditKnowledge'): void
  (e: 'update:editKnowledgeContent', value: string): void
}>()
</script>

<template>
  <div class="detail-header">
    <FileText :size="22" :style="{ color: 'var(--lumi-sky)' }" />
    <h3>知识记忆</h3>
    <div class="detail-actions">
      <button v-if="!isEditingKnowledge" class="h-btn primary" @click="emit('startEditKnowledge')">
        <Edit3 :size="14" /> 编辑
      </button>
      <template v-else>
        <button class="h-btn" @click="emit('cancelEditKnowledge')"><X :size="14" /> 取消</button>
        <button class="h-btn primary" @click="emit('saveEditKnowledge')" :disabled="isSaving || !knowledgeHasChanges">
          <Loader2 v-if="isSaving" :size="14" class="spin-animation" />
          <Save v-else :size="14" /> 保存
        </button>
      </template>
    </div>
  </div>

  <div v-if="isEditingKnowledge" class="editor-section">
    <textarea
      :value="editKnowledgeContent"
      @input="emit('update:editKnowledgeContent', ($event.target as HTMLTextAreaElement).value)"
      class="memory-editor"
      placeholder="编辑知识记忆..."
    ></textarea>
    <div class="editor-hint">使用 ## 标题创建知识章节，- 开头添加知识点</div>
  </div>
  <div v-else class="markdown-preview">
    <div v-if="knowledgeSectionCards.length === 0" class="empty-section">
      <BookOpen :size="28" />
      <p>暂无知识记忆</p>
      <p class="empty-hint">对话中AI会自动提取并存储知识信息</p>
    </div>
    <template v-else>
      <div v-for="(section, idx) in knowledgeSectionCards" :key="idx" class="memory-section-card" :style="{ '--ms-color': 'var(--lumi-sky)' }">
        <div class="ms-header">
          <div class="ms-dot"></div>
          <span class="ms-label">{{ section.title }}</span>
          <span class="ms-count">{{ section.content.split('\n').filter((l: string) => l.trim()).length }} 条</span>
        </div>
        <div class="ms-body">
          <p v-for="(line, lidx) in section.content.split('\n').filter((l: string) => l.trim())" :key="lidx" class="ms-line">{{ line.replace(/^-\s*/, '') }}</p>
        </div>
      </div>
    </template>
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

.detail-actions {
  margin-left: auto;
  display: flex;
  gap: var(--space-2);
}

.editor-section { flex: 1; min-height: 300px; }

.memory-editor {
  width: 100%;
  min-height: 300px;
  padding: var(--space-4);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--text);
  font-size: var(--text-base);
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  line-height: 1.6;
  resize: vertical;
  outline: none;
}

.memory-editor:focus { border-color: var(--task-purple); }

.editor-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: var(--space-2);
  text-align: right;
}

.markdown-preview { flex: 1; }

.memory-section-card {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border);
  margin-bottom: 10px;
  transition: all var(--transition-slow);
}

.memory-section-card:hover {
  border-color: var(--ms-color);
  box-shadow: 0 2px 12px color-mix(in srgb, var(--ms-color) 8%, transparent);
}

.ms-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 10px;
}

.ms-dot {
  width: var(--space-2);
  height: var(--space-2);
  border-radius: var(--radius-full);
  background: var(--ms-color);
  flex-shrink: 0;
}

.ms-label {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text);
}

.ms-count {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-left: auto;
}

.ms-body {
  padding-left: var(--space-4);
}

.ms-line {
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: 1.6;
  margin-bottom: 3px;
}

.empty-hint { font-size: var(--text-sm) !important; opacity: 0.7; }
</style>
