<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  Palette,
  Image as ImageIcon,
  RotateCcw,
  Check,
  Loader2
} from 'lucide-vue-next'
import { useToast } from '@/composables/useToast'
import {
  useStageBackgroundStore,
  STAGE_BG_PRESET_COLORS
} from '@/stores/stage-background'

const stageBg = useStageBackgroundStore()
const toast = useToast()

const expanded = ref(false)
const uploading = ref(false)
const rootRef = ref<HTMLElement | null>(null)
const colorInputRef = ref<HTMLInputElement | null>(null)

// ─── 当前激活的球（用于高亮环 + 对勾） ───
const activeBallId = computed<string>(() => {
  if (stageBg.settings.mode === 'default') return 'default'
  if (stageBg.settings.mode === 'image') return 'image'
  const current = (stageBg.settings.color ?? '').toLowerCase()
  const preset = STAGE_BG_PRESET_COLORS.find((p) => p.hex.toLowerCase() === current)
  return preset ? preset.id : 'custom-color'
})

// ─── 展开 / 收起 ───
function toggleMenu() {
  expanded.value = !expanded.value
}

function closeMenu() {
  expanded.value = false
}

function handleOutsideClick(e: MouseEvent) {
  if (!expanded.value) return
  if (rootRef.value && !rootRef.value.contains(e.target as Node)) {
    closeMenu()
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') closeMenu()
}

onMounted(() => {
  // capture 阶段监听，确保在球自身点击处理之前判定外部点击
  document.addEventListener('click', handleOutsideClick, true)
  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleOutsideClick, true)
  document.removeEventListener('keydown', handleKeydown)
})

// ─── 各球动作 ───
function handleReset() {
  stageBg.reset()
  closeMenu()
}

function handlePresetColor(hex: string) {
  stageBg.applyColor(hex)
  closeMenu()
}

function handleCustomColorClick() {
  colorInputRef.value?.click()
}

// input 事件在选择过程中实时生效（实时预览），change 事件在选择确认后收起菜单
function handleColorInput(e: Event) {
  const value = (e.target as HTMLInputElement).value
  if (/^#[0-9a-fA-F]{6}$/.test(value)) {
    stageBg.applyColor(value)
  }
}

function handleColorChange() {
  closeMenu()
}

