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
  Brain
} from 'lucide-vue-next'
import SettingsAppearanceSection from '../../components/settings-detail/SettingsAppearanceSection.vue'
import SettingsNotificationsSection from '../../components/settings-detail/SettingsNotificationsSection.vue'
import SettingsSecuritySection from '../../components/settings-detail/SettingsSecuritySection.vue'
import SettingsTtsSection from '../../components/settings-detail/SettingsTtsSection.vue'
import SettingsPlatformsSection from '../../components/settings-detail/SettingsPlatformsSection.vue'
import SettingsMainAgentSection from '../../components/settings-detail/SettingsMainAgentSection.vue'
import SettingsMcpSection from '../../components/settings-detail/SettingsMcpSection.vue'
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
    default: return null
  }
})
</script>

<template>
  <div class="settings-detail-view">
    <div v-if="currentSection" class="detail-content animate-fade-in">
      <div class="settings-detail-header">
        <button class="back-btn" @click="router.push('/settings')">
          <ArrowLeft :size="18" />
        </button>
        <div class="header-icon">
          <component :is="currentSection.icon" :size="24" />
        </div>
        <div>
          <h1 class="page-title">{{ currentSection.label }}</h1>
          <p class="page-subtitle">{{ currentSection.desc }}</p>
        </div>
      </div>

      <div class="settings-body">
        <component :is="sectionComponent" />
      </div>
    </div>

    <div v-else class="not-found animate-fade-in">
      <h2>设置项未找到</h2>
      <p>请返回设置主页选择有效的设置项</p>
      <button class="back-home-btn" @click="router.push('/settings')">返回设置</button>
    </div>
  </div>
</template>

<style scoped>
.settings-detail-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.detail-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.settings-detail-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-5) var(--space-7);
  border-bottom: 1px solid var(--workspace-border);
  flex-shrink: 0;
}

.back-btn {
  width: var(--space-8);
  height: var(--space-8);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.back-btn:hover {
  background: var(--workspace-hover);
  color: var(--lumi-primary);
}

.header-icon {
  width: var(--space-9);
  height: var(--space-9);
  border-radius: var(--radius-lg);
  background: var(--lumi-brand-gradient-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
}

.page-title {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-top: 1px;
}

.settings-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6) var(--space-7);
}

.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: var(--space-3);
  color: var(--text-muted);
}

.not-found h2 {
  font-size: var(--text-2xl);
  color: var(--text-primary);
}

.not-found p {
  font-size: var(--text-base);
}

.back-home-btn {
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-5);
  border-radius: var(--radius-md);
  background: var(--lumi-primary);
  color: var(--text-inverse);
  font-size: var(--text-base);
  font-weight: 600;
  transition: all var(--transition-fast);
}

.back-home-btn:hover {
  background: var(--lumi-primary-hover);
}
</style>
