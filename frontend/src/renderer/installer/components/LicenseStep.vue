<template>
  <div class="step-content license-step">
    <div class="step-header">
      <h1>许可协议</h1>
      <p>请仔细阅读以下许可协议，您必须同意此协议才能继续安装。</p>
    </div>

    <div class="license-container">
      <div class="license-header-bar">
        <span class="license-title">GNU AFFERO GENERAL PUBLIC LICENSE v3</span>
        <a class="license-link" @click="openLicenseUrl">查看完整协议</a>
      </div>
      <div class="license-text" ref="licenseRef">
        <pre>{{ licenseText || '正在加载许可协议...' }}</pre>
      </div>
    </div>

    <div class="agreement-section">
      <label class="radio-option" :class="{ selected: installOptions.agreeLicense }">
        <input
          type="radio"
          name="license-agreement"
          :checked="installOptions.agreeLicense"
          @change="installOptions.agreeLicense = true"
        />
        <span class="radio-custom"></span>
        <div class="option-content">
          <strong>我同意此协议 (A)</strong>
          <p>我已阅读并理解 AGPL-3.0 协议的全部条款，同意遵守其规定。</p>
        </div>
      </label>

      <label class="radio-option" :class="{ selected: !installOptions.agreeLicense }">
        <input
          type="radio"
          name="license-agreement"
          :checked="!installOptions.agreeLicense"
          @change="installOptions.agreeLicense = false"
        />
        <span class="radio-custom"></span>
        <div class="option-content">
          <strong>我不同意此协议 (D)</strong>
          <p>如果不同意，将无法继续安装 LuomiNest。</p>
        </div>
      </label>
    </div>

    <div class="opensource-notice">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>
      </svg>
      <div>
        <strong>开源承诺：</strong>LuomiNest 基于 AGPL-3.0 协议开源，
        所有源代码可在 GitHub 免费获取。本软件<strong>不存在任何付费版本或高级功能</strong>。
        如遇任何形式的付费要求，均为非官方渠道行为。
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
        :disabled="!installOptions.agreeLicense"
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
defineProps<{
  licenseText: string
  installOptions: { agreeLicense: boolean; [key: string]: unknown }
}>()

const emit = defineEmits<{
  next: []
  back: []
  cancel: []
}>()

const openLicenseUrl = async () => {
  try {
    await window.installerAPI.openUrl('https://www.gnu.org/licenses/agpl-3.0.html')
  } catch {
    // ignore
  }
}
</script>
