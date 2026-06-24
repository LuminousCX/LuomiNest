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
- **Windows**: `frontend/release/dist/LuomiNest-Setup-0.7.0.exe` (NSIS 安装包)
- **Windows**: `frontend/release/dist/LuomiNest-Portable-0.7.0.exe` (便携版)
- **Linux**: `frontend/release/dist/LuomiNest-0.7.0-linux-x64.AppImage`
- **Linux**: `frontend/release/dist/LuomiNest-0.7.0-linux-x64.deb`
- **macOS**: `frontend/release/dist/LuomiNest-0.7.0-mac-x64.dmg`

### 说明
- 本地打包只构建**当前平台**的包
- 跨平台构建请使用 GitHub Actions（见方式二）
- 不再使用 WSL 交叉编译（脆弱且慢）
- 不再使用 Inno Setup（与 electron-builder NSIS 重复）

---

## 方式二：GitHub Actions 云端打包（推荐用于正式发布）

### 触发方式

```bash
# 1. 推送版本标签触发自动发布
git tag v0.7.0
git push origin v0.7.0

# 2. 或手动触发（仅构建不上传 Release）
gh workflow run release.yml
```

### 构建矩阵

| 平台 | Runner | 产物 |
|------|--------|------|
| Windows | `windows-latest` | NSIS 安装包 + 便携版 |
| Linux | `ubuntu-latest` | AppImage + deb |
| macOS | `macos-latest` | DMG + ZIP |

### 工作流特性
- pnpm 缓存（加速依赖安装）
- pip 缓存（加速 Python 依赖安装）
- 仅安装 `.[dev]` 依赖（不装重型 voice 依赖如 torch）
- 自动创建 GitHub Release（含变更日志）
- 预发布版本自动识别（tag 含 `-` 如 `v0.7.0-beta`）

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
- **文件名**: `LuomiNest-Setup-0.7.0.exe`
- **大小**: ~120MB（含后端）
- **特点**:
  - 自定义安装路径
  - 桌面快捷方式、开始菜单、开机自启选项
  - 中英文双语
  - 完整卸载支持
  - 旧版本自动检测升级

### Windows 便携版
- **文件名**: `LuomiNest-Portable-0.7.0.exe`
- **大小**: ~120MB
- **特点**: 单文件可执行，无需安装，数据保存在程序同目录

### Linux AppImage
- **文件名**: `LuomiNest-0.7.0-linux-x64.AppImage`
- **特点**: 免安装，chmod +x 后直接运行

### Linux deb
- **文件名**: `LuomiNest-0.7.0-linux-x64.deb`
- **特点**: Debian/Ubuntu 系包管理器安装

### macOS DMG
- **文件名**: `LuomiNest-0.7.0-mac-x64.dmg`
- **特点**: 标准 macOS 安装镜像

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
│   ├── package.json             # electron-builder 配置
│   ├── build/
│   │   ├── nsis-extra.nsh       # NSIS 自定义脚本
│   │   ├── entitlements.mac.plist  # macOS 权限配置
│   │   └── luominest.desktop    # Linux 桌面入口
│   └── resources/
│       └── backend/             # PyInstaller 输出（gitignore）
├── build-all.ps1                # 本地一键打包脚本
└── Makefile                     # Make 命令（可选）
```

---

*最后更新: 2026-06-23*
*适用于 LuomiNest v0.7.0+*
