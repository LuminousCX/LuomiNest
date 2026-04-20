<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  User,
  Palette,
  Bell,
  Shield,
  Database,
  Globe,
  Settings
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const section = computed(() => route.params.section as string)

const sectionMap: Record<string, { label: string; icon: typeof User; desc: string; items: { label: string; desc: string; type: string }[] }> = {
  profile: {
    label: '个人资料',
    icon: User,
    desc: '管理你的账户信息',
    items: [
      { label: '用户名', desc: '设置你的显示名称', type: 'input' },
      { label: '头像', desc: '上传或更换头像', type: 'upload' },
      { label: '个人简介', desc: '一段简短的自我介绍', type: 'textarea' },
      { label: '语言偏好', desc: '界面显示语言', type: 'select' }
    ]
  },
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
  memory: {
    label: '记忆系统',
    icon: Database,
    desc: '三层记忆架构配置',
    items: [
      { label: '工作记忆容量', desc: '短期对话上下文窗口大小', type: 'slider' },
      { label: '情景记忆', desc: '自动保存对话场景', type: 'toggle' },
      { label: '语义记忆', desc: '长期知识图谱构建', type: 'toggle' },
      { label: '记忆检索', desc: '相关记忆自动召回', type: 'toggle' }
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
  }
}

const currentSection = computed(() => sectionMap[section.value] ?? null)
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
        <div class="setting-items-card animate-slide-up">
          <div
            v-for="(item, idx) in currentSection.items"
            :key="item.label"
            :class="['setting-row', { last: idx === currentSection.items.length - 1 }]"
          >
            <div class="row-info">
              <span class="row-label">{{ item.label }}</span>
              <span class="row-desc">{{ item.desc }}</span>
            </div>
            <div class="row-control">
              <div v-if="item.type === 'toggle'" class="toggle-switch">
                <span class="toggle-thumb" />
              </div>
              <div v-else-if="item.type === 'select'" class="control-select">
                <span class="control-placeholder">请选择</span>
              </div>
              <div v-else-if="item.type === 'input'" class="control-input">
                <span class="control-placeholder">点击输入</span>
              </div>
              <div v-else-if="item.type === 'slider'" class="control-slider">
                <div class="slider-track" />
              </div>
              <div v-else-if="item.type === 'connect'" class="control-connect">
                <span class="connect-btn">连接</span>
              </div>
              <div v-else class="control-default">
                <span class="control-placeholder">配置</span>
              </div>
            </div>
          </div>
        </div>
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
  gap: 12px;
  padding: 20px 28px;
  border-bottom: 1px solid var(--workspace-border);
  flex-shrink: 0;
}

.back-btn {
  width: 36px;
  height: 36px;
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
  width: 44px;
  height: 44px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, rgba(13, 148, 136, 0.1), rgba(20, 184, 166, 0.1));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 1px;
}

.settings-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
}

.setting-items-card {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  max-width: 640px;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid var(--workspace-border);
  transition: background var(--transition-fast);
}

.setting-row.last {
  border-bottom: none;
}

.setting-row:hover {
  background: var(--workspace-hover);
}

.row-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.row-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.row-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.row-control {
  flex-shrink: 0;
  margin-left: 16px;
}

.toggle-switch {
  width: 44px;
  height: 24px;
  border-radius: 12px;
  background: var(--workspace-border);
  position: relative;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.toggle-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.control-select,
.control-input,
.control-default {
  padding: 6px 14px;
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-sm);
}

.control-placeholder {
  font-size: 12px;
  color: var(--text-muted);
}

.control-slider {
  width: 120px;
  height: 6px;
}

.slider-track {
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: var(--workspace-border);
  position: relative;
}

.slider-track::after {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 60%;
  height: 100%;
  border-radius: 3px;
  background: var(--lumi-primary);
}

.control-connect {
  padding: 6px 16px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-light);
}

.connect-btn {
  font-size: 12px;
  font-weight: 600;
  color: var(--lumi-primary);
}

.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: var(--text-muted);
}

.not-found h2 {
  font-size: 18px;
  color: var(--text-primary);
}

.not-found p {
  font-size: 13px;
}

.back-home-btn {
  margin-top: 8px;
  padding: 8px 20px;
  border-radius: var(--radius-md);
  background: var(--lumi-primary);
  color: white;
  font-size: 13px;
  font-weight: 600;
  transition: all var(--transition-fast);
}

.back-home-btn:hover {
  background: var(--lumi-primary-hover);
}
</style>
