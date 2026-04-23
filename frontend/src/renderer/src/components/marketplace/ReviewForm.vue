<script setup lang="ts">
import { ref } from 'vue'
import { Send } from 'lucide-vue-next'
import RatingStars from './RatingStars.vue'

const props = defineProps<{
  itemId: string
}>()

const emit = defineEmits<{
  submit: [itemId: string, rating: number, content: string]
}>()

const rating = ref(0)
const content = ref('')
const isExpanded = ref(false)

function expand() {
  isExpanded.value = true
}

function handleSubmit() {
  if (rating.value === 0 || !content.value.trim()) return
  emit('submit', props.itemId, rating.value, content.value.trim())
  rating.value = 0
  content.value = ''
  isExpanded.value = false
}

function handleCancel() {
  rating.value = 0
  content.value = ''
  isExpanded.value = false
}
</script>

<template>
  <div :class="['review-form', { expanded: isExpanded }]">
    <div v-if="!isExpanded" class="form-trigger" @click="expand">
      <span>写下你的评价...</span>
    </div>
    <template v-else>
      <div class="form-rating">
        <span class="form-label">评分</span>
        <RatingStars v-model="rating" :rating="0" :interactive="true" :size="20" />
      </div>
      <textarea
        v-model="content"
        class="form-textarea"
        placeholder="分享你的使用体验..."
        rows="3"
      ></textarea>
      <div class="form-actions">
        <button class="action-btn cancel" @click="handleCancel">取消</button>
        <button
          :class="['action-btn submit', { disabled: rating === 0 || !content.trim() }]"
          :disabled="rating === 0 || !content.trim()"
          @click="handleSubmit"
        >
          <Send :size="14" />
          提交评价
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.review-form {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: 16px;
  border: 1px solid var(--border-light);
}

.form-trigger {
  padding: 10px 14px;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.form-trigger:hover {
  color: var(--text-secondary);
  background: var(--surface-hover);
}

.form-rating {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.form-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.form-textarea {
  width: 100%;
  padding: 10px 14px;
  background: var(--surface);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-primary);
  resize: vertical;
  min-height: 80px;
  transition: all var(--transition-fast);
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
  gap: 10px;
  justify-content: flex-end;
  margin-top: 12px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.action-btn.cancel {
  color: var(--text-muted);
  background: var(--surface);
}

.action-btn.cancel:hover {
  background: var(--surface-hover);
}

.action-btn.submit {
  color: white;
  background: var(--lumi-primary);
}

.action-btn.submit:hover {
  background: var(--lumi-primary-hover);
}

.action-btn.submit.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
