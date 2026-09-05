<script setup lang="ts">
import { ref, watch } from 'vue'
import { Search, Clock, X, TrendingUp, ArrowRight } from 'lucide-vue-next'
import { useMarketplaceStore } from '../../stores/marketplace'
import { debounce } from '../../utils/debounce'
import SearchInput from '../common/SearchInput.vue'

const store = useMarketplaceStore()

const localQuery = ref(store.searchQuery)

watch(() => store.searchQuery, (val) => {
  localQuery.value = val
})

const updateQuery = debounce((query: string) => {
  store.searchQuery = query
}, 200)

const onInput = () => {
  store.showSearchSuggestions = true
  const query = localQuery.value
  if (!query) {
    store.clearSearch()
    return
  }
  updateQuery(query)
}

const onFocus = () => {
  store.showSearchSuggestions = true
}

const onBlur = () => {
  setTimeout(() => {
    store.showSearchSuggestions = false
  }, 200)
}

const selectSuggestion = (text: string) => {
  localQuery.value = text
  store.performSearch(text)
}

const handleSubmit = () => {
  store.performSearch(localQuery.value)
}

const removeHistory = (text: string, e: Event) => {
  e.stopPropagation()
  store.removeSearchHistoryEntry(text)
}
</script>

<template>
  <div class="market-search">
    <div class="search-input-wrap">
      <SearchInput
        v-model="localQuery"
        size="md"
        placeholder="搜索插件或技能..."
        :loading="false"
        @update:model-value="onInput"
        @focus="onFocus"
        @blur="onBlur"
        @enter="handleSubmit"
      >
        <template #icon>
          <Search :size="16" />
        </template>
      </LumiInput>
    </div>

    <Transition name="suggestions">
      <div v-if="store.showSearchSuggestions && store.searchSuggestions.length > 0" class="suggestions-dropdown">
        <div
          v-for="suggestion in store.searchSuggestions"
          :key="suggestion.type + '|' + suggestion.text"
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
  position: relative;
  width: 100%;
}

.suggestions-dropdown {
  position: absolute;
  top: calc(100% + var(--space-2));
  left: 0;
  right: 0;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  z-index: var(--z-dropdown);
  overflow: hidden;
  backdrop-filter: var(--glass-blur);
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.suggestion-item:hover {
  background: var(--surface-hover);
}

.suggestion-icon {
  width: calc(var(--space-6) + var(--space-1));
  height: calc(var(--space-6) + var(--space-1));
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
  font-size: var(--text-base);
  color: var(--text-primary);
}

.suggestion-type {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  padding: calc(var(--space-1) / 2) var(--space-1);
  border-radius: var(--radius-full);
  background: var(--workspace-panel);
}

.remove-history-btn {
  width: var(--space-5);
  height: var(--space-5);
  border-radius: var(--radius-xs);
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
  padding: var(--space-2) var(--space-4);
  border-top: 1px solid var(--border-light);
}

.clear-history-btn {
  font-size: var(--text-xs);
  color: var(--text-muted);
  transition: color var(--transition-fast);
}

.clear-history-btn:hover {
  color: var(--lumi-accent);
}

.suggestions-enter-active {
  animation: lumi-fade-in var(--duration-normal) var(--ease-out-expo);
}

.suggestions-leave-active {
  animation: lumi-fade-in var(--duration-fast) var(--ease-out-expo) reverse;
}

</style>
