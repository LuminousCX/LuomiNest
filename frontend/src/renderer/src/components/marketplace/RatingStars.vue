<script setup lang="ts">
import { Star } from 'lucide-vue-next'

const props = defineProps<{
  rating: number
  maxRating?: number
  size?: number
  interactive?: boolean
  modelValue?: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

const max = props.maxRating || 5
const size = props.size || 14

function getStarType(index: number) {
  const value = props.interactive ? (props.modelValue ?? 0) : props.rating
  if (index <= Math.floor(value)) return 'full'
  if (index === Math.ceil(value) && value % 1 >= 0.3) return 'half'
  return 'empty'
}

function handleClick(index: number) {
  if (props.interactive) {
    emit('update:modelValue', index)
  }
}
</script>

<template>
  <div class="rating-stars" :class="{ interactive }">
    <button
      v-for="i in max"
      :key="i"
      class="star-btn"
      :class="[getStarType(i), { interactive }]"
      :disabled="!interactive"
      @click="handleClick(i)"
    >
      <Star :size="size" />
    </button>
    <span v-if="!interactive" class="rating-value">{{ rating.toFixed(1) }}</span>
  </div>
</template>

<style scoped>
.rating-stars {
  display: inline-flex;
  align-items: center;
  gap: 1px;
}

.star-btn {
  display: flex;
  align-items: center;
  padding: 0;
  border: none;
  background: none;
  cursor: default;
  transition: transform var(--transition-fast);
}

.star-btn.interactive {
  cursor: pointer;
}

.star-btn.interactive:hover {
  transform: scale(1.2);
}

.star-btn.full {
  color: #f59e0b;
}

.star-btn.half {
  color: #f59e0b;
  opacity: 0.6;
}

.star-btn.empty {
  color: var(--text-muted);
  opacity: 0.3;
}

.rating-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-left: 4px;
}
</style>
