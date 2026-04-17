import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const STORAGE_KEY = 'luominest-theme'

  const isDark = ref(getInitialTheme())

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
  }, { immediate: true })

  applyTheme(isDark.value)

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem(STORAGE_KEY)) {
      applyTheme(e.matches)
    }
  })

  return {
    isDark,
    toggleTheme,
    setTheme
  }
})
