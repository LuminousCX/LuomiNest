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
from sqlalchemy import select, func, update
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
from app.security.auth.password import hash_password_async, verify_password_async
from app.security.rate_limiter import limiter, RATE_AUTH


# 登录失败时的人工延迟（秒），增加暴力破解时间成本
_LOGIN_FAILURE_DELAY = 1.5
# 最小用户名校验长度
_USERNAME_MIN_LENGTH = 3
# 单用户存续的 refresh jti 存活名单上限（多端各自登录持有；超出按 FIFO 淘汰最旧）
_MAX_ACTIVE_REFRESH_JTIS = 10

# 进程内串行化 login/refresh 对 jti 存活名单的「读-改-写」：
# 并发提交同一 jti 时后到者必见名单已更新而按重放处理（轮换语义下的确定性结果），
# 避免双读旧名单各自签发造成轮换分叉、稍后误触发全量吊销（单用户桌面应用，无吞吐顾虑）
_REFRESH_STATE_LOCK = asyncio.Lock()


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
@limiter.limit(RATE_AUTH)
async def register(request: Request, body: RegisterRequest):
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
            select(User).where(User.username == body.username)
        )
        if existing.scalar_one_or_none():
            raise ValidationError(f"用户名 '{body.username}' 已被占用")

        # 创建用户（bcrypt 哈希走线程池，避免阻塞事件循环）
        user = User(
            username=body.username,
            display_name=body.display_name,
            password_hash=await hash_password_async(body.password),
            token_version=1,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        logger.success(f"[Auth] 新用户注册成功: username={body.username}, id={user.id}")

        return ok(
            {
                "user_id": user.id,
                "username": user.username,
            },
            message="注册成功",
        )


@router.post("/login")
@limiter.limit(RATE_AUTH)
async def login(request: Request, body: LoginRequest):
    """用户登录。

    验证用户名密码，签发 access_token 和 refresh_token。
    失败时统一返回"用户名或密码错误"并延迟响应（防暴力破解）。
    """
    # 用户名长度快速校验（避免对过短用户名做无意义查询）
    if len(body.username) < _USERNAME_MIN_LENGTH:
        await asyncio.sleep(_LOGIN_FAILURE_DELAY)
        raise AuthenticationError("用户名或密码错误")

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.username == body.username)
        )
        user = result.scalar_one_or_none()

    if not user:
        await asyncio.sleep(_LOGIN_FAILURE_DELAY)
        raise AuthenticationError("用户名或密码错误")
    if not user.is_active:
        await asyncio.sleep(_LOGIN_FAILURE_DELAY)
        raise AuthenticationError("用户已被禁用")
    if not await verify_password_async(body.password, user.password_hash):
        await asyncio.sleep(_LOGIN_FAILURE_DELAY)
        raise AuthenticationError("用户名或密码错误")

    device_id = body.device_id or ""
    roles = ["user"]

    access_token = create_access_token(
        user_id=user.id,
        device_id=device_id,
        roles=roles,
        token_version=user.token_version,
    )
    refresh_token, refresh_jti = create_refresh_token(
        user_id=user.id,
        device_id=device_id,
        token_version=user.token_version,
    )

    # 登记新 refresh token 的 jti（轮换/重用检测的存活名单，见 refresh 端点；
    # 多端各自登录各持一个 jti，超出上限按 FIFO 淘汰最旧）。
    # 锁内重读名单 + 窄列 UPDATE：不回写整行，防止把并发登出刚递增的
    # token_version 用本请求加载的旧值冲掉
    async with _REFRESH_STATE_LOCK:
        async with async_session_factory() as session:
            current = await session.execute(
                select(User.active_refresh_jtis).where(User.id == user.id)
            )
            active_jtis = list(current.scalar_one() or [])
            active_jtis.append(refresh_jti)
            await session.execute(
                update(User)
                .where(User.id == user.id)
                .values(active_refresh_jtis=active_jtis[-_MAX_ACTIVE_REFRESH_JTIS:])
            )
            await session.commit()

    logger.success(f"[Auth] 用户登录成功: username={body.username}")

    return ok(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
        message="登录成功",
    )


