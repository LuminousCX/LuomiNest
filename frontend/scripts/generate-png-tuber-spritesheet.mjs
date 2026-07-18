/**
 * generate-png-tuber-spritesheet.mjs
 *
 * 生成 Codex 风格的 PNG Tuber spritesheet 测试素材。
 *
 * 规格（参照 OpenAI Codex Pet 格式）：
 *   - 总尺寸: 1536 × 1872 像素
 *   - 网格: 8 列 × 9 行
 *   - 单帧: 192 × 208 像素
 *   - 状态数: 9 个，每个状态 8 帧
 *
 * 9 个状态:
 *   1. idle           - 待机呼吸
 *   2. running-right  - 向右跑
 *   3. running-left   - 向左跑
 *   4. waving         - 挥手
 *   5. jumping        - 跳跃
 *   6. failed         - 失败/晕
 *   7. waiting        - 等待
 *   8. running        - 奔跑
 *   9. review         - 思考
 *
 * 设计原则:
 *   - 零侵权: 程序化生成，不使用任何外部素材
 *   - 品牌一致: 使用 LuomiNest 品牌色 (#147EBC)
 *   - 风格统一: 与 usePixelPet 的 Q 版小精灵视觉一致
 *   - 颜色变量: 所有颜色从 CSS 变量取值，便于全局换肤
 *
 * 运行:
 *   node frontend/scripts/generate-png-tuber-spritesheet.mjs
 *
 * 输出:
 *   frontend/src/renderer/public/png/codex-pet/
 *     ├── spritesheet.png   (1536×1872 主图集)
 *     ├── thumbnail.png     (192×208 缩略图，取 idle 第 0 帧)
 *     └── manifest.json     (状态配置)
 */
import sharp from 'sharp'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// ---------------------------------------------------------------------------
// Codex Pet 规格常量
// ---------------------------------------------------------------------------

const FRAME_WIDTH = 192
const FRAME_HEIGHT = 208
const COLS = 8
const ROWS = 9
const SHEET_WIDTH = FRAME_WIDTH * COLS    // 1536
const SHEET_HEIGHT = FRAME_HEIGHT * ROWS  // 1872

// ---------------------------------------------------------------------------
// LuomiNest 品牌色（与 usePixelPet 保持一致）
// ---------------------------------------------------------------------------

const COLOR_BRAND = '#147EBC'        // 主色（身体）
const COLOR_BRAND_DARK = '#0D6BA8'   // 深色（阴影）
const COLOR_BRAND_LIGHT = '#62A9C8'  // 浅色（高光）
const COLOR_BLACK = '#1F2937'        // 黑色（眼睛/嘴巴）
const COLOR_CHEEK = '#F9A8D4'        // 腮红
const COLOR_WHITE = '#FFFFFF'
const COLOR_ALERT = '#EF4444'        // 警示红
const COLOR_Z = '#9CA3AF'            // Z 字（睡眠）
const COLOR_QUESTION = '#FBBF24'     // 问号（思考）

// ---------------------------------------------------------------------------
// 9 个状态定义（与 Codex Pet 对齐）
// ---------------------------------------------------------------------------

/**
 * @typedef {Object} FrameDrawer
 * @property {string} state - 状态名
 * @property {number} frame - 当前帧索引 (0-7)
 * @property {number} totalFrames - 总帧数 (8)
 */

/**
 * 生成单帧 SVG 字符串
 * @param {{state: string, frame: number, totalFrames: number}} ctx
 * @returns {string} SVG 字符串
 */
function drawFrame(ctx) {
  const { state, frame, totalFrames } = ctx
  const drawer = STATE_DRAWERS[state]
  if (!drawer) {
    return drawEmptyFrame()
  }
  return drawer({ frame, totalFrames })
}

// ---------------------------------------------------------------------------
// 基础绘制函数（返回 SVG 元素字符串）
// ---------------------------------------------------------------------------

