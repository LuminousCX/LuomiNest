<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  Heart,
  Download,
  Star,
  Calendar,
  Tag,
  Shield,
  ExternalLink,
  MessageSquare,
  ChevronDown,
  ChevronUp
} from 'lucide-vue-next'
import { useMarketplaceStore } from '../../stores/marketplace'
import MarketIcon from '../../components/marketplace/MarketIcon.vue'
import RatingStars from '../../components/marketplace/RatingStars.vue'
import InstallButton from '../../components/marketplace/InstallButton.vue'
import ReviewItem from '../../components/marketplace/ReviewItem.vue'
import ReviewForm from '../../components/marketplace/ReviewForm.vue'

const route = useRoute()
const router = useRouter()
const store = useMarketplaceStore()

const itemId = computed(() => route.params.id as string)
const itemType = computed(() => route.params.type as 'plugin' | 'skill')

const item = computed(() => store.findItem(itemId.value))
const typeLabel = computed(() => itemType.value === 'plugin' ? '插件' : 'Skill')
const typeColor = computed(() => itemType.value === 'plugin' ? '#6366f1' : '#0d9488')

const showChangelog = ref(false)
const showPermissions = ref(false)

onMounted(() => {
  if (itemId.value) {
    store.fetchReviews(itemId.value)
  }
})

function goBack() {
  router.push('/marketplace')
}

function handleInstall(id: string) {
  store.installItem(id)
}

function handleUninstall(id: string) {
  store.uninstallItem(id)
}

function handleToggleFavorite() {
  if (item.value) {
    store.toggleFavorite(item.value.id)
  }
}

function handleReviewSubmit(itemId: string, rating: number, content: string) {
  store.addReview(itemId, rating, content)
}

function handleLikeReview(reviewId: string) {
  store.likeReview(reviewId)
}

function formatMarkdown(text: string): string {
  return text
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>')
}
</script>

