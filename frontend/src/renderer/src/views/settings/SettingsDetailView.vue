<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  ArrowLeft,
  Palette,
  Bell,
  Shield,
  Globe,
  Settings,
  Brain,
  Puzzle,
  LogIn,
  Languages
} from 'lucide-vue-next'
import SettingsAppearanceSection from '../../components/settings-detail/SettingsAppearanceSection.vue'
import SettingsNotificationsSection from '../../components/settings-detail/SettingsNotificationsSection.vue'
import SettingsSecuritySection from '../../components/settings-detail/SettingsSecuritySection.vue'
import SettingsPlatformsSection from '../../components/settings-detail/SettingsPlatformsSection.vue'
import SettingsMainAgentSection from '../../components/settings-detail/SettingsMainAgentSection.vue'
import SettingsMcpSection from '../../components/settings-detail/SettingsMcpSection.vue'
import SettingsPluginsSection from '../../components/settings-detail/SettingsPluginsSection.vue'
import SettingsLoginSection from '../../components/settings-detail/SettingsLoginSection.vue'
import SettingsLanguageSection from '../../components/settings-detail/SettingsLanguageSection.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const section = computed(() => route.params.section as string)

// 标签走 vue-i18n，语言切换时 computed 重新求值
const sectionMap = computed<Record<string, { label: string; icon: typeof Palette; desc: string }>>(() => ({
  appearance: {
    label: t('settings.appearance'),
    icon: Palette,
    desc: t('settings.appearanceDesc')
  },
  notifications: {
    label: t('settings.notifications'),
    icon: Bell,
    desc: t('settings.notificationsDesc')
  },
  language: {
    label: t('settings.languageSection'),
    icon: Languages,
    desc: t('settings.languageSectionDesc')
  },
  privacy: {
    label: t('settings.privacy'),
    icon: Shield,
    desc: t('settings.privacyDesc')
  },
  platforms: {
    label: t('settings.platforms'),
    icon: Globe,
    desc: t('settings.platformsDesc')
  },
  mcp: {
    label: t('settings.mcp'),
    icon: Settings,
    desc: t('settings.mcpDesc')
  },
  'main-agent': {
    label: t('settings.mainAgent'),
    icon: Brain,
    desc: t('settings.mainAgentDesc')
  },
  plugins: {
    label: t('settings.plugins'),
    icon: Puzzle,
    desc: t('settings.pluginsDesc')
  },
  auth: {
    label: t('settings.auth'),
    icon: LogIn,
    desc: t('settings.authDesc')
  }
}))

const currentSection = computed(() => sectionMap.value[section.value] ?? null)

const sectionComponent = computed(() => {
  switch (section.value) {
    case 'appearance': return SettingsAppearanceSection
    case 'notifications': return SettingsNotificationsSection
    case 'language': return SettingsLanguageSection
    case 'privacy': return SettingsSecuritySection
    case 'platforms': return SettingsPlatformsSection
    case 'mcp': return SettingsMcpSection
    case 'main-agent': return SettingsMainAgentSection
    case 'plugins': return SettingsPluginsSection
    case 'auth': return SettingsLoginSection
    default: return null
  }
})
</script>

<template>
  <div class="lumi-settings-page">
    <template v-if="currentSection">
      <div class="lumi-settings-page__header animate-fade-in">
        <button class="lumi-settings-page__back" @click="router.push('/settings')">
          <ArrowLeft :size="18" />
        </button>
        <div class="lumi-settings-icon-wrap">
          <component :is="currentSection.icon" :size="22" />
        </div>
        <div>
          <h1 class="lumi-settings-page__title">{{ currentSection.label }}</h1>
          <p class="lumi-settings-page__subtitle">{{ currentSection.desc }}</p>
        </div>
      </div>

      <div class="lumi-settings-page__body custom-scrollbar">
        <component :is="sectionComponent" />
      </div>
    </template>

    <div v-else class="settings-not-found animate-fade-in">
      <h2>{{ t('settings.notFoundTitle') }}</h2>
      <p>{{ t('settings.notFoundDesc') }}</p>
      <button class="settings-not-found__btn" @click="router.push('/settings')">{{ t('settings.backToSettings') }}</button>
    </div>
  </div>
</template>

<style scoped>
.settings-not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: var(--space-3);
  color: var(--text-muted);
}

.settings-not-found h2 {
  font-size: var(--text-2xl);
  color: var(--text-primary);
}

.settings-not-found p {
  font-size: var(--text-base);
}

.settings-not-found__btn {
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-5);
  border-radius: var(--radius-md);
  background: var(--lumi-primary);
  color: var(--text-inverse);
  font-size: var(--text-base);
  font-weight: 600;
  transition: all var(--transition-fast);
}

.settings-not-found__btn:hover {
  background: var(--lumi-primary-hover);
}
</style>
