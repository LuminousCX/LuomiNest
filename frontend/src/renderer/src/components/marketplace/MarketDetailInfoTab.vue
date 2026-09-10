<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ExternalLink } from 'lucide-vue-next'
import type { MarketplaceItem } from '../../types/marketplace'
import { formatFileSize, formatDateRelative } from '../../utils/format'

const props = defineProps<{
  item: MarketplaceItem
}>()

const { t } = useI18n()

</script>

<template>
  <div class="tab-content">
    <div class="info-section">
      <h3 class="info-title">{{ t('market.info.detailTitle') }}</h3>
      <p class="info-text">{{ item.description || item.summary }}</p>
    </div>

    <div class="info-section">
      <h3 class="info-title">{{ t('market.info.infoTitle') }}</h3>
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">{{ t('market.info.version') }}</span>
          <span class="info-value">v{{ item.version }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('market.info.size') }}</span>
          <span class="info-value">{{ formatFileSize(item.size) }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('market.info.license') }}</span>
          <span class="info-value">{{ item.license || t('market.info.notSpecified') }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('market.info.minVersion') }}</span>
          <span class="info-value">{{ item.minAppVersion || t('market.info.noRequirement') }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('market.info.updated') }}</span>
          <span class="info-value">{{ formatDateRelative(item.updatedAt) }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{ t('market.info.created') }}</span>
          <span class="info-value">{{ formatDateRelative(item.createdAt) }}</span>
        </div>
      </div>
    </div>

    <div v-if="item.homepage || item.repository" class="info-section">
      <h3 class="info-title">{{ t('market.info.links') }}</h3>
      <div class="info-links">
        <a v-if="item.homepage" :href="item.homepage" target="_blank" class="info-link">
          <ExternalLink :size="14" />
          {{ t('market.info.homepage') }}
        </a>
        <a v-if="item.repository" :href="item.repository" target="_blank" class="info-link">
          <ExternalLink :size="14" />
          {{ t('market.info.repository') }}
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