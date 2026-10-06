# LuomiNest 无头（Headless）Docker 部署

> 链路 E / 《2026-10-05 Docker 无头部署就绪度评估》阶段 1：**单容器、单副本、SQLite named volume**。
> 镜像内已固定 `DEPLOYMENT_MODE=headless`：未提供认证凭据会**拒绝启动**（fail-closed），
> 不会出现"服务活着但全 API 401"的假就绪状态。

## 1. 这是什么 / 不是什么

- 是：后端（FastAPI）的单容器服务器化部署，适合 NAS / VPS / 宿主机常驻。
- 不是：多副本水平扩展（进程内单例 + SQLite 双写，**明确不支持**）；也不含前端 ——
  桌面版 Electron 前端可直接把 API 地址指向本容器，或自备静态前端 + 反代。

## 2. 前置条件

- Docker Engine ≥ 24（compose v2 内置）；无需宿主机 Python。
- 构建上下文为**仓库根**（compose 已配置），根目录 `.dockerignore` 会排除
  frontend/文档/模型/构建产物，上下文只含 backend 运行所需源码。

## 3. 快速开始

```bash
# ① 生成凭据（三选一里最简单的 env 注入方式）
python -c "import secrets; print(secrets.token_urlsafe(32))"   # → LUOMINEST_AUTH_TOKEN
python -c "import secrets; print(secrets.token_urlsafe(48))"   # → SECRET_KEY（强烈建议显式设置）

# ② 在 docker/ 下创建 .env（compose 自动加载）
cat > docker/.env <<'EOF'
LUOMINEST_AUTH_TOKEN=<上一步生成的 token>
SECRET_KEY=<上一步生成的密钥>
EOF

# ③ 构建并启动（首次构建需拉取依赖，数分钟）
docker compose -f docker/docker-compose.yml up -d --build

# ④ 验证
curl http://127.0.0.1:18000/health          # → {"status":"ok","service":"LuomiNest"}
curl -H "Authorization: Bearer <token>" http://127.0.0.1:18000/api/v1/info
```

桌面版前端对接：设置里把后端地址指向 `http://<主机>:<端口>`，认证 token 填 `LUOMINEST_AUTH_TOKEN` 的值。

## 4. 环境变量清单（docker/.env 模板）

| 变量 | 必填 | 生成/获取建议 | 说明 |
|---|---|---|---|
| `LUOMINEST_AUTH_TOKEN` | **是**（三选一） | `python -c "import secrets; print(secrets.token_urlsafe(32))"` | 本地认证 Bearer token，env 注入**不落盘**；客户端全部 `/api/*`、`/ws`、`/mcp` 调用携带。未设置且无其他凭据来源时容器拒绝启动（compose 层用 `:?` 直接报错） |
| `SECRET_KEY` | 强烈建议 | `python -c "import secrets; print(secrets.token_urlsafe(48))"` | 加密主密钥（LLM API Key 等入库加密的根密钥）。**留空则走机器指纹绑定存储，容器重建后指纹变化 → 已加密数据不可解密且拒绝启动（P0-3）**。显式注入即跳过指纹绑定。设定后不可更换（换 = 旧密文全废） |
| `JWT_SECRET_KEY` | 三选一时必填 | `python -c "import secrets; print(secrets.token_urlsafe(48))"` | 仅 `AUTH_MODE=jwt` 时需要；留空的 jwt 密钥会按指纹自动生成，容器重建即作废 |
| `AUTH_MODE` | 否（默认 `local`） | — | `local`（单共享 Bearer）或 `jwt`（多用户）。远程暴露建议 `jwt` + `ALLOW_REGISTRATION=false` |
| `ALLOW_REGISTRATION` | 否（默认 `true`） | — | jwt 模式下暴露公网时务必改 `false` |
| `LUOMINEST_PORT` | 否（默认 `18000`） | — | 端口，宿主机映射与容器内监听同步变化 |
| `LUOMINEST_BIND` | 否（默认 `127.0.0.1`） | — | 宿主机侧绑定面。`0.0.0.0` = 对局域网开放（请确保 token 足够强，或前置 Nginx/Caddy 终结 TLS——本镜像无 TLS） |
| `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` | 否 | — | 也可启动后在网页设置里录入（入库走 SECRET_KEY 加密） |

