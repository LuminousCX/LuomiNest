<template>
  <div class="step-content complete-step">
    <div class="complete-header">
      <div class="success-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="16 9 10 15 8 13"/>
        </svg>
      </div>
      <h1>安装完成</h1>
      <p>LuomiNest 已成功安装到您的设备上。</p>
    </div>

    <div class="complete-info">
      <div class="info-card">
        <div class="info-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <div>
          <strong>安装位置</strong>
          <p>{{ installOptions.installPath }}</p>
        </div>
      </div>
    </div>

    <div class="complete-actions">
      <label class="launch-option">
        <input type="checkbox" v-model="launchOnComplete" />
        <span>立即启动 LuomiNest</span>
      </label>
    </div>

    <div class="opensource-final">
      <p>
        感谢您选择 LuomiNest！本软件由
        <a @click="openGitHub">LuminousCX R&D Team</a>
        开源维护。如果您喜欢这个项目，欢迎在 GitHub 上给我们一个 Star。
      </p>
    </div>

    <div class="step-actions">
      <button class="btn btn-secondary" @click="$emit('cancel')">关闭</button>
      <button class="btn btn-primary launch-btn" @click="handleLaunch">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
        {{ launchOnComplete ? '启动应用' : '完成' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  installOptions: { installPath: string; [key: string]: unknown }
}>()

const emit = defineEmits<{
  cancel: []
  launch: []
}>()

const launchOnComplete = ref(true)

const handleLaunch = () => {
  if (launchOnComplete.value) {
    emit('launch')
  } else {
    emit('cancel')
  }
}

const openGitHub = async () => {
  try {
    await window.installerAPI.openUrl('https://github.com/LuminousCX/LuomiNest')
  } catch {
    // ignore
  }
}
</script>
