<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  Palette,
  Bell,
  Shield,
  Globe,
  Settings,
  Brain,
  Puzzle,
  LogIn
} from 'lucide-vue-next'
import SettingsAppearanceSection from '../../components/settings-detail/SettingsAppearanceSection.vue'
import SettingsNotificationsSection from '../../components/settings-detail/SettingsNotificationsSection.vue'
import SettingsSecuritySection from '../../components/settings-detail/SettingsSecuritySection.vue'
import SettingsPlatformsSection from '../../components/settings-detail/SettingsPlatformsSection.vue'
import SettingsMainAgentSection from '../../components/settings-detail/SettingsMainAgentSection.vue'
import SettingsMcpSection from '../../components/settings-detail/SettingsMcpSection.vue'
import SettingsPluginsSection from '../../components/settings-detail/SettingsPluginsSection.vue'
import SettingsLoginSection from '../../components/settings-detail/SettingsLoginSection.vue'

const route = useRoute()
const router = useRouter()

const section = computed(() => route.params.section as string)

const sectionMap: Record<string, { label: string; icon: typeof Palette; desc: string }> = {
  appearance: {
    label: '外观主题',
    icon: Palette,
    desc: '自定义界面颜色与风格'
  },
  notifications: {
    label: '通知设置',
    icon: Bell,
    desc: '配置消息提醒方式'
  },
  privacy: {
    label: '隐私安全',
    icon: Shield,
    desc: '数据加密与访问控制'
  },
  platforms: {
    label: '消息平台',
    icon: Globe,
    desc: 'QQ / 微信 / Discord 等'
  },
  mcp: {
    label: 'MCP 工具',
    icon: Settings,
    desc: '外部工具接入协议'
  },
  'main-agent': {
    label: '主智能体',
    icon: Brain,
    desc: '工作台主 Agent 的人格、模型与行为配置'
  },
  plugins: {
    label: '插件与技能',
    icon: Puzzle,
    desc: '前端插件 / 后端插件 / 技能管理'
  },
  auth: {
    label: '登录 / 注册',
    icon: LogIn,
    desc: '本地账户登录、注册与 JWT 管理'
  }
}

const currentSection = computed(() => sectionMap[section.value] ?? null)

const sectionComponent = computed(() => {
  switch (section.value) {
    case 'appearance': return SettingsAppearanceSection
    case 'notifications': return SettingsNotificationsSection
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
      <h2>设置项未找到</h2>
      <p>请返回设置主页选择有效的设置项</p>
      <button class="settings-not-found__btn" @click="router.push('/settings')">返回设置</button>
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
