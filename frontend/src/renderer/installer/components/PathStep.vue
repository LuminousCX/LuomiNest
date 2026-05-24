<template>
  <div class="step-content path-step">
    <div class="step-header">
      <h1>选择安装位置</h1>
      <p>选择 LuomiNest 的安装目录。建议使用默认路径。</p>
    </div>

    <div class="path-input-group">
      <label class="input-label">安装路径</label>
      <div class="path-input-row">
        <input
          type="text"
          v-model="installOptions.installPath"
          class="path-input"
          placeholder="请输入或选择安装路径"
          @blur="validatePath"
        />
        <button class="btn btn-outline browse-btn" @click="browseDirectory">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          浏览
        </button>
      </div>

      <div v-if="validationErrors.length > 0" class="validation-errors">
        <div v-for="(error, index) in validationErrors" :key="index" class="error-item">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          {{ error }}
        </div>
      </div>

      <div v-if="!validationErrors.length && installOptions.installPath && validated" class="validation-success">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
        安装路径有效
      </div>
    </div>

    <div class="disk-info">
      <div class="info-row">
        <span class="info-label">所需空间</span>
        <span class="info-value">约 200 MB</span>
      </div>
    </div>

    <div class="step-actions">
      <button class="btn btn-secondary" @click="$emit('back')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
        </svg>
        返回
      </button>
      <button
        class="btn btn-primary"
        :disabled="validationErrors.length > 0 || !installOptions.installPath"
        @click="$emit('next')"
      >
        下一步
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  defaultPath: string
  installOptions: { installPath: string; [key: string]: unknown }
}>()

const emit = defineEmits<{
  next: []
  back: []
  cancel: []
}>()

const validationErrors = ref<string[]>([])
const validated = ref(false)

const validatePath = async () => {
  const path = (installOptions as unknown as { installPath: string }).installPath
  if (!path) {
    validationErrors.value = []
    return
  }

  try {
    const result = await window.installerAPI.validatePath(path)
    validationErrors.value = result.errors
    validated.value = true
  } catch {
    validationErrors.value = ['无法验证路径']
  }
}

const browseDirectory = async () => {
  try {
    const result = await window.installerAPI.browseDirectory(
      (installOptions as unknown as { installPath: string }).installPath
    )
    if (result) {
      ;(installOptions as unknown as { installPath: string }).installPath = result
      await validatePath()
    }
  } catch {
    // ignore
  }
}
</script>
