<script setup lang="ts">
import { computed } from 'vue'
import {
  MessageSquare, Clock, BarChart3, FileText, Image, Code2,
  Target, Hash, PenTool, Languages, Terminal, Brain, Palette,
  GraduationCap, BookOpen, ShieldCheck, LayoutGrid, Zap, Workflow,
  Star, Download, Heart, Puzzle, Sparkles
} from 'lucide-vue-next'

const iconMap: Record<string, any> = {
  MessageSquare, Clock, BarChart3, FileText, Image, Code2,
  Target, Hash, PenTool, Languages, Terminal, Brain, Palette,
  GraduationCap, BookOpen, ShieldCheck, LayoutGrid, Zap, Workflow,
  Star, Download, Heart, Puzzle, Sparkles
}

const props = defineProps<{
  name: string
  size?: number
}>()

const icon = computed(() => iconMap[props.name] || Puzzle)
</script>

<template>
  <component :is="icon" :size="size || 20" />
</template>