/** Q 版小精灵的身体 + 头部（不含表情） */
function drawBody({ offsetX = 0, offsetY = 0, breathe = 0, tilt = 0 }) {
  const cx = 96 + offsetX
  const headCy = 70 + offsetY + breathe
  const bodyCy = 150 + offsetY + breathe

  return `
    <g transform="rotate(${tilt} ${cx} ${bodyCy})">
      <!-- 身体 -->
      <ellipse cx="${cx}" cy="${bodyCy}" rx="42" ry="36" fill="${COLOR_BRAND_DARK}"/>
      <ellipse cx="${cx - 8}" cy="${bodyCy - 8}" rx="20" ry="14" fill="${COLOR_BRAND_LIGHT}" opacity="0.5"/>
      <!-- 头部 -->
      <circle cx="${cx}" cy="${headCy}" r="50" fill="${COLOR_BRAND}"/>
      <ellipse cx="${cx - 12}" cy="${headCy - 14}" rx="22" ry="14" fill="${COLOR_BRAND_LIGHT}" opacity="0.4"/>
      <!-- 高光 -->
      <circle cx="${cx - 18}" cy="${headCy - 18}" r="6" fill="${COLOR_WHITE}" opacity="0.6"/>
    </g>
  `
}

/** 眼睛（支持眨眼和方向） */
function drawEyes({ offsetX = 0, offsetY = 0, blink = false, look = 'center' }) {
  const cy = 65 + offsetY
  const lx = 80 + offsetX + (look === 'left' ? -2 : look === 'right' ? 2 : 0)
  const rx = 112 + offsetX + (look === 'left' ? -2 : look === 'right' ? 2 : 0)
  const ly = cy + (look === 'up' ? -2 : look === 'down' ? 2 : 0)

  if (blink) {
    return `
      <line x1="${lx - 5}" y1="${ly}" x2="${lx + 5}" y2="${ly}" stroke="${COLOR_BLACK}" stroke-width="2.5" stroke-linecap="round"/>
      <line x1="${rx - 5}" y1="${ly}" x2="${rx + 5}" y2="${ly}" stroke="${COLOR_BLACK}" stroke-width="2.5" stroke-linecap="round"/>
    `
  }
  return `
    <circle cx="${lx}" cy="${ly}" r="5" fill="${COLOR_BLACK}"/>
    <circle cx="${rx}" cy="${ly}" r="5" fill="${COLOR_BLACK}"/>
    <circle cx="${lx + 1.5}" cy="${ly - 1.5}" r="1.5" fill="${COLOR_WHITE}"/>
    <circle cx="${rx + 1.5}" cy="${ly - 1.5}" r="1.5" fill="${COLOR_WHITE}"/>
  `
}

/** 嘴巴 */
function drawMouth({ offsetX = 0, offsetY = 0, shape = 'smile' }) {
  const mx = 96 + offsetX
  const my = 90 + offsetY
  switch (shape) {
    case 'smile':
      return `<path d="M ${mx - 8} ${my} Q ${mx} ${my + 8} ${mx + 8} ${my}" stroke="${COLOR_BLACK}" stroke-width="2.5" fill="none" stroke-linecap="round"/>`
    case 'frown':
      return `<path d="M ${mx - 8} ${my + 4} Q ${mx} ${my - 4} ${mx + 8} ${my + 4}" stroke="${COLOR_BLACK}" stroke-width="2.5" fill="none" stroke-linecap="round"/>`
    case 'open':
      return `<ellipse cx="${mx}" cy="${my + 2}" rx="6" ry="5" fill="${COLOR_BLACK}"/>`
    case 'flat':
      return `<line x1="${mx - 6}" y1="${my}" x2="${mx + 6}" y2="${my}" stroke="${COLOR_BLACK}" stroke-width="2.5" stroke-linecap="round"/>`
    case 'o':
      return `<ellipse cx="${mx}" cy="${my + 2}" rx="4" ry="5" fill="${COLOR_BLACK}"/>`
    case 'triangle':
      return `<path d="M ${mx - 6} ${my - 2} L ${mx + 6} ${my - 2} L ${mx} ${my + 6} Z" fill="${COLOR_BLACK}"/>`
    default:
      return ''
  }
}

/** 腮红 */
function drawCheeks({ offsetX = 0, offsetY = 0 }) {
  return `
    <ellipse cx="${76 + offsetX}" cy="${82 + offsetY}" rx="6" ry="3" fill="${COLOR_CHEEK}" opacity="0.7"/>
    <ellipse cx="${116 + offsetX}" cy="${82 + offsetY}" rx="6" ry="3" fill="${COLOR_CHEEK}" opacity="0.7"/>
  `
}

