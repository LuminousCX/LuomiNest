"""LuomiNest JWT 认证模块（预留）。

当前生产认证使用 app.security.auth.local_token.py 的本地共享令牌 +
secrets.compare_digest 常量时间比较模式，未启用 JWT。

本文件预留作为后续多用户/分布式场景下 JWT 签发与校验的实现入口，
依赖 pyproject.toml 中已声明的 python-jose[cryptography] 与 passlib[bcrypt]。
在补全实现前，请勿在主流程中 import 本模块。
"""
