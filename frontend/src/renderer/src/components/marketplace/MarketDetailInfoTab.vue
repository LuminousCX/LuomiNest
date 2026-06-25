<script setup lang="ts">
import { ExternalLink } from 'lucide-vue-next'
import type { MarketplaceItem } from '../../types/marketplace'
import { formatFileSize, formatDateRelative } from '../../utils/format'

const props = defineProps<{
  item: MarketplaceItem
}>()

</script>

<template>
  <div class="tab-content">
    <div class="info-section">
      <h3 class="info-title">详细介绍</h3>
      <p class="info-text">{{ item.description || item.summary }}</p>
    </div>

    <div class="info-section">
      <h3 class="info-title">信息</h3>
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">版本</span>
          <span class="info-value">v{{ item.version }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">大小</span>
          <span class="info-value">{{ formatFileSize(item.size) }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">许可证</span>
          <span class="info-value">{{ item.license || '未指定' }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">最低版本</span>
          <span class="info-value">{{ item.minAppVersion || '无要求' }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">更新日期</span>
          <span class="info-value">{{ formatDateRelative(item.updatedAt) }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">创建日期</span>
          <span class="info-value">{{ formatDateRelative(item.createdAt) }}</span>
        </div>
      </div>
    </div>

    <div v-if="item.homepage || item.repository" class="info-section">
      <h3 class="info-title">链接</h3>
      <div class="info-links">
        <a v-if="item.homepage" :href="item.homepage" target="_blank" class="info-link">
          <ExternalLink :size="14" />
          主页
        </a>
        <a v-if="item.repository" :href="item.repository" target="_blank" class="info-link">
          <ExternalLink :size="14" />
          仓库
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tab-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.info-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.info-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.info-text {
  font-size: var(--text-md);
  color: var(--text-secondary);
  line-height: 1.7;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: var(--space-3);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3);
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
}

.info-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.info-links {
  display: flex;
  gap: var(--space-3);
}

.info-link {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  transition: all var(--transition-fast);
}

.info-link:hover {
  background: var(--lumi-primary);
  color: var(--text-inverse);
}
</style>