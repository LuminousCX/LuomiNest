<script setup lang="ts">
import { computed } from 'vue'
import { Loader2 } from 'lucide-vue-next'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'outline' | 'danger' | 'danger-ghost'
type ButtonSize = 'sm' | 'md' | 'lg'

interface Props {
  variant?: ButtonVariant
  size?: ButtonSize
  disabled?: boolean
  loading?: boolean
  block?: boolean
  icon?: boolean
  iconOnly?: boolean
  type?: 'button' | 'submit' | 'reset'
  ariaLabel?: string
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'secondary',
  size: 'md',
  disabled: false,
  loading: false,
  block: false,
  icon: false,
  iconOnly: false,
  type: 'button'
})

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const isDisabled = computed(() => props.disabled || props.loading)

const classes = computed(() => {
  const list = ['lumi-btn']
  list.push(`lumi-btn--${props.variant}`)
  list.push(`lumi-btn--${props.size}`)
  if (props.block) list.push('lumi-btn--block')
  if (props.iconOnly || props.icon) list.push(props.size === 'sm' ? 'lumi-btn--icon-sm' : props.size === 'lg' ? 'lumi-btn--icon-lg' : 'lumi-btn--icon')
  if (props.loading) list.push('is-loading')
  if (isDisabled.value) list.push('is-disabled')
  return list
})

const handleClick = (e: MouseEvent) => {
  if (isDisabled.value) return
  emit('click', e)
}
</script>

<template>
  <button
    :type="type"
    :class="classes"
    :disabled="isDisabled"
    :aria-label="ariaLabel"
    @click="handleClick"
  >
    <Loader2 v-if="loading" class="lumi-btn__spinner" :size="size === 'lg' ? 18 : 16" />
    <slot name="icon" />
    <span v-if="!iconOnly" class="lumi-btn-text">
      <slot />
    </span>
  </button>
</template>

<style scoped>
.lumi-btn__spinner {
  animation: spin 1s linear infinite;
}
</style>
