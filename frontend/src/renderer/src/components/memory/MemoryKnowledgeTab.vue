<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { FileText, Edit3, X, Save, Loader2, BookOpen } from 'lucide-vue-next'
import type { KnowledgeSection } from '../../stores/memory'

interface Props {
  isEditingKnowledge: boolean
  editKnowledgeContent: string
  isSaving: boolean
  knowledgeHasChanges: boolean
  knowledgeSectionCards: KnowledgeSection[]
}

const { t } = useI18n()

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
    <FileText :size="22" class="detail-icon" />
    <h3>{{ t('memory.knowledge.title') }}</h3>
    <div class="detail-actions">
      <button v-if="!isEditingKnowledge" class="h-btn primary" @click="emit('startEditKnowledge')">
        <Edit3 :size="14" /> {{ t('memory.knowledge.edit') }}
      </button>
      <template v-else>
        <button class="h-btn" @click="emit('cancelEditKnowledge')"><X :size="14" /> {{ t('memory.knowledge.cancel') }}</button>
        <button class="h-btn primary" @click="emit('saveEditKnowledge')" :disabled="isSaving || !knowledgeHasChanges">
          <Loader2 v-if="isSaving" :size="14" class="spin-animation" />
          <Save v-else :size="14" /> {{ t('memory.knowledge.save') }}
        </button>
      </template>
    </div>
  </div>

  <div v-if="isEditingKnowledge" class="editor-section">
    <textarea
      :value="editKnowledgeContent"
      @input="emit('update:editKnowledgeContent', ($event.target as HTMLTextAreaElement).value)"
      class="memory-editor"
      :placeholder="t('memory.knowledge.editPlaceholder')"
    ></textarea>
    <div class="editor-hint">{{ t('memory.knowledge.editorHint') }}</div>
  </div>
  <div v-else class="markdown-preview">
    <div v-if="knowledgeSectionCards.length === 0" class="empty-section">
      <BookOpen :size="28" />
      <p>{{ t('memory.knowledge.empty') }}</p>
      <p class="empty-hint">{{ t('memory.knowledge.emptyHint') }}</p>
    </div>
    <template v-else>
      <div v-for="(section, idx) in knowledgeSectionCards" :key="idx" class="memory-section-card">
        <div class="ms-header">
          <span class="ms-label">{{ section.title }}</span>
          <span class="ms-count">{{ section.content.split('\n').filter((l: string) => l.trim()).length }} {{ t('memory.knowledge.itemCountSuffix') }}</span>
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

/* 标题裸图标：中性色（无彩色） */
.detail-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

/* editor-section / memory-editor / editor-hint 见 memory-shared.css */

.markdown-preview { flex: 1; }

.memory-section-card {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border);
  margin-bottom: 10px;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.memory-section-card:hover {
  border-color: var(--border);
  box-shadow: var(--shadow-xs);
}

.ms-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 10px;
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
<style scoped src="./memory-shared.css"></style>
