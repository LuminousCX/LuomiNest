<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  hoverable?: boolean
  borderless?: boolean
  flat?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const props = withDefaults(defineProps<Props>(), {
  hoverable: false,
  borderless: false,
  flat: false,
  padding: 'md'
})

const classes = computed(() => {
  const list = ['lumi-card']
  if (props.hoverable) list.push('lumi-card--hover')
  if (props.borderless) list.push('lumi-card--borderless')
  if (props.flat) list.push('lumi-card--flat')
  return list
})

const bodyPadding = computed(() => {
  const map = {
    none: '0',
    sm: 'var(--space-3)',
    md: 'var(--space-4)',
    lg: 'var(--space-5)'
  }
  return map[props.padding]
})
</script>

<template>
  <div :class="classes">
    <div v-if="$slots.header || $slots.title" class="lumi-card__header">
      <div class="lumi-card__title">
        <slot name="title" />
      </div>
      <div v-if="$slots.header" class="lumi-card__header-extra">
        <slot name="header" />
      </div>
    </div>
    <div class="lumi-card__body">
      <slot />
    </div>
    <div v-if="$slots.footer" class="lumi-card__footer">
      <slot name="footer" />
    </div>
  </div>
</template>

<style scoped>
.lumi-card__body {
  padding: v-bind(bodyPadding);
}
</style>
