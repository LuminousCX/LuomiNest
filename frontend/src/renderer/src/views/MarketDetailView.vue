<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft, Star, Download, Users, Tag,
  ExternalLink, Check, FileText, ChevronDown,
  ChevronRight,
} from 'lucide-vue-next'
import { useMarketplaceStore } from '../stores/marketplace'
import MarketplaceInstallBtn from '../components/marketplace/MarketplaceInstallBtn.vue'
import MarketplaceReviews from '../components/marketplace/MarketplaceReviews.vue'
import type { MarketplaceType } from '../types/marketplace'
import { formatDateRelative, formatFileSize, formatDownloadCount } from '../utils/format'
import { ITEM_ICON_MAP, DEFAULT_ICON } from '../utils/marketplace-icons'

const route = useRoute()
const router = useRouter()
const store = useMarketplaceStore()

const activeTab = ref<'info' | 'versions' | 'reviews'>('info')
const expandedVersion = ref<string | null>(null)

const VALID_TYPES: MarketplaceType[] = ['plugin', 'skill', 'agent']

const itemType = computed<MarketplaceType>(() => {
  const t = route.params.type as string
  return VALID_TYPES.includes(t as MarketplaceType) ? (t as MarketplaceType) : 'plugin'
})

const itemId = computed(() => route.params.id as string)

const item = computed(() => store.getItemByTypeAndId(itemType.value, itemId.value))

const itemReviews = computed(() => store.getItemReviews(itemId.value))

const downloadDisplay = computed(() => {
  if (!item.value) return ''
  return formatDownloadCount(item.value.downloadCount)
})

function goBack() {
  router.push('/market')
}

function toggleVersion(version: string) {
  expandedVersion.value = expandedVersion.value === version ? null : version
}

const formatSize = (bytes: number) => formatFileSize(bytes)

const formatDate = (dateStr: string) => formatDateRelative(dateStr)
</script>

<template>
  <div v-if="item" class="market-detail-view">
    <div class="detail-topbar animate-fade-in">
      <button class="back-btn" @click="goBack">
        <ArrowLeft :size="18" />
        <span>{{ itemType === 'plugin' ? '插件市场' : itemType === 'skill' ? '技能市场' : '智能体市场' }}</span>
      </button>
    </div>

    <div class="detail-content">
      <div class="detail-hero animate-slide-up">
        <div class="hero-icon">
          <component :is="ITEM_ICON_MAP[item.icon] || DEFAULT_ICON" :size="40" />
        </div>
        <div class="hero-info">
          <div class="hero-title-row">
            <h1 class="hero-title">{{ item.name }}</h1>
            <span v-if="item.author.verified" class="verified-badge">
              <Check :size="12" />
              认证
            </span>
          </div>
          <p class="hero-author">by {{ item.author.name }}</p>
          <p class="hero-summary">{{ item.summary }}</p>
          <div class="hero-stats">
            <div class="hero-stat">
              <Star :size="14" class="star-icon" />
              <span class="stat-value">{{ item.rating.toFixed(1) }}</span>
              <span class="stat-label">({{ item.ratingCount }})</span>
            </div>
            <div class="hero-stat">
              <Download :size="14" />
              <span class="stat-value">{{ downloadDisplay }}</span>
              <span class="stat-label">下载</span>
            </div>
            <div class="hero-stat">
              <Users :size="14" />
              <span class="stat-value">{{ item.installedCount }}</span>
              <span class="stat-label">安装</span>
            </div>
          </div>
          <div class="hero-tags">
            <span
              v-for="tag in item.tags"
              :key="tag.id"
              class="detail-tag"
              :style="{ '--tag-color': tag.color }"
            >{{ tag.name }}</span>
          </div>
          <MarketplaceInstallBtn :item="item" size="large" />
        </div>
      </div>

      <div class="detail-tabs">
        <button
          :class="['tab-btn', { active: activeTab === 'info' }]"
          @click="activeTab = 'info'"
        >
          <FileText :size="15" />
          详情
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'versions' }]"
          @click="activeTab = 'versions'"
        >
          <Tag :size="15" />
          版本 ({{ item.versions.length }})
        </button>
        <button
          :class="['tab-btn', { active: activeTab === 'reviews' }]"
          @click="activeTab = 'reviews'"
        >
          <Star :size="15" />
          评价 ({{ item.ratingCount }})
        </button>
      </div>

      <div class="detail-body">
        <Transition name="tab-switch" mode="out-in">
          <div v-if="activeTab === 'info'" key="info" class="tab-content">
            <div class="info-section">
              <h3 class="info-title">详细介绍</h3>
              <p class="info-text">{{ item.description }}</p>
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
                  <span class="info-value">{{ formatSize(item.size) }}</span>
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
                  <span class="info-value">{{ formatDate(item.updatedAt) }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">创建日期</span>
                  <span class="info-value">{{ formatDate(item.createdAt) }}</span>
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

          <div v-else-if="activeTab === 'versions'" key="versions" class="tab-content">
            <div class="versions-list">
              <div
                v-for="ver in item.versions"
                :key="ver.version"
                class="version-item"
              >
                <button class="version-header" @click="toggleVersion(ver.version)">
                  <div class="version-info">
                    <span class="version-number">v{{ ver.version }}</span>
                    <span v-if="ver.version === item.version" class="version-current">当前</span>
                    <span class="version-date">{{ formatDate(ver.releasedAt) }}</span>
                  </div>
                  <div class="version-meta">
                    <span class="version-size">{{ formatSize(ver.size) }}</span>
                    <component
                      :is="expandedVersion === ver.version ? ChevronDown : ChevronRight"
                      :size="16"
                      class="version-expand"
                    />
                  </div>
                </button>
                <Transition name="expand">
                  <div v-if="expandedVersion === ver.version" class="version-changelog">
                    <p>{{ ver.changelog }}</p>
                  </div>
                </Transition>
              </div>
            </div>
          </div>

          <div v-else-if="activeTab === 'reviews'" key="reviews" class="tab-content">
            <MarketplaceReviews :item-id="itemId" :reviews="itemReviews" />
          </div>
        </Transition>
      </div>
    </div>
  </div>

  <div v-else class="detail-not-found">
    <p>未找到该商品</p>
    <button class="back-btn" @click="goBack">返回市场</button>
  </div>
</template>

<style scoped>
.market-detail-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.detail-topbar {
  display: flex;
  align-items: center;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.back-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
}

.detail-hero {
  display: flex;
  gap: 24px;
  margin-bottom: 28px;
}

.hero-icon {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-xl);
  background: var(--workspace-panel);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
  flex-shrink: 0;
}

