<script setup lang="ts">
import { ref, computed } from 'vue'
import { MessageCircle, Send } from 'lucide-vue-next'
import type { MarketplaceReview } from '../../types/marketplace'
import MarketplaceRating from './MarketplaceRating.vue'
import { useMarketplaceStore } from '../../stores/marketplace'
import { formatDateRelative as formatDate } from '../../utils/format'
import LumiButton from '../../components/common/LumiButton.vue'
import LumiEmptyState from '../../components/common/LumiEmptyState.vue'
import LumiInput from '../../components/common/LumiInput.vue'

const props = defineProps<{
  itemId: string
  reviews: MarketplaceReview[]
}>()

const store = useMarketplaceStore()
const sortBy = ref<'newest' | 'rating'>('newest')
const showReplyInput = ref<string | null>(null)
const replyContent = ref('')
const newReviewRating = ref(5)
const newReviewContent = ref('')
const showReviewForm = ref(false)

const sortedReviews = computed(() => {
  const list = [...props.reviews]
  if (sortBy.value === 'rating') {
    list.sort((a, b) => b.rating - a.rating)
  } else {
    list.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  }
  return list
})

const ratingDistribution = computed(() => {
  const dist = [0, 0, 0, 0, 0]
  for (const r of props.reviews) {
    if (r.rating >= 1 && r.rating <= 5) {
      dist[r.rating - 1]++
    }
  }
  return dist.reverse()
})

const averageRating = computed(() => {
  if (props.reviews.length === 0) return 0
  const total = props.reviews.reduce((sum, r) => sum + r.rating, 0)
  return Math.round((total / props.reviews.length) * 10) / 10
})

function submitReview() {
  if (!newReviewContent.value.trim()) return
  store.addReview(props.itemId, {
    itemId: props.itemId,
    userId: 'current-user',
    userName: '我',
    rating: newReviewRating.value,
    content: newReviewContent.value.trim(),
  })
  newReviewContent.value = ''
  newReviewRating.value = 5
  showReviewForm.value = false
}

function submitReply(reviewId: string) {
  if (!replyContent.value.trim()) return
  store.addReviewReply(props.itemId, reviewId, {
    userId: 'current-user',
    userName: '我',
    content: replyContent.value.trim(),
  })
  replyContent.value = ''
  showReplyInput.value = null
}
</script>

<template>
  <div class="market-reviews">
    <div class="reviews-summary">
      <div class="rating-big">
        <span class="rating-number">{{ averageRating.toFixed(1) }}</span>
        <MarketplaceRating :model-value="averageRating" :readonly="true" :size="14" />
        <span class="rating-count">{{ reviews.length }} 条评价</span>
      </div>
      <div class="rating-bars">
        <div v-for="(count, idx) in ratingDistribution" :key="idx" class="rating-bar-row">
          <span class="bar-label">{{ 5 - idx }}</span>
          <div class="bar-track">
            <div
              class="bar-fill"
              :style="{ width: reviews.length ? (count / reviews.length * 100) + '%' : '0%' }"
            ></div>
          </div>
          <span class="bar-count">{{ count }}</span>
        </div>
      </div>
    </div>

    <div class="reviews-actions">
      <div class="sort-toggle">
        <button
          :class="['sort-btn', { active: sortBy === 'newest' }]"
          @click="sortBy = 'newest'"
        >最新</button>
        <button
          :class="['sort-btn', { active: sortBy === 'rating' }]"
          @click="sortBy = 'rating'"
        >评分</button>
      </div>
      <LumiButton variant="primary" size="sm" @click="showReviewForm = !showReviewForm">
        <MessageCircle :size="14" />
        写评价
      </LumiButton>
    </div>

    <Transition name="review-form">
      <div v-if="showReviewForm" class="review-form">
        <div class="form-rating">
          <span class="form-label">评分</span>
          <MarketplaceRating v-model="newReviewRating" :size="20" />
        </div>
        <textarea
          v-model="newReviewContent"
          class="form-textarea"
          placeholder="分享你的使用体验..."
          rows="3"
        ></textarea>
        <div class="form-actions">
          <LumiButton variant="ghost" size="sm" @click="showReviewForm = false">
            取消
          </LumiButton>
          <LumiButton
            variant="primary"
            size="sm"
            :disabled="!newReviewContent.trim()"
            @click="submitReview"
          >
            <Send :size="13" />
            发布
          </LumiButton>
        </div>
      </div>
    </Transition>

    <div class="reviews-list">
      <div v-for="review in sortedReviews" :key="review.id" class="review-item">
        <div class="review-header">
          <div class="review-user">
            <div class="user-avatar">{{ review.userName.charAt(0) }}</div>
            <div class="user-info">
              <span class="user-name">{{ review.userName }}</span>
              <span class="review-date">{{ formatDate(review.createdAt) }}</span>
            </div>
          </div>
          <MarketplaceRating :model-value="review.rating" :readonly="true" :size="12" />
        </div>
        <p class="review-content">{{ review.content }}</p>
        <div class="review-interactions">
          <button class="reply-btn" @click="showReplyInput = showReplyInput === review.id ? null : review.id">
            回复
          </button>
        </div>

        <div v-if="review.replies?.length" class="replies-list">
          <div v-for="reply in review.replies" :key="reply.id" class="reply-item">
            <div class="reply-user">
              <div class="reply-avatar">{{ reply.userName.charAt(0) }}</div>
              <span class="reply-name">{{ reply.userName }}</span>
              <span class="reply-date">{{ formatDate(reply.createdAt) }}</span>
            </div>
            <p class="reply-content">{{ reply.content }}</p>
          </div>
        </div>

        <Transition name="reply-form">
          <div v-if="showReplyInput === review.id" class="reply-form">
            <LumiInput
              v-model="replyContent"
              size="sm"
              placeholder="写回复..."
              @enter="submitReply(review.id)"
            />
            <LumiButton
              variant="outline"
              size="sm"
              icon-only
              aria-label="发送回复"
              :disabled="!replyContent.trim()"
              @click="submitReply(review.id)"
            >
              <Send :size="12" />
            </LumiButton>
          </div>
        </Transition>
      </div>

      <LumiEmptyState
        v-if="reviews.length === 0"
        :icon="MessageCircle"
        title="暂无评价"
        description="快来写第一条吧！"
      />
    </div>
  </div>