@router.post("/refresh")
@limiter.limit(RATE_AUTH)
async def refresh_token(request: Request, body: RefreshRequest):
    """刷新 Access Token（refresh 轮换 + 重用检测）。

    每次刷新签发新 refresh token（携带新 jti），旧 jti 随即移出存活名单立即失效；
    检测到名单外 jti（已轮换/已吊销的 token 被重放）时递增 token_version，
    吊销该用户全部 refresh/access token，防泄露后的静默续用。
    兼容说明：升级前签发的 refresh token 无 jti 声明，首次刷新按旧值放行并纳入轮换。
    """
    # 验证 refresh_token（expected_type="refresh"：access token 不能用于刷新）
    try:
        payload = jwt_verify_token(body.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise AuthenticationError(f"Refresh token 无效: {exc.message}")

    # 检查 token type（verify_token 已校验，此处兜底防御）
    if payload.get("type") != "refresh":
        raise AuthenticationError("无效的令牌类型，需要 refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("令牌中缺少用户信息")

    async with _REFRESH_STATE_LOCK:
        async with async_session_factory() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

        if not user:
            raise AuthenticationError("用户不存在")
        if not user.is_active:
            raise AuthenticationError("用户已被禁用")

        # 比对 token_version：登出/吊销后旧 refresh token 不能再换取新 access token
        # （兼容说明：升级前签发的 refresh token 无 ver 声明，按 1 处理；已登出的用户需重新登录）
        if int(payload.get("ver", 1) or 1) != user.token_version:
            raise AuthenticationError("令牌已失效，请重新登录")

        # 重用检测：jti 不在存活名单 = 已轮换/已吊销的 refresh 被重放
        # → 递增 token_version 吊销该用户全部 refresh 与 access token（fail-closed）
        jti = payload.get("jti")
        active_jtis = list(user.active_refresh_jtis or [])
        if jti is None and not active_jtis:
            # 升级前签发的无 jti 旧 refresh：仅当名单为空（升级后尚无新登录）时
            # 走此兼容路径放行一次，本次刷新即纳入轮换名单
            pass
        elif jti not in active_jtis:
            # 含名单非空时出现的无 jti 旧 token：与重放同口径 fail-closed 处理
            # （窄列原子更新：版本号 DB 侧 +1，不回写整行避免覆盖并发变更）
            async with async_session_factory() as session:
                await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(token_version=User.token_version + 1, active_refresh_jtis=[])
                )
                await session.commit()

            # 立即清除认证中间件的版本缓存，吊销不留 TTL 残留窗口
            from app.security.auth.middleware import invalidate_token_version_cache

            invalidate_token_version_cache(user_id)
            logger.warning(
                f"[Auth] 检测到 refresh token 重用，已吊销该用户全部会话: "
                f"user_id={user_id}, jti={jti}"
            )
            raise AuthenticationError("检测到令牌重用，全部会话已吊销，请重新登录")

        # 轮换：签发新 refresh token（新 jti），旧 jti 移出存活名单立即失效
        device_id = payload.get("device_id", "")
        roles = ["user"]

        access_token = create_access_token(
            user_id=user.id,
            device_id=device_id,
            roles=roles,
            token_version=user.token_version,
        )
        new_refresh_token, new_jti = create_refresh_token(
            user_id=user.id,
            device_id=device_id,
            token_version=user.token_version,
        )
        if jti in active_jtis:
            active_jtis.remove(jti)
        active_jtis.append(new_jti)
        async with async_session_factory() as session:
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(active_refresh_jtis=active_jtis[-_MAX_ACTIVE_REFRESH_JTIS:])
            )
            await session.commit()

        logger.info(f"[Auth] Refresh token 轮换完成: user_id={user_id}")

        return ok(
            {
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer",
            },
            message="刷新成功",
        )


@router.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    """登出（吊销当前设备 Token）。

    递增用户的 token_version，使旧 JWT 因版本不匹配而失效；
    同时清空 refresh jti 存活名单（全部 refresh token 随版本号一并失效）。
    """
    new_version = user.token_version + 1
    # 窄列更新：不回写整行，避免覆盖并发请求对其他列的变更
    async with async_session_factory() as session:
        await session.execute(
            update(User)
            .where(User.id == user.id)
            .values(token_version=new_version, active_refresh_jtis=[])
        )
        await session.commit()

    # 立即清除认证中间件的版本缓存，旧 token 不残留 TTL 窗口
    from app.security.auth.middleware import invalidate_token_version_cache

    invalidate_token_version_cache(user.id)

    logger.success(f"[Auth] 用户登出成功: username={user.username}, new_version={new_version}")

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
