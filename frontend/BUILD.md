# LuomiNest 打包指南

## 打包方式概览

LuomiNest 提供本地打包和云端打包两种方式：

| 方式 | 命令 | 输出产物 | 适用场景 |
|------|------|----------|----------|
| **本地一键打包** | `.\build-all.ps1` | 当前平台安装包 | 本地测试、快速验证 |
| **GitHub Actions** | 推送 `v*` 标签 | Win + Linux + macOS 全平台 | 正式发布 |
| **仅前端** | `pnpm run build:win` | NSIS + Portable | 前端调试 |
| **仅后端** | `cd backend && build.bat` | PyInstaller 可执行 | 后端调试 |

---

## 方式一：本地一键打包（推荐用于本地测试）

```powershell
# 在项目根目录执行
.\build-all.ps1
```

### 构建流程
```
[Step 1/5] Building backend with PyInstaller...
[Step 2/5] Verifying backend executable...
[Step 3/5] Building frontend with electron-vite...
[Step 4/5] Creating platform packages...
[Step 5/5] Summary
```

### 输出位置
- **Windows**: `frontend/release/dist/LuomiNest-Setup-0.8.0.exe` (NSIS 安装包)
- **Windows**: `frontend/release/dist/LuomiNest-Portable-0.8.0.exe` (便携版)
- **Linux**: `frontend/release/dist/LuomiNest-0.8.0-linux-x64.AppImage`
- **Linux**: `frontend/release/dist/LuomiNest-0.8.0-linux-x64.deb`
- **macOS**: `frontend/release/dist/LuomiNest-0.8.0-mac-arm64.dmg`

### 说明
- 本地打包只构建**当前平台**的包
- 跨平台构建请使用 GitHub Actions（见方式二）
- Windows 安装包由 electron-builder NSIS 直接产出（与 CI 同一条链路），
  Inno Setup 链路已移除（build/luominest.iss 已删除）
- 架构策略：各平台产物对应构建 runner 的原生架构（Win/Linux x64、macOS arm64），
  保证包内 PyInstaller 后端与 Electron 架构一致；后续需 arm64 Windows / Intel Mac 时再扩展矩阵
- macOS 产物当前未签名（无 Apple 开发者证书），首次打开需右键 → 打开

---

## 方式二：GitHub Actions 云端打包（推荐用于正式发布）

### 触发方式

```bash
# 1. 推送版本标签触发自动发布
git tag v0.8.0
git push origin v0.8.0

# 2. 或手动触发（仅构建不上传 Release）
gh workflow run release.yml
```

### 构建矩阵

| 平台 | Runner | 产物 |
|------|--------|------|
| Windows | `windows-latest` | NSIS 安装包 + 便携版 |
| Linux | `ubuntu-latest` | AppImage + deb |
| macOS | `macos-latest` | DMG + ZIP (arm64, 未签名) |

### 工作流特性
- pnpm 缓存（加速依赖安装）
- pip 缓存（加速 Python 依赖安装）
- 仅安装 `.[dev]` 依赖（不装重型 voice 依赖如 torch）
- 自动下载 TTS 模型（vits-melo-tts-zh_en ~162MB，extraResources 硬引用，不进 git）
- macOS 跳过签名探测（`CSC_IDENTITY_AUTO_DISCOVERY=false`，产出未签名包）
- electron-builder 统一 `--publish never`，Release 由 create-release job 统一创建
- 自动创建 GitHub Release（含变更日志）
- 预发布版本自动识别（tag 含 `-` 如 `v0.8.0-beta`）

### 配置文件
- 工作流: `.github/workflows/release.yml`
- 后端 spec: `backend/luominest-backend.spec`
- 前端构建: `frontend/package.json` 的 `build` 字段

---

## 方式三：单独构建前端

```bash
cd frontend

# Windows NSIS + 便携版
pnpm run build:win

# 仅 NSIS 安装包
pnpm run build:win-nsis

# 仅便携版
pnpm run build:win-portable

# Linux AppImage + deb + tar.gz
pnpm run build:linux

# macOS DMG + zip
pnpm run build:mac
```

### 镜像加速（国内用户）

`.npmrc` 已配置 npmmirror 镜像，无需手动设置。

---

## 方式四：单独构建后端

```bash
cd backend

# Windows
.\build.bat

# Linux/macOS
bash ./build.sh
```

### 输出
- `backend/dist/luominest-backend/luominest-backend.exe` (Windows)
- `backend/dist/luominest-backend/luominest-backend` (Linux/macOS)

### 说明
- 使用 PyInstaller COLLECT 模式（目录形式，非单文件）
- 仅打包核心依赖，voice 相关重型依赖（torch、faster-whisper、sherpa-onnx）不打包
- voice 依赖在运行时懒加载，缺失时优雅降级

---

## 打包产物详解

### Windows NSIS 安装包
- **文件名**: `LuomiNest-Setup-0.8.0.exe`
- **大小**: ~540MB（含 PyInstaller 后端与 TTS 模型，NSIS LZMA 压缩后）
- **说明**: FileDescription/ProductName 等可执行文件元数据均来自 package.json（name/description/build.productName），禁止出现 Electron 字样
- **特点**:
  - 自定义安装路径（assisted 安装向导，中英文界面）
  - 桌面快捷方式、开始菜单
  - 完整卸载支持（卸载保留用户数据）
  - 无需管理员权限（per-user 安装）

### Windows 便携版
- **文件名**: `LuomiNest-Portable-0.8.0.exe`
- **大小**: ~540MB
- **特点**: 单文件可执行，无需安装，解压即用

### Linux AppImage
- **文件名**: `LuomiNest-0.8.0-linux-x64.AppImage`
- **特点**: 免安装，chmod +x 后直接运行

