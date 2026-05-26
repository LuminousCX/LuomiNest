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
  margin-top: 8px;
}

.suggestions-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.suggestion-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: var(--radius-full);
  font-size: 12px;
  line-height: 1.4;
  color: var(--text-secondary);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all 0.2s ease;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.suggestion-btn:hover {
  color: var(--lumi-primary, #147EBC);
  background: var(--lumi-primary-light, rgba(20, 126, 188, 0.08));
  border-color: var(--lumi-primary, #147EBC);
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
