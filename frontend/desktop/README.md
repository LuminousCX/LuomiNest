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
| Electron | 39.x | 桌面应用框架 |
| Vue | 3.5.x | 前端框架 |
| TypeScript | 5.9.x | 类型安全 |
| Vue Router | 4.x | 路由管理 |
| Playwright | 1.59.x | 浏览器自动化引擎 |
| electron-vite | 5.x | Electron 构建工具 |
| electron-builder | 26.x | 打包工具 |
| lucide-vue-next | 0.577.x | 图标库 |

## 项目结构

```
desktop/
├── src/
│   ├── main/                    # 主进程代码
│   │   ├── index.ts             # 主进程入口（窗口管理、IPC、托盘）
│   │   └── services/            # 主进程服务
│   │       ├── playwright.ts    # Playwright 浏览器控制
│   │       ├── cdp.ts           # Chrome DevTools Protocol
│   │       └── tab-manager.ts   # 标签页管理
│   ├── preload/                 # 预加载脚本（安全桥接）
│   │   └── index.ts
│   └── renderer/                # 渲染进程（Vue 前端）
│       └── src/
│           ├── main.ts          # Vue 应用入口
│           ├── App.vue          # 根组件
│           ├── router/          # 路由配置
│           │   └── index.ts
│           ├── components/      # 组件
│           │   ├── TitleBar.vue     # 自定义标题栏
│           │   ├── LumiSidebar.vue  # 辰汐侧边栏（含 Agent 面板）
│           │   └── IconRail.vue     # 图标导航栏
│           ├── composables/     # 组合式函数
│           │   └── usePlaywright.ts
│           ├── views/           # 页面视图
│           │   ├── WorkspaceView.vue
│           │   ├── WorkflowView.vue
│           │   ├── InspireView.vue
│           │   ├── TasksView.vue
│           │   ├── BrowserView.vue
│           │   └── SettingsView.vue
│           ├── styles/          # 全局样式
│           │   └── main.css
│           └── types/           # TypeScript 类型定义
│               └── index.ts
├── out/                         # 构建输出目录
├── release/                     # 打包输出目录
├── package.json                 # 项目配置
├── electron.vite.config.ts      # 构建配置
├── tsconfig.json                # TypeScript 配置
├── BUILD.md                     # 打包指南
└── .npmrc                       # npm 镜像配置
```

## 开发环境搭建

### 前置要求

- Node.js 18+ / npm 9+
- Windows 10/11（当前主要开发平台）

### 安装依赖

```bash
cd frontend/desktop
npm install
```

### 启动开发

```bash
npm run dev
```

### 常用命令

```bash
npm run dev              # 启动开发服务器
npm run build            # 构建项目
npm run build:win        # 打包 Windows 安装程序
npm run build:unpack     # 打包解压版
npm run typecheck        # TypeScript 类型检查
```

## 打包发布

详细打包说明请参阅 [BUILD.md](./BUILD.md)。

打包产物位于 `release/dist/` 目录：
- `LuomiNest Setup x.x.x.exe` - NSIS 安装程序
- `LuomiNest x.x.x.exe` - 便携版
- `win-unpacked/` - 解压版

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
