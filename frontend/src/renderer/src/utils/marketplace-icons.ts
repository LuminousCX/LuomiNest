import type { Component } from 'vue'
import {
  Brain, Home, MessageSquare, Search, Volume2, Zap, User, RefreshCw,
  Globe, Laptop, PenTool, BookOpen, Palette, HeartPulse, Users, BarChart3,
  Bot, Lightbulb, Terminal, GraduationCap, TrendingUp, Shield, Scale,
  Package, LayoutGrid, Cpu, Wrench, Puzzle, MessageCircle, Code, Image, Heart,
} from 'lucide-vue-next'

const ITEM_ICON_MAP: Record<string, Component> = {
  Brain, Home, MessageSquare, Search, Volume2, Zap, User, RefreshCw,
  Globe, Laptop, PenTool, BookOpen, Palette, HeartPulse, Users, BarChart3,
  Bot, Lightbulb, Terminal, GraduationCap, TrendingUp, Shield, Scale,
  Package, LayoutGrid, Cpu, Wrench, Puzzle, MessageCircle, Code, Image, Heart,
}

const DEFAULT_ICON: Component = Package

export { ITEM_ICON_MAP, DEFAULT_ICON }
