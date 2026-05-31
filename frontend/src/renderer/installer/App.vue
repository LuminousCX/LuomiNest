<template>
  <div class="installer-container">
    <div class="installer-titlebar" @mousedown="startDrag">
      <div class="titlebar-brand">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/>
          <path d="M2 17l10 5 10-5"/>
          <path d="M2 12l10 5 10-5"/>
        </svg>
        <span>LuomiNest</span>
      </div>
      <div class="titlebar-controls">
        <button class="titlebar-btn minimize" @click="handleMinimize" title="最小化">
          <svg width="12" height="12" viewBox="0 0 12 12"><line x1="2" y1="6" x2="10" y2="6" stroke="currentColor" stroke-width="1.5"/></svg>
        </button>
        <button class="titlebar-btn close" @click="handleClose" title="关闭">
          <svg width="12" height="12" viewBox="0 0 12 12"><line x1="2" y1="2" x2="10" y2="10" stroke="currentColor" stroke-width="1.5"/><line x1="10" y1="2" x2="2" y2="10" stroke="currentColor" stroke-width="1.5"/></svg>
        </button>
      </div>
    </div>

    <div class="installer-content">
      <div class="installer-sidebar">
        <div class="sidebar-logo">
          <div class="logo-glow"></div>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/>
            <path d="M2 17l10 5 10-5"/>
            <path d="M2 12l10 5 10-5"/>
          </svg>
        </div>
        <h2 class="sidebar-title">LuomiNest</h2>
        <p class="sidebar-version">v{{ version }}</p>
        <p class="sidebar-desc">辰汐分布式AI伴侣平台</p>

        <nav class="step-indicators">
          <div
            v-for="(step, index) in steps"
            :key="step.id"
            class="step-indicator"
            :class="{
              active: currentStep === index,
              completed: currentStep > index
            }"
          >
            <div class="step-dot">
              <svg v-if="currentStep > index" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              <span v-else>{{ index + 1 }}</span>
            </div>
            <span class="step-label">{{ step.label }}</span>
          </div>
        </nav>

        <div class="sidebar-footer">
          <p class="opensource-badge">100% 开源免费</p>
          <p class="opensource-link" @click="openUrl('https://github.com/LuminousCX/LuomiNest')">
            github.com/LuminousCX/LuomiNest
          </p>
        </div>
      </div>

      <div class="installer-main">
        <transition name="slide-fade" mode="out-in">
          <component
            :is="steps[currentStep].component"
            :key="currentStep"
            v-bind="stepProps"
            @next="nextStep"
            @back="prevStep"
            @cancel="handleCancel"
            @install="startInstall"
            @launch="launchApp"
          />
        </transition>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, markRaw } from 'vue'
import WelcomeStep from './components/WelcomeStep.vue'
import LicenseStep from './components/LicenseStep.vue'
import PathStep from './components/PathStep.vue'
import OptionsStep from './components/OptionsStep.vue'
import ProgressStep from './components/ProgressStep.vue'
import CompleteStep from './components/CompleteStep.vue'

declare global {
  interface Window {
    installerAPI: {
      getLicense: () => Promise<string>
      getDefaultPath: () => Promise<string>
      browseDirectory: (defaultPath?: string) => Promise<string | null>
      getDiskSpace: (path: string) => Promise<{ free: number; total: number }>
      validatePath: (targetPath: string) => Promise<{ valid: boolean; errors: string[] }>
      startInstallation: (options: {
        installPath: string
        agreeLicense: boolean
        allowTelemetry: boolean
        createShortcut: boolean
        autoLaunch: boolean
      }) => Promise<{ success: boolean; error?: string }>
      launchApp: () => Promise<void>
      openUrl: (url: string) => Promise<void>
      minimize: () => void
      close: () => void
      onProgress: (callback: (data: { progress: number; step: number; totalSteps: number; message: string }) => void) => () => void
    }
  }
}

const version = '0.5.0'

const currentStep = ref(0)

const installOptions = reactive({
  installPath: '',
  agreeLicense: false,
  allowTelemetry: false,
  createShortcut: true,
  autoLaunch: false
})

const progressData = reactive({
  progress: 0,
  currentStep: 0,
  totalSteps: 5,
  message: ''
})

const steps = [
  { id: 'welcome', label: '欢迎', component: markRaw(WelcomeStep) },
  { id: 'license', label: '许可协议', component: markRaw(LicenseStep) },
  { id: 'path', label: '安装位置', component: markRaw(PathStep) },
  { id: 'options', label: '选项', component: markRaw(OptionsStep) },
  { id: 'progress', label: '安装中', component: markRaw(ProgressStep) },
  { id: 'complete', label: '完成', component: markRaw(CompleteStep) }
]

const stepProps = {
  licenseText: '',
  defaultPath: '',
  installOptions,
  progressData
}

const initDefaults = async () => {
  try {
    const [license, path] = await Promise.all([
      window.installerAPI.getLicense(),
      window.installerAPI.getDefaultPath()
    ])
    stepProps.licenseText = license
    stepProps.defaultPath = path
    installOptions.installPath = path
  } catch {
    // use defaults
  }
}

initDefaults()

const nextStep = () => {
  if (currentStep.value < steps.length - 1) {
    currentStep.value++
  }
}

const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

const startInstall = async () => {
  currentStep.value = 4

  const unsubscribe = window.installerAPI.onProgress((data) => {
    Object.assign(progressData, data)
  })

  try {
    const result = await window.installerAPI.startInstallation({
      installPath: installOptions.installPath,
      agreeLicense: installOptions.agreeLicense,
      allowTelemetry: installOptions.allowTelemetry,
      createShortcut: installOptions.createShortcut,
      autoLaunch: installOptions.autoLaunch
    })

    if (result.success) {
      currentStep.value = 5
    } else {
      progressData.message = `安装失败: ${result.error || '未知错误'}`
    }
  } catch (err) {
    progressData.message = `安装出错: ${String(err)}`
  }

  unsubscribe()
}

const launchApp = async () => {
  await window.installerAPI.launchApp()
}

const handleCancel = () => {
  if (confirm('确定要取消安装吗？')) {
    window.installerAPI.close()
  }
}

const handleMinimize = () => {
  window.installerAPI.minimize()
}

const handleClose = () => {
  if (currentStep.value < 4) {
    handleCancel()
  } else {
    window.installerAPI.close()
  }
}

const openUrl = async (url: string) => {
  await window.installerAPI.openUrl(url)
}

let dragStartX = 0
let dragStartY = 0

const startDrag = (e: MouseEvent) => {
  if ((e.target as HTMLElement).closest('.titlebar-controls')) return
  dragStartX = e.screenX - window.screenLeft
  dragStartY = e.screenY - window.screenTop

  const onMove = (ev: MouseEvent) => {
    window.moveTo(ev.screenX - dragStartX, ev.screenY - dragStartY)
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }

  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}
</script>