镜像内已固定的基线（一般无需覆盖）：`DEPLOYMENT_MODE=headless`、`LUOMINEST_HOST=0.0.0.0`、
`LUOMINEST_DATA_DIR=/app/data`、`LUOMINEST_LOG_DIR=/app/data/logs`、`ENVIRONMENT=production`、`API_DOCS_ENABLED=false`。

> headless 认证三选一（代码强校验）：① env 注入 `LUOMINEST_AUTH_TOKEN`；② 数据卷内已有
> `config/auth_token`（随卷迁移的存量实例）；③ `AUTH_MODE=jwt` + 显式 `JWT_SECRET_KEY`。
> `LUOMINEST_NO_AUTH` 在任何形态都不豁免认证。

## 5. 数据卷内容（luominest-data → 容器内 /app/data）

| 路径 | 内容 |
|---|---|
| `luominest.db` (+ `-wal`/`-shm`) | 主库（SQLite，WAL 模式） |
| `config/auth_token` | 本地认证 token（env 注入时不生成） |
| `config/secret_key` + `config/secret_key.kdf-salt` | 加密主密钥密文（机器指纹绑定） |
| `config/secret_key.recovery` | 口令恢复包（仅显式创建后存在） |
| `config/jwt_secret_key` + `.kdf-salt` | JWT 签名密钥 |
| `uploads/` `avatars/` | 上传文件、头像 |
| `logs/backend.log` | 后端日志（5MB × 5 轮转；`docker compose logs -f` 看 stdout 同样内容） |

**迁移 = 整卷导出**（必须含 `config/` 三件套：`secret_key`、`*.kdf-salt`、`auth_token`）：

```bash
docker compose -f docker/docker-compose.yml stop backend
docker run --rm -v luominest_luominest-data:/data -v "$PWD":/backup alpine \
    tar czf /backup/luominest-data.tgz -C /data .
# 新机上反向解入后 docker compose up -d
```

> 卷名前缀为 compose 项目名（`luominest`），实际名称以 `docker volume ls` 为准。

## 6. SECRET_KEY 换机恢复包（未显式注入 SECRET_KEY 时的补救）

如果当初**没有**显式设置 `SECRET_KEY`（走了指纹绑定），容器重建/换节点后启动会报
"SECRET_KEY 解密失败"。凭恢复包 + 口令可救回：

```bash
# 原容器还活着时，先创建恢复包（口令不落盘，至少 8 位，请牢记）：
docker compose -f docker/docker-compose.yml run --rm --no-deps backend \
    python -m app.security.crypto.secret_key_manager create-recovery --data-dir /app/data

# 换机后：数据卷迁过来，在**新**容器里凭口令恢复（恢复包随卷自动迁移）：
docker compose -f docker/docker-compose.yml run --rm --no-deps backend \
    python -m app.security.crypto.secret_key_manager recover --data-dir /app/data
# 恢复成功后：docker compose -f docker/docker-compose.yml up -d backend
```

JWT 密钥同理，加 `--file jwt_secret_key`。桌面版（宿主机）对应命令见
`backend/app/security/crypto/secret_key_manager.py` 模块 docstring。

**最佳实践仍是显式注入 `SECRET_KEY`**——从头就不依赖机器指纹，天然免恢复。

## 7. 与桌面版共存注意事项

- **数据隔离**：容器数据在 named volume 里，与桌面版 userData（Electron 注入的
  `LUOMINEST_DATA_DIR`）完全独立，互不影响；但**同一个数据卷不要同时被桌面版和容器使用**
  （SQLite 跨机双写会损坏）。
