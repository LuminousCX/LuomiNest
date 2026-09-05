<script setup lang="ts">
import { BookOpen, Plus, Search, Filter, ChevronDown, Check, X, Save, Loader2, Archive, Tag, Edit3, Trash2 } from 'lucide-vue-next'
import SearchInput from '../common/SearchInput.vue'
import { CATEGORY_LABELS, CATEGORY_COLORS, FACT_CATEGORIES } from '../../stores/memory'
import type { FactItem, FactCategory } from '../../stores/memory'

interface Props {
  factCount: number
  filteredFactCount: number
  factsByCategory: Record<string, FactItem[]>
  showAddFact: boolean
  newFactContent: string
  newFactCategory: FactCategory
  editingFactId: string | null
  editFactContent: string
  editFactCategory: FactCategory
  searchQuery: string
  filterCategory: string
  saving: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'startAddFact'): void
  (e: 'cancelAddFact'): void
  (e: 'confirmAddFact'): void
  (e: 'startEditFact', fact: FactItem): void
  (e: 'cancelEditFact'): void
  (e: 'saveEditFact'): void
  (e: 'deleteFact', factId: string): void
  (e: 'update:searchQuery', value: string): void
  (e: 'update:filterCategory', value: string): void
  (e: 'update:newFactContent', value: string): void
  (e: 'update:newFactCategory', value: FactCategory): void
  (e: 'update:editFactContent', value: string): void
  (e: 'update:editFactCategory', value: FactCategory): void
}>()

function formatExpiresAt(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  } catch {
    return iso
  }
}
</script>

<template>
  <div class="detail-header">
    <BookOpen :size="22" :style="{ color: 'var(--lumi-success)' }" />
    <h3>记忆事实</h3>
    <div class="detail-actions">
      <button class="h-btn primary" @click="emit('startAddFact')">
        <Plus :size="14" /> 添加事实
      </button>
    </div>
  </div>

  <div class="facts-search-bar">
    <div class="search-input-wrap">
      <SearchInput
        :model-value="searchQuery"
        placeholder="搜索事实..."
        @update:model-value="(v) => emit('update:searchQuery', String(v ?? ''))"
      />
    </div>
    <div class="filter-dropdown">
      <button class="filter-btn" @click="emit('update:filterCategory', filterCategory === 'all' ? '' : 'all')">
        <Filter :size="14" />
        <span>{{ filterCategory === 'all' ? '全部分类' : CATEGORY_LABELS[filterCategory] || '筛选' }}</span>
        <ChevronDown :size="14" />
      </button>
      <div v-if="filterCategory !== 'all'" class="filter-options">
        <button
          v-for="cat in FACT_CATEGORIES"
          :key="cat"
          class="filter-option"
          :class="{ active: filterCategory === cat }"
          @click="emit('update:filterCategory', filterCategory === cat ? 'all' : cat)"
        >
          <Check v-if="filterCategory === cat" :size="12" />
          {{ CATEGORY_LABELS[cat] }}
        </button>
      </div>
    </div>
  </div>

  <div v-if="showAddFact" class="add-fact-form">
    <div class="add-fact-row">
      <input
        :value="newFactContent"
        @input="emit('update:newFactContent', ($event.target as HTMLInputElement).value)"
        type="text"
        placeholder="输入事实内容..."
        class="add-fact-input"
      />
      <select :value="newFactCategory" @change="emit('update:newFactCategory', ($event.target as HTMLSelectElement).value as FactCategory)" class="add-fact-select">
        <option v-for="cat in FACT_CATEGORIES" :key="cat" :value="cat">{{ CATEGORY_LABELS[cat] }}</option>
      </select>
      <button class="h-btn primary" @click="emit('confirmAddFact')" :disabled="!newFactContent.trim() || saving">
        <Loader2 v-if="saving" :size="14" class="spin-animation" />
        <Save v-else :size="14" />
      </button>
      <button class="h-btn" @click="emit('cancelAddFact')"><X :size="14" /></button>
    </div>
  </div>

  <div v-if="factCount === 0 && !showAddFact" class="empty-section">
    <Archive :size="28" />
    <p>暂无记忆事实</p>
    <p class="empty-hint">对话中AI会自动提取并存储用户信息</p>
  </div>

  <div v-else-if="filteredFactCount === 0" class="empty-section">
    <Search :size="28" />
    <p>没有找到匹配的事实</p>
    <p class="empty-hint">尝试调整搜索关键词或筛选条件</p>
  </div>

  <div v-else class="facts-grid">
    <div v-for="(items, cat) in factsByCategory" :key="cat">
      <div v-if="items.length > 0" class="fact-category-group">
        <div class="fact-category-header" :style="{ '--cat-color': CATEGORY_COLORS[cat] || 'var(--task-sky)' }">
          <div class="cat-dot"></div>
          <Tag :size="13" :style="{ color: CATEGORY_COLORS[cat] || 'var(--task-sky)' }" />
          <span class="cat-label">{{ CATEGORY_LABELS[cat] || cat }}</span>
          <span class="cat-count">{{ items.length }}</span>
        </div>
        <div class="fact-items">
          <div
            v-for="fact in items"
            :key="fact.id"
            class="fact-item"
            :style="{ '--fact-color': CATEGORY_COLORS[fact.category] || 'var(--task-sky)' }"
          >
            <template v-if="editingFactId === fact.id">
              <div class="fact-edit-row">
                <input
                  :value="editFactContent"
                  @input="emit('update:editFactContent', ($event.target as HTMLInputElement).value)"
                  type="text"
                  class="add-fact-input"
                />
                <select :value="editFactCategory" @change="emit('update:editFactCategory', ($event.target as HTMLSelectElement).value as FactCategory)" class="add-fact-select">
                  <option v-for="c in FACT_CATEGORIES" :key="c" :value="c">{{ CATEGORY_LABELS[c] }}</option>
                </select>
                <button class="h-btn primary" @click="emit('saveEditFact')" :disabled="saving">
                  <Save :size="13" />
                </button>
                <button class="h-btn" @click="emit('cancelEditFact')"><X :size="13" /></button>
              </div>
            </template>
            <template v-else>
              <div class="fact-main">
                <span class="fact-text" :class="{ 'fact-deprecated': !fact.is_latest }">{{ fact.content }}</span>
                <span v-if="!fact.is_latest" class="fact-badge deprecated">已替代</span>
                <span v-if="fact.expires_at" class="fact-badge expires">过期: {{ formatExpiresAt(fact.expires_at) }}</span>
                <span v-if="fact.source_error" class="fact-error">避免: {{ fact.source_error }}</span>
              </div>
              <div class="fact-actions">
                <button class="fact-btn" @click="emit('startEditFact', fact)"><Edit3 :size="12" /></button>
                <button class="fact-btn danger" @click="emit('deleteFact', fact.id)"><Trash2 :size="12" /></button>
              </div>
            </template>
          </div>
        </div>
      </div>
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