</template>

<style scoped>
.market-reviews {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.reviews-summary {
  display: flex;
  gap: var(--space-6);
  padding: var(--space-5);
  background: var(--workspace-panel);
  border-radius: var(--radius-lg);
}

.rating-big {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  min-width: 100px;
}

.rating-number {
  font-size: var(--text-4xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  line-height: var(--leading-none);
}

.rating-count {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.rating-bars {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  justify-content: center;
}

.rating-bar-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.bar-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  width: var(--space-3);
  text-align: right;
}

.bar-track {
  flex: 1;
  height: 6px;
  border-radius: var(--radius-xs);
  background: var(--border-light);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: var(--radius-xs);
  background: var(--lumi-warning);
  transition: width var(--transition-normal);
}

.bar-count {
  font-size: var(--text-xs);
  color: var(--text-muted);
  width: var(--space-5);
}

.reviews-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sort-toggle {
  display: flex;
  gap: var(--space-1);
  background: var(--workspace-panel);
  border-radius: var(--radius-full);
  padding: var(--space-1);
}

.sort-btn {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.sort-btn.active {
  background: var(--workspace-card);
  color: var(--text-primary);
  box-shadow: var(--shadow-xs);
}

.review-form {
  padding: var(--space-5);
  background: var(--workspace-panel);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.form-rating {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.form-label {
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}

.form-textarea {
  width: 100%;
  padding: var(--space-3) var(--space-4);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  color: var(--text-primary);
  resize: vertical;
  min-height: 60px;
  transition: border-color var(--transition-fast);
}

.form-textarea:focus {
  border-color: var(--lumi-primary);
  box-shadow: var(--input-focus-ring);
}

.form-textarea::placeholder {
  color: var(--text-muted);
}

.form-actions {
  display: flex;
  gap: var(--space-2);
  justify-content: flex-end;
}

.reviews-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.review-item {
  padding: var(--space-5);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
}

.review-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.review-user {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.user-avatar {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-full);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
}

.user-info {
  display: flex;
  flex-direction: column;
}

.user-name {
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.review-date {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.review-content {
  font-size: var(--text-base);
  color: var(--text-secondary);
  line-height: var(--leading-relaxed);
  margin-bottom: var(--space-2);
}

.review-interactions {
  display: flex;
  gap: var(--space-3);
}

.reply-btn {
  font-size: var(--text-sm);
  color: var(--text-muted);
  transition: color var(--transition-fast);
}

.reply-btn:hover {
  color: var(--lumi-primary);
}

.replies-list {
  margin-top: var(--space-3);
  padding-left: var(--space-4);
  border-left: 2px solid var(--border-light);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.reply-item {
  padding: var(--space-3);
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
}

.reply-user {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.reply-avatar {
  width: var(--space-6);
  height: var(--space-6);
  border-radius: var(--radius-full);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
}

.reply-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.reply-date {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.reply-content {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: var(--leading-normal);
}

.reply-form {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.review-form-enter-active,
.reply-form-enter-active {
  animation: lumi-fade-in var(--duration-normal) var(--ease-out-expo);
}

.review-form-leave-active,
.reply-form-leave-active {
  animation: lumi-fade-in var(--duration-fast) var(--ease-out-expo) reverse;
}

@media (prefers-reduced-motion: reduce) {
  .sort-btn,
  .form-textarea,
  .reply-btn {
    animation: none;
    transition: none;
  }
}
</style>