### Linux deb
- **文件名**: `LuomiNest-0.8.0-linux-x64.deb`
- **特点**: Debian/Ubuntu 系包管理器安装

### macOS DMG
- **文件名**: `LuomiNest-0.8.0-mac-arm64.dmg`
- **特点**: Apple Silicon 原生，未签名（首次打开：右键 → 打开）

---

## 前置要求

### Windows
- Node.js 22+
- pnpm 10+
- Python 3.12+
- Visual C++ Build Tools（编译原生模块）

### Linux
- Node.js 22+
- pnpm 10+
- Python 3.12+
- `libarchive-tools rpm libxtst6 libnss3 libnotify4`（GitHub Actions 已自动安装）

### macOS
- Node.js 22+
- pnpm 10+
- Python 3.12+
- Xcode Command Line Tools

---

## CI 排障实录（2026-09-12 全链路首次跑通）

`release.yml` 首次全流程验证时踩过的坑，已全部修复并三平台跑通。改动 CI 时先对照此清单：

| # | 症状 | 根因 | 修复 |
|---|------|------|------|
| 1 | 三平台 `Setup pnpm` 全挂 | `pnpm/action-setup@v4` 不带 `version` 时只在**仓库根**找 `packageManager` 字段，本仓库声明在 `frontend/package.json` | 显式 `version: 10.34.5`（与 packageManager 一致） |
| 2 | Windows `Install backend dependencies` 挂，报 `To modify pip, please run ...` | venv 内 `pip.exe` 无法自替换（Windows 特有） | 统一 `python -m pip` |
| 3 | macOS `Build macOS packages` 挂，报 `Cannot read properties of null (reading 'channel')` | electron-builder 拿到 `GH_TOKEN` 就会生成自动更新元数据（updateInfo），项目未配置 publish/channel | `package.json` 的 `build.publish: null` + 打包步骤**不传** `GH_TOKEN` + `--publish never`；Release 统一由 `create-release` job 创建 |
| 4 | Linux `Build Linux packages` 挂，报 `Please specify project homepage` | deb 包元数据硬性要求 `homepage` | `package.json` 补 `homepage` 字段 |

其他注意：

- **TTS 模型**：`extraResources` 硬引用 `backend/models/tts/vits-melo-tts-zh_en`（~162MB，不进 git），CI 有专门的下载步骤——删掉它三平台打包全挂。
- **不要给打包步骤传 `GH_TOKEN`**：除非像 airi 那样配齐了 `publish: { provider: github, channel: ... }` 全套更新配置。
- **发布操作速查**：
  - master 上版本号变更并 push → 自动打 `v0.8.0-dev.N` **预发布**（detect job 对比 HEAD~1 版本号）
  - `git tag v0.8.0 && git push origin v0.8.0` → **正式 Release**（六件套产物自动上传）
  - 手动验证构建：Actions 页 Run workflow（workflow_dispatch），或 API dispatch
- **签名现状**：Windows 无代码签名证书（日志里 `signing with signtool.exe` 只是编辑 exe 元数据，不是真签名）；macOS 未签名未公证，`CSC_IDENTITY_AUTO_DISCOVERY=false`。拿到证书后在 `mac` 段配 `CSC_LINK`/公证即可。

---

## 常见问题

### 1. 后端构建失败：spec 文件未找到

**错误**: `luominest-backend.spec file not found`

**原因**: `.gitignore` 曾错误地忽略 `*.spec` 文件，已修复。

**解决**: 确认 `backend/luominest-backend.spec` 文件存在。

### 2. whisper-cpp-python 编译失败

**错误**: `Unable to invoke 'cpp'. Make sure its path was passed correctly`

**原因**: `whisper-cpp-python` 需要 C 预处理器，Windows 上没有。该依赖已从 `pyproject.toml` 移除（从未被 import 的死依赖）。

**解决**: 已修复，更新 `pyproject.toml` 后重新构建。

### 3. 后端可执行文件路径变化

PyInstaller 使用 COLLECT 模式（目录形式），输出路径从：
- `dist/luominest-backend.exe` → `dist/luominest-backend/luominest-backend.exe`

前端通过 `process.resourcesPath/backend/luominest-backend.exe` 定位，路径已对齐。

### 4. 下载速度慢

`.npmrc` 已配置 npmmirror 镜像。如需切换回官方源，编辑 `frontend/.npmrc`。

### 5. 文件被占用

```powershell
# 关闭残留进程
Stop-Process -Name "LuomiNest" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "electron" -Force -ErrorAction SilentlyContinue

# 清理 release 目录
Remove-Item -Recurse -Force frontend/release
```

---

## 项目结构

```
LuomiNest/
├── .github/workflows/
│   └── release.yml              # GitHub Actions 全平台打包
├── backend/
│   ├── luominest-backend.spec   # PyInstaller 打包配置（已入库）
│   ├── build.bat                # Windows 后端构建脚本
│   ├── build.sh                 # Linux/macOS 后端构建脚本
│   ├── pyproject.toml           # Python 依赖配置
│   └── main.py                  # 后端入口
├── frontend/
│   ├── package.json             # electron-builder 配置（NSIS/portable/AppImage/deb/dmg）
│   ├── build/
│   │   ├── entitlements.mac.plist  # macOS 权限配置
│   │   └── luominest.desktop    # Linux 桌面入口（参考）
│   ├── generate-icon.js         # 从 icon.svg 生成 icon.ico/png/icon.mac.png
│   └── resources/
│       ├── icon.ico / icon.png / icon.mac.png
│       └── backend/             # PyInstaller 输出（gitignore）
├── build-all.ps1                # 本地一键打包脚本
└── Makefile                     # Make 命令（可选）
```

---

*最后更新: 2026-09-12*
*适用于 LuomiNest v0.8.0+*
