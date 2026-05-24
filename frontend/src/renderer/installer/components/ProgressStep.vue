<template>
  <div class="step-content progress-step">
    <div class="progress-header">
      <div class="spinner"></div>
      <h1>正在安装 LuomiNest</h1>
      <p class="progress-message">{{ progressData.message || '请稍候...' }}</p>
    </div>

    <div class="progress-bar-container">
      <div class="progress-bar" :style="{ width: `${progressData.progress}%` }">
        <div class="progress-glow"></div>
      </div>
      <span class="progress-percent">{{ progressData.progress }}%</span>
    </div>

    <div class="progress-details">
      <div class="detail-item" v-for="n in 5" :key="n" :class="{ active: progressData.currentStep >= n, done: progressData.currentStep > n }">
        <div class="detail-icon">
          <svg v-if="progressData.currentStep > n" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          <div v-else-if="progressData.currentStep === n" class="mini-spinner"></div>
          <span v-else>{{ n }}</span>
        </div>
        <span :class="{ 'detail-text': true, done: progressData.currentStep > n }">
          {{ stepLabels[n - 1] }}
        </span>
      </div>
    </div>

    <div class="step-actions single">
      <button class="btn btn-text" disabled>安装进行中，请勿关闭此窗口...</button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  progressData: {
    progress: number
    currentStep: number
    totalSteps: number
    message: string
  }
}>()

const stepLabels = [
  '准备安装环境',
  '复制应用程序文件',
  '配置系统设置',
  '保存用户配置',
  '完成安装'
]
</script>
