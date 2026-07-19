import {
  Stack,
  Grid,
  H1,
  H2,
  H3,
  Text,
  Stat,
  Tag,
  Divider,
  Table,
  Callout,
  Row,
  Pill,
} from "qoder/canvas";

const themes = [
  { id: "blue", name: "默认蓝", primary: "#147EBC", secondary: "#5BA4D4", accent: "#f43f5e" },
  { id: "purple", name: "紫罗兰", primary: "#7C3AED", secondary: "#A78BFA", accent: "#EC4899" },
  { id: "red", name: "中国红", primary: "#C0392B", secondary: "#E74C3C", accent: "#F59E0B" },
  { id: "green", name: "翡翠绿", primary: "#059669", secondary: "#34D399", accent: "#8B5CF6" },
  { id: "orange", name: "暖橘橙", primary: "#EA580C", secondary: "#FB923C", accent: "#0EA5E9" },
];

const modules = [
  { name: "主题数据模型", status: "PASS", files: "theme-types.ts, theme-presets.ts" },
  { name: "CSS 变量系统", status: "PASS", files: "themes.css, variables.css, main.css" },
  { name: "主题 Store", status: "PASS", files: "stores/theme.ts" },
  { name: "设置页面 UI", status: "PASS", files: "SettingsAppearanceSection.vue + 3 子组件" },
  { name: "全局背景组件", status: "PASS", files: "AppBackgroundOverlay.vue, App.vue" },
  { name: "IPC 持久化", status: "PASS", files: "preload/index.ts, ipc-handlers.ts, bg-protocol.ts" },
  { name: "硬编码颜色迁移", status: "PASS", files: "5 个组件文件" },
  { name: "静态资源", status: "PASS", files: "public/themes/ (7 文件)" },
];

const bugsFixed = [
  { id: "1", issue: "themes.css 缺失 7 个品牌变量覆盖", impact: "主题切换视觉无变化", fix: "补全 10 个选择器块的 22 个变量" },
  { id: "2", issue: "ThemePresetSelector 双重写入", impact: "响应式时序竞态", fix: "移除冗余 emit，单通道更新" },
  { id: "3", issue: "设置页面布局偏左", impact: "视觉不协调", fix: "复用主智能体页面卡片式布局" },
  { id: "4", issue: "隐藏 input[type=file] 在 Electron 中失效", impact: "无法上传背景", fix: "改用原生 dialog.showOpenDialog" },
  { id: "5", issue: "file:// URL 被 CSP 阻止", impact: "背景图无法渲染", fix: "注册 luominest-bg: 自定义协议" },
  { id: "6", issue: "协议 URL 解析 hostname/pathname 混淆", impact: "400 Bad Request", fix: "优先从 url.hostname 提取文件名" },
  { id: "7", issue: "Vue Proxy 无法通过 IPC structured clone", impact: "保存配置崩溃", fix: "toRaw() + JSON 序列化转纯对象" },
  { id: "8", issue: "CSS 渐变被错误包裹 url()", impact: "预设背景失效", fix: "正则检测渐变，分支处理" },
];

const keyFiles = [
  { file: "stores/theme-types.ts", desc: "数据模型接口", type: "新建" },
  { file: "stores/theme-presets.ts", desc: "5 个预设主题定义", type: "新建" },
  { file: "stores/theme.ts", desc: "多主题 + 背景管理 Store", type: "修改" },
  { file: "styles/themes.css", desc: "297 行 CSS 变量覆盖", type: "新建" },
  { file: "styles/variables.css", desc: "新增辅色 + 背景变量", type: "修改" },
  { file: "components/AppBackgroundOverlay.vue", desc: "全局背景层", type: "新建" },
  { file: "components/theme/*", desc: "3 个主题 UI 子组件", type: "新建" },
  { file: "main/services/bg-protocol.ts", desc: "自定义协议处理器", type: "新建" },
  { file: "shared/ipc-types.ts", desc: "跨进程共享类型", type: "新建" },
];

