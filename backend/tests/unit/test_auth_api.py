"""auth 端点链路回归测试（用户域无 service，端点内裸 SQL + 临时 SQLite）。

覆盖（JWT 模式，经真实认证中间件）：
- 注册 → 登录 → /me → refresh → logout → 旧 token 失效 → 重登 的完整链路
- 单用户模式：已有用户时再注册被拒
- ALLOW_REGISTRATION=False 时注册被拒
- 登录失败统一返回"用户名或密码错误"（不泄露用户是否存在）

注：auth 端点没有独立的"改密"接口，旧凭据失效语义由 logout 递增
token_version 吊销旧 JWT 验证（与改密后强制重登同机制）。
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete as sa_delete

from app.api.v1.endpoints.auth import router as auth_router
from app.core.config import settings
from app.core.exceptions import LuomiNestError
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import sync_session_factory
from app.security.auth.middleware import luomi_auth_middleware
from app.security.auth.password import hash_password
from app.security.rate_limiter import limiter, rate_limit_exceeded_handler


@pytest.fixture(scope="module")
def auth_app(_init_test_db):
    """最小化装配：仅 auth 路由 + 与 app_factory 一致的错误信封与认证中间件。"""
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")

    @app.exception_handler(LuomiNestError)
    async def lumi_error_handler(request: Request, exc: LuomiNestError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": 1,
                "message": exc.message,
                "error": {"code": exc.code, "message": exc.message},
                "data": None,
            },
        )

    from slowapi.errors import RateLimitExceeded

    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        return await luomi_auth_middleware(request, call_next)

    return app


@pytest.fixture(autouse=True)
def _clean_users():
    """清空用户表：注册链路依赖单用户模式的"空表"前置状态。"""
    with sync_session_factory() as session:
        session.execute(sa_delete(User))
        session.commit()
    yield


@pytest.fixture
async def client(auth_app, monkeypatch):
    """JWT 模式 + 关闭限流的 AsyncClient（同一事件循环内发全部请求）。

    限流内存桶跨用例共享，RATE_AUTH=10/minute 会被链路测试打满，测试中禁用；
    登录失败的人工防爆破延迟置 0，避免拖慢用例。
    """
    monkeypatch.setattr(settings, "AUTH_MODE", "jwt")
    monkeypatch.setattr(limiter, "enabled", False)
    monkeypatch.setattr("app.api.v1.endpoints.auth._LOGIN_FAILURE_DELAY", 0.0)

    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_register_login_refresh_logout_chain(client):
    # 注册：单用户模式空表允许创建
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "secret123", "display_name": "Alice"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["message"] == "注册成功"
    assert body["data"]["username"] == "alice"
    assert body["data"]["user_id"]

    # 登录：签发 access/refresh token
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "secret123"}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["token_type"] == "bearer"
    access_token, refresh_token = data["access_token"], data["refresh_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # /me：返回当前用户且不含 password_hash
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    me = resp.json()["data"]
    assert me["username"] == "alice"
    assert me["is_active"] is True
    assert "password_hash" not in me

    # refresh：换发新 access_token 且可用
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    new_access = resp.json()["data"]["access_token"]
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert resp.status_code == 200

    # access token 不能当 refresh token 用（type 校验）
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_FAILED"

    # logout：递增 token_version 吊销旧 JWT
    resp = await client.post("/api/v1/auth/logout", headers=headers)
    assert resp.status_code == 200

    # logout 前签发的新旧 access token 全部因版本不匹配失效
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert resp.status_code == 401

    # 重新登录恢复访问
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "secret123"}
    )
    assert resp.status_code == 200
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {resp.json()['data']['access_token']}"},
    )
    assert resp.status_code == 200


async def test_register_rejected_when_user_exists(client):
    # 直接落库一个用户，制造"已存在用户"前置状态（单用户模式）
    from app.infrastructure.database.session import async_session_factory

    async with async_session_factory() as session:
        session.add(
            User(
                username="bob",
                password_hash=hash_password("password1"),
                token_version=1,
                is_active=True,
            )
        )
        await session.commit()

    resp = await client.post(
        "/api/v1/auth/register", json={"username": "carl", "password": "secret123"}
    )
    assert resp.status_code == 422
    assert "已存在用户账户" in resp.json()["message"]


async def test_register_rejected_when_registration_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_REGISTRATION", False)

    resp = await client.post(
        "/api/v1/auth/register", json={"username": "dave", "password": "secret123"}
    )
    assert resp.status_code == 422
    assert "当前不允许新用户注册" in resp.json()["message"]


async def test_login_failure_does_not_leak_user_existence(client):
    # 先注册一个真实用户
    resp = await client.post(
        "/api/v1/auth/register", json={"username": "eve", "password": "secret123"}
    )
    assert resp.status_code == 200

    # 不存在的用户 与 存在的用户+错密码：返回统一错误，不泄露用户是否存在
    missing = await client.post(
        "/api/v1/auth/login", json={"username": "ghost_user", "password": "whatever1"}
    )
    wrong_password = await client.post(
        "/api/v1/auth/login", json={"username": "eve", "password": "wrongpass"}
    )
    assert missing.status_code == wrong_password.status_code == 401
    assert missing.json()["message"] == wrong_password.json()["message"] == "用户名或密码错误"
    assert missing.json()["error"]["code"] == wrong_password.json()["error"]["code"] == "AUTH_FAILED"
