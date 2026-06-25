export const getItem = <T>(key: string, defaultValue: T): T => {
  try {
    const raw = localStorage.getItem(key)
    if (raw === null) return defaultValue
    return JSON.parse(raw) as T
  } catch {
    return defaultValue
  }
}

export const setItem = <T>(key: string, value: T): void => {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // ignore storage errors
  }
}

export const getStringItem = (key: string, defaultValue: string): string => {
  try {
    return localStorage.getItem(key) ?? defaultValue
  } catch {
    return defaultValue
  }
}

export const setStringItem = (key: string, value: string): void => {
  try {
    localStorage.setItem(key, value)
  } catch {
    // ignore storage errors
  }
}

export const removeItem = (key: string): void => {
  try {
    localStorage.removeItem(key)
  } catch {
    // ignore storage errors
  }
}
