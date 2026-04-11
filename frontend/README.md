# LuomiNest Desktop - 辰汐分布式AI伴侣桌面客户端

> 基于 Electron + Vue3 + TypeScript 构建的 LuomiNest 桌面应用程序

## 项目概述

LuomiNest Desktop 是辰汐分布式 AI 伴侣平台的桌面客户端，提供沉浸式的 AI 交互体验。核心功能模块包括：

- **工作台 (Workspace)** - AI 对话与多 Agent 协作
- **工作流画布 (Workflow)** - 可视化自动化流程编排
- **灵感工坊 (Inspire)** - AI 驱动的创意辅助工具
- **任务中心 (Tasks)** - 项目与任务管理
- **内置浏览器 (Browser)** - 基于 Playwright 的浏览器内核
- **设置 (Settings)** - 系统配置与偏好管理

## 技术栈

| 技术 | 版本 | 作用 |
|------|------|------|
| Electron | 41.x | 桌面应用框架 |
| Vue | 3.5.x | 前端框架 |
| TypeScript | 6.0.x | 类型安全 |
| Vue Router | 5.0.x | 路由管理 |
| Playwright | 1.59.x | 浏览器自动化引擎 |
| electron-vite | 5.x | Electron 构建工具 |
| electron-builder | 26.x | 打包工具 |
| lucide-vue-next | 0.577.x | 图标库 |
| pnpm | 10.33.x | 包管理器 |

## 开发环境搭建

### 前置要求

- Node.js 20.19+ / 22.12+
- pnpm 10.33+
- Inno Setup 6（用于构建安装程序）
- Windows 10/11

### 安装工具

```powershell
# 安装 pnpm
npm install -g pnpm@10.33.0 --registry https://registry.npmmirror.com

# 安装 Inno Setup 6（二选一）
winget install --id JRSoftware.InnoSetup -e -s winget -i
# 或从 https://jrsoftware.org/isdl.php 下载安装
```

### 安装依赖

```powershell
cd frontend
pnpm install

# 首次安装后批准构建脚本（全选）
pnpm approve-builds
```

### 开发命令

```powershell
pnpm run dev          # 启动开发服务器
pnpm run build        # 构建项目
pnpm run typecheck    # TypeScript 类型检查
```

### 构建命令

```powershell
pnpm run build:portable    # 构建便携版
pnpm run build:installer   # 构建安装版（Inno Setup）
pnpm run build:all         # 同时构建两个版本
.\build.ps1                # PowerShell 脚本构建安装版
```

### 输出目录

```
release/
├── dist/
│   ├── win-unpacked/              # 解压后的应用文件
│   └── LuomiNest 1.0.0.exe        # 便携版
└── installer/
    └── LuomiNest-Setup-1.0.0.exe  # Inno Setup 安装程序
```

## 项目结构

```
frontend/
├── src/
│   ├── main/                    # 主进程代码
│   │   ├── index.ts             # 主进程入口
│   │   └── services/            # 主进程服务
│   ├── preload/                 # 预加载脚本
│   └── renderer/                # 渲染进程（Vue 前端）
│       └── src/
│           ├── main.ts          # Vue 应用入口
│           ├── App.vue          # 根组件
│           ├── router/          # 路由配置
│           ├── components/      # 组件
│           ├── views/           # 页面视图
│           ├── styles/          # 全局样式
│           └── types/           # TypeScript 类型定义
├── resources/
│   └── icon.ico                 # 应用图标
├── out/                         # 构建输出目录
├── release/                     # 打包输出目录
├── package.json                 # 项目配置
├── electron.vite.config.ts      # 构建配置
├── installer.iss                # Inno Setup 配置
├── build.ps1                    # 构建脚本
└── .npmrc                       # 镜像配置
```

## Electron 架构

```
┌─────────────────────────────────────────────────────────┐
│                   LuomiNest Desktop                      │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    IPC    ┌─────────────────────┐  │
│  │   主进程         │ ◄──────► │    渲染进程          │  │
│  │                 │           │  (Vue3 + Router)    │  │
│  │  - 窗口/托盘管理  │           │                     │  │
│  │  - Playwright    │           │  - 工作台/工作流     │  │
│  │  - CDP 服务      │           │  - 灵感/任务/浏览器  │  │
│  │  - 标签页管理    │           │  - 设置             │  │
│  └─────────────────┘           └─────────────────────┘  │
│           │                              │              │
│           ▼                              ▼              │
│  ┌─────────────────┐           ┌─────────────────────┐  │
│  │   Preload        │           │  contextBridge API  │  │
│  │  (安全桥接)       │           │  window.api.*       │  │
│  └─────────────────┘           └─────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```
