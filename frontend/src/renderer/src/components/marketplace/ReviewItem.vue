<script setup lang="ts">
import { ThumbsUp } from 'lucide-vue-next'
import type { MarketReview } from '../../types/marketplace'
import RatingStars from './RatingStars.vue'

defineProps<{
  review: MarketReview
}>()

const emit = defineEmits<{
  like: [reviewId: string]
}>()

function formatDate(dateStr: string) {
  return dateStr
}
</script>

<template>
  <div class="review-item">
    <div class="review-header">
      <div class="reviewer-avatar">
        {{ review.userName.charAt(0) }}
      </div>
      <div class="reviewer-info">
        <span class="reviewer-name">{{ review.userName }}</span>
        <span class="review-date">{{ formatDate(review.createdAt) }}</span>
      </div>
      <RatingStars :rating="review.rating" :size="12" />
    </div>
    <p class="review-content">{{ review.content }}</p>
    <button class="like-btn" @click="emit('like', review.id)">
      <ThumbsUp :size="13" />
      <span>{{ review.likes }}</span>
    </button>
  </div>
</template>

<style scoped>
.review-item {
  padding: 16px 0;
  border-bottom: 1px solid var(--border-light);
}

.review-item:last-child {
  border-bottom: none;
}

.review-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.reviewer-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--lumi-primary), #14b8a6);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.reviewer-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.reviewer-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.review-date {
  font-size: 11px;
  color: var(--text-muted);
}

.review-content {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 8px;
}

.like-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.like-btn:hover {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}
</style>