<template>
  <div v-if="item" class="detail-view">
    <div class="detail-topbar animate-fade-in">
      <button class="back-btn" @click="goBack" aria-label="返回">
        <ArrowLeft :size="18" />
        <span>返回市场</span>
      </button>
    </div>

    <div class="detail-content">
      <div class="detail-hero animate-slide-up">
        <div class="hero-icon" :style="{ background: typeColor + '14', color: typeColor }">
          <MarketIcon :name="item.icon" :size="36" />
        </div>
        <div class="hero-info">
          <div class="hero-badges">
            <span class="type-badge" :style="{ background: typeColor + '18', color: typeColor }">
              {{ typeLabel }}
            </span>
            <span v-if="item.isInstalled" class="installed-badge">已安装</span>
          </div>
          <h1 class="hero-title">{{ item.name }}</h1>
          <p class="hero-author">by {{ item.author }}</p>
          <p class="hero-desc">{{ item.description }}</p>
          <div class="hero-stats">
            <div class="stat-item">
              <Star :size="14" class="star-icon" />
              <span class="stat-value">{{ item.rating.toFixed(1) }}</span>
              <span class="stat-label">({{ item.reviewCount }} 评价)</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <Download :size="14" />
              <span class="stat-value">{{ item.downloadCount.toLocaleString() }}</span>
              <span class="stat-label">下载</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <Calendar :size="14" />
              <span class="stat-value">{{ item.updatedAt }}</span>
              <span class="stat-label">更新</span>
            </div>
          </div>
        </div>
        <div class="hero-actions">
          <InstallButton :item="item" @install="handleInstall" @uninstall="handleUninstall" />
          <button
            :class="['fav-action-btn', { active: item.isFavorite }]"
            @click="handleToggleFavorite"
            :aria-label="item.isFavorite ? '取消收藏' : '收藏'"
          >
            <Heart :size="18" />
          </button>
        </div>
      </div>

      <div class="detail-body">
        <div class="detail-main">
          <div class="detail-section animate-slide-up" style="animation-delay: 100ms">
            <h2 class="section-heading">详细介绍</h2>
            <div class="description-content" v-html="formatMarkdown(item.longDescription)"></div>
          </div>

          <div v-if="item.changelog" class="detail-section animate-slide-up" style="animation-delay: 150ms">
            <button class="collapsible-header" @click="showChangelog = !showChangelog">
              <h2 class="section-heading">更新日志</h2>
              <component :is="showChangelog ? ChevronUp : ChevronDown" :size="18" class="collapse-icon" />
            </button>
            <Transition name="expand">
              <div v-if="showChangelog" class="collapsible-content">
                <div class="changelog-content" v-html="formatMarkdown(item.changelog)"></div>
              </div>
            </Transition>
          </div>

          <div v-if="item.permissions.length > 0" class="detail-section animate-slide-up" style="animation-delay: 200ms">
            <button class="collapsible-header" @click="showPermissions = !showPermissions">
              <h2 class="section-heading">
                <Shield :size="16" />
                权限要求
              </h2>
              <component :is="showPermissions ? ChevronUp : ChevronDown" :size="18" class="collapse-icon" />
            </button>
            <Transition name="expand">
              <div v-if="showPermissions" class="collapsible-content">
                <div class="permissions-list">
                  <div v-for="perm in item.permissions" :key="perm" class="permission-item">
                    <Shield :size="14" />
                    <span>{{ perm }}</span>
                  </div>
                </div>
              </div>
            </Transition>
          </div>

          <div class="detail-section reviews-section animate-slide-up" style="animation-delay: 250ms">
            <div class="reviews-header">
              <h2 class="section-heading">
                <MessageSquare :size="16" />
                用户评价
                <span class="review-count">({{ store.reviews.length }})</span>
              </h2>
              <RatingStars :rating="item.rating" :size="14" />
            </div>

            <ReviewForm :item-id="item.id" @submit="handleReviewSubmit" />

            <div class="reviews-list">
              <ReviewItem
                v-for="review in store.reviews"
                :key="review.id"
                :review="review"
                @like="handleLikeReview"
              />
            </div>
          </div>
        </div>

        <div class="detail-sidebar animate-slide-in-right">
          <div class="sidebar-card">
            <h4 class="sidebar-heading">信息</h4>
            <div class="info-list">
              <div class="info-row">
                <span class="info-label">版本</span>
                <span class="info-value">v{{ item.version }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">大小</span>
                <span class="info-value">{{ item.size }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">作者</span>
                <span class="info-value">{{ item.author }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">分类</span>
                <span class="info-value">{{ item.category }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">更新</span>
                <span class="info-value">{{ item.updatedAt }}</span>
              </div>
            </div>
          </div>

          <div class="sidebar-card">
            <h4 class="sidebar-heading">
              <Tag :size="14" />
              标签
            </h4>
            <div class="tag-list">
              <span v-for="tag in item.tags" :key="tag" class="detail-tag">{{ tag }}</span>
            </div>
          </div>

          <div v-if="item.homepage" class="sidebar-card">
            <a :href="item.homepage" target="_blank" rel="noopener" class="homepage-link">
              <ExternalLink :size="14" />
              <span>项目主页</span>
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div v-else class="not-found animate-scale-in">
    <div class="not-found-icon">
      <Star :size="48" />
    </div>
    <h2>未找到该内容</h2>
    <p>该{{ typeLabel }}可能已被下架或链接无效</p>
    <button class="back-market-btn" @click="goBack">返回市场</button>
  </div>
</template>

<style scoped>
.detail-view {
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
  gap: 6px;
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
  padding: 24px;
}

.detail-hero {
  display: flex;
  gap: 24px;
  padding: 24px;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-xl);
  margin-bottom: 24px;
}

.hero-icon {
  width: 72px;
  height: 72px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.hero-info {
  flex: 1;
  min-width: 0;
}

.hero-badges {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.type-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: var(--radius-full);
}

.installed-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.hero-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.hero-author {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.hero-desc {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-bottom: 14px;
}

.hero-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.stat-item .star-icon {
  color: #f59e0b;
}

.stat-value {
  font-weight: 600;
  color: var(--text-primary);
}

.stat-label {
  color: var(--text-muted);
}

.stat-divider {
  width: 1px;
  height: 14px;
  background: var(--border);
}

.hero-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
  flex-shrink: 0;
}

.fav-action-btn {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  background: var(--bg-secondary);
  transition: all var(--transition-fast);
}

.fav-action-btn:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.fav-action-btn.active {
  color: var(--lumi-accent);
}

.fav-action-btn.active :deep(svg) {
  fill: var(--lumi-accent);
}

.detail-body {
  display: flex;
  gap: 24px;
}

.detail-main {
  flex: 1;
  min-width: 0;
}

.detail-sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-section {
  margin-bottom: 24px;
}

.section-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 14px;
}

.description-content {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.description-content :deep(h3) {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-top: 16px;
  margin-bottom: 8px;
}

.description-content :deep(h4) {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-top: 12px;
  margin-bottom: 6px;
}

.description-content :deep(li) {
  margin-left: 16px;
  list-style: disc;
  margin-bottom: 4px;
}

.collapsible-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0;
  margin-bottom: 14px;
}

.collapsible-header .section-heading {
  margin-bottom: 0;
}

.collapse-icon {
  color: var(--text-muted);
  transition: transform var(--transition-fast);
}

.collapsible-content {
  padding-bottom: 8px;
}

.changelog-content {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.changelog-content :deep(h3) {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-top: 10px;
  margin-bottom: 6px;
}

.changelog-content :deep(li) {
  margin-left: 16px;
  list-style: disc;
  margin-bottom: 3px;
}

.permissions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.permission-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  font-size: 13px;
  color: var(--text-secondary);
}

.permission-item svg {
  color: var(--lumi-primary);
}

.reviews-section {
  margin-bottom: 0;
}

.reviews-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.review-count {
  font-size: 13px;
  font-weight: 400;
  color: var(--text-muted);
}

.reviews-list {
  margin-top: 16px;
}

.sidebar-card {
  padding: 16px;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
}

.sidebar-heading {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-label {
  font-size: 12px;
  color: var(--text-muted);
}

.info-value {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.detail-tag {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-weight: 500;
}

.homepage-link {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--lumi-primary);
  transition: all var(--transition-fast);
}

.homepage-link:hover {
  color: var(--lumi-primary-hover);
}

.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: var(--workspace-bg);
  text-align: center;
  padding: 40px;
}

.not-found-icon {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  background: var(--workspace-panel);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.not-found h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.not-found p {
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 20px;
}

.back-market-btn {
  padding: 8px 24px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: white;
  background: var(--lumi-primary);
  transition: all var(--transition-fast);
}

.back-market-btn:hover {
  background: var(--lumi-primary-hover);
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}

@media (max-width: 768px) {
  .detail-hero {
    flex-direction: column;
    gap: 16px;
    padding: 18px;
  }

  .hero-actions {
    flex-direction: row;
    align-items: center;
    width: 100%;
  }

  .hero-actions .install-button-wrapper {
    flex: 1;
  }

  .detail-body {
    flex-direction: column;
  }

  .detail-sidebar {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
  }

  .sidebar-card {
    flex: 1;
    min-width: 200px;
  }

  .detail-content {
    padding: 16px;
  }

  .hero-stats {
    gap: 8px;
  }
}
</style>
