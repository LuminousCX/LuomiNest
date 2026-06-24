<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next'

defineProps<{
  questions: string[]
}>()

const emit = defineEmits<{
  select: [question: string]
}>()
</script>

<template>
  <div class="suggested-questions">
    <div class="suggestions-list">
      <button
        v-for="(question, index) in questions"
        :key="index"
        class="suggestion-btn"
        @click="emit('select', question)"
      >
        <Sparkles :size="12" class="suggestion-icon" />
        <span>{{ question }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.suggested-questions {
  margin-top: var(--space-2);
}

.suggestions-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.suggestion-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--text-sm);
  line-height: 1.4;
  color: var(--text-secondary);
  background: var(--surface);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--transition-fast);
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.suggestion-btn:hover {
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  border-color: var(--lumi-brand);
  transform: translateY(-1px);
  box-shadow: var(--shadow-xs);
}

.suggestion-icon {
  flex-shrink: 0;
  opacity: 0.5;
}

.suggestion-btn:hover .suggestion-icon {
  opacity: 1;
}
</style>
