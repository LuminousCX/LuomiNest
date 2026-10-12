<script setup lang="ts">
import { Globe, Edit3, X, Save, Loader2, Sparkles } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import type { MemoryProfile, SummarySections } from '../../stores/memory'

const { t } = useI18n()

interface Props {
  profile: MemoryProfile
  hasProfile: boolean
  isEditingSummary: boolean
  editSummaryContent: string
  isSaving: boolean
  summaryHasChanges: boolean
  summarySectionNames: readonly string[]
  hasSummary: boolean
  summarySections: SummarySections
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'startEditSummary'): void
  (e: 'cancelEditSummary'): void
  (e: 'saveEditSummary'): void
  (e: 'update:editSummaryContent', value: string): void
}>()
</script>

<template>
  <div class="detail-header">
    <Globe :size="22" class="detail-icon" />
    <h3>{{ t('memory.profile.title') }}</h3>
    <div class="detail-actions">
      <button v-if="!isEditingSummary" class="h-btn primary" @click="emit('startEditSummary')">
        <Edit3 :size="14" /> {{ t('memory.profile.edit') }}
      </button>
      <template v-else>
        <button class="h-btn" @click="emit('cancelEditSummary')"><X :size="14" /> {{ t('memory.profile.cancel') }}</button>
        <button class="h-btn primary" @click="emit('saveEditSummary')" :disabled="isSaving || !summaryHasChanges">
          <Loader2 v-if="isSaving" :size="14" class="spin-animation" />
          <Save v-else :size="14" /> {{ t('memory.profile.save') }}
        </button>
      </template>
    </div>
  </div>

  <div v-if="hasProfile" class="profile-card">
    <div class="profile-top">
      <div class="profile-avatar-lg">{{ profile.name?.[0] || '?' }}</div>
      <div class="profile-info">
        <span class="profile-name">{{ profile.name || t('memory.profile.unknownUser') }}</span>
        <span class="profile-label">{{ t('memory.profile.aiYou') }}</span>
      </div>
    </div>
    <div v-if="profile.static_facts && profile.static_facts.length > 0" class="profile-section">
      <div class="profile-section-label">{{ t('memory.profile.staticLabel') }}</div>
      <div class="profile-tags">
        <span v-for="(fact, idx) in profile.static_facts" :key="idx" class="profile-tag static">{{ fact }}</span>
      </div>
    </div>
    <div v-if="profile.dynamic_context && profile.dynamic_context.length > 0" class="profile-section">
      <div class="profile-section-label">{{ t('memory.profile.dynamicLabel') }}</div>
      <div class="profile-tags">
        <span v-for="(ctx, idx) in profile.dynamic_context" :key="idx" class="profile-tag dynamic">{{ ctx }}</span>
      </div>
    </div>
  </div>

  <div v-if="isEditingSummary" class="editor-section">
    <textarea
      :value="editSummaryContent"
      @input="emit('update:editSummaryContent', ($event.target as HTMLTextAreaElement).value)"
      class="memory-editor"
      :placeholder="t('memory.profile.editPlaceholder')"
    ></textarea>
    <div class="editor-hint">{{ t('memory.profile.markdownHint') }}</div>
  </div>
  <template v-else>
    <div
      v-for="sectionName in summarySectionNames"
      :key="sectionName"
      class="distilled-section-card"
    >
      <div class="distilled-section-header">
        <span class="section-title-text">{{ sectionName }}</span>
      </div>
      <div class="distilled-section-body">
        <template v-if="summarySections[sectionName as keyof SummarySections] && summarySections[sectionName as keyof SummarySections].trim()">
          <p v-for="(line, idx) in summarySections[sectionName as keyof SummarySections].split('\n').filter((l: string) => l.trim())" :key="idx" class="distilled-line">{{ line.replace(/^-\s*/, '') }}</p>
        </template>
        <template v-else>
          <p class="empty-hint">{{ t('memory.profile.empty') }}</p>
        </template>
      </div>
    </div>
    <div v-if="!hasSummary" class="empty-section summary-empty">
      <Sparkles :size="28" />
      <p>{{ t('memory.profile.emptyTitle') }}</p>
      <p class="empty-hint">{{ t('memory.profile.emptyHint') }}</p>
    </div>
  </template>
</template>

<style scoped>
.detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 标题裸图标：中性色（无彩色） */
.detail-icon {
  color: var(--text-muted);
  flex-shrink: 0;
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

.profile-card {
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border);
}

.profile-top {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.profile-avatar-lg {
  width: var(--space-8);
  height: var(--space-8);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-2xl);
  font-weight: 700;
  flex-shrink: 0;
}

.profile-info { display: flex; flex-direction: column; }

.profile-name {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text);
}

.profile-label {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.profile-section {
  margin-top: var(--space-3);
}

.profile-section-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-bottom: 6px;
  font-weight: 500;
}

.profile-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.profile-tag {
  padding: 3px 10px;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
}

.profile-tag.static {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.profile-tag.dynamic {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

/* editor-section / memory-editor / editor-hint 见 memory-shared.css */

.distilled-section-card {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.distilled-section-card:hover {
  border-color: var(--border);
  box-shadow: var(--shadow-xs);
}

.distilled-section-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 10px;
}

.section-title-text {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text);
}

.distilled-section-body {
  padding-left: var(--space-4);
}

.distilled-line {
  font-size: var(--text-sm);
  color: var(--text);
  line-height: 1.6;
  margin-bottom: 2px;
}

.empty-hint { font-size: var(--text-sm) !important; opacity: 0.7; }

.empty-section.summary-empty {
  margin-top: var(--space-4);
}
</style>
<style scoped src="./memory-shared.css"></style>
