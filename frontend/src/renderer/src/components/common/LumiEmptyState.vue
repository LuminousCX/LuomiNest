<script setup lang="ts">
import { computed } from 'vue'
import {
  Inbox,
  Search,
  FileQuestion,
  AlertCircle,
  FolderOpen,
  type LucideIcon
} from 'lucide-vue-next'

type EmptyIcon = 'inbox' | 'search' | 'file' | 'error' | 'folder' | LucideIcon

interface Props {
  icon?: EmptyIcon
  title?: string
  description?: string
  size?: 'sm' | 'md' | 'lg'
}

const props = withDefaults(defineProps<Props>(), {
  icon: 'inbox',
  title: '暂无数据',
  description: '',
  size: 'md'
})

const iconMap: Record<string, LucideIcon> = {
  inbox: Inbox,
  search: Search,
  file: FileQuestion,
  error: AlertCircle,
  folder: FolderOpen
}

const iconComponent = computed(() => {
  if (typeof props.icon === 'string' && iconMap[props.icon]) {
    return iconMap[props.icon]
  }
  if (typeof props.icon === 'function') {
    return props.icon
  }
  return Inbox
})

const iconSize = computed(() => {
  const map = { sm: 36, md: 48, lg: 64 }
  return map[props.size]
})
</script>

<template>
  <div class="lumi-empty" :class="`lumi-empty--${size}`">
    <component :is="iconComponent" class="lumi-empty__icon" :size="iconSize" />
    <div v-if="title" class="lumi-empty__title">{{ title }}</div>
    <div v-if="description" class="lumi-empty__desc">{{ description }}</div>
    <div v-if="$slots.action" class="lumi-empty__action">
      <slot name="action" />
    </div>
  </div>
</template>

<style scoped>
.lumi-empty--sm {
  padding: var(--space-5) var(--space-4);
}

.lumi-empty--lg {
  padding: var(--space-10) var(--space-8);
}

.lumi-empty--lg .lumi-empty__title {
  font-size: var(--text-xl);
}
</style>
