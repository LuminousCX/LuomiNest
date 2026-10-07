/**
 * 全仓唯一的 Lucide 图标名 → 组件映射（marketplace 与 plugins 两份重叠映射的合并，
 * 见调查报告 §12）。仅导入常用子集，避免打包全量 lucide。
 */

import type { Component } from 'vue'
import {
  BarChart3,
  BookOpen,
  Bot,
  Brain,
  Calendar,
  Code,
  Cpu,
  Globe,
  GraduationCap,
  Heart,
  HeartPulse,
  Home,
  Image,
  Laptop,
  LayoutGrid,
  Lightbulb,
  MessageCircle,
  MessageSquare,
  Package,
  Palette,
  PenTool,
  Puzzle,
  RefreshCw,
  Scale,
  Search,
  Settings,
  Shield,
  Sparkles,
  GitBranch,
  Terminal,
  TrendingUp,
  User,
  Users,
  Volume2,
  Wrench,
  Zap,
} from 'lucide-vue-next'

export const LUCIDE_ICON_MAP: Record<string, Component> = {
  BarChart3,
  BookOpen,
  Bot,
  Brain,
  Calendar,
  Code,
  Cpu,
  Globe,
  GraduationCap,
  Heart,
  HeartPulse,
  Home,
  Image,
  Laptop,
  LayoutGrid,
  Lightbulb,
  MessageCircle,
  MessageSquare,
  Package,
  Palette,
  PenTool,
  Puzzle,
  RefreshCw,
  Scale,
  Search,
  Settings,
  Shield,
  Sparkles,
  GitBranch,
  Terminal,
  TrendingUp,
  User,
  Users,
  Volume2,
  Wrench,
  Zap,
}

export const DEFAULT_ICON: Component = Package

/** 根据图标名解析 Lucide 组件，未命中时返回 fallback（默认 Package） */
export const resolveIcon = (iconName?: string, fallback: Component = DEFAULT_ICON): Component => {
  if (!iconName) return fallback
  return LUCIDE_ICON_MAP[iconName] ?? fallback
}
