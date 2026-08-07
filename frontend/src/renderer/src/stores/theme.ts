import { defineStore } from 'pinia'
import { ref, computed, watch, toRaw } from 'vue'
import { getItem, setItem, getStringItem, setStringItem } from '../utils/storage'
import type { BackgroundConfig, BackgroundFit, ColorTheme, Skin, ThemeConfig } from './theme-types'
import { MAX_CUSTOM_THEMES, MAX_CUSTOM_SKINS } from './theme-types'
import { presetThemes } from './theme-presets'
import { presetSkins, findPresetSkinById, getDefaultSkinIdForColorTheme } from './skin-presets'

const SYSTEM_DARK_QUERY = '(prefers-color-scheme: dark)'

export const useThemeStore = defineStore('theme', () => {
  // ─── Storage Keys ────────────────────────────
  const STORAGE_KEY = 'luominest-theme'
  const CONFIG_STORAGE_KEY = 'luominest-theme-config'

  // ─── Legacy State (kept for backward compatibility) ─
  const isDark = ref(getInitialTheme())
  const activeColorThemeId = ref<string>('blue')
  const activeMode = ref<'light' | 'dark' | 'system'>('light')
  const customThemes = ref<ColorTheme[]>([])
  const background = ref<BackgroundConfig & { fit?: BackgroundFit }>({
    image: null,
    blur: 5,
    opacity: 100
  })

  // ─── New Skin State ──────────────────────────
  const activeSkinId = ref<string>(getDefaultSkinIdForColorTheme('blue'))
  const customSkins = ref<Skin[]>([])

  // ─── Getters ─────────────────────────────────
  const allThemes = computed<ColorTheme[]>(() => [...presetThemes, ...customThemes.value])

  const allSkins = computed<Skin[]>(() => [...presetSkins, ...customSkins.value])

  const activeTheme = computed<ColorTheme | undefined>(() =>
    allThemes.value.find((t) => t.id === activeColorThemeId.value)
  )

  const activeSkin = computed<Skin | undefined>(() =>
    allSkins.value.find((s) => s.id === activeSkinId.value)
  )

  const isCustomTheme = computed<boolean>(() =>
    customThemes.value.some((t) => t.id === activeColorThemeId.value)
  )

  const isCustomSkin = computed<boolean>(() =>
    customSkins.value.some((s) => s.id === activeSkinId.value)
  )

  const effectiveColorThemeId = computed<string>(() =>
    activeSkin.value?.colorThemeId ?? activeColorThemeId.value
  )

  const effectiveMode = computed<'light' | 'dark' | 'system'>(() =>
    activeSkin.value?.mode ?? activeMode.value
  )

  const effectiveBackground = computed<BackgroundConfig & { fit?: BackgroundFit }>(() =>
    activeSkin.value?.background ?? background.value
  )

  const effectiveGlassIntensity = computed<number>(() =>
    activeSkin.value?.glassIntensity ?? 35
  )

  const effectiveAmbientIntensity = computed<number>(() =>
    activeSkin.value?.ambientIntensity ?? 30
  )

  const effectiveRadiusTendency = computed<number>(() =>
    activeSkin.value?.radiusTendency ?? 50
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
    document.documentElement.setAttribute('data-color-theme', effectiveColorThemeId.value)
  }

  function setActiveMode(mode: 'light' | 'dark' | 'system') {
    applyMode(mode)
    saveConfig()
  }

  function applyThemeToDOM() {
    const resolvedMode = isDark.value ? 'dark' : 'light'
    document.documentElement.setAttribute('data-theme', resolvedMode)
    document.documentElement.setAttribute('data-color-theme', effectiveColorThemeId.value)
  }

  function resolveSystemDark(): boolean {
    if (typeof window === 'undefined') return false
    return window.matchMedia(SYSTEM_DARK_QUERY).matches
  }

  function applyMode(mode: 'light' | 'dark' | 'system') {
    activeMode.value = mode
    const dark = mode === 'system' ? resolveSystemDark() : mode === 'dark'
    applyTheme(dark)
  }

  function applyBackgroundToCSS() {
    const root = document.documentElement
    const bg = effectiveBackground.value
    root.style.setProperty('--app-bg-blur', `${bg.blur}px`)
    root.style.setProperty('--app-bg-opacity', String(bg.opacity / 100))
    root.style.setProperty('--app-bg-fit', bg.fit ?? 'cover')
    root.style.setProperty('--app-bg-scale', bg.blur > 0 ? '1.06' : '1')
    root.style.setProperty('--lumi-glass-intensity', String(effectiveGlassIntensity.value / 100))
    root.style.setProperty('--lumi-ambient-intensity', String(effectiveAmbientIntensity.value / 100))
    root.style.setProperty('--lumi-radius-tendency', String(effectiveRadiusTendency.value / 100))
  }

  // ─── Persistence ─────────────────────────────
  function saveConfig() {
    const config = JSON.parse(JSON.stringify({
      activeColorThemeId: activeColorThemeId.value,
      activeMode: activeMode.value,
      background: toRaw(background.value),
      customThemes: toRaw(customThemes.value),
      activeSkinId: activeSkinId.value,
      customSkins: toRaw(customSkins.value)
    })) as ThemeConfig
    setItem(CONFIG_STORAGE_KEY, config)
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
    // 选择色彩主题时，如果当前是经典皮肤或无皮肤，则切换到对应经典皮肤
    const currentSkin = activeSkin.value
    if (!currentSkin || currentSkin.type === 'preset' && currentSkin.id.startsWith('skin-classic-')) {
      activeSkinId.value = getDefaultSkinIdForColorTheme(id)
    }
    applyThemeToDOM()
    applyBackgroundToCSS()
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
      if (effectiveColorThemeId.value === id) applyThemeToDOM()
      saveConfig()
    }
  }

  function deleteCustomTheme(id: string) {
    customThemes.value = customThemes.value.filter((t) => t.id !== id)
    if (effectiveColorThemeId.value === id) {
      activeColorThemeId.value = 'blue'
      activeSkinId.value = getDefaultSkinIdForColorTheme('blue')
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

  function setBackgroundFit(fit: BackgroundFit) {
    background.value = { ...background.value, fit }
    applyBackgroundToCSS()
    saveConfig()
  }

  // ─── Actions: Skin ───────────────────────────
  function setSkin(id: string) {
    activeSkinId.value = id
    const skin = activeSkin.value
    if (skin) {
      activeColorThemeId.value = skin.colorThemeId
      activeMode.value = skin.mode
      background.value = {
        image: skin.background.image,
        blur: skin.background.blur,
        opacity: skin.background.opacity
      }
    }
    applyMode(effectiveMode.value)
    applyThemeToDOM()
    applyBackgroundToCSS()
    saveConfig()
  }

  function addCustomSkin(skin: Skin) {
    if (customSkins.value.length >= MAX_CUSTOM_SKINS) return
    customSkins.value.push(skin)
    setSkin(skin.id)
  }

  function updateCustomSkin(id: string, updates: Partial<Skin>) {
    const idx = customSkins.value.findIndex((s) => s.id === id)
    if (idx !== -1) {
      customSkins.value[idx] = { ...customSkins.value[idx], ...updates }
      if (activeSkinId.value === id) {
        setSkin(id)
      } else {
        saveConfig()
      }
    }
  }

  function deleteCustomSkin(id: string) {
    customSkins.value = customSkins.value.filter((s) => s.id !== id)
    if (activeSkinId.value === id) {
      activeSkinId.value = getDefaultSkinIdForColorTheme(activeColorThemeId.value)
      setSkin(activeSkinId.value)
    } else {
      saveConfig()
    }
  }

  function renameCustomSkin(id: string, name: string) {
    updateCustomSkin(id, { name })
  }

  // ─── Watchers ────────────────────────────────
  let initialized = false

  watch(isDark, (val) => {
    setStringItem(STORAGE_KEY, val ? 'dark' : 'light')
    document.documentElement.setAttribute('data-theme', val ? 'dark' : 'light')
    if (initialized) {
      getApi()?.setTheme(val ? 'dark' : 'light').catch(() => {})
      saveConfig()
    }
  })

  // ─── Initialization ──────────────────────────
  function migrateLegacyConfig(config: Partial<ThemeConfig>): Partial<ThemeConfig> {
    // 已有皮肤字段：直接返回
    if (config.activeSkinId && (config.customSkins || findPresetSkinById(config.activeSkinId))) {
      return config
    }

    // 旧配置迁移：根据色彩主题 + 背景生成对应经典皮肤或自定义皮肤
    const colorId = config.activeColorThemeId ?? 'blue'
    const bg = config.background ?? { image: null, blur: 5, opacity: 100 }
    const mode = config.activeMode ?? (config.isDark ? 'dark' : 'light')

    const defaultSkinId = getDefaultSkinIdForColorTheme(colorId)
    const hasCustomBackground = !!bg.image
    const isCustomColor = (config.customThemes ?? []).some((t) => t.id === colorId)

    if (!hasCustomBackground && !isCustomColor && findPresetSkinById(defaultSkinId)) {
      return { ...config, activeSkinId: defaultSkinId }
    }

    // 创建自定义皮肤来承载旧配置
    const skinId = `migrated-${Date.now()}`
    const migratedSkin: Skin = {
      id: skinId,
      name: isCustomColor ? '我的自定义主题' : '我的皮肤',
      type: 'custom',
      colorThemeId: colorId,
      mode,
      background: {
        image: bg.image,
        blur: bg.blur,
        opacity: bg.opacity,
        fit: 'cover'
      },
      glassIntensity: 35,
      ambientIntensity: 30,
      radiusTendency: 50
    }
    return {
      ...config,
      activeSkinId: skinId,
      customSkins: [...(config.customSkins ?? []), migratedSkin]
    }
  }

  function initFromConfig(config: Partial<ThemeConfig>) {
    const migrated = migrateLegacyConfig(config)

    if (migrated.activeSkinId) activeSkinId.value = migrated.activeSkinId
    if (migrated.customSkins) customSkins.value = migrated.customSkins
    if (migrated.activeColorThemeId) activeColorThemeId.value = migrated.activeColorThemeId
    if (migrated.customThemes) customThemes.value = migrated.customThemes
    if (migrated.background) background.value = migrated.background
    if (migrated.activeMode) {
      applyMode(migrated.activeMode)
    } else if (typeof migrated.isDark === 'boolean') {
      activeMode.value = migrated.isDark ? 'dark' : 'light'
      applyMode(activeMode.value)
    }

    // 确保激活的皮肤有效
    if (!findPresetSkinById(activeSkinId.value) && !customSkins.value.some((s) => s.id === activeSkinId.value)) {
      activeSkinId.value = getDefaultSkinIdForColorTheme(activeColorThemeId.value)
    }
  }

  // 1. 先尝试从本地存储恢复，保证首屏不闪白/黑
  const savedConfig = loadConfig()
  if (savedConfig) {
    initFromConfig(savedConfig)
  } else {
    activeMode.value = isDark.value ? 'dark' : 'light'
    applyMode(activeMode.value)
  }

  applyThemeToDOM()
  applyBackgroundToCSS()

  // Listen to system dark mode changes when in system mode
  if (typeof window !== 'undefined') {
    const media = window.matchMedia(SYSTEM_DARK_QUERY)
    media.addEventListener('change', (e) => {
      if (effectiveMode.value === 'system') {
        applyTheme(e.matches)
      }
    })
  }

  // 2. 再从 IPC 加载权威配置（异步，覆盖本地存储）
  const api = getApi()
  if (api) {
    api.getThemeConfig().then((config: any) => {
      if (config) {
        initFromConfig(config)
        applyMode(effectiveMode.value)
        applyThemeToDOM()
        applyBackgroundToCSS()
      }
      initialized = true
    }).catch(() => {
      api.getTheme().then((theme: string) => {
        if (theme === 'dark') {
          activeMode.value = 'dark'
          applyMode('dark')
        } else if (theme === 'light') {
          activeMode.value = 'light'
          applyMode('light')
        }
        applyThemeToDOM()
        applyBackgroundToCSS()
        initialized = true
      }).catch(() => {
        initialized = true
      })
    })
  } else {
    initialized = true
  }

  return {
    // Legacy
    isDark,
    toggleTheme,
    setTheme,
    // Color theme state
    activeColorThemeId,
    activeMode,
    customThemes,
    background,
    // Skin state
    activeSkinId,
    customSkins,
    // Getters
    allThemes,
    allSkins,
    activeTheme,
    activeSkin,
    isCustomTheme,
    isCustomSkin,
    effectiveColorThemeId,
    effectiveMode,
    effectiveBackground,
    effectiveGlassIntensity,
    effectiveAmbientIntensity,
    effectiveRadiusTendency,
    // Color theme actions
    setColorTheme,
    setActiveMode,
    addCustomTheme,
    updateCustomTheme,
    deleteCustomTheme,
    renameCustomTheme,
    // Background actions
    setBackgroundImage,
    setBackgroundBlur,
    setBackgroundOpacity,
    setBackgroundFit,
    // Skin actions
    setSkin,
    addCustomSkin,
    updateCustomSkin,
    deleteCustomSkin,
    renameCustomSkin,
    // DOM application
    applyThemeToDOM,
    applyBackgroundToCSS
  }
})
