<script setup lang="ts">
import { ref, watch } from 'vue'
import { Search, Clock, X, TrendingUp, ArrowRight } from 'lucide-vue-next'
import { useMarketplaceStore } from '../../stores/marketplace'

const store = useMarketplaceStore()

const inputRef = ref<HTMLInputElement | null>(null)
const localQuery = ref(store.searchQuery)

watch(() => store.searchQuery, (val) => {
  localQuery.value = val
})

function onInput() {
  store.searchQuery = localQuery.value
  store.showSearchSuggestions = true
}

function onFocus() {
  store.showSearchSuggestions = true
}

function onBlur() {
  setTimeout(() => {
    store.showSearchSuggestions = false
  }, 200)
}

function selectSuggestion(text: string) {
  localQuery.value = text
  store.performSearch(text)
}

function handleSubmit() {
  store.performSearch(localQuery.value)
}

function clearInput() {
  localQuery.value = ''
  store.clearSearch()
  inputRef.value?.focus()
}

function removeHistory(text: string, e: Event) {
  e.stopPropagation()
  store.removeSearchHistoryEntry(text)
}
</script>

<template>
  <div class="market-search">
    <div class="search-input-wrap">
      <Search :size="16" class="search-icon" />
      <input
        ref="inputRef"
        v-model="localQuery"
        type="text"
        class="search-input"
        placeholder="搜索插件或技能..."
        @input="onInput"
        @focus="onFocus"
        @blur="onBlur"
        @keyup.enter="handleSubmit"
      />
      <button v-if="localQuery" class="clear-btn" @click="clearInput">
        <X :size="14" />
      </button>
    </div>

    <Transition name="suggestions">
      <div v-if="store.showSearchSuggestions && store.searchSuggestions.length > 0" class="suggestions-dropdown">
        <div
          v-for="(suggestion, idx) in store.searchSuggestions"
          :key="idx"
          class="suggestion-item"
          @mousedown.prevent="selectSuggestion(suggestion.text)"
        >
          <div class="suggestion-icon">
            <Clock v-if="suggestion.type === 'history'" :size="14" />
            <TrendingUp v-else-if="suggestion.type === 'category'" :size="14" />
            <Search v-else :size="14" />
          </div>
          <span class="suggestion-text">{{ suggestion.text }}</span>
          <span class="suggestion-type">
            {{ suggestion.type === 'history' ? '历史' : suggestion.type === 'category' ? '分类' : '建议' }}
          </span>
          <button
            v-if="suggestion.type === 'history'"
            class="remove-history-btn"
            @mousedown.prevent="removeHistory(suggestion.text, $event)"
          >
            <X :size="12" />
          </button>
          <ArrowRight v-else :size="12" class="suggestion-arrow" />
        </div>

        <div v-if="store.searchHistory.length > 0 && !localQuery" class="suggestions-footer">
          <button class="clear-history-btn" @mousedown.prevent="store.clearSearchHistory()">
            清除搜索历史
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.market-search {
  position: relative;
  width: 100%;
}

.search-input-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  transition: all var(--transition-fast);
}

.search-input-wrap:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  background: transparent;
  font-size: 14px;
  color: var(--text-primary);
  min-width: 0;
}

.search-input::placeholder {
  color: var(--text-muted);
}

.clear-btn {
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.clear-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.suggestions-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  z-index: 50;
  overflow: hidden;
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.suggestion-item:hover {
  background: var(--surface-hover);
}

.suggestion-icon {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: var(--workspace-panel);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  flex-shrink: 0;
}

.suggestion-text {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
}

.suggestion-type {
  font-size: 10px;
  color: var(--text-muted);
  padding: 2px 6px;
  border-radius: var(--radius-full);
  background: var(--workspace-panel);
}

.remove-history-btn {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.remove-history-btn:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.suggestion-arrow {
  color: var(--text-muted);
  flex-shrink: 0;
}

.suggestions-footer {
  padding: 8px 16px;
  border-top: 1px solid var(--border-light);
}

.clear-history-btn {
  font-size: 12px;
  color: var(--text-muted);
  transition: color var(--transition-fast);
}

.clear-history-btn:hover {
  color: var(--lumi-accent);
}

.suggestions-enter-active {
  animation: lumi-fade-in 0.2s ease-out;
}

.suggestions-leave-active {
  animation: lumi-fade-in 0.15s ease-out reverse;
}
</style>
