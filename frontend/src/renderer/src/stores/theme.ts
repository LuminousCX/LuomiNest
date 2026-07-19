import { defineStore } from 'pinia'
import { ref, computed, watch, toRaw } from 'vue'
import { getItem, setItem, getStringItem, setStringItem } from '../utils/storage'
import type { BackgroundConfig, ColorTheme, ThemeConfig } from './theme-types'
import { MAX_CUSTOM_THEMES } from './theme-types'
import { presetThemes } from './theme-presets'

export const useThemeStore = defineStore('theme', () => {
  // ─── Storage Keys ────────────────────────────
  const STORAGE_KEY = 'luominest-theme'
  const CONFIG_STORAGE_KEY = 'luominest-theme-config'

  // ─── Existing State ──────────────────────────
  const isDark = ref(getInitialTheme())

  // ─── New State ───────────────────────────────
  const activeColorThemeId = ref<string>('blue')
  const customThemes = ref<ColorTheme[]>([])
  const background = ref<BackgroundConfig>({
    image: null,
    blur: 0,
    opacity: 100
  })

  // ─── Getters ─────────────────────────────────
  const allThemes = computed<ColorTheme[]>(() => [...presetThemes, ...customThemes.value])

  const activeTheme = computed<ColorTheme | undefined>(() =>
    allThemes.value.find((t) => t.id === activeColorThemeId.value)
  )

  const isCustomTheme = computed<boolean>(() =>
    customThemes.value.some((t) => t.id === activeColorThemeId.value)
  )

  // ─── IPC Helper ──────────────────────────────
  const getApi = () => {
    return window.api?.config
  }

  // ─── Initial Load ────────────────────────────
  function getInitialTheme(): boolean {
    const stored = getStringItem(STORAGE_KEY, '')
    if (stored) return stored === 'dark'
    return false
  }

  function loadConfig(): Partial<ThemeConfig> | null {
    const config = getItem<ThemeConfig | null>(CONFIG_STORAGE_KEY, null)
    return config
  }

  // ─── DOM Application ─────────────────────────
  function applyTheme(dark: boolean) {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
    isDark.value = dark
    // Also sync color theme attribute
    document.documentElement.setAttribute('data-color-theme', activeColorThemeId.value)
  }

  function applyThemeToDOM() {
    const resolvedMode = isDark.value ? 'dark' : 'light'
    document.documentElement.setAttribute('data-theme', resolvedMode)
    document.documentElement.setAttribute('data-color-theme', activeColorThemeId.value)
  }

  function isCssGradient(value: string): boolean {
    return (
      value.startsWith('linear-gradient') ||
      value.startsWith('radial-gradient') ||
      value.startsWith('conic-gradient')
    )
  }

  function applyBackgroundToCSS() {
    const root = document.documentElement
    const image = background.value.image
    if (image) {
      if (isCssGradient(image)) {
        root.style.setProperty('--app-bg-image', image)
      } else {
        root.style.setProperty('--app-bg-image', `url('${image}')`)
      }
    } else {
      root.style.setProperty('--app-bg-image', 'none')
    }
    root.style.setProperty('--app-bg-blur', `${background.value.blur}px`)
    root.style.setProperty('--app-bg-opacity', String(background.value.opacity / 100))
  }

  // ─── Persistence ─────────────────────────────
  function saveConfig() {
    // 使用 toRaw + JSON 序列化，确保去掉 Vue Proxy/Ref，避免 IPC structured clone 失败
    const config = JSON.parse(JSON.stringify({
      activeColorThemeId: activeColorThemeId.value,
      activeMode: isDark.value ? 'dark' : 'light',
      background: toRaw(background.value),
      customThemes: toRaw(customThemes.value)
    })) as ThemeConfig
    setItem(CONFIG_STORAGE_KEY, config)
    // 同时通过 IPC 持久化到后端配置文件
    getApi()?.setThemeConfig(config).catch(() => {})
  }

  // ─── Actions: Existing (backward compatible) ─
  function toggleTheme() {
    applyTheme(!isDark.value)
  }

  function setTheme(dark: boolean) {
    applyTheme(dark)
  }

  // ─── Actions: Color Theme ────────────────────
  function setColorTheme(id: string) {
    activeColorThemeId.value = id
    applyThemeToDOM()
    saveConfig()
  }

  function addCustomTheme(theme: ColorTheme) {
    if (customThemes.value.length >= MAX_CUSTOM_THEMES) return
    customThemes.value.push(theme)
    saveConfig()
  }

  function updateCustomTheme(id: string, updates: Partial<ColorTheme>) {
    const idx = customThemes.value.findIndex((t) => t.id === id)
    if (idx !== -1) {
      customThemes.value[idx] = { ...customThemes.value[idx], ...updates }
      if (activeColorThemeId.value === id) applyThemeToDOM()
      saveConfig()
    }
  }

  function deleteCustomTheme(id: string) {
    customThemes.value = customThemes.value.filter((t) => t.id !== id)
    if (activeColorThemeId.value === id) {
      activeColorThemeId.value = 'blue'
      applyThemeToDOM()
    }
    saveConfig()
  }

  function renameCustomTheme(id: string, name: string) {
    updateCustomTheme(id, { name })
  }

  // ─── Actions: Background ─────────────────────
  function setBackgroundImage(image: string | null) {
    background.value.image = image
    applyBackgroundToCSS()
    saveConfig()
  }

  function setBackgroundBlur(blur: number) {
    background.value.blur = blur
    applyBackgroundToCSS()
    saveConfig()
  }

  function setBackgroundOpacity(opacity: number) {
    background.value.opacity = opacity
    applyBackgroundToCSS()
    saveConfig()
  }

  // ─── Watchers ────────────────────────────────
  let initialized = false

  watch(isDark, (val) => {
    setStringItem(STORAGE_KEY, val ? 'dark' : 'light')
    // Update data-theme attribute
    document.documentElement.setAttribute('data-theme', val ? 'dark' : 'light')
    if (initialized) {
      getApi()?.setTheme(val ? 'dark' : 'light').catch(() => {})
      saveConfig()
    }
  })

  // ─── Initialization ──────────────────────────
  // Load persisted config
  const savedConfig = loadConfig()
  if (savedConfig) {
    if (savedConfig.activeColorThemeId) activeColorThemeId.value = savedConfig.activeColorThemeId
    if (savedConfig.customThemes) customThemes.value = savedConfig.customThemes
    if (savedConfig.background) background.value = savedConfig.background
    // Restore isDark from config if available
    if (savedConfig.activeMode) {
      const modeDark = savedConfig.activeMode === 'dark'
      isDark.value = modeDark
    }
  }

  // Apply to DOM immediately
  applyTheme(isDark.value)
  applyBackgroundToCSS()

  // Try to load from IPC (overrides localStorage)
  const api = getApi()
  if (api) {
    // Load full theme config from IPC (authoritative source)
    api.getThemeConfig().then((config: any) => {
      if (config) {
        if (config.activeColorThemeId) activeColorThemeId.value = config.activeColorThemeId
        if (config.customThemes) customThemes.value = config.customThemes
        if (config.background) background.value = config.background
        if (config.activeMode) {
          isDark.value = config.activeMode === 'dark'
        }
        applyThemeToDOM()
        applyBackgroundToCSS()
      }
      initialized = true
    }).catch(() => {
      // Fallback: just load light/dark from legacy IPC
      api.getTheme().then((theme: string) => {
        if (theme === 'dark') applyTheme(true)
        else if (theme === 'light') applyTheme(false)
        initialized = true
      }).catch(() => {
        initialized = true
      })
    })
  } else {
    initialized = true
  }

  return {
    // Existing
    isDark,
    toggleTheme,
    setTheme,
    // New state
    activeColorThemeId,
    customThemes,
    background,
    // New getters
    allThemes,
    activeTheme,
    isCustomTheme,
    // Color theme actions
    setColorTheme,
    addCustomTheme,
    updateCustomTheme,
    deleteCustomTheme,
    renameCustomTheme,
    // Background actions
    setBackgroundImage,
    setBackgroundBlur,
    setBackgroundOpacity,
    // DOM application
    applyThemeToDOM,
    applyBackgroundToCSS
  }
})
