export const LUOMINEST_AGENT_PALETTE = [
  '#147EBC',
  '#6366f1',
  '#f59e0b',
  '#f43f5e',
  '#8b5cf6',
  '#06b6d4',
  '#84cc16',
  '#ec4899'
] as const

export const LUOMINEST_AGENT_PALETTE_CSS = [
  'var(--lumi-primary)',
  'var(--lumi-indigo)',
  'var(--lumi-amber)',
  'var(--lumi-accent)',
  'var(--task-purple)',
  'var(--lumi-sky)',
  'var(--lumi-emerald)',
  'var(--task-pink)'
] as const

export const LUOMINEST_MEMORY_SPACE_COLORS = [
  { id: 'user-space', color: '#8b5cf6', cssVar: 'var(--task-purple)' },
  { id: 'agent-memory', color: '#0ea5e9', cssVar: 'var(--lumi-sky)' },
  { id: 'thread-memory', color: '#f59e0b', cssVar: 'var(--lumi-amber)' }
] as const

export const LUOMINEST_EMOTION_COLORS = [
  { id: 'happy', color: '#f59e0b', cssVar: 'var(--lumi-amber)' },
  { id: 'sad', color: '#6366f1', cssVar: 'var(--lumi-indigo)' },
  { id: 'neutral', color: '#8b5cf6', cssVar: 'var(--task-purple)' },
  { id: 'love', color: '#ec4899', cssVar: 'var(--task-pink)' },
  { id: 'surprise', color: '#22c55e', cssVar: 'var(--lumi-success)' }
] as const

export const LUOMINEST_TIER_COLORS = [
  { tier: 'critical', color: '#8b5cf6', cssVar: 'var(--task-purple)' },
  { tier: 'important', color: '#22c55e', cssVar: 'var(--lumi-success)' },
  { tier: 'normal', color: '#f59e0b', cssVar: 'var(--lumi-amber)' }
] as const

export const LUOMINEST_WORKFLOW_COLORS = {
  agent: '#147EBC',
  tool: '#6366f1',
  condition: '#f59e0b',
  output: '#22c55e',
  trigger: '#f43f5e'
} as const

export const LUOMINEST_WORKFLOW_COLORS_CSS = {
  agent: 'var(--lumi-primary)',
  tool: 'var(--lumi-indigo)',
  condition: 'var(--lumi-amber)',
  output: 'var(--lumi-success)',
  trigger: 'var(--lumi-accent)'
} as const
