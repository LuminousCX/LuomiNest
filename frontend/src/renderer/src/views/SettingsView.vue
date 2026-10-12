<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ChevronRight, User } from 'lucide-vue-next'
import { useCloudAccountStore } from '../stores/cloud-account'

interface SettingItem {
  label: string
  desc: string
  route: string
}

interface SettingGroup {
  title: string
  items: SettingItem[]
}

defineProps<{
  version?: string
}>()

const router = useRouter()
const { t } = useI18n()
const cloudAccount = useCloudAccountStore()

// 用户资料处头像与左上角侧栏同源（生态站通行证账号）
onMounted(() => cloudAccount.start())

// 标签走 vue-i18n，语言切换时 computed 重新求值
// 视觉取向：纯文字行（无图标 chip、无彩色点缀），层次靠留白与 hover 弱底色
const settingGroups = computed<SettingGroup[]>(() => [
  {
    title: t('settings.groupPreferences'),
    items: [
      { label: t('settings.language'), desc: t('settings.languageDesc'), route: '/settings/language' },
      { label: t('settings.appearance'), desc: t('settings.appearanceDesc'), route: '/settings/appearance' },
      { label: t('settings.notifications'), desc: t('settings.notificationsDesc'), route: '/settings/notifications' }
    ]
  },
  {
    title: t('settings.groupSystem'),
    items: [
      { label: t('settings.mainAgent'), desc: t('settings.mainAgentDesc'), route: '/settings/main-agent' },
      { label: t('settings.aiModel'), desc: t('settings.aiModelDesc'), route: '/settings/ai-model' },
      { label: t('settings.auth'), desc: t('settings.authDesc'), route: '/settings/auth' },
      { label: t('settings.cloud'), desc: t('settings.cloudDesc'), route: '/settings/cloud' },
      { label: t('settings.privacy'), desc: t('settings.privacyDesc'), route: '/settings/privacy' }
    ]
  },
  {
    title: t('settings.groupConnection'),
    items: [
      { label: t('settings.platforms'), desc: t('settings.platformsDesc'), route: '/settings/platforms' },
      { label: t('settings.plugins'), desc: t('settings.pluginsDesc'), route: '/settings/plugins' }
    ]
  }
])

const footerLinks = computed(() => [
  { label: t('settings.aboutDev'), route: '/settings/about' },
  { label: t('settings.license'), route: '/settings/license' },
  { label: t('settings.terms'), route: '/settings/terms-detail' },
  { label: t('settings.privacyCompliance'), route: '/settings/privacy-detail' }
])

const navigateTo = (route: string) => {
  router.push(route)
}
</script>

<template>
  <div class="settings-view">
    <div class="settings-view__content">
      <div class="settings-hero animate-fade-in">
        <div class="settings-hero__avatar">
          <img
            v-if="cloudAccount.avatar"
            :src="cloudAccount.avatar"
            :alt="cloudAccount.nickname || t('settings.title')"
            class="settings-hero__avatar-img"
            referrerpolicy="no-referrer"
          />
          <User v-else :size="28" />
        </div>
        <div class="settings-hero__content">
          <h1 class="settings-hero__title lumi-title-2xl">{{ t('settings.title') }}</h1>
          <p class="settings-hero__subtitle">{{ t('settings.subtitle') }}</p>
        </div>
        <div class="settings-hero__line">
          <span class="settings-hero__dot" />
          <span class="settings-hero__dash" />
          <span class="settings-hero__dot" />
        </div>
      </div>

      <div class="settings-body lumi-stack-5">
        <div
          v-for="(group, gIdx) in settingGroups"
          :key="group.title"
          class="setting-group animate-slide-up"
          :style="{ animationDelay: `${gIdx * 80}ms` }"
        >
          <h3 class="group-header__title">{{ group.title }}</h3>
          <div class="setting-items">
            <button
              v-for="item in group.items"
              :key="item.label"
              class="setting-item"
              @click="navigateTo(item.route)"
            >
              <div class="setting-item__info lumi-item-info">
                <span class="setting-item__label">{{ item.label }}</span>
                <span class="setting-item__desc">{{ item.desc }}</span>
              </div>
              <ChevronRight :size="16" class="setting-item__arrow" />
            </button>
          </div>
        </div>
      </div>

      <footer class="settings-footer">
        <div class="footer-brand">
          <span v-if="version" class="version-text">LuomiNest v{{ version }} · LuminousChenXi</span>
        </div>
        <nav class="footer-links">
          <button
            v-for="link in footerLinks"
            :key="link.label"
            type="button"
            class="footer-links__link"
            @click="navigateTo(link.route)"
          >
            {{ link.label }}
          </button>
        </nav>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  overflow-y: auto;
  padding: var(--space-6) var(--space-8) var(--space-5);
}

.settings-view__content {
  max-width: 860px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

/* ── Hero ── */
.settings-hero {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-5) 0;
  margin-bottom: var(--space-4);
  position: relative;
}

.settings-hero__avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: var(--radius-full);
  background: var(--surface);
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
  flex-shrink: 0;
  overflow: hidden;
}

.settings-hero__avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.settings-hero__content {
  flex: 1;
}

.settings-hero__title {
  letter-spacing: -0.3px;
  margin-bottom: var(--space-1);
}

.settings-hero__subtitle {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.settings-hero__line {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
  padding-left: var(--space-4);
}

.settings-hero__dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
  opacity: 0.6;
}

.settings-hero__dash {
  width: 48px;
  height: 1px;
  background: var(--border-light);
}

/* ── Body ──
   分组列表 / 条目行 / footer 的样式统一收敛到
   styles/views/settings-shared.css（.setting-group 等），此处只留页面壳。 */
.settings-body {
  padding-bottom: var(--space-6);
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .settings-view {
    padding: var(--space-4) var(--space-5) var(--space-3);
  }

  .settings-hero {
    flex-wrap: wrap;
    padding: var(--space-4) 0;
  }

  .settings-hero__line {
    display: none;
  }
}

@media (max-width: 480px) {
  .settings-view {
    padding: var(--space-3) var(--space-4) var(--space-2);
  }

  .settings-hero__avatar {
    width: 44px;
    height: 44px;
  }

  .settings-hero__title {
    font-size: var(--text-xl);
  }
}
</style>