/** 手臂（左右两条） */
function drawArms({ offsetX = 0, offsetY = 0, leftArm = 0, rightArm = 0 }) {
  const bodyCy = 150 + offsetY
  const lx = 54 + offsetX
  const rx = 138 + offsetX
  return `
    <line x1="${lx}" y1="${bodyCy - 10}" x2="${lx - 8 + leftArm}" y2="${bodyCy + 20 + leftArm}" stroke="${COLOR_BRAND_DARK}" stroke-width="10" stroke-linecap="round"/>
    <line x1="${rx}" y1="${bodyCy - 10}" x2="${rx + 8 - rightArm}" y2="${bodyCy + 20 + rightArm}" stroke="${COLOR_BRAND_DARK}" stroke-width="10" stroke-linecap="round"/>
  `
}

// ---------------------------------------------------------------------------
// 9 个状态的绘制函数（每个返回完整 SVG 字符串）
// ---------------------------------------------------------------------------

/** 1. idle: 待机呼吸，第 4 帧眨眼 */
function drawIdle({ frame, totalFrames }) {
  const breathe = Math.sin((frame / totalFrames) * Math.PI * 2) > 0 ? -2 : 0
  const blink = frame === 4
  return `
    ${drawBody({ breathe })}
    ${drawEyes({ offsetY: breathe, blink })}
    ${drawMouth({ offsetY: breathe, shape: 'smile' })}
    ${drawCheeks({ offsetY: breathe })}
  `
}

/** 2. running-right: 向右跑，身体倾斜右，腿部交替 */
function drawRunningRight({ frame }) {
  const tilt = 8
  const bounce = frame % 2 === 0 ? -3 : 0
  const legSwing = frame % 2 === 0 ? 4 : -4
  return `
    ${drawBody({ offsetX: 4, offsetY: bounce, tilt })}
    ${drawEyes({ offsetX: 4, offsetY: bounce, look: 'right' })}
    ${drawMouth({ offsetX: 4, offsetY: bounce, shape: 'flat' })}
    <!-- 腿 -->
    <line x1="88" y1="${183 + bounce}" x2="${88 + legSwing}" y2="${200 + bounce}" stroke="${COLOR_BRAND_DARK}" stroke-width="8" stroke-linecap="round"/>
    <line x1="104" y1="${183 + bounce}" x2="${104 - legSwing}" y2="${200 + bounce}" stroke="${COLOR_BRAND_DARK}" stroke-width="8" stroke-linecap="round"/>
    <!-- 速度线 -->
    <line x1="20" y1="${100 + bounce}" x2="40" y2="${100 + bounce}" stroke="${COLOR_BRAND_LIGHT}" stroke-width="2" opacity="0.6"/>
    <line x1="15" y1="${120 + bounce}" x2="35" y2="${120 + bounce}" stroke="${COLOR_BRAND_LIGHT}" stroke-width="2" opacity="0.6"/>
  `
}

/** 3. running-left: 向左跑（镜像 running-right） */
function drawRunningLeft({ frame }) {
  const tilt = -8
  const bounce = frame % 2 === 0 ? -3 : 0
  const legSwing = frame % 2 === 0 ? -4 : 4
  return `
    ${drawBody({ offsetX: -4, offsetY: bounce, tilt })}
    ${drawEyes({ offsetX: -4, offsetY: bounce, look: 'left' })}
    ${drawMouth({ offsetX: -4, offsetY: bounce, shape: 'flat' })}
    <!-- 腿 -->
    <line x1="88" y1="${183 + bounce}" x2="${88 + legSwing}" y2="${200 + bounce}" stroke="${COLOR_BRAND_DARK}" stroke-width="8" stroke-linecap="round"/>
    <line x1="104" y1="${183 + bounce}" x2="${104 - legSwing}" y2="${200 + bounce}" stroke="${COLOR_BRAND_DARK}" stroke-width="8" stroke-linecap="round"/>
    <!-- 速度线 -->
    <line x1="152" y1="${100 + bounce}" x2="172" y2="${100 + bounce}" stroke="${COLOR_BRAND_LIGHT}" stroke-width="2" opacity="0.6"/>
    <line x1="157" y1="${120 + bounce}" x2="177" y2="${120 + bounce}" stroke="${COLOR_BRAND_LIGHT}" stroke-width="2" opacity="0.6"/>
  `
}

