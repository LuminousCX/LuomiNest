<script setup lang="ts">
import { ref, computed } from 'vue'
import { MessageCircle, Send } from 'lucide-vue-next'
import type { MarketplaceReview } from '../../types/marketplace'
import MarketplaceRating from './MarketplaceRating.vue'
import { useMarketplaceStore } from '../../stores/marketplace'

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

function formatDate(dateStr: string) {
  return dateStr
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
      <button class="write-review-btn" @click="showReviewForm = !showReviewForm">
        <MessageCircle :size="14" />
        写评价
      </button>
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
          <button class="form-cancel" @click="showReviewForm = false">取消</button>
          <button
            :class="['form-submit', { disabled: !newReviewContent.trim() }]"
            :disabled="!newReviewContent.trim()"
            @click="submitReview"
          >
            <Send :size="13" />
            发布
          </button>
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
            <input
              v-model="replyContent"
              type="text"
              class="reply-input"
              placeholder="写回复..."
              @keyup.enter="submitReply(review.id)"
            />
            <button
              class="reply-submit"
              :disabled="!replyContent.trim()"
              @click="submitReply(review.id)"
            >
              <Send :size="12" />
            </button>
          </div>
        </Transition>
      </div>

      <div v-if="reviews.length === 0" class="empty-reviews">
        <MessageCircle :size="32" />
        <p>暂无评价，快来写第一条吧！</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.market-reviews {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.reviews-summary {
  display: flex;
  gap: 24px;
  padding: 20px;
  background: var(--workspace-panel);
  border-radius: var(--radius-lg);
}

.rating-big {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  min-width: 100px;
}

.rating-number {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.rating-count {
  font-size: 11px;
  color: var(--text-muted);
}

.rating-bars {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  justify-content: center;
}

.rating-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bar-label {
  font-size: 11px;
  color: var(--text-muted);
  width: 12px;
  text-align: right;
}

.bar-track {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: var(--border-light);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 3px;
  background: #f59e0b;
  transition: width var(--transition-normal);
}

.bar-count {
  font-size: 11px;
  color: var(--text-muted);
  width: 20px;
}

.reviews-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sort-toggle {
  display: flex;
  gap: 4px;
  background: var(--workspace-panel);
  border-radius: var(--radius-full);
  padding: 3px;
}

.sort-btn {
  padding: 5px 12px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.sort-btn.active {
  background: var(--workspace-card);
  color: var(--text-primary);
  box-shadow: var(--shadow-xs);
}

.write-review-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 500;
  color: white;
  background: var(--lumi-primary);
  transition: all var(--transition-fast);
}

.write-review-btn:hover {
  background: var(--lumi-primary-hover);
}

.review-form {
  padding: 16px;
  background: var(--workspace-panel);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-rating {
  display: flex;
  align-items: center;
  gap: 10px;
}

.form-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.form-textarea {
  width: 100%;
  padding: 10px 14px;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-primary);
  resize: vertical;
  min-height: 60px;
  transition: border-color var(--transition-fast);
}

.form-textarea:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.form-textarea::placeholder {
  color: var(--text-muted);
}

.form-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.form-cancel {
  padding: 6px 14px;
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.form-cancel:hover {
  background: var(--surface-hover);
}

.form-submit {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 16px;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 500;
  color: white;
  background: var(--lumi-primary);
  transition: all var(--transition-fast);
}

.form-submit:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.form-submit.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.reviews-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.review-item {
  padding: 16px;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
}

.review-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.review-user {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
}

.user-info {
  display: flex;
  flex-direction: column;
}

.user-name {
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

.review-interactions {
  display: flex;
  gap: 12px;
}

.reply-btn {
  font-size: 12px;
  color: var(--text-muted);
  transition: color var(--transition-fast);
}

.reply-btn:hover {
  color: var(--lumi-primary);
}

.replies-list {
  margin-top: 12px;
  padding-left: 16px;
  border-left: 2px solid var(--border-light);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.reply-item {
  padding: 10px;
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
}

.reply-user {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.reply-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 600;
}

.reply-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

.reply-date {
  font-size: 10px;
  color: var(--text-muted);
}

.reply-content {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.reply-form {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.reply-input {
  flex: 1;
  padding: 8px 12px;
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--text-primary);
  transition: border-color var(--transition-fast);
}

.reply-input:focus {
  border-color: var(--lumi-primary);
}

.reply-input::placeholder {
  color: var(--text-muted);
}

.reply-submit {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
  transition: all var(--transition-fast);
}

.reply-submit:hover:not(:disabled) {
  background: var(--lumi-primary-light);
}

.reply-submit:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.empty-reviews {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px 0;
  color: var(--text-muted);
}

.empty-reviews p {
  font-size: 13px;
}

.review-form-enter-active,
.reply-form-enter-active {
  animation: lumi-fade-in 0.25s ease-out;
}

.review-form-leave-active,
.reply-form-leave-active {
  animation: lumi-fade-in 0.15s ease-out reverse;
}
</style>
