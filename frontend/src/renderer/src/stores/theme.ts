import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

declare global {
  interface Window {
    api?: any
  }
}

export const useThemeStore = defineStore('theme', () => {
  const STORAGE_KEY = 'luominest-theme'

  const isDark = ref(getInitialTheme())

  const getApi = () => {
    return window.api?.config
  }

  function getInitialTheme(): boolean {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) return stored === 'dark'
    return window.matchMedia('(prefers-color-scheme: dark)').matches
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

  watch(isDark, (val) => {
    localStorage.setItem(STORAGE_KEY, val ? 'dark' : 'light')
    getApi()?.setTheme(val ? 'dark' : 'light').catch(() => {})
  }, { immediate: true })

  applyTheme(isDark.value)

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem(STORAGE_KEY)) {
      applyTheme(e.matches)
    }
  })

  getApi()?.getTheme().then((theme: string) => {
    if (theme === 'dark') applyTheme(true)
    else if (theme === 'light') applyTheme(false)
  }).catch(() => {})

  return {
    isDark,
    toggleTheme,
    setTheme
  }
})
