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

const ICON_THEME_MAP: Record<string, string> = {
  Brain: 'Brain',
  Home: 'Home',
  MessageSquare: 'MessageSquare',
  Search: 'Search',
  Volume2: 'Volume2',
  Zap: 'Zap',
  User: 'User',
  RefreshCw: 'RefreshCw',
  Globe: 'Globe',
  Laptop: 'Laptop',
  PenTool: 'PenTool',
  BookOpen: 'BookOpen',
  Palette: 'Palette',
  HeartPulse: 'HeartPulse',
  Users: 'Users',
  BarChart3: 'BarChart3',
  Bot: 'Bot',
  Lightbulb: 'Lightbulb',
  Terminal: 'Terminal',
  GraduationCap: 'GraduationCap',
  TrendingUp: 'TrendingUp',
  Shield: 'Shield',
  Scale: 'Scale',
  Package: 'Package',
  LayoutGrid: 'LayoutGrid',
  Cpu: 'Cpu',
  Wrench: 'Wrench',
  Puzzle: 'Puzzle',
  MessageCircle: 'MessageCircle',
  Code: 'Code',
  Image: 'Image',
  Heart: 'Heart',
}

const getIconTheme = (iconKey: string): string => ICON_THEME_MAP[iconKey] || 'default'

export { ITEM_ICON_MAP, DEFAULT_ICON, ICON_THEME_MAP, getIconTheme }
