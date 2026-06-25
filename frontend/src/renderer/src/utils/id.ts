export const generateId = (prefix = ''): string => {
  const base = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  return prefix ? `${prefix}-${base}` : base
}
