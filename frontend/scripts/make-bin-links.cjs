#!/usr/bin/env node
/**
 * 在网络共享路径上重建 node_modules/.bin 垫片。
 *
 * 背景：pnpm 的 bin 链接器在映射盘/UNC 路径下会把逻辑路径与 realpath 出的
 * UNC 路径错误拼接（如 D:\192.168.31.140\... 或双重 \\ip\Data 前缀），
 * 导致 .bin 垫片全部创建失败。因此本机（项目挂载为网络盘的环境）在
 * 用户级配置 bin-links=false，改由本脚本按 hoisted 平铺布局直接读取
 * 各包 package.json 的 bin 字段生成本地垫片。
 *
 * 用法：node scripts/make-bin-links.cjs（在 frontend 目录下、安装依赖后执行一次）
 * 幂等：可重复运行；bin 目标不存在的（如 @types/node 的占位 bin）自动跳过。
 */
const fs = require('fs')
const path = require('path')

const nm = path.join(process.cwd(), 'node_modules')
const binDir = path.join(nm, '.bin')
fs.mkdirSync(binDir, { recursive: true })

const nodeExe = process.execPath
const nodeExeSh = nodeExe.split('\\').join('/')
let created = 0
let skipped = 0

const packages = []
for (const entry of fs.readdirSync(nm, { withFileTypes: true })) {
  if (!entry.isDirectory() || entry.name.startsWith('.')) continue
  if (entry.name.startsWith('@')) {
    for (const sub of fs.readdirSync(path.join(nm, entry.name), { withFileTypes: true })) {
      if (sub.isDirectory()) packages.push(`${entry.name}/${sub.name}`)
    }
  } else {
    packages.push(entry.name)
  }
}

for (const pkg of packages) {
  let pkgJson
  try {
    pkgJson = JSON.parse(fs.readFileSync(path.join(nm, pkg, 'package.json'), 'utf8'))
  } catch {
    continue
  }
  if (!pkgJson.bin) continue
  const bins =
    typeof pkgJson.bin === 'string'
      ? { [pkgJson.name.split('/').pop()]: pkgJson.bin }
      : pkgJson.bin
  for (const [name, rel] of Object.entries(bins)) {
    const target = path.join(nm, pkg, rel)
    if (!fs.existsSync(target)) {
      skipped++
      continue
    }
    const targetSh = target.split('\\').join('/')
    fs.writeFileSync(path.join(binDir, `${name}.cmd`), `@ECHO off\r\n"${nodeExe}" "${target}" %*\r\n`)
    fs.writeFileSync(path.join(binDir, name), `#!/bin/sh\n"${nodeExeSh}" "${targetSh}" "$@"\n`)
    created++
  }
}

console.log(`bin shims: ${created} created, ${skipped} skipped (bin target missing)`)