export default function ThemeSystemReport() {
  return (
    <Stack gap={24}>
      <Stack gap={8}>
        <H1>LuomiNest 主题系统重构</H1>
        <Text tone="secondary">
          完整实现自定义主题系统：5 预设 + 5 自定义三色主题、全局背景图片、设置页面 UI、CSS 变量驱动、Electron IPC 持久化
        </Text>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="8/8" label="模块通过审计" tone="success" />
        <Stat value="5" label="预设色彩主题" />
        <Stat value="22" label="CSS 变量/主题块" />
        <Stat value="8" label="运行时 Bug 修复" />
      </Grid>

      <Divider />

      <H2>预设主题配色（莫兰迪三色风格）</H2>
      <Grid columns={5} gap={12}>
        {themes.map((t) => (
          <Stack key={t.id} gap={6} style={{ alignItems: "center" }}>
            <Row gap={4}>
              <div style={{ width: 24, height: 24, borderRadius: "50%", background: t.primary }} />
              <div style={{ width: 24, height: 24, borderRadius: "50%", background: t.secondary }} />
              <div style={{ width: 24, height: 24, borderRadius: "50%", background: t.accent }} />
            </Row>
            <Text size="small" weight="medium">{t.name}</Text>
            <Text size="small" tone="secondary">{t.id}</Text>
          </Stack>
        ))}
      </Grid>

      <Divider />

      <H2>架构概览</H2>
      <Grid columns={2} gap={16}>
        <Stack gap={8}>
          <H3>双维度主题模型</H3>
          <Text size="small">
            data-theme (light/dark) × data-color-theme (色彩风格) 正交组合，任何色彩主题均可搭配浅色或深色模式。CSS 变量驱动，零 JS 渲染开销。
          </Text>
          <H3>持久化策略</H3>
          <Text size="small">
            Electron IPC 存储完整 ThemeConfig 到 userData 目录。Vue Proxy 通过 toRaw() + JSON 序列化避免 structured clone 错误。
          </Text>
        </Stack>
        <Stack gap={8}>
          <H3>背景图片系统</H3>
          <Text size="small">
            预设渐变背景 + 用户自定义上传。自定义 luominest-bg: 协议安全提供本地文件，CSP 白名单已配置。桌宠页面三层保护排除。
          </Text>
          <H3>设置页面 UI</H3>
          <Text size="small">
            复用主智能体页面卡片式布局，预设色卡网格 + 自定义主题编辑器（实时预览）+ 背景管理（模糊/透明度滑块）。
          </Text>
        </Stack>
      </Grid>

      <Divider />

      <H2>模块审计结果</H2>
      <Table
        headers={["模块", "状态", "关键文件"]}
        rows={modules.map((m) => [
          m.name,
          <Tag tone="success">{m.status}</Tag>,
          <Text size="small" tone="secondary">{m.files}</Text>,
        ])}
      />

      <Divider />

      <H2>运行时 Bug 修复记录</H2>
      <Table
        headers={["#", "问题", "修复方案"]}
        rows={bugsFixed.map((b) => [
          b.id,
          <Text size="small">{b.issue}</Text>,
          <Text size="small">{b.fix}</Text>,
        ])}
      />

      <Divider />

      <H2>关键文件清单</H2>
      <Table
        headers={["文件", "说明", "操作"]}
        rows={keyFiles.map((f) => [
          <Text size="small" weight="medium">{f.file}</Text>,
          <Text size="small">{f.desc}</Text>,
          f.type === "新建" ? <Pill tone="success">新建</Pill> : <Pill tone="info">修改</Pill>,
        ])}
      />

      <Divider />

      <Callout tone="success">
        <Text weight="medium">验证通过</Text>
        <Text size="small">
          vue-tsc --noEmit 零错误 | Spec 8 模块全部 PASS | TypeScript 编译、CSS 一致性、IPC 链路、静态资源均验证通过
        </Text>
      </Callout>
    </Stack>
  );
}
