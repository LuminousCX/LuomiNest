<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { X } from 'lucide-vue-next'

const { t } = useI18n()

type ModalSize = 'sm' | 'md' | 'lg'

interface Props {
  visible?: boolean
  title?: string
  size?: ModalSize
  /** 自定义宽度（数字按 px），覆盖 size 预设 */
  width?: number | string
  /** 表单校验失败等场景的抖动反馈 */
  shake?: boolean
  closable?: boolean
  showMask?: boolean
  maskClosable?: boolean
  zIndex?: number
  /** plain：无头无脚灯箱模式——面板不带底色/边框/内边距，内容尺寸完全由插槽决定 */
  plain?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  title: '',
  size: 'md',
  width: undefined,
  shake: false,
  closable: true,
  showMask: true,
  maskClosable: true,
  zIndex: undefined,
  plain: false
})

const emit = defineEmits<{
  close: []
  'update:visible': [visible: boolean]
  /** 遮罩被点击时始终触发（无论 maskClosable），供抖动等自定义反馈使用 */
  'mask-click': []
}>()

const classes = computed(() => {
  const list = ['lumi-modal']
  if (!props.plain) list.push(`lumi-modal--${props.size}`)
  if (props.plain) list.push('lumi-modal--plain')
  if (props.shake) list.push('lumi-modal--shake')
  return list
})

const overlayStyle = computed(() => {
  if (props.zIndex !== undefined) {
    return { zIndex: props.zIndex }
  }
  return {}
})

const modalStyle = computed(() => {
  if (props.width !== undefined) {
    return { width: typeof props.width === 'number' ? `${props.width}px` : props.width }
  }
  return {}
})

const handleMaskClick = () => {
  emit('mask-click')
  if (props.maskClosable) {
    emit('update:visible', false)
    emit('close')
  }
}

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && props.closable) {
    handleClose()
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="lumi-modal">
      <div
        v-if="visible"
        class="lumi-modal-overlay"
        :style="overlayStyle"
        @click.self="handleMaskClick"
        @keydown="handleKeydown"
      >
        <div :class="classes" :style="modalStyle" role="dialog" aria-modal="true">
          <div v-if="!plain" class="lumi-modal__header">
            <h3 class="lumi-modal__title">
              <slot name="title">{{ title }}</slot>
            </h3>
            <button
              v-if="closable"
              type="button"
              class="lumi-modal__close"
              :aria-label="t('close')"
              @click="handleClose"
            >
              <X :size="18" />
            </button>
          </div>
          <div class="lumi-modal__body">
            <slot />
          </div>
          <div v-if="$slots.footer && !plain" class="lumi-modal__footer">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.lumi-modal-enter-active,
.lumi-modal-leave-active {
  transition: opacity var(--duration-fast) var(--ease-default);
}

.lumi-modal-enter-from,
.lumi-modal-leave-to {
  opacity: 0;
}

.lumi-modal-enter-active .lumi-modal,
.lumi-modal-leave-active .lumi-modal {
  transition: transform var(--duration-enter) var(--ease-out-expo), opacity var(--duration-fast) var(--ease-default);
}

.lumi-modal-enter-from .lumi-modal,
.lumi-modal-leave-to .lumi-modal {
  opacity: 0;
  transform: scale(0.96) translateY(8px);
}

.lumi-modal--shake {
  animation: lumi-modal-shake 0.4s var(--ease-default);
}

@keyframes lumi-modal-shake {
  0%, 100% { transform: translateX(0); }
  20%, 60% { transform: translateX(-6px); }
  40%, 80% { transform: translateX(6px); }
}

/* plain 灯箱模式：面板退化成透明容器，内容（图片/导航钮）完全由插槽决定 */
.lumi-modal--plain {
  width: auto;
  max-width: none;
  max-height: none;
  overflow: visible;
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  box-shadow: none;
  animation: none;
}
</style>