- **端口**：桌面版默认 `127.0.0.1:18000`；容器默认映射到宿主机 `127.0.0.1:18000` ——
  同机同时跑会冲突，用 `LUOMINEST_PORT` 错开（如 18001）。
- **内置插件/技能**：容器挂了 `luominest-plugins`/`luominest-skills` 卷（首挂从镜像播种），
  与桌面版 backend/ 目录互不可见；运行期安装的插件随卷持久化。

## 8. 常用运维

```bash
docker compose -f docker/docker-compose.yml logs -f backend        # 日志
docker compose -f docker/docker-compose.yml ps                     # 状态（含 healthy）
docker compose -f docker/docker-compose.yml up -d --build backend  # 升级镜像（数据在卷中不受影响）
docker compose -f docker/docker-compose.yml down                   # 停止（卷保留）
```

## 9. 已知限制（按 05 报告，阶段 1 边界）

1. **硬性单副本**：`--scale` / 多容器共用数据卷不被支持（进程内单例 + SQLite 双写损坏）。
2. **依赖未锁定**：backend 无 `uv.lock`，镜像构建时按 `pyproject.toml` 下限式约束解析最新版；
   构建不可复现问题待 lock 文件落地后改为 `uv sync --frozen`（报告 P2）。
3. **语音栈不在镜像内**：sherpa-onnx/torch/faster-whisper 等 voice extras 未安装（懒加载，
   不装可正常启动），本地语音识别/合成不可用；云端 TTS（edge-tts 等）可用。
4. **内嵌 MQTT broker**：headless 下仍会随主服务启动，匿名、仅绑容器内 `127.0.0.1`、
   未向宿主机发布端口——外部不可达（安全），但 IoT 集成暂不可用；需要时换外置 Mosquitto
   （报告阶段 2，注意现存 mosquitto.conf 同样 allow_anonymous）。
5. **适配器 WS 端口（8080-8082）未发布**：QQ/MC/通用游戏接入需在 compose 显式加端口映射，
   并为实例配置 `access_token`（非 loopback + 无凭据目前仅 WARNING，报告 P1-1 建议升级为启动失败，尚未实现）。
6. **优雅退出最后一公里**：uvicorn 未设 `timeout_graceful_shutdown`（源码级，本轮不改源码），
   在途 SSE/LLM 流可能拖到 `stop_grace_period: 45s` 后被 SIGKILL。
7. **健康端点较浅**：`/health` 为静态 JSON，无 DB ping / readiness 区分（报告 P2，阶段 3）。
8. **无 TLS / CORS**：对外暴露请前置反代终结 HTTPS；`CORS_ORIGINS` 如需放开给指定前端，
   通过 env 覆盖为精确 origin 列表（严禁 `*` + credentials）。
9. **`os.cpu_count()` 不感知 cgroup**：容器 CPU limit 下 LLM 并发自适应失真，
   建议显式设 `LLM_MAX_CONCURRENT_REQUESTS`。
10. **Live2D/VRM 模型目录**：`backend/models/` 不进镜像（模型渲染属前端职责），
    `LIVE2D_MODEL_PATH` 等路径在容器内无内容，属预期。

## 10. 文件清单

| 文件 | 用途 |
|---|---|
| `docker/Dockerfile` | 多阶段构建（uv 装主依赖 → python:3.12-slim 运行镜像），非 root、HEALTHCHECK、`CMD python main.py` |
| `docker/docker-compose.yml` | 单容器编排：named volume、env 模板、restart/优雅退出/健康检查 |
| `docker/.env`（用户自建，不入库） | 真实凭据；根 `.gitignore` 的 `.env` 规则已覆盖 |
| `/.dockerignore`（仓库根） | 控制构建上下文（frontend/文档/模型/产物/密钥全部排除） |
