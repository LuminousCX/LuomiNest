# LuomiNest 打包指南

## 📦 打包方式

### 方式一：使用打包脚本（推荐）

**以管理员身份运行** PowerShell 或 CMD：

```powershell
# PowerShell (管理员)
.\build.bat
```

或

```cmd
# CMD (管理员)
.\build.bat
```

---

### 方式二：手动打包

#### 1. 设置镜像加速（可选，国内用户推荐）

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

#### 2. 执行打包命令

```bash
npm run build:win
```

---

## 📂 打包产物

打包完成后，在 `release/dist/` 目录下会生成：

### 1. NSIS 安装包
- **文件名**: `LuomiNest Setup 0.3.0.exe`
- **大小**: ~80MB
- **特点**: 
  - 完整安装程序
  - 支持自定义安装路径
  - 自动创建桌面快捷方式
  - 自动创建开始菜单快捷方式
  - 支持卸载

### 2. 便携版 (Portable)
- **文件名**: `LuomiNest 0.3.0.exe`
- **大小**: ~80MB
- **特点**:
  - 单文件可执行
  - 无需安装，双击即用
  - 可放在U盘随身携带
  - 数据保存在程序同目录

---

## ⚠️ 常见问题

### 1. 符号链接权限错误

**错误信息**:
```
ERROR: Cannot create symbolic link : 客户端没有所需的特权
```

**解决方案**:
- **方法1**: 以管理员身份运行 PowerShell/CMD
- **方法2**: 启用Windows开发者模式
  - 设置 → 更新和安全 → 开发者选项 → 开发者模式

### 2. 下载速度慢

**解决方案**: 使用国内镜像加速
```powershell
$env:ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
```

### 3. 文件被占用

**错误信息**:
```
The process cannot access the file because it is being used by another process
```

**解决方案**:
- 关闭所有可能占用文件的程序（资源管理器、VS Code等）
- 删除 `release` 目录后重新打包

---

## 🚀 快速启动

### 开发模式
```bash
npm run dev
```

### 仅构建（不打包）
```bash
npm run build
```

### 打包但不生成安装包
```bash
npm run build:unpack
```

---

## 📝 其他打包命令

```bash
# 仅打包NSIS安装包
npm run build && electron-builder --win nsis

# 仅打包便携版
npm run build && electron-builder --win portable

# 打包32位版本
npm run build && electron-builder --win --ia32

# 同时打包32位和64位
npm run build && electron-builder --win --x64 --ia32
```

---

## 💡 提示

1. **首次打包**会下载Electron二进制文件（~137MB），请耐心等待
2. 下载的文件会缓存到 `%LOCALAPPDATA%\electron-builder\Cache\`，下次打包会更快
3. 如需分发应用，建议使用NSIS安装包
4. 便携版适合个人使用或测试

---

## 🔐 代码签名（可选）

如果需要代码签名证书，请：

1. 购买代码签名证书
2. 在 `package.json` 中配置:
```json
{
  "build": {
    "win": {
      "certificateFile": "path/to/certificate.pfx",
      "certificatePassword": "your-password"
    }
  }
}
```

未签名的应用在Windows上会显示"未知发布者"警告，但不影响使用。
