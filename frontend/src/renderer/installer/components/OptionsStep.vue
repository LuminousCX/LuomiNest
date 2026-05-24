<template>
  <div class="step-content options-step">
    <div class="step-header">
      <h1>安装选项</h1>
      <p>自定义您的安装选项。所有选项均可稍后在设置中更改。</p>
    </div>

    <div class="options-list">
      <label class="option-item">
        <input
          type="checkbox"
          v-model="installOptions.allowTelemetry"
          class="custom-checkbox"
        />
        <div class="option-content">
          <div class="option-header">
            <strong>允许上传匿名使用数据</strong>
            <span class="option-badge optional">可选</span>
          </div>
          <p class="option-desc">
            帮助我们改进 LuomiNest。收集的数据仅包含匿名的性能统计和错误报告，
            不包含任何个人信息或对话内容。您可以随时在设置中关闭此功能。
          </p>
        </div>
      </label>

      <label class="option-item">
        <input
          type="checkbox"
          v-model="installOptions.createShortcut"
          class="custom-checkbox"
        />
        <div class="option-content">
          <div class="option-header">
            <strong>创建桌面快捷方式</strong>
            <span class="option-badge recommended">推荐</span>
          </div>
          <p class="option-desc">在桌面和开始菜单创建 LuomiNest 快捷方式，方便快速启动。</p>
        </div>
      </label>

      <label class="option-item">
        <input
          type="checkbox"
          v-model="installOptions.autoLaunch"
          class="custom-checkbox"
        />
        <div class="option-content">
          <div class="option-header">
            <strong>开机自启动</strong>
          </div>
          <p class="option-desc">登录系统后自动启动 LuomiNest 后台服务。适合需要持续运行 AI 伴侣的用户。</p>
        </div>
      </label>
    </div>

    <div class="opensource-reminder">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
      <div>
        <strong>隐私保护：</strong>LuomiNest 尊重您的隐私权。
        所有数据处理均在本地完成（除非您明确启用云端功能）。
        我们承诺<strong>永远不会</strong>将您的个人数据用于商业用途或出售给第三方。
      </div>
    </div>

    <div class="step-actions">
      <button class="btn btn-secondary" @click="$emit('back')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
        </svg>
        返回
      </button>
      <button class="btn btn-primary install-btn" @click="$emit('install')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
        开始安装
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  installOptions: {
    allowTelemetry: boolean
    createShortcut: boolean
    autoLaunch: boolean
    [key: string]: unknown
  }
}>()

defineEmits<{
  next: []
  back: []
  cancel: []
  install: []
}>()
</script>
