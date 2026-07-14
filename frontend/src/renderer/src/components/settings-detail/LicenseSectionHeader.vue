<script setup lang="ts">
import type { Component } from 'vue'

withDefaults(defineProps<{
  icon: Component
  title: string
  desc?: string
  theme?: 'primary' | 'warning' | 'accent' | 'success'
}>(), {
  theme: 'primary'
})
</script>

<template>
  <div class="license-section__header">
    <div class="lumi-settings-icon-wrap" :class="`lumi-settings-icon-wrap--${theme}`">
      <component :is="icon" :size="16" />
    </div>
    <div>
      <h3 class="license-section__title">{{ title }}</h3>
      <p v-if="desc" class="license-section__desc">{{ desc }}</p>
    </div>
  </div>
</template>