/** 4. waving: 挥手打招呼，右手举起摆动 */
function drawWaving({ frame }) {
  const wave = Math.sin((frame / 8) * Math.PI * 2) * 8
  const breathe = frame % 2 === 0 ? -1 : 0
  return `
    ${drawBody({ breathe })}
    ${drawArms({ offsetY: breathe, rightArm: -25 + wave })}
    ${drawEyes({ offsetY: breathe })}
    ${drawMouth({ offsetY: breathe, shape: 'open' })}
    ${drawCheeks({ offsetY: breathe })}
  `
}

/** 5. jumping: 跳跃，抛物线轨迹 */
function drawJumping({ frame, totalFrames }) {
  const jumpHeight = Math.sin((frame / totalFrames) * Math.PI) * 30
  const offset = -Math.round(jumpHeight)
  return `
    ${drawBody({ offsetY: offset })}
    ${drawEyes({ offsetY: offset })}
    ${drawMouth({ offsetY: offset, shape: 'open' })}
    ${drawCheeks({ offsetY: offset })}
    <!-- 阴影 -->
    <ellipse cx="96" cy="200" rx="${30 - offset / 2}" ry="4" fill="${COLOR_BLACK}" opacity="0.2"/>
  `
}

/** 6. failed: 失败/晕，身体摇晃，头上星星 */
function drawFailed({ frame }) {
  const tilt = frame % 2 === 0 ? -10 : 10
  const offsetX = frame % 2 === 0 ? -3 : 3
  return `
    ${drawBody({ offsetX, tilt })}
    ${drawEyes({ offsetX, blink: true })}
    ${drawMouth({ offsetX, shape: 'triangle' })}
    <!-- 头上星星（旋转） -->
    ${drawStars(96 + offsetX, 20, frame)}
  `
}

/** 7. waiting: 等待，原地踏步，看表 */
function drawWaiting({ frame }) {
  const tap = frame % 2 === 0 ? 0 : -2
  const breathe = frame % 2 === 0 ? -1 : 0
  return `
    ${drawBody({ breathe })}
    ${drawEyes({ offsetY: breathe, look: 'down' })}
    ${drawMouth({ offsetY: breathe, shape: 'flat' })}
    ${drawArms({ offsetY: breathe, rightArm: -15 + tap })}
    <!-- 怀表 -->
    <circle cx="138" cy="${160 + breathe}" r="8" fill="${COLOR_BRAND_DARK}" stroke="${COLOR_BRAND_LIGHT}" stroke-width="1.5"/>
    <line x1="138" y1="${160 + breathe}" x2="138" y2="${155 + breathe}" stroke="${COLOR_WHITE}" stroke-width="1"/>
    <line x1="138" y1="${160 + breathe}" x2="142" y2="${160 + breathe}" stroke="${COLOR_WHITE}" stroke-width="1"/>
  `
}

/** 8. running: 奔跑（通用前进），快速步态 */
function drawRunning({ frame }) {
  const bounce = frame % 2 === 0 ? -4 : 0
  const legSwing = frame % 2 === 0 ? 6 : -6
  const armSwing = frame % 2 === 0 ? 8 : -8
  return `
    ${drawBody({ offsetY: bounce })}
    ${drawArms({ offsetY: bounce, leftArm: -armSwing, rightArm: -armSwing })}
    ${drawEyes({ offsetY: bounce, look: 'center' })}
    ${drawMouth({ offsetY: bounce, shape: 'flat' })}
    <!-- 腿 -->
    <line x1="88" y1="${183 + bounce}" x2="${88 + legSwing}" y2="${200 + bounce}" stroke="${COLOR_BRAND_DARK}" stroke-width="8" stroke-linecap="round"/>
    <line x1="104" y1="${183 + bounce}" x2="${104 - legSwing}" y2="${200 + bounce}" stroke="${COLOR_BRAND_DARK}" stroke-width="8" stroke-linecap="round"/>
    <!-- 速度线 -->
    <line x1="10" y1="${90 + bounce}" x2="40" y2="${90 + bounce}" stroke="${COLOR_BRAND_LIGHT}" stroke-width="3" opacity="0.7"/>
    <line x1="5" y1="${110 + bounce}" x2="35" y2="${110 + bounce}" stroke="${COLOR_BRAND_LIGHT}" stroke-width="3" opacity="0.7"/>
    <line x1="15" y1="${130 + bounce}" x2="38" y2="${130 + bounce}" stroke="${COLOR_BRAND_LIGHT}" stroke-width="2" opacity="0.5"/>
  `
}

