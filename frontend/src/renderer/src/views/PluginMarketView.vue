<script setup lang="ts">
import { Puzzle } from 'lucide-vue-next'
import MarketViewLayout from '../components/marketplace/MarketViewLayout.vue'
</script>

<template>
  <MarketViewLayout
    market-type="plugin"
    :icon="Puzzle"
    title="插件市场"
    subtitle="扩展 LuomiNest 的能力边界"
    icon-color="#6366f1"
    icon-bg="linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.1))"
    all-label="全部插件"
    empty-text="没有找到匹配的插件"
  />
</template>
