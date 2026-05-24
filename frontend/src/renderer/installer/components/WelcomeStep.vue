<template>
  <div class="step-content welcome-step">
    <div class="welcome-header">
      <h1>欢迎使用 LuomiNest</h1>
      <p class="welcome-subtitle">辰汐分布式AI伴侣平台</p>
    </div>

    <div class="welcome-body">
      <div class="feature-grid">
        <div class="feature-card">
          <div class="feature-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <h3>智能对话</h3>
          <p>基于大语言模型的自然语言交互，支持多轮对话与上下文理解</p>
        </div>

        <div class="feature-card">
          <div class="feature-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="11" width="18" height="10" rx="2"/>
              <circle cx="12" cy="5" r="3"/>
              <path d="M12 8v3"/>
            </svg>
          </div>
          <h3>Live2D 虚拟形象</h3>
          <p>高精度 Live2D 实时渲染，支持表情、动作、口型同步</p>
        </div>

        <div class="feature-card">
          <div class="feature-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
          </div>
          <h3>全屋智能控制</h3>
          <p>分布式架构支持多设备协同，统一管理智能家居生态</p>
        </div>

        <div class="feature-card highlight">
          <div class="feature-icon open-source">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>
            </svg>
          </div>
          <h3>100% 开源免费</h3>
          <p>AGPL-3.0 协议开源，无任何付费功能，社区驱动持续迭代</p>
        </div>
      </div>

      <div class="notice-banner">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="16" x2="12" y2="12"/>
          <line x1="12" y1="8" x2="12.01" y2="8"/>
        </svg>
        <span><strong>LuomiNest 是完全免费的开源软件。</strong>如果您是通过付费渠道获取的版本，建议卸载后从 GitHub 官方仓库下载正版。我们承诺：所有核心功能永久免费开放。</span>
      </div>
    </div>

    <div class="step-actions">
      <button class="btn btn-secondary" @click="$emit('cancel')">取消</button>
      <button class="btn btn-primary" @click="$emit('next')">
        开始安装
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineEmits<{
  next: []
  back: []
  cancel: []
}>()
</script>