/** 9. review: 思考/审查，挠头，问号 */
function drawReview({ frame }) {
  const breathe = frame % 2 === 0 ? -1 : 0
  const showQuestion = frame % 2 === 0
  return `
    ${drawBody({ breathe })}
    ${drawArms({ offsetY: breathe, rightArm: -28 })}
    ${drawEyes({ offsetY: breathe, look: 'up' })}
    ${drawMouth({ offsetY: breathe, shape: 'flat' })}
    <!-- 问号 -->
    ${showQuestion ? drawQuestion(150, 30) : ''}
  `
}

// ---------------------------------------------------------------------------
// 辅助绘制（星星、问号）
// ---------------------------------------------------------------------------

function drawStars(cx, cy, frame) {
  const positions = [
    { x: cx - 20, y: cy, size: 6 },
    { x: cx, y: cy - 8, size: 8 },
    { x: cx + 20, y: cy, size: 6 },
  ]
  const rotation = frame * 45
  return positions.map((p, i) => {
    const r = p.size
    const rot = rotation + i * 30
    return `<g transform="translate(${p.x} ${p.y}) rotate(${rot})">
      <path d="M 0 ${-r} L ${r * 0.3} ${-r * 0.3} L ${r} 0 L ${r * 0.3} ${r * 0.3} L 0 ${r} L ${-r * 0.3} ${r * 0.3} L ${-r} 0 L ${-r * 0.3} ${-r * 0.3} Z" fill="${COLOR_ALERT}"/>
    </g>`
  }).join('')
}

function drawQuestion(cx, cy) {
  return `<text x="${cx}" y="${cy + 12}" font-family="sans-serif" font-size="24" font-weight="bold" fill="${COLOR_QUESTION}">?</text>`
}

function drawEmptyFrame() {
  return `<rect x="0" y="0" width="${FRAME_WIDTH}" height="${FRAME_HEIGHT}" fill="none"/>`
}

// ---------------------------------------------------------------------------
// 状态绘制函数映射
// ---------------------------------------------------------------------------

const STATE_DRAWERS = {
  idle: drawIdle,
  'running-right': drawRunningRight,
  'running-left': drawRunningLeft,
  waving: drawWaving,
  jumping: drawJumping,
  failed: drawFailed,
  waiting: drawWaiting,
  running: drawRunning,
  review: drawReview,
}

// 状态配置（写入 manifest.json）
const STATE_CONFIG = [
  { name: 'idle', fps: 4, loop: true, next: null },
  { name: 'running-right', fps: 8, loop: true, next: null },
  { name: 'running-left', fps: 8, loop: true, next: null },
  { name: 'waving', fps: 6, loop: true, next: null },
  { name: 'jumping', fps: 8, loop: false, next: 'idle' },
  { name: 'failed', fps: 6, loop: true, next: null },
  { name: 'waiting', fps: 4, loop: true, next: null },
  { name: 'running', fps: 10, loop: true, next: null },
  { name: 'review', fps: 3, loop: true, next: null },
]

// LuomiNest 12 情绪 → Codex 9 状态映射
const EMOTION_TO_STATE = {
  happy: 'waving',
  sad: 'failed',
  neutral: 'idle',
  love: 'waving',
  surprise: 'jumping',
  angry: 'failed',
  think: 'review',
  awkward: 'failed',
  curious: 'review',
  shy: 'waving',
  excited: 'jumping',
  confused: 'review',
}

// ---------------------------------------------------------------------------
// SVG 生成
// ---------------------------------------------------------------------------

