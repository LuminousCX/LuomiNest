<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  modelValue: string
  label?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const nativeInput = ref<HTMLInputElement | null>(null)
const hexInput = ref(props.modelValue)

// Sync hex text when prop changes
watch(() => props.modelValue, (val) => {
  hexInput.value = val
})

function openColorPicker() {
  nativeInput.value?.click()
}

function onNativeInput(e: Event) {
  const target = e.target as HTMLInputElement
  emit('update:modelValue', target.value)
}

function onHexCommit() {
  const v = hexInput.value.trim()
  if (/^#[0-9a-fA-F]{6}$/.test(v)) {
    emit('update:modelValue', v)
  } else {
    // Revert to current value
    hexInput.value = props.modelValue
  }
}
</script>

<template>
  <div class="color-picker-wrapper">
    <span v-if="label" class="color-picker-label">{{ label }}</span>
    <div
      class="color-picker-swatch"
      :style="{ background: modelValue }"
      @click="openColorPicker"
    />
    <input
      ref="nativeInput"
      type="color"
      class="color-picker-native"
      :value="modelValue"
      @input="onNativeInput"
    />
    <input
      ref="hexInput"
      v-model="hexInput"
      type="text"
      class="color-picker-hex"
      maxlength="7"
      placeholder="#000000"
      @blur="onHexCommit"
      @keydown.enter="onHexCommit"
    />
  </div>
</template>
