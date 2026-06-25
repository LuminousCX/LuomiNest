<script setup lang="ts">
import { computed } from 'vue'
import { X } from 'lucide-vue-next'

type ModalSize = 'sm' | 'md' | 'lg'

interface Props {
  visible?: boolean
  title?: string
  size?: ModalSize
  closable?: boolean
  showMask?: boolean
  maskClosable?: boolean
  zIndex?: number
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  title: '',
  size: 'md',
  closable: true,
  showMask: true,
  maskClosable: true,
  zIndex: undefined
})

const emit = defineEmits<{
  close: []
  'update:visible': [visible: boolean]
}>()

const classes = computed(() => {
  const list = ['lumi-modal']
  list.push(`lumi-modal--${props.size}`)
  return list
})

const overlayStyle = computed(() => {
  if (props.zIndex !== undefined) {
    return { zIndex: props.zIndex }
  }
  return {}
})

const handleMaskClick = () => {
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
        <div :class="classes" role="dialog" aria-modal="true">
          <div class="lumi-modal__header">
            <h3 class="lumi-modal__title">{{ title }}</h3>
            <button
              v-if="closable"
              type="button"
              class="lumi-modal__close"
              aria-label="关闭"
              @click="handleClose"
            >
              <X :size="18" />
            </button>
          </div>
          <div class="lumi-modal__body">
            <slot />
          </div>
          <div v-if="$slots.footer" class="lumi-modal__footer">
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
</style>
