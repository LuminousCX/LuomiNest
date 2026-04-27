# LuomiNest 打包指南

## 📦 打包方式概览

LuomiNest 提供多种打包方式，满足不同场景需求：

| 方式 | 命令 | 输出产物 | 适用场景 |
|------|------|----------|----------|
| **Inno Setup安装包（推荐）** | `.\build-installer.ps1` | `LuomiNest-Setup-0.3.0.exe` | 正式发布、分发 |
| **electron-builder (NSIS)** | `pnpm run build:win-nsis` | `LuomiNest-Setup-0.3.0.exe` | 快速测试 |
| **electron-builder (全部)** | `pnpm run build:win` | NSIS + Portable | 完整构建 |
| **便携版** | `pnpm run build:win-portable` | `LuomiNest-Portable-0.3.0.exe` | U盘携带、绿色版 |
| **全平台构建** | `..\build-all.bat` / `..\build-all.ps1` | 全部格式 | CI/CD |

---

## 🎨 新特性：Ollama风格安装向导

### ✨ 安装向导改进（v2.0）

最新的安装程序采用 **Ollama风格极简设计**，提供现代化用户体验：

#### UI特点
- 🎨 **纯白背景 + 渐变效果** - 简洁清爽的视觉体验
- 🖼️ **右上角品牌图标** - 100x100px透明背景Logo
- 🔤 **Segoe UI字体系统** - Windows原生现代字体
- 🔵 **蓝色主题色 (#0078D4)** - 统一的按钮和进度条样式
- 📱 **大窗口尺寸 (700x500)** - 更好的内容展示空间

#### 智能快捷方式选项
安装过程中提供三个可选的快捷方式创建选项：

✅ **桌面快捷方式**
- 在桌面创建 LuomiNest 快捷方式
- 默认勾选，用户可取消
- 便于快速启动应用

✅ **Windows开始菜单**
- 在开始菜单创建程序组
- 包含：主程序、官网链接、许可协议、卸载程序
- 默认勾选，符合Windows用户习惯

✅ **开机自动启动**
- 登录时自动启动 LuomiNest
- 默认不勾选，避免资源占用
- 适合需要常驻后台的场景

#### 安装流程
```
欢迎页面 → 许可协议 → 安装模式选择 → 
目录选择 → 快捷方式设置 → 安装进度 → 完成页面
```

#### 多语言支持
- 🇨🇳 简体中文（默认）
- 🇺🇸 English
- 自动检测系统语言或允许用户选择

#### 智能权限处理
- 自动检测管理员权限状态
- 推荐最佳安装模式：
  - **管理员用户** → Program Files（所有用户）
  - **普通用户** → LocalAppData（当前用户）
- 支持权限提升请求

---

## 方式一：使用 Inno Setup 构建脚本（推荐用于正式发布）

**以管理员身份运行** PowerShell 或 CMD：

```powershell
# PowerShell (管理员)
cd frontend
.\build-installer.ps1
```

或

```cmd
# CMD (管理员)
cd frontend
build-installer.bat
```

### 输出位置
```
release/installer/LuomiNest-Setup-0.3.0.exe
```

### 特点
- ✅ Ollama风格精美UI
- ✅ 可选桌面/开始菜单/开机启动快捷方式
- ✅ 中英双语支持
- ✅ 完整卸载支持
- ✅ Windows注册表集成
- ✅ 旧版本自动检测与升级

### 前置要求
1. **Inno Setup 6** - 从 https://jrsoftware.org/isdl.php 下载安装
2. **Node.js 18+** 和 **pnpm**
3. **Python 3.10+** （后端构建）

---

## 方式二：使用 electron-builder 构建

### 1. 设置镜像加速（可选，国内用户推荐）

**PowerShell:**
```powershell
$env:ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
$env:ELECTRON_BUILDER_BINARIES_MIRROR="https://npmmirror.com/mirrors/electron-builder-binaries/"
```

**CMD:**
```cmd
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
set ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/
```

### 2. 执行打包命令

#### 仅NSIS安装包
```bash
pnpm run build:win-nsis
```
输出：`release/dist/LuomiNest-Setup-0.3.0.exe`

#### NSIS + 便携版（完整）
```bash
pnpm run build:win
```
输出：
- `release/dist/LuomiNest-Setup-0.3.0.exe` (~80MB)
- `release/dist/LuomiNest-Portable-0.3.0.exe` (~80MB)

#### 仅便携版
```bash
pnpm run build:win-portable
```

---

## 方式三：全局一键构建（前后端+打包）

### Windows (PowerShell)
```powershell
# 以管理员身份运行
.\build-all.ps1
```

### Windows (CMD)
```cmd
# 以管理员身份运行
build-all.bat
```

### Linux/Mac
```bash
chmod +x build-all.sh
./build-all.sh
```

### 构建步骤
```
[Step 1/6] Building backend with PyInstaller...
[Step 2/6] Verifying backend executable...
[Step 3/6] Creating distribution directory...
[Step 4/6] Copying backend to distribution and frontend resources...
[Step 5/6] Building frontend with electron-vite...
[Step 6/6] Creating installer packages...
```

---

## 📂 打包产物详解

### 1. Inno Setup 安装包（推荐）
- **文件名**: `LuomiNest-Setup-0.3.0.exe`
- **大小**: ~85MB（含后端）
- **位置**: `release/installer/` 或 `release/dist/`
- **特点**:
  - Ollama风格UI设计
  - 可自定义安装路径
  - 可选：桌面快捷方式、开始菜单、开机自启
  - 支持中英文界面
  - 完整的卸载程序
  - 注册到"应用和功能"
  - 支持旧版本升级

### 2. electron-builder NSIS 安装包
- **文件名**: `LuomiNest Setup 0.3.0.exe`
- **大小**: ~80MB
- **位置**: `release/dist/`
- **特点**:
  - 标准NSIS安装器
  - 自定义安装路径
  - 自动创建快捷方式
  - 支持卸载

### 3. 便携版 (Portable)
- **文件名**: `LuomiNest-Portable-0.3.0.exe`
- **大小**: ~80MB
- **位置**: `release/dist/`
- **特点**:
  - 单文件可执行，无需安装
  - 双击即用，零配置
  - 可放在U盘随身携带
  - 数据保存在程序同目录
  - 适合开发测试

---

## ⚙️ 高级配置选项

### Inno Setup 自定义配置

编辑 `installer.iss` 文件可调整：

```pascal
; 修改版本号
#define MyAppVersion "0.3.0"

; 修改安装模式默认值
InstallModePage.Values[0] := True  ; 所有用户（推荐）
InstallModePage.Values[1] := False ; 当前用户

; 修改快捷方式默认值
DesktopCheck.Checked := True    ; 桌面快捷方式
StartMenuCheck.Checked := True   ; 开始菜单
AutoLaunchCheck.Checked := False ; 开机自启
```

### electron-builder 配置

编辑 `package.json` 的 `build` 字段：

```json
{
  "nsis": {
    "oneClick": false,
    "perMachine": false,
    "allowToChangeInstallationDirectory": true,
    "createDesktopShortcut": true,
    "createStartMenuShortcut": true,
    "displayLanguageSelector": true,
    "unicode": true
  }
}
```

---

## ⚠️ 常见问题

### 1. Inno Setup 未找到

**错误信息**:
```
Inno Setup not found!
Please install Inno Setup 6 from: https://jrsoftware.org/isdl.php
```

**解决方案**:
1. 下载并安装 [Inno Setup 6](https://jrsoftware.org/isdl.php)
2. 重启终端
3. 重新运行构建脚本

### 2. 符号链接权限错误

**错误信息**:
```
ERROR: Cannot create symbolic link : 客户端没有所需的特权
```

**解决方案**:
- **方法1**: 以管理员身份运行 PowerShell/CMD
- **方法2**: 启用Windows开发者模式
  - 设置 → 更新和安全 → 开发者选项 → 开发者模式

### 3. 下载速度慢

**解决方案**: 使用国内镜像加速
```powershell
$env:ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
```

### 4. 后端构建失败

**检查项**:
1. Python 版本是否 >= 3.10
2. 是否激活了虚拟环境 `.venv`
3. PyInstaller是否正确安装
4. 查看 `luominest-backend.spec` 配置

**手动构建后端**:
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install pyinstaller
pip install -e ".[dev]"
pyinstaller luominest-backend.spec --clean --noconfirm
```

### 5. 文件被占用

**错误信息**:
```
The process cannot access the file because it is being used by another process
```

**解决方案**:
- 关闭所有可能占用文件的程序（VS Code、资源管理器等）
- 删除 `release` 目录后重新打包
- 检查是否有LuomiNest进程正在运行

### 6. 安装向导显示异常

**可能原因**:
- 图标文件缺失 (`resources/icon.ico`)
- 字体未安装（Segoe UI为系统自带）
- DPI缩放问题

**解决方案**:
1. 确保 `resources/icon.ico` 存在
2. 在高DPI显示器上测试
3. 使用兼容模式运行安装程序

---

## 🚀 快速启动指南

### 开发模式
```bash
cd frontend
pnpm run dev
```

### 仅构建前端（不打包）
```bash
cd frontend
pnpm run build
```

### 仅构建后端
```bash
cd backend
# Windows
.\build.bat
# Linux/Mac
./build.sh
```

### 类型检查
```bash
cd frontend
pnpm run typecheck
```

---

## 📝 其他打包命令

```bash
# macOS DMG + zip
pnpm run build:mac

# Linux AppImage + deb + tar.gz
pnpm run build:linux

# 同时打包32位和64位（Windows）
pnpm run build && electron-builder --win --x64 --ia32

# 静默安装参数
LuomiNest-Setup-0.3.0.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART

# 静默卸载
unins000.exe /VERYSILENT
```

---

## 💡 最佳实践建议

### 正式发布前检查清单
- [ ] 更新版本号（`package.json`, `installer.iss`）
- [ ] 测试安装/卸载流程
- [ ] 验证快捷方式功能正常
- [ ] 测试多语言切换
- [ ] 检查管理员/普通用户安装模式
- [ ] 测试旧版本升级
- [ ] 验证数字签名（如需要）
- [ ] 测试杀毒软件误报情况

### 性能优化建议
1. **首次打包**会下载Electron二进制文件（~137MB），请耐心等待
2. 下载缓存位置：`%LOCALAPPDATA%\electron-builder\Cache\`
3. 启用LZMA压缩减小安装包体积
4. 使用`.gitignore`排除不必要的文件

### 分发建议
- **正式发布**: 使用 Inno Setup 安装包（Ollama风格）
- **内部测试**: 使用 electron-builder NSIS 或便携版
- **CI/CD自动化**: 使用 `build-all.ps1` 一键构建
- **开源项目**: 同时提供安装包和便携版

---

## 🔐 代码签名（可选）

如果需要避免"未知发布者"警告，请配置代码签名：

### 购买证书
推荐证书颁发机构：
- DigiCode
- Sectigo
- GlobalSign

### 配置方法

**Inno Setup (installer.iss)**:
```pascal
[Setup]
SignedUninstaller=yes
SignTool=mysigntool $f
```

**electron-builder (package.json)**:
```json
{
  "build": {
    "win": {
      "certificateFile": "path/to/certificate.pfx",
      "certificatePassword": "your-password",
      "signAndEditExecutable": true,
      "requestedExecutionLevel": "asInvoker"
    }
  }
}
```

### 签名工具
```powershell
# 使用 signtool.exe (Windows SDK)
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com output.exe

# 使用 osslsigncode (跨平台)
osslsigncode sign -certs cert.pem -key key.pem -in input.exe -out signed.exe
```

---

## 📊 版本历史

### v2.0.0 (当前版本)
- ✨ 全新Ollama风格安装向导UI
- ✨ 可选桌面/开始菜单/开机启动快捷方式
- ✨ 中英双语支持
- ✨ 智能权限检测和处理
- ✨ 完整的Windows系统集成
- 🔧 优化安装包体积和性能

### v1.0.0
- 初始版本
- 基础NSIS安装包支持
- 便携版支持

---

## 🆘 技术支持

遇到问题？请检查：
1. 查看构建日志中的详细错误信息
2. 确保所有依赖已正确安装
3. 检查磁盘空间是否充足（建议 > 5GB）
4. 查看项目Issues或提交新Issue

**构建环境要求**:
- Windows 7 SP1+ / macOS 10.13+ / Ubuntu 18.04+
- Node.js 18+
- pnpm 8+
- Python 3.10+ (后端)
- Inno Setup 6 (可选，用于Inno Setup安装包)

---

*最后更新: 2026-04-23*
*适用于 LuomiNest v0.3.0+*
