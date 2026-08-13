// 默认范例皮肤背景图转换脚本：将源图片压缩为 webp 并输出到 public/themes/backgrounds/
// 用法: node scripts/convert-default-theme-bg.mjs <源图片路径> [输出文件名]
// 示例: node scripts/convert-default-theme-bg.mjs "E:\wallhaven\wallhaven-qz9ykr_1920x1080.png" wallhaven-qz9ykr.webp
// 使用项目内已有的 sharp 依赖，避免引入新依赖。
import { writeFileSync, existsSync, mkdirSync } from 'fs'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'
import sharp from 'sharp'

const __dirname = dirname(fileURLToPath(import.meta.url))

const SRC = process.argv[2]
const OUT_NAME = process.argv[3] ?? 'wallhaven-qz9ykr.webp'
const OUT = resolve(__dirname, '../src/renderer/public/themes/backgrounds', OUT_NAME)

async function main() {
  if (!SRC) {
    console.error('用法: node scripts/convert-default-theme-bg.mjs <源图片路径> [输出文件名]')
    process.exit(1)
  }
  if (!existsSync(SRC)) {
    console.error(`源文件不存在: ${SRC}`)
    process.exit(1)
  }
  mkdirSync(dirname(OUT), { recursive: true })

  const image = sharp(SRC)
  const metadata = await image.metadata()

  // 限制最长边 1920，保证作为背景足够清晰且体积可控
  const maxDim = 1920
  const longest = Math.max(metadata.width ?? 0, metadata.height ?? 0)
  const pipeline = longest > maxDim ? image.resize({ width: maxDim, height: maxDim, fit: 'inside', withoutEnlargement: true }) : image

  const buf = await pipeline
    .webp({ quality: 82, effort: 4 })
    .toBuffer()

  writeFileSync(OUT, buf)
  console.log(`OK: ${OUT}`)
  console.log(`  源: ${(metadata.width ?? 0)}x${(metadata.height ?? 0)}`)
  console.log(`  输出: ${Math.round(buf.length / 1024)} KB`)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
