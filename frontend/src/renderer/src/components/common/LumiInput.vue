<script setup lang="ts">
import { ref, computed, useSlots } from 'vue'
import { Eye, EyeOff } from 'lucide-vue-next'

interface Props {
  modelValue?: string | number | null
  modelModifiers?: { number?: boolean }
  type?: 'text' | 'password' | 'email' | 'number' | 'search' | 'tel' | 'url'
  placeholder?: string
  autocomplete?: string
  disabled?: boolean
  readonly?: boolean
  error?: boolean | string
  success?: boolean
  size?: 'sm' | 'md' | 'lg'
  clearable?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  type: 'text',
  disabled: false,
  readonly: false,
  error: false,
  success: false,
  size: 'md',
  clearable: false
})

const emit = defineEmits<{
  'update:modelValue': [value: string | number | null]
  blur: [event: FocusEvent]
  focus: [event: FocusEvent]
  enter: [event: KeyboardEvent]
}>()

const slots = useSlots()
const showPassword = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

const isPassword = computed(() => props.type === 'password')
const inputType = computed(() => {
  if (isPassword.value) return showPassword.value ? 'text' : 'password'
  return props.type
})

const errorMessage = computed(() => typeof props.error === 'string' ? props.error : '')
const hasError = computed(() => !!props.error)

const inputClasses = computed(() => {
  const list = ['lumi-input']
  list.push(`lumi-input--${props.size}`)
  if (slots.icon) list.push('has-icon')
  if (hasError.value) list.push('is-error')
  if (props.success) list.push('is-success')
  return list
})

const togglePassword = () => {
  showPassword.value = !showPassword.value
}

const handleInput = (e: Event) => {
  const value = (e.target as HTMLInputElement).value
  if (props.type === 'number' || props.modelModifiers?.number) {
    emit('update:modelValue', value === '' ? null : Number(value))
  } else {
    emit('update:modelValue', value)
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter') emit('enter', e)
}

const clear = () => {
  emit('update:modelValue', props.type === 'number' || props.modelModifiers?.number ? null : '')
  inputRef.value?.focus()
}
</script>

<template>
  <div class="lumi-input-root">
    <div class="lumi-input__wrapper">
      <span v-if="slots.icon" class="lumi-input__icon">
        <slot name="icon" />
      </span>
      <input
        ref="inputRef"
        :type="inputType"
        :value="modelValue"
        :placeholder="placeholder"
        :autocomplete="autocomplete"
        :disabled="disabled"
        :readonly="readonly"
        :class="inputClasses"
        @input="handleInput"
        @blur="$emit('blur', $event)"
        @focus="$emit('focus', $event)"
        @keydown="handleKeydown"
      />
      <button
        v-if="isPassword"
        type="button"
        class="lumi-input__suffix"
        tabindex="-1"
        @click="togglePassword"
      >
        <EyeOff v-if="showPassword" :size="16" />
        <Eye v-else :size="16" />
      </button>
      <button
        v-else-if="clearable && modelValue"
        type="button"
        class="lumi-input__suffix"
        tabindex="-1"
        @click="clear"
      >
        <span class="lumi-input__clear">×</span>
      </button>
    </div>
    <div v-if="errorMessage" class="form-error">
      {{ errorMessage }}
    </div>
  </div>
</template>

<style scoped>
.lumi-input-root {
  width: 100%;
}

.lumi-input__suffix {
  position: absolute;
  right: var(--space-3);
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-6);
  height: var(--space-6);
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.lumi-input__suffix:hover {
  color: var(--text);
  background: var(--surface-hover);
}

.lumi-input__clear {
  font-size: var(--text-xl);
  line-height: 1;
}

.lumi-input--sm {
  min-height: var(--space-7);
  font-size: var(--text-sm);
  padding: 0 var(--space-3);
}

.lumi-input--lg {
  min-height: 44px;
  font-size: var(--text-md);
  padding: 0 var(--space-5);
}

/* 带 icon 时为图标让位（scoped 特异性需覆盖上方 size 的 padding 简写） */
.lumi-input.has-icon {
  padding-left: var(--space-8);
}
</style>