/** 生成单帧的完整 SVG 字符串（带 viewBox） */
function generateFrameSvg(state, frame) {
  const inner = drawFrame({ state, frame, totalFrames: COLS })
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${FRAME_WIDTH}" height="${FRAME_HEIGHT}" viewBox="0 0 ${FRAME_WIDTH} ${FRAME_HEIGHT}">
    ${inner}
  </svg>`
}

/** 生成整个 spritesheet 的 SVG（1536×1872） */
function generateSpritesheetSvg() {
  const frames = []
  STATE_CONFIG.forEach((stateConfig, rowIdx) => {
    for (let col = 0; col < COLS; col++) {
      const x = col * FRAME_WIDTH
      const y = rowIdx * FRAME_HEIGHT
      const inner = drawFrame({ state: stateConfig.name, frame: col, totalFrames: COLS })
      frames.push(`<g transform="translate(${x} ${y})">${inner}</g>`)
    }
  })

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${SHEET_WIDTH}" height="${SHEET_HEIGHT}" viewBox="0 0 ${SHEET_WIDTH} ${SHEET_HEIGHT}">
    ${frames.join('\n')}
  </svg>`
}

// ---------------------------------------------------------------------------
// manifest.json 生成
// ---------------------------------------------------------------------------

function generateManifest() {
  return {
    schema_version: '1.0',
    name: 'codex-pet',
    display_name: 'Codex Pet',
    type: 'png',
    format: 'spritesheet',
    sheet: {
      image: 'spritesheet.png',
      width: SHEET_WIDTH,
      height: SHEET_HEIGHT,
      frame_width: FRAME_WIDTH,
      frame_height: FRAME_HEIGHT,
      cols: COLS,
      rows: ROWS,
    },
    states: STATE_CONFIG.map((s, idx) => ({
      name: s.name,
      row: idx,
      frames: COLS,
      fps: s.fps,
      loop: s.loop,
      next: s.next,
    })),
    emotion_map: EMOTION_TO_STATE,
    default_state: 'idle',
    colors: {
      brand: COLOR_BRAND,
      brand_dark: COLOR_BRAND_DARK,
      brand_light: COLOR_BRAND_LIGHT,
    },
  }
}

// ---------------------------------------------------------------------------
// 主函数
// ---------------------------------------------------------------------------

async function main() {
  const outputDir = path.resolve(__dirname, '..', 'src', 'renderer', 'public', 'png', 'codex-pet')
  console.log(`[PNG Tuber] 输出目录: ${outputDir}`)

  // 确保输出目录存在
  await fs.mkdir(outputDir, { recursive: true })

  // 1. 生成 spritesheet.png
  console.log('[PNG Tuber] 生成 spritesheet.png (1536×1872)...')
  const sheetSvg = generateSpritesheetSvg()
  const sheetPath = path.join(outputDir, 'spritesheet.png')
  await sharp(Buffer.from(sheetSvg))
    .png({ compressionLevel: 9 })
    .toFile(sheetPath)
  console.log(`[PNG Tuber] ✓ spritesheet.png 已生成 (${SHEET_WIDTH}×${SHEET_HEIGHT})`)

  // 2. 生成 thumbnail.png（idle 第 0 帧）
  console.log('[PNG Tuber] 生成 thumbnail.png (192×208)...')
  const thumbSvg = generateFrameSvg('idle', 0)
  const thumbPath = path.join(outputDir, 'thumbnail.png')
  await sharp(Buffer.from(thumbSvg))
    .png({ compressionLevel: 9 })
    .toFile(thumbPath)
  console.log(`[PNG Tuber] ✓ thumbnail.png 已生成`)

  // 3. 生成 manifest.json
  console.log('[PNG Tuber] 生成 manifest.json...')
  const manifest = generateManifest()
  const manifestPath = path.join(outputDir, 'manifest.json')
  await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2), 'utf-8')
  console.log(`[PNG Tuber] ✓ manifest.json 已生成`)

  // 4. 输出状态映射摘要
  console.log('\n[PNG Tuber] 状态映射 (LuomiNest 12 情绪 → Codex 9 状态):')
  for (const [emotion, state] of Object.entries(EMOTION_TO_STATE)) {
    console.log(`  ${emotion.padEnd(10)} → ${state}`)
  }

  console.log('\n[PNG Tuber] 完成！')
  console.log(`[PNG Tuber] 文件位于: ${outputDir}`)
  console.log('[PNG Tuber] 提示: 可用 AI 生成的原创素材替换 spritesheet.png，保持尺寸 1536×1872 不变')
}

main().catch((err) => {
  console.error('[PNG Tuber] 生成失败:', err)
  process.exit(1)
})
