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

<style scoped>
/* 说明：这些规则原先放在 license-view.css（LicenseView 的 scoped 样式），
   但 scoped 样式无法命中子组件的内部节点，__title/__desc 实际从未生效，故移到本组件内。 */
.license-section__title {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  margin-bottom: var(--space-1);
}

.license-section__desc {
  font-size: var(--text-base);
  color: var(--text-muted);
}
</style>