async function handleImageClick() {
  if (uploading.value) return
  uploading.value = true
  try {
    const result = await stageBg.uploadImage()
    if (!result.success) {
      // 用户取消选择时不提示（结构化 cancelled 标志，不依赖错误文案）
      if (!result.cancelled) {
        toast.error(`上传背景图片失败：${result.error ?? '未知错误'}`)
      }
      return
    }
    if (result.warning) {
      toast.warning(result.warning)
    } else {
      toast.success(`背景图片已应用（${result.width}×${result.height}）`)
    }
    closeMenu()
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    console.error('[StageBackgroundMenu] upload error:', err)
    toast.error(`上传背景图片失败：${message}`)
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div ref="rootRef" class="stage-bg-menu" :class="{ open: expanded }">
    <!-- 触发球 -->
    <button
      class="bg-trigger-ball"
      :class="{ active: activeBallId !== 'default' }"
      title="舞台背景设置"
      aria-label="舞台背景设置"
      :aria-expanded="expanded"
      @click="toggleMenu"
    >
      <Palette :size="15" />
    </button>

    <!-- 展开的圆球列表（纯图形，无文字，逐个下落动画） -->
    <div class="bg-ball-list" aria-hidden="!expanded">
      <!-- 恢复默认 -->
      <button
        class="bg-ball bg-ball--default"
        :class="{ 'is-active': activeBallId === 'default' }"
        :style="{ '--i': 0 }"
        title="恢复默认背景"
        aria-label="恢复默认背景"
        :tabindex="expanded ? 0 : -1"
        @click="handleReset"
      >
        <RotateCcw :size="13" />
      </button>

      <!-- 预设底色：红 / 黄 / 绿 -->
      <button
        v-for="(preset, idx) in STAGE_BG_PRESET_COLORS"
        :key="preset.id"
        class="bg-ball bg-ball--preset"
        :class="{ 'is-active': activeBallId === preset.id }"
        :style="{ '--i': idx + 1, '--ball-color': preset.hex }"
        :title="`${preset.id === 'red' ? '红' : preset.id === 'yellow' ? '黄' : '绿'}色底`"
        :aria-label="`${preset.id === 'red' ? '红' : preset.id === 'yellow' ? '黄' : '绿'}色底`"
        :tabindex="expanded ? 0 : -1"
        @click="handlePresetColor(preset.hex)"
      >
        <Check v-if="activeBallId === preset.id" :size="13" class="ball-check" />
      </button>

      <!-- 自定义颜色（调起系统颜色选择器） -->
      <button
        class="bg-ball bg-ball--custom-color"
        :class="{ 'is-active': activeBallId === 'custom-color' }"
        :style="{ '--i': STAGE_BG_PRESET_COLORS.length + 1 }"
        title="自定义颜色"
        aria-label="自定义颜色"
        :tabindex="expanded ? 0 : -1"
        @click="handleCustomColorClick"
      >
        <Check v-if="activeBallId === 'custom-color'" :size="13" class="ball-check" />
      </button>
      <input
        ref="colorInputRef"
        type="color"
        class="bg-hidden-color-input"
        :value="stageBg.settings.color ?? '#5BA4D4'"
        aria-hidden="true"
        tabindex="-1"
        @input="handleColorInput"
        @change="handleColorChange"
      />

      <!-- 自定义图片（上传，一次仅保留一张） -->
      <button
        class="bg-ball bg-ball--image"
        :class="{ 'is-active': activeBallId === 'image' }"
        :style="{ '--i': STAGE_BG_PRESET_COLORS.length + 2 }"
        title="自定义背景图片"
        aria-label="自定义背景图片"
        :disabled="uploading"
        :tabindex="expanded ? 0 : -1"
        @click="handleImageClick"
      >
        <Loader2 v-if="uploading" :size="13" class="ball-spin" />
        <ImageIcon v-else :size="13" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.stage-bg-menu {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* ─── 触发球 ─── */
.bg-trigger-ball {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-light);
  background: var(--surface);
  color: var(--text-muted);
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition:
    color var(--duration-fast) var(--ease-in-out),
    border-color var(--duration-fast) var(--ease-in-out),
    transform var(--duration-fast) var(--ease-in-out),
    box-shadow var(--duration-fast) var(--ease-in-out);
}

.bg-trigger-ball:hover {
  color: var(--lumi-brand);
  border-color: var(--lumi-brand-border);
  transform: scale(1.08);
}

.bg-trigger-ball.active,
.stage-bg-menu.open .bg-trigger-ball {
  color: var(--lumi-brand);
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-subtle);
}

/* ─── 圆球列表（向下展开，逐个下落） ─── */
.bg-ball-list {
  position: absolute;
  top: calc(100% + 10px);
  right: 50%;
  transform: translateX(50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  z-index: 60;
  padding: 8px 6px;
  border-radius: var(--radius-full);
  background: color-mix(in srgb, var(--surface) 82%, transparent);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-md, 0 8px 24px rgba(0, 0, 0, 0.12));
  transition:
    opacity var(--duration-normal) var(--ease-in-out),
    transform var(--duration-normal) var(--ease-in-out);
}

.stage-bg-menu:not(.open) .bg-ball-list {
  opacity: 0;
  transform: translateX(50%) translateY(-8px) scale(0.9);
  pointer-events: none;
}

.bg-ball {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--surface);
  cursor: pointer;
  position: relative;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.16);
  transition:
    transform var(--duration-normal) var(--ease-out-expo, cubic-bezier(0.16, 1, 0.3, 1)),
    opacity var(--duration-normal) var(--ease-in-out),
    box-shadow var(--duration-fast) var(--ease-in-out);
}

/* 收起状态：上移 + 缩小 + 透明，逐个延迟落下 */
.stage-bg-menu:not(.open) .bg-ball {
  opacity: 0;
  transform: translateY(-10px) scale(0.4);
  transition-delay: 0s;
}

.stage-bg-menu.open .bg-ball {
  opacity: 1;
  transform: translateY(0) scale(1);
  transition-delay: calc(var(--i) * 40ms);
}

.bg-ball:hover {
  transform: translateY(0) scale(1.14);
  transition-delay: 0s;
}

.bg-ball:focus-visible {
  outline: 2px solid var(--lumi-brand);
  outline-offset: 2px;
}

.bg-ball.is-active {
  box-shadow:
    0 0 0 2px var(--lumi-brand),
    0 2px 8px rgba(0, 0, 0, 0.2);
}

/* 恢复默认球：浅灰底 + 图标 */
.bg-ball--default {
  background: var(--surface-hover);
  color: var(--text-muted);
}

.bg-ball--default:hover {
  color: var(--text);
}

/* 预设底色球 */
.bg-ball--preset {
  background: var(--ball-color);
  color: rgba(255, 255, 255, 0.95);
}

.ball-check {
  color: rgba(255, 255, 255, 0.95);
  stroke-width: 3;
}

/* 自定义颜色球：彩虹渐变 */
.bg-ball--custom-color {
  background: conic-gradient(
    from 180deg,
    #ff6b6b,
    #f5b940,
    #7ed957,
    #4cc3e8,
    #7a6ff0,
    #ff6b6b
  );
  color: rgba(255, 255, 255, 0.95);
}

/* 自定义图片球：蓝调渐变 + 图标 */
.bg-ball--image {
  background: linear-gradient(135deg, var(--lumi-brand) 0%, #7ec8e3 100%);
  color: rgba(255, 255, 255, 0.95);
}

.bg-ball--image:disabled {
  cursor: wait;
  opacity: 0.75;
}

.ball-spin {
  animation: ball-spin 1s linear infinite;
}

@keyframes ball-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 隐藏的原生取色器 */
.bg-hidden-color-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}
</style>
