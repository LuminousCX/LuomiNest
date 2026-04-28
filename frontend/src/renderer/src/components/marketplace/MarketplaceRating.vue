<script setup lang="ts">
import { computed } from 'vue'
import { Star } from 'lucide-vue-next'

const props = defineProps<{
  modelValue: number
  max?: number
  size?: number
  readonly?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

const maxStars = computed(() => props.max ?? 5)
const starSize = computed(() => props.size ?? 16)

const selectStar = (index: number) => {
  if (props.readonly) return
  emit('update:modelValue', index + 1)
}
</script>

<template>
  <div class="market-rating">
    <button
      v-for="i in maxStars"
      :key="i"
      class="star-btn"
      :class="{ readonly }"
      @click="selectStar(i - 1)"
    >
      <Star
        :size="starSize"
        :class="['star-icon', { filled: i <= modelValue, half: i === Math.ceil(modelValue) && modelValue % 1 !== 0 }]"
      />
    </button>
  </div>
</template>

<style scoped>
.market-rating {
  display: flex;
  gap: 2px;
}

.star-btn {
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform var(--transition-fast);
}

.star-btn:not(.readonly):hover {
  transform: scale(1.2);
}

.star-icon {
  color: var(--border);
  transition: color var(--transition-fast);
}

.star-icon.filled {
  color: var(--lumi-star);
  fill: var(--lumi-star);
}
</style>