.detail-actions {
  margin-left: auto;
  display: flex;
  gap: var(--space-2);
}

.h-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: var(--radius-xs);
  font-size: var(--text-base);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-slow);
  white-space: nowrap;
}

.h-btn:hover { background: var(--surface-hover); color: var(--text); }

.h-btn.primary {
  color: var(--text);
  background: var(--task-sky-soft);
  border: 1px solid var(--task-sky-border);
}

.h-btn.primary:hover { background: var(--task-sky-soft); }
.h-btn:disabled { opacity: 0.5; cursor: default; }


.empty-hint { font-size: var(--text-sm) !important; opacity: 0.7; }

.facts-search-bar {
  display: flex;
  gap: var(--space-3);
  align-items: center;
}

.search-input-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  background: var(--surface);
}

.facts-search-input {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text);
  font-size: var(--text-base);
  outline: none;
}

.filter-dropdown {
  position: relative;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  background: var(--surface);
  color: var(--text);
  font-size: var(--text-base);
  cursor: pointer;
}

.filter-options {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  padding: var(--space-1);
  min-width: 120px;
}

.filter-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-base);
  color: var(--text);
  cursor: pointer;
  border-radius: var(--radius-xs);
}

.filter-option:hover {
  background: var(--surface-hover);
}

.filter-option.active {
  background: var(--task-sky-soft);
}

.add-fact-form {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--task-sky-border);
}

.add-fact-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.add-fact-input {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  background: var(--bg);
  color: var(--text);
  font-size: var(--text-base);
  outline: none;
}

.add-fact-input:focus { border-color: var(--task-sky); }

.add-fact-select {
  padding: var(--space-2) 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  background: var(--bg);
  color: var(--text);
  font-size: var(--text-sm);
  outline: none;
  min-width: 80px;
}

.facts-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.fact-category-group {
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border);
  overflow: hidden;
}

.fact-category-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 10px 14px;
  background: color-mix(in srgb, var(--cat-color) 6%, transparent);
  border-bottom: 1px solid var(--border);
}

.cat-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--cat-color);
  flex-shrink: 0;
}

.cat-label {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text);
}

.cat-count {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-left: auto;
  padding: 1px var(--space-2);
  border-radius: var(--radius-xs);
  background: var(--bg);
}

.fact-items {
  padding: 6px;
}

.fact-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: var(--radius-xs);
  transition: all 200ms;
}

.fact-item:hover {
  background: color-mix(in srgb, var(--fact-color) 4%, transparent);
}

.fact-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.fact-text {
  font-size: var(--text-base);
  color: var(--text);
  line-height: 1.5;
}

.fact-error {
  font-size: var(--text-xs);
  color: var(--lumi-warning);
  opacity: 0.8;
}

.fact-deprecated {
  text-decoration: line-through;
  opacity: 0.5;
}

.fact-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: var(--radius-xs);
  font-size: var(--text-2xs);
  font-weight: 500;
}

.fact-badge.deprecated {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.fact-badge.expires {
  background: var(--lumi-warning-light);
  color: var(--lumi-warning);
}

.fact-actions {
  display: flex;
  gap: var(--space-1);
}

.fact-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-xs);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms;
}

.fact-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.fact-btn.danger:hover {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.fact-edit-row {
  display: flex;
  gap: 6px;
  align-items: center;
  flex: 1;
}

@media (max-width: 768px) {
  .facts-search-bar {
    flex-direction: column;
  }

  .search-input-wrap {
    width: 100%;
  }

  .filter-dropdown {
    align-self: flex-start;
  }

  .add-fact-row {
    flex-wrap: wrap;
  }

  .add-fact-input {
    width: 100%;
  }

  .add-fact-select {
    flex: 1;
  }

  .fact-item {
    flex-wrap: wrap;
  }

  .fact-actions {
    margin-top: var(--space-2);
  }
}
</style>
