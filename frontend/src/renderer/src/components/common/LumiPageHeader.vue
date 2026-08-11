<script setup lang="ts">
import { type Component } from 'vue'
import { ArrowLeft } from 'lucide-vue-next'

defineProps<{
  title?: string
  desc?: string
  icon?: Component
  back?: boolean
  badge?: string
}>()

defineEmits<{ back: [] }>()
</script>

<template>
  <div class="lumi-page-header">
    <div class="lumi-page-header__left">
      <button
        v-if="back"
        class="lumi-page-header__back"
        @click="$emit('back')"
      >
        <ArrowLeft :size="18" />
      </button>
      <!-- Default slot overrides title/desc/icon rendering -->
      <slot>
        <div v-if="icon" class="lumi-page-header__icon">
          <component :is="icon" :size="20" />
        </div>
        <div class="lumi-page-header__text">
          <div class="lumi-page-header__title-row">
            <h1 class="lumi-page-header__title">{{ title }}</h1>
            <span v-if="badge" class="lumi-page-header__badge">
              <slot name="badge">{{ badge }}</slot>
            </span>
          </div>
          <p v-if="desc" class="lumi-page-header__desc">{{ desc }}</p>
        </div>
      </slot>
    </div>
    <div v-if="$slots.actions" class="lumi-page-header__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.lumi-page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.lumi-page-header__left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.lumi-page-header__back {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-8);
  height: var(--space-8);
  border-radius: var(--radius-md);
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.lumi-page-header__back:hover {
  background: var(--surface-hover);
  color: var(--lumi-primary);
}

.lumi-page-header__icon {
  width: var(--space-9);
  height: var(--space-9);
  border-radius: var(--radius-lg);
  background: var(--lumi-primary-gradient-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
  flex-shrink: 0;
}

.lumi-page-header__text {
  min-width: 0;
}

.lumi-page-header__title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.lumi-page-header__title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  line-height: 1.2;
}

.lumi-page-header__badge {
  font-size: var(--text-xs);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  font-weight: var(--font-medium);
  white-space: nowrap;
}

.lumi-page-header__desc {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.lumi-page-header__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}
</style>