.hero-info {
  flex: 1;
  min-width: 0;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
}

.hero-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.verified-badge {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 600;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.hero-author {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.hero-summary {
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 14px;
}

.hero-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 14px;
}

.hero-stat {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
}

.hero-stat .star-icon {
  color: var(--lumi-star);
}

.stat-value {
  font-weight: 600;
  color: var(--text-primary);
}

.stat-label {
  color: var(--text-muted);
  font-size: 12px;
}

.hero-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.detail-tag {
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 500;
  background: color-mix(in srgb, var(--tag-color) 10%, transparent);
  color: var(--tag-color);
}

.detail-tabs {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--workspace-panel);
  border-radius: var(--radius-lg);
  margin-bottom: 20px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.tab-btn:hover {
  color: var(--text-secondary);
}

.tab-btn.active {
  background: var(--workspace-card);
  color: var(--text-primary);
  box-shadow: var(--shadow-xs);
}

.detail-body {
  min-height: 200px;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.info-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.info-text {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
}

.info-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.info-links {
  display: flex;
  gap: 12px;
}

.info-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  transition: all var(--transition-fast);
}

.info-link:hover {
  background: var(--lumi-primary);
  color: var(--text-inverse);
}

.versions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
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
  padding: 14px 18px;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.version-header:hover {
  background: var(--surface-hover);
}

.version-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.version-number {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.version-current {
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 600;
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.version-date {
  font-size: 12px;
  color: var(--text-muted);
}

.version-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.version-size {
  font-size: 12px;
  color: var(--text-muted);
}

.version-expand {
  color: var(--text-muted);
}

.version-changelog {
  padding: 0 18px 14px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease-in-out;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.tab-switch-enter-active {
  animation: lumi-fade-in 0.2s ease-out;
}

.tab-switch-leave-active {
  animation: lumi-fade-in 0.1s ease-out reverse;
}

.detail-not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
  color: var(--text-muted);
}

.detail-not-found .back-btn {
  color: var(--lumi-primary);
}
</style>
