<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next'
import MarketViewLayout from '../components/marketplace/MarketViewLayout.vue'
</script>

<template>
  <MarketViewLayout
    market-type="skill"
    :icon="Sparkles"
    title="技能市场"
    subtitle="赋予 AI 更丰富的专业技能"
    icon-color="var(--lumi-primary)"
    icon-bg="linear-gradient(135deg, rgba(13, 148, 136, 0.1), rgba(20, 184, 166, 0.1))"
    all-label="全部技能"
    empty-text="没有找到匹配的技能"
  />
</template>
