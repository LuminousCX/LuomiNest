---
id: skill-creator
name: 技能创建助手
description: 元技能，指导 AI 创建、修改、校验 LuomiNest SKILL.md 文件，使 AI 能根据用户需求自主扩展能力库
version: 1.0.0
author: LuminousCX
license: MIT
tags: [skill, meta, creation, authoring]
category: productivity
icon: Sparkles
trigger_keywords: [创建技能, 新建技能, 修改技能, 编辑技能, 技能创建, 技能编辑, skill creator, create skill, edit skill, new skill, make skill]
---

# 技能创建助手（Skill Creator）

当用户请求创建、修改、查看或校验技能（SKILL.md）时，本技能提供完整的格式规范与最佳实践指引。AI 应严格按照本技能描述的格式产出 SKILL.md 内容，并通过工具调用持久化到 `backend/skills/<skill_id>/SKILL.md`。

## 1. 触发条件

满足以下任一情形即应用本技能：

- 用户明确请求"创建一个技能"、"新建技能"、"帮我写一个 SKILL.md"
- 用户请求"修改/更新/优化某个技能"
- 用户请求"检查/校验技能格式"
- 用户描述一个新能力需求，并希望 AI 能在后续对话中复用该能力

## 2. SKILL.md 格式规范

SKILL.md 由两部分组成：**YAML Frontmatter**（元数据）+ **Markdown Body**（Prompt 指令体）。

### 2.1 Frontmatter 标准字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 技能唯一标识，使用 kebab-case，与目录名一致 |
| `name` | string | 是 | 中文展示名称（2-12 字） |
| `description` | string | 是 | 一句话描述技能作用（20-80 字） |
| `version` | string | 是 | 语义化版本号，初始为 `1.0.0` |
| `author` | string | 是 | 作者，项目内置技能使用 `LuminousCX` |
| `license` | string | 否 | 许可证，默认 `MIT` |
| `tags` | string[] | 否 | 标签数组，用于市场展示与过滤 |
| `category` | string | 否 | 分类 id（如 `productivity`、`coding`、`lifestyle`） |
| `icon` | string | 否 | Lucide 图标名（PascalCase，如 `Map`、`Sparkles`） |
| `trigger_keywords` | string[] | 是 | 触发关键词数组，至少 3 个，包含中英文 |

**非标准字段**：frontmatter 中除上述字段外的内容会自动进入 `metadata`，不影响加载但可被工具读取。避免添加 `type: plugin`（会被识别为插件而非技能）。

### 2.2 Body 结构

Body 是注入到 LLM Prompt 的指令体，AI 将据此完成用户请求。Body 必须包含以下结构（顺序可调整）：

```markdown
# {技能中文名}

{一段简短开场说明：何时应用此技能、核心目标}

## 1. 触发条件

{列出应用此技能的典型情形}

## 2. 执行流程

{分步骤、有条理地描述 AI 应如何完成相关任务}

## 3. 输出格式

{明确 AI 输出的结构、字段、示例}

## 4. 注意事项

{边界情况、安全约束、不应做的事}
```

## 3. 创建技能的流程

当用户请求创建新技能时：

1. **明确需求**：主动询问技能的目标场景、触发关键词建议、输出形式。若用户已描述清楚，无需追问。
2. **确认 id**：建议使用 kebab-case 英文 id（如 `code-reviewer`、`meeting-summary`），与目录名一致。
3. **生成内容**：按 §2 规范生成 frontmatter + body。
4. **写入文件**：通过 `skill.write` 工具（或调用 `/api/v1/skills/{id}/draft` 接口）将内容写入 `backend/skills/<id>/SKILL.md`。
5. **自动重载**：写入成功后调用 `skill.reload` 工具（或 `/api/v1/skills/<id>/reload`）让新技能立即生效。
6. **反馈结果**：向用户展示技能 id、名称、触发关键词、文件路径，并提示可在"设置 → 插件与技能"中管理。

## 4. 修改技能的流程

当用户请求修改现有技能时：

1. **定位技能**：通过 id 或名称查找。若不确定，调用 `skill.list` 工具列出所有技能。
2. **读取当前内容**：调用 `skill.get` 工具获取 frontmatter + body 全文。
3. **明确修改范围**：与用户确认要修改的部分（frontmatter / body 的某个章节 / 全部重写）。
4. **生成新内容**：基于现有内容做最小化修改，保留未提及的部分。
5. **写入并重载**：同 §3 步骤 4-5。
6. **反馈差异**：简要说明修改了哪些字段或章节。

## 5. 校验技能的流程

当用户请求校验技能格式时，按以下清单检查并报告问题：

- [ ] frontmatter 以 `---` 开始和结束
- [ ] `id` 为合法 kebab-case，与目录名一致
- [ ] `name` 非空且为中文（推荐）
- [ ] `description` 长度在 20-80 字
- [ ] `version` 符合语义化版本格式（如 `1.0.0`）
- [ ] `trigger_keywords` 至少 3 个关键词
- [ ] body 以 `#` 一级标题开头
- [ ] body 至少包含"执行流程"或等价章节
- [ ] 不含 `type: plugin` 字段
- [ ] 不含未授权的敏感权限声明

## 6. 注意事项

- **不要伪造能力**：技能 body 描述的执行流程应是 AI 真实可执行的；若依赖外部工具（如搜索、代码执行），应在 body 中明确说明调用哪个工具。
- **避免重复**：创建前先调用 `skill.list` 查看是否已有类似技能，避免重复实现。
- **版权合规**：技能内容应为原创或基于公开规范；不要直接复制第三方 prompt，可参考方法但需用自己语言重写。
- **关键词精准**：trigger_keywords 应选择用户真实会输入的词，避免过于宽泛（如 `ai`、`help`）导致无差别触发。
- **Body 长度**：建议 body 控制在 100-800 行；过长会污染上下文，过短则指引不足。
- **版本管理**：每次修改 body 或 frontmatter 字段时递增 version（小修改 patch、新增章节 minor、不兼容 major）。
- **不破坏现有技能**：修改技能时保留原作者署名（除非用户明确要求更换），新增内容应附 `## Changelog` 章节记录变更。
