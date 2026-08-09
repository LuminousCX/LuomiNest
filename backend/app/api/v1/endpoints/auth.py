"""LuomiNest 认证 API 端点。

提供用户注册、登录、Token 刷新、登出及当前用户信息查询。
仅在 AUTH_MODE="jwt" 时有实际意义。

安全特性：
- 登录失败统一返回"用户名或密码错误"（不泄露用户是否存在）
- 登录失败延迟响应（防暴力破解，参考 AstrBot 登录防爆破模式）
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from loguru import logger

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ValidationError
from app.core.utils import ok
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import async_session_factory
from app.security.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_token as jwt_verify_token,
    TokenError,
)
from app.security.auth.password import hash_password, verify_password


# 登录失败时的人工延迟（秒），增加暴力破解时间成本
_LOGIN_FAILURE_DELAY = 1.5
# 最小用户名校验长度
_USERNAME_MIN_LENGTH = 3


# ── Pydantic 请求/响应模型 ─────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str | None = Field(None, max_length=100)


class LoginRequest(BaseModel):
    username: str
    password: str
    device_id: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Router ─────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/auth", tags=["认证"])


# ── 依赖注入 ───────────────────────────────────────────────────────────────────

async def get_current_user(request: Request) -> User:
    """从 JWT 中提取当前用户（仅 jwt 模式下使用）。

    依赖中间件已将用户信息存入 request.state.user。
    """
    user_info = getattr(request.state, "user", None)
    if not user_info or not user_info.get("user_id"):
        raise AuthenticationError("未授权，缺少有效的认证令牌")

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.id == user_info["user_id"])
        )
        user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError("用户不存在")
    if not user.is_active:
        raise AuthenticationError("用户已被禁用")

    # 验证 token_version 匹配（防止已吊销的 Token 继续使用）
    token_ver = user_info.get("token_version", 1)
    if token_ver != user.token_version:
        raise AuthenticationError("令牌已失效，请重新登录")

    return user


# ── 端点 ───────────────────────────────────────────────────────────────────────

@router.post("/register")
async def register(request: RegisterRequest):
    """用户注册。

    检查 ALLOW_REGISTRATION 配置，若已有用户则拒绝（单用户模式）。
    """
    if not settings.ALLOW_REGISTRATION:
        raise ValidationError("当前不允许新用户注册")

    async with async_session_factory() as session:
        # 检查是否已有用户（单用户模式）
        count_result = await session.execute(select(func.count()).select_from(User))
        user_count = count_result.scalar() or 0
        if user_count > 0:
            raise ValidationError("已存在用户账户，当前不支持多用户注册")

        # 检查用户名是否已被占用
        existing = await session.execute(
            select(User).where(User.username == request.username)
        )
        if existing.scalar_one_or_none():
            raise ValidationError(f"用户名 '{request.username}' 已被占用")

        # 创建用户
        user = User(
            username=request.username,
            display_name=request.display_name,
            password_hash=hash_password(request.password),
            token_version=1,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        logger.success(f"[Auth] 新用户注册成功: username={request.username}, id={user.id}")

        return ok(
            {
                "user_id": user.id,
                "username": user.username,
            },
            message="注册成功",
        )


@router.post("/login")
async def login(request: LoginRequest):
    """用户登录。

    验证用户名密码，签发 access_token 和 refresh_token。
    失败时统一返回"用户名或密码错误"并延迟响应（防暴力破解）。
    """
    # 用户名长度快速校验（避免对过短用户名做无意义查询）
    if len(request.username) < _USERNAME_MIN_LENGTH:
        await asyncio.sleep(_LOGIN_FAILURE_DELAY)
        raise AuthenticationError("用户名或密码错误")

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.username == request.username)
        )
        user = result.scalar_one_or_none()

    if not user:
        await asyncio.sleep(_LOGIN_FAILURE_DELAY)
        raise AuthenticationError("用户名或密码错误")
    if not user.is_active:
        await asyncio.sleep(_LOGIN_FAILURE_DELAY)
        raise AuthenticationError("用户已被禁用")
    if not verify_password(request.password, user.password_hash):
        await asyncio.sleep(_LOGIN_FAILURE_DELAY)
        raise AuthenticationError("用户名或密码错误")

    device_id = request.device_id or ""
    roles = ["user"]

    access_token = create_access_token(
        user_id=user.id,
        device_id=device_id,
        roles=roles,
        token_version=user.token_version,
    )
    refresh_token = create_refresh_token(
        user_id=user.id,
        device_id=device_id,
    )

    logger.success(f"[Auth] 用户登录成功: username={request.username}")

    return ok(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
        message="登录成功",
    )


@router.post("/refresh")
async def refresh_token(request: RefreshRequest):
    """刷新 Access Token。

    验证 refresh_token，检查 token type 和 token_version，签发新的 access_token。
    """
    # 验证 refresh_token
    try:
        payload = jwt_verify_token(request.refresh_token)
    except TokenError as exc:
        raise AuthenticationError(f"Refresh token 无效: {exc.message}")

    # 检查 token type
    if payload.get("type") != "refresh":
        raise AuthenticationError("无效的令牌类型，需要 refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("令牌中缺少用户信息")

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError("用户不存在")
    if not user.is_active:
        raise AuthenticationError("用户已被禁用")

    # 签发新的 access_token
    device_id = payload.get("device_id", "")
    roles = ["user"]

    access_token = create_access_token(
        user_id=user.id,
        device_id=device_id,
        roles=roles,
        token_version=user.token_version,
    )

    return ok(
        {
            "access_token": access_token,
            "token_type": "bearer",
        },
        message="刷新成功",
    )


@router.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    """登出（吊销当前设备 Token）。

    递增用户的 token_version，使旧 JWT 因版本不匹配而失效。
    """
    async with async_session_factory() as session:
        user.token_version += 1
        session.add(user)
        await session.commit()

    logger.success(f"[Auth] 用户登出成功: username={user.username}, new_version={user.token_version}")

    return ok(None, message="登出成功")


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """获取当前用户信息（不含 password_hash）。"""
    return ok(
        {
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "is_active": user.is_active,
            "token_version": user.token_version,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }
    )
