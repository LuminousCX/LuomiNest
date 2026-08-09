<script setup lang="ts">
import { Globe, Edit3, X, Save, Loader2, Sparkles } from 'lucide-vue-next'
import type { MemoryProfile, SummarySections } from '../../stores/memory'

interface Props {
  profile: MemoryProfile
  hasProfile: boolean
  isEditingSummary: boolean
  editSummaryContent: string
  isSaving: boolean
  summaryHasChanges: boolean
  summarySectionNames: readonly string[]
  summarySectionColors: Record<string, string>
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
    <Globe :size="22" :style="{ color: 'var(--task-sky)' }" />
    <h3>用户画像</h3>
    <div class="detail-actions">
      <button v-if="!isEditingSummary" class="h-btn primary" @click="emit('startEditSummary')">
        <Edit3 :size="14" /> 编辑
      </button>
      <template v-else>
        <button class="h-btn" @click="emit('cancelEditSummary')"><X :size="14" /> 取消</button>
        <button class="h-btn primary" @click="emit('saveEditSummary')" :disabled="isSaving || !summaryHasChanges">
          <Loader2 v-if="isSaving" :size="14" class="spin-animation" />
          <Save v-else :size="14" /> 保存
        </button>
      </template>
    </div>
  </div>

  <div v-if="hasProfile" class="profile-card">
    <div class="profile-top">
      <div class="profile-avatar-lg">{{ profile.name?.[0] || '?' }}</div>
      <div class="profile-info">
        <span class="profile-name">{{ profile.name || '未知用户' }}</span>
        <span class="profile-label">AI 记住的你</span>
      </div>
    </div>
    <div v-if="profile.static_facts && profile.static_facts.length > 0" class="profile-section">
      <div class="profile-section-label">稳定偏好</div>
      <div class="profile-tags">
        <span v-for="(fact, idx) in profile.static_facts" :key="idx" class="profile-tag static">{{ fact }}</span>
      </div>
    </div>
    <div v-if="profile.dynamic_context && profile.dynamic_context.length > 0" class="profile-section">
      <div class="profile-section-label">当前状态</div>
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
      placeholder="编辑 AI 总结内容..."
    ></textarea>
    <div class="editor-hint">支持 Markdown 格式，使用 ## 作为段落标题</div>
  </div>
  <template v-else>
    <div
      v-for="sectionName in summarySectionNames"
      :key="sectionName"
      class="distilled-section-card"
      :style="{ '--section-color': summarySectionColors[sectionName] }"
    >
      <div class="distilled-section-header">
        <div class="section-dot" :style="{ background: summarySectionColors[sectionName] }"></div>
        <span class="section-title-text">{{ sectionName }}</span>
      </div>
      <div class="distilled-section-body">
        <template v-if="summarySections[sectionName as keyof SummarySections] && summarySections[sectionName as keyof SummarySections].trim()">
          <p v-for="(line, idx) in summarySections[sectionName as keyof SummarySections].split('\n').filter((l: string) => l.trim())" :key="idx" class="distilled-line">{{ line.replace(/^-\s*/, '') }}</p>
        </template>
        <template v-else>
          <p class="empty-hint">暂无内容</p>
        </template>
      </div>
    </div>
    <div v-if="!hasSummary" class="empty-section summary-empty">
      <Sparkles :size="28" />
      <p>AI 还不了解你</p>
      <p class="empty-hint">与 Agent 对话后，AI 会自动总结你的信息</p>
    </div>
  </template>
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

.profile-card {
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--task-sky-soft), var(--lumi-sky-soft));
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
  background: var(--lumi-accent-glow);
  color: var(--task-sky);
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
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.profile-tag.dynamic {
  background: var(--lumi-info-light);
  color: var(--lumi-info);
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

.memory-editor:focus { border-color: var(--task-sky); }

.editor-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: var(--space-2);
  text-align: right;
}

.distilled-section-card {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border);
  transition: all var(--transition-slow);
}

.distilled-section-card:hover {
  border-color: var(--section-color);
  box-shadow: 0 2px 12px color-mix(in srgb, var(--section-color) 8%, transparent);
}

.distilled-section-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 10px;
}

.section-dot {
  width: var(--space-2);
  height: var(--space-2);
  border-radius: var(--radius-full);
  flex-shrink: 0;
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
