# syntax=docker/dockerfile:1
# =============================================================================
# LuomiNest Backend 无头（headless）容器镜像
# 链路 E / 《2026-10-05 Docker 无头部署就绪度》阶段 1：单容器、单副本、SQLite 卷
#
# 设计要点（与报告 P0 项一一对应）：
# - 入口用 `python main.py`（P0-1：绕开历史 Dockerfile 缺 --factory 的坑；
#   host/port 走 env LUOMINEST_HOST / LUOMINEST_PORT，见 main.py::resolve_host_port）
# - 多阶段构建：builder 用 uv 只装 project.dependencies 主依赖
#   （不装 dev/voice/extras；语音重型栈懒加载，不装可正常启动）
# - COPY backend 源码而非 wheel 安装（P0-5：wheel 只含 app 包，
#   运行还需要 main.py 与 plugins/、skills/ 目录；dev 模式路径按 CWD 解析，
#   WORKDIR=/app 时 PLUGIN_DIR/SKILL_DIR 恰好落在 /app/plugins、/app/skills）
# - 非 root 用户运行；数据卷挂载点 /app/data 归属应用用户
# - DEPLOYMENT_MODE=headless 直接烧进镜像：本镜像即无头形态，
#   未注入认证凭据会在启动期 fail-closed 拒绝启动（拒绝启动好过"活着但全 401"）
# =============================================================================

# ── 阶段 1：builder——uv 安装主依赖到独立 venv ────────────────────────────────
FROM python:3.12-slim AS builder

# uv 版本跟随项目本机使用的 0.12 线（uv 官方镜像发布 X.Y minor tag）
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

# 不让 uv 另下载解释器（镜像自带 python3.12）；硬链接跨文件系统时退回复制；
# 预编译 .pyc 加速容器冷启动
ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /build

# 只先拷依赖清单：pyproject 未变时依赖安装层可命中缓存
COPY backend/pyproject.toml ./pyproject.toml

# `-r pyproject.toml`：只装 [project.dependencies] 主依赖；
# dev / voice / extras 等 optional-dependencies 一律不装（镜像最小化）
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python -r pyproject.toml

# ── 阶段 2：runtime——精简运行镜像 ────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="LuomiNest Backend (headless)" \
      org.opencontainers.image.description="LuomiNest 无头部署镜像（FastAPI 后端，DEPLOYMENT_MODE=headless）" \
      org.opencontainers.image.source="https://github.com/luminous-ChenXi/LuomiNest" \
      org.opencontainers.image.licenses="AGPL-3.0"

# - PYTHONDONTWRITEBYTECODE/PYTHONUNBUFFERED：容器标准姿势（不写 .pyc、日志直出 stdout）
# - LUOMINEST_HOST=0.0.0.0：容器内必须绑非 loopback，否则端口映射进来全是 connection refused
#   （P0-2）；LUOMINEST_PORT 默认 18000，与历史桌面版一致，compose 可覆盖
# - LUOMINEST_DATA_DIR=/app/data：数据目录显式固定到卷挂载点（DB、token、密钥、上传、头像、日志）
# - LUOMINEST_LOG_DIR=/app/data/logs：日志落卷（P2：不设会写进容器可写层，重建即丢）
# - DEPLOYMENT_MODE=headless：本镜像即无头形态，启动期强制校验认证凭据三选一
# - ENVIRONMENT=production + API_DOCS_ENABLED=false：生产基线（关 /docs、/redoc）
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LUOMINEST_HOST=0.0.0.0 \
    LUOMINEST_PORT=18000 \
    LUOMINEST_DATA_DIR=/app/data \
    LUOMINEST_LOG_DIR=/app/data/logs \
    DEPLOYMENT_MODE=headless \
    ENVIRONMENT=production \
    API_DOCS_ENABLED=false \
    PATH="/opt/venv/bin:${PATH}"

# 固定 UID/GID 的非 root 用户（10001 避免与宿主机常见 UID 撞车）
RUN groupadd --system --gid 10001 luominest && \
    useradd --system --uid 10001 --gid 10001 --home-dir /app --shell /usr/sbin/nologin luominest

WORKDIR /app

# venv 整体搬入运行镜像（base 镜像一致，python 符号链接指向的 /usr/local/bin 解释器仍在）
COPY --from=builder /opt/venv /opt/venv

# 运行必需源码：入口 + app 包（含 app/data/avatar-manifest.json 内置模型清单）
# pyproject.toml 拷到 CWD：app/__init__.py 靠它读取版本号（缺失会显示 0.0.0）
# 代码目录保持 root 只读（非 root 不可篡改），可写面收敛到数据卷与插件/技能目录
COPY --chown=root:root backend/main.py ./main.py
COPY --chown=root:root backend/pyproject.toml ./pyproject.toml
COPY --chown=root:root backend/app ./app

# 插件/技能目录授予应用用户写权限：运行期插件市场/技能安装会写入
# （注意：写入容器可写层，容器重建即丢——持久化方案见 docker-compose.yml 卷注释）
COPY --chown=luominest:luominest backend/plugins ./plugins
COPY --chown=luominest:luominest backend/skills ./skills

# 数据卷挂载点：预建目录结构并归属应用用户，
# named volume 首次挂载时继承该属主，避免 "Permission denied"
RUN mkdir -p /app/data/config /app/data/logs /app/data/uploads /app/data/avatars && \
    chown -R luominest:luominest /app/data

# 用户名而非数字（UID/GID 已在上方固定为 10001），可读性优先；
# DL3066 为 info 级提示，此处为刻意选择
# hadolint ignore=DL3066
USER luominest

# 主 API 端口（EXPOSE 仅声明用途；实际以 env LUOMINEST_PORT 为准，改动需同步 compose 端口映射）
EXPOSE 18000

# 健康检查打现有 /health 端点（免鉴权，见 app/security/auth/middleware.py 豁免清单；
# 报告 P2 注：该端点目前是静态 JSON，未含 DB ping——readiness 拆分属阶段 3）
# slim 镜像没有 curl/wget，用 venv 自带的 python 标准库探测；
# 端口跟随运行时 env LUOMINEST_PORT，compose 覆盖端口后检查不会失配
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=5 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(\"http://127.0.0.1:%s/health\" % os.environ.get(\"LUOMINEST_PORT\", \"18000\"), timeout=4)"]

# 不用 uvicorn import-string + --factory（历史 Dockerfile 的缺陷），
# 直接走 main.py：host/port 优先级链 CLI > env > 默认值，镜像内已烧 env
CMD ["python", "main.py"]
