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
  Volume2,
  Brain,
  Puzzle,
  LogIn
} from 'lucide-vue-next'
import SettingsAppearanceSection from '../../components/settings-detail/SettingsAppearanceSection.vue'
import SettingsNotificationsSection from '../../components/settings-detail/SettingsNotificationsSection.vue'
import SettingsSecuritySection from '../../components/settings-detail/SettingsSecuritySection.vue'
import SettingsTtsSection from '../../components/settings-detail/SettingsTtsSection.vue'
import SettingsPlatformsSection from '../../components/settings-detail/SettingsPlatformsSection.vue'
import SettingsMainAgentSection from '../../components/settings-detail/SettingsMainAgentSection.vue'
import SettingsMcpSection from '../../components/settings-detail/SettingsMcpSection.vue'
import SettingsPluginsSection from '../../components/settings-detail/SettingsPluginsSection.vue'
import SettingsLoginSection from '../../components/settings-detail/SettingsLoginSection.vue'
import type { SectionItem } from '../../components/settings-detail/types'

const route = useRoute()
const router = useRouter()

const section = computed(() => route.params.section as string)

const sectionMap: Record<string, { label: string; icon: typeof Palette; desc: string; items: SectionItem[] }> = {
  appearance: {
    label: '外观主题',
    icon: Palette,
    desc: '自定义界面颜色与风格',
    items: [
      { label: '主题模式', desc: '浅色 / 深色 / 跟随系统', type: 'select' },
      { label: '主色调', desc: '选择界面主色调', type: 'color' },
      { label: '字体大小', desc: '调整界面文字大小', type: 'slider' },
      { label: '动画效果', desc: '开启或关闭界面动画', type: 'toggle' }
    ]
  },
  notifications: {
    label: '通知设置',
    icon: Bell,
    desc: '配置消息提醒方式',
    items: [
      { label: '桌面通知', desc: '接收桌面推送通知', type: 'toggle' },
      { label: '声音提醒', desc: '收到消息时播放提示音', type: 'toggle' },
      { label: '免打扰模式', desc: '设定免打扰时段', type: 'time' },
      { label: '消息预览', desc: '在通知中显示消息内容', type: 'toggle' }
    ]
  },
  privacy: {
    label: '隐私安全',
    icon: Shield,
    desc: '数据加密与访问控制',
    items: [
      { label: '端到端加密', desc: '所有对话数据加密存储', type: 'toggle' },
      { label: '本地存储', desc: '数据仅保存在本地设备', type: 'toggle' },
      { label: '自动清除', desc: '定期清除过期对话记录', type: 'select' },
      { label: '访问控制', desc: '设置应用启动密码', type: 'password' }
    ]
  },
  platforms: {
    label: '消息平台',
    icon: Globe,
    desc: 'QQ / 微信 / Discord 等',
    items: [
      { label: 'QQ', desc: '连接 QQ 机器人', type: 'connect' },
      { label: '微信', desc: '连接微信公众号/企微', type: 'connect' },
      { label: 'Discord', desc: '连接 Discord Bot', type: 'connect' },
      { label: 'Telegram', desc: '连接 Telegram Bot', type: 'connect' }
    ]
  },
  mcp: {
    label: 'MCP 工具',
    icon: Settings,
    desc: '外部工具接入协议',
    items: [
      { label: '已安装工具', desc: '查看和管理已安装的 MCP 工具', type: 'list' },
      { label: '添加工具', desc: '从市场或自定义安装工具', type: 'button' },
      { label: '工具权限', desc: '管理工具的访问权限', type: 'select' },
      { label: '运行日志', desc: '查看工具运行日志', type: 'button' }
    ]
  },
  'main-agent': {
    label: '主智能体',
    icon: Brain,
    desc: '工作台主 Agent 的人格、模型与行为配置',
    items: []
  },
  tts: {
    label: '语音合成 (TTS)',
    icon: Volume2,
    desc: '本地/在线 TTS 引擎与设备检测',
    items: []
  },
  plugins: {
    label: '插件与技能',
    icon: Puzzle,
    desc: '前端插件 / 后端插件 / 技能管理',
    items: []
  },
  auth: {
    label: '登录 / 注册',
    icon: LogIn,
    desc: '本地账户登录、注册与 JWT 管理',
    items: []
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
    case 'tts': return SettingsTtsSection
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
