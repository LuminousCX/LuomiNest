import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const STORAGE_KEY = 'luominest-theme'

  const isDark = ref(getInitialTheme())

  const getApi = () => {
    return window.api?.config
  }

  function getInitialTheme(): boolean {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) return stored === 'dark'
    return false
  }

  function applyTheme(dark: boolean) {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
    isDark.value = dark
  }

  function toggleTheme() {
    applyTheme(!isDark.value)
  }

  function setTheme(dark: boolean) {
    applyTheme(dark)
  }

  let initialized = false

  watch(isDark, (val) => {
    localStorage.setItem(STORAGE_KEY, val ? 'dark' : 'light')
    if (initialized) {
      getApi()?.setTheme(val ? 'dark' : 'light').catch(() => {})
    }
  })

  applyTheme(isDark.value)

  const api = getApi()
  if (api) {
    api.getTheme().then((theme: string) => {
      if (theme === 'dark') applyTheme(true)
      else if (theme === 'light') applyTheme(false)
      initialized = true
    }).catch(() => {
      initialized = true
    })
  } else {
    initialized = true
  }

  return {
    isDark,
    toggleTheme,
    setTheme
  }
})
