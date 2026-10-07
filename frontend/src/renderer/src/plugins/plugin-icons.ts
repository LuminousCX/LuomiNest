/**
 * 插件视图图标解析器 — 将 manifest 中声明的 Lucide 图标名解析为组件。
 * 映射表已并入 utils/lucide-icon-map（与市场图标同一份并集），本文件只保留插件域 API。
 */

import type { Component } from 'vue'
import { resolveIcon } from '../utils/lucide-icon-map'

/** 根据图标名解析 Lucide 组件，未找到时返回默认图标（Package） */
export const resolvePluginIcon = (iconName?: string): Component => resolveIcon(iconName)
