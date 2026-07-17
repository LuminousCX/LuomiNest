/**
 * 插件视图图标解析器 — 将 manifest 中声明的 Lucide 图标名解析为组件。
 *
 * 仅导入常用图标子集，避免打包全量 lucide。
 * 插件若声明未在 map 中的图标名，将回退到默认图标（Package）。
 */

import type { Component } from 'vue'
import {
  Sparkles,
  Package,
  Puzzle,
  LayoutGrid,
  Bot,
  Brain,
  Cpu,
  Globe,
  Palette,
  Terminal,
  BarChart3,
  GitBranch,
  Calendar,
  Home,
  MessageSquare,
  Settings,
  Zap,
  BookOpen,
  Lightbulb,
  Wrench,
  Code,
  Image,
  Heart,
  Shield,
  Users,
  Bot as BotIcon,
} from 'lucide-vue-next'

const PLUGIN_ICON_MAP: Record<string, Component> = {
  Sparkles,
  Package,
  Puzzle,
  LayoutGrid,
  Bot,
  Brain,
  Cpu,
  Globe,
  Palette,
  Terminal,
  BarChart3,
  GitBranch,
  Calendar,
  Home,
  MessageSquare,
  Settings,
  Zap,
  BookOpen,
  Lightbulb,
  Wrench,
  Code,
  Image,
  Heart,
  Shield,
  Users,
  BotIcon,
}

const DEFAULT_PLUGIN_ICON: Component = Package

/** 根据图标名解析 Lucide 组件，未找到时返回默认图标 */
export const resolvePluginIcon = (iconName?: string): Component => {
  if (!iconName) return DEFAULT_PLUGIN_ICON
  return PLUGIN_ICON_MAP[iconName] ?? DEFAULT_PLUGIN_ICON
}
