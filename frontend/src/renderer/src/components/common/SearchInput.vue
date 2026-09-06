<script setup lang="ts">
/**
 * 统一搜索输入框：LumiInput 封装，内置 Search 图标、可清空、loading 态。
 *
 * 会话搜索（走后端）与本地过滤搜索共用，保证全应用搜索框样式一致。
 */
import { computed, ref } from 'vue'
import { Search, Loader2 } from 'lucide-vue-next'
import LumiInput from './LumiInput.vue'

interface Props {
  modelValue?: string | number | null
  placeholder?: string
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  placeholder: '搜索...',
  size: 'sm',
  loading: false,
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string | number | null]
  enter: [event: KeyboardEvent]
  focus: [event: FocusEvent]
  blur: [event: FocusEvent]
}>()

const model = computed<string>({
  get: () => (props.modelValue ?? '') as string,
  set: (value) => emit('update:modelValue', value),
})

const inputRef = ref<InstanceType<typeof LumiInput> | null>(null)

defineExpose({
  focus: () => inputRef.value?.focus(),
})
</script>

<template>
  <LumiInput
    ref="inputRef"
    v-model="model"
    type="text"
    :placeholder="placeholder"
    :size="size"
    :disabled="disabled"
    clearable
    @enter="emit('enter', $event)"
    @focus="emit('focus', $event)"
    @blur="emit('blur', $event)"
  >
    <template #icon>
      <Loader2 v-if="loading && model" :size="14" class="search-input-spinner" />
      <Search v-else :size="14" />
    </template>
  </LumiInput>
</template>

<style scoped>
.search-input-spinner {
  animation: spin 0.9s linear infinite;
}
</style>
