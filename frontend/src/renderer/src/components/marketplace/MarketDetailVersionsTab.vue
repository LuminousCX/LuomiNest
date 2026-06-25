<script setup lang="ts">
import { Tag, ChevronDown, ChevronRight } from 'lucide-vue-next'
import type { MarketplaceItem } from '../../types/marketplace'
import { formatFileSize, formatDateRelative } from '../../utils/format'

const props = defineProps<{
  item: MarketplaceItem
  expandedVersion: string | null
}>()

const emit = defineEmits<{
  toggleVersion: [version: string]
}>()

</script>

<template>
  <div class="tab-content">
    <div v-if="item.versions && item.versions.length > 0" class="versions-list">
      <div
        v-for="ver in item.versions"
        :key="ver.version"
        class="version-item"
      >
        <button class="version-header" @click="emit('toggleVersion', ver.version)">
          <div class="version-info">
            <span class="version-number">v{{ ver.version }}</span>
            <span v-if="ver.version === item.version" class="version-current">当前</span>
            <span class="version-date">{{ formatDateRelative(ver.releasedAt) }}</span>
          </div>
          <div class="version-meta">
            <span class="version-size">{{ formatFileSize(ver.size) }}</span>
            <component
              :is="expandedVersion === ver.version ? ChevronDown : ChevronRight"
              :size="16"
              class="version-expand"
            />
          </div>
        </button>
        <Transition name="expand">
          <div v-if="expandedVersion === ver.version" class="version-changelog">
            <p>{{ ver.changelog || '暂无更新日志' }}</p>
          </div>
        </Transition>
      </div>
    </div>
    <div v-else class="empty-versions">
      <Tag :size="32" />
      <p>暂无版本信息</p>
    </div>
  </div>
</template>

<style scoped>
.tab-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.versions-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.version-item {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.version-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: var(--space-3) var(--space-5);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.version-header:hover {
  background: var(--surface-hover);
}

.version-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.version-number {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.version-current {
  padding: calc(var(--space-1) / 2) var(--space-2);
  border-radius: var(--radius-full);
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.version-date {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.version-meta {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.version-size {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.version-expand {
  color: var(--text-muted);
}

.version-changelog {
  padding: 0 var(--space-5) var(--space-3);
  font-size: var(--text-base);
  color: var(--text-secondary);
  line-height: var(--leading-normal);
}

.empty-versions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-10) 0;
  color: var(--text-muted);
}

.empty-versions p {
  font-size: var(--text-base);
}

.expand-enter-active,
.expand-leave-active {
  transition: all var(--duration-fast) var(--ease-in-out);
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}
</style>