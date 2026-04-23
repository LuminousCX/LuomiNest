<script setup lang="ts">
import { ref } from 'vue'
import { Search, X } from 'lucide-vue-next'

const props = defineProps<{
  modelValue: string
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const isFocused = ref(false)

function handleInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLInputElement).value)
}

function clearSearch() {
  emit('update:modelValue', '')
}
</script>

<template>
  <div :class="['search-bar', { focused: isFocused }]">
    <Search :size="16" class="search-icon" />
    <input
      :value="modelValue"
      type="text"
      class="search-input"
      :placeholder="placeholder || '搜索插件或 Skill...'"
      @input="handleInput"
      @focus="isFocused = true"
      @blur="isFocused = false"
    />
    <button v-if="modelValue" class="clear-btn" @click="clearSearch" aria-label="清除搜索">
      <X :size="14" />
    </button>
  </div>
</template>

<style scoped>
.search-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px;
  background: var(--bg-secondary);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.search-bar.focused {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
  background: var(--surface);
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  background: transparent;
  font-size: 13px;
  color: var(--text-primary);
  min-width: 0;
}

.search-input::placeholder {
  color: var(--text-muted);
}

.clear-btn {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.clear-btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}
</style>
