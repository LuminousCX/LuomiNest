<script setup lang="ts">
import { ChevronRight } from 'lucide-vue-next'
import type { SectionItem } from './types'

defineProps<{
  section: string
  items: SectionItem[]
}>()
</script>

<template>
  <div class="settings-panel settings-panel--narrow animate-slide-up">
    <section class="settings-card">
      <div class="settings-card__body settings-card__body--compact">
        <div
          v-for="item in items"
          :key="item.label"
          class="settings-list-row"
        >
          <div class="settings-list-row__info">
            <span class="settings-list-row__title">{{ item.label }}</span>
            <span class="settings-list-row__desc">{{ item.desc }}</span>
          </div>
          <div class="settings-list-row__control">
            <span v-if="item.type === 'toggle'" class="lumi-toggle" />
            <span v-else-if="item.type === 'select'" class="settings-row-control">
              <span>请选择</span>
              <ChevronRight :size="14" />
            </span>
            <span v-else-if="item.type === 'input'" class="settings-row-control">
              <span>点击输入</span>
              <ChevronRight :size="14" />
            </span>
            <span v-else-if="item.type === 'slider'" class="settings-row-control__slider" />
            <span v-else-if="item.type === 'connect'" class="settings-row-control__connect">
              连接
            </span>
            <span v-else-if="item.type === 'time'" class="settings-row-control">
              <span>设置时段</span>
              <ChevronRight :size="14" />
            </span>
            <span v-else-if="item.type === 'password'" class="settings-row-control">
              <span>配置密码</span>
              <ChevronRight :size="14" />
            </span>
            <span v-else class="settings-row-control">
              <span>配置</span>
              <ChevronRight :size="14" />
            </span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings-list-row {
  cursor: default;
}

.settings-list-row__title {
  font-weight: 500;
}
</style>
